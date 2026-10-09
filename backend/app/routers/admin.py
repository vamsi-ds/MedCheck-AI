"""Administrator endpoints: account management and audit inspection.

Administrators manage accounts and can inspect audit events. They explicitly
do NOT get clinical privileges (no patient records, no finding reviews).
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import audit
from ..database import get_db
from ..models import AuditEvent, User, UserStatus, UserRole
from ..schemas import AdminUserUpdate, AuditEventOut, UserOut
from ..security import require_admin

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/users", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
    user_status: UserStatus | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    query = db.query(User)
    if user_status is not None:
        query = query.filter(User.status == user_status)
    return (
        query.order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )


@router.get("/users/count")
def count_users(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    def c(status: UserStatus) -> int:
        return db.query(func.count(User.id)).filter(User.status == status).scalar() or 0
    return {"total": db.query(func.count(User.id)).scalar() or 0,
            "pending": c(UserStatus.pending),
            "active": c(UserStatus.active),
            "inactive": c(UserStatus.inactive)}


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: AdminUserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Approve/deactivate accounts and assign roles.

    Guards: admins cannot demote or deactivate their own account, and the last
    active admin can never be removed. Role changes to/from admin are audited.
    """
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found.")

    changes: list[str] = []
    if payload.status is not None and payload.status != target.status.value:
        new_status = UserStatus(payload.status)
        if target.id == admin.id and new_status != UserStatus.active:
            raise HTTPException(status_code=409, detail="You cannot deactivate your own account.")
        if (target.role == UserRole.admin and new_status != UserStatus.active):
            active_admins = (
                db.query(func.count(User.id))
                .filter(User.role == UserRole.admin, User.status == UserStatus.active)
                .scalar() or 0
            )
            if active_admins <= 1:
                raise HTTPException(status_code=409, detail="The last active administrator cannot be deactivated.")
        target.status = new_status
        if new_status == UserStatus.active and target.activated_at is None:
            target.activated_at = datetime.now(timezone.utc)
        changes.append(f"status={new_status.value}")

    if payload.role is not None and payload.role != target.role.value:
        if target.id == admin.id:
            raise HTTPException(status_code=409, detail="You cannot change your own role.")
        if target.role == UserRole.admin:
            active_admins = (
                db.query(func.count(User.id))
                .filter(User.role == UserRole.admin, User.status == UserStatus.active)
                .scalar() or 0
            )
            if active_admins <= 1:
                raise HTTPException(status_code=409, detail="The last active administrator cannot be demoted.")
        target.role = UserRole(payload.role)
        changes.append(f"role={target.role.value}")

    if not changes:
        return target
    db.commit()
    db.refresh(target)
    audit.record(db, "admin.user_update", actor_user_id=admin.id, entity_type="user",
                 entity_id=target.id, detail="; ".join(changes))
    return target


@router.get("/audit", response_model=list[AuditEventOut])
def list_audit(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
    action: str | None = Query(default=None, max_length=80),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    query = db.query(AuditEvent)
    if action:
        query = query.filter(AuditEvent.action == action)
    events = (
        query.order_by(AuditEvent.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    out: list[AuditEventOut] = []
    for e in events:
        item = AuditEventOut.model_validate(e)
        item.actor_username = e.actor.username if e.actor else None
        out.append(item)
    return out
