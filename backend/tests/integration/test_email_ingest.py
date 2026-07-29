"""Automatic email intake, end to end, with a fake mailbox.

This is the feature the product's whole value claim rests on: an RFQ that lands
in the company inbox must become a structured, parsed RFQ without anyone opening
an email client. The guarantees asserted here are the ones a buyer is actually
trusting:

* nothing is created twice, however often a message is re-fetched;
* a partner's rate reply lands on the right RFQ;
* a customer's reply stops the automated follow-up cadence;
* a message that fails processing is kept and marked, never lost;
* one organization can never see another's mail or mailbox credentials;
* the mailbox password is never returned by the API and never stored in clear.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage as PyEmailMessage

import pytest

from tests.integration.conftest import requires_integration

pytestmark = requires_integration


# --------------------------------------------------------------------------
# Fake mailbox
# --------------------------------------------------------------------------


class FakeMailbox:
    """An in-memory IMAP stand-in.

    It mirrors the two behaviours that matter for correctness: UID watermarking
    (only messages newer than `since_uid` come back) and read-only access
    (fetching never mutates the stored messages).
    """

    def __init__(self) -> None:
        self.messages: list[tuple[int, bytes]] = []
        self._next_uid = 1
        self.fail_with: Exception | None = None
        self.fetch_calls = 0

    def add(self, raw: bytes) -> int:
        uid = self._next_uid
        self._next_uid += 1
        self.messages.append((uid, raw))
        return uid

    def client(self, _config):
        mailbox = self

        from app.email.base import EmailClient
        from app.email.imap_client import parse_message

        class _Client(EmailClient):
            def verify(self) -> None:
                if mailbox.fail_with is not None:
                    raise mailbox.fail_with

            def fetch_new(self, *, since_uid: int | None, limit: int):
                mailbox.fetch_calls += 1
                if mailbox.fail_with is not None:
                    raise mailbox.fail_with
                selected = [
                    (uid, raw)
                    for uid, raw in mailbox.messages
                    if since_uid is None or uid > since_uid
                ]
                return [parse_message(raw, uid=uid) for uid, raw in selected[:limit]]

        return _Client()


def build_email(
    *,
    subject: str,
    body: str,
    sender: str = "Ali Rezaei <ali@acme-trading.com>",
    message_id: str | None = None,
    references: str | None = None,
    received_at: datetime | None = None,
    attachments: list[tuple[str, str, bytes]] | None = None,
) -> bytes:
    message = PyEmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = "sales@forwarder.example"
    message["Message-ID"] = message_id or f"<{uuid.uuid4().hex}@acme-trading.com>"
    if references:
        message["References"] = references
    stamp = received_at or datetime.now(timezone.utc)
    message["Date"] = stamp.strftime("%a, %d %b %Y %H:%M:%S %z")
    message.set_content(body)
    for filename, content_type, payload in attachments or []:
        maintype, subtype = content_type.split("/", 1)
        message.add_attachment(
            payload, maintype=maintype, subtype=subtype, filename=filename
        )
    return message.as_bytes()


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


def _signup(client, company: str) -> dict:
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
    }


@pytest.fixture
def mailbox():
    """Install a fake transport for the duration of one test."""
    from app.email import set_email_client_factory

    box = FakeMailbox()
    set_email_client_factory(box.client)
    yield box
    set_email_client_factory(None)


@pytest.fixture
def org(client):
    return _signup(client, "Mailbox Co")


@pytest.fixture
def configured(client, org):
    """An organization with a stored (fake) mailbox connection."""
    res = client.put(
        "/api/mailbox/config",
        json={
            "host": "imap.example.com",
            "port": 993,
            "username": "sales@forwarder.example",
            "password": "app-password-123",
            "folder": "INBOX",
        },
        headers=org["headers"],
    )
    assert res.status_code == 200, res.text
    return {**org, "config": res.json()}


def _sync(client, headers) -> dict:
    res = client.post("/api/mailbox/sync", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


# --------------------------------------------------------------------------
# Credentials
# --------------------------------------------------------------------------


def test_password_is_never_returned_by_the_api(client, configured):
    body = configured["config"]
    assert "password" not in body
    assert "encrypted_password" not in body

    fetched = client.get("/api/mailbox/config", headers=configured["headers"]).json()
    assert "app-password-123" not in str(fetched)


def test_password_is_encrypted_at_rest(configured):
    """A database dump must not reveal the customer's mail account."""
    from sqlalchemy import select

    from app.core.db import SessionLocal
    from app.core.tenancy import organization_scope
    from app.models.mailbox import MailboxConfig

    db = SessionLocal()
    try:
        with organization_scope(configured["org_id"], db):
            config = db.execute(select(MailboxConfig)).scalars().one()
            assert "app-password-123" not in config.encrypted_password
            assert config.get_password() == "app-password-123"
    finally:
        db.close()


