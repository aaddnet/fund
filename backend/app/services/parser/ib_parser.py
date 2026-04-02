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
    "asset category": "asset_category",   # enables forex/cash detection in _emit_rows
    "asset class": "asset_category",      # alternative column name in some exports
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
    # V4.1: Internal transfers
    "内部转账": "transfer",
    "转账": "transfer",
    # V4.1: Dividend-related
    "代付股息": "pil",          # Payment in Lieu of Dividend
    "股息费用": "dividend_fee",  # IB -FEE rows associated with dividends
    "股利费用": "dividend_fee",
    # V4.1: ADR fees
    "存托凭证费": "adr_fee",
    "存托费": "adr_fee",
    # V4.1: Securities lending
    "证券出借": "lending_out",
    "证券归还": "lending_return",
    "出借收入": "lending_income",
    # V4.1: Accruals
    "利息应计": "interest_accrual",
    "股息应计": "dividend_accrual",
    "利息应计冲销": "interest_accrual_reversal",
    "股息应计冲销": "dividend_accrual_reversal",
    # V4.1: FX translation — stored (previously ignored)
    "FX Translations P&L": "fx_translation",
}
# Legacy set kept for backward compat (no longer used in routing)
_ZH_CASH_TYPES: set[str] = set()

# V4.1: EN description keyword → tx_type mapping (used when 交易类型 is missing/unknown)
# Checked against description.lower(); first match wins
_EN_DESCRIPTION_KEYWORDS: dict[str, str] = {
    "internal transfer": "transfer",
    "payment in lieu": "pil",
    " -fee": "dividend_fee",                   # IB dividend -FEE rows (note leading space)
    "adr management fee": "adr_fee",
    "adr fee": "adr_fee",
    "interest on customer collateral": "lending_income",
    "securities lent": "lending_out",
    "securities returned": "lending_return",
    "interest accrual": "interest_accrual",
    "dividend accrual": "dividend_accrual",
    "accrual reversal": "interest_accrual_reversal",
    "fx translation": "fx_translation",
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

# Section names that contain transaction data (EN + ZH)
# "Transactions" is used in IB's 1Y/Transactions Statement export format
_TRADE_SECTIONS = {"trades", "transactions", "transaction history", "交易"}

# V4.2: IB Activity Statement DataDiscriminator → tx_category + tx_type routing
DISCRIMINATOR_MAP: dict[str, dict] = {
    "trades":               {"tx_category": "TRADE"},
    "cash transactions":    {"tx_category": "CASH"},
    "transfers":            {"tx_category": "CASH",   "tx_type": "deposit_transfer"},
    "interest":             {"tx_category": "CASH"},
    "dividends":            {"tx_category": "CASH"},
    "fees":                 {"tx_category": "CASH"},
    "forex":                {"tx_category": "FX",     "tx_type": "fx_trade"},
    "securities lent":      {"tx_category": "LENDING"},
}


def identify_cash_type(description: str) -> str:
    """
    V4.2: Map a Cash Transactions description string to the appropriate tx_type.
    Falls back to 'adjustment' for unrecognised descriptions.
    """
    desc = (description or "").lower()
    if "electronic fund transfer" in desc:
        return "deposit_eft"
    elif "internal transfer" in desc or "account transfer" in desc:
        return "deposit_transfer"
    elif "debit interest" in desc or "margin interest" in desc:
        return "interest_debit"
    elif "credit interest" in desc:
        return "interest_credit"
    elif "dividend" in desc and "fee" in desc:
        return "dividend_fee"
    elif "payment in lieu" in desc or "pil" in desc:
        return "pil"
    elif "dividend" in desc:
        return "dividend"
    elif "adr management fee" in desc or "adr fee" in desc:
        return "adr_fee"
    elif "withdrawal" in desc:
        return "withdrawal"
    elif "deposit" in desc:
        return "deposit_eft"
    elif "interest accrual" in desc:
        return "interest_accrual"
    elif "dividend accrual" in desc:
        return "dividend_accrual"
    elif "accrual reversal" in desc:
        return "interest_accrual"
    elif "securities lent" in desc:
        return "lending_out"
    elif "securities returned" in desc:
        return "lending_return"
    elif "interest on customer collateral" in desc:
        return "lending_income"
    elif "adr" in desc and "fee" in desc:
        return "adr_fee"
    else:
        return "adjustment"


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
    writer.writerow(["trade_date", "asset_code", "quantity", "price", "currency", "fee", "tx_type", "description", "tx_subtype"])

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
            # V4.1: check EN description keywords first (IB mixes EN in ZH exports)
            en_matched = False
            for kw, mapped in _EN_DESCRIPTION_KEYWORDS.items():
                if kw in desc_lower:
                    tx_type = mapped
                    en_matched = True
                    break
            if not en_matched:
                is_cash_adj = any(kw in desc_lower for kw in ("p&l", "dividend", "interest", "adjustment", "withholding"))
                is_fx = (tx_type_zh in ("转换", "外汇") and ("." in asset_code or "/" in asset_code or len(asset_code) == 6)) or \
                        (not is_cash_adj and any(kw in desc_lower for kw in ("forex", "conversion")))
                if is_cash_adj:
                    tx_type = "cash_in" if sign_val > 0 else "cash_out"
                elif is_fx:
                    tx_type = "forex_buy" if sign_val > 0 else "forex_sell"
                else:
                    tx_type = "sell" if (net_signed or total_signed) < 0 else "buy"

        # Compute tx_subtype from tx_type_zh
        tx_subtype = ""
        if tx_type_zh == "电子资金转账":
            tx_subtype = "eft"
        elif tx_type_zh in ("内部转账", "转账") or tx_type == "transfer":
            tx_subtype = "transfer"
        elif tx_type_zh == "股息":
            tx_subtype = "ordinary"
        elif tx_type_zh == "替代支付":
            tx_subtype = "special"

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
            description or "",
            tx_subtype,
        ])

    return out.getvalue().encode("utf-8")


