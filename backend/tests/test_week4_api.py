from datetime import date

from app.models import ExchangeRate


def test_login_returns_bearer_token_and_me_profile(client):
    response = client.post("/auth/login", data={"username": "ops", "password": "ops123"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    token = payload["access_token"]

    me_response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_response.status_code == 200
    assert me_response.json()["actor"]["role"] == "ops"


def test_client_readonly_is_scoped_to_own_customer_data(client, seeded_db, client_headers):
    response = client.get("/customer/1", headers=client_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["client"]["id"] == 1
    assert all(account["client_id"] == 1 for account in payload["accounts"])

    forbidden = client.get("/customer/2", headers=client_headers)
    assert forbidden.status_code == 403


def test_ops_share_subscribe_creates_audit_log(client, seeded_db, auth_headers):
    response = client.post(
        "/share/subscribe",
        headers=auth_headers,
        json={"fund_id": 1, "client_id": 1, "tx_date": "2026-06-30", "amount_usd": "50"},
    )
    assert response.status_code == 200

    audit_response = client.get("/audit", headers=auth_headers)
    assert audit_response.status_code == 200
    audit_rows = audit_response.json()
    assert any(row["action"] == "share.subscribe" and row["actor_id"] == "ops" for row in audit_rows)


def test_scheduler_manual_trigger_runs_and_records_job(client, seeded_db, auth_headers, monkeypatch):
    from app.services import scheduler as scheduler_service

    def fake_fetch_and_save_rates(db, base, quote, snapshot_date):
        row = ExchangeRate(base_currency=base, quote_currency=quote, rate=1.23, snapshot_date=snapshot_date)
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    monkeypatch.setattr(scheduler_service, "fetch_and_save_rates", fake_fetch_and_save_rates)
    response = client.post("/scheduler/jobs/fx-weekly/run", headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["job_name"] == "fx-weekly"
    assert payload["fetched"]

    jobs_response = client.get("/scheduler/jobs", headers=auth_headers)
    assert jobs_response.status_code == 200
    assert any(row["job_name"] == "fx-weekly" and row["status"] == "success" for row in jobs_response.json())


def test_redeem_failure_returns_validation_error(client, seeded_db, auth_headers):
    response = client.post(
        "/share/redeem",
        headers=auth_headers,
        json={"fund_id": 1, "client_id": 1, "tx_date": "2026-06-30", "amount_usd": "5000"},
    )
    assert response.status_code == 400
    assert "exceed" in response.json()["detail"]


def test_logout_revokes_token(client, auth_headers):
    response = client.post("/auth/logout", headers=auth_headers)
    assert response.status_code == 204

    me_response = client.get("/auth/me", headers=auth_headers)
    assert me_response.status_code == 401
