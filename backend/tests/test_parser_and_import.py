from datetime import datetime, timezone

import pytest

from app.services.import_service import _build_positions, _parse_csv_rows


def test_parse_csv_rows_normalizes_values_and_skips_blank_lines():
    content = b"trade_date,asset_code,quantity,price,currency,tx_type,fee,snapshot_date\n2026-03-31,aapl,10,200,usd,buy,1,2026-03-31\n\n"
    rows = _parse_csv_rows(content)
    assert len(rows) == 1
    assert rows[0]["asset_code"] == "AAPL"
    assert rows[0]["currency"] == "USD"
    assert rows[0]["fee"] == "1"


def test_parse_csv_rows_rejects_missing_required_columns():
    content = b"trade_date,asset_code,quantity\n2026-03-31,AAPL,10\n"
    with pytest.raises(ValueError, match="missing required columns"):
        _parse_csv_rows(content)


def test_parse_csv_rows_accepts_alias_columns_and_common_formats():
    content = b"Date,Ticker,Shares,Execution Price,CCY,Side,Commission,As Of\n03/31/2026,msft,1,234.56,usd,sell,$1.25,2026/03/31\n"
    rows = _parse_csv_rows(content)
    assert rows == [
        {
            "row_number": 2,
            "trade_date": "2026-03-31",
            "asset_code": "MSFT",
            "quantity": "-1",
            "price": "234.56",
            "currency": "USD",
            "tx_type": "sell",
            "fee": "1.25",
            "snapshot_date": "2026-03-31",
        }
    ]


def test_parse_csv_rows_supports_parentheses_for_negative_fee():
    content = b"trade_date,asset_code,quantity,price,currency,tx_type,fee\n2026-03-31,AAPL,10,200,USD,buy,(1.50)\n"
    rows = _parse_csv_rows(content)
    assert rows[0]["fee"] == "-1.50"


def test_build_positions_aggregates_cost_basis_per_snapshot():
    preview_rows = [
        {
            "row_number": 2,
            "trade_date": "2026-03-31",
            "asset_code": "AAPL",
            "quantity": "10",
            "price": "100",
            "currency": "USD",
            "tx_type": "buy",
            "fee": "5",
            "snapshot_date": "2026-03-31",
        },
        {
            "row_number": 3,
            "trade_date": "2026-03-31",
            "asset_code": "AAPL",
            "quantity": "5",
            "price": "120",
            "currency": "USD",
            "tx_type": "buy",
            "fee": "0",
            "snapshot_date": "2026-03-31",
        },
    ]
    positions = _build_positions(account_id=1, preview_rows=preview_rows)
    assert len(positions) == 1
    assert str(positions[0]["quantity"]) == "15"
    assert round(float(positions[0]["average_cost"]), 6) == round((10 * 100 + 5 + 5 * 120) / 15, 6)


def test_build_positions_reduces_cost_basis_after_sell():
    preview_rows = [
        {
            "row_number": 2,
            "trade_date": "2026-03-01",
            "asset_code": "AAPL",
            "quantity": "10",
            "price": "100",
            "currency": "USD",
            "tx_type": "buy",
            "fee": "0",
            "snapshot_date": "2026-03-01",
        },
        {
            "row_number": 3,
            "trade_date": "2026-03-10",
            "asset_code": "AAPL",
            "quantity": "-4",
            "price": "130",
            "currency": "USD",
            "tx_type": "sell",
            "fee": "2",
            "snapshot_date": "2026-03-10",
        },
    ]
    positions = _build_positions(account_id=1, preview_rows=preview_rows)
    assert len(positions) == 2
    latest = positions[-1]
    assert str(latest["quantity"]) == "6"
    assert round(float(latest["average_cost"]), 6) == round((600 + 2) / 6, 6)


def test_build_positions_rejects_sell_above_current_position():
    preview_rows = [
        {
            "row_number": 2,
            "trade_date": "2026-03-10",
            "asset_code": "AAPL",
            "quantity": "-4",
            "price": "130",
            "currency": "USD",
            "tx_type": "sell",
            "fee": "2",
            "snapshot_date": "2026-03-10",
        },
    ]
    with pytest.raises(ValueError, match="sell quantity exceeds current position"):
        _build_positions(account_id=1, preview_rows=preview_rows)


# ---------------------------------------------------------------------------
# IB parser tests
# ---------------------------------------------------------------------------

from app.services.parser import ib_parser


