"""PDF annual statement parser service.

Extracts text from PDF using PyMuPDF, then calls a local Ollama-compatible
LLM (or Claude API as fallback) to produce structured JSON with positions,
cash balances, and capital events.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from decimal import Decimal

import httpx

from app.core.config import settings
from app.db import SessionLocal
from app.models import Account, CashPosition, PdfImportBatch, Position

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are a JSON-only financial data extraction API. "
    "Never write prose. Never explain. Output only the JSON continuation."
)

# /no_think suppresses qwen3 chain-of-thought; {pdf_text} is replaced via str.replace
_USER_TEMPLATE = """\
/no_think
From the broker statement below, fill in and return ONLY the following JSON (no extra text):

{
  "account_info": {"account_no": "", "broker": "", "base_currency": "USD"},
  "statement_end_date": "YYYY-MM-DD",
  "positions": [{"asset_code": "", "asset_name": "", "quantity": 0.0, "average_cost": 0.0, "currency": "USD", "market_value": 0.0, "asset_type": "stock"}],
  "cash_balances": [{"currency": "USD", "balance": 0.0}],
  "capital_events": [{"date": "", "type": "deposit", "amount": 0.0, "currency": "USD", "note": ""}],
  "parsing_confidence": "high"
}

Statement:
{pdf_text}
"""

# ---------------------------------------------------------------------------
# PDF text extraction
# ---------------------------------------------------------------------------


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
        page_text = f"--- 第{i + 1}页 ---\n" + "\n".join(b[4] for b in blocks if b[6] == 0)
        pages.append(page_text)
    return "\n\n".join(pages)


# ---------------------------------------------------------------------------
# AI parsing
# ---------------------------------------------------------------------------

_MAX_TEXT_CHARS = 24000


async def parse_pdf_with_ai(pdf_bytes: bytes) -> dict:
    """Send PDF text to Ollama/Claude API and return parsed JSON."""
    text = extract_pdf_text(pdf_bytes)
    if len(text) > _MAX_TEXT_CHARS:
        text = text[:_MAX_TEXT_CHARS] + " ...[截断]"

    ollama_base = getattr(settings, "ollama_base_url", None) or "http://ollama:11434"
    model = getattr(settings, "ollama_model", None) or "qwen3.5:latest"

    # Use str.replace instead of .format() to avoid KeyError when PDF text contains { }
    user_content = _USER_TEMPLATE.replace("{pdf_text}", text)

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
            # Assistant priming: force the model to continue from '{' so it
            # cannot output prose before the JSON object.
            {"role": "assistant", "content": "{"},
        ],
        "stream": False,
        "think": False,            # Suppress CoT for qwen3/deepseek-r1
        "options": {"temperature": 0.1},
    }

    async with httpx.AsyncClient(timeout=300.0) as client:
        resp = await client.post(f"{ollama_base}/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
        # Prepend the priming character we sent as the assistant seed
        raw = "{" + data["message"]["content"]

    logger.info("Ollama raw response (first 200 chars): %s", raw[:200])
    return _parse_json_response(raw)


def _strip_think_tags(raw: str) -> str:
    """Remove <think>...</think> blocks produced by reasoning models."""
    import re
    # Non-greedy strip of all <think> blocks
    cleaned = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
    return cleaned.strip()


def _parse_json_response(raw: str) -> dict:
    """Strip thinking tags + markdown fences, then parse JSON."""
    # Step 1: remove <think> blocks (qwen3, deepseek-r1, etc.)
    raw = _strip_think_tags(raw)

    # Step 2: strip markdown code fences
    if raw.startswith("```"):
        lines = raw.split("\n")
        inner = lines[1:] if lines[0].startswith("```") else lines
        if inner and inner[-1].strip() == "```":
            inner = inner[:-1]
        raw = "\n".join(inner).strip()

    # Step 3: extract first JSON object/array if there's surrounding text
    import re
    if not raw.startswith(("{", "[")):
        match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", raw)
        if match:
            raw = match.group(1)

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning("JSON parse failed: %s | raw: %s", e, raw[:300])
        return {"parse_error": True, "raw_text": raw[:1000]}


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
    from sqlalchemy.orm import Session as _Session

    batch = db.query(PdfImportBatch).filter(PdfImportBatch.id == batch_id).first()
    if not batch:
        raise ValueError(f"PDF import batch {batch_id} not found.")
    if batch.status not in ("parsed", "confirmed"):
        raise ValueError("Only parsed batches can be confirmed.")

    data = batch.confirmed_result if batch.confirmed_result else batch.parsed_result
    if not data:
        raise ValueError("No parsed data found.")

    snap_date = batch.snapshot_date

    # Upsert positions
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

    # Upsert cash positions
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

    # Store capital events as pending deposits
    capital_events = data.get("capital_events", [])
    if capital_events:
        batch.pending_deposits = json.dumps(capital_events)
        batch.status = "confirmed_pending_deposits"
    else:
        batch.status = "confirmed"

    db.commit()
    db.refresh(batch)
    return batch
