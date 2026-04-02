"""futu_parser.py — Futu / Moomoo CSV export parser (V4.3).

File format characteristics:
- Simple flat CSV, one row per partial fill
- Direction column (方向): 买入 / 卖出 = new order row; empty = continuation row (partial fill)
- Numbers may contain thousand-separators (2,500)
- Timestamps include timezone annotation e.g. "2019-04-01 09:30:00 美东时间"

Key column names (Chinese):
  方向 / 代码 / 名称 / 市场 / 币种 / 成交数量 / 成交价格 / 成交金额
  成交时间 / 佣金 / 平台使用费 / 交收费 / 消费税 / 合计费用
"""
from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime
from typing import Optional

from app.services.parser.base_parser import TransactionRow

# Futu column aliases (Chinese → internal key)
_FUTU_COL_MAP = {
    "方向":     "direction",
    "代码":     "asset_code",
    "名称":     "asset_name",
    "市场":     "market",
    "币种":     "currency",
    "成交数量":  "filled_qty",
    "成交价格":  "avg_price",
    "成交金额":  "filled_amount",
    "成交时间":  "trade_time",
    "佣金":     "commission",
    "平台使用费": "platform_fee",
    "交收费":   "clearing_fee",
    "消费税":   "tax",
    "合计费用":  "total_fee",
    # English aliases (Moomoo EN export)
    "direction":     "direction",
    "code":          "asset_code",
    "name":          "asset_name",
    "market":        "market",
    "currency":      "currency",
    "qty":           "filled_qty",
    "avg. price":    "avg_price",
    "amount":        "filled_amount",
    "time":          "trade_time",
    "commission":    "commission",
    "platform fee":  "platform_fee",
    "settlement fee":"clearing_fee",
    "stamp duty":    "tax",
    "total fees":    "total_fee",
}

# Required Chinese columns to identify Futu format
_FUTU_REQUIRED = {"方向", "代码", "成交数量", "成交金额"}


def _clean_number(s: str) -> float:
    """Remove thousand separators, handle empty / dash."""
    if not s or s.strip() in ("", "-", "--", "N/A"):
        return 0.0
    cleaned = re.sub(r"[,，\s]", "", s.strip())
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def parse_futu_datetime(s: str) -> date:
    """
    Parse Futu timestamp strings.
    Handles: "2019-04-01 09:30:00 美东时间"
             "2019/04/01 09:30:00"
             "2019-04-01"
    """
    if not s:
        return date.today()
    # Strip trailing timezone annotation (Chinese or English)
    s = re.sub(r"\s+[\u4e00-\u9fff]+.*$", "", s.strip())
    s = re.sub(r"\s+[A-Z]{2,5}$", "", s.strip())
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%d",
        "%Y/%m/%d",
    ):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    # Last resort: take the first date-like token
    m = re.search(r"(\d{4})[-/](\d{2})[-/](\d{2})", s)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return date.today()


def _identify_asset_type(asset_code: str, asset_name: str, market: str) -> str:
    code = asset_code.upper()
    name = asset_name.lower()
    # Option pattern: e.g. AAPL240119C00185000 or NIO 241115C4000
    if re.search(r"[CP]\d{4,}", code) or re.search(r"\d{6}[CP]\d+", code):
        return "option"
    if "etf" in name or "fund" in name or "trust" in name:
        return "etf"
    return "stock"


def _futu_row_to_tx(row: dict) -> TransactionRow:
    is_buy = row["direction"] == "买入"
    market = row.get("market", "")
    exchange = "HK" if "港" in market else "US"

    qty = row["filled_qty"]
    amount = row["filled_amount"]
    currency = row.get("currency", "USD").strip()

    # Gross amount: buy = negative (cash outflow), sell = positive (cash inflow)
    gross = -amount if is_buy else amount

    # Fee decomposition (all stored as negative numbers)
    commission = -abs(row.get("commission", 0))
    transaction_fee = -abs(row.get("clearing_fee", 0)) + (-abs(row.get("tax", 0)))
    other_fee = -abs(row.get("platform_fee", 0))

    asset_code = row.get("asset_code", "").strip()
    asset_name = row.get("asset_name", "").strip()

    return TransactionRow(
        tx_category=   "TRADE",
        tx_type=       "stock_buy" if is_buy else "stock_sell",
        trade_date=    parse_futu_datetime(row.get("trade_time", "")),
        currency=      currency,
        asset_code=    asset_code,
        asset_name=    asset_name,
        exchange=      exchange,
        asset_type=    _identify_asset_type(asset_code, asset_name, market),
        quantity=      qty,
        price=         row.get("avg_price", 0),
        gross_amount=  gross,
        commission=    commission if commission != 0 else None,
        transaction_fee= transaction_fee if transaction_fee != 0 else None,
        other_fee=     other_fee if other_fee != 0 else None,
        description=   f"{'买入' if is_buy else '卖出'} {asset_code} {asset_name}",
    )


