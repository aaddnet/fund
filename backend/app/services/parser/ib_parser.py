from __future__ import annotations

"""
Interactive Brokers parser — supports three export formats:

1. **Activity Statement EN** (multi-section CSV):
   Trades,Header,DataDiscriminator,Asset Category,Currency,Symbol,Date/Time,Quantity,T. Price,...
   Trades,Data,Order,Stocks,USD,AAPL,"2024-01-15, 09:30:00",100,185.50,...

2. **Activity Statement ZH** (Chinese-localized multi-section CSV):
   Transaction History,Header,日期,账户,说明,交易类型,代码,数量,价格,Price Currency,总额,佣金,净额
   Transaction History,Data,2019/12/31,U***3137,FX Translations P&L,调整,...

3. **Flex Query Transactions** (flat CSV):
   AccountID,Currency,Symbol,TradeDate,Quantity,TradePrice,IBCommission,...

Buy vs Sell is determined by the sign of the Quantity column
(positive = buy, negative = sell), or by the 交易类型 column in ZH format.
"""

import csv
import io


# Activity Statement EN: IB column name → standard column name
_IB_ACTIVITY_COL_MAP = {
    "symbol": "asset_code",
    "date/time": "trade_date",
    "quantity": "quantity",
    "t. price": "price",
    "comm/fee": "fee",
    "currency": "currency",
}

# Activity Statement ZH: Chinese column name → standard column name
_IB_ZH_COL_MAP = {
    "代码": "asset_code",
    "说明": "description",
    "日期": "trade_date",
    "数量": "quantity",
    "价格": "price",
    "佣金": "fee",
    "price currency": "currency",
    "货币": "currency",
    "交易类型": "tx_type_zh",
    "总额": "total_amount",
    "净额": "net_amount",
}

# Chinese tx_type mapping — explicit routing by 交易类型 column
# "zh_cash" = determine cash_in/cash_out from sign of net/total amount
_ZH_TX_TYPE_MAP = {
    # Position-affecting trades
    "买入": "buy",
    "买": "buy",
    "卖出": "sell",
    "卖": "sell",
    # Cash-only (income)
    "股息": "cash_in",
    "替代支付": "cash_in",    # dividend substitute payment
    "贷方利息": "cash_in",   # credit interest income
    # Cash-only (expense, sign is negative so we detect from net)
    "外国预扣税": "zh_cash",  # withholding tax → net is negative → cash_out
    "借方利息": "zh_cash",    # debit interest / margin cost → net is negative → cash_out
    # Adjustments — sign determines direction
    "调整": "zh_cash",
    "现金转账": "zh_cash",   # small internal cash transfer
    # Deposit / capital events — flagged for manual confirmation
    "存款": "deposit_pending",
    "电子资金转账": "deposit_pending",
    # Ignored (non-cash P&L translation entries)
    "FX Translations P&L": "ignore",
}
# Legacy set kept for backward compat (no longer used in routing)
_ZH_CASH_TYPES: set[str] = set()

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

# Section names that contain transaction data (EN + ZH)
_TRADE_SECTIONS = {"trades", "transaction history", "交易"}