_IB_SAMPLE = b"""\
Trades,Header,DataDiscriminator,Asset Category,Currency,Symbol,Date/Time,Quantity,T. Price,C. Price,Proceeds,Comm/Fee,Basis,Realized P/L,MTM P/L,Code
Trades,Data,Order,Stocks,USD,AAPL,"2024-01-15, 09:30:00",100,185.50,186.00,-18550,-1.50,-18551.50,,,
Trades,Data,Order,Stocks,USD,GOOGL,"2024-01-16, 10:00:00",-50,140.00,140.50,7000,-1.00,7001,100,,
Trades,SubTotal,,,,,,,,,,,,,,
Trades,Total,,,,,,,,,,,,,,
"""


def test_ib_preprocess_extracts_trades_section():
    result = ib_parser.preprocess(_IB_SAMPLE)
    rows = _parse_csv_rows(result)
    assert len(rows) == 2


def test_ib_preprocess_buy_sell_sign():
    result = ib_parser.preprocess(_IB_SAMPLE)
    rows = _parse_csv_rows(result)
    by_asset = {r["asset_code"]: r for r in rows}
    assert by_asset["AAPL"]["tx_type"] == "buy"
    assert by_asset["GOOGL"]["tx_type"] == "sell"


def test_ib_preprocess_quantity_is_positive():
    result = ib_parser.preprocess(_IB_SAMPLE)
    rows = _parse_csv_rows(result)
    for row in rows:
        assert float(row["quantity"]) > 0


def test_ib_preprocess_fee_is_positive():
    result = ib_parser.preprocess(_IB_SAMPLE)
    rows = _parse_csv_rows(result)
    for row in rows:
        assert float(row["fee"]) >= 0


def test_ib_preprocess_returns_raw_for_unknown_format():
    raw = b"date,asset_code,quantity,price,currency,tx_type\n2024-01-01,AAPL,10,100,USD,buy\n"
    result = ib_parser.preprocess(raw)
    # Falls back to raw — still parseable as standard CSV
    rows = _parse_csv_rows(result)
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# Kraken parser tests
# ---------------------------------------------------------------------------

from app.services.parser import kraken_parser


_KRAKEN_SAMPLE = b"""\
txid,ordertxid,pair,time,type,ordertype,price,cost,fee,vol,margin,misc,ledgers
TID001,OID001,XXBTZUSD,2024-01-15 10:30:00,buy,limit,43000.00,4300.00,6.45,0.1,0,,
TID002,OID002,XETHZUSD,2024-01-16 11:00:00,sell,market,2200.00,2200.00,3.30,1.0,0,,
TID003,OID003,SOLUSD,2024-01-17 12:00:00,buy,limit,95.00,950.00,1.43,10,0,,
"""


def test_kraken_preprocess_parses_known_pairs():
    result = kraken_parser.preprocess(_KRAKEN_SAMPLE)
    rows = _parse_csv_rows(result)
    assert len(rows) == 3


def test_kraken_preprocess_normalises_asset_codes():
    result = kraken_parser.preprocess(_KRAKEN_SAMPLE)
    rows = _parse_csv_rows(result)
    assets = {r["asset_code"] for r in rows}
    assert "BTC" in assets
    assert "ETH" in assets
    assert "SOL" in assets


def test_kraken_preprocess_buy_sell_preserved():
    result = kraken_parser.preprocess(_KRAKEN_SAMPLE)
    rows = _parse_csv_rows(result)
    by_asset = {r["asset_code"]: r for r in rows}
    assert by_asset["BTC"]["tx_type"] == "buy"
    assert by_asset["ETH"]["tx_type"] == "sell"


def test_kraken_preprocess_parse_pair_xxbt():
    asset, currency = kraken_parser._parse_pair("XXBTZUSD")
    assert asset == "BTC"
    assert currency == "USD"


def test_kraken_preprocess_parse_pair_sol():
    asset, currency = kraken_parser._parse_pair("SOLUSD")
    assert asset == "SOL"
    assert currency == "USD"


# ---------------------------------------------------------------------------
# Schwab parser tests
# ---------------------------------------------------------------------------

from app.services.parser import schwab_parser


_SCHWAB_SAMPLE = b"""\
"Transactions  for account XXXX-1234 as of 01/20/2024, 06:00:00 ET"
""
"Date","Action","Symbol","Description","Quantity","Price","Fees & Comm","Amount"
"01/15/2024","Buy","AAPL","APPLE INC","100","$185.50","$1.50","-$18,551.50"
"01/16/2024","Sell","GOOGL","ALPHABET INC C","50","$140.00","$1.00","$6,999.00"
"01/20/2024","Reinvest Shares","MSFT","MICROSOFT CORP","0.54","$380.00","","$205.20"
"01/18/2024","Cash Dividend","AAPL","APPLE INC","","","","$10.00"
"","","","","","","",""
"Transactions Total","","","","","","","-$11,337.30"
"""