def _emit_rows(data_rows: list[list[str]], col_idx: dict[str, int]) -> bytes:
    """Write standardised output CSV from parsed data rows."""
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["trade_date", "asset_code", "quantity", "price", "currency", "fee", "tx_type", "description", "tx_subtype"])

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

        description = _get("description") if "description" in col_idx else ""

        # Determine tx_type from explicit column or quantity sign
        explicit_type = _get("tx_type").strip().lower()
        if is_forex:
            tx_type = "fx_trade"
        elif is_cash:
            tx_type = identify_cash_type(description)
        elif explicit_type in ("buy", "buy/sell:buy"):
            tx_type = "stock_buy"
        elif explicit_type in ("sell", "buy/sell:sell"):
            tx_type = "stock_sell"
        else:
            # V4.2: check description for EN keywords before defaulting to buy/sell
            desc_lower = description.lower()
            en_matched = False
            for kw, mapped in _EN_DESCRIPTION_KEYWORDS.items():
                if kw in desc_lower:
                    tx_type = mapped
                    en_matched = True
                    break
            if not en_matched:
                tx_type = "stock_sell" if qty < 0 else "stock_buy"

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
            description,
            "",   # tx_subtype not available from EN format
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


# ── V4.3 Section-level parsers ────────────────────────────────────────────
# These return TransactionRow objects directly, used by the new import preview.

import re
from datetime import date
from typing import Optional

from app.services.parser.base_parser import TransactionRow

IB_SECTION_MAP: dict[str, str] = {
    "Trades":             "parse_ib_trades",
    "Cash Transactions":  "parse_ib_cash",
    "Transfers":          "parse_ib_transfers",
    "Interest":           "parse_ib_interest",
    "Dividends":          "parse_ib_dividends",
    "Fees":               "parse_ib_fees",
    "Forex":              "parse_ib_forex",
}

SKIP_SECTIONS: set[str] = {
    "Mark-to-Market Performance Summary",
    "Realized & Unrealized Performance Summary",
    "Open Positions",
    "Net Stock Position Summary",
    "Transaction Fees",
    "Financial Instrument Information",
    "IB Managed Securities Lent",
    "Notes/Legal Notes",
    "Change in Dividend Accruals",
}


