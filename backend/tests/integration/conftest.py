"""Integration test fixtures — run against a live Postgres (+ optionally Redis).

Enable with:  RUN_INTEGRATION=1 pytest tests/integration
The suite migrates the database and bootstraps the admin user itself, so a
bare, empty Postgres (e.g. a CI service container) is enough.
"""
from __future__ import annotations

import os
from typing import Any

import pytest

requires_integration = pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION") != "1",
    reason="integration tests need RUN_INTEGRATION=1 and a live Postgres",
)


class IntegrationFakeLLM:
    """Deterministic LLM used for integration runs (no network, no cost).

    Real-API behaviour is covered separately by `python -m app.smoke_llm`.
    """

    provider = "fake"
    model = "fake-integration"

    RFQ_OUTPUT: dict[str, Any] = {
        "customer_company": None, "contact_name": "Ahmed", "contact_email": None,
        "contact_phone": None, "origin": "Shanghai", "destination": "Jebel Ali",
        "pickup_address": None, "delivery_address": None, "transport_mode": "Sea",
        "shipment_type": "FCL", "container_type": "40HC",
        "commodity": "Plastic household items", "hs_code": None,
        "gross_weight": "12500 kg", "cbm": None, "dimensions": None,
        "package_count": None, "incoterm": None, "cargo_ready_date_text": "15 July",
        "dangerous_goods": False, "temperature_requirement": None,
        "insurance_required": False, "customs_required": False,
        "warehouse_required": False, "special_handling": None,
        "requested_charges": ["Ocean freight", "Destination charges"],
        "missing_fields": ["Customer company", "HS code"],
        "urgency": "Normal", "urgency_score": 0.4,
        "recommended_next_action": "Request Incoterm and HS code.",
    }

    # Test emails carry an explicit marker in the subject so triage is
    # deterministic; real classification quality is measured by the eval suite,
    # not by these tests.
    MARKERS = {
        "[RFQ]": "New RFQ",
        "[RATE]": "Partner rate reply",
        "[REPLY]": "Customer reply",
        "[SPAM]": "Not relevant",
    }

    def complete(self, *, system: str, user: str, max_tokens: int = 4096) -> str:
        return "DRAFT TEXT (editable) — generated for integration testing."

    def _classify(self, user: str) -> dict[str, Any]:
        import re

        classification = "Not relevant"
        for marker, label in self.MARKERS.items():
            if marker in user:
                classification = label
                break
        reference = re.search(r"\b(?:RFQ|Q|JOB)-\d{4}-\d{4}\b", user)
        return {
            "classification": classification,
            "confidence": 0.95,
            "reason": "Marker found in subject.",
            "mentions_reference": reference.group(0) if reference else None,
        }

    def complete_structured(
        self, *, system: str, user: str, schema: dict, max_tokens: int = 8000
    ) -> dict:
        props = schema.get("properties", {})
        if "classification" in props:  # email-triage schema
            return self._classify(user)
        if "suggestions" in props:  # document-suggestions schema
            return {
                "suggestions": [
                    {"document_type": "Commercial Invoice", "reason": "Required for customs."},
                    {"document_type": "Packing List", "reason": "Required for cargo handling."},
                    {"document_type": "Bill of Lading", "reason": "Sea shipment transport document."},
                ]
            }
        if "options" in props:  # rate-analysis schema
            ids = props["options"]["items"]["properties"]["rate_id"]["enum"]
            return {
                "cheapest_rate_id": ids[0],
                "fastest_rate_id": ids[-1],
                "best_margin_rate_id": ids[0],
                "lowest_risk_rate_id": ids[0],
                "recommended_rate_id": ids[0],
                "recommendation_reason": "Cheapest reliable option.",
                "tradeoffs": "Price vs transit time.",
                "options": [
                    {
                        "rate_id": i,
                        "partner_name": f"Partner {i}",
                        "summary": "Solid option.",
                        "pros": ["competitive"],
                        "cons": [],
                        "risk_notes": None,
                    }
                    for i in ids
                ],
            }
        return dict(self.RFQ_OUTPUT)


@pytest.fixture(scope="session")
def integration_env():
    """Migrate the DB and bootstrap the admin account (idempotent)."""
    from alembic import command
    from alembic.config import Config

    command.upgrade(Config("alembic.ini"), "head")

    from app.core.db import SessionLocal
    from app.initial_data import ensure_admin

    db = SessionLocal()
    try:
        ensure_admin(db)
    finally:
        db.close()
    yield


@pytest.fixture(scope="session")
def client(integration_env):
    from fastapi.testclient import TestClient

    from app.llm.factory import set_llm
    from app.main import app

    set_llm(IntegrationFakeLLM())  # never hit a real provider in CI
    with TestClient(app) as test_client:
        yield test_client
    set_llm(None)


@pytest.fixture(scope="session")
def auth_headers(client):
    from app.core.config import settings

    res = client.post(
        "/api/auth/login",
        data={"username": settings.admin_email, "password": settings.admin_password},
    )
    assert res.status_code == 200, f"login failed: {res.text}"
    return {"Authorization": f"Bearer {res.json()['access_token']}"}
