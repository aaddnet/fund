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
