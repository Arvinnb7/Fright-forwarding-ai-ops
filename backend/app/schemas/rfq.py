"""RFQ schemas: API I/O + the structured-extraction contract for the parser agent."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    RFQStatus,
    ShipmentType,
    TransportMode,
    Urgency,
)

# ── Agent extraction contract ────────────────────────────────
# Validated model the parser agent returns. A matching JSON schema (below) is
# sent to the LLM so the output is constrained.


class RFQExtraction(BaseModel):
    customer_company: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None

    origin: str | None = None
    destination: str | None = None
    pickup_address: str | None = None
    delivery_address: str | None = None

    transport_mode: TransportMode | None = None
    shipment_type: ShipmentType | None = None
    container_type: str | None = None
    commodity: str | None = None
    hs_code: str | None = None
    gross_weight: str | None = None
    cbm: str | None = None
    dimensions: str | None = None
    package_count: str | None = None
    incoterm: str | None = None
    cargo_ready_date_text: str | None = None

    dangerous_goods: bool = False
    temperature_requirement: str | None = None
    insurance_required: bool = False
    customs_required: bool = False
    warehouse_required: bool = False
    special_handling: str | None = None

    requested_charges: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    urgency: Urgency = Urgency.NORMAL
    urgency_score: float | None = None
    recommended_next_action: str | None = None


def _nullable_str() -> dict[str, Any]:
    return {"type": ["string", "null"]}


# Hand-built JSON schema for the LLM (provider-neutral; additionalProperties
# disallowed so the output stays exactly on-contract).
RFQ_EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "customer_company": _nullable_str(),
        "contact_name": _nullable_str(),
        "contact_email": _nullable_str(),
        "contact_phone": _nullable_str(),
        "origin": _nullable_str(),
        "destination": _nullable_str(),
        "pickup_address": _nullable_str(),
        "delivery_address": _nullable_str(),
        "transport_mode": {
            "type": ["string", "null"],
            "enum": [*[m.value for m in TransportMode], None],
        },
        "shipment_type": {
            "type": ["string", "null"],
            "enum": [*[m.value for m in ShipmentType], None],
        },
        "container_type": _nullable_str(),
        "commodity": _nullable_str(),
        "hs_code": _nullable_str(),
        "gross_weight": _nullable_str(),
        "cbm": _nullable_str(),
        "dimensions": _nullable_str(),
        "package_count": _nullable_str(),
        "incoterm": _nullable_str(),
        "cargo_ready_date_text": _nullable_str(),
        "dangerous_goods": {"type": "boolean"},
        "temperature_requirement": _nullable_str(),
        "insurance_required": {"type": "boolean"},
        "customs_required": {"type": "boolean"},
        "warehouse_required": {"type": "boolean"},
        "special_handling": _nullable_str(),
        "requested_charges": {"type": "array", "items": {"type": "string"}},
        "missing_fields": {"type": "array", "items": {"type": "string"}},
        "urgency": {"type": "string", "enum": [m.value for m in Urgency]},
        "urgency_score": {"type": ["number", "null"]},
        "recommended_next_action": _nullable_str(),
    },
    "required": [
        "customer_company",
        "contact_name",
        "contact_email",
        "contact_phone",
        "origin",
        "destination",
        "pickup_address",
        "delivery_address",
        "transport_mode",
        "shipment_type",
        "container_type",
        "commodity",
        "hs_code",
        "gross_weight",
        "cbm",
        "dimensions",
        "package_count",
        "incoterm",
        "cargo_ready_date_text",
        "dangerous_goods",
        "temperature_requirement",
        "insurance_required",
        "customs_required",
        "warehouse_required",
        "special_handling",
        "requested_charges",
        "missing_fields",
        "urgency",
        "urgency_score",
        "recommended_next_action",
    ],
}


# ── API schemas ──────────────────────────────────────────────


class RFQParseRequest(BaseModel):
    raw_message: str = Field(min_length=1, description="Pasted customer inquiry text")
    customer_id: int | None = None
    persist: bool = Field(
        default=True, description="Create an RFQ record from the extraction"
    )


class RFQUpdate(BaseModel):
    """Editable fields on an RFQ (all optional — partial update)."""

    customer_id: int | None = None
    origin: str | None = None
    destination: str | None = None
    pickup_address: str | None = None
    delivery_address: str | None = None
    transport_mode: TransportMode | None = None
    shipment_type: ShipmentType | None = None
    container_type: str | None = None
    commodity: str | None = None
    hs_code: str | None = None
    gross_weight: str | None = None
    cbm: str | None = None
    dimensions: str | None = None
    package_count: str | None = None
    incoterm: str | None = None
    cargo_ready_date: date | None = None
    required_delivery_date: date | None = None
    dangerous_goods: bool | None = None
    temperature_requirement: str | None = None
    insurance_required: bool | None = None
    customs_required: bool | None = None
    warehouse_required: bool | None = None
    special_handling: str | None = None
    missing_fields: list[str] | None = None
    requested_charges: list[str] | None = None
    urgency: Urgency | None = None
    status: RFQStatus | None = None
    # Assignment. Explicitly nullable so work can be handed back to the pool.
    owner_id: int | None = None


class RFQOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reference: str | None
    customer_id: int | None
    raw_message: str | None
    origin: str | None
    destination: str | None
    pickup_address: str | None
    delivery_address: str | None
    transport_mode: TransportMode | None
    shipment_type: ShipmentType | None
    container_type: str | None
    commodity: str | None
    hs_code: str | None
    gross_weight: str | None
    cbm: str | None
    dimensions: str | None
    package_count: str | None
    incoterm: str | None
    cargo_ready_date: date | None
    required_delivery_date: date | None
    dangerous_goods: bool
    temperature_requirement: str | None
    insurance_required: bool
    customs_required: bool
    warehouse_required: bool
    special_handling: str | None
    missing_fields: list[str]
    requested_charges: list[str]
    recommended_next_action: str | None
    urgency: Urgency
    urgency_score: float | None
    status: RFQStatus
    owner_id: int | None
    received_at: datetime | None
    first_quoted_at: datetime | None
    created_at: datetime
    updated_at: datetime
