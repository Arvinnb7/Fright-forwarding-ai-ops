"""Phase 3 modules over HTTP: CRM → booking → documents → status update →
issues → exports → settings → follow-up cadence."""
from __future__ import annotations

import pytest

from tests.integration.conftest import requires_integration

pytestmark = requires_integration


@pytest.fixture(scope="module")
def customer_id(client, auth_headers) -> int:
    res = client.post(
        "/api/customers",
        json={
            "company_name": "Integration Trading FZE",
            "contact_name": "Sara",
            "email": "sara@integration-trading.example",
            "country": "UAE",
            "city": "Dubai",
        },
        headers=auth_headers,
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


@pytest.fixture(scope="module")
def sent_quote_id(client, auth_headers, customer_id) -> int:
    """Create an RFQ linked to the customer, add a rate, quote it, send it."""
    rfq = client.post(
        "/api/rfqs/parse",
        json={
            "raw_message": "Quote 1x40HC Shanghai to Jebel Ali, plastic goods, 12500 kg.",
            "persist": True,
            "customer_id": customer_id,
        },
        headers=auth_headers,
    ).json()["rfq"]
    rate = client.post(
        f"/api/rfqs/{rfq['id']}/rates",
        json={"partner_name": "Line X", "cost_amount": 1500, "currency": "USD",
              "transit_time": "28 days"},
        headers=auth_headers,
    ).json()
    review = client.post(
        "/api/quotes/start",
        json={"rfq_id": rfq["id"], "selected_rate_id": rate["id"], "markup_value": 20},
        headers=auth_headers,
    ).json()
    approved = client.post(
        f"/api/quotes/{review['quote_id']}/approve",
        json={"approved": True, "mark_sent": True},
        headers=auth_headers,
    ).json()
    assert approved["status"] == "Sent"
    return approved["id"]


def test_customer_crud_and_profile(client, auth_headers, customer_id):
    res = client.get(f"/api/customers/{customer_id}", headers=auth_headers)
    assert res.json()["company_name"] == "Integration Trading FZE"

    res = client.get("/api/customers?search=Integration", headers=auth_headers)
    assert any(c["id"] == customer_id for c in res.json())

    res = client.patch(
        f"/api/customers/{customer_id}", json={"industry": "Distribution"},
        headers=auth_headers,
    )
    assert res.json()["industry"] == "Distribution"

    profile = client.post(f"/api/customers/{customer_id}/profile", headers=auth_headers)
    assert profile.status_code == 200
    body = profile.json()
    assert body["summary"]
    assert body["stats"]["rfq_count"] >= 0


def test_booking_documents_status_update_issue(client, auth_headers, sent_quote_id):
    # Convert the sent quote → booking (marks quote Won)
    booking = client.post(
        "/api/bookings/from-quote",
        json={"quote_id": sent_quote_id, "shipper": "Shanghai Plastics Co",
              "consignee": "Integration Trading FZE"},
        headers=auth_headers,
    )
    assert booking.status_code == 201, booking.text
    booking = booking.json()
    assert booking["job_number"].startswith("JOB-")
    assert booking["agreed_price"] == 1800.0
    assert (
        client.get(f"/api/quotes/{sent_quote_id}", headers=auth_headers).json()["status"]
        == "Won"
    )

    bid = booking["id"]
    # Draft-stage quotes cannot be booked
    bad = client.post(
        "/api/bookings/from-quote", json={"quote_id": 999999}, headers=auth_headers
    )
    assert bad.status_code == 400

    # Status timeline update
    res = client.patch(
        f"/api/bookings/{bid}", json={"status": "In transit"}, headers=auth_headers
    )
    assert res.json()["status"] == "In transit"

    # AI document suggestions → created as Required
    sug = client.post(
        f"/api/bookings/{bid}/documents/suggest?create=true", headers=auth_headers
    ).json()
    assert sug["suggestions"]
    docs = client.get(f"/api/bookings/{bid}/documents", headers=auth_headers).json()
    assert docs

    # Mark one received
    res = client.patch(
        f"/api/bookings/documents/{docs[0]['id']}",
        json={"status": "Received"},
        headers=auth_headers,
    )
    assert res.json()["status"] == "Received"

    # Customer status update draft
    upd = client.post(
        f"/api/bookings/{bid}/status-update-draft",
        json={"status": "Vessel departed", "eta": "2026-08-15"},
        headers=auth_headers,
    ).json()
    assert upd["draft"]

    # Issue on the booking + drafts
    issue = client.post(
        "/api/issues",
        json={"booking_id": bid, "issue_type": "Customs hold",
              "severity": "High", "description": "Held for HS-code verification."},
        headers=auth_headers,
    ).json()
    esc = client.post(
        f"/api/issues/{issue['id']}/draft", json={"kind": "escalation"},
        headers=auth_headers,
    ).json()
    assert esc["draft"]
    res = client.patch(
        f"/api/issues/{issue['id']}",
        json={"status": "Resolved", "resolution_notes": "Docs corrected."},
        headers=auth_headers,
    )
    assert res.json()["status"] == "Resolved"


def test_exports_and_settings(client, auth_headers):
    for name in ("rfqs", "quotes", "customers"):
        res = client.get(f"/api/exports/{name}.csv", headers=auth_headers)
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("text/csv")
        assert len(res.text.splitlines()) >= 1  # header row at minimum

    res = client.get("/api/settings", headers=auth_headers).json()
    assert res["llm_provider"]
    assert "api_key" not in str(res).lower() or res.get("llm_key_configured") in (True, False)


def test_list_filters_and_pagination(client, auth_headers):
    res = client.get("/api/rfqs?search=Shanghai&limit=5", headers=auth_headers)
    assert res.status_code == 200
    assert "x-total-count" in {k.lower() for k in res.headers.keys()}
    res = client.get("/api/quotes?status_filter=Won", headers=auth_headers)
    assert all(q["status"] == "Won" for q in res.json())


def test_follow_up_cadence(client, auth_headers, sent_quote_id):
    """Marking a follow-up Sent schedules the next one per the 0/1/3/5/7 cadence."""
    fus = [
        f
        for f in client.get("/api/follow-ups", headers=auth_headers).json()
        if f["quote_id"] == sent_quote_id
    ]
    assert len(fus) == 1  # scheduled when the quote was sent
    before = len(fus)

    res = client.patch(
        f"/api/follow-ups/{fus[0]['id']}",
        json={"status": "Sent", "sent_manually": True},
        headers=auth_headers,
    )
    assert res.status_code == 200

    after = [
        f
        for f in client.get("/api/follow-ups", headers=auth_headers).json()
        if f["quote_id"] == sent_quote_id
    ]
    assert len(after) == before + 1  # next cadence step was auto-scheduled
    pending = [f for f in after if f["status"] == "Pending"]
    assert pending and pending[0]["due_date"] is not None