def safe_float(s) -> Optional[float]:
    """Parse to float, return None on failure."""
    if s is None:
        return None
    try:
        return float(str(s).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def parse_ib_datetime(s: str) -> date:
    """Parse IB datetime string: '2018-03-29, 09:30:00' → date(2018, 3, 29)."""
    return _normalise_ib_datetime(s or "")  # type: ignore[return-value]
    # _normalise_ib_datetime returns str; convert:


def _parse_ib_date(s: str) -> date:
    """Return date object from IB date string."""
    norm = _normalise_ib_datetime(s or "")
    if not norm:
        return date.today()
    try:
        return date.fromisoformat(norm)
    except ValueError:
        return date.today()


def _is_option_symbol(symbol: str) -> bool:
    """Detect IB option symbols like 'NIO 241115C4000' or 'AAPL 240119C00185000'."""
    s = symbol.upper()
    # Pattern: LETTERS SPACES 6DIGITS [CP] DIGITS
    return bool(re.search(r"[A-Z]+\s+\d{6}[CP]\d+", s))


def _identify_asset_type(symbol: str, description: str = "") -> str:
    s = symbol.upper()
    desc = description.lower()
    if _is_option_symbol(s):
        return "option"
    if re.search(r"\d{6}[CP]\d+", s):
        return "option"
    if "etf" in desc or "fund" in desc:
        return "etf"
    if "bond" in desc or "note" in desc or "treasury" in desc:
        return "bond"
    return "stock"


def _extract_interest_period(description: str) -> Optional[date]:
    """Extract month/year from e.g. 'USD Debit Interest for Oct-2018'."""
    m = re.search(r"(\w{3})-(\d{4})", description or "")
    if not m:
        return None
    month_map = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }
    month_name = m.group(1).lower()
    month = month_map.get(month_name)
    year = int(m.group(2))
    if not month:
        return None
    import calendar
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, last_day)


def _hdr_idx(header: list[str], *names: str) -> Optional[int]:
    """Find column index by any of the candidate names (case-insensitive)."""
    lower = [h.lower().strip() for h in header]
    for n in names:
        try:
            return lower.index(n.lower())
        except ValueError:
            pass
    return None


def _get_col(row: list[str], idx: Optional[int], default: str = "") -> str:
    if idx is None or idx >= len(row):
        return default
    return row[idx].strip()


# ── Section parsers ───────────────────────────────────────────────────────

def parse_ib_trades(rows: list[list[str]], header: list[str]) -> list[TransactionRow]:
    results = []
    i_date    = _hdr_idx(header, "date/time", "datetime", "tradedate")
    i_symbol  = _hdr_idx(header, "symbol")
    i_desc    = _hdr_idx(header, "description")
    i_qty     = _hdr_idx(header, "quantity")
    i_price   = _hdr_idx(header, "t. price", "tradeprice", "price")
    i_proceeds= _hdr_idx(header, "proceeds")
    i_comm    = _hdr_idx(header, "comm/fee", "ibcommission", "commission")
    i_basis   = _hdr_idx(header, "basis", "cost basis")
    i_pnl     = _hdr_idx(header, "realized p/l", "realizedpl")
    i_curr    = _hdr_idx(header, "currency")
    i_cat     = _hdr_idx(header, "asset category", "assetcategory")

    for row in rows:
        symbol = _get_col(row, i_symbol)
        if not symbol or "Total" in symbol or symbol == "Symbol":
            continue

        qty_s = _get_col(row, i_qty).replace(",", "")
        qty_f = safe_float(qty_s)
        if qty_f is None or qty_f == 0:
            continue

        asset_cat = _get_col(row, i_cat).lower()
        description = _get_col(row, i_desc)
        currency = _get_col(row, i_curr) or "USD"

        # Classify tx_type
        if asset_cat == "forex":
            tx_type = "fx_trade"
        elif _is_option_symbol(symbol):
            tx_type = "option_buy" if qty_f > 0 else "option_sell"
        else:
            tx_type = "stock_buy" if qty_f > 0 else "stock_sell"

        results.append(TransactionRow(
            trade_date=   _parse_ib_date(_get_col(row, i_date)),
            tx_category=  "TRADE",
            tx_type=      tx_type,
            currency=     currency,
            asset_code=   symbol.strip(),
            asset_name=   description,
            asset_type=   _identify_asset_type(symbol, description),
            quantity=     abs(qty_f),
            price=        safe_float(_get_col(row, i_price).replace(",", "")),
            gross_amount= safe_float(_get_col(row, i_proceeds).replace(",", "")),
            commission=   safe_float(_get_col(row, i_comm).replace(",", "")),
            cost_basis=   safe_float(_get_col(row, i_basis).replace(",", "")),
            realized_pnl= safe_float(_get_col(row, i_pnl).replace(",", "")),
            description=  description,
        ))
    return results