# --------------------------------------------------------------------------
# Core ingestion
# --------------------------------------------------------------------------


def test_rfq_email_becomes_a_structured_rfq(client, configured, mailbox):
    """The core promise: no human opens the inbox, and the RFQ is ready."""
    asked_at = datetime.now(timezone.utc) - timedelta(hours=3)
    mailbox.add(
        build_email(
            subject="[RFQ] Rate request Shanghai to Jebel Ali",
            body="Hi, please quote 1x40HC plastic goods, 12500 kg, ready 15 July.",
            received_at=asked_at,
        )
    )

    result = _sync(client, configured["headers"])
    assert result["fetched"] == 1
    assert result["rfqs_created"] == 1

    rfqs = client.get("/api/rfqs", headers=configured["headers"]).json()
    assert len(rfqs) == 1
    rfq = rfqs[0]
    assert rfq["origin"] == "Shanghai"
    assert rfq["destination"] == "Jebel Ali"
    assert rfq["reference"].startswith("RFQ-")

    messages = client.get("/api/mailbox/messages", headers=configured["headers"]).json()
    assert len(messages) == 1
    assert messages[0]["classification"] == "New RFQ"
    assert messages[0]["status"] == "Processed"
    assert messages[0]["rfq_id"] == rfq["id"]


def test_received_at_is_the_customer_clock_not_the_processing_clock(
    client, configured, mailbox
):
    """Response time is measured from when the customer asked. If we stamped
    processing time instead, every reported response time would be flattering
    and meaningless."""
    from sqlalchemy import select

    from app.core.db import SessionLocal
    from app.core.tenancy import organization_scope
    from app.models.rfq import RFQ

    asked_at = datetime.now(timezone.utc) - timedelta(days=2)
    mailbox.add(
        build_email(
            subject="[RFQ] Please quote",
            body="Shanghai to Jebel Ali, 40HC.",
            received_at=asked_at,
        )
    )
    _sync(client, configured["headers"])

    db = SessionLocal()
    try:
        with organization_scope(configured["org_id"], db):
            rfq = db.execute(select(RFQ)).scalars().one()
            assert rfq.received_at is not None
            drift = abs((rfq.received_at - asked_at).total_seconds())
            assert drift < 60, f"received_at drifted by {drift}s from the email date"
            assert rfq.received_at < rfq.created_at
    finally:
        db.close()


def test_ingestion_is_idempotent(client, configured, mailbox):
    """Re-polling must never duplicate a customer's request."""
    raw = build_email(
        subject="[RFQ] Rate request",
        body="Shanghai to Jebel Ali, 40HC.",
        message_id="<stable-id@acme-trading.com>",
    )
    mailbox.add(raw)

    first = _sync(client, configured["headers"])
    assert first["rfqs_created"] == 1

    # Same message re-appears (server re-delivery, watermark reset, retry).
    mailbox.messages.clear()
    mailbox._next_uid = 1
    mailbox.add(raw)
    from sqlalchemy import update

    from app.core.db import SessionLocal
    from app.models.mailbox import MailboxConfig

    db = SessionLocal()
    try:
        db.execute(
            update(MailboxConfig)
            .where(MailboxConfig.org_id == configured["org_id"])
            .values(last_seen_uid=None)
        )
        db.commit()
    finally:
        db.close()

    second = _sync(client, configured["headers"])
    assert second["fetched"] == 1
    assert second["skipped_duplicates"] == 1
    assert second["rfqs_created"] == 0

    assert len(client.get("/api/rfqs", headers=configured["headers"]).json()) == 1
    assert len(
        client.get("/api/mailbox/messages", headers=configured["headers"]).json()
    ) == 1


