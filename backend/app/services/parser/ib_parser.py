"""
Interactive Brokers Activity Statement parser.

Expected export: Activity Statement → Trades section (CSV format).
IB CSV structure: each row starts with section name and row type.
  Trades,Header,DataDiscriminator,Asset Category,Currency,Symbol,Date/Time,Quantity,T. Price,...
  Trades,Data,Order,Stocks,USD,AAPL,"2024-01-15, 09:30:00",100,185.50,...
  Trades,SubTotal,...
  Trades,Total,...

Buy vs Sell is determined by the sign of the Quantity column
(positive = buy, negative = sell).
"""

import csv
import io


# IB column name → standard column name
_IB_COL_MAP = {
    "symbol": "asset_code",
    "date/time": "trade_date",
    "quantity": "quantity",
    "t. price": "price",
    "comm/fee": "fee",
    "currency": "currency",
}


def preprocess(raw: bytes) -> bytes:
    """
    Transform IB Activity Statement CSV into a standard single-section CSV
    with columns: trade_date, asset_code, quantity, price, currency, fee, tx_type.
    Returns raw bytes unchanged if the format is not recognised.
    """
    text = raw.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text))

    header: list[str] | None = None
    data_rows: list[list[str]] = []

    for row in reader:
        if not row:
            continue
        section = row[0].strip()
        row_type = row[1].strip() if len(row) > 1 else ""

        if section == "Trades" and row_type == "Header":
            # Skip the first two positional columns (section, row_type, DataDiscriminator)
            header = [col.strip() for col in row[2:]]
        elif section == "Trades" and row_type == "Data":
            discriminator = row[2].strip() if len(row) > 2 else ""
            # Skip aggregation rows
            if discriminator in ("SubTotal", "Total", ""):
                continue
            data_rows.append([col.strip() for col in row[2:]])

    if not header or not data_rows:
        # Not a multi-section IB file — return unchanged so _parse_csv_rows handles it
        return raw

    header_lower = [h.lower() for h in header]
    col_idx: dict[str, int] = {}
    for ib_col, std_col in _IB_COL_MAP.items():
        try:
            col_idx[std_col] = header_lower.index(ib_col)
        except ValueError:
            pass

    required = {"asset_code", "trade_date", "quantity", "price"}
    if not required.issubset(col_idx):
        return raw  # columns not found — fall back to raw

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["trade_date", "asset_code", "quantity", "price", "currency", "fee", "tx_type"])

    for row in data_rows:
        def _get(col: str) -> str:
            idx = col_idx.get(col)
            return row[idx].strip() if idx is not None and idx < len(row) else ""

        trade_date = _normalise_ib_datetime(_get("trade_date"))
        qty_raw = _get("quantity").replace(",", "")
        try:
            qty = float(qty_raw)
        except ValueError:
            continue
        if qty == 0:
            continue

        tx_type = "sell" if qty < 0 else "buy"
        price = _get("price").replace(",", "")
        fee_raw = _get("fee").replace(",", "")
        # IB reports fees as negative — store absolute value
        try:
            fee = str(abs(float(fee_raw))) if fee_raw else "0"
        except ValueError:
            fee = "0"

        writer.writerow([
            trade_date,
            _get("asset_code"),
            str(abs(qty)),
            price or "0",
            _get("currency") or "USD",
            fee,
            tx_type,
        ])

    return out.getvalue().encode("utf-8")


def _normalise_ib_datetime(value: str) -> str:
    """Convert '2024-01-15, 09:30:00' or '2024-01-15 09:30:00' to 'YYYY-MM-DD'."""
    value = value.strip()
    if "," in value:
        value = value.split(",")[0].strip()
    if " " in value:
        value = value.split(" ")[0].strip()
    return value


def parse(path: str):
    """Legacy file-path interface."""
    from pathlib import Path
    return preprocess(Path(path).read_bytes())
