"""Cross-tenant isolation — the acceptance gate for the SaaS deployment.

A single leak here is a customer-visible breach, so this suite tries to reach
another organization's data through every route shape we expose: list, read by
id, update, delete, AI actions, exports and reports.
"""
from __future__ import annotations

import uuid

import pytest

from tests.integration.conftest import requires_integration

pytestmark = requires_integration


def _signup(client, company: str) -> dict:
    """Create an isolated organization and return its auth headers + ids."""
    email = f"{uuid.uuid4().hex[:10]}@example.com"
    res = client.post(
        "/api/auth/signup",
        json={
            "company_name": company,
            "full_name": "Owner",
            "email": email,
            "password": "test-password-123",
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    return {
        "headers": {"Authorization": f"Bearer {body['access_token']}"},
        "org_id": body["organization"]["id"],
        "email": email,
    }


@pytest.fixture(scope="module")
def org_a(client):
    return _signup(client, "Alpha Forwarding")


@pytest.fixture(scope="module")
def org_b(client):
    return _signup(client, "Beta Logistics")


@pytest.fixture(scope="module")
def a_data(client, org_a) -> dict:
    """A full record set owned by organization A."""
    h = org_a["headers"]
    customer = client.post(
        "/api/customers", json={"company_name": "Alpha Customer"}, headers=h
    ).json()
    rfq = client.post(
        "/api/rfqs/parse",
        json={"raw_message": "Quote 40HC Shanghai to Jebel Ali", "persist": True},
        headers=h,
    ).json()["rfq"]
    rate = client.post(
        f"/api/rfqs/{rfq['id']}/rates",
        json={"partner_name": "Alpha Line", "cost_amount": 1500, "currency": "USD"},
        headers=h,
    ).json()
    review = client.post(
        "/api/quotes/start",
        json={"rfq_id": rfq["id"], "selected_rate_id": rate["id"], "markup_value": 20},
        headers=h,
    ).json()
    quote = client.post(
        f"/api/quotes/{review['quote_id']}/approve",
        json={"approved": True, "mark_sent": True},
        headers=h,
    ).json()
    booking = client.post(
        "/api/bookings/from-quote", json={"quote_id": quote["id"]}, headers=h
    ).json()
    issue = client.post(
        "/api/issues",
        json={"booking_id": booking["id"], "issue_type": "Customs hold"},
        headers=h,
    ).json()
    follow_up = [
        f
        for f in client.get("/api/follow-ups", headers=h).json()
        if f["quote_id"] == quote["id"]
    ][0]
    return {
        "customer": customer, "rfq": rfq, "rate": rate, "quote": quote,
        "booking": booking, "issue": issue, "follow_up": follow_up,
    }


def test_signup_creates_isolated_organizations(org_a, org_b):
    assert org_a["org_id"] != org_b["org_id"]


def test_lists_never_include_another_orgs_rows(client, org_b, a_data):
    """B's collection endpoints must not contain any of A's records."""
    h = org_b["headers"]
    checks = [
        ("/api/rfqs", a_data["rfq"]["id"]),
        ("/api/quotes", a_data["quote"]["id"]),
        ("/api/customers", a_data["customer"]["id"]),
        ("/api/bookings", a_data["booking"]["id"]),
        ("/api/issues", a_data["issue"]["id"]),
        ("/api/follow-ups", a_data["follow_up"]["id"]),
    ]
    for path, foreign_id in checks:
        rows = client.get(path, headers=h).json()
        assert all(r["id"] != foreign_id for r in rows), f"{path} leaked org A row"


def test_reading_another_orgs_record_by_id_is_404(client, org_b, a_data):
    """Direct id access must behave as if the row does not exist."""
    h = org_b["headers"]
    for path in [
        f"/api/rfqs/{a_data['rfq']['id']}",
        f"/api/quotes/{a_data['quote']['id']}",
        f"/api/customers/{a_data['customer']['id']}",
        f"/api/bookings/{a_data['booking']['id']}",
    ]:
        assert client.get(path, headers=h).status_code == 404, f"{path} was readable"


def test_mutating_another_orgs_record_is_404(client, org_b, a_data):
    h = org_b["headers"]
    assert client.patch(
        f"/api/rfqs/{a_data['rfq']['id']}", json={"incoterm": "HACKED"}, headers=h
    ).status_code == 404
    assert client.patch(
        f"/api/customers/{a_data['customer']['id']}",
        json={"company_name": "HACKED"},
        headers=h,
    ).status_code == 404
    assert client.patch(
        f"/api/rates/{a_data['rate']['id']}", json={"cost_amount": 1}, headers=h
    ).status_code == 404
    assert client.patch(
        f"/api/issues/{a_data['issue']['id']}", json={"status": "Closed"}, headers=h
    ).status_code == 404
    assert client.delete(
        f"/api/rates/{a_data['rate']['id']}", headers=h
    ).status_code == 404


def test_original_records_survive_the_attempts(client, org_a, a_data):
    """After B's attempts, A's data is unchanged."""
    h = org_a["headers"]
    rfq = client.get(f"/api/rfqs/{a_data['rfq']['id']}", headers=h).json()
    assert rfq["incoterm"] != "HACKED"
    customer = client.get(f"/api/customers/{a_data['customer']['id']}", headers=h).json()
    assert customer["company_name"] == "Alpha Customer"
    rates = client.get(f"/api/rfqs/{a_data['rfq']['id']}/rates", headers=h).json()
    assert any(r["id"] == a_data["rate"]["id"] for r in rates), "rate was deleted"


def test_ai_actions_cannot_target_another_orgs_records(client, org_b, a_data):
    h = org_b["headers"]
    assert client.post(
        f"/api/rfqs/{a_data['rfq']['id']}/missing-info-draft", headers=h
    ).status_code == 404
    assert client.post(
        f"/api/rfqs/{a_data['rfq']['id']}/rate-request-draft",
        json={"partner_type": "Shipping line"},
        headers=h,
    ).status_code == 404
    assert client.post(
        f"/api/quotes/{a_data['quote']['id']}/approve",
        json={"approved": True},
        headers=h,
    ).status_code == 404
    assert client.post(
        f"/api/bookings/{a_data['booking']['id']}/status-update-draft",
        json={"status": "In transit"},
        headers=h,
    ).status_code == 404


def test_child_collections_are_scoped(client, org_b, a_data):
    """Nested routes must not expose children of another org's parent."""
    h = org_b["headers"]
    assert client.get(
        f"/api/rfqs/{a_data['rfq']['id']}/rates", headers=h
    ).status_code == 404
    assert client.get(
        f"/api/bookings/{a_data['booking']['id']}/documents", headers=h
    ).status_code == 404


def test_exports_and_reports_are_scoped(client, org_b, a_data):
    """A fresh org's exports/metrics must not count another org's data."""
    h = org_b["headers"]
    csv_text = client.get("/api/exports/rfqs.csv", headers=h).text
    assert "Jebel Ali" not in csv_text
    csv_text = client.get("/api/exports/quotes.csv", headers=h).text
    assert (a_data["quote"]["quote_number"] or "@@") not in csv_text

    metrics = client.get("/api/reports/dashboard", headers=h).json()
    assert metrics["quotes_sent"] == 0
    assert metrics["estimated_pipeline"] == 0


def test_per_org_reference_numbering_restarts(client, org_b):
    """Each tenant gets its own sequence starting at 1 — not a global counter."""
    h = org_b["headers"]
    rfq = client.post(
        "/api/rfqs/parse",
        json={"raw_message": "Quote LCL Ningbo to Dubai", "persist": True},
        headers=h,
    ).json()["rfq"]
    assert rfq["reference"].endswith("-0001"), rfq["reference"]


def test_admin_cannot_modify_users_of_another_org(client, org_a, org_b):
    """User management is org-bound even for an admin."""
    a_users = client.get("/api/auth/users", headers=org_a["headers"]).json()
    b_users = client.get("/api/auth/users", headers=org_b["headers"]).json()
    a_ids = {u["id"] for u in a_users}
    b_ids = {u["id"] for u in b_users}
    assert a_ids.isdisjoint(b_ids), "user lists overlap across organizations"

    foreign_id = next(iter(a_ids))
    res = client.patch(
        f"/api/auth/users/{foreign_id}", json={"is_active": False},
        headers=org_b["headers"],
    )
    assert res.status_code == 404
