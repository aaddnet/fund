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
    try:
        _parse_csv_rows(content)
    except ValueError as exc:
        assert "missing required columns" in str(exc)
    else:
        raise AssertionError("expected ValueError for missing columns")


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
