"""PDF annual statement parser service.

Extracts text from PDF using PyMuPDF, then calls a local Ollama-compatible
LLM to produce structured JSON with positions, cash balances, and capital events.
"""
from __future__ import annotations

import json
import logging
import re
from decimal import Decimal

import httpx

from app.core.config import settings
from app.models import CashPosition, PdfImportBatch, Position

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are a financial data extraction API. "
    "Output ONLY valid JSON. No prose, no markdown, no explanation."
)

_USER_TEMPLATE = """\
Extract structured data from this broker statement and return JSON with exactly these fields:
- account_info: {account_no, broker, base_currency}
- statement_end_date: YYYY-MM-DD string
- positions: array of {asset_code, asset_name, quantity, average_cost, currency, market_value, asset_type}
- cash_balances: array of {currency, balance}
- capital_events: array of {date, type (deposit/withdrawal), amount, currency, note}
- parsing_confidence: "high", "medium", or "low"

Statement text:
{pdf_text}
"""

# ---------------------------------------------------------------------------
# PDF text extraction + smart section trimming
# ---------------------------------------------------------------------------

# IBKR and common broker section keywords to extract
_SECTION_KEYWORDS = [
    "open position", "positions", "cash report", "ending cash",
    "cash balance", "deposit", "withdrawal", "account information",
    "account summary", "net asset value", "total equity",
    "statement of", "portfolio", "holdings",
]

_MAX_SECTION_CHARS = 2000   # per section
_MAX_TOTAL_CHARS = 3000     # total input to LLM — keep within thinking model token budget


def extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract text from PDF bytes using PyMuPDF (fitz)."""
    try:
        import fitz  # type: ignore[import]
    except ImportError:
        raise RuntimeError("PyMuPDF (fitz) is not installed. Run: pip install pymupdf")

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    for i, page in enumerate(doc):
        blocks = page.get_text("blocks")
        page_text = "\n".join(b[4] for b in blocks if b[6] == 0)
        pages.append(page_text)
    return "\n\n".join(pages)


def _extract_key_sections(full_text: str) -> str:
    """
    Pull only the financially relevant sections from a full statement text.
    Looks for known section headers and grabs up to _MAX_SECTION_CHARS chars after each.
    Falls back to a plain truncation if no sections found.
    """
    lines = full_text.splitlines()
    collected: list[str] = []
    total = 0
    in_section = False
    section_chars = 0

    for line in lines:
        lower = line.lower()
        is_header = any(kw in lower for kw in _SECTION_KEYWORDS)

        if is_header:
            in_section = True
            section_chars = 0

        if in_section:
            collected.append(line)
            section_chars += len(line) + 1
            total += len(line) + 1
            if section_chars >= _MAX_SECTION_CHARS:
                in_section = False
            if total >= _MAX_TOTAL_CHARS:
                break

    if total < 200:
        # No recognisable sections found — fall back to plain truncation
        return full_text[:_MAX_TOTAL_CHARS]

    return "\n".join(collected)


# ---------------------------------------------------------------------------
# AI parsing
# ---------------------------------------------------------------------------

async def parse_pdf_with_ai(pdf_bytes: bytes) -> dict:
    """Send key PDF sections to Ollama and return parsed JSON."""
    full_text = extract_pdf_text(pdf_bytes)
    text = _extract_key_sections(full_text)
    logger.info("PDF text: %d chars full → %d chars after section trim", len(full_text), len(text))

    ollama_base = settings.ollama_base_url
    model = settings.ollama_model

    user_content = _USER_TEMPLATE.replace("{pdf_text}", text)

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 4096, "num_ctx": 8192},
    }

    async with httpx.AsyncClient(timeout=300.0) as client:
        resp = await client.post(f"{ollama_base}/api/chat", json=payload)
        resp.raise_for_status()
        raw = resp.json()["message"]["content"]

    logger.info("Ollama raw (first 300): %s", raw[:300])
    return _parse_json_response(raw)


def _strip_think_tags(raw: str) -> str:
    return re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()


def _parse_json_response(raw: str) -> dict:
    """Strip think tags + markdown fences, extract first JSON object, parse."""
    raw = _strip_think_tags(raw)

    # Strip markdown code fences
    if raw.startswith("```"):
        lines = raw.split("\n")
        inner = lines[1:] if lines[0].startswith("```") else lines
        if inner and inner[-1].strip() == "```":
            inner = inner[:-1]
        raw = "\n".join(inner).strip()

    # If still doesn't start with {, scan for first JSON object
    if not raw.startswith("{"):
        m = re.search(r"\{[\s\S]*\}", raw)
        if m:
            raw = m.group(0)

    # Try to fix truncated JSON by finding the last complete top-level key
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Attempt to recover by truncating at the last complete field
        truncated = _recover_truncated_json(raw)
        if truncated:
            return truncated
        logger.warning("JSON parse failed | raw: %s", raw[:500])
        return {"parse_error": True, "raw_text": raw[:1000]}


def _recover_truncated_json(raw: str) -> dict | None:
    """Try progressively shorter strings until JSON parses (handles truncated output)."""
    # Find the last } and try parsing up to it
    last_brace = raw.rfind("}")
    while last_brace > 0:
        candidate = raw[:last_brace + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            last_brace = raw.rfind("}", 0, last_brace)
    return None


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


def serialize_pdf_batch(batch: PdfImportBatch) -> dict:
    return {
        "id": batch.id,
        "account_id": batch.account_id,
        "snapshot_date": batch.snapshot_date.isoformat() if batch.snapshot_date else None,
        "filename": batch.filename,
        "status": batch.status,
        "failed_reason": batch.failed_reason,
        "ai_model": batch.ai_model,
        "parsed_data": batch.parsed_result,
        "confirmed_data": batch.confirmed_result,
        "pending_deposits": batch.pending_deposit_rows,
        "created_at": batch.created_at.isoformat() if batch.created_at else None,
    }


def confirm_pdf_batch(db, batch_id: int) -> PdfImportBatch:
    """Write confirmed positions/cash into DB from a PDF batch."""
    batch = db.query(PdfImportBatch).filter(PdfImportBatch.id == batch_id).first()
    if not batch:
        raise ValueError(f"PDF import batch {batch_id} not found.")
    if batch.status not in ("parsed", "confirmed"):
        raise ValueError("Only parsed batches can be confirmed.")

    data = batch.confirmed_result if batch.confirmed_result else batch.parsed_result
    if not data:
        raise ValueError("No parsed data found.")

    snap_date = batch.snapshot_date

    for p in data.get("positions", []):
        asset_code = str(p.get("asset_code", "")).strip().upper()
        if not asset_code:
            continue
        qty = Decimal(str(p.get("quantity", 0)))
        avg_cost = Decimal(str(p.get("average_cost", 0)))
        currency = str(p.get("currency", "USD")).upper()
        existing = db.query(Position).filter_by(
            account_id=batch.account_id, asset_code=asset_code, snapshot_date=snap_date
        ).first()
        if existing:
            existing.quantity = qty
            existing.average_cost = avg_cost
            existing.currency = currency
        else:
            db.add(Position(
                account_id=batch.account_id,
                asset_code=asset_code,
                quantity=qty,
                average_cost=avg_cost,
                currency=currency,
                snapshot_date=snap_date,
            ))

    for c in data.get("cash_balances", []):
        currency = str(c.get("currency", "USD")).upper()
        amount = Decimal(str(c.get("balance", 0)))
        existing = db.query(CashPosition).filter_by(
            account_id=batch.account_id, currency=currency, snapshot_date=snap_date
        ).first()
        if existing:
            existing.amount = amount
        else:
            db.add(CashPosition(
                account_id=batch.account_id,
                currency=currency,
                amount=amount,
                snapshot_date=snap_date,
                note="pdf_import",
            ))

    capital_events = data.get("capital_events", [])
    if capital_events:
        batch.pending_deposits = json.dumps(capital_events)
        batch.status = "confirmed_pending_deposits"
    else:
        batch.status = "confirmed"

    db.commit()
    db.refresh(batch)
    return batch
