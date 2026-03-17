from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import Header, HTTPException, Query

from app.core.config import settings

ROLE_ADMIN = "admin"
ROLE_OPS = "ops"
ROLE_CLIENT_READONLY = "client-readonly"
ALLOWED_ROLES = {ROLE_ADMIN, ROLE_OPS, ROLE_CLIENT_READONLY}


@dataclass
class Actor:
    role: str
    operator_id: str
    client_scope_id: Optional[int] = None

    @property
    def is_client(self) -> bool:
        return self.role == ROLE_CLIENT_READONLY


async def get_actor(
    role_header: Optional[str] = Header(default=None, alias=settings.auth_role_header),
    client_id_header: Optional[str] = Header(default=None, alias=settings.auth_client_id_header),
    operator_header: Optional[str] = Header(default=None, alias=settings.auth_operator_header),
    dev_role: Optional[str] = Query(default=None, alias="auth_dev_role"),
    dev_client_scope_id: Optional[int] = Query(default=None, alias="auth_dev_client_id"),
    dev_operator_id: Optional[str] = Query(default=None, alias="auth_dev_operator_id"),
) -> Actor:
    selected_role = (role_header or dev_role or ROLE_ADMIN).strip().lower()
    selected_operator_id = (operator_header or dev_operator_id or selected_role or "unknown").strip()
    selected_client_id = dev_client_scope_id
    if client_id_header is not None:
        try:
            selected_client_id = int(client_id_header)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid x-client-id header") from exc

    if not settings.auth_enabled:
        return Actor(role=ROLE_ADMIN, operator_id=selected_operator_id, client_scope_id=selected_client_id)

    if selected_role not in ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail=f"unsupported role: {selected_role}")

    if selected_role == ROLE_CLIENT_READONLY and selected_client_id is None:
        raise HTTPException(status_code=403, detail="client-readonly requires client scope")

    return Actor(role=selected_role, operator_id=selected_operator_id, client_scope_id=selected_client_id)


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
