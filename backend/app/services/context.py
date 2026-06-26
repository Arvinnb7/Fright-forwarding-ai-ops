"""Render ORM rows into compact, readable context blocks for the agents.

Keeping this in one place means every agent sees the shipment the same way, and
the prompts stay decoupled from the ORM.
"""
from __future__ import annotations

from app.models.quote import Quote
from app.models.rfq import RFQ

_FIELDS: list[tuple[str, str]] = [
    ("reference", "RFQ reference"),
    ("origin", "Origin"),
    ("destination", "Destination"),
    ("pickup_address", "Pickup address"),
    ("delivery_address", "Delivery address"),
    ("transport_mode", "Transport mode"),
    ("shipment_type", "Shipment type"),
    ("container_type", "Container type"),
    ("commodity", "Commodity"),
    ("hs_code", "HS code"),
    ("gross_weight", "Gross weight"),
    ("cbm", "Volume / CBM"),
    ("dimensions", "Dimensions"),
    ("package_count", "Packages"),
    ("incoterm", "Incoterm"),
    ("cargo_ready_date", "Cargo ready date"),
    ("temperature_requirement", "Temperature requirement"),
    ("special_handling", "Special handling"),
]


def _value(rfq: RFQ, attr: str) -> str | None:
    val = getattr(rfq, attr, None)
    if val is None or val == "":
        return None
    # Enums render as their .value
    return getattr(val, "value", str(val))


def rfq_context(rfq: RFQ) -> str:
    """A readable summary of what is known about the shipment."""
    lines: list[str] = []
    for attr, label in _FIELDS:
        val = _value(rfq, attr)
        if val:
            lines.append(f"- {label}: {val}")
    flags = []
    if rfq.dangerous_goods:
        flags.append("Dangerous goods")
    if rfq.insurance_required:
        flags.append("Insurance required")
    if rfq.customs_required:
        flags.append("Customs clearance required")
    if rfq.warehouse_required:
        flags.append("Warehouse required")
    if flags:
        lines.append(f"- Requirements: {', '.join(flags)}")
    if rfq.requested_charges:
        lines.append(f"- Requested charges: {', '.join(rfq.requested_charges)}")
    if rfq.missing_fields:
        lines.append(f"- Missing information: {', '.join(rfq.missing_fields)}")
    return "\n".join(lines) if lines else "- (no structured details captured yet)"


def quote_context(quote: Quote) -> str:
    """A readable summary of a quotation for the follow-up agent."""
    lines: list[str] = [f"- Quote number: {quote.quote_number or quote.id}"]
    if quote.customer and quote.customer.company_name:
        lines.append(f"- Customer: {quote.customer.company_name}")
    if quote.selling_price is not None:
        lines.append(f"- Selling price: {quote.selling_price} {quote.currency}")
    if quote.validity_date:
        lines.append(f"- Validity: {quote.validity_date.isoformat()}")
    if quote.sent_at:
        lines.append(f"- Sent on: {quote.sent_at.date().isoformat()}")
    if quote.rfq:
        if quote.rfq.origin and quote.rfq.destination:
            lines.append(f"- Route: {quote.rfq.origin} -> {quote.rfq.destination}")
        if quote.rfq.commodity:
            lines.append(f"- Commodity: {quote.rfq.commodity}")
    return "\n".join(lines)

