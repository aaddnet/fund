from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Cookie, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import get_db
from app.models import AuthSession, AuthUser

ROLE_ADMIN = "admin"
ROLE_OPS = "ops"
ROLE_CLIENT_READONLY = "client-readonly"
ROLE_OPS_READONLY = "ops-readonly"
ROLE_SUPPORT = "support"
ALLOWED_ROLES = {ROLE_ADMIN, ROLE_OPS, ROLE_CLIENT_READONLY, ROLE_OPS_READONLY, ROLE_SUPPORT}
PBKDF2_ITERATIONS = 390000
PASSWORD_MIN_LENGTH = 10
PASSWORD_COMPLEXITY_PATTERN = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).+$")

PERMISSIONS_BY_ROLE = {
    ROLE_ADMIN: {
        "auth.manage",
        "audit.read",
        "accounts.read",
        "accounts.write",
        "clients.read",
        "clients.write",
        "customer.read",
        "dashboard.read",
        "fees.read",
        "fees.write",
        "import.read",
        "import.write",
        "nav.read",
        "nav.write",
        "price.read",
        "price.write",
        "rates.read",
        "rates.write",
        "reports.read",
        "scheduler.run",
        "scheduler.read",
        "shares.read",
        "shares.write",
    },
    ROLE_OPS: {
        "audit.read",
        "accounts.read",
        "clients.read",
        "customer.read",
        "dashboard.read",
        "fees.read",
        "fees.write",
        "import.read",
        "import.write",
        "nav.read",
        "nav.write",
        "price.read",
        "price.write",
        "rates.read",
        "rates.write",
        "reports.read",
        "scheduler.run",
        "scheduler.read",
        "shares.read",
        "shares.write",
    },
    ROLE_OPS_READONLY: {
        "accounts.read",
        "clients.read",
        "customer.read",
        "dashboard.read",
        "fees.read",
        "import.read",
        "nav.read",
        "price.read",
        "rates.read",
        "reports.read",
        "scheduler.read",
        "shares.read",
    },
    ROLE_SUPPORT: {
        "accounts.read",
        "clients.read",
        "customer.read",
        "dashboard.read",
        "nav.read",
        "reports.read",
        "shares.read",
    },
    ROLE_CLIENT_READONLY: {
        "customer.read",
        "nav.read",
        "reports.read",
        "shares.read",
    },
}


@dataclass
class Actor:
    role: str
    operator_id: str
    client_scope_id: Optional[int] = None
    auth_mode: str = "dev"
    user_id: Optional[int] = None
    session_id: Optional[int] = None
    username: Optional[str] = None
    permissions: tuple[str, ...] = ()
    auth_via_cookie: bool = False

    @property
    def is_client(self) -> bool:
        return self.role == ROLE_CLIENT_READONLY

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions


@dataclass
class AuthenticatedSession:
    user: AuthUser
    session: AuthSession
    access_token: str
    refresh_token: str
    csrf_token: str
    access_expires_at: datetime
    refresh_expires_at: datetime


def permissions_for_role(role: str) -> tuple[str, ...]:
    return tuple(sorted(PERMISSIONS_BY_ROLE.get(role, set())))


def validate_password_policy(password: str) -> None:
    if len(password) < PASSWORD_MIN_LENGTH:
        raise HTTPException(status_code=400, detail=f"password must be at least {PASSWORD_MIN_LENGTH} characters")
    if not PASSWORD_COMPLEXITY_PATTERN.match(password):
        raise HTTPException(status_code=400, detail="password must include uppercase, lowercase, and number")


def hash_password(password: str) -> str:
    validate_password_policy(password)
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt_b64, digest_b64 = encoded_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_text)
        salt = base64.b64decode(salt_b64.encode())
        expected = base64.b64decode(digest_b64.encode())
    except (ValueError, TypeError):
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(candidate, expected)


def _hash_token(token: str, *, kind: str) -> str:
    return hashlib.sha256(f"{settings.auth_secret_key}:{kind}:{token}".encode("utf-8")).hexdigest()


def _hash_session_token(token: str) -> str:
    return _hash_token(token, kind="access")


def _hash_refresh_token(token: str) -> str:
    return _hash_token(token, kind="refresh")


def _coerce_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _mark_failed_login(user: Optional[AuthUser], db: Session) -> None:
    if user is None:
        return
    user.failed_login_attempts = int(user.failed_login_attempts or 0) + 1
    user.last_failed_login_at = _utcnow()
    if user.failed_login_attempts >= settings.auth_lockout_threshold:
        user.locked_until = _utcnow() + timedelta(minutes=settings.auth_lockout_minutes)
    db.commit()


