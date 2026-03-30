"""
Moomoo (Futu) trade history parser.

Expected export: Trade → Filled Orders → Export as CSV.
Column names vary by app version and region; this parser normalises the most
common variants seen in US and HK account exports.

Common column sets:
  Version A (US):  Date, Symbol, Side, Qty., Avg. Price, Trading Fees, Status
  Version B (US):  Transaction Time, Symbol, Side, Qty., Avg. Price, Amount(USD), Fees, Status
  Version C (HK):  成交时间, 股票代码, 买卖, 成交数量, 成交均价, 手续费, 状态

Only rows with Status "Filled" (or equivalent) are imported.
Currency defaults to USD; override via the "Currency" column when present.
"""

import csv
import io
import re

# Identifies option contract codes, e.g. NIO241115C4000, TSLA240119P00200000
_OPTION_PATTERN = re.compile(r'^[A-Z]+\d{6}[CP]\d+$')

# Normalised column name → standard field name
_COL_ALIASES: dict[str, str] = {
    # Date / time
    "date": "trade_date",
    "transaction time": "trade_date",
    "time": "trade_date",
    "trade date": "trade_date",
    "filled time": "trade_date",
    "成交时间": "trade_date",
    # Asset
    "symbol": "asset_code",
    "stock code": "asset_code",
    "ticker": "asset_code",
    "code": "asset_code",
    "股票代码": "asset_code",
    "代码": "asset_code",
    # Side / direction
    "side": "tx_type",
    "direction": "tx_type",
    "buy/sell": "tx_type",
    "买卖": "tx_type",
    "方向": "tx_type",
    # Quantity
    "qty.": "quantity",
    "qty": "quantity",
    "quantity": "quantity",
    "shares": "quantity",
    "filled qty": "quantity",
    "成交数量": "quantity",
    # Filled amount (needed for weighted avg price on continuation rows)
    "amount(usd)": "filled_amount",
    "amount(hkd)": "filled_amount",
    "amount": "filled_amount",
    "成交金额": "filled_amount",
    "交易金额": "filled_amount",
    # Price
    "avg. price": "price",
    "avg price": "price",
    "price": "price",
    "price(usd)": "price",
    "price(hkd)": "price",
    "execution price": "price",
    "成交均价": "price",
    "成交价格": "price",
    # Fee
    "trading fees": "fee",
    "fees": "fee",
    "fee": "fee",
    "commission": "fee",
    "手续费": "fee",
    "合计费用": "fee",
    # Currency
    "currency": "currency",
    "ccy": "currency",
    "货币": "currency",
    # Status (used to filter filled orders)
    "status": "status",
    "order status": "status",
    "状态": "status",
    "交易状态": "status",
}

# Side values → standard tx_type
_SIDE_MAP: dict[str, str] = {
    "buy": "buy",
    "long": "buy",
    "买入": "buy",
    "买": "buy",
    "sell": "sell",
    "short": "sell",
    "卖出": "sell",
    "卖": "sell",
}

# Status values that indicate a completed/filled order
_FILLED_STATUSES: set[str] = {"filled", "completed", "done", "all filled", "全部成交", "成交"}


def preprocess(raw: bytes) -> bytes:
    """
    Transform Moomoo trade history CSV into standard format.
    Returns raw bytes unchanged if the format is not recognised.

    Handles partial-fill continuation rows: rows where direction (方向) is empty
    are merged into the preceding main order row by accumulating filled qty and
    computing weighted average price.
    """
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    if not reader.fieldnames:
        return raw

    # Build original-column → standard-field mapping
    col_map: dict[str, str] = {}
    for original in reader.fieldnames:
        normalised = original.strip().lower()
        if normalised in _COL_ALIASES:
            col_map[original] = _COL_ALIASES[normalised]

    # Must be able to map at least asset_code and tx_type
    mapped_std = set(col_map.values())
    if "asset_code" not in mapped_std and "tx_type" not in mapped_std:
        return raw  # not a Moomoo file

    # --- Pass 1: merge continuation rows into main order rows ---
    merged_orders: list[dict[str, str]] = []
    current: dict | None = None

    for row in reader:
        # Normalise row keys
        norm: dict[str, str] = {}
        for orig, val in row.items():
            std = col_map.get(orig, orig.strip().lower())
            norm[std] = (val or "").strip()

        tx_type_raw = norm.get("tx_type", "").strip()
        asset_code = norm.get("asset_code", "").strip()
        status = norm.get("status", "").lower()

        # Skip non-filled orders (only for main rows that carry a status)
        if status and status not in _FILLED_STATUSES:
            current = None  # discard any in-progress accumulation
            continue

        is_continuation = (not tx_type_raw and not asset_code)

        if not is_continuation:
            # New main order row — flush the previous one
            if current is not None:
                merged_orders.append(current)
            # Initialise accumulator from this main row
            qty = _clean_number(norm.get("quantity", "0"))
            amount = _clean_number(norm.get("filled_amount", "0"))
            price_val = _clean_number(norm.get("price", "0"))
            # If filled_amount is available use it; otherwise derive from qty × price
            if amount == 0 and qty != 0 and price_val != 0:
                amount = qty * price_val
            current = {
                "trade_date": norm.get("trade_date", ""),
                "asset_code": asset_code,
                "tx_type_raw": tx_type_raw,
                "filled_qty": qty,
                "filled_amount": amount,
                "avg_price": price_val,
                "fee": norm.get("fee", "0") or "0",
                "currency": norm.get("currency", "USD") or "USD",
                "status": status,
            }
        else:
            # Continuation row — accumulate into current
            if current is None:
                continue  # no parent to accumulate into
            add_qty = _clean_number(norm.get("quantity", "0"))
            add_amount = _clean_number(norm.get("filled_amount", "0"))
            add_price = _clean_number(norm.get("price", "0"))
            if add_amount == 0 and add_qty != 0 and add_price != 0:
                add_amount = add_qty * add_price
            current["filled_qty"] += add_qty
            current["filled_amount"] += add_amount
            # Recompute weighted average price
            if current["filled_qty"] > 0:
                current["avg_price"] = current["filled_amount"] / current["filled_qty"]

    # Flush last pending order
    if current is not None:
        merged_orders.append(current)

    # --- Pass 2: write standardised output ---
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["trade_date", "asset_code", "quantity", "price", "currency", "fee", "tx_type"])

    has_rows = False
    for order in merged_orders:
        trade_date = order["trade_date"].split(" ")[0]  # strip time/timezone
        asset_code = order["asset_code"]
        tx_type = _SIDE_MAP.get(order["tx_type_raw"].lower())
        if not trade_date or not asset_code or tx_type is None:
            continue
        if order["filled_qty"] == 0:
            continue

        writer.writerow([
            trade_date,
            asset_code,
            str(order["filled_qty"]),
            str(order["avg_price"]),
            order["currency"],
            order["fee"],
            tx_type,
        ])
        has_rows = True

    if not has_rows:
        return raw
    return out.getvalue().encode("utf-8")


def _clean_number(val: str) -> float:
    """Strip thousands separators and convert to float; return 0.0 on empty/dash."""
    v = (val or "").strip().replace(",", "")
    if not v or v == "-":
        return 0.0
    try:
        return float(v)
    except ValueError:
        return 0.0


def parse(path: str):
    """Legacy file-path interface."""
    from pathlib import Path
    return preprocess(Path(path).read_bytes())
