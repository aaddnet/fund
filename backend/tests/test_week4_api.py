"""Tests for authentication, session management, and role-based access control."""
from datetime import datetime, timedelta, timezone

from app.models import AuthSession, AuthUser, ExchangeRate


def test_login_returns_bearer_token_and_me_profile(client):
    response = client.post("/auth/login", data={"username": "admin", "password": "Admin12345"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["refresh_token"]
    token = payload["access_token"]

    me_response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_response.status_code == 200
    assert me_response.json()["actor"]["role"] == "admin"
    assert "accounts.write" in me_response.json()["actor"]["permissions"]


def test_login_sets_http_only_auth_cookies(client):
    response = client.post("/auth/login", data={"username": "admin", "password": "Admin12345"})
    assert response.status_code == 200
    cookie_names = {cookie.name for cookie in response.cookies.jar}
    assert "invest_access_token" in cookie_names
    assert "invest_refresh_token" in cookie_names
    assert "invest_csrf_token" in cookie_names
    assert response.json()["csrf_token"]


def test_refresh_rotates_access_token(client, seeded_db):
    login_response = client.post("/auth/login", data={"username": "admin", "password": "Admin12345"})
    payload = login_response.json()
    refresh_response = client.post(
        "/auth/refresh",
        data={"refresh_token": payload["refresh_token"]},
        headers={"x-csrf-token": client.cookies.get("invest_csrf_token")},
    )
    assert refresh_response.status_code == 200
    refreshed = refresh_response.json()
    assert refreshed["access_token"] != payload["access_token"]
    assert refreshed["refresh_token"] != payload["refresh_token"]

    db = seeded_db
    session = db.query(AuthSession).order_by(AuthSession.id.desc()).first()
    assert session.refresh_parent_hash is not None
    assert session.refresh_family_id is not None


def test_refresh_accepts_cookie_when_form_token_missing(client):
    login_response = client.post("/auth/login", data={"username": "admin", "password": "Admin12345"})
    assert login_response.status_code == 200
    csrf_token = client.cookies.get("invest_csrf_token")
    refresh_response = client.post("/auth/refresh", headers={"x-csrf-token": csrf_token})
    assert refresh_response.status_code == 200
    assert refresh_response.json()["access_token"] != login_response.json()["access_token"]


def test_cookie_auth_requires_csrf_header_for_refresh(client):
    login_response = client.post("/auth/login", data={"username": "admin", "password": "Admin12345"})
    assert login_response.status_code == 200
    refresh_response = client.post("/auth/refresh")
    assert refresh_response.status_code == 403
    assert "csrf" in refresh_response.json()["detail"]


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


def test_logout_revokes_token(client, auth_headers):
    response = client.post("/auth/logout", headers=auth_headers)
    assert response.status_code == 204

    me_response = client.get("/auth/me", headers=auth_headers)
    assert me_response.status_code == 401


def test_lockout_after_repeated_failed_logins(client, seeded_db):
    for _ in range(5):
        response = client.post("/auth/login", data={"username": "admin", "password": "WrongPass123"})
        assert response.status_code == 401

    locked_response = client.post("/auth/login", data={"username": "admin", "password": "Admin12345"})
    assert locked_response.status_code == 423


def test_readonly_can_read_but_cannot_write(client, seeded_db):
    login_response = client.post("/auth/login", data={"username": "readonly", "password": "Readonly1234"})
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    read_response = client.get("/nav", headers=headers)
    assert read_response.status_code == 200

    write_response = client.post("/nav/calc", headers=headers, json={"nav_date": "2026-06-30"})
    assert write_response.status_code == 403
    assert "missing permissions" in write_response.json()["detail"]


def test_readonly_permissions_guard_core_endpoints(client, seeded_db):
    login_response = client.post("/auth/login", data={"username": "readonly", "password": "Readonly1234"})
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    assert client.get("/account", headers=headers).status_code == 200
    assert client.get("/reports/overview", headers=headers, params={"period_value": "2026-Q2"}).status_code == 200
    assert client.get("/import", headers=headers).status_code == 200
    assert client.get("/audit", headers=headers).status_code == 403
    assert client.post("/scheduler/jobs/fx-weekly/run", headers=headers).status_code == 403


def test_new_login_revokes_previous_refresh_token(client, seeded_db):
    first_login = client.post("/auth/login", data={"username": "admin", "password": "Admin12345"})
    second_login = client.post("/auth/login", data={"username": "admin", "password": "Admin12345"})
    response = client.post(
        "/auth/refresh",
        data={"refresh_token": first_login.json()["refresh_token"]},
        headers={"x-csrf-token": client.cookies.get("invest_csrf_token")},
    )
    assert second_login.status_code == 200
    assert response.status_code == 401


def test_password_change_timestamp_invalidates_existing_session(client, seeded_db):
    login_response = client.post("/auth/login", data={"username": "admin", "password": "Admin12345"})
    token = login_response.json()["access_token"]

    db = seeded_db
    user = db.query(AuthUser).filter(AuthUser.username == "admin").first()
    user.password_changed_at = datetime.now(timezone.utc) + timedelta(minutes=1)
    db.commit()

    me_response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_response.status_code == 401


def test_idle_session_is_rejected_for_refresh(client, seeded_db):
    login_response = client.post("/auth/login", data={"username": "admin", "password": "Admin12345"})
    refresh_token = login_response.json()["refresh_token"]

    db = seeded_db
    session = db.query(AuthSession).order_by(AuthSession.id.desc()).first()
    session.last_seen_at = datetime.now(timezone.utc) - timedelta(hours=3)
    session.refreshed_at = datetime.now(timezone.utc) - timedelta(hours=3)
    db.commit()

    refresh_response = client.post(
        "/auth/refresh",
        data={"refresh_token": refresh_token},
        headers={"x-csrf-token": client.cookies.get("invest_csrf_token")},
    )
    assert refresh_response.status_code == 401


def test_refresh_token_reuse_revokes_refresh_family(client, seeded_db):
    login_response = client.post("/auth/login", data={"username": "admin", "password": "Admin12345"})
    first_refresh_token = login_response.json()["refresh_token"]

    refresh_response = client.post(
        "/auth/refresh",
        data={"refresh_token": first_refresh_token},
        headers={"x-csrf-token": client.cookies.get("invest_csrf_token")},
    )
    assert refresh_response.status_code == 200
    second_refresh_token = refresh_response.json()["refresh_token"]

    reuse_response = client.post(
        "/auth/refresh",
        data={"refresh_token": first_refresh_token},
        headers={"x-csrf-token": client.cookies.get("invest_csrf_token")},
    )
    assert reuse_response.status_code == 401
    assert "reuse" in reuse_response.json()["detail"]

    family_refresh_response = client.post(
        "/auth/refresh",
        data={"refresh_token": second_refresh_token},
        headers={"x-csrf-token": client.cookies.get("invest_csrf_token")},
    )
    assert family_refresh_response.status_code == 401

    db = seeded_db
    sessions = db.query(AuthSession).all()
    assert sessions
    assert all(session.revoked_at is not None for session in sessions)


def test_admin_can_create_and_list_auth_users(client, seeded_db, auth_headers):
    create_response = client.post(
        "/auth/users",
        headers=auth_headers,
        json={"username": "newuser", "password": "NewUser12345", "role": "readonly", "display_name": "New User"},
    )
    assert create_response.status_code in (200, 201)
    assert create_response.json()["username"] == "newuser"

    list_response = client.get("/auth/users", headers=auth_headers)
    assert list_response.status_code == 200
    assert any(item["username"] == "newuser" and item["role"] == "readonly" for item in list_response.json())


def test_user_can_change_own_password(client, seeded_db):
    # Create a test user first
    admin_login = client.post("/auth/login", data={"username": "admin", "password": "Admin12345"})
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}
    client.post("/auth/users", headers=admin_headers, json={
        "username": "pwtest", "password": "PwTest12345", "role": "readonly",
    })

    # Login as test user and change password
    login_response = client.post("/auth/login", data={"username": "pwtest", "password": "PwTest12345"})
    headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

    change_response = client.patch(
        "/auth/me/password",
        headers=headers,
        json={"current_password": "PwTest12345", "new_password": "PwTest54321A"},
    )
    assert change_response.status_code == 200

    old_login = client.post("/auth/login", data={"username": "pwtest", "password": "PwTest12345"})
    assert old_login.status_code == 401
    new_login = client.post("/auth/login", data={"username": "pwtest", "password": "PwTest54321A"})
    assert new_login.status_code == 200


def test_admin_can_reset_password_and_disable_user(client, seeded_db, auth_headers):
    # Create test user
    client.post("/auth/users", headers=auth_headers, json={
        "username": "disabletest", "password": "Disable12345", "role": "readonly",
    })

    db = seeded_db
    user = db.query(AuthUser).filter(AuthUser.username == "disabletest").first()
    user_id = user.id

    reset_response = client.post(f"/auth/users/{user_id}/reset-password", headers=auth_headers, json={"new_password": "Reset12345A"})
    assert reset_response.status_code == 200

    disabled_response = client.patch(f"/auth/users/{user_id}", headers=auth_headers, json={"is_active": False})
    assert disabled_response.status_code == 200
    assert disabled_response.json()["is_active"] is False

    login_after_disable = client.post("/auth/login", data={"username": "disabletest", "password": "Reset12345A"})
    assert login_after_disable.status_code == 401
