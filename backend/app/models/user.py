"""Application user — belongs to exactly one organization."""
from __future__ import annotations

from enum import Enum

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import TimestampMixin, enum_column


class UserRole(str, Enum):
    """What a member may do inside their organization.

    ADMIN       — everything, including managing users and org settings.
    COORDINATOR — the day-to-day operator: may approve pricing and send.
    VIEWER      — read-only (management / finance visibility).
    """

    ADMIN = "admin"
    COORDINATOR = "coordinator"
    VIEWER = "viewer"


class User(Base, TimestampMixin):
    """Not tenant-filtered: login resolves a user by email *before* the
    organization is known. Scoping is done explicitly via `organization_id`."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255))
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role: Mapped[UserRole] = mapped_column(
        enum_column(UserRole), default=UserRole.COORDINATOR, nullable=False
    )

    @property
    def can_approve_pricing(self) -> bool:
        return self.role in (UserRole.ADMIN, UserRole.COORDINATOR)

    @property
    def is_org_admin(self) -> bool:
        return self.role == UserRole.ADMIN
