"""Tests for the complete CSV import workflow (upload -> preview -> confirm -> verify)."""
import pytest

from app.db import SessionLocal
from app.models import Account, Position, Transaction
from app.services.auth import bootstrap_auth_users


VALID_CSV = (
    b"trade_date,asset_code,quantity,price,currency,tx_type,fee,snapshot_date\n"
    b"2026-03-31,AAPL,10,200,USD,buy,1,2026-03-31\n"
    b"2026-03-31,BTC,0.5,80000,USD,buy,2,2026-03-31\n"
)

MISSING_COLUMNS_CSV = b"trade_date,asset_code,quantity\n2026-03-31,AAPL,10\n"

DUPLICATE_ASSET_CSV = (
    b"trade_date,asset_code,quantity,price,currency,tx_type,fee,snapshot_date\n"
    b"2026-03-31,AAPL,10,200,USD,buy,1,2026-03-31\n"
    b"2026-03-31,AAPL,5,210,USD,buy,0,2026-03-31\n"
)


@pytest.fixture()
def import_db(client):
    db = SessionLocal()
    db.add(Account(id=40, broker="IB", account_no="IMP-001", holder_name="Import Test"))
    db.commit()
    bootstrap_auth_users(db)
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def admin_headers(client, import_db):
    resp = client.post("/auth/login", data={"username": "admin", "password": "Admin12345"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Upload tests
# ---------------------------------------------------------------------------


def test_upload_creates_parsed_batch(client, import_db, admin_headers):
    resp = client.post(
        "/import/upload",
        headers=admin_headers,
        files={"file": ("test.csv", VALID_CSV, "text/csv")},
        data={"source": "csv", "account_id": "40"},
    )
    assert resp.status_code == 200
    batch = resp.json()
    assert batch["status"] == "parsed"
    assert batch["row_count"] == 2
    assert batch["parsed_count"] == 2
    assert len(batch["preview_rows"]) == 2


def test_upload_with_invalid_csv_creates_failed_batch(client, import_db, admin_headers):
    resp = client.post(
        "/import/upload",
        headers=admin_headers,
        files={"file": ("bad.csv", MISSING_COLUMNS_CSV, "text/csv")},
        data={"source": "csv", "account_id": "40"},
    )
    assert resp.status_code == 200
    batch = resp.json()
    assert batch["status"] == "failed"
    assert batch["failed_reason"] is not None


def test_upload_normalises_asset_codes_and_currencies(client, import_db, admin_headers):
    lowercase_csv = (
        b"trade_date,asset_code,quantity,price,currency,tx_type,fee,snapshot_date\n"
        b"2026-03-31,aapl,10,200,usd,buy,1,2026-03-31\n"
    )
    resp = client.post(
        "/import/upload",
        headers=admin_headers,
        files={"file": ("lower.csv", lowercase_csv, "text/csv")},
        data={"source": "csv", "account_id": "40"},
    )
    batch = resp.json()
    assert batch["preview_rows"][0]["asset_code"] == "AAPL"
    assert batch["preview_rows"][0]["currency"] == "USD"


# ---------------------------------------------------------------------------
# Confirm tests
# ---------------------------------------------------------------------------


def test_confirm_writes_transactions_and_positions(client, import_db, admin_headers):
    # Upload
    upload_resp = client.post(
        "/import/upload",
        headers=admin_headers,
        files={"file": ("test.csv", VALID_CSV, "text/csv")},
        data={"source": "csv", "account_id": "40"},
    )
    batch_id = upload_resp.json()["id"]

    # Confirm
    confirm_resp = client.post(f"/import/{batch_id}/confirm", headers=admin_headers)
    assert confirm_resp.status_code == 200
    confirmed = confirm_resp.json()
    assert confirmed["status"] == "confirmed"
    assert confirmed["confirmed_count"] == 2

    # Verify transactions were written
    db = SessionLocal()
    tx_count = db.query(Transaction).filter(Transaction.import_batch_id == batch_id).count()
    assert tx_count == 2

    # Verify positions were written (AAPL + BTC for snapshot 2026-03-31)
    pos_count = db.query(Position).filter(Position.account_id == 40).count()
    assert pos_count == 2
    db.close()


def test_confirm_aggregates_duplicate_assets_into_single_position(client, import_db, admin_headers):
    upload_resp = client.post(
        "/import/upload",
        headers=admin_headers,
        files={"file": ("dup.csv", DUPLICATE_ASSET_CSV, "text/csv")},
        data={"source": "csv", "account_id": "40"},
    )
    batch_id = upload_resp.json()["id"]
    client.post(f"/import/{batch_id}/confirm", headers=admin_headers)

    db = SessionLocal()
    positions = db.query(Position).filter(Position.account_id == 40, Position.asset_code == "AAPL").all()
    db.close()
    # Two buy rows for AAPL on the same snapshot date -> one aggregated position
    assert len(positions) == 1
    assert positions[0].quantity == 15  # 10 + 5


def test_confirm_idempotent(client, import_db, admin_headers):
    """Confirming an already-confirmed batch returns it without error."""
    upload_resp = client.post(
        "/import/upload",
        headers=admin_headers,
        files={"file": ("test.csv", VALID_CSV, "text/csv")},
        data={"source": "csv", "account_id": "40"},
    )
    batch_id = upload_resp.json()["id"]

    first = client.post(f"/import/{batch_id}/confirm", headers=admin_headers)
    assert first.status_code == 200

    second = client.post(f"/import/{batch_id}/confirm", headers=admin_headers)
    assert second.status_code == 200
    assert second.json()["status"] == "confirmed"


def test_confirm_nonexistent_batch_returns_error(client, import_db, admin_headers):
    resp = client.post("/import/9999/confirm", headers=admin_headers)
    assert resp.status_code == 400
    assert "not found" in resp.json()["detail"]


def test_confirm_failed_batch_returns_400(client, import_db, admin_headers):
    upload_resp = client.post(
        "/import/upload",
        headers=admin_headers,
        files={"file": ("bad.csv", MISSING_COLUMNS_CSV, "text/csv")},
        data={"source": "csv", "account_id": "40"},
    )
    batch_id = upload_resp.json()["id"]

    resp = client.post(f"/import/{batch_id}/confirm", headers=admin_headers)
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Auth tests for import endpoints
# ---------------------------------------------------------------------------


def test_import_upload_requires_auth(client, import_db):
    resp = client.post(
        "/import/upload",
        files={"file": ("test.csv", VALID_CSV, "text/csv")},
        data={"source": "csv", "account_id": "40"},
    )
    assert resp.status_code == 401


def test_import_list_requires_auth(client, import_db):
    resp = client.get("/import")
    assert resp.status_code == 401
