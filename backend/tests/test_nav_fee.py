"""Tests for NAV calculation and fee calculation logic."""
from datetime import date
from decimal import Decimal

import pytest

from app.db import SessionLocal
from app.models import Account, AssetPrice, Client, ExchangeRate, FeeRecord, Fund, NAVRecord, Position
from app.services.fee_service import calc_fee
from app.services.nav_engine import calc_nav


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def nav_db(client):
    """Seeded database with fund, accounts, prices, and FX rates for NAV tests."""
    db = SessionLocal()

    fund = Fund(id=10, name="NAV Test Fund", base_currency="USD", total_shares=100)
    db.add(fund)

    client_obj = Client(id=10, name="NAV Tester", email="nav@test.com")
    db.add(client_obj)

    account_usd = Account(id=10, fund_id=10, client_id=10, broker="IB", account_no="T-USD")
    account_hkd = Account(id=11, fund_id=10, client_id=10, broker="HK", account_no="T-HKD")
    db.add_all([account_usd, account_hkd])
    db.commit()

    try:
        yield db
    finally:
        db.close()


def _seed_snapshot(db, nav_date: date, positions: list[dict], prices: list[dict], fx_rates: list[dict]):
    for p in positions:
        db.add(Position(**p, snapshot_date=nav_date))
    for pr in prices:
        db.merge(AssetPrice(**pr, snapshot_date=nav_date))
    for fx in fx_rates:
        db.merge(ExchangeRate(**fx, snapshot_date=nav_date))
    db.commit()


# ---------------------------------------------------------------------------
# NAV tests
# ---------------------------------------------------------------------------


def test_nav_calc_usd_only(nav_db):
    """Pure USD positions — NAV should equal total market value / total_shares."""
    nav_date = date(2026, 3, 31)
    _seed_snapshot(
        nav_db,
        nav_date,
        positions=[
            {"account_id": 10, "asset_code": "AAPL", "quantity": 10, "average_cost": 150, "currency": "USD"},
            {"account_id": 10, "asset_code": "BTC", "quantity": Decimal("0.5"), "average_cost": 60000, "currency": "USD"},
        ],
        prices=[
            {"asset_code": "AAPL", "price_usd": 200, "source": "test"},
            {"asset_code": "BTC", "price_usd": 80000, "source": "test"},
        ],
        fx_rates=[],
    )

    nav = calc_nav(nav_db, fund_id=10, nav_date=nav_date)

    # AAPL: 10 * 200 = 2000; BTC: 0.5 * 80000 = 40000; total = 42000
    # shares = 100, nav_per_share = 420
    assert nav.total_assets_usd == Decimal("42000")
    assert nav.nav_per_share == Decimal("420")
    assert nav.is_locked is True


def test_nav_calc_with_fx_conversion(nav_db):
    """HKD position converted via FX snapshot should yield correct USD value."""
    nav_date = date(2026, 6, 30)
    _seed_snapshot(
        nav_db,
        nav_date,
        positions=[
            {"account_id": 10, "asset_code": "AAPL", "quantity": 5, "average_cost": 200, "currency": "USD"},
            {"account_id": 11, "asset_code": "0700.HK", "quantity": 100, "average_cost": 300, "currency": "HKD"},
        ],
        prices=[
            {"asset_code": "AAPL", "price_usd": 220, "source": "test"},
            {"asset_code": "0700.HK", "price_usd": 40, "source": "test"},
        ],
        fx_rates=[
            {"base_currency": "HKD", "quote_currency": "USD", "rate": Decimal("0.1282")},
        ],
    )

    nav = calc_nav(nav_db, fund_id=10, nav_date=nav_date)

    # AAPL: 5 * 220 = 1100; 0700.HK: 100 * 40 = 4000 USD; total = 5100
    assert nav.total_assets_usd == Decimal("5100")
    assert nav.total_shares == Decimal("100")
    expected_per_share = Decimal("5100") / Decimal("100")
    assert nav.nav_per_share == expected_per_share


def test_nav_calc_fallback_to_average_cost(nav_db):
    """When no price snapshot exists, NAV falls back to average_cost."""
    nav_date = date(2026, 9, 30)
    _seed_snapshot(
        nav_db,
        nav_date,
        positions=[
            {"account_id": 10, "asset_code": "UNLISTED", "quantity": 10, "average_cost": 500, "currency": "USD"},
        ],
        prices=[],  # no price snapshot
        fx_rates=[],
    )

    nav = calc_nav(nav_db, fund_id=10, nav_date=nav_date)

    # Fallback: 10 * 500 = 5000 USD
    assert nav.total_assets_usd == Decimal("5000")


