import os
from datetime import date
from pathlib import Path

TEST_DB = Path("/tmp/invest_week4_test.sqlite3")
if TEST_DB.exists():
    TEST_DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["SCHEDULER_ENABLED"] = "false"

from fastapi.testclient import TestClient

from app.db import Base, SessionLocal, engine
from app.main import app
from app.models import Account, Client, ExchangeRate, Fund, NAVRecord, ShareTransaction

client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    db.add(Fund(id=1, name="Demo Fund", base_currency="USD", total_shares=100))
    db.add(Fund(id=2, name="Other Fund", base_currency="USD", total_shares=50))
    db.add(Client(id=1, name="Alice", email="alice@example.com"))
    db.add(Client(id=2, name="Bob", email="bob@example.com"))
    db.add(Account(id=1, fund_id=1, client_id=1, broker="IB", account_no="ACC-001"))
    db.add(Account(id=2, fund_id=2, client_id=2, broker="IB", account_no="ACC-002"))
    db.add(NAVRecord(id=1, fund_id=1, nav_date=date(2026, 6, 30), total_assets_usd=1000, total_shares=100, nav_per_share=10, is_locked=True))
    db.add(NAVRecord(id=2, fund_id=2, nav_date=date(2026, 6, 30), total_assets_usd=2000, total_shares=50, nav_per_share=40, is_locked=True))
    db.add(ShareTransaction(id=1, fund_id=1, client_id=1, tx_date=date(2026, 6, 30), tx_type="subscribe", amount_usd=100, shares=10, nav_at_date=10))
    db.add(ShareTransaction(id=2, fund_id=2, client_id=2, tx_date=date(2026, 6, 30), tx_type="subscribe", amount_usd=400, shares=10, nav_at_date=40))
    db.commit()
    db.close()


def teardown_function():
    Base.metadata.drop_all(bind=engine)


def test_client_readonly_is_scoped_to_own_customer_data():
    response = client.get("/customer/1", headers={"x-dev-role": "client-readonly", "x-client-id": "1"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["client"]["id"] == 1
    assert all(account["client_id"] == 1 for account in payload["accounts"])

    forbidden = client.get("/customer/2", headers={"x-dev-role": "client-readonly", "x-client-id": "1"})
    assert forbidden.status_code == 403


def test_ops_share_subscribe_creates_audit_log():
    response = client.post(
        "/share/subscribe",
        headers={"x-dev-role": "ops", "x-operator-id": "ops-user"},
        json={"fund_id": 1, "client_id": 1, "tx_date": "2026-06-30", "amount_usd": "50"},
    )
    assert response.status_code == 200

    audit_response = client.get("/audit", headers={"x-dev-role": "ops"})
    assert audit_response.status_code == 200
    audit_rows = audit_response.json()
    assert any(row["action"] == "share.subscribe" and row["actor_id"] == "ops-user" for row in audit_rows)


def test_scheduler_manual_trigger_runs_and_records_job(monkeypatch):
    from app.services import scheduler as scheduler_service

    def fake_fetch_and_save_rates(db, base, quote, snapshot_date):
        row = ExchangeRate(base_currency=base, quote_currency=quote, rate=1.23, snapshot_date=snapshot_date)
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    monkeypatch.setattr(scheduler_service, "fetch_and_save_rates", fake_fetch_and_save_rates)
    response = client.post("/scheduler/jobs/fx-weekly/run", headers={"x-dev-role": "ops", "x-operator-id": "ops-user"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["job_name"] == "fx-weekly"
    assert payload["fetched"]

    jobs_response = client.get("/scheduler/jobs", headers={"x-dev-role": "ops"})
    assert jobs_response.status_code == 200
    assert any(row["job_name"] == "fx-weekly" and row["status"] == "success" for row in jobs_response.json())


def test_redeem_failure_returns_validation_error():
    response = client.post(
        "/share/redeem",
        headers={"x-dev-role": "ops", "x-operator-id": "ops-user"},
        json={"fund_id": 1, "client_id": 1, "tx_date": "2026-06-30", "amount_usd": "5000"},
    )
    assert response.status_code == 400
    assert "exceed" in response.json()["detail"]
