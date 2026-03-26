import os
import sys
import types
from datetime import date
from pathlib import Path

import pytest

# Provide a minimal multitasking stub so yfinance can be imported in test environments
# where the multitasking wheel fails to build (missing legacy distutils support).
if "multitasking" not in sys.modules:
    _mt = types.ModuleType("multitasking")
    _mt.task = lambda f: f  # type: ignore[attr-defined]
    _mt.is_main_thread = lambda: True  # type: ignore[attr-defined]
    sys.modules["multitasking"] = _mt

sys.path.append(str(Path(__file__).resolve().parents[1]))
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

TEST_DB = Path("/tmp/invest_test.sqlite3")
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["SCHEDULER_ENABLED"] = "false"
os.environ["AUTH_MODE"] = "token"
os.environ["AUTH_ALLOW_DEV_FALLBACK"] = "false"
os.environ["AUTH_BOOTSTRAP_USERS_JSON"] = (
    '[{"username":"admin","password":"Admin12345","role":"admin"},'
    '{"username":"ops","password":"Ops1234567","role":"ops"},'
    '{"username":"viewer","password":"Viewer12345","role":"ops-readonly"},'
    '{"username":"client1","password":"Client12345","role":"client-readonly","client_scope_id":1}]'
)

from app.db import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Account, Client, ExchangeRate, Fund, NAVRecord, ShareTransaction  # noqa: E402
from app.services.auth import bootstrap_auth_users  # noqa: E402


@pytest.fixture()
def client():
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
    try:
        command.downgrade(config, "base")
    except Exception:
        pass
    command.upgrade(config, "head")

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def seeded_db(client):
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
    bootstrap_auth_users(db)
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def ops_token(client):
    response = client.post("/auth/login", data={"username": "ops", "password": "Ops1234567"})
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture()
def client_token(client, seeded_db):
    response = client.post("/auth/login", data={"username": "client1", "password": "Client12345"})
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture()
def auth_headers(ops_token):
    return {"Authorization": f"Bearer {ops_token}"}


@pytest.fixture()
def client_headers(client_token):
    return {"Authorization": f"Bearer {client_token}"}
