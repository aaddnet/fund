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

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["trade_date", "asset_code", "quantity", "price", "currency", "fee", "tx_type"])

    has_rows = False
    last_asset: str = ""
    last_tx_type_raw: str = ""

    for row in reader:
        # Normalise row
        norm: dict[str, str] = {}
        for orig, val in row.items():
            std = col_map.get(orig, orig.strip().lower())
            norm[std] = (val or "").strip()

        trade_date = norm.get("trade_date", "")
        asset_code = norm.get("asset_code", "")
        quantity = norm.get("quantity", "")
        price = norm.get("price", "")
        fee = norm.get("fee", "0") or "0"
        currency = norm.get("currency", "USD") or "USD"
        tx_type_raw = norm.get("tx_type", "")
        status = norm.get("status", "").lower()

        # Partial fill continuation rows: no symbol/direction, inherit from parent order
        if not asset_code and not tx_type_raw:
            asset_code = last_asset
            tx_type_raw = last_tx_type_raw
        else:
            last_asset = asset_code
            last_tx_type_raw = tx_type_raw

        # Only import filled orders; allow rows with no status column (status="")
        if status and status not in _FILLED_STATUSES:
            continue

        if not trade_date or not asset_code:
            continue

        # Strip time component and timezone suffix from date field
        trade_date = trade_date.split(" ")[0]

        tx_type = _SIDE_MAP.get(tx_type_raw.lower())
        if tx_type is None:
            continue

        writer.writerow([trade_date, asset_code, quantity, price, currency, fee, tx_type])
        has_rows = True

    if not has_rows:
        return raw
    return out.getvalue().encode("utf-8")


def parse(path: str):
    """Legacy file-path interface."""
    from pathlib import Path
    return preprocess(Path(path).read_bytes())
