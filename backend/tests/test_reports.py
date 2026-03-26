"""Tests for the /reports/overview and /reports/export endpoints."""
from datetime import date

import pytest

from app.db import SessionLocal
from app.models import Account, Client, FeeRecord, Fund, NAVRecord, ShareTransaction
from app.services.auth import bootstrap_auth_users


@pytest.fixture()
def reports_db(client):
    db = SessionLocal()
    db.add(Fund(id=30, name="Report Fund A", base_currency="USD", total_shares=200))
    db.add(Fund(id=31, name="Report Fund B", base_currency="USD", total_shares=100))
    db.add(Client(id=30, name="Report Client", email="report@test.com"))
    db.add(Client(id=31, name="Other Client", email="other@test.com"))
    db.add(Account(id=30, fund_id=30, client_id=30, broker="IB", account_no="R-001"))
    db.add(Account(id=31, fund_id=31, client_id=31, broker="IB", account_no="R-002"))

    # Q1 2026 NAV records
    db.add(NAVRecord(fund_id=30, nav_date=date(2026, 3, 31), total_assets_usd=20000, total_shares=200, nav_per_share=100, is_locked=True))
    db.add(NAVRecord(fund_id=31, nav_date=date(2026, 3, 31), total_assets_usd=10000, total_shares=100, nav_per_share=100, is_locked=True))
    # Q2 2026 NAV records
    db.add(NAVRecord(fund_id=30, nav_date=date(2026, 6, 30), total_assets_usd=24000, total_shares=200, nav_per_share=120, is_locked=True))

    # Share transactions
    db.add(ShareTransaction(fund_id=30, client_id=30, tx_date=date(2026, 3, 31), tx_type="subscribe", amount_usd=5000, shares=50, nav_at_date=100))
    db.add(ShareTransaction(fund_id=30, client_id=30, tx_date=date(2026, 6, 30), tx_type="redeem", amount_usd=1200, shares=10, nav_at_date=120))

    # Fee record in Q2
    db.add(FeeRecord(fund_id=30, fee_date=date(2026, 6, 30), gross_return="0.20", fee_rate="0.036", fee_amount_usd=864, nav_start=100, nav_end_before_fee=24000, annual_return_pct="0.20", excess_return_pct="0.12", fee_base_usd=24000, nav_after_fee=23136, applied_date=date(2026, 6, 30)))

    db.commit()
    bootstrap_auth_users(db)
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def ops_headers(client, reports_db):
    resp = client.post("/auth/login", data={"username": "ops", "password": "Ops1234567"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def client30_headers(client, reports_db):
    """client-readonly user scoped to client 30."""
    from app.models import AuthUser
    from app.services.auth import hash_password

    db = SessionLocal()
    if not db.query(AuthUser).filter(AuthUser.username == "client30").first():
        db.add(AuthUser(username="client30", password_hash=hash_password("Client30Pass"), role="client-readonly", client_scope_id=30, display_name="C30", is_active=True, failed_login_attempts=0))
        db.commit()
    db.close()

    resp = client.post("/auth/login", data={"username": "client30", "password": "Client30Pass"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Overview tests
# ---------------------------------------------------------------------------


def test_reports_quarter_filter_returns_correct_date_range(client, reports_db, ops_headers):
    resp = client.get("/reports/overview?period_type=quarter&period_value=2026-Q1", headers=ops_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["filters"]["date_from"] == "2026-01-01"
    assert data["filters"]["date_to"] == "2026-03-31"


def test_reports_month_filter(client, reports_db, ops_headers):
    resp = client.get("/reports/overview?period_type=month&period_value=2026-03", headers=ops_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["filters"]["date_from"] == "2026-03-01"
    assert data["filters"]["date_to"] == "2026-03-31"


def test_reports_year_filter(client, reports_db, ops_headers):
    resp = client.get("/reports/overview?period_type=year&period_value=2026", headers=ops_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["filters"]["date_from"] == "2026-01-01"
    assert data["filters"]["date_to"] == "2026-12-31"
    # Both Q1 and Q2 NAV records should be included
    assert data["summary"]["nav_record_count"] >= 3


def test_reports_q1_contains_subscribe(client, reports_db, ops_headers):
    resp = client.get("/reports/overview?period_type=quarter&period_value=2026-Q1", headers=ops_headers)
    data = resp.json()
    assert data["summary"]["share_tx_count"] == 1
    assert data["summary"]["subscription_amount_usd"] == 5000.0


def test_reports_q2_contains_fee_records_for_ops(client, reports_db, ops_headers):
    resp = client.get("/reports/overview?period_type=quarter&period_value=2026-Q2", headers=ops_headers)
    data = resp.json()
    assert data["summary"]["fee_record_count"] == 1
    assert data["fee_records"][0]["fee_amount_usd"] == 864.0


def test_reports_fee_hidden_from_client_readonly(client, reports_db, client30_headers):
    resp = client.get("/reports/overview?period_type=quarter&period_value=2026-Q2", headers=client30_headers)
    assert resp.status_code == 200
    data = resp.json()
    # client-readonly must not see fee_records
    assert data["fee_records"] == []


def test_reports_client_readonly_scoped_to_own_fund(client, reports_db, client30_headers):
    resp = client.get("/reports/overview?period_type=quarter&period_value=2026-Q1", headers=client30_headers)
    assert resp.status_code == 200
    data = resp.json()
    # Only fund 30 NAV records should be visible (fund 31 belongs to client 31)
    nav_fund_ids = {row["fund_id"] for row in data["nav_records"]}
    assert 31 not in nav_fund_ids


def test_reports_invalid_period_type_returns_400(client, reports_db, ops_headers):
    resp = client.get("/reports/overview?period_type=week&period_value=2026-W01", headers=ops_headers)
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Export tests
# ---------------------------------------------------------------------------


def test_reports_export_csv_returns_file(client, reports_db, ops_headers):
    resp = client.get("/reports/export?period_type=quarter&period_value=2026-Q1", headers=ops_headers)
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    content = resp.text
    assert "# Share Flow" in content
    assert "# NAV Records" in content


def test_reports_export_csv_contains_data(client, reports_db, ops_headers):
    resp = client.get("/reports/export?period_type=quarter&period_value=2026-Q1", headers=ops_headers)
    content = resp.text
    # Q1 subscribe row should be present
    assert "subscribe" in content
    assert "5000" in content


def test_reports_export_requires_auth(client, reports_db):
    resp = client.get("/reports/export?period_type=quarter&period_value=2026-Q1")
    assert resp.status_code == 401
