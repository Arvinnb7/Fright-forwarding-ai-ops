"""Who did what, and when.

Two reasons this exists. The everyday one: when a price went out wrong, the desk
needs to know who approved it and what it was before. The commercial one: a
forwarder handling other people's cargo is asked by their own customers and
auditors to show that pricing decisions are attributable, and "the software
doesn't record that" is not an acceptable answer.

The actor's email is copied onto the row rather than only referenced. A person
who has left the company can be removed from the users table; what they approved
must remain readable.
"""
from __future__ import annotations

from enum import Enum

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.tenancy import TenantMixin
from app.models.base import TimestampMixin, enum_column


class AuditAction(str, Enum):
    CREATED = "Created"
    UPDATED = "Updated"
    DELETED = "Deleted"


class AuditEvent(Base, TenantMixin, TimestampMixin):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Who. `user_id` may be null for work done by the scheduler; `actor` always
    # says something a human can read.
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    actor: Mapped[str] = mapped_column(String(255), nullable=False, default="system")

    # What.
    entity_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    entity_id: Mapped[int] = mapped_column(index=True, nullable=False)
    entity_ref: Mapped[str | None] = mapped_column(String(64))
    action: Mapped[AuditAction] = mapped_column(
        enum_column(AuditAction), default=AuditAction.UPDATED, nullable=False
    )
    field: Mapped[str | None] = mapped_column(String(64))
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
