"""PDF annual statement parser service.

AI-01: Smart multi-page classification (no AI) + batched vision model parsing.
AI-03: Per-type prompts with strict number formatting rules.
AI-04: Multi-broker prompt templates (IB / Futu / Schwab / Kraken).
AI-05: Ollama JSON Schema structured output constraints.

Renders PDF pages to PNG via PyMuPDF (200 DPI), classifies pages by keyword,
then sends relevant pages in batches to Ollama vision model for structured JSON extraction.
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
# Page classification keywords (AI-01)
# ---------------------------------------------------------------------------

POSITION_KEYWORDS = [
    "position", "holdings", "open position", "financial instrument",
    "持仓", "证券持仓", "资产明细", "投资组合",
]
TRADE_KEYWORDS = [
    "trade", "transaction", "activity", "execution",
    "成交", "交易记录", "委托记录",
]
CASH_KEYWORDS = [
    "cash balance", "net asset", "cash & equivalent",
    "现金余额", "净资产", "资金明细", "cash",
]
SUMMARY_KEYWORDS = [
    "account summary", "account information", "account overview",
    "账户摘要", "账户概览", "账户信息",
]
SKIP_KEYWORDS = [
    "disclosure", "risk warning", "important information", "legal notice",
    "风险提示", "免责声明", "声明",
]

_DPI = 100           # 100 DPI + JPEG compression ≈ 80KB/page (safe for local models)
_BATCH_SIZE = 1      # 1 page per AI call — avoids ReadTimeout on CPU/slow GPU
_JPEG_QUALITY = 85   # JPEG quality; 85 keeps table text legible, 5-10× smaller than PNG


# ---------------------------------------------------------------------------
# AI-04: Multi-broker prompt templates
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "/no_think "  # disable qwen3 thinking mode — prevents token explosion
    "You are a financial statement data extraction API. "
    "Output ONLY valid JSON. No prose, no markdown fences, no explanation."
)

# AI-03: Strict number formatting rules in all prompts
_NUMBER_RULES = """
Number formatting rules (STRICT):
1. Remove thousand separators: 2,500 → 2500
2. Keep negative sign: -1,234.56 → -1234.56
3. If a number is unclear or missing, output null — do NOT guess
4. Quantities for stocks/ETFs: integer preferred
5. Quantities for crypto: keep up to 8 decimal places
6. Prices: keep 2-4 decimal places
7. One row = one security — do NOT merge or split rows
"""

SUMMARY_PROMPT = f"""
Extract account information from this broker statement image. Return a single JSON object:
{{
  "account_info": {{"account_no": "", "broker": "", "base_currency": ""}},
  "statement_end_date": "YYYY-MM-DD",
  "capital_events": [{{"date": "YYYY-MM-DD", "type": "deposit|withdrawal", "amount": 0, "currency": "", "note": ""}}]
}}

{_NUMBER_RULES}
Return ONLY the JSON object.
"""

POSITION_PROMPT = f"""
你是专业券商账单数据提取助手。从图片中提取持仓表格，输出 JSON 对象。

{_NUMBER_RULES.replace('Number formatting rules (STRICT):', '数字规则（严格执行）：')}

输出格式：
{{
  "positions": [
    {{
      "asset_code":    "AAPL",
      "asset_name":    "Apple Inc.",
      "quantity":      300,
      "average_cost":  182.50,
      "currency":      "USD",
      "market_price":  195.20,
      "market_value":  58560.00,
      "unrealized_pnl": 3810.00,
      "asset_type":    "stock"
    }}
  ]
}}

只输出 JSON 对象，不要任何解释文字。
"""

CASH_PROMPT = f"""
Extract cash balances from this broker statement image. Return a JSON object:
{{
  "cash_balances": [{{"currency": "USD", "balance": 12345.67}}]
}}

{_NUMBER_RULES}
Return ONLY the JSON object.
"""

TRADE_PROMPT = f"""
Extract trade/transaction records from this broker statement image. Return a JSON object:
{{
  "trades": [
    {{
      "date": "YYYY-MM-DD",
      "asset_code": "AAPL",
      "side": "buy|sell",
      "quantity": 100,
      "price": 182.50,
      "currency": "USD",
      "commission": 1.00
    }}
  ]
}}

