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
from sqlalchemy import event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import TimestampMixin, enum_column as _enum
from app.core.tenancy import OwnedMixin, TenantMixin
from app.models.enums import RFQStatus, ShipmentType, TransportMode, Urgency

# JSONB on PostgreSQL, plain JSON elsewhere (e.g. SQLite in tests).
JSONType = JSON().with_variant(JSONB, "postgresql")

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.partner_rate import PartnerRate
    from app.models.quote import Quote


class RFQ(Base, TenantMixin, OwnedMixin, TimestampMixin):
    __tablename__ = "rfqs"
    # Reference numbers restart per organization, so uniqueness is scoped.
    __table_args__ = (UniqueConstraint("org_id", "reference", name="uq_rfqs_org_reference"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str | None] = mapped_column(String(64), index=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"))

    raw_message: Mapped[str | None] = mapped_column(Text)
    # The two ends of the response-time clock the whole ROI case rests on.
    # `received_at` is when the CUSTOMER asked (the email date), not when we
    # processed it; `first_quoted_at` is when the first quotation actually went
    # out. Stored rather than derived so the number can be filtered and sorted
    # on directly, and so a later status change cannot rewrite history.
    received_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    first_quoted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )

    # Routing
    origin: Mapped[str | None] = mapped_column(String(255))
    destination: Mapped[str | None] = mapped_column(String(255))
    # Derived lane identity, kept in sync by the listeners at the bottom of this
    # module so no write path can forget to recompute it.
    lane_key: Mapped[str | None] = mapped_column(String(512), index=True)
    route_key: Mapped[str | None] = mapped_column(String(512), index=True)
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
    partner_rates: Mapped[list["PartnerRate"]] = relationship(back_populates="rfq")
    quotes: Mapped[list["Quote"]] = relationship(back_populates="rfq")


# The lane key is what makes "we have quoted this before" work, so it is
# recomputed by the ORM on every insert and update rather than by each caller.
# A route corrected by hand three days later must start matching immediately.
@event.listens_for(RFQ, "before_insert")
@event.listens_for(RFQ, "before_update")
def _refresh_lane_key(_mapper, _connection, target: "RFQ") -> None:
    from app.services.lanes import lane_key, route_key

    target.lane_key = lane_key(
        target.origin, target.destination, target.transport_mode, target.container_type
    )
    target.route_key = route_key(target.origin, target.destination)