def parse_ib_cash(rows: list[list[str]], header: list[str]) -> list[TransactionRow]:
    results = []
    i_date = _hdr_idx(header, "date", "settle date", "settledate")
    i_curr = _hdr_idx(header, "currency")
    i_amt  = _hdr_idx(header, "amount")
    i_desc = _hdr_idx(header, "description")
    i_sym  = _hdr_idx(header, "symbol")

    for row in rows:
        amt = safe_float(_get_col(row, i_amt).replace(",", ""))
        if amt is None:
            continue
        desc = _get_col(row, i_desc)
        tx_type = identify_cash_type(desc)

        # FX Translation and zero-amount rows → mark as "other" (待处理)
        is_other = tx_type in ("adjustment",) and (
            "fx translation" in desc.lower() or
            "accrual" in desc.lower() or
            amt == 0
        )

        results.append(TransactionRow(
            trade_date=   _parse_ib_date(_get_col(row, i_date)),
            tx_category=  "CASH",
            tx_type=      tx_type,
            currency=     _get_col(row, i_curr) or "USD",
            gross_amount= amt,
            asset_code=   _get_col(row, i_sym) or None,
            description=  desc,
            is_other=     is_other,
        ))
    return results


def parse_ib_transfers(rows: list[list[str]], header: list[str]) -> list[TransactionRow]:
    results = []
    i_date = _hdr_idx(header, "date", "settle date")
    i_curr = _hdr_idx(header, "currency")
    i_amt  = _hdr_idx(header, "amount", "cash amount")
    i_desc = _hdr_idx(header, "description")

    for row in rows:
        amt = safe_float(_get_col(row, i_amt).replace(",", ""))
        if amt is None:
            continue
        results.append(TransactionRow(
            trade_date=   _parse_ib_date(_get_col(row, i_date)),
            tx_category=  "CASH",
            tx_type=      "deposit_transfer",
            currency=     _get_col(row, i_curr) or "USD",
            gross_amount= amt,
            description=  _get_col(row, i_desc),
        ))
    return results


def parse_ib_interest(rows: list[list[str]], header: list[str]) -> list[TransactionRow]:
    results = []
    i_date = _hdr_idx(header, "date", "settle date")
    i_curr = _hdr_idx(header, "currency")
    i_amt  = _hdr_idx(header, "amount")
    i_desc = _hdr_idx(header, "description")

    for row in rows:
        amt = safe_float(_get_col(row, i_amt).replace(",", ""))
        if amt is None:
            continue
        desc = _get_col(row, i_desc)
        tx_type = "interest_debit" if (amt or 0) < 0 else "interest_credit"
        period = _extract_interest_period(desc)

        results.append(TransactionRow(
            trade_date=        _parse_ib_date(_get_col(row, i_date)),
            tx_category=       "CASH",
            tx_type=           tx_type,
            currency=          _get_col(row, i_curr) or "USD",
            gross_amount=      amt,
            description=       desc,
            accrual_period_end=period,
        ))
    return results


def parse_ib_dividends(rows: list[list[str]], header: list[str]) -> list[TransactionRow]:
    results = []
    i_date = _hdr_idx(header, "date", "ex date")
    i_curr = _hdr_idx(header, "currency")
    i_amt  = _hdr_idx(header, "amount")
    i_desc = _hdr_idx(header, "description")
    i_sym  = _hdr_idx(header, "symbol")

    for row in rows:
        amt = safe_float(_get_col(row, i_amt).replace(",", ""))
        if amt is None:
            continue
        desc = _get_col(row, i_desc).lower()

        if "fee" in desc:
            tx_type = "dividend_fee"
        elif "payment in lieu" in desc or "pil" in desc:
            tx_type = "pil"
        else:
            tx_type = "dividend"

        results.append(TransactionRow(
            trade_date=   _parse_ib_date(_get_col(row, i_date)),
            tx_category=  "CASH",
            tx_type=      tx_type,
            currency=     _get_col(row, i_curr) or "USD",
            gross_amount= amt,
            asset_code=   _get_col(row, i_sym) or None,
            description=  _get_col(row, i_desc),
        ))
    return results


def parse_ib_fees(rows: list[list[str]], header: list[str]) -> list[TransactionRow]:
    results = []
    i_date = _hdr_idx(header, "date", "settle date")
    i_curr = _hdr_idx(header, "currency")
    i_amt  = _hdr_idx(header, "amount")
    i_desc = _hdr_idx(header, "description")

    for row in rows:
        amt = safe_float(_get_col(row, i_amt).replace(",", ""))
        if amt is None:
            continue
        desc = _get_col(row, i_desc).lower()
        if "adr" in desc:
            tx_type = "adr_fee"
        else:
            tx_type = "other_fee"

        results.append(TransactionRow(
            trade_date=   _parse_ib_date(_get_col(row, i_date)),
            tx_category=  "CASH",
            tx_type=      tx_type,
            currency=     _get_col(row, i_curr) or "USD",
            gross_amount= amt,
            description=  _get_col(row, i_desc),
        ))
    return results


