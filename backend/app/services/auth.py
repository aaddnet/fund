from __future__ import annotations

import base64
import hashlib
import hmac
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import get_db
from app.models import AuthSession, AuthUser, Client

ROLE_ADMIN = "admin"
ROLE_OPS = "ops"
ROLE_CLIENT_READONLY = "client-readonly"
ALLOWED_ROLES = {ROLE_ADMIN, ROLE_OPS, ROLE_CLIENT_READONLY}
PBKDF2_ITERATIONS = 390000


@dataclass
class Actor:
    role: str
    operator_id: str
    client_scope_id: Optional[int] = None
    auth_mode: str = "dev"
    user_id: Optional[int] = None
    session_id: Optional[int] = None
    username: Optional[str] = None

    @property
    def is_client(self) -> bool:
        return self.role == ROLE_CLIENT_READONLY


@dataclass
class AuthenticatedSession:
    user: AuthUser
    session: AuthSession
    token: str
    expires_at: datetime


def hash_password(password: str) -> str:
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


def _hash_session_token(token: str) -> str:
    return hashlib.sha256(f"{settings.auth_secret_key}:{token}".encode("utf-8")).hexdigest()


def bootstrap_auth_users(db: Session) -> None:
    configured_users = settings.auth_bootstrap_users or []
    for item in configured_users:
        username = str(item.get("username", "")).strip()
        password = str(item.get("password", "")).strip()
        role = str(item.get("role", "")).strip().lower()
        requested_client_scope_id = item.get("client_scope_id")
        if not username or not password or role not in ALLOWED_ROLES:
            continue
        client_scope_id = requested_client_scope_id
        if requested_client_scope_id is not None:
            client_exists = db.query(Client.id).filter(Client.id == requested_client_scope_id).first()
            client_scope_id = requested_client_scope_id if client_exists else None

        existing = db.query(AuthUser).filter(AuthUser.username == username).first()
        if existing:
            if existing.client_scope_id is None and client_scope_id is not None:
                existing.client_scope_id = client_scope_id
                db.commit()
            continue
        # 这里保留最小 bootstrap 机制，方便本地和 Docker 联调快速进入系统。
        db.add(
            AuthUser(
                username=username,
                password_hash=hash_password(password),
                role=role,
                client_scope_id=client_scope_id,
                display_name=item.get("display_name") or username,
                is_active=True,
            )
        )
    db.commit()


def login_with_password(db: Session, username: str, password: str) -> AuthenticatedSession:
    user = db.query(AuthUser).filter(AuthUser.username == username.strip()).first()
    if not user or not user.is_active or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid username or password")

    if user.role == ROLE_CLIENT_READONLY and user.client_scope_id is None:
        for item in settings.auth_bootstrap_users or []:
            if item.get("username") == user.username and item.get("client_scope_id") is not None:
                client_exists = db.query(Client.id).filter(Client.id == item["client_scope_id"]).first()
                if client_exists:
                    user.client_scope_id = item["client_scope_id"]
                    db.commit()
                    db.refresh(user)
                break

    raw_token = os.urandom(32).hex()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.auth_token_ttl_hours)
    session = AuthSession(
        user_id=user.id,
        session_token_hash=_hash_session_token(raw_token),
        expires_at=expires_at,
        last_seen_at=datetime.now(timezone.utc),
    )
    user.last_login_at = datetime.now(timezone.utc)
    db.add(session)
    db.commit()
    db.refresh(user)
    db.refresh(session)
    return AuthenticatedSession(user=user, session=session, token=raw_token, expires_at=expires_at)


def revoke_session(db: Session, session_id: int) -> None:
    session = db.query(AuthSession).filter(AuthSession.id == session_id).first()
    if not session:
        return
    session.revoked_at = datetime.now(timezone.utc)
    db.commit()


def authenticate_bearer_token(db: Session, authorization: Optional[str]) -> Optional[Actor]:
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
    now = datetime.now(timezone.utc)
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if session.revoked_at is not None or expires_at <= now or not user.is_active:
        raise HTTPException(status_code=401, detail="session expired or revoked")

    session.last_seen_at = now
    db.commit()
    return Actor(
        role=user.role,
        operator_id=user.username,
        client_scope_id=user.client_scope_id,
        auth_mode="session",
        user_id=user.id,
        session_id=session.id,
        username=user.username,
    )


async def get_actor(
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    role_header: Optional[str] = Header(default=None, alias=settings.auth_role_header),
    client_id_header: Optional[str] = Header(default=None, alias=settings.auth_client_id_header),
    operator_header: Optional[str] = Header(default=None, alias=settings.auth_operator_header),
    dev_role: Optional[str] = Query(default=None, alias="auth_dev_role"),
    dev_client_scope_id: Optional[int] = Query(default=None, alias="auth_dev_client_id"),
    dev_operator_id: Optional[str] = Query(default=None, alias="auth_dev_operator_id"),
) -> Actor:
    if not settings.auth_enabled:
        return Actor(role=ROLE_ADMIN, operator_id="auth-disabled", auth_mode="disabled")

    if settings.auth_mode in {"token", "session", "hybrid"}:
        actor = authenticate_bearer_token(db, authorization)
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
        return Actor(role=selected_role, operator_id=selected_operator_id, client_scope_id=selected_client_id, auth_mode="dev")

    raise HTTPException(status_code=401, detail="authentication required")


def require_roles(actor: Actor, *roles: str) -> Actor:
    if actor.role not in roles:
        raise HTTPException(status_code=403, detail="role is not allowed for this operation")
    return actor


def require_client_scope(actor: Actor, client_id: Optional[int]) -> Actor:
    if actor.role != ROLE_CLIENT_READONLY:
        return actor
    if client_id is None or actor.client_scope_id != client_id:
        raise HTTPException(status_code=403, detail="client scope mismatch")
    return actor


def apply_client_scope_filters(actor: Actor, fund_id: Optional[int], client_id: Optional[int]) -> tuple[Optional[int], Optional[int]]:
    if actor.role != ROLE_CLIENT_READONLY:
        return fund_id, client_id
    if actor.client_scope_id is None:
        raise HTTPException(status_code=403, detail="client scope is required")
    return fund_id, actor.client_scope_id
