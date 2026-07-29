"""Provider-neutral mail-fetching interface.

Ingestion depends only on :class:`EmailClient`, so the pipeline can be tested
end-to-end without a mail server (and a Gmail/Outlook API transport can be added
later without touching the ingestion logic).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


class EmailError(RuntimeError):
    """Raised when a mailbox cannot be reached or read."""


@dataclass
class FetchedAttachment:
    filename: str
    content_type: str
    size_bytes: int
    content: bytes = b""


@dataclass
class FetchedEmail:
    """One message, normalised across transports."""

    message_id: str
    uid: int | None = None
    thread_key: str | None = None
    from_address: str | None = None
    from_name: str | None = None
    to_address: str | None = None
    subject: str | None = None
    body: str = ""
    received_at: datetime | None = None
    attachments: list[FetchedAttachment] = field(default_factory=list)

    def attachment_metadata(self) -> list[dict[str, Any]]:
        return [
            {
                "filename": a.filename,
                "content_type": a.content_type,
                "size_bytes": a.size_bytes,
            }
            for a in self.attachments
        ]


class EmailClient(ABC):
    """Read-only access to a mailbox."""

    @abstractmethod
    def fetch_new(self, *, since_uid: int | None, limit: int) -> list[FetchedEmail]:
        """Return messages newer than `since_uid`, oldest first.

        Implementations must not mutate the mailbox (no flag changes, no
        deletions) — the customer's inbox stays exactly as they left it.
        """

    @abstractmethod
    def verify(self) -> None:
        """Raise :class:`EmailError` if the mailbox cannot be opened."""
