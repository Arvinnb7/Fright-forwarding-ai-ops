"""Booking / job file created from a won quote."""
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import TimestampMixin, enum_column
from app.core.tenancy import TenantMixin
from app.models.enums import BookingStatus

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.issue import Issue
    from app.models.quote import Quote


class Booking(Base, TenantMixin, TimestampMixin):
    __tablename__ = "bookings"
    # Reference numbers restart per organization, so uniqueness is scoped.
    __table_args__ = (UniqueConstraint("org_id", "job_number", name="uq_bookings_org_job"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    job_number: Mapped[str | None] = mapped_column(String(64), index=True)
    quote_id: Mapped[int | None] = mapped_column(ForeignKey("quotes.id"), index=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), index=True)

    shipper: Mapped[str | None] = mapped_column(Text)
    consignee: Mapped[str | None] = mapped_column(Text)
    notify_party: Mapped[str | None] = mapped_column(Text)
    origin: Mapped[str | None] = mapped_column(String(255))
    destination: Mapped[str | None] = mapped_column(String(255))
    cargo_details: Mapped[str | None] = mapped_column(Text)

    agreed_price: Mapped[float | None] = mapped_column(Float)
    estimated_cost: Mapped[float | None] = mapped_column(Float)
    estimated_margin: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8), default="USD")

    assigned_to: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[BookingStatus] = mapped_column(
        enum_column(BookingStatus), default=BookingStatus.BOOKING_CONFIRMED
    )
    etd: Mapped[date | None] = mapped_column(Date)
    eta: Mapped[date | None] = mapped_column(Date)

    quote: Mapped["Quote | None"] = relationship(back_populates="bookings")
    documents: Mapped[list["Document"]] = relationship(
        back_populates="booking", cascade="all, delete-orphan"
    )
    issues: Mapped[list["Issue"]] = relationship(
        back_populates="booking", cascade="all, delete-orphan"
    )
