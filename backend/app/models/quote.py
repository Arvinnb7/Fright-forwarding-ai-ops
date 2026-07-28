"""Quotation built for the customer."""
from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import TimestampMixin, enum_column
from app.core.tenancy import TenantMixin
from app.models.enums import QuoteStatus

if TYPE_CHECKING:
    from app.models.booking import Booking
    from app.models.customer import Customer
    from app.models.follow_up import FollowUp
    from app.models.rfq import RFQ


class Quote(Base, TenantMixin, TimestampMixin):
    __tablename__ = "quotes"
    # Reference numbers restart per organization, so uniqueness is scoped.
    __table_args__ = (UniqueConstraint("org_id", "quote_number", name="uq_quotes_org_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    quote_number: Mapped[str | None] = mapped_column(String(64), index=True)
    rfq_id: Mapped[int | None] = mapped_column(ForeignKey("rfqs.id"), index=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), index=True)
    selected_rate_id: Mapped[int | None] = mapped_column(ForeignKey("partner_rates.id"))

    cost_amount: Mapped[float | None] = mapped_column(Float)
    selling_price: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    gross_margin: Mapped[float | None] = mapped_column(Float)
    gross_margin_percentage: Mapped[float | None] = mapped_column(Float)

    validity_date: Mapped[date | None] = mapped_column(Date)
    quote_text: Mapped[str | None] = mapped_column(Text)
    status: Mapped[QuoteStatus] = mapped_column(enum_column(QuoteStatus), default=QuoteStatus.DRAFT)

    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_follow_up_date: Mapped[date | None] = mapped_column(Date)
    lost_reason: Mapped[str | None] = mapped_column(Text)

    rfq: Mapped["RFQ | None"] = relationship(back_populates="quotes")
    customer: Mapped["Customer | None"] = relationship(back_populates="quotes")
    follow_ups: Mapped[list["FollowUp"]] = relationship(
        back_populates="quote", cascade="all, delete-orphan"
    )
    bookings: Mapped[list["Booking"]] = relationship(back_populates="quote")
