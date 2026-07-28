"""Exception / issue tracked during the shipment lifecycle."""
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import TimestampMixin, enum_column
from app.core.tenancy import TenantMixin
from app.models.enums import IssueSeverity, IssueStatus

if TYPE_CHECKING:
    from app.models.booking import Booking


class Issue(Base, TenantMixin, TimestampMixin):
    __tablename__ = "issues"

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int | None] = mapped_column(ForeignKey("bookings.id"), index=True)

    issue_type: Mapped[str] = mapped_column(String(128), nullable=False)
    severity: Mapped[IssueSeverity] = mapped_column(
        enum_column(IssueSeverity), default=IssueSeverity.MEDIUM
    )
    description: Mapped[str | None] = mapped_column(Text)
    responsible_party: Mapped[str | None] = mapped_column(String(255))
    next_action: Mapped[str | None] = mapped_column(Text)
    due_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[IssueStatus] = mapped_column(enum_column(IssueStatus), default=IssueStatus.OPEN)
    resolution_notes: Mapped[str | None] = mapped_column(Text)

    booking: Mapped["Booking | None"] = relationship(back_populates="issues")
