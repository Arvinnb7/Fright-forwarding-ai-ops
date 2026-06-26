"""RFQ parser agent tests against the spec's §17 worked example."""
from __future__ import annotations

from app.agents.rfq_parser import run_rfq_parser
from app.schemas.rfq import RFQExtraction
from app.services.rfq_service import create_rfq_from_extraction

EXAMPLE_RFQ = """
Hi,

Please quote for 1x40HC from Shanghai to Jebel Ali.
Commodity: plastic household items.
Gross weight: 12,500 kg.
Cargo ready by 15 July.
Need ocean freight and destination charges.

Regards,
Ahmed
"""

# What a competent model returns for the example (the agent then post-processes).
MODEL_OUTPUT = {
    "customer_company": None,
    "contact_name": "Ahmed",
    "contact_email": None,
    "contact_phone": None,
    "origin": "Shanghai",
    "destination": "Jebel Ali",
    "pickup_address": None,
    "delivery_address": None,
    "transport_mode": "Sea",
    "shipment_type": "FCL",
    "container_type": "40HC",
    "commodity": "Plastic household items",
    "hs_code": None,
    "gross_weight": "12500 kg",
    "cbm": None,
    "dimensions": None,
    "package_count": None,
    "incoterm": None,
    "cargo_ready_date_text": "15 July",
    "dangerous_goods": False,
    "temperature_requirement": None,
    "insurance_required": False,
    "customs_required": False,
    "warehouse_required": False,
    "special_handling": None,
    "requested_charges": ["Ocean freight", "Destination charges"],
    "missing_fields": ["Customer company", "HS code", "Pickup address"],
    "urgency": "Normal",
    "urgency_score": 0.4,
    "recommended_next_action": "Request company name, Incoterm and HS code before pricing.",
}


def test_rfq_parser_extracts_core_fields(fake_llm):
    fake_llm.structured_response = MODEL_OUTPUT
    extraction = run_rfq_parser(EXAMPLE_RFQ, fake_llm)

    assert isinstance(extraction, RFQExtraction)
    assert extraction.origin == "Shanghai"
    assert extraction.destination == "Jebel Ali"
    assert extraction.transport_mode.value == "Sea"
    assert extraction.shipment_type.value == "FCL"
    assert extraction.container_type == "40HC"
    assert extraction.requested_charges == ["Ocean freight", "Destination charges"]


def test_rfq_parser_flags_pricing_critical_missing_fields(fake_llm):
    fake_llm.structured_response = MODEL_OUTPUT
    extraction = run_rfq_parser(EXAMPLE_RFQ, fake_llm)

    # Incoterm is pricing-critical and absent → must be flagged even though the
    # model omitted it from its own missing_fields list.
    assert "Incoterm" in extraction.missing_fields
    # The model's own missing fields are preserved too.
    assert "HS code" in extraction.missing_fields


def test_create_rfq_from_extraction_persists(fake_llm, db_session):
    fake_llm.structured_response = MODEL_OUTPUT
    extraction = run_rfq_parser(EXAMPLE_RFQ, fake_llm)

    rfq = create_rfq_from_extraction(db_session, extraction, EXAMPLE_RFQ.strip())

    assert rfq.id is not None
    assert rfq.reference.startswith("RFQ-")
    assert rfq.origin == "Shanghai"
    assert rfq.status.value == "Incomplete"  # has missing fields
    assert rfq.extracted_fields["container_type"] == "40HC"