def test_watermark_advances_so_messages_are_read_once(client, configured, mailbox):
    mailbox.add(build_email(subject="[RFQ] One", body="Shanghai to Dubai 40HC."))
    _sync(client, configured["headers"])

    config = client.get("/api/mailbox/config", headers=configured["headers"]).json()
    assert config["last_seen_uid"] == 1
    assert config["last_polled_at"] is not None

    # Nothing new: a second poll fetches nothing at all.
    assert _sync(client, configured["headers"])["fetched"] == 0

    mailbox.add(build_email(subject="[RFQ] Two", body="Ningbo to Dubai 20GP."))
    assert _sync(client, configured["headers"])["fetched"] == 1
    assert (
        client.get("/api/mailbox/config", headers=configured["headers"]).json()[
            "last_seen_uid"
        ]
        == 2
    )


def test_irrelevant_mail_is_ignored_not_turned_into_an_rfq(client, configured, mailbox):
    """A newsletter must not create work for the coordinator."""
    mailbox.add(
        build_email(
            subject="[SPAM] Container market weekly newsletter",
            body="Unsubscribe here.",
            sender="news@marketing.example",
        )
    )

    result = _sync(client, configured["headers"])
    assert result["ignored"] == 1
    assert result["rfqs_created"] == 0
    assert client.get("/api/rfqs", headers=configured["headers"]).json() == []

    message = client.get("/api/mailbox/messages", headers=configured["headers"]).json()[0]
    assert message["status"] == "Ignored"
    # Still stored with a reason, so a wrong call is visible and correctable.
    assert message["classification_reason"]


def test_partner_rate_reply_attaches_to_the_right_rfq(client, configured, mailbox):
    """A rate quote from a carrier is useless if it lands on the wrong shipment."""
    root_id = "<thread-root@forwarder.example>"
    mailbox.add(
        build_email(
            subject="[RFQ] Rate request Shanghai to Jebel Ali",
            body="Please quote 40HC.",
            message_id=root_id,
        )
    )
    _sync(client, configured["headers"])
    rfq = client.get("/api/rfqs", headers=configured["headers"]).json()[0]

    mailbox.add(
        build_email(
            subject="[RATE] Re: Rate request Shanghai to Jebel Ali",
            body="Our rate is USD 1500 all-in, transit 22 days.",
            sender="rates@carrier.example",
            references=root_id,
        )
    )
    result = _sync(client, configured["headers"])
    assert result["rate_replies_linked"] == 1

    messages = client.get("/api/mailbox/messages", headers=configured["headers"]).json()
    reply = next(m for m in messages if m["classification"] == "Partner rate reply")
    assert reply["rfq_id"] == rfq["id"]


def test_rate_reply_links_by_quoted_reference_without_a_thread(
    client, configured, mailbox
):
    """Partners often reply from a different address with a fresh thread; the
    RFQ reference in the body is then the only link."""
    mailbox.add(
        build_email(subject="[RFQ] Rate request", body="Shanghai to Jebel Ali 40HC.")
    )
    _sync(client, configured["headers"])
    rfq = client.get("/api/rfqs", headers=configured["headers"]).json()[0]

    mailbox.add(
        build_email(
            subject="[RATE] Quotation",
            body=f"Regarding your enquiry {rfq['reference']}: USD 1500 all-in.",
            sender="pricing@another-carrier.example",
        )
    )
    _sync(client, configured["headers"])

    messages = client.get("/api/mailbox/messages", headers=configured["headers"]).json()
    reply = next(m for m in messages if m["classification"] == "Partner rate reply")
    assert reply["rfq_id"] == rfq["id"]


