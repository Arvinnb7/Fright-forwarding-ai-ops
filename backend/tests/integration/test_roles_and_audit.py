"""Roles, ownership and the audit trail.

Role enforcement is the second security gate after tenant isolation, and it
fails the same way: not by being wrong, but by being *missing* on the one
endpoint somebody forgot. So the viewer tests below sweep every kind of write
the API exposes rather than checking a representative sample, and the policy
they exercise is applied once on the router rather than route by route.
"""
from __future__ import annotations

import uuid

import pytest

from tests.integration.conftest import requires_integration

pytestmark = requires_integration


def _signup(client, company: str = "Team Forwarding") -> dict:
    res = client.post(
        "/api/auth/signup",
        json={
            "company_name": f"{company} {uuid.uuid4().hex[:6]}",
            "full_name": "Owner",
            "email": f"{uuid.uuid4().hex[:10]}@example.com",
            "password": "test-password-123",
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    return {
        "headers": {"Authorization": f"Bearer {body['access_token']}"},
        "org_id": body["organization"]["id"],
        "user_id": body["user"]["id"],
        "email": body["user"]["email"],
    }


def _add_member(client, admin: dict, role: str) -> dict:
    email = f"{uuid.uuid4().hex[:10]}@example.com"
    password = "member-password-123"
    res = client.post(
        "/api/auth/users",
        json={"email": email, "password": password, "role": role, "full_name": role.title()},
        headers=admin["headers"],
    )
    assert res.status_code == 201, res.text
    user = res.json()
    token = client.post(
        "/api/auth/login", data={"username": email, "password": password}
    ).json()["access_token"]
    return {
        "headers": {"Authorization": f"Bearer {token}"},
        "user_id": user["id"],
        "email": email,
        "role": role,
    }


@pytest.fixture
def admin(client):
    return _signup(client)


@pytest.fixture
def coordinator(client, admin):
    return _add_member(client, admin, "coordinator")


@pytest.fixture
def viewer(client, admin):
    return _add_member(client, admin, "viewer")


def _make_rfq(client, headers) -> dict:
    return client.post(
        "/api/rfqs/parse",
        json={"raw_message": "Quote 40HC Shanghai to Jebel Ali", "persist": True},
        headers=headers,
    ).json()["rfq"]


# --------------------------------------------------------------------------
# Viewers are read-only, everywhere
# --------------------------------------------------------------------------


def test_a_viewer_can_read(client, admin, viewer):
    _make_rfq(client, admin["headers"])

    for path in (
        "/api/rfqs",
        "/api/quotes",
        "/api/bookings",
        "/api/customers",
        "/api/issues",
        "/api/follow-ups",
        "/api/reports/dashboard",
        "/api/reports/performance",
        "/api/rates/lanes",
        "/api/audit",
        "/api/auth/me",
    ):
        res = client.get(path, headers=viewer["headers"])
        assert res.status_code == 200, f"{path} → {res.status_code} {res.text}"


def test_a_viewer_is_refused_every_kind_of_write(client, admin, viewer):
    """Swept across the whole surface, not sampled: the failure mode of role
    checks is a single endpoint that nobody remembered to guard."""
    rfq = _make_rfq(client, admin["headers"])
    booking_doc_id = 1  # never reached; the guard rejects before any lookup

    attempts = [
        ("post", "/api/rfqs/parse", {"json": {"raw_message": "x", "persist": True}}),
        ("patch", f"/api/rfqs/{rfq['id']}", {"json": {"origin": "Hacked"}}),
        ("post", f"/api/rfqs/{rfq['id']}/rates", {"json": {"partner_name": "X"}}),
        ("post", "/api/customers", {"json": {"company_name": "X"}}),
        ("post", "/api/quotes/start", {"json": {"rfq_id": rfq["id"], "markup_value": 20}}),
        ("post", "/api/quotes/1/approve", {"json": {"approved": True}}),
        ("post", "/api/bookings/from-quote", {"json": {"quote_id": 1}}),
        ("patch", "/api/bookings/1", {"json": {"status": "Delivered"}}),
        ("post", "/api/bookings/1/documents", {"json": {"document_type": "X"}}),
        ("delete", f"/api/bookings/documents/{booking_doc_id}", {}),
        ("post", "/api/issues", {"json": {"issue_type": "X", "description": "y"}}),
        ("post", "/api/mailbox/sync", {}),
        ("put", "/api/mailbox/config", {"json": {"host": "h", "username": "u", "password": "p"}}),
        ("post", "/api/rates/tariff/import", {"files": {"file": ("t.csv", b"a", "text/csv")}}),
        ("post", "/api/auth/users", {"json": {"email": "x@y.com", "password": "abcdefghij"}}),
    ]

    for method, path, kwargs in attempts:
        res = getattr(client, method)(path, headers=viewer["headers"], **kwargs)
        assert res.status_code == 403, f"{method.upper()} {path} → {res.status_code}"
        assert "read-only" in res.json()["detail"].lower()


def test_the_guard_covers_endpoints_nobody_remembered_to_annotate(client, viewer):
    """The policy lives on the router, so an endpoint added tomorrow is guarded
    without anyone thinking about it.

    Proven rather than asserted: this picks a route that genuinely declares no
    role dependency of its own, then shows a viewer is still refused.
    """
    import inspect

    from app.api import bookings
    from app.core.deps import require_org_admin, require_pricing_approval, require_write

    role_guards = {require_write, require_pricing_approval, require_org_admin}
    declared = {
        parameter.default.dependency
        for parameter in inspect.signature(bookings.update_booking).parameters.values()
        if hasattr(parameter.default, "dependency")
    }
    assert not (declared & role_guards), "pick a route that is genuinely unannotated"

    res = client.patch(
        "/api/bookings/1", json={"status": "Delivered"}, headers=viewer["headers"]
    )
    assert res.status_code == 403


def test_a_coordinator_can_do_the_daily_work(client, admin, coordinator):
    rfq = _make_rfq(client, coordinator["headers"])
    assert rfq["id"]

    rate = client.post(
        f"/api/rfqs/{rfq['id']}/rates",
        json={"partner_name": "Carrier A", "cost_amount": 1500, "currency": "USD"},
        headers=coordinator["headers"],
    )
    assert rate.status_code == 201

    review = client.post(
        "/api/quotes/start",
        json={
            "rfq_id": rfq["id"],
            "selected_rate_id": rate.json()["id"],
            "markup_value": 20,
        },
        headers=coordinator["headers"],
    )
    assert review.status_code == 200

    approved = client.post(
        f"/api/quotes/{review.json()['quote_id']}/approve",
        json={"approved": True, "mark_sent": True},
        headers=coordinator["headers"],
    )
    assert approved.status_code == 200


def test_only_administrators_manage_members_and_the_mailbox(client, admin, coordinator):
    """A coordinator runs the desk; they do not hand out access or hold the
    company's mailbox credentials."""
    invited = client.post(
        "/api/auth/users",
        json={"email": f"{uuid.uuid4().hex[:8]}@example.com", "password": "abcdefghij"},
        headers=coordinator["headers"],
    )
    assert invited.status_code == 403
    assert "administrator" in invited.json()["detail"].lower()

    mailbox = client.put(
        "/api/mailbox/config",
        json={"host": "imap.example.com", "username": "u@e.com", "password": "p"},
        headers=coordinator["headers"],
    )
    assert mailbox.status_code == 403


def test_an_admin_cannot_lock_the_organization_out_by_demoting_themselves(client, admin):
    res = client.patch(
        f"/api/auth/users/{admin['user_id']}",
        json={"role": "viewer"},
        headers=admin["headers"],
    )
    assert res.status_code == 400
    assert "your own role" in res.json()["detail"].lower()


def test_a_deactivated_member_cannot_log_in(client, admin, coordinator):
    client.patch(
        f"/api/auth/users/{coordinator['user_id']}",
        json={"is_active": False},
        headers=admin["headers"],
    )
    # An already-issued token stops working too, not just new logins.
    assert client.get("/api/rfqs", headers=coordinator["headers"]).status_code == 401


def test_members_of_another_organization_cannot_be_touched(client, admin):
    other = _signup(client, "Rival Forwarding")

    res = client.patch(
        f"/api/auth/users/{other['user_id']}",
        json={"role": "viewer"},
        headers=admin["headers"],
    )
    assert res.status_code == 404

    members = client.get("/api/auth/users", headers=admin["headers"]).json()
    assert other["user_id"] not in [m["id"] for m in members]


# --------------------------------------------------------------------------
# Ownership
# --------------------------------------------------------------------------


def test_work_is_owned_by_whoever_created_it(client, admin, coordinator):
    mine = _make_rfq(client, coordinator["headers"])
    theirs = _make_rfq(client, admin["headers"])

    assert mine["owner_id"] == coordinator["user_id"]
    assert theirs["owner_id"] == admin["user_id"]

    my_work = client.get("/api/rfqs?mine=true", headers=coordinator["headers"]).json()
    assert [r["id"] for r in my_work] == [mine["id"]]

    team = client.get("/api/rfqs", headers=coordinator["headers"]).json()
    assert {r["id"] for r in team} == {mine["id"], theirs["id"]}


def test_a_quote_is_owned_by_whoever_priced_it(client, admin, coordinator):
    rfq = _make_rfq(client, admin["headers"])
    rate = client.post(
        f"/api/rfqs/{rfq['id']}/rates",
        json={"partner_name": "Carrier A", "cost_amount": 1500},
        headers=admin["headers"],
    ).json()
    review = client.post(
        "/api/quotes/start",
        json={"rfq_id": rfq["id"], "selected_rate_id": rate["id"], "markup_value": 20},
        headers=coordinator["headers"],
    ).json()

    quote = client.get(f"/api/quotes/{review['quote_id']}", headers=admin["headers"]).json()
    assert quote["owner_id"] == coordinator["user_id"]


def test_work_created_by_the_system_has_no_owner(client, admin, mailbox_factory):
    """An RFQ built from an email at 3am has no author, and says so rather than
    crediting whoever happens to look at it first."""
    box = mailbox_factory()
    client.put(
        "/api/mailbox/config",
        json={"host": "imap.example.com", "username": "sales@e.com", "password": "p"},
        headers=admin["headers"],
    )
    box.add_rfq_email()
    client.post("/api/mailbox/sync", headers=admin["headers"])

    unassigned = client.get("/api/rfqs?unassigned=true", headers=admin["headers"]).json()
    assert len(unassigned) == 1
    assert unassigned[0]["owner_id"] is None


def test_work_can_be_reassigned_and_handed_back(client, admin, coordinator):
    rfq = _make_rfq(client, admin["headers"])

    reassigned = client.patch(
        f"/api/rfqs/{rfq['id']}",
        json={"owner_id": coordinator["user_id"]},
        headers=admin["headers"],
    ).json()
    assert reassigned["owner_id"] == coordinator["user_id"]

    back_to_pool = client.patch(
        f"/api/rfqs/{rfq['id']}", json={"owner_id": None}, headers=admin["headers"]
    ).json()
    assert back_to_pool["owner_id"] is None
    assert client.get("/api/rfqs?unassigned=true", headers=admin["headers"]).json()


# --------------------------------------------------------------------------
# Audit trail
# --------------------------------------------------------------------------


def test_who_approved_the_price_is_recorded(client, admin, coordinator):
    """The question the trail exists to answer."""
    rfq = _make_rfq(client, admin["headers"])
    rate = client.post(
        f"/api/rfqs/{rfq['id']}/rates",
        json={"partner_name": "Carrier A", "cost_amount": 1500},
        headers=admin["headers"],
    ).json()
    review = client.post(
        "/api/quotes/start",
        json={"rfq_id": rfq["id"], "selected_rate_id": rate["id"], "markup_value": 20},
        headers=admin["headers"],
    ).json()
    client.post(
        f"/api/quotes/{review['quote_id']}/approve",
        json={"approved": True, "mark_sent": True},
        headers=coordinator["headers"],
    )

    events = client.get(
        f"/api/audit?entity_type=Quote&entity_id={review['quote_id']}",
        headers=admin["headers"],
    ).json()
    # Newest first, so the latest change to each field is the first one seen.
    latest: dict[str, dict] = {}
    for event in events:
        if event["field"]:
            latest.setdefault(event["field"], event)

    # The approval itself: the coordinator moved it to Sent.
    assert latest["status"]["actor"] == coordinator["email"]
    assert latest["status"]["new_value"] == "Sent"

    # The price was set when the quote was priced, and stayed at 1800 through
    # approval — so it is attributed to who set it, not to who approved it.
    assert latest["selling_price"]["new_value"] == "1800.0"
    assert latest["selling_price"]["actor"] == admin["email"]

    # Earlier steps stay attributed to whoever took them: the trail is a
    # history, not a record of the most recent hand on the file.
    started_by = [
        e for e in events if e["field"] == "status" and e["new_value"] == "Pending approval"
    ]
    assert started_by and started_by[0]["actor"] == admin["email"]

    created = [e for e in events if e["action"] == "Created"]
    assert created and created[0]["actor"] == admin["email"]
    assert created[0]["entity_id"] == review["quote_id"]


def test_a_price_edited_at_approval_is_attributed_to_the_approver(client, admin, coordinator):
    """The sharpest version of the question: someone approved a *different*
    number than the one that was proposed. Who, and what was it before?"""
    rfq = _make_rfq(client, admin["headers"])
    rate = client.post(
        f"/api/rfqs/{rfq['id']}/rates",
        json={"partner_name": "Carrier A", "cost_amount": 1500},
        headers=admin["headers"],
    ).json()
    review = client.post(
        "/api/quotes/start",
        json={"rfq_id": rfq["id"], "selected_rate_id": rate["id"], "markup_value": 20},
        headers=admin["headers"],
    ).json()
    assert review["selling_price"] == 1800.0

    client.post(
        f"/api/quotes/{review['quote_id']}/approve",
        json={"approved": True, "mark_sent": True, "selling_price": 1650.0},
        headers=coordinator["headers"],
    )

    events = client.get(
        f"/api/audit?entity_type=Quote&entity_id={review['quote_id']}",
        headers=admin["headers"],
    ).json()
    price_change = next(
        e for e in events if e["field"] == "selling_price" and e["new_value"] == "1650.0"
    )
    assert price_change["actor"] == coordinator["email"]
    assert price_change["old_value"] == "1800.0"
    assert "1800.0 → 1650.0" in price_change["summary"]


def test_the_trail_records_the_previous_value_not_just_the_new_one(client, admin):
    rfq = _make_rfq(client, admin["headers"])
    client.patch(
        f"/api/rfqs/{rfq['id']}", json={"status": "Ready for pricing"}, headers=admin["headers"]
    )
    client.patch(
        f"/api/rfqs/{rfq['id']}", json={"status": "Cancelled"}, headers=admin["headers"]
    )

    events = client.get(
        f"/api/audit?entity_type=RFQ&entity_id={rfq['id']}", headers=admin["headers"]
    ).json()
    latest = events[0]
    assert latest["old_value"] == "Ready for pricing"
    assert latest["new_value"] == "Cancelled"
    assert "Ready for pricing → Cancelled" in latest["summary"]


def test_role_changes_are_recorded(client, admin, coordinator):
    client.patch(
        f"/api/auth/users/{coordinator['user_id']}",
        json={"role": "viewer"},
        headers=admin["headers"],
    )

    events = client.get(
        f"/api/audit?entity_type=User&entity_id={coordinator['user_id']}",
        headers=admin["headers"],
    ).json()
    role_change = next(e for e in events if e["field"] == "role")
    assert role_change["actor"] == admin["email"]
    assert role_change["old_value"] == "coordinator"
    assert role_change["new_value"] == "viewer"


def test_noise_is_not_recorded(client, admin):
    """A log of everything is read by nobody. A corrected commodity description
    is not a decision."""
    rfq = _make_rfq(client, admin["headers"])
    before = len(client.get("/api/audit", headers=admin["headers"]).json())

    client.patch(
        f"/api/rfqs/{rfq['id']}",
        json={"commodity": "Plastic goods", "gross_weight": "12500 kg"},
        headers=admin["headers"],
    )

    after = client.get("/api/audit", headers=admin["headers"]).json()
    assert len(after) == before


def test_a_rolled_back_change_leaves_no_audit_row(client, admin):
    """An audit row for something that never happened is worse than none."""
    from sqlalchemy import select

    from app.core.db import SessionLocal
    from app.core.tenancy import acting_as, organization_scope
    from app.models.audit import AuditEvent
    from app.models.enums import RFQStatus
    from app.models.rfq import RFQ

    rfq = _make_rfq(client, admin["headers"])

    db = SessionLocal()
    try:
        with organization_scope(admin["org_id"], db):
            with acting_as(db, admin["user_id"], admin["email"]):
                row = db.get(RFQ, rfq["id"])
                row.status = RFQStatus.CANCELLED
                db.flush()
                db.rollback()

            events = db.execute(
                select(AuditEvent).where(
                    AuditEvent.entity_type == "RFQ", AuditEvent.entity_id == rfq["id"]
                )
            ).scalars().all()
            assert events == []
    finally:
        db.close()


def test_background_work_is_attributed_to_the_system_not_a_person(client, admin):
    from sqlalchemy import select

    from app.core.db import SessionLocal
    from app.core.tenancy import organization_scope
    from app.models.audit import AuditEvent
    from app.models.enums import RFQStatus
    from app.models.rfq import RFQ

    rfq = _make_rfq(client, admin["headers"])

    db = SessionLocal()
    try:
        with organization_scope(admin["org_id"], db):  # no acting_as: a worker
            db.get(RFQ, rfq["id"]).status = RFQStatus.CANCELLED
            db.commit()
            event = db.execute(
                select(AuditEvent)
                .where(AuditEvent.entity_id == rfq["id"], AuditEvent.field == "status")
                .order_by(AuditEvent.id.desc())
            ).scalars().first()
            assert event is not None
            assert event.actor == "system"
            assert event.user_id is None
    finally:
        db.close()


def test_the_trail_survives_the_person_who_made_the_change(client, admin, coordinator):
    """Deleting a member must not erase what they approved."""
    from sqlalchemy import select

    from app.core.db import SessionLocal
    from app.core.tenancy import bypass_tenant_isolation, organization_scope
    from app.models.audit import AuditEvent
    from app.models.user import User

    rfq = _make_rfq(client, coordinator["headers"])
    client.patch(
        f"/api/rfqs/{rfq['id']}", json={"status": "Cancelled"}, headers=coordinator["headers"]
    )

    db = SessionLocal()
    try:
        with bypass_tenant_isolation(db):
            db.delete(db.get(User, coordinator["user_id"]))
            db.commit()
        with organization_scope(admin["org_id"], db):
            event = db.execute(
                select(AuditEvent).where(
                    AuditEvent.entity_id == rfq["id"], AuditEvent.field == "status"
                )
            ).scalars().first()
            assert event is not None
            assert event.actor == coordinator["email"]
            assert event.user_id is None  # the account is gone; the record is not
    finally:
        db.close()


def test_the_audit_trail_is_never_visible_across_organizations(client, admin):
    rfq = _make_rfq(client, admin["headers"])
    client.patch(
        f"/api/rfqs/{rfq['id']}", json={"status": "Cancelled"}, headers=admin["headers"]
    )
    assert client.get("/api/audit", headers=admin["headers"]).json()

    other = _signup(client, "Rival Forwarding")
    assert client.get("/api/audit", headers=other["headers"]).json() == []
    assert (
        client.get(
            f"/api/audit?entity_type=RFQ&entity_id={rfq['id']}", headers=other["headers"]
        ).json()
        == []
    )
