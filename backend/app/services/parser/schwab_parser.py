"""
Charles Schwab brokerage transaction history parser.

Expected export: Accounts → History → Export (CSV).
File structure:
  Row 0: "Transactions  for account XXXX-XXXX as of MM/DD/YYYY, HH:MM:SS ET"
  Row 1: blank
  Row 2: header row → Date,Action,Symbol,Description,Quantity,Price,Fees & Comm,Amount
  Rows 3+: data rows
  Last rows: blank / "Transactions Total" summary rows (no Symbol → skipped)

Actions mapped to tx_type:
  Buy / Buy to Open                       → buy
  Sell / Sell to Close                    → sell
  Reinvest Shares / Reinvest Dividends    → buy
  Cash Dividend / Bank Interest / etc.    → skipped (non-equity)

Currency is always USD for US Schwab accounts.
"""

import csv
import io
import re

# Schwab Action → standard tx_type
_ACTION_MAP: dict[str, str] = {
    "buy": "buy",
    "buy to open": "buy",
    "buy to cover": "buy",
    "reinvest shares": "buy",
    "reinvest dividends": "buy",
    "sell": "sell",
    "sell to close": "sell",
    "sell short": "sell",
}

# Actions we intentionally skip (income / cash / transfers — not equity trades)
_SKIP_ACTIONS: set[str] = {
    "cash dividend",
    "qualified dividend",
    "non-qualified div",
    "bank interest",
    "misc cash entry",
    "moneylink transfer",
    "moneylink deposit",
    "moneylink withdrawal",
    "journaled shares",
    "security transfer",
    "margin interest",
    "foreign tax paid",
    "wire funds",
    "wire funds received",
    "stock plan activity",
    "exchange or exercise",
    "expired",
    "assigned",
}


def preprocess(raw: bytes) -> bytes:
    """
    Transform Schwab transaction CSV into standard format.
    Scans for the real header row, skips meta and summary lines.
    Returns raw bytes unchanged if the format is not recognised.
    """
    text = raw.decode("utf-8-sig")
    lines = text.splitlines()

    # Find the header row: first line matching /^"?Date"?\s*,/
    header_idx: int | None = None
    for i, line in enumerate(lines):
        if re.match(r'^"?Date"?\s*,', line.strip()):
            header_idx = i
            break

    if header_idx is None:
        return raw  # not a Schwab file

    csv_text = "\n".join(lines[header_idx:])
    reader = csv.DictReader(io.StringIO(csv_text))

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["trade_date", "asset_code", "quantity", "price", "currency", "fee", "tx_type"])

    has_rows = False
    for row in reader:
        date_val = (row.get("Date") or "").strip()
        action_raw = (row.get("Action") or "").strip()
        symbol = (row.get("Symbol") or "").strip()
        quantity = (row.get("Quantity") or "").strip()
        price = _clean_amount(row.get("Price") or "")
        fee = _clean_amount(row.get("Fees & Comm") or "0") or "0"

        # Skip rows without date or symbol (summary / blank lines)
        if not date_val or not symbol:
            continue

        action = action_raw.lower()

        # Skip non-trade actions
        if action in _SKIP_ACTIONS:
            continue

        tx_type = _ACTION_MAP.get(action)
        if tx_type is None:
            # Unknown action — skip rather than silently mis-classify
            continue

        writer.writerow([date_val, symbol, quantity or "0", price or "0", "USD", fee, tx_type])
        has_rows = True

    if not has_rows:
        return raw
    return out.getvalue().encode("utf-8")


def _clean_amount(value: str) -> str:
    """Remove $, commas; convert parentheses notation to negative."""
    v = value.strip().replace("$", "").replace(",", "")
    if v.startswith("(") and v.endswith(")"):
        return "-" + v[1:-1]
    return v


def parse(path: str):
    """Legacy file-path interface."""
    from pathlib import Path
    return preprocess(Path(path).read_bytes())