def _clear_failed_login(user: AuthUser) -> None:
    user.failed_login_attempts = 0
    user.last_failed_login_at = None
    user.locked_until = None


def _ensure_not_locked(user: AuthUser) -> None:
    locked_until = _coerce_utc(user.locked_until)
    if locked_until and locked_until > _utcnow():
        raise HTTPException(status_code=423, detail=f"account locked until {locked_until.isoformat()}")


def _mint_session_tokens() -> tuple[str, str, str]:
    return os.urandom(32).hex(), os.urandom(32).hex(), os.urandom(24).hex()


def _mint_refresh_family_id() -> str:
    return os.urandom(16).hex()


def _session_reference_time(session: AuthSession) -> datetime:
    return _coerce_utc(session.last_seen_at) or _coerce_utc(session.refreshed_at) or _coerce_utc(session.created_at) or _utcnow()


def _session_expired_by_idle_timeout(session: AuthSession, now: datetime) -> bool:
    idle_minutes = max(int(settings.auth_session_idle_minutes or 0), 0)
    if idle_minutes <= 0:
        return False
    return _session_reference_time(session) + timedelta(minutes=idle_minutes) <= now


def _session_invalid_for_user(session: AuthSession, user: AuthUser, now: datetime) -> bool:
    password_changed_at = _coerce_utc(user.password_changed_at)
    session_anchor = _coerce_utc(session.refreshed_at) or _coerce_utc(session.created_at)
    if password_changed_at and session_anchor and password_changed_at > session_anchor:
        return True
    return _session_expired_by_idle_timeout(session, now)


