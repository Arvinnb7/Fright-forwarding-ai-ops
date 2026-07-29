"""Document uploads — the shipment file has to hold the actual paperwork.

Until now `Document` recorded a checklist only, with a `file_path` column that
nothing ever wrote. A job file that cannot hold the bill of lading is not a job
file, so these tests cover storing, serving and isolating the real bytes.
"""
from __future__ import annotations

import uuid

import pytest

from tests.integration.conftest import requires_integration

pytestmark = requires_integration


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
    return {"headers": {"Authorization": f"Bearer {body['access_token']}"}}


def _booking_with_document(client, headers) -> dict:
    rfq = client.post(
        "/api/rfqs/parse",
        json={"raw_message": "Quote 40HC Shanghai to Jebel Ali", "persist": True},
        headers=headers,
    ).json()["rfq"]
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
    booking = client.post(
        "/api/bookings/from-quote", json={"quote_id": quote["id"]}, headers=headers
    ).json()
    document = client.post(
        f"/api/bookings/{booking['id']}/documents",
        json={"document_type": "Bill of Lading"},
        headers=headers,
    ).json()
    return {"booking": booking, "document": document}


@pytest.fixture(scope="module")
def org(client):
    return _signup(client, "Docs Forwarding")


@pytest.fixture
def document(client, org):
    return _booking_with_document(client, org["headers"])["document"]


def test_upload_then_download_round_trip(client, org, document):
    content = b"%PDF-1.4 bill of lading"
    res = client.post(
        f"/api/bookings/documents/{document['id']}/file",
        files={"file": ("bl.pdf", content, "application/pdf")},
        headers=org["headers"],
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["file_name"] == "bl.pdf"
    assert body["file_size_bytes"] == len(content)
    assert body["has_file"] is True
    # The checklist must agree with reality once the file exists.
    assert body["status"] == "Received"

    download = client.get(
        f"/api/bookings/documents/{document['id']}/file", headers=org["headers"]
    )
    assert download.status_code == 200
    assert download.content == content
    assert download.headers["content-type"].startswith("application/pdf")
    assert download.headers["x-content-type-options"] == "nosniff"


def test_document_without_a_file_reports_it(client, org, document):
    assert document["has_file"] is False
    res = client.get(
        f"/api/bookings/documents/{document['id']}/file", headers=org["headers"]
    )
    assert res.status_code == 404


def test_reupload_replaces_the_previous_file(client, org, document):
    url = f"/api/bookings/documents/{document['id']}/file"
    client.post(
        url, files={"file": ("v1.pdf", b"version one", "application/pdf")},
        headers=org["headers"],
    )
    client.post(
        url, files={"file": ("v2.pdf", b"version two", "application/pdf")},
        headers=org["headers"],
    )

    download = client.get(url, headers=org["headers"])
    assert download.content == b"version two"
    assert "v2.pdf" in download.headers["content-disposition"]


def test_empty_and_oversized_uploads_are_rejected(client, org, document):
    from app.core.config import settings

    url = f"/api/bookings/documents/{document['id']}/file"
    empty = client.post(
        url, files={"file": ("empty.pdf", b"", "application/pdf")}, headers=org["headers"]
    )
    assert empty.status_code == 400

    oversized = b"x" * (settings.max_upload_mb * 1024 * 1024 + 1)
    too_big = client.post(
        url,
        files={"file": ("huge.pdf", oversized, "application/pdf")},
        headers=org["headers"],
    )
    assert too_big.status_code == 413

    # Neither attempt left the document in a half-updated state.
    assert (
        client.get(url, headers=org["headers"]).status_code == 404
    ), "a rejected upload must not become the document's file"


def test_another_tenant_cannot_read_or_replace_the_file(client, org, document):
    client.post(
        f"/api/bookings/documents/{document['id']}/file",
        files={"file": ("contract.pdf", b"confidential terms", "application/pdf")},
        headers=org["headers"],
    )

    intruder = _signup(client, "Rival Forwarding")
    assert (
        client.get(
            f"/api/bookings/documents/{document['id']}/file", headers=intruder["headers"]
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/bookings/documents/{document['id']}/file",
            files={"file": ("evil.pdf", b"overwritten", "application/pdf")},
            headers=intruder["headers"],
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/bookings/documents/{document['id']}", headers=intruder["headers"]
        ).status_code
        == 404
    )

    # Untouched for the owner.
    still_there = client.get(
        f"/api/bookings/documents/{document['id']}/file", headers=org["headers"]
    )
    assert still_there.content == b"confidential terms"


def test_deleting_the_document_removes_the_stored_file(client, org, document):
    from app.services.storage import StorageError, read_bytes

    from app.core.db import SessionLocal
    from app.core.tenancy import bypass_tenant_isolation
    from app.models.document import Document

    client.post(
        f"/api/bookings/documents/{document['id']}/file",
        files={"file": ("temp.pdf", b"to be deleted", "application/pdf")},
        headers=org["headers"],
    )

    db = SessionLocal()
    try:
        with bypass_tenant_isolation(db):
            row = db.get(Document, document["id"])
            path, org_id = row.file_path, row.org_id
    finally:
        db.close()
    assert read_bytes(path, org_id) == b"to be deleted"

    assert (
        client.delete(
            f"/api/bookings/documents/{document['id']}", headers=org["headers"]
        ).status_code
        == 204
    )
    with pytest.raises(StorageError):
        read_bytes(path, org_id)
