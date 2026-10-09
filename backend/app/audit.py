"""Audit logging helper — records security-relevant events."""
from __future__ import annotations

from sqlalchemy.orm import Session

from .models import AuditEvent


def record(
    db: Session,
    action: str,
    *,
    actor_user_id: int | None = None,
    entity_type: str | None = None,
    entity_id: str | int | None = None,
    detail: str | None = None,
) -> None:
    db.add(AuditEvent(
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        detail=detail,
    ))
    db.commit()