def test_schwab_preprocess_parses_trades():
    result = schwab_parser.preprocess(_SCHWAB_SAMPLE)
    rows = _parse_csv_rows(result)
    # Buy, Sell, Reinvest Shares → 3 rows; Cash Dividend + totals skipped
    assert len(rows) == 3


def test_schwab_preprocess_skips_dividends_and_totals():
    result = schwab_parser.preprocess(_SCHWAB_SAMPLE)
    rows = _parse_csv_rows(result)
    assets = {r["asset_code"] for r in rows}
    assert "AAPL" in assets  # from Buy row (Dividend row skipped)
    assert len(rows) == 3


def test_schwab_preprocess_buy_sell_types():
    result = schwab_parser.preprocess(_SCHWAB_SAMPLE)
    rows = _parse_csv_rows(result)
    by_asset_type = {(r["asset_code"], r["tx_type"]) for r in rows}
    assert ("AAPL", "buy") in by_asset_type
    assert ("GOOGL", "sell") in by_asset_type
    assert ("MSFT", "buy") in by_asset_type


def test_schwab_clean_amount_strips_dollar_and_commas():
    assert schwab_parser._clean_amount("$18,551.50") == "18551.50"
    assert schwab_parser._clean_amount("($1.50)") == "-1.50"
    assert schwab_parser._clean_amount("") == ""


# ---------------------------------------------------------------------------
# Moomoo parser tests
# ---------------------------------------------------------------------------

from app.services.parser import moomoo_parser


_MOOMOO_SAMPLE = b"""\
Date,Symbol,Side,Qty.,Avg. Price,Trading Fees,Status
2024-01-15,AAPL,Buy,100,185.50,1.50,Filled
2024-01-16,GOOGL,Sell,50,140.00,1.00,Filled
2024-01-17,TSLA,Buy,20,200.00,0.50,Cancelled
2024-01-18,NVDA,Buy,10,500.00,0.80,Filled
"""


def test_moomoo_preprocess_parses_filled_orders():
    result = moomoo_parser.preprocess(_MOOMOO_SAMPLE)
    rows = _parse_csv_rows(result)
    # Only Filled rows (3 rows; Cancelled skipped)
    assert len(rows) == 3


def test_moomoo_preprocess_skips_cancelled():
    result = moomoo_parser.preprocess(_MOOMOO_SAMPLE)
    rows = _parse_csv_rows(result)
    assets = {r["asset_code"] for r in rows}
    assert "TSLA" not in assets


def test_moomoo_preprocess_buy_sell_mapping():
    result = moomoo_parser.preprocess(_MOOMOO_SAMPLE)
    rows = _parse_csv_rows(result)
    by_asset = {r["asset_code"]: r for r in rows}
    assert by_asset["AAPL"]["tx_type"] == "buy"
    assert by_asset["GOOGL"]["tx_type"] == "sell"


_MOOMOO_SAMPLE_ZH = b"""\
\xe6\x88\x90\xe4\xba\xa4\xe6\x97\xb6\xe9\x97\xb4,\xe8\x82\xa1\xe7\xa5\xa8\xe4\xbb\xa3\xe7\xa0\x81,\xe4\xb9\xb0\xe5\x8d\x96,\xe6\x88\x90\xe4\xba\xa4\xe6\x95\xb0\xe9\x87\x8f,\xe6\x88\x90\xe4\xba\xa4\xe5\x9d\x87\xe4\xbb\xb7,\xe6\x89\x8b\xe7\xbb\xad\xe8\xb4\xb9,\xe7\x8a\xb6\xe6\x80\x81
2024-01-15 09:30:00,AAPL,\xe4\xb9\xb0\xe5\x85\xa5,100,185.50,1.50,\xe5\x85\xa8\xe9\x83\xa8\xe6\x88\x90\xe4\xba\xa4
"""


def test_moomoo_preprocess_chinese_columns():
    result = moomoo_parser.preprocess(_MOOMOO_SAMPLE_ZH)
    rows = _parse_csv_rows(result)
    assert len(rows) == 1
    assert rows[0]["asset_code"] == "AAPL"
    assert rows[0]["tx_type"] == "buy"
