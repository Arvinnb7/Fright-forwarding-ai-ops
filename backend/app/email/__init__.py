"""Mail transport layer.

Ingestion depends on the `EmailClient` interface only; `get_email_client()`
builds the concrete transport from a stored mailbox configuration, and
`set_email_client_factory()` lets tests inject a fake without a mail server.
"""
from __future__ import annotations

from typing import Callable

from app.email.base import EmailClient, EmailError, FetchedAttachment, FetchedEmail

_factory_override: Callable[..., EmailClient] | None = None


def set_email_client_factory(factory: Callable[..., EmailClient] | None) -> None:
    """Inject an EmailClient factory (used by tests). Pass None to reset."""
    global _factory_override
    _factory_override = factory


def get_email_client(config) -> EmailClient:
    """Build a client for a `MailboxConfig` row."""
    if _factory_override is not None:
        return _factory_override(config)

    from app.email.imap_client import IMAPClient

    return IMAPClient(
        host=config.host,
        port=config.port,
        username=config.username,
        password=config.get_password(),
        use_ssl=config.use_ssl,
        folder=config.folder,
    )


__all__ = [
    "EmailClient",
    "EmailError",
    "FetchedAttachment",
    "FetchedEmail",
    "get_email_client",
    "set_email_client_factory",
]
