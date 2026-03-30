from __future__ import annotations

"""
Interactive Brokers parser — supports two export formats:

1. **Activity Statement** (multi-section CSV):
   Trades,Header,DataDiscriminator,Asset Category,Currency,Symbol,Date/Time,Quantity,T. Price,...
   Trades,Data,Order,Stocks,USD,AAPL,"2024-01-15, 09:30:00",100,185.50,...

2. **Flex Query Transactions** (flat CSV):
   AccountID,Currency,Symbol,TradeDate,Quantity,TradePrice,IBCommission,...
   U8503137,USD,AAPL,2019-04-01,100,185.50,-1.00,...

Buy vs Sell is determined by the sign of the Quantity column
(positive = buy, negative = sell).
"""

import csv
import io


# Activity Statement: IB column name → standard column name
_IB_ACTIVITY_COL_MAP = {
    "symbol": "asset_code",
    "date/time": "trade_date",
    "quantity": "quantity",
    "t. price": "price",
    "comm/fee": "fee",
    "currency": "currency",
}

# Flex Query: IB column name (lowered) → standard column name
_IB_FLEX_COL_MAP = {
    "symbol": "asset_code",
    "underlyingsymbol": "asset_code",
    "tradedate": "trade_date",
    "datetime": "trade_date",
    "date/time": "trade_date",
    "tradetime": None,  # skip
    "quantity": "quantity",
    "tradeprice": "price",
    "t. price": "price",
    "price": "price",
    "ibcommission": "fee",
    "commission": "fee",
    "comm/fee": "fee",
    "currencyprimary": "currency",
    "currency": "currency",
    "buy/sell": "tx_type",
    "buysell": "tx_type",
    "code": None,  # skip
    "assetcategory": "asset_category",
}


def preprocess(raw: bytes) -> bytes:
    """
    Transform IB CSV (Activity Statement or Flex Query) into a standard CSV
    with columns: trade_date, asset_code, quantity, price, currency, fee, tx_type.
    Returns raw bytes unchanged if the format is not recognised.
    """
    text = raw.decode("utf-8-sig")

    # Try Activity Statement format first (multi-section with "Trades,Header,...")
    result = _try_activity_statement(text)
    if result is not None:
        return result

    # Try Flex Query flat CSV format
    result = _try_flex_query(text)
    if result is not None:
        return result

    # Not recognised — return unchanged for generic parser
    return raw


def _try_activity_statement(text: str) -> bytes | None:
    """Parse IB Activity Statement multi-section CSV."""
    reader = csv.reader(io.StringIO(text))

    header: list[str] | None = None
    data_rows: list[list[str]] = []

    for row in reader:
        if not row:
            continue
        section = row[0].strip()
        row_type = row[1].strip() if len(row) > 1 else ""

        if section == "Trades" and row_type == "Header":
            header = [col.strip() for col in row[2:]]
        elif section == "Trades" and row_type == "Data":
            discriminator = row[2].strip() if len(row) > 2 else ""
            if discriminator in ("SubTotal", "Total", ""):
                continue
            data_rows.append([col.strip() for col in row[2:]])

    if not header or not data_rows:
        return None

    header_lower = [h.lower() for h in header]
    col_idx: dict[str, int] = {}
    for ib_col, std_col in _IB_ACTIVITY_COL_MAP.items():
        try:
            col_idx[std_col] = header_lower.index(ib_col)
        except ValueError:
            pass

    required = {"asset_code", "trade_date", "quantity", "price"}
    if not required.issubset(col_idx):
        return None

    return _emit_rows(data_rows, col_idx)


