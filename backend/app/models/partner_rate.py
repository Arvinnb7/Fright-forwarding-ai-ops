"""Rate offer received from a partner (carrier/agent/trucker/...)."""
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import TimestampMixin, enum_column
from app.models.enums import PartnerType

if TYPE_CHECKING:
    from app.models.rfq import RFQ


class PartnerRate(Base, TimestampMixin):
    __tablename__ = "partner_rates"

    id: Mapped[int] = mapped_column(primary_key=True)
    rfq_id: Mapped[int] = mapped_column(ForeignKey("rfqs.id"), index=True, nullable=False)

    partner_name: Mapped[str] = mapped_column(String(255), nullable=False)
    partner_type: Mapped[PartnerType | None] = mapped_column(enum_column(PartnerType))

    cost_amount: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    included_charges: Mapped[str | None] = mapped_column(Text)
    excluded_charges: Mapped[str | None] = mapped_column(Text)
    transit_time: Mapped[str | None] = mapped_column(String(128))
    validity_date: Mapped[date | None] = mapped_column(Date)
    free_time: Mapped[str | None] = mapped_column(String(128))
    notes: Mapped[str | None] = mapped_column(Text)
    risk_notes: Mapped[str | None] = mapped_column(Text)
    reliability_score: Mapped[float | None] = mapped_column(Float)

    rfq: Mapped["RFQ"] = relationship(back_populates="partner_rates")