def preprocess(raw: bytes) -> bytes:
    """
    Transform IB CSV (Activity Statement or Flex Query) into a standard CSV
    with columns: trade_date, asset_code, quantity, price, currency, fee, tx_type.
    Returns raw bytes unchanged if the format is not recognised.
    """
    text = raw.decode("utf-8-sig")

    # Try Activity Statement format (EN or ZH multi-section)
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
    """Parse IB Activity Statement multi-section CSV (EN or ZH)."""
    reader = csv.reader(io.StringIO(text))

    header: list[str] | None = None
    data_rows: list[list[str]] = []

    for row in reader:
        if not row:
            continue
        section = row[0].strip()
        row_type = row[1].strip() if len(row) > 1 else ""

        # Match section name (EN: "Trades", ZH: "Transaction History" / "交易")
        section_lower = section.lower()
        if not any(section_lower == s for s in _TRADE_SECTIONS):
            continue

        if row_type == "Header":
            header = [col.strip() for col in row[2:]]
        elif row_type == "Data":
            discriminator = row[2].strip() if len(row) > 2 else ""
            if discriminator.lower() in ("subtotal", "total"):
                continue
            data_rows.append([col.strip() for col in row[2:]])

    if not header or not data_rows:
        return None

    header_lower = [h.lower() for h in header]

    # Detect if this is ZH format by checking for Chinese columns
    is_zh = any(h in _IB_ZH_COL_MAP for h in header_lower)

    col_map = _IB_ZH_COL_MAP if is_zh else _IB_ACTIVITY_COL_MAP
    col_idx: dict[str, int] = {}
    for ib_col, std_col in col_map.items():
        try:
            col_idx[std_col] = header_lower.index(ib_col)
        except ValueError:
            pass

    # For ZH format: need at least trade_date + (quantity or total_amount)
    if is_zh:
        if "trade_date" not in col_idx:
            return None
        return _emit_zh_rows(data_rows, col_idx)

    # EN format: need asset_code, trade_date, quantity, price
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
        first = row[0].strip().lower()
        if first in ("total", "subtotal", ""):
            continue
        data_rows.append([c.strip() for c in row])

    if not data_rows:
        return None

    return _emit_rows(data_rows, col_idx)


def _emit_zh_rows(data_rows: list[list[str]], col_idx: dict[str, int]) -> bytes:
    """Write standardised output CSV from ZH Activity Statement rows."""
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["trade_date", "asset_code", "quantity", "price", "currency", "fee", "tx_type"])

    for row in data_rows:
        def _get(col: str) -> str:
            idx = col_idx.get(col)
            return row[idx].strip() if idx is not None and idx < len(row) else ""

        trade_date = _normalise_ib_datetime(_get("trade_date"))
        if not trade_date:
            continue

        # Determine asset_code: use 代码 column, fallback to 说明 (description)
        asset_code = _get("asset_code")
        if asset_code == "-":
            asset_code = ""
        description = _get("description")

        # Determine tx_type from 交易类型
        tx_type_zh = _get("tx_type_zh").strip()
        tx_type = _ZH_TX_TYPE_MAP.get(tx_type_zh, "")

        # Skip explicitly ignored types (FX P&L translation entries)
        if tx_type == "ignore":
            continue

        # Parse raw numeric fields (keep sign for now)
        qty_raw = _get("quantity").replace(",", "")
        total_raw = _get("total_amount").replace(",", "")
        net_raw = _get("net_amount").replace(",", "")
        price_raw = _get("price").replace(",", "")

        qty = _safe_float(qty_raw.replace("-", ""))
        price = _safe_float(price_raw.replace("-", ""))
        # Keep sign for total/net to determine cash direction
        total_signed = _safe_float(total_raw)
        net_signed = _safe_float(net_raw)
        fee_raw = _get("fee").replace(",", "")
        fee = abs(_safe_float(fee_raw))

        currency = _get("currency")
        if not currency or currency == "-":
            currency = "USD"

        # Skip rows without meaningful data
        if qty == 0 and total_signed == 0 and net_signed == 0:
            continue

        # Resolve "zh_cash" placeholder: determine direction from net/total sign
        if tx_type == "zh_cash":
            sign_val = net_signed or total_signed
            tx_type = "cash_in" if sign_val >= 0 else "cash_out"

        # For deposit_pending rows: use abs(net) as the amount, price=1
        if tx_type == "deposit_pending":
            dep_amount = abs(net_signed) or abs(total_signed)
            if dep_amount == 0:
                continue
            note = _get("description")
            writer.writerow([
                trade_date,
                asset_code or currency,
                str(dep_amount),
                "1",
                currency,
                "0",
                tx_type,
            ])
            continue

        # For buy/sell rows with explicit quantity: quantity column has actual share count
        # For cash-only rows (dividends, interest, etc.): quantity may be 0 or the dollar amount
        if tx_type in ("buy", "sell"):
            # Use actual share quantity; skip if zero
            if qty == 0:
                continue
        else:
            # cash_in / cash_out rows: quantity = absolute dollar amount
            if qty == 0:
                qty = abs(net_signed) or abs(total_signed)
                price = 1.0
            if qty == 0:
                continue

        # Determine tx_type if not yet classified (unknown 交易类型 → fallback heuristic)
        if not tx_type:
            desc_lower = description.lower() if description else ""
            sign_val = net_signed or total_signed or qty
            is_cash_adj = any(kw in desc_lower for kw in ("p&l", "dividend", "interest", "adjustment", "withholding"))
            is_fx = (tx_type_zh in ("转换", "外汇") and ("." in asset_code or "/" in asset_code or len(asset_code) == 6)) or \
                    (not is_cash_adj and any(kw in desc_lower for kw in ("forex", "conversion")))
            if is_cash_adj:
                tx_type = "cash_in" if sign_val > 0 else "cash_out"
            elif is_fx:
                tx_type = "forex_buy" if sign_val > 0 else "forex_sell"
            else:
                tx_type = "sell" if (net_signed or total_signed) < 0 else "buy"

        # Derive asset_code from description if 代码 is empty
        if not asset_code and description:
            asset_code = _extract_asset_from_description(description, currency, tx_type)

        if not asset_code:
            asset_code = currency  # fallback for cash/adjustment rows

        writer.writerow([
            trade_date,
            asset_code,
            str(abs(qty)),
            str(abs(price)) if price else "0",
            currency,
            str(fee),
            tx_type,
        ])

    return out.getvalue().encode("utf-8")


