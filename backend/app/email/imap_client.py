"""IMAP implementation of the mail-fetching interface (read-only)."""
from __future__ import annotations

import email
import imaplib
from email.header import decode_header, make_header
from email.message import Message
from email.utils import parseaddr, parsedate_to_datetime

from app.core.logging import get_logger
from app.email.base import EmailClient, EmailError, FetchedAttachment, FetchedEmail

log = get_logger("email.imap")

# Guard rails: a single monster message must not blow up memory or the context
# window; bodies are truncated and attachments are captured as metadata plus a
# bounded amount of content.
MAX_BODY_CHARS = 20_000
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024


def _decode(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return str(make_header(decode_header(value)))
    except Exception:  # pragma: no cover - malformed headers in the wild
        return value


def _body_text(message: Message) -> str:
    """Prefer text/plain; fall back to stripped HTML."""
    plain: list[str] = []
    html: list[str] = []
    for part in message.walk():
        if part.get_content_maintype() == "multipart":
            continue
        if part.get_filename():
            continue
        content_type = part.get_content_type()
        if content_type not in ("text/plain", "text/html"):
            continue
        try:
            payload = part.get_payload(decode=True) or b""
            text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        except Exception:  # pragma: no cover
            continue
        (plain if content_type == "text/plain" else html).append(text)

    if plain:
        return "\n".join(plain)[:MAX_BODY_CHARS]
    if html:
        import re

        stripped = re.sub(r"<[^>]+>", " ", "\n".join(html))
        return re.sub(r"\s+", " ", stripped).strip()[:MAX_BODY_CHARS]
    return ""


def _attachments(message: Message) -> list[FetchedAttachment]:
    found: list[FetchedAttachment] = []
    for part in message.walk():
        filename = part.get_filename()
        if not filename:
            continue
        try:
            content = part.get_payload(decode=True) or b""
        except Exception:  # pragma: no cover
            content = b""
        if len(content) > MAX_ATTACHMENT_BYTES:
            content = b""  # too large to keep; metadata is still recorded
        found.append(
            FetchedAttachment(
                filename=_decode(filename) or filename,
                content_type=part.get_content_type(),
                size_bytes=len(content),
                content=content,
            )
        )
    return found


def parse_message(raw: bytes, uid: int | None = None) -> FetchedEmail:
    """Convert a raw RFC-822 message into the normalised shape.

    Exposed separately so it can be unit-tested without any network.
    """
    message = email.message_from_bytes(raw)
    from_name, from_address = parseaddr(message.get("From", ""))
    _, to_address = parseaddr(message.get("To", ""))

    received_at = None
    if message.get("Date"):
        try:
            received_at = parsedate_to_datetime(message["Date"])
        except Exception:  # pragma: no cover - malformed Date headers
            received_at = None

    # Group replies with their original: References/In-Reply-To point at the
    # thread root, which is how partner rate replies find their RFQ.
    references = (message.get("References") or "").split()
    thread_key = (
        references[0]
        if references
        else (message.get("In-Reply-To") or message.get("Message-ID"))
    )

    return FetchedEmail(
        message_id=(message.get("Message-ID") or f"uid-{uid}").strip(),
        uid=uid,
        thread_key=(thread_key or "").strip() or None,
        from_address=(from_address or "").lower() or None,
        from_name=_decode(from_name),
        to_address=(to_address or "").lower() or None,
        subject=_decode(message.get("Subject")),
        body=_body_text(message),
        received_at=received_at,
        attachments=_attachments(message),
    )


class IMAPClient(EmailClient):
    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        use_ssl: bool = True,
        folder: str = "INBOX",
        timeout: int = 30,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._use_ssl = use_ssl
        self._folder = folder
        self._timeout = timeout

    def _connect(self):
        try:
            factory = imaplib.IMAP4_SSL if self._use_ssl else imaplib.IMAP4
            conn = factory(self._host, self._port, timeout=self._timeout)
            conn.login(self._username, self._password)
            # readonly=True: never alter flags in the customer's mailbox.
            conn.select(self._folder, readonly=True)
            return conn
        except Exception as exc:
            raise EmailError(f"Could not open mailbox {self._username}: {exc}") from exc

    def verify(self) -> None:
        conn = self._connect()
        try:
            conn.logout()
        except Exception:  # pragma: no cover
            pass

    def fetch_new(self, *, since_uid: int | None, limit: int) -> list[FetchedEmail]:
        conn = self._connect()
        try:
            # UID-based search so nothing is missed or re-read across polls.
            criteria = f"{(since_uid or 0) + 1}:*"
            status, data = conn.uid("SEARCH", None, "UID", criteria)
            if status != "OK":
                raise EmailError(f"IMAP search failed: {status}")

            uids = [int(u) for u in (data[0] or b"").split()]
            # A "N:*" search always returns at least the newest message even when
            # nothing is newer — drop anything we have already processed.
            if since_uid is not None:
                uids = [u for u in uids if u > since_uid]
            uids = sorted(uids)[:limit]

            messages: list[FetchedEmail] = []
            for uid in uids:
                status, payload = conn.uid("FETCH", str(uid), "(BODY.PEEK[])")
                if status != "OK" or not payload or not isinstance(payload[0], tuple):
                    log.warning("imap_fetch_skipped", uid=uid, status=status)
                    continue
                messages.append(parse_message(payload[0][1], uid=uid))
            return messages
        finally:
            try:
                conn.logout()
            except Exception:  # pragma: no cover
                pass
