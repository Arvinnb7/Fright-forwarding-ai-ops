"""The IMAP client against a real socket speaking the real protocol.

The ingestion tests inject a fake transport, which proves the pipeline but not
the transport. Since a customer's first impression is entirely "did it connect
and read my mail", the client is exercised here against a minimal in-process
IMAP server: command syntax, UID watermarking, and — critically — that the
mailbox is opened read-only and fetched with BODY.PEEK so the customer's unread
flags are never touched.
"""
from __future__ import annotations

import socket
import threading
from email.message import EmailMessage as PyEmailMessage

import pytest

from app.email.base import EmailError
from app.email.imap_client import IMAPClient

USERNAME = "sales@forwarder.example"
PASSWORD = "app-password-123"


def _message(subject: str, body: str, message_id: str) -> bytes:
    message = PyEmailMessage()
    message["Subject"] = subject
    message["From"] = f"Ali <ali@acme-trading.com>"
    message["To"] = USERNAME
    message["Message-ID"] = message_id
    message["Date"] = "Tue, 14 Jul 2026 09:30:00 +0000"
    message.set_content(body)
    return message.as_bytes()


class TinyIMAPServer:
    """Just enough IMAP4rev1 for the client's happy path, plus a record of every
    command it received so the read-only guarantees can be asserted."""

    def __init__(self, messages: dict[int, bytes], *, reject_login: bool = False) -> None:
        self.messages = messages
        self.reject_login = reject_login
        self.commands: list[str] = []
        self._sock = socket.socket()
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(1)
        self.port = self._sock.getsockname()[1]
        self._thread = threading.Thread(target=self._serve, daemon=True)

    def __enter__(self) -> "TinyIMAPServer":
        self._thread.start()
        return self

    def __exit__(self, *_exc) -> None:
        try:
            self._sock.close()
        except OSError:
            pass

    def _serve(self) -> None:
        while True:
            try:
                conn, _ = self._sock.accept()
            except OSError:
                return
            threading.Thread(target=self._session, args=(conn,), daemon=True).start()

    def _session(self, conn: socket.socket) -> None:
        stream = conn.makefile("rwb")
        stream.write(b"* OK [CAPABILITY IMAP4rev1] TinyIMAP ready\r\n")
        stream.flush()
        try:
            while True:
                line = stream.readline()
                if not line:
                    return
                text = line.decode("utf-8", "replace").strip()
                self.commands.append(text)
                tag, _, rest = text.partition(" ")
                command = rest.upper()

                if command.startswith("CAPABILITY"):
                    stream.write(b"* CAPABILITY IMAP4rev1\r\n")
                    stream.write(f"{tag} OK CAPABILITY done\r\n".encode())
                elif command.startswith("LOGIN"):
                    if self.reject_login:
                        stream.write(f"{tag} NO [AUTHENTICATIONFAILED] Invalid credentials\r\n".encode())
                    else:
                        stream.write(f"{tag} OK LOGIN done\r\n".encode())
                elif command.startswith("EXAMINE") or command.startswith("SELECT"):
                    stream.write(f"* {len(self.messages)} EXISTS\r\n".encode())
                    stream.write(b"* OK [PERMANENTFLAGS ()] Read-only\r\n")
                    access = "READ-ONLY" if command.startswith("EXAMINE") else "READ-WRITE"
                    stream.write(f"{tag} OK [{access}] done\r\n".encode())
                elif command.startswith("UID SEARCH"):
                    lower, _, _ = rest.upper().partition("UID SEARCH UID ")[2].partition(":")
                    try:
                        floor = int(lower)
                    except ValueError:
                        floor = 1
                    hits = sorted(uid for uid in self.messages if uid >= floor)
                    # Real servers return the last message even when the range
                    # starts beyond it; reproduce that so the client's own
                    # filtering is exercised.
                    if not hits and self.messages:
                        hits = [max(self.messages)]
                    stream.write(("* SEARCH " + " ".join(map(str, hits)) + "\r\n").encode())
                    stream.write(f"{tag} OK SEARCH done\r\n".encode())
                elif command.startswith("UID FETCH"):
                    uid = int(rest.split()[2])
                    raw = self.messages[uid]
                    stream.write(f"* 1 FETCH (UID {uid} BODY[] {{{len(raw)}}}\r\n".encode())
                    stream.write(raw)
                    stream.write(b")\r\n")
                    stream.write(f"{tag} OK FETCH done\r\n".encode())
                elif command.startswith("LOGOUT"):
                    stream.write(b"* BYE logging out\r\n")
                    stream.write(f"{tag} OK LOGOUT done\r\n".encode())
                    stream.flush()
                    return
                else:
                    stream.write(f"{tag} BAD unsupported: {command}\r\n".encode())
                stream.flush()
        except (OSError, ValueError):
            return
        finally:
            try:
                conn.close()
            except OSError:
                pass


