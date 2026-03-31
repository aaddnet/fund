"""PDF annual statement parser service.

Renders PDF pages to images via PyMuPDF, then sends them to a local
Ollama vision model (qwen2-vl) for structured JSON extraction.
"""
from __future__ import annotations

import base64
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
    "You are a financial statement data extraction API. "
    "Output ONLY valid JSON. No prose, no markdown fences, no explanation."
)

_USER_PROMPT = """\
Extract all financial data from this broker statement image and return a single JSON object with:
- account_info: {account_no, broker, base_currency}
- statement_end_date: YYYY-MM-DD
- positions: [{asset_code, asset_name, quantity, average_cost, currency, market_value, asset_type}]
- cash_balances: [{currency, balance}]
- capital_events: [{date, type (deposit/withdrawal), amount, currency, note}]
- parsing_confidence: "high" | "medium" | "low"

Return ONLY the JSON object, nothing else.
"""

# ---------------------------------------------------------------------------
# PDF → images
# ---------------------------------------------------------------------------

_DPI = 100          # 100 DPI keeps image size ~100 KB/page, manageable for vision model
_MAX_PAGES = 3      # first 3 pages cover account summary + positions + cash


def render_pdf_pages(pdf_bytes: bytes) -> list[str]:
    """
    Render PDF pages to PNG and return list of base64-encoded strings.
    Limits to _MAX_PAGES to keep Ollama request size manageable.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise RuntimeError("PyMuPDF is not installed. Run: pip install pymupdf")

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images_b64: list[str] = []
    mat = fitz.Matrix(_DPI / 72, _DPI / 72)   # scale factor from 72dpi base

    for i, page in enumerate(doc):
        if i >= _MAX_PAGES:
            break
        pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
        png_bytes = pix.tobytes("png")
        images_b64.append(base64.b64encode(png_bytes).decode())

    logger.info("Rendered %d PDF page(s) at %d dpi", len(images_b64), _DPI)
    return images_b64


# ---------------------------------------------------------------------------
# AI parsing via vision model
# ---------------------------------------------------------------------------

async def parse_pdf_with_ai(pdf_bytes: bytes) -> dict:
    """Send rendered PDF page images to Ollama vision model, return parsed JSON."""
    images_b64 = render_pdf_pages(pdf_bytes)
    if not images_b64:
        raise ValueError("PDF rendered 0 pages.")

    ollama_base = settings.ollama_base_url
    model = settings.ollama_model

    # Ollama vision API: images attached to the user message
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": _USER_PROMPT,
                "images": images_b64,
            },
        ],
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 2048, "num_ctx": 8192},
    }

    logger.info("Sending %d image(s) to %s / %s", len(images_b64), ollama_base, model)
    async with httpx.AsyncClient(timeout=600.0) as client:
        resp = await client.post(f"{ollama_base}/api/chat", json=payload)
        resp.raise_for_status()
        raw = resp.json()["message"]["content"]

    logger.info("Vision model raw (first 400): %s", raw[:400])
    return _parse_json_response(raw)


# ---------------------------------------------------------------------------
# JSON extraction helpers
# ---------------------------------------------------------------------------

def _parse_json_response(raw: str) -> dict:
    """Strip think tags + markdown fences, extract first JSON object."""
    # Remove <think>...</think> reasoning blocks
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

    # Strip markdown code fences
    if raw.startswith("```"):
        lines = raw.split("\n")
        inner = lines[1:] if lines[0].startswith("```") else lines
        if inner and inner[-1].strip() == "```":
            inner = inner[:-1]
        raw = "\n".join(inner).strip()

    # Find first complete JSON object
    if not raw.startswith("{"):
        m = re.search(r"\{[\s\S]*\}", raw)
        if m:
            raw = m.group(0)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        recovered = _recover_truncated_json(raw)
        if recovered:
            return recovered
        logger.warning("JSON parse failed | raw: %s", raw[:500])
        return {"parse_error": True, "raw_text": raw[:1000]}


def _recover_truncated_json(raw: str) -> dict | None:
    """Walk back from last } to find the longest parseable prefix."""
    pos = len(raw) - 1
    while pos > 0:
        pos = raw.rfind("}", 0, pos + 1)
        if pos < 0:
            break
        try:
            return json.loads(raw[: pos + 1])
        except json.JSONDecodeError:
            pos -= 1
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