def _emit_rows(data_rows: list[list[str]], col_idx: dict[str, int]) -> bytes:
    """Write standardised output CSV from parsed data rows."""
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["trade_date", "asset_code", "quantity", "price", "currency", "fee", "tx_type"])

    for row in data_rows:
        def _get(col: str) -> str:
            idx = col_idx.get(col)
            return row[idx].strip() if idx is not None and idx < len(row) else ""

        # Classify asset category
        asset_cat = _get("asset_category").lower()
        is_forex = asset_cat == "forex"
        is_cash = asset_cat == "cash"
        if asset_cat == "" and "asset_category" in col_idx:
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
        if is_forex:
            tx_type = "forex_buy" if qty > 0 else "forex_sell"
        elif is_cash:
            tx_type = "cash_in" if qty > 0 else "cash_out"
        elif explicit_type in ("buy", "buy/sell:buy"):
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


_DESCRIPTION_SKIP_WORDS = {"dividend", "interest", "withholding", "tax", "fee", "commission",
                           "adjustment", "transfer", "deposit", "withdrawal", "payment", "on", "cash"}


def _extract_asset_from_description(description: str, currency: str, tx_type: str) -> str:
    """Try to extract a meaningful asset code from the description field."""
    desc = description.strip()
    if not desc:
        return currency

    # FX-related descriptions
    if any(kw in desc.lower() for kw in ("fx", "forex", "conversion")):
        return f"{currency}.USD" if currency != "USD" else "USD"

    # Try words as ticker, skipping known non-ticker keywords
    for word in desc.split():
        # Remove parenthetical ISIN if present
        if "(" in word:
            word = word.split("(")[0]
        if word.lower() in _DESCRIPTION_SKIP_WORDS:
            continue
        if word and word.isalnum() and len(word) <= 10:
            return word.upper()

    return currency


def _safe_float(value: str) -> float:
    """Parse float safely, return 0.0 on failure."""
    if not value or value == "-":
        return 0.0
    try:
        return float(value.replace(",", ""))
    except ValueError:
        return 0.0


def _normalise_ib_datetime(value: str) -> str:
    """Convert '2024-01-15, 09:30:00' or '20240115' or '2019/12/31' to 'YYYY-MM-DD'."""
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
    # Handle YYYY/MM/DD format
    if "/" in value:
        value = value.replace("/", "-")
    return value


def parse(path: str):
    """Legacy file-path interface."""
    from pathlib import Path
    return preprocess(Path(path).read_bytes())