def _client(port: int) -> IMAPClient:
    return IMAPClient(
        host="127.0.0.1",
        port=port,
        username=USERNAME,
        password=PASSWORD,
        use_ssl=False,
        folder="INBOX",
        timeout=10,
    )


def test_fetches_and_parses_over_a_real_socket():
    messages = {
        1: _message("Rate request", "Shanghai to Jebel Ali 40HC", "<one@acme.com>"),
        2: _message("Second enquiry", "Ningbo to Dubai 20GP", "<two@acme.com>"),
    }
    with TinyIMAPServer(messages) as server:
        fetched = _client(server.port).fetch_new(since_uid=None, limit=10)

    assert [m.uid for m in fetched] == [1, 2]
    assert [m.message_id for m in fetched] == ["<one@acme.com>", "<two@acme.com>"]
    assert "Shanghai" in fetched[0].body
    assert fetched[0].from_address == "ali@acme-trading.com"


def test_the_mailbox_is_never_modified():
    """The customer's inbox must look untouched afterwards: opened read-only,
    fetched with PEEK, and no flag or delete commands at all."""
    messages = {1: _message("Rate request", "Shanghai to Dubai", "<one@acme.com>")}
    with TinyIMAPServer(messages) as server:
        _client(server.port).fetch_new(since_uid=None, limit=10)
        issued = " ".join(server.commands).upper()

    assert "EXAMINE" in issued, "mailbox was not opened read-only"
    assert "BODY.PEEK[]" in issued, "fetch would have set the \\Seen flag"
    for forbidden in ("STORE", "DELETE", "EXPUNGE", "APPEND", "MOVE", "COPY"):
        assert forbidden not in issued, f"client issued a mutating command: {forbidden}"


def test_watermark_skips_already_processed_messages():
    messages = {
        1: _message("Old", "already processed", "<one@acme.com>"),
        2: _message("Older", "also processed", "<two@acme.com>"),
        3: _message("New", "Shanghai to Dubai", "<three@acme.com>"),
    }
    with TinyIMAPServer(messages) as server:
        fetched = _client(server.port).fetch_new(since_uid=2, limit=10)

    assert [m.uid for m in fetched] == [3]


def test_nothing_new_returns_nothing_even_though_the_server_replies():
    """A `N:*` search always yields at least one message; returning it would
    reprocess the newest mail forever."""
    messages = {1: _message("Only", "Shanghai to Dubai", "<one@acme.com>")}
    with TinyIMAPServer(messages) as server:
        assert _client(server.port).fetch_new(since_uid=1, limit=10) == []


def test_batch_limit_is_respected():
    messages = {
        uid: _message(f"Enquiry {uid}", "Shanghai to Dubai", f"<{uid}@acme.com>")
        for uid in range(1, 8)
    }
    with TinyIMAPServer(messages) as server:
        fetched = _client(server.port).fetch_new(since_uid=None, limit=3)

    # Oldest first, so a backlog is worked through in arrival order.
    assert [m.uid for m in fetched] == [1, 2, 3]


def test_bad_credentials_produce_an_actionable_error():
    with TinyIMAPServer({}, reject_login=True) as server:
        with pytest.raises(EmailError) as excinfo:
            _client(server.port).verify()

    assert USERNAME in str(excinfo.value)


def test_unreachable_server_is_reported_as_an_email_error():
    # Port 1 is reserved and never listening.
    with pytest.raises(EmailError):
        IMAPClient(
            host="127.0.0.1",
            port=1,
            username=USERNAME,
            password=PASSWORD,
            use_ssl=False,
            timeout=2,
        ).verify()


def test_verify_succeeds_against_a_working_server():
    with TinyIMAPServer({1: _message("Hi", "body", "<one@acme.com>")}) as server:
        _client(server.port).verify()  # must not raise
