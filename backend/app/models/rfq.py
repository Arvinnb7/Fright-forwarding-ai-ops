"""RFQ — the central inquiry record."""
from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import TimestampMixin, enum_column as _enum
from app.core.tenancy import TenantMixin
from app.models.enums import RFQStatus, ShipmentType, TransportMode, Urgency

# JSONB on PostgreSQL, plain JSON elsewhere (e.g. SQLite in tests).
JSONType = JSON().with_variant(JSONB, "postgresql")

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.partner_rate import PartnerRate
    from app.models.quote import Quote


class RFQ(Base, TenantMixin, TimestampMixin):
    __tablename__ = "rfqs"
    # Reference numbers restart per organization, so uniqueness is scoped.
    __table_args__ = (UniqueConstraint("org_id", "reference", name="uq_rfqs_org_reference"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str | None] = mapped_column(String(64), index=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"))

    raw_message: Mapped[str | None] = mapped_column(Text)
    # When the CUSTOMER asked (email date), not when we processed it.
    # This is the start of the response-time clock the ROI case rests on.
    received_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )

    # Routing
    origin: Mapped[str | None] = mapped_column(String(255))
    destination: Mapped[str | None] = mapped_column(String(255))
    pickup_address: Mapped[str | None] = mapped_column(Text)
    delivery_address: Mapped[str | None] = mapped_column(Text)

    # Shipment characteristics
    transport_mode: Mapped[TransportMode | None] = mapped_column(_enum(TransportMode))
    shipment_type: Mapped[ShipmentType | None] = mapped_column(_enum(ShipmentType))
    container_type: Mapped[str | None] = mapped_column(String(64))
    commodity: Mapped[str | None] = mapped_column(Text)
    hs_code: Mapped[str | None] = mapped_column(String(32))
    gross_weight: Mapped[str | None] = mapped_column(String(64))
    cbm: Mapped[str | None] = mapped_column(String(64))
    dimensions: Mapped[str | None] = mapped_column(String(255))
    package_count: Mapped[str | None] = mapped_column(String(64))
    incoterm: Mapped[str | None] = mapped_column(String(32))
    cargo_ready_date: Mapped[date | None] = mapped_column(Date)
    required_delivery_date: Mapped[date | None] = mapped_column(Date)

    # Flags / requirements
    dangerous_goods: Mapped[bool] = mapped_column(Boolean, default=False)
    temperature_requirement: Mapped[str | None] = mapped_column(String(128))
    insurance_required: Mapped[bool] = mapped_column(Boolean, default=False)
    customs_required: Mapped[bool] = mapped_column(Boolean, default=False)
    warehouse_required: Mapped[bool] = mapped_column(Boolean, default=False)
    special_handling: Mapped[str | None] = mapped_column(Text)

    # AI-derived
    missing_fields: Mapped[list[str]] = mapped_column(JSONType, default=list)
    extracted_fields: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    requested_charges: Mapped[list[str]] = mapped_column(JSONType, default=list)
    recommended_next_action: Mapped[str | None] = mapped_column(Text)
    urgency: Mapped[Urgency] = mapped_column(_enum(Urgency), default=Urgency.NORMAL)
    urgency_score: Mapped[float | None] = mapped_column(Float)
    status: Mapped[RFQStatus] = mapped_column(_enum(RFQStatus), default=RFQStatus.NEW)

    customer: Mapped["Customer | None"] = relationship(back_populates="rfqs")
    partner_rates: Mapped[list["PartnerRate"]] = relationship(
        back_populates="rfq", cascade="all, delete-orphan"
    )
    quotes: Mapped[list["Quote"]] = relationship(back_populates="rfq")
