"""Rate offer from a partner (carrier/agent/trucker/...), or an imported tariff.

Originally a rate belonged to exactly one RFQ, which meant every enquiry began
by asking partners for prices that were often already known — and made a fast
answer impossible. Rates now carry their own lane, and `rfq_id` is optional, so
a standing rate sheet can be loaded once and quoted from immediately.

The lane columns are copied from the RFQ when the rate is entered rather than
followed by reference: editing an old RFQ must not silently rewrite what a
partner quoted for.
"""
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Date, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.tenancy import TenantMixin
from app.models.base import TimestampMixin, enum_column
from app.models.enums import PartnerType, TransportMode

if TYPE_CHECKING:
    from app.models.rfq import RFQ


class RateSource(str, Enum):
    """Where the number came from — it changes how far to trust it."""

    PARTNER_QUOTE = "Partner quote"  # a partner priced this specific enquiry
    TARIFF = "Tariff"  # imported from a standing rate sheet


class PartnerRate(Base, TenantMixin, TimestampMixin):
    __tablename__ = "partner_rates"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Optional: tariff rates exist without any enquiry behind them.
    rfq_id: Mapped[int | None] = mapped_column(ForeignKey("rfqs.id"), index=True)

    partner_name: Mapped[str] = mapped_column(String(255), nullable=False)
    partner_type: Mapped[PartnerType | None] = mapped_column(enum_column(PartnerType))
    source: Mapped[RateSource] = mapped_column(
        enum_column(RateSource), default=RateSource.PARTNER_QUOTE, nullable=False
    )

    # ── Lane identity (see app/services/lanes.py) ────────────
    origin: Mapped[str | None] = mapped_column(String(255))
    destination: Mapped[str | None] = mapped_column(String(255))
    transport_mode: Mapped[TransportMode | None] = mapped_column(enum_column(TransportMode))
    container_type: Mapped[str | None] = mapped_column(String(64))
    lane_key: Mapped[str | None] = mapped_column(String(512), index=True)
    route_key: Mapped[str | None] = mapped_column(String(512), index=True)

    cost_amount: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    included_charges: Mapped[str | None] = mapped_column(Text)
    excluded_charges: Mapped[str | None] = mapped_column(Text)
    transit_time: Mapped[str | None] = mapped_column(String(128))
    validity_date: Mapped[date | None] = mapped_column(Date, index=True)
    free_time: Mapped[str | None] = mapped_column(String(128))
    notes: Mapped[str | None] = mapped_column(Text)
    risk_notes: Mapped[str | None] = mapped_column(Text)
    reliability_score: Mapped[float | None] = mapped_column(Float)

    rfq: Mapped["RFQ | None"] = relationship(back_populates="partner_rates")