def _revoke_user_sessions(db: Session, user_id: int, *, except_session_id: Optional[int] = None) -> None:
    query = db.query(AuthSession).filter(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
    if except_session_id is not None:
        query = query.filter(AuthSession.id != except_session_id)
    now = _utcnow()
    for session in query.all():
        session.revoked_at = now


def _revoke_refresh_family(db: Session, refresh_family_id: Optional[str], *, reason: str = "refresh_reuse_detected") -> None:
    if not refresh_family_id:
        return
    now = _utcnow()
    rows = db.query(AuthSession).filter(AuthSession.refresh_family_id == refresh_family_id).all()
    for session in rows:
        session.revoked_at = session.revoked_at or now
        session.refresh_reused_at = session.refresh_reused_at or now


def _validate_client_scope(db: Session, role: str, client_scope_id: Optional[int]) -> Optional[int]:
    # v1: client scope is not used (no client/LP concept)
    return None


def list_auth_users(db: Session) -> list[AuthUser]:
    return db.query(AuthUser).order_by(AuthUser.id.asc()).all()


def create_auth_user(
    db: Session,
    *,
    username: str,
    password: str,
    role: str,
    client_scope_id: Optional[int],
    display_name: Optional[str],
    is_active: bool,
) -> AuthUser:
    normalized_username = username.strip()
    normalized_role = role.strip().lower()
    if not normalized_username:
        raise HTTPException(status_code=400, detail="username is required")
    if normalized_role not in ALLOWED_ROLES:
        raise HTTPException(status_code=400, detail="unsupported role")
    if db.query(AuthUser.id).filter(AuthUser.username == normalized_username).first():
        raise HTTPException(status_code=409, detail="username already exists")

    user = AuthUser(
        username=normalized_username,
        password_hash=hash_password(password),
        role=normalized_role,
        client_scope_id=_validate_client_scope(db, normalized_role, client_scope_id),
        display_name=display_name.strip() if display_name else normalized_username,
        is_active=bool(is_active),
        password_changed_at=_utcnow(),
        failed_login_attempts=0,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_auth_user(
    db: Session,
    *,
    user_id: int,
    role: Optional[str] = None,
    client_scope_id: Optional[int] = None,
    display_name: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> AuthUser:
    user = db.query(AuthUser).filter(AuthUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="user not found")

    next_role = user.role if role is None else role.strip().lower()
    if next_role not in ALLOWED_ROLES:
        raise HTTPException(status_code=400, detail="unsupported role")

    user.role = next_role
    if display_name is not None:
        user.display_name = display_name.strip() or user.username
    if is_active is not None:
        user.is_active = bool(is_active)
    if client_scope_id is not None or next_role == ROLE_CLIENT_READONLY:
        user.client_scope_id = _validate_client_scope(db, next_role, client_scope_id)
    elif next_role != ROLE_CLIENT_READONLY:
        user.client_scope_id = None

    if is_active is False:
        _revoke_user_sessions(db, user.id)
    db.commit()
    db.refresh(user)
    return user


def change_password(db: Session, *, actor: Actor, current_password: str, new_password: str) -> AuthUser:
    if actor.user_id is None:
        raise HTTPException(status_code=400, detail="session user is required")
    user = db.query(AuthUser).filter(AuthUser.id == actor.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    if not verify_password(current_password, user.password_hash):
        raise HTTPException(status_code=401, detail="current password is invalid")

    user.password_hash = hash_password(new_password)
    user.password_changed_at = _utcnow()
    _clear_failed_login(user)
    _revoke_user_sessions(db, user.id, except_session_id=actor.session_id)
    db.commit()
    db.refresh(user)
    return user


def admin_reset_password(db: Session, *, user_id: int, new_password: str) -> AuthUser:
    user = db.query(AuthUser).filter(AuthUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    user.password_hash = hash_password(new_password)
    user.password_changed_at = _utcnow()
    _clear_failed_login(user)
    _revoke_user_sessions(db, user.id)
    db.commit()
    db.refresh(user)
    return user


def bootstrap_auth_users(db: Session) -> None:
    configured_users = settings.auth_bootstrap_users or []
    for item in configured_users:
        username = str(item.get("username", "")).strip()
        password = str(item.get("password", "")).strip()
        role = str(item.get("role", "")).strip().lower()
        if not username or not password or role not in ALLOWED_ROLES:
            continue

        existing = db.query(AuthUser).filter(AuthUser.username == username).first()
        if existing:
            if existing.password_changed_at is None:
                existing.password_changed_at = existing.created_at or _utcnow()
            db.commit()
            continue
        db.add(
            AuthUser(
                username=username,
                password_hash=hash_password(password),
                role=role,
                display_name=item.get("display_name") or username,
                is_active=True,
                password_changed_at=_utcnow(),
                failed_login_attempts=0,
            )
        )
    db.commit()


def _issue_session(db: Session, user: AuthUser) -> AuthenticatedSession:
    raw_access_token, raw_refresh_token, csrf_token = _mint_session_tokens()
    now = _utcnow()
    access_expires_at = now + timedelta(minutes=settings.auth_access_token_ttl_minutes)
    refresh_expires_at = now + timedelta(days=settings.auth_refresh_token_ttl_days)
    session = AuthSession(
        user_id=user.id,
        session_token_hash=_hash_session_token(raw_access_token),
        refresh_token_hash=_hash_refresh_token(raw_refresh_token),
        refresh_family_id=_mint_refresh_family_id(),
        expires_at=access_expires_at,
        refresh_expires_at=refresh_expires_at,
        last_seen_at=now,
        refreshed_at=now,
    )
    user.last_login_at = now
    db.add(session)
    db.commit()
    db.refresh(user)
    db.refresh(session)
    return AuthenticatedSession(
        user=user,
        session=session,
        access_token=raw_access_token,
        refresh_token=raw_refresh_token,
        csrf_token=csrf_token,
        access_expires_at=access_expires_at,
        refresh_expires_at=refresh_expires_at,
    )


def login_with_password(db: Session, username: str, password: str) -> AuthenticatedSession:
    user = db.query(AuthUser).filter(AuthUser.username == username.strip()).first()
    if not user or not user.is_active:
        _mark_failed_login(user, db)
        raise HTTPException(status_code=401, detail="invalid username or password")

    _ensure_not_locked(user)
    if not verify_password(password, user.password_hash):
        _mark_failed_login(user, db)
        raise HTTPException(status_code=401, detail="invalid username or password")

    _clear_failed_login(user)

    if user.role == ROLE_CLIENT_READONLY and user.client_scope_id is None:
        for item in settings.auth_bootstrap_users or []:
            if item.get("username") == user.username and item.get("client_scope_id") is not None:
                client_exists = db.query(Client.id).filter(Client.id == item["client_scope_id"]).first()
                if client_exists:
                    user.client_scope_id = item["client_scope_id"]
                    break

    _revoke_user_sessions(db, user.id)
    db.commit()
    db.refresh(user)
    return _issue_session(db, user)


def revoke_session(db: Session, session_id: int) -> None:
    session = db.query(AuthSession).filter(AuthSession.id == session_id).first()
    if not session:
        return
    session.revoked_at = _utcnow()
    db.commit()


def _build_actor(user: AuthUser, session: AuthSession, *, auth_via_cookie: bool = False) -> Actor:
    return Actor(
        role=user.role,
        operator_id=user.username,
        client_scope_id=user.client_scope_id,
        auth_mode="session",
        user_id=user.id,
        session_id=session.id,
        username=user.username,
        permissions=permissions_for_role(user.role),
        auth_via_cookie=auth_via_cookie,
    )


def authenticate_bearer_token(db: Session, authorization: Optional[str], *, auth_via_cookie: bool = False) -> Optional[Actor]:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="invalid authorization header")

    hashed = _hash_session_token(token.strip())
    row = (
        db.query(AuthSession, AuthUser)
        .join(AuthUser, AuthUser.id == AuthSession.user_id)
        .filter(AuthSession.session_token_hash == hashed)
        .first()
    )
    if not row:
        raise HTTPException(status_code=401, detail="invalid session token")

    session, user = row
    now = _utcnow()
    expires_at = _coerce_utc(session.expires_at)
    if session.revoked_at is not None or (expires_at and expires_at <= now) or not user.is_active or _session_invalid_for_user(session, user, now):
        session.revoked_at = session.revoked_at or now
        db.commit()
        raise HTTPException(status_code=401, detail="session expired or revoked")

    session.last_seen_at = now
    db.commit()
    return _build_actor(user, session, auth_via_cookie=auth_via_cookie)


def refresh_access_token(db: Session, refresh_token: str) -> AuthenticatedSession:
    hashed = _hash_refresh_token(refresh_token.strip())
    row = (
        db.query(AuthSession, AuthUser)
        .join(AuthUser, AuthUser.id == AuthSession.user_id)
        .filter(AuthSession.refresh_token_hash == hashed)
        .first()
    )
    now = _utcnow()
    if not row:
        reused_session = db.query(AuthSession).filter(AuthSession.refresh_parent_hash == hashed).first()
        if reused_session:
            _revoke_refresh_family(db, reused_session.refresh_family_id)
            db.commit()
            raise HTTPException(status_code=401, detail="refresh token reuse detected")
        raise HTTPException(status_code=401, detail="invalid refresh token")

    session, user = row
    refresh_expires_at = _coerce_utc(session.refresh_expires_at)
    if (
        session.revoked_at is not None
        or (refresh_expires_at and refresh_expires_at <= now)
        or not user.is_active
        or _session_invalid_for_user(session, user, now)
    ):
        session.revoked_at = session.revoked_at or now
        db.commit()
        raise HTTPException(status_code=401, detail="refresh token expired or revoked")
    _ensure_not_locked(user)

    old_refresh_token_hash = session.refresh_token_hash
    raw_access_token, raw_refresh_token, csrf_token = _mint_session_tokens()
    session.session_token_hash = _hash_session_token(raw_access_token)
    session.refresh_token_hash = _hash_refresh_token(raw_refresh_token)
    session.refresh_parent_hash = old_refresh_token_hash
    session.refresh_family_id = session.refresh_family_id or _mint_refresh_family_id()
    session.refresh_reused_at = None
    session.expires_at = now + timedelta(minutes=settings.auth_access_token_ttl_minutes)
    session.refresh_expires_at = now + timedelta(days=settings.auth_refresh_token_ttl_days)
    session.last_seen_at = now
    session.refreshed_at = now
    db.commit()
    db.refresh(user)
    db.refresh(session)
    return AuthenticatedSession(
        user=user,
        session=session,
        access_token=raw_access_token,
        refresh_token=raw_refresh_token,
        csrf_token=csrf_token,
        access_expires_at=_coerce_utc(session.expires_at) or now,
        refresh_expires_at=_coerce_utc(session.refresh_expires_at) or now,
    )


async def get_actor(
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    access_cookie: Optional[str] = Cookie(default=None, alias=settings.auth_access_cookie_name),
    role_header: Optional[str] = Header(default=None, alias=settings.auth_role_header),
    client_id_header: Optional[str] = Header(default=None, alias=settings.auth_client_id_header),
    operator_header: Optional[str] = Header(default=None, alias=settings.auth_operator_header),
    dev_role: Optional[str] = Query(default=None, alias="auth_dev_role"),
    dev_client_scope_id: Optional[int] = Query(default=None, alias="auth_dev_client_id"),
    dev_operator_id: Optional[str] = Query(default=None, alias="auth_dev_operator_id"),
) -> Actor:
    if not settings.auth_enabled:
        return Actor(role=ROLE_ADMIN, operator_id="auth-disabled", auth_mode="disabled", permissions=permissions_for_role(ROLE_ADMIN))

    if settings.auth_mode in {"token", "session", "hybrid"}:
        if authorization:
            actor = authenticate_bearer_token(db, authorization, auth_via_cookie=False)
        else:
            actor = authenticate_bearer_token(db, f"Bearer {access_cookie}" if settings.auth_cookie_enabled and access_cookie else None, auth_via_cookie=True)
        if actor is not None:
            return actor
        if settings.auth_mode in {"token", "session"} and not settings.auth_allow_dev_fallback:
            raise HTTPException(status_code=401, detail="bearer token required")

    if settings.auth_mode in {"dev", "hybrid"} or settings.auth_allow_dev_fallback:
        selected_role = (role_header or dev_role or ROLE_ADMIN).strip().lower()
        selected_operator_id = (operator_header or dev_operator_id or selected_role or "unknown").strip()
        selected_client_id = dev_client_scope_id
        if client_id_header is not None:
            try:
                selected_client_id = int(client_id_header)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="invalid x-client-id header") from exc

        if selected_role not in ALLOWED_ROLES:
            raise HTTPException(status_code=403, detail=f"unsupported role: {selected_role}")
        if selected_role == ROLE_CLIENT_READONLY and selected_client_id is None:
            raise HTTPException(status_code=403, detail="client-readonly requires client scope")
        return Actor(
            role=selected_role,
            operator_id=selected_operator_id,
            client_scope_id=selected_client_id,
            auth_mode="dev",
            permissions=permissions_for_role(selected_role),
        )

    raise HTTPException(status_code=401, detail="authentication required")


def require_roles(actor: Actor, *roles: str) -> Actor:
    if actor.role not in roles:
        raise HTTPException(status_code=403, detail="role is not allowed for this operation")
    return actor


def require_permissions(actor: Actor, *permissions: str) -> Actor:
    missing = [permission for permission in permissions if permission not in actor.permissions]
    if missing:
        raise HTTPException(status_code=403, detail=f"missing permissions: {', '.join(missing)}")
    return actor


def require_client_scope(actor: Actor, client_id: Optional[int]) -> Actor:
    if actor.role != ROLE_CLIENT_READONLY:
        return actor
    if client_id is None or actor.client_scope_id != client_id:
        raise HTTPException(status_code=403, detail="client scope mismatch")
    return actor


def change_password(db: Session, user_id: int, old_password: str, new_password: str) -> None:
    user = db.query(AuthUser).filter(AuthUser.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=404, detail="user not found")
    if not verify_password(old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="old password is incorrect")
    validate_password_policy(new_password)
    user.password_hash = hash_password(new_password)
    user.password_changed_at = _utcnow()
    # Revoke all active sessions so existing tokens are invalidated after a password change.
    db.query(AuthSession).filter(
        AuthSession.user_id == user_id,
        AuthSession.revoked_at.is_(None),
    ).update({"revoked_at": _utcnow()}, synchronize_session=False)
    db.commit()


def list_users(db: Session) -> list[dict]:
    users = db.query(AuthUser).order_by(AuthUser.id.asc()).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "role": u.role,
            "display_name": u.display_name,
            "is_active": u.is_active,
            "client_scope_id": u.client_scope_id,
            "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
            "password_changed_at": u.password_changed_at.isoformat() if u.password_changed_at else None,
            "failed_login_attempts": u.failed_login_attempts,
            "locked_until": u.locked_until.isoformat() if u.locked_until else None,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ]


def unlock_user(db: Session, user_id: int) -> dict:
    user = db.query(AuthUser).filter(AuthUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    _clear_failed_login(user)
    db.commit()
    return {"id": user.id, "username": user.username, "locked_until": None, "failed_login_attempts": 0}


def apply_client_scope_filters(actor: Actor, fund_id: Optional[int], client_id: Optional[int]) -> tuple[Optional[int], Optional[int]]:
    if actor.role != ROLE_CLIENT_READONLY:
        return fund_id, client_id
    if actor.client_scope_id is None:
        raise HTTPException(status_code=403, detail="client scope is required")
    return fund_id, actor.client_scope_id