def parse_futu_trades(rows: list[dict]) -> list[TransactionRow]:
    """
    Parse Futu trade rows with partial-fill merging.
    A new order starts when direction is 买入/卖出.
    A continuation row (direction == "") merges into the previous order.
    """
    results = []
    pending: Optional[dict] = None

    for row in rows:
        direction = row.get("direction", "").strip()

        if direction in ("买入", "卖出"):
            # Save previous pending order
            if pending is not None:
                results.append(_futu_row_to_tx(pending))

            pending = {
                "direction":    direction,
                "asset_code":   row.get("asset_code", ""),
                "asset_name":   row.get("asset_name", ""),
                "market":       row.get("market", ""),
                "currency":     row.get("currency", "USD"),
                "filled_qty":   _clean_number(row.get("filled_qty", "0")),
                "avg_price":    _clean_number(row.get("avg_price", "0")),
                "filled_amount":_clean_number(row.get("filled_amount", "0")),
                "trade_time":   row.get("trade_time", ""),
                "commission":   _clean_number(row.get("commission", "0")),
                "platform_fee": _clean_number(row.get("platform_fee", "0")),
                "clearing_fee": _clean_number(row.get("clearing_fee", "0")),
                "tax":          _clean_number(row.get("tax", "0")),
                "total_fee":    _clean_number(row.get("total_fee", "0")),
            }

        elif direction == "" and pending is not None:
            # Continuation row: accumulate qty + amount, recalculate avg price
            extra_qty    = _clean_number(row.get("filled_qty", "0"))
            extra_amount = _clean_number(row.get("filled_amount", "0"))
            pending["filled_qty"]    += extra_qty
            pending["filled_amount"] += extra_amount
            if pending["filled_qty"] > 0:
                pending["avg_price"] = pending["filled_amount"] / pending["filled_qty"]
            # Accumulate fees
            pending["commission"]   += _clean_number(row.get("commission", "0"))
            pending["platform_fee"] += _clean_number(row.get("platform_fee", "0"))
            pending["clearing_fee"] += _clean_number(row.get("clearing_fee", "0"))
            pending["tax"]          += _clean_number(row.get("tax", "0"))
            pending["total_fee"]    += _clean_number(row.get("total_fee", "0"))

    if pending is not None:
        results.append(_futu_row_to_tx(pending))

    return results


def preprocess(raw: bytes) -> bytes:
    """
    Detect and parse Futu CSV.
    Returns raw bytes unchanged if format is not recognised.
    This maintains compatibility with the import_service pipeline.
    """
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = raw.decode("gbk")
        except UnicodeDecodeError:
            return raw

    reader = csv.reader(io.StringIO(text))
    rows_raw = list(reader)
    if len(rows_raw) < 2:
        return raw

    # Find header row (first non-empty row)
    header_row_idx = 0
    for i, r in enumerate(rows_raw):
        if any(c.strip() for c in r):
            header_row_idx = i
            break

    header = [c.strip() for c in rows_raw[header_row_idx]]
    header_set = set(header)

    # Identify Futu format by required columns
    if not _FUTU_REQUIRED.issubset(header_set):
        return raw  # Not a Futu file

    # Map columns
    col_idx: dict[str, int] = {}
    for i, h in enumerate(header):
        internal = _FUTU_COL_MAP.get(h.lower(), _FUTU_COL_MAP.get(h))
        if internal:
            col_idx[internal] = i

    if "direction" not in col_idx or "filled_qty" not in col_idx:
        return raw

    # Parse data rows into dicts
    data_rows = []
    for row in rows_raw[header_row_idx + 1:]:
        if not row or not any(c.strip() for c in row):
            continue
        d: dict = {}
        for key, idx in col_idx.items():
            d[key] = row[idx].strip() if idx < len(row) else ""
        data_rows.append(d)

    if not data_rows:
        return raw

    tx_rows = parse_futu_trades(data_rows)
    if not tx_rows:
        return raw

    # Emit as standard CSV for downstream import_service
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow([
        "trade_date", "asset_code", "asset_name", "quantity", "price",
        "currency", "tx_type", "gross_amount", "commission",
        "transaction_fee", "other_fee", "exchange", "asset_type", "description",
    ])
    for t in tx_rows:
        writer.writerow([
            t.trade_date.isoformat(),
            t.asset_code or "",
            t.asset_name or "",
            t.quantity or "",
            t.price or "",
            t.currency,
            t.tx_type,
            t.gross_amount if t.gross_amount is not None else "",
            t.commission if t.commission is not None else "",
            t.transaction_fee if t.transaction_fee is not None else "",
            t.other_fee if t.other_fee is not None else "",
            t.exchange or "",
            t.asset_type or "",
            t.description or "",
        ])

    return out.getvalue().encode("utf-8")