def _try_flex_query(text: str) -> bytes | None:
    """Parse IB Flex Query flat CSV (transactions export)."""
    reader = csv.reader(io.StringIO(text))

    rows = list(reader)
    if len(rows) < 2:
        return None

    # Find header row — first non-empty row
    header_row = None
    data_start = 0
    for i, row in enumerate(rows):
        if row and any(c.strip() for c in row):
            header_row = [c.strip() for c in row]
            data_start = i + 1
            break

    if not header_row:
        return None

    header_lower = [h.lower().replace(" ", "") for h in header_row]

    # Check if this looks like an IB file by checking for IB-specific columns
    ib_indicators = {"symbol", "tradeprice", "ibcommission", "currencyprimary",
                     "tradedate", "buy/sell", "buysell", "assetcategory",
                     "accountid", "t.price", "comm/fee"}
    found_indicators = set(header_lower) & ib_indicators
    if len(found_indicators) < 2:
        return None  # Not an IB file

    col_idx: dict[str, int] = {}
    for i, h in enumerate(header_lower):
        std_col = _IB_FLEX_COL_MAP.get(h)
        if std_col and std_col not in col_idx:
            col_idx[std_col] = i

    required = {"asset_code", "trade_date", "quantity"}
    if not required.issubset(col_idx):
        return None

    data_rows = []
    for row in rows[data_start:]:
        if not row or not any(c.strip() for c in row):
            continue
        # Skip trailing summary/total rows
        first = row[0].strip().lower()
        if first in ("total", "subtotal", ""):
            continue
        data_rows.append([c.strip() for c in row])

    if not data_rows:
        return None

    return _emit_rows(data_rows, col_idx)


def _emit_rows(data_rows: list[list[str]], col_idx: dict[str, int]) -> bytes:
    """Write standardised output CSV from parsed data rows."""
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["trade_date", "asset_code", "quantity", "price", "currency", "fee", "tx_type"])

    for row in data_rows:
        def _get(col: str) -> str:
            idx = col_idx.get(col)
            return row[idx].strip() if idx is not None and idx < len(row) else ""

        # Skip non-stock rows if asset_category is present
        asset_cat = _get("asset_category").lower()
        if asset_cat and asset_cat in ("forex", "cash", ""):
            continue

        trade_date = _normalise_ib_datetime(_get("trade_date"))
        if not trade_date:
            continue

        qty_raw = _get("quantity").replace(",", "")
        try:
            qty = float(qty_raw)
        except ValueError:
            continue
        if qty == 0:
            continue

        # Determine tx_type from explicit column or quantity sign
        explicit_type = _get("tx_type").strip().lower()
        if explicit_type in ("buy", "buy/sell:buy"):
            tx_type = "buy"
        elif explicit_type in ("sell", "buy/sell:sell"):
            tx_type = "sell"
        else:
            tx_type = "sell" if qty < 0 else "buy"

        price_raw = _get("price").replace(",", "") if "price" in col_idx else "0"
        try:
            price = str(abs(float(price_raw))) if price_raw else "0"
        except ValueError:
            price = "0"

        fee_raw = _get("fee").replace(",", "") if "fee" in col_idx else "0"
        try:
            fee = str(abs(float(fee_raw))) if fee_raw else "0"
        except ValueError:
            fee = "0"

        writer.writerow([
            trade_date,
            _get("asset_code"),
            str(abs(qty)),
            price,
            _get("currency") or "USD",
            fee,
            tx_type,
        ])

    return out.getvalue().encode("utf-8")


def _normalise_ib_datetime(value: str) -> str:
    """Convert '2024-01-15, 09:30:00' or '20240115' or '2024-01-15 09:30:00' to 'YYYY-MM-DD'."""
    value = value.strip()
    if not value:
        return ""
    if "," in value:
        value = value.split(",")[0].strip()
    if " " in value:
        value = value.split(" ")[0].strip()
    # Handle YYYYMMDD compact format
    if len(value) == 8 and value.isdigit():
        return f"{value[:4]}-{value[4:6]}-{value[6:8]}"
    return value


def parse(path: str):
    """Legacy file-path interface."""
    from pathlib import Path
    return preprocess(Path(path).read_bytes())
