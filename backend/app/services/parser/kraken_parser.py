"""
Kraken Trades history parser.

Expected export: Account → History → Trades (CSV download).
Columns: txid, ordertxid, pair, time, type, ordertype, price, cost, fee, vol, margin, misc, ledgers

  pair  : trading pair e.g. XXBTZUSD, XETHZUSD, SOLUSD
  type  : "buy" or "sell"
  price : execution price in quote currency
  vol   : base asset volume traded
  fee   : fee in quote currency
  time  : "YYYY-MM-DD HH:MM:SS.ffffff"

Asset code extraction: strip known Kraken prefixes (X/Z) and map to standard tickers.
Quote currency inferred from the end of the pair string.
"""

import csv
import io

# Map Kraken internal asset codes → standard ticker symbols
_ASSET_MAP: dict[str, str] = {
    "XXBT": "BTC",
    "XBT": "BTC",
    "XETH": "ETH",
    "XLTC": "LTC",
    "XXRP": "XRP",
    "XRP": "XRP",
    "XXLM": "XLM",
    "XZEC": "ZEC",
    "ZUSD": "USD",
    "ZEUR": "EUR",
    "ZGBP": "GBP",
    "ZCAD": "CAD",
    "ZJPY": "JPY",
    "ETH": "ETH",
    "SOL": "SOL",
    "ADA": "ADA",
    "DOT": "DOT",
    "MATIC": "MATIC",
    "LINK": "LINK",
    "AVAX": "AVAX",
    "ATOM": "ATOM",
    "UNI": "UNI",
    "USDT": "USDT",
    "USDC": "USDC",
}

# Common quote currencies (checked from the end of the pair string)
_QUOTE_CURRENCIES = ["USDT", "USDC", "USD", "EUR", "GBP", "BTC", "ETH", "CAD", "JPY"]


def preprocess(raw: bytes) -> bytes:
    """
    Transform Kraken Trades CSV into standard format.
    Returns raw bytes unchanged if the format is not recognised.
    """
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    if not reader.fieldnames:
        return raw

    fieldnames_lower = [f.lower() for f in reader.fieldnames]
    required = {"pair", "time", "type", "price", "vol"}
    if not required.issubset(set(fieldnames_lower)):
        return raw  # not a Kraken trades export

    # Build a case-insensitive column lookup
    col_map = {f.lower(): f for f in reader.fieldnames}

    def _get(row: dict, key: str) -> str:
        original = col_map.get(key, key)
        return (row.get(original) or "").strip()

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["trade_date", "asset_code", "quantity", "price", "currency", "fee", "tx_type"])

    has_rows = False
    for row in reader:
        pair = _get(row, "pair").upper()
        trade_time = _get(row, "time")
        tx_type = _get(row, "type").lower()
        price = _get(row, "price")
        vol = _get(row, "vol")
        fee = _get(row, "fee") or "0"

        if not pair or not trade_time or not vol:
            continue
        if tx_type not in ("buy", "sell"):
            # Skip transfers, deposits, staking, etc.
            continue

        asset_code, currency = _parse_pair(pair)
        if not asset_code:
            continue

        # Take only the date part from the timestamp
        trade_date = trade_time.split(" ")[0] if " " in trade_time else trade_time

        writer.writerow([trade_date, asset_code, vol, price, currency, fee, tx_type])
        has_rows = True

    if not has_rows:
        return raw
    return out.getvalue().encode("utf-8")


def _parse_pair(pair: str) -> tuple[str, str]:
    """
    Extract (base_asset, quote_currency) from a Kraken pair string.
    Examples: XXBTZUSD → (BTC, USD), XETHZEUR → (ETH, EUR), SOLUSD → (SOL, USD)
    """
    # Try stripping known quote currencies from the end
    for quote_raw in _QUOTE_CURRENCIES:
        if pair.endswith(quote_raw):
            base_raw = pair[: -len(quote_raw)]
            base = _ASSET_MAP.get(base_raw, base_raw)
            quote = _ASSET_MAP.get(quote_raw, quote_raw)
            return base, quote

    # Try matching known asset map keys from the start
    for k, v in _ASSET_MAP.items():
        if pair.startswith(k):
            remainder = pair[len(k):]
            quote = _ASSET_MAP.get(remainder, remainder)
            return v, quote

    # Last resort: return the pair itself
    return pair, "USD"


def parse(path: str):
    """Legacy file-path interface."""
    from pathlib import Path
    return preprocess(Path(path).read_bytes())