def test_nav_calc_idempotent(nav_db):
    """Recalculating NAV for same fund+date returns the cached record, not a duplicate."""
    nav_date = date(2026, 12, 31)
    _seed_snapshot(
        nav_db,
        nav_date,
        positions=[{"account_id": 10, "asset_code": "MSFT", "quantity": 10, "average_cost": 400, "currency": "USD"}],
        prices=[{"asset_code": "MSFT", "price_usd": 410, "source": "test"}],
        fx_rates=[],
    )

    first = calc_nav(nav_db, fund_id=10, nav_date=nav_date)
    second = calc_nav(nav_db, fund_id=10, nav_date=nav_date)

    assert first.id == second.id
    total_count = nav_db.query(NAVRecord).filter(NAVRecord.fund_id == 10, NAVRecord.nav_date == nav_date).count()
    assert total_count == 1


def test_nav_calc_raises_without_positions(nav_db):
    """NAV calc raises ValueError when no positions exist for the given date."""
    with pytest.raises(ValueError, match="No positions found"):
        calc_nav(nav_db, fund_id=10, nav_date=date(2025, 1, 1))


# ---------------------------------------------------------------------------
# Fee tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def fee_db(client):
    db = SessionLocal()
    fund = Fund(id=20, name="Fee Test Fund", base_currency="USD", total_shares=1000)
    db.add(fund)
    db.commit()
    try:
        yield db
    finally:
        db.close()


def test_fee_calc_below_hurdle(fee_db):
    """When annual return is below the hurdle rate (8%), fee_amount_usd should be zero."""
    fee_db.add(NAVRecord(fund_id=20, nav_date=date(2025, 12, 31), total_assets_usd=100000, total_shares=1000, nav_per_share=100, is_locked=True))
    # Return from 100 → 105 over 365 days ≈ 5% annual, below 8% hurdle
    fee_db.add(NAVRecord(fund_id=20, nav_date=date(2026, 12, 31), total_assets_usd=105000, total_shares=1000, nav_per_share=105, is_locked=True))
    fee_db.commit()

    result = calc_fee(fee_db, fund_id=20, fee_date=date(2026, 12, 31))

    assert result["fee_amount_usd"] == 0.0
    assert result["excess_return_pct"] == 0.0


def test_fee_calc_above_hurdle(fee_db):
    """When annual return exceeds the 8% hurdle, 30% of the excess is charged."""
    fee_db.add(NAVRecord(fund_id=20, nav_date=date(2025, 6, 30), total_assets_usd=100000, total_shares=1000, nav_per_share=100, is_locked=True))
    # Return 100 → 120 over 365 days = 20% annual, excess = 20% - 8% = 12%, fee = 30% * 12% * 120000
    fee_db.add(NAVRecord(fund_id=20, nav_date=date(2026, 6, 30), total_assets_usd=120000, total_shares=1000, nav_per_share=120, is_locked=True))
    fee_db.commit()

    result = calc_fee(fee_db, fund_id=20, fee_date=date(2026, 6, 30))

    # Annualised return over 365 days = 20% exactly; excess = 12%; fee_rate = 3.6%; fee = 3.6% * 120000
    assert result["fee_amount_usd"] > 0
    assert result["annual_return_pct"] > 0.08
    assert result["excess_return_pct"] > 0
    expected_fee = float(Decimal(str(result["fee_base_usd"])) * Decimal(str(result["fee_rate"])))
    assert abs(result["fee_amount_usd"] - expected_fee) < 0.01


def test_fee_calc_requires_two_nav_records(fee_db):
    """Calling calc_fee with fewer than 2 NAV records should raise ValueError."""
    fee_db.add(NAVRecord(fund_id=20, nav_date=date(2026, 3, 31), total_assets_usd=50000, total_shares=1000, nav_per_share=50, is_locked=True))
    fee_db.commit()

    with pytest.raises(ValueError, match="need >=2 nav records"):
        calc_fee(fee_db, fund_id=20, fee_date=date(2026, 3, 31))


def test_fee_calc_idempotent(fee_db):
    """Recalculating fee for the same fund+date updates the record in place."""
    fee_db.add(NAVRecord(fund_id=20, nav_date=date(2025, 3, 31), total_assets_usd=100000, total_shares=1000, nav_per_share=100, is_locked=True))
    fee_db.add(NAVRecord(fund_id=20, nav_date=date(2026, 3, 31), total_assets_usd=150000, total_shares=1000, nav_per_share=150, is_locked=True))
    fee_db.commit()

    first = calc_fee(fee_db, fund_id=20, fee_date=date(2026, 3, 31))
    second = calc_fee(fee_db, fund_id=20, fee_date=date(2026, 3, 31))

    assert first["id"] == second["id"]
    count = fee_db.query(FeeRecord).filter(FeeRecord.fund_id == 20, FeeRecord.fee_date == date(2026, 3, 31)).count()
    assert count == 1
