"""MIME parsing — the layer every ingested email passes through first.

Real mailboxes contain encoded headers, HTML-only bodies, forwarded chains and
attachments; a parsing bug here silently loses customer requests, so this is
tested without any network or database.
"""
from __future__ import annotations

from email.message import EmailMessage as PyEmailMessage

from app.email.imap_client import MAX_BODY_CHARS, parse_message


def _raw(
    *,
    subject: str = "Quote request",
    sender: str = "Ali Rezaei <ali@acme-trading.com>",
    to: str = "sales@forwarder.com",
    body: str = "Need a rate Shanghai to Jebel Ali.",
    html: str | None = None,
    date: str | None = "Tue, 14 Jul 2026 09:30:00 +0000",
    message_id: str | None = "<msg-1@acme-trading.com>",
    references: str | None = None,
    in_reply_to: str | None = None,
    attachments: list[tuple[str, str, bytes]] | None = None,
) -> bytes:
    message = PyEmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = to
    if date:
        message["Date"] = date
    if message_id:
        message["Message-ID"] = message_id
    if references:
        message["References"] = references
    if in_reply_to:
        message["In-Reply-To"] = in_reply_to

    if html is not None and not body:
        message.set_content(html, subtype="html")
    else:
        message.set_content(body)
        if html is not None:
            message.add_alternative(html, subtype="html")

    for filename, content_type, payload in attachments or []:
        maintype, subtype = content_type.split("/", 1)
        message.add_attachment(
            payload, maintype=maintype, subtype=subtype, filename=filename
        )
    return message.as_bytes()


def test_parses_core_fields():
    parsed = parse_message(_raw(), uid=42)

    assert parsed.message_id == "<msg-1@acme-trading.com>"
    assert parsed.uid == 42
    assert parsed.from_address == "ali@acme-trading.com"
    assert parsed.from_name == "Ali Rezaei"
    assert parsed.to_address == "sales@forwarder.com"
    assert parsed.subject == "Quote request"
    assert "Shanghai" in parsed.body
    assert parsed.received_at is not None
    assert parsed.received_at.year == 2026


def test_addresses_are_lowercased_for_matching():
    """Customer matching compares addresses directly, so case must not matter."""
    parsed = parse_message(_raw(sender="Ali <ALI@ACME-Trading.COM>"))

    assert parsed.from_address == "ali@acme-trading.com"


def test_encoded_headers_are_decoded():
    subject = "=?utf-8?B?2K/Ysdiu2YjYp9iz2Kog2YbYsdiu?="  # Persian "rate request"
    parsed = parse_message(_raw(subject=subject))

    assert parsed.subject is not None
    assert "=?utf-8?" not in parsed.subject


def test_thread_key_prefers_references_root():
    """A partner's rate reply must resolve to the RFQ's original thread."""
    parsed = parse_message(
        _raw(
            message_id="<reply-9@partner.com>",
            references="<root-1@forwarder.com> <mid-2@partner.com>",
            in_reply_to="<mid-2@partner.com>",
        )
    )

    assert parsed.thread_key == "<root-1@forwarder.com>"


def test_thread_key_falls_back_to_in_reply_to_then_own_id():
    reply = parse_message(_raw(message_id="<r@x.com>", in_reply_to="<root@x.com>"))
    original = parse_message(_raw(message_id="<root@x.com>"))

    assert reply.thread_key == "<root@x.com>"
    assert original.thread_key == "<root@x.com>"


def test_html_only_body_is_stripped_to_text():
    parsed = parse_message(
        _raw(body="", html="<html><body><p>Rate <b>Shanghai</b> to Dubai</p></body></html>")
    )

    assert "<" not in parsed.body
    assert "Shanghai" in parsed.body


def test_plain_text_wins_over_html_alternative():
    parsed = parse_message(
        _raw(body="PLAIN VERSION", html="<p>HTML VERSION</p>")
    )

    assert "PLAIN VERSION" in parsed.body
    assert "HTML VERSION" not in parsed.body


def test_oversized_body_is_truncated():
    parsed = parse_message(_raw(body="x" * (MAX_BODY_CHARS + 5_000)))

    assert len(parsed.body) == MAX_BODY_CHARS


def test_attachments_are_captured_with_metadata():
    parsed = parse_message(
        _raw(
            attachments=[
                ("packing-list.pdf", "application/pdf", b"%PDF-1.4 fake"),
                ("photo.jpg", "image/jpeg", b"\xff\xd8\xff fake"),
            ]
        )
    )

    assert [a.filename for a in parsed.attachments] == ["packing-list.pdf", "photo.jpg"]
    assert parsed.attachments[0].content_type == "application/pdf"
    assert parsed.attachments[0].size_bytes == len(b"%PDF-1.4 fake")
    # Metadata is what reaches the database; the bytes stay out of the row.
    assert parsed.attachment_metadata()[0] == {
        "filename": "packing-list.pdf",
        "content_type": "application/pdf",
        "size_bytes": len(b"%PDF-1.4 fake"),
    }


def test_attachment_filenames_do_not_become_the_body():
    parsed = parse_message(
        _raw(body="Body text", attachments=[("rates.txt", "text/plain", b"IGNORE ME")])
    )

    assert "IGNORE ME" not in parsed.body


def test_message_without_id_falls_back_to_uid():
    """Some servers omit Message-ID; ingestion still needs a stable key."""
    parsed = parse_message(_raw(message_id=None), uid=77)

    assert parsed.message_id == "uid-77"


def test_malformed_date_does_not_raise():
    parsed = parse_message(_raw(date="not a date"))

    assert parsed.received_at is None