def test_customer_reply_stops_the_follow_up_cadence(client, configured, mailbox):
    """Chasing a customer who already answered is the fastest way to make an
    automated tool feel robotic — and to lose the deal."""
    headers = configured["headers"]
    customer = client.post(
        "/api/customers",
        json={"company_name": "Acme Trading", "email": "ali@acme-trading.com"},
        headers=headers,
    ).json()

    root_id = "<quote-thread@forwarder.example>"
    mailbox.add(
        build_email(
            subject="[RFQ] Rate request Shanghai to Jebel Ali",
            body="Please quote 40HC.",
            message_id=root_id,
        )
    )
    _sync(client, headers)
    rfq = client.get("/api/rfqs", headers=headers).json()[0]
    client.patch(
        f"/api/rfqs/{rfq['id']}", json={"customer_id": customer["id"]}, headers=headers
    )

    rate = client.post(
        f"/api/rfqs/{rfq['id']}/rates",
        json={"partner_name": "Carrier A", "cost_amount": 1500, "currency": "USD"},
        headers=headers,
    ).json()
    review = client.post(
        "/api/quotes/start",
        json={"rfq_id": rfq["id"], "selected_rate_id": rate["id"], "markup_value": 20},
        headers=headers,
    ).json()
    quote = client.post(
        f"/api/quotes/{review['quote_id']}/approve",
        json={"approved": True, "mark_sent": True},
        headers=headers,
    ).json()
    assert quote["status"] == "Sent"
    assert quote["next_follow_up_date"] is not None

    pending = client.get("/api/follow-ups", headers=headers).json()
    assert any(f["quote_id"] == quote["id"] for f in pending)

    mailbox.add(
        build_email(
            subject="[REPLY] Re: our quotation",
            body="Thanks, the price is acceptable. Please proceed.",
            references=root_id,
        )
    )
    result = _sync(client, headers)
    assert result["customer_replies_linked"] == 1

    updated = client.get(f"/api/quotes/{quote['id']}", headers=headers).json()
    assert updated["next_follow_up_date"] is None

    follow_ups = client.get("/api/follow-ups", headers=headers).json()
    mine = [f for f in follow_ups if f["quote_id"] == quote["id"]]
    assert mine, "follow-up disappeared instead of being closed"
    assert all(f["status"] == "Replied" for f in mine)

    message = next(
        m
        for m in client.get("/api/mailbox/messages", headers=headers).json()
        if m["classification"] == "Customer reply"
    )
    assert message["quote_id"] == quote["id"]


def test_attachments_are_stored_and_downloadable(client, configured, mailbox):
    """RFQs routinely carry the packing list attached; if it were dropped the
    coordinator would have to open the mail client anyway."""
    mailbox.add(
        build_email(
            subject="[RFQ] Rate request with docs",
            body="Shanghai to Jebel Ali, details attached.",
            attachments=[
                ("packing-list.pdf", "application/pdf", b"%PDF-1.4 packing list"),
                ("بارنامه.txt", "text/plain", "شرح کالا".encode()),
            ],
        )
    )
    _sync(client, configured["headers"])

    message = client.get("/api/mailbox/messages", headers=configured["headers"]).json()[0]
    assert [a["filename"] for a in message["attachments"]] == [
        "packing-list.pdf",
        "بارنامه.txt",
    ]

    res = client.get(
        f"/api/mailbox/messages/{message['id']}/attachments/0",
        headers=configured["headers"],
    )
    assert res.status_code == 200
    assert res.content == b"%PDF-1.4 packing list"
    assert "packing-list.pdf" in res.headers["content-disposition"]

    # A non-ASCII name must not break the download header.
    res = client.get(
        f"/api/mailbox/messages/{message['id']}/attachments/1",
        headers=configured["headers"],
    )
    assert res.status_code == 200
    assert res.content.decode() == "شرح کالا"

    assert (
        client.get(
            f"/api/mailbox/messages/{message['id']}/attachments/9",
            headers=configured["headers"],
        ).status_code
        == 404
    )


def test_attachments_are_not_reachable_from_another_tenant(client, configured, mailbox):
    mailbox.add(
        build_email(
            subject="[RFQ] Confidential",
            body="Shanghai to Dubai.",
            attachments=[("contract.pdf", "application/pdf", b"secret terms")],
        )
    )
    _sync(client, configured["headers"])
    message = client.get("/api/mailbox/messages", headers=configured["headers"]).json()[0]

    other = _signup(client, "Rival Forwarding")
    res = client.get(
        f"/api/mailbox/messages/{message['id']}/attachments/0", headers=other["headers"]
    )
    assert res.status_code == 404


# --------------------------------------------------------------------------
# Failure handling
# --------------------------------------------------------------------------


def test_a_message_that_fails_processing_is_kept_and_marked(client, configured, mailbox):
    """A parsing failure must never silently swallow a customer's request."""
    from app.llm.factory import get_llm, set_llm

    working = get_llm()

    class BrokenLLM:
        provider = "fake"
        model = "broken"

        def complete(self, **_kwargs) -> str:
            raise RuntimeError("provider unavailable")

        def complete_structured(self, **_kwargs) -> dict:
            raise RuntimeError("provider unavailable")

    mailbox.add(build_email(subject="[RFQ] Rate request", body="Shanghai to Dubai."))
    set_llm(BrokenLLM())
    try:
        result = _sync(client, configured["headers"])
    finally:
        set_llm(working)

    assert result["failed"] == 1
    assert result["rfqs_created"] == 0

    message = client.get("/api/mailbox/messages", headers=configured["headers"]).json()[0]
    assert message["status"] == "Failed"
    assert "provider unavailable" in message["error"]
    # The body is preserved, so the RFQ can still be recovered by hand.
    assert "Shanghai" in message["body"]


