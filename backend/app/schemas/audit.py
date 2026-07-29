"""Audit trail schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.audit import AuditAction


class AuditEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    # `actor` is the stored name, not a join: it stays readable after the person
    # who made the change has left and their account has been removed.
    user_id: int | None
    actor: str
    entity_type: str
    entity_id: int
    entity_ref: str | None
    action: AuditAction
    field: str | None
    old_value: str | None
    new_value: str | None
    summary: str
    created_at: datetime
