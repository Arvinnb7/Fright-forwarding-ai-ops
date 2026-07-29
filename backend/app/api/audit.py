"""Audit trail — who changed what.

Readable by any member of the organization, not just administrators: the point
is that a coordinator can see who moved a quote to Won before asking about it,
and internal transparency about one's own company's records is the behaviour a
team expects. Cross-organization access is impossible here by construction —
`AuditEvent` is tenant-scoped like every other record.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.audit import AuditEvent
from app.models.user import User
from app.schemas.audit import AuditEventOut

router = APIRouter()


@router.get("", response_model=list[AuditEventOut])
def list_events(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    entity_type: str | None = None,
    entity_id: int | None = None,
    user_id: int | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[AuditEvent]:
    stmt = select(AuditEvent).order_by(AuditEvent.id.desc())
    if entity_type:
        stmt = stmt.where(AuditEvent.entity_type == entity_type)
    if entity_id is not None:
        stmt = stmt.where(AuditEvent.entity_id == entity_id)
    if user_id is not None:
        stmt = stmt.where(AuditEvent.user_id == user_id)
    return list(db.execute(stmt.limit(limit).offset(offset)).scalars().all())
