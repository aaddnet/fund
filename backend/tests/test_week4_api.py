from datetime import date, datetime, timedelta, timezone

from app.models import AuthSession, AuthUser, ExchangeRate


def test_login_returns_bearer_token_and_me_profile(client):
    response = client.post("/auth/login", data={"username": "ops", "password": "Ops1234567"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["refresh_token"]
    token = payload["access_token"]

    me_response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_response.status_code == 200
    assert me_response.json()["actor"]["role"] == "ops"
    assert "shares.write" in me_response.json()["actor"]["permissions"]


def test_login_sets_http_only_auth_cookies(client):
    response = client.post("/auth/login", data={"username": "ops", "password": "Ops1234567"})
    assert response.status_code == 200
    cookie_names = {cookie.name for cookie in response.cookies.jar}
    assert "invest_access_token" in cookie_names
    assert "invest_refresh_token" in cookie_names


def test_refresh_rotates_access_token(client):
    login_response = client.post("/auth/login", data={"username": "ops", "password": "Ops1234567"})
    payload = login_response.json()
    refresh_response = client.post("/auth/refresh", data={"refresh_token": payload["refresh_token"]})
    assert refresh_response.status_code == 200
    refreshed = refresh_response.json()
    assert refreshed["access_token"] != payload["access_token"]
    assert refreshed["refresh_token"] != payload["refresh_token"]


def test_refresh_accepts_cookie_when_form_token_missing(client):
    login_response = client.post("/auth/login", data={"username": "ops", "password": "Ops1234567"})
    assert login_response.status_code == 200
    refresh_response = client.post("/auth/refresh")
    assert refresh_response.status_code == 200
    assert refresh_response.json()["access_token"] != login_response.json()["access_token"]


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


def test_lockout_after_repeated_failed_logins(client, seeded_db):
    for _ in range(5):
        response = client.post("/auth/login", data={"username": "ops", "password": "WrongPass123"})
        assert response.status_code == 401

    locked_response = client.post("/auth/login", data={"username": "ops", "password": "Ops1234567"})
    assert locked_response.status_code == 423


def test_viewer_can_read_but_cannot_write(client, seeded_db):
    login_response = client.post("/auth/login", data={"username": "viewer", "password": "Viewer12345"})
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    read_response = client.get("/nav", headers=headers)
    assert read_response.status_code == 200

    write_response = client.post("/share/subscribe", headers=headers, json={"fund_id": 1, "client_id": 1, "tx_date": "2026-06-30", "amount_usd": "50"})
    assert write_response.status_code == 403
    assert "missing permissions" in write_response.json()["detail"]


def test_supporting_permissions_guard_core_read_endpoints(client, seeded_db):
    login_response = client.post("/auth/login", data={"username": "viewer", "password": "Viewer12345"})
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    assert client.get("/account", headers=headers).status_code == 200
    assert client.get("/client", headers=headers).status_code == 200
    assert client.get("/reports/overview", headers=headers, params={"period_value": "2026-Q2"}).status_code == 200
    assert client.get("/import", headers=headers).status_code == 200
    assert client.get("/audit", headers=headers).status_code == 403
    assert client.post("/scheduler/jobs/fx-weekly/run", headers=headers).status_code == 403


def test_new_login_revokes_previous_refresh_token(client, seeded_db):
    first_login = client.post("/auth/login", data={"username": "ops", "password": "Ops1234567"})
    second_login = client.post("/auth/login", data={"username": "ops", "password": "Ops1234567"})
    response = client.post("/auth/refresh", data={"refresh_token": first_login.json()["refresh_token"]})
    assert second_login.status_code == 200
    assert response.status_code == 401


def test_password_change_timestamp_invalidates_existing_session(client, seeded_db):
    login_response = client.post("/auth/login", data={"username": "ops", "password": "Ops1234567"})
    token = login_response.json()["access_token"]

    db = seeded_db
    user = db.query(AuthUser).filter(AuthUser.username == "ops").first()
    user.password_changed_at = datetime.now(timezone.utc) + timedelta(minutes=1)
    db.commit()

    me_response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_response.status_code == 401


def test_idle_session_is_rejected_for_refresh(client, seeded_db):
    login_response = client.post("/auth/login", data={"username": "ops", "password": "Ops1234567"})
    refresh_token = login_response.json()["refresh_token"]

    db = seeded_db
    session = db.query(AuthSession).order_by(AuthSession.id.desc()).first()
    session.last_seen_at = datetime.now(timezone.utc) - timedelta(hours=3)
    session.refreshed_at = datetime.now(timezone.utc) - timedelta(hours=3)
    db.commit()

    refresh_response = client.post("/auth/refresh", data={"refresh_token": refresh_token})
    assert refresh_response.status_code == 401