def test_unreachable_mailbox_reports_the_error_instead_of_failing_silently(
    client, configured, mailbox
):
    from app.email import EmailError

    mailbox.fail_with = EmailError("Could not open mailbox: authentication failed")

    res = client.post("/api/mailbox/sync", headers=configured["headers"])
    assert res.status_code == 502
    assert "authentication failed" in res.json()["detail"]

    config = client.get("/api/mailbox/config", headers=configured["headers"]).json()
    assert config["last_error"] is not None
    assert "authentication failed" in config["last_error"]

    test_result = client.post("/api/mailbox/test", headers=configured["headers"]).json()
    assert test_result["ok"] is False


def test_successful_poll_clears_a_previous_error(client, configured, mailbox):
    from app.email import EmailError

    mailbox.fail_with = EmailError("temporary outage")
    client.post("/api/mailbox/sync", headers=configured["headers"])
    assert (
        client.get("/api/mailbox/config", headers=configured["headers"]).json()[
            "last_error"
        ]
        is not None
    )

    mailbox.fail_with = None
    _sync(client, configured["headers"])
    assert (
        client.get("/api/mailbox/config", headers=configured["headers"]).json()[
            "last_error"
        ]
        is None
    )


def test_disabled_mailbox_is_not_polled(client, configured, mailbox):
    client.patch(
        "/api/mailbox/config", json={"is_enabled": False}, headers=configured["headers"]
    )
    mailbox.add(build_email(subject="[RFQ] Rate request", body="Shanghai to Dubai."))

    res = client.post("/api/mailbox/sync", headers=configured["headers"])
    assert res.status_code == 400
    assert mailbox.fetch_calls == 0


# --------------------------------------------------------------------------
# Tenant isolation
# --------------------------------------------------------------------------


def test_one_tenant_cannot_see_another_tenants_mail(client, configured, mailbox):
    mailbox.add(
        build_email(
            subject="[RFQ] Confidential shipment for tenant A",
            body="Shanghai to Jebel Ali, 40HC.",
        )
    )
    _sync(client, configured["headers"])
    a_messages = client.get(
        "/api/mailbox/messages", headers=configured["headers"]
    ).json()
    assert len(a_messages) == 1

    other = _signup(client, "Rival Forwarding")
    assert client.get("/api/mailbox/messages", headers=other["headers"]).json() == []
    assert client.get("/api/mailbox/config", headers=other["headers"]).json() is None
    assert client.get("/api/rfqs", headers=other["headers"]).json() == []

    stolen = client.get(
        f"/api/mailbox/messages/{a_messages[0]['id']}", headers=other["headers"]
    )
    assert stolen.status_code == 404

    # And the other tenant cannot delete or overwrite A's mailbox connection.
    assert client.delete("/api/mailbox/config", headers=other["headers"]).status_code == 404
    assert (
        client.get("/api/mailbox/config", headers=configured["headers"]).json()
        is not None
    )


def test_the_worker_polls_each_tenant_in_its_own_scope(client, mailbox):
    """The Celery job has no request context; if it did not scope per tenant it
    would either see nothing or mix organizations together."""
    from app.workers.tasks import poll_mailboxes

    tenants = []
    for name in ("Worker Alpha", "Worker Beta"):
        tenant = _signup(client, name)
        client.put(
            "/api/mailbox/config",
            json={
                "host": "imap.example.com",
                "username": f"{name.lower().replace(' ', '.')}@example.com",
                "password": "app-password-123",
            },
            headers=tenant["headers"],
        )
        tenants.append(tenant)

    mailbox.add(
        build_email(subject="[RFQ] Rate request", body="Shanghai to Jebel Ali 40HC.")
    )

    totals = poll_mailboxes()
    assert totals["mailboxes"] >= 2
    assert totals["failed"] == 0

    for tenant in tenants:
        rfqs = client.get("/api/rfqs", headers=tenant["headers"]).json()
        assert len(rfqs) == 1, f"{tenant['org_id']} got {len(rfqs)} RFQs"
        messages = client.get("/api/mailbox/messages", headers=tenant["headers"]).json()
        assert len(messages) == 1
