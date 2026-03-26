from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models import AuditLog
from app.services.auth import Actor


def record_audit(
    db: Session,
    actor: Actor,
    action: str,
    entity_type: str,
    entity_id: Optional[str] = None,
    status: str = "success",
    detail: Optional[dict[str, Any]] = None,
) -> AuditLog:
    row = AuditLog(
        actor_role=actor.role,
        actor_id=actor.operator_id,
        client_scope_id=actor.client_scope_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        status=status,
        detail_json=json.dumps(detail or {}, ensure_ascii=False),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def serialize_audit(row: AuditLog) -> dict[str, Any]:
    return {
        "id": row.id,
        "actor_role": row.actor_role,
        "actor_id": row.actor_id,
        "client_scope_id": row.client_scope_id,
        "action": row.action,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "status": row.status,
        "detail": row.detail,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def list_audit_logs(
    db: Session,
    limit: int = 100,
    action: Optional[str] = None,
    client_scope_id: Optional[int] = None,
) -> list[dict[str, Any]]:
    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action == action)
    if client_scope_id is not None:
        query = query.filter(AuditLog.client_scope_id == client_scope_id)
    rows = query.order_by(AuditLog.id.desc()).limit(limit).all()
    return [serialize_audit(row) for row in rows]
