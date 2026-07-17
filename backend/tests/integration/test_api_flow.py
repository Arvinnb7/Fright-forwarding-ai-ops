"""Full HTTP flow against a live Postgres: the spec's core workflow end-to-end.

RFQ parse → drafts → rate entry/analysis → quote (pause → approve) →
follow-up → reports. Mirrors spec §16 acceptance criteria.
"""
from __future__ import annotations

import pytest

from tests.integration.conftest import requires_integration

pytestmark = requires_integration

RAW_MESSAGE = (
    "Please quote for 1x40HC from Shanghai to Jebel Ali. "
    "Commodity: plastic household items. Gross weight: 12,500 kg. "
    "Cargo ready by 15 July. Need ocean freight and destination charges."
)


@pytest.fixture(scope="module")
def rfq_id(client, auth_headers) -> int:
    res = client.post(
        "/api/rfqs/parse",
        json={"raw_message": RAW_MESSAGE, "persist": True},
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["extraction"]["origin"] == "Shanghai"
    assert "Incoterm" in body["extraction"]["missing_fields"]  # post-processing
    assert body["rfq"]["reference"].startswith("RFQ-")
    return body["rfq"]["id"]


def test_health(client):
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/health/db").json()["database"] == "reachable"


def test_auth_required(client):
    assert client.get("/api/rfqs").status_code == 401


def test_rfq_crud(client, auth_headers, rfq_id):
    assert any(
        r["id"] == rfq_id for r in client.get("/api/rfqs", headers=auth_headers).json()
    )
    res = client.patch(
        f"/api/rfqs/{rfq_id}", json={"incoterm": "FOB"}, headers=auth_headers
    )
    assert res.json()["incoterm"] == "FOB"
    assert client.get("/api/rfqs/999999", headers=auth_headers).status_code == 404


def test_drafts(client, auth_headers, rfq_id):
    res = client.post(f"/api/rfqs/{rfq_id}/missing-info-draft", headers=auth_headers)
    assert res.status_code == 200 and res.json()["draft"]
    res = client.post(
        f"/api/rfqs/{rfq_id}/rate-request-draft",
        json={"partner_type": "Shipping line"},
        headers=auth_headers,
    )
    assert res.status_code == 200 and res.json()["draft"]


def test_rates_and_quote_flow(client, auth_headers, rfq_id):
    # Enter two partner rates
    r1 = client.post(
        f"/api/rfqs/{rfq_id}/rates",
        json={"partner_name": "Line A", "partner_type": "Shipping line",
              "cost_amount": 1500, "currency": "USD", "transit_time": "30 days"},
        headers=auth_headers,
    )
    r2 = client.post(
        f"/api/rfqs/{rfq_id}/rates",
        json={"partner_name": "Line B", "partner_type": "Shipping line",
              "cost_amount": 1750, "currency": "USD", "transit_time": "22 days"},
        headers=auth_headers,
    )
    assert r1.status_code == 201 and r2.status_code == 201
    rate_ids = {r1.json()["id"], r2.json()["id"]}

    # AI comparison references real rate ids only
    analysis = client.post(
        f"/api/rfqs/{rfq_id}/rates/analyze", headers=auth_headers
    ).json()
    assert analysis["recommended_rate_id"] in rate_ids
    assert len(analysis["options"]) == 2

    # Quote: margin math + pause for approval (spec §12 human-in-the-loop)
    review = client.post(
        "/api/quotes/start",
        json={"rfq_id": rfq_id, "selected_rate_id": r1.json()["id"], "markup_value": 20},
        headers=auth_headers,
    ).json()
    assert review["selling_price"] == 1800.0
    assert review["gross_margin"] == 300.0
    quote_id = review["quote_id"]
    assert (
        client.get(f"/api/quotes/{quote_id}", headers=auth_headers).json()["status"]
        == "Pending approval"
    )

    # Approve with an edited price; mark sent → follow-up scheduled
    approved = client.post(
        f"/api/quotes/{quote_id}/approve",
        json={"approved": True, "selling_price": 2000, "mark_sent": True},
        headers=auth_headers,
    ).json()
    assert approved["status"] == "Sent"
    assert approved["selling_price"] == 2000.0
    assert approved["gross_margin"] == 500.0  # recomputed after human edit

    # PDF export
    pdf = client.get(f"/api/quotes/{quote_id}/pdf", headers=auth_headers)
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"

    # Follow-up exists and can be drafted + updated
    follow_ups = client.get("/api/follow-ups", headers=auth_headers).json()
    mine = [f for f in follow_ups if f["quote_id"] == quote_id]
    assert mine, "expected a follow-up scheduled on send"
    fu_id = mine[0]["id"]
    draft = client.post(
        f"/api/follow-ups/{fu_id}/draft",
        json={"follow_up_type": "polite"},
        headers=auth_headers,
    ).json()
    assert draft["draft"]
    updated = client.patch(
        f"/api/follow-ups/{fu_id}",
        json={"status": "Sent", "sent_manually": True},
        headers=auth_headers,
    ).json()
    assert updated["status"] == "Sent"


def test_reports(client, auth_headers):
    dash = client.get("/api/reports/dashboard", headers=auth_headers).json()
    assert "estimated_pipeline" in dash
    daily = client.get("/api/reports/daily", headers=auth_headers).json()
    assert daily["report_text"]
    pdf = client.get("/api/reports/daily/pdf", headers=auth_headers)
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
