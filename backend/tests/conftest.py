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
    '{"username":"readonly","password":"Readonly1234","role":"readonly"}]'
)

from app.db import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Account, ExchangeRate, NAVRecord, Transaction  # noqa: E402
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
    db.add(Account(id=1, broker="IB", account_no="ACC-001", holder_name="Alice"))
    db.add(Account(id=2, broker="moomoo", account_no="ACC-002", holder_name="Bob"))
    db.add(NAVRecord(id=1, nav_date=date(2026, 6, 30), total_assets_usd=50000, is_locked=True))
    db.add(Transaction(
        account_id=1, trade_date=date(2026, 6, 30), asset_code="AAPL",
        quantity=10, price=200, currency="USD", tx_type="buy", tx_category="TRADE",
        source="manual", fee=1,
    ))
    db.commit()
    bootstrap_auth_users(db)
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def admin_token(client):
    response = client.post("/auth/login", data={"username": "admin", "password": "Admin12345"})
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture()
def readonly_token(client, seeded_db):
    response = client.post("/auth/login", data={"username": "readonly", "password": "Readonly1234"})
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture()
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}