{_NUMBER_RULES}
Return ONLY the JSON object.
"""

# AI-04: Broker-specific variants override default prompts
_BROKER_POSITION_HINTS = {
    "interactive brokers": "Focus on the 'Financial Instrument Summary' section. Asset codes are in the 'Symbol' column.",
    "ib": "Focus on the 'Financial Instrument Summary' section. Asset codes are in the 'Symbol' column.",
    "futu": "Statement is bilingual (Chinese/English). Extract Hong Kong stocks (e.g. 00700.HK) and US stocks separately. asset_code format: AAPL for US, 00700 for HK.",
    "moomoo": "Statement is bilingual (Chinese/English). Extract Hong Kong stocks (e.g. 00700.HK) and US stocks separately.",
    "schwab": "Standard US broker format. Verify quantity column alignment carefully.",
    "charles schwab": "Standard US broker format. Verify quantity column alignment carefully.",
    "kraken": "Crypto exchange. Include staking positions with asset_type='crypto'. Quantity precision up to 8 decimal places.",
}


def _get_position_prompt(broker_hint: str = "") -> str:
    """Return position prompt, optionally with broker-specific instructions."""
    extra = ""
    broker_lower = broker_hint.lower() if broker_hint else ""
    for key, hint in _BROKER_POSITION_HINTS.items():
        if key in broker_lower:
            extra = f"\nBroker-specific instruction: {hint}\n"
            break
    return POSITION_PROMPT + extra


# ---------------------------------------------------------------------------
# AI-05: JSON Schema constraints for structured output
# ---------------------------------------------------------------------------

_POSITION_SCHEMA = {
    "type": "object",
    "properties": {
        "positions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["asset_code", "quantity", "currency"],
                "properties": {
                    "asset_code":    {"type": "string"},
                    "asset_name":    {"type": "string"},
                    "quantity":      {"type": "number"},
                    "average_cost":  {"type": ["number", "null"]},
                    "currency":      {"type": "string", "enum": ["USD", "HKD", "CNY", "EUR", "GBP", "SGD", "AUD", "JPY"]},
                    "market_price":  {"type": ["number", "null"]},
                    "market_value":  {"type": ["number", "null"]},
                    "unrealized_pnl": {"type": ["number", "null"]},
                    "asset_type":    {"type": "string", "enum": ["stock", "etf", "crypto", "fund", "option", "bond"]},
                },
            },
        }
    },
}

_CASH_SCHEMA = {
    "type": "object",
    "properties": {
        "cash_balances": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["currency", "balance"],
                "properties": {
                    "currency": {"type": "string"},
                    "balance":  {"type": "number"},
                },
            },
        }
    },
}

_SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "account_info": {
            "type": "object",
            "properties": {
                "account_no":    {"type": "string"},
                "broker":        {"type": "string"},
                "base_currency": {"type": "string"},
            },
        },
        "statement_end_date": {"type": "string"},
        "capital_events": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "date":     {"type": "string"},
                    "type":     {"type": "string", "enum": ["deposit", "withdrawal"]},
                    "amount":   {"type": "number"},
                    "currency": {"type": "string"},
                    "note":     {"type": "string"},
                },
            },
        },
    },
}

_PROMPT_MAP = {
    "summary":   (SUMMARY_PROMPT,  _SUMMARY_SCHEMA),
    "positions": (POSITION_PROMPT, _POSITION_SCHEMA),
    "cash":      (CASH_PROMPT,     _CASH_SCHEMA),
    "trades":    (TRADE_PROMPT,    None),
}


# ---------------------------------------------------------------------------
# AI-01: Page classification
# ---------------------------------------------------------------------------

def classify_pages(pdf_bytes: bytes) -> dict:
    """
    Lightweight full-doc scan using fitz text extraction (no AI).
    Returns page indices grouped by content type.
    """
    try:
        import fitz
    except ImportError:
        raise RuntimeError("PyMuPDF is not installed. Run: pip install pymupdf")

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages: dict[str, list[int]] = {
        "summary":   [],
        "positions": [],
        "trades":    [],
        "cash":      [],
    }

    for i, page in enumerate(doc):
        text = page.get_text("text").lower()

        # Skip pure disclaimer / disclosure pages
        if any(kw in text for kw in SKIP_KEYWORDS) and len(text) < 2000:
            logger.debug("Page %d: skip (disclosure)", i)
            continue

        if any(kw in text for kw in POSITION_KEYWORDS):
            pages["positions"].append(i)
        elif any(kw in text for kw in TRADE_KEYWORDS):
            pages["trades"].append(i)
        elif any(kw in text for kw in CASH_KEYWORDS):
            pages["cash"].append(i)
        elif i < 3:
            pages["summary"].append(i)

    logger.info(
        "Page classification: summary=%s positions=%s trades=%s cash=%s",
        pages["summary"], pages["positions"], pages["trades"], pages["cash"],
    )
    return pages


# ---------------------------------------------------------------------------
# AI-01: PDF → images
# ---------------------------------------------------------------------------

def render_pages_to_images(pdf_bytes: bytes, page_indices: list[int], dpi: int = _DPI) -> list[str]:
    """Render specified PDF pages to JPEG (compressed), return list of base64-encoded strings.

    JPEG at quality=85 is ~5-10× smaller than PNG, dramatically reducing
    the payload sent to the vision model and preventing ReadTimeout.
    """
    try:
        import fitz
    except ImportError:
        raise RuntimeError("PyMuPDF is not installed. Run: pip install pymupdf")

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    scale = dpi / 72.0
    mat = fitz.Matrix(scale, scale)
    images: list[str] = []

    for i in page_indices:
        if i >= len(doc):
            continue
        pix = doc[i].get_pixmap(matrix=mat, colorspace=fitz.csRGB)
        # Encode as JPEG for compact payload; fall back to PNG on error
        try:
            img_bytes = pix.tobytes("jpeg", jpg_quality=_JPEG_QUALITY)
        except Exception:
            img_bytes = pix.tobytes("png")
        images.append(base64.b64encode(img_bytes).decode())
        kb = len(img_bytes) // 1024
        logger.info("Page %d rendered: %d DPI, %d KB", i, dpi, kb)

    return images


def _batch(lst: list, size: int):
    for i in range(0, len(lst), size):
        yield lst[i : i + size]


# ---------------------------------------------------------------------------
# AI call (AI-05: JSON Schema structured output)
# ---------------------------------------------------------------------------

async def ask_ai(
    images_b64: list[str],
    prompt_type: str = "positions",
    broker_hint: str = "",
) -> dict:
    """Send images to Ollama vision model with JSON Schema constraint."""
    if prompt_type == "positions":
        user_prompt = _get_position_prompt(broker_hint)
        schema = _POSITION_SCHEMA
    else:
        user_prompt, schema = _PROMPT_MAP.get(prompt_type, (POSITION_PROMPT, _POSITION_SCHEMA))

    ollama_base = settings.ollama_base_url
    model = settings.ollama_model

    payload: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": user_prompt,
                "images": images_b64,
            },
        ],
        "stream": True,   # streaming: each token resets the read-timeout clock
        "think": False,   # suppress qwen3 reasoning chain
        "options": {"temperature": 0.1, "num_ctx": 8192, "num_predict": 2048},
    }

    # AI-05: attach JSON Schema if supported (Ollama >= 0.5 for object format)
    if schema is not None:
        payload["format"] = schema

    logger.info(
        "Sending %d image(s) to %s / %s [type=%s]",
        len(images_b64), ollama_base, model, prompt_type,
    )

    # Use per-chunk timeout: model only needs to produce a token every 120s
    _timeout = httpx.Timeout(connect=30.0, read=120.0, write=120.0, pool=30.0)
    raw_parts: list[str] = []

    async with httpx.AsyncClient(timeout=_timeout) as client:
        async with client.stream("POST", f"{ollama_base}/api/chat", json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                delta = chunk.get("message", {}).get("content", "")
                if delta:
                    raw_parts.append(delta)
                if chunk.get("done"):
                    break

    raw = "".join(raw_parts)

    logger.info("Vision model raw (first 400): %s", raw[:400])
    return _parse_json_response(raw)


# ---------------------------------------------------------------------------
# AI-01: Smart multi-page orchestrator
# ---------------------------------------------------------------------------

async def parse_pdf_smart(pdf_bytes: bytes) -> dict:
    """
    Full smart PDF parser:
    1. Classify all pages by content (no AI).
    2. Parse summary / positions (batched) / cash pages.
    3. Merge duplicate positions (weighted average cost).
    """
    pages = classify_pages(pdf_bytes)

    result: dict = {
        "account_info":      {},
        "statement_end_date": None,
        "positions":         [],
        "cash_balances":     [],
        "capital_events":    [],
        "trades":            [],
        "parsing_confidence": "high",
        "page_classification": {k: v for k, v in pages.items()},
    }

    broker_hint = ""

    # 1. Summary pages → account_info + capital_events
    if pages["summary"]:
        imgs = render_pages_to_images(pdf_bytes, pages["summary"])
        r = await ask_ai(imgs, prompt_type="summary")
        result["account_info"]      = r.get("account_info", {})
        result["statement_end_date"] = r.get("statement_end_date")
        result["capital_events"]    = r.get("capital_events", [])
        broker_hint = (result["account_info"].get("broker") or "").lower()

    # 2. Position pages (batched, each batch ≤ _BATCH_SIZE pages)
    for batch_indices in _batch(pages["positions"], _BATCH_SIZE):
        imgs = render_pages_to_images(pdf_bytes, batch_indices)
        r = await ask_ai(imgs, prompt_type="positions", broker_hint=broker_hint)
        result["positions"].extend(r.get("positions", []))

    # 3. Cash pages (up to 3 pages)
    if pages["cash"]:
        imgs = render_pages_to_images(pdf_bytes, pages["cash"][:3])
        r = await ask_ai(imgs, prompt_type="cash")
        result["cash_balances"] = r.get("cash_balances", [])

    # 4. Trade pages (up to 3 batches)
    trade_batches = list(_batch(pages["trades"], _BATCH_SIZE))[:3]
    for batch_indices in trade_batches:
        imgs = render_pages_to_images(pdf_bytes, batch_indices)
        r = await ask_ai(imgs, prompt_type="trades")
        result["trades"].extend(r.get("trades", []))

    # 5. Merge duplicate positions
    result["positions"] = _merge_positions(result["positions"])

    if not result["positions"] and not result["cash_balances"]:
        result["parsing_confidence"] = "low"
    elif len(result["positions"]) < 3:
        result["parsing_confidence"] = "medium"

    return result


# Keep legacy entry point name so existing routes.py import still works
async def parse_pdf_with_ai(pdf_bytes: bytes) -> dict:
    """Entry point called by routes.py background task."""
    return await parse_pdf_smart(pdf_bytes)


# ---------------------------------------------------------------------------
# Position merging (AI-01: same asset_code across pages → weighted avg cost)
# ---------------------------------------------------------------------------

def _merge_positions(positions: list[dict]) -> list[dict]:
    """Deduplicate positions by asset_code, computing weighted average cost."""
    merged: dict[str, dict] = {}

    for pos in positions:
        code = str(pos.get("asset_code") or "").strip().upper()
        if not code:
            continue

        qty = pos.get("quantity")
        cost = pos.get("average_cost")

        if code not in merged:
            merged[code] = dict(pos)
            merged[code]["asset_code"] = code
        else:
            existing = merged[code]
            old_qty = existing.get("quantity") or 0
            new_qty = qty or 0
            total_qty = old_qty + new_qty

            # Weighted average cost
            if total_qty and cost is not None and existing.get("average_cost") is not None:
                existing["average_cost"] = (
                    (existing["average_cost"] * old_qty + cost * new_qty) / total_qty
                )
            elif cost is not None:
                existing["average_cost"] = cost

            existing["quantity"] = total_qty

            # Sum market values if present
            if pos.get("market_value") is not None and existing.get("market_value") is not None:
                existing["market_value"] = (existing["market_value"] or 0) + (pos["market_value"] or 0)

    return list(merged.values())


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

    # Find first complete JSON object or array
    if not raw.startswith(("{", "[")):
        m = re.search(r"[\[{][\s\S]*[\]}]", raw)
        if m:
            raw = m.group(0)

    try:
        parsed = json.loads(raw)
        # If root is a list, wrap it
        if isinstance(parsed, list):
            return {"positions": parsed}
        return parsed
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
    data = batch.parsed_result
    return {
        "id": batch.id,
        "account_id": batch.account_id,
        "snapshot_date": batch.snapshot_date.isoformat() if batch.snapshot_date else None,
        "filename": batch.filename,
        "status": batch.status,
        "failed_reason": batch.failed_reason,
        "ai_model": batch.ai_model,
        "parsed_data": data,
        "confirmed_data": batch.confirmed_result,
        "pending_deposits": batch.pending_deposit_rows,
        "validation": data.get("_validation") if data else None,
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
        avg_cost = Decimal(str(p.get("average_cost", 0) or 0))
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