def parse_ib_forex(rows: list[list[str]], header: list[str]) -> list[TransactionRow]:
    """
    IB Forex section: each row has two currencies in the symbol like 'USD.HKD'.
    Quantity column gives amount of base currency (sold if negative, bought if positive).
    Proceeds = counter currency amount.
    """
    results = []
    i_date    = _hdr_idx(header, "date/time", "datetime")
    i_sym     = _hdr_idx(header, "symbol")
    i_qty     = _hdr_idx(header, "quantity")
    i_price   = _hdr_idx(header, "t. price", "price")
    i_proceeds= _hdr_idx(header, "proceeds")
    i_comm    = _hdr_idx(header, "comm/fee", "commission")
    i_curr    = _hdr_idx(header, "currency")

    for row in rows:
        symbol = _get_col(row, i_sym)
        if not symbol or "Total" in symbol:
            continue
        qty_f = safe_float(_get_col(row, i_qty).replace(",", ""))
        if qty_f is None or qty_f == 0:
            continue

        proceeds_f = safe_float(_get_col(row, i_proceeds).replace(",", ""))
        comm_f = safe_float(_get_col(row, i_comm).replace(",", ""))
        currency = _get_col(row, i_curr) or "USD"

        # Symbol like "USD.HKD": left = from, right = to
        parts = symbol.split(".")
        from_curr = parts[0].strip() if len(parts) >= 1 else currency
        to_curr   = parts[1].strip() if len(parts) >= 2 else currency

        # qty_f is amount of from_curr (negative = we sold from_curr)
        from_amount = float(qty_f)          # already signed
        to_amount   = float(proceeds_f) if proceeds_f is not None else 0.0

        rate_f = safe_float(_get_col(row, i_price).replace(",", ""))

        results.append(TransactionRow(
            trade_date=      _parse_ib_date(_get_col(row, i_date)),
            tx_category=     "FX",
            tx_type=         "fx_trade",
            currency=        currency,
            asset_code=      symbol,
            fx_from_currency=from_curr,
            fx_from_amount=  from_amount,
            fx_to_currency=  to_curr,
            fx_to_amount=    to_amount,
            fx_rate=         rate_f,
            commission=      comm_f,
            description=     f"FX {from_curr}/{to_curr}",
        ))
    return results


# ── V4.3 main entry: multi-section Activity Statement parser ─────────────

def parse_ib_activity_v43(text: str) -> list[TransactionRow]:
    """
    Parse a full IB Activity Statement CSV into a list of TransactionRow objects.
    Handles multi-section format: reads all Section headers, dispatches to
    section-level parse functions, skips non-transactional sections.
    """
    _SECTION_PARSERS = {
        "trades":             parse_ib_trades,
        "cash transactions":  parse_ib_cash,
        "transfers":          parse_ib_transfers,
        "interest":           parse_ib_interest,
        "dividends":          parse_ib_dividends,
        "fees":               parse_ib_fees,
        "forex":              parse_ib_forex,
    }
    _SKIP = {s.lower() for s in SKIP_SECTIONS}

    reader = csv.reader(io.StringIO(text))
    # Collect section name → (header, rows)
    sections: dict[str, tuple[list[str], list[list[str]]]] = {}
    current_section: Optional[str] = None
    current_header: list[str] = []

    for row in reader:
        if not row:
            continue
        section_name = row[0].strip()
        row_type = row[1].strip() if len(row) > 1 else ""

        if row_type == "Header":
            current_section = section_name
            current_header = [c.strip() for c in row[2:]]
            if current_section not in sections:
                sections[current_section] = (current_header, [])
            else:
                sections[current_section] = (current_header, sections[current_section][1])
        elif row_type == "Data" and current_section:
            discriminator = row[2].strip() if len(row) > 2 else ""
            if discriminator.lower() in ("subtotal", "total"):
                continue
            data = [c.strip() for c in row[2:]]
            if current_section in sections:
                sections[current_section][1].append(data)

    results: list[TransactionRow] = []
    for section_name, (header, rows) in sections.items():
        section_lower = section_name.lower()
        if section_lower in _SKIP:
            continue
        parser_fn = _SECTION_PARSERS.get(section_lower)
        if parser_fn and rows:
            parsed = parser_fn(rows, header)
            results.extend(parsed)

    return results
