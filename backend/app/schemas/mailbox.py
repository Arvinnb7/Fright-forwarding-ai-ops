"""Mailbox configuration and ingested-message schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.email_message import EmailClassification, EmailProcessingStatus


class MailboxConfigCreate(BaseModel):
    host: str = Field(min_length=1, max_length=255)
    port: int = 993
    use_ssl: bool = True
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=512)
    folder: str = "INBOX"
    is_enabled: bool = True


class MailboxConfigUpdate(BaseModel):
    host: str | None = None
    port: int | None = None
    use_ssl: bool | None = None
    username: str | None = None
    password: str | None = None  # write-only; never returned
    folder: str | None = None
    is_enabled: bool | None = None


class MailboxConfigOut(BaseModel):
    """Note the absence of any password field — credentials are write-only."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    host: str
    port: int
    use_ssl: bool
    username: str
    folder: str
    is_enabled: bool
    last_seen_uid: int | None
    last_polled_at: datetime | None
    last_error: str | None
    created_at: datetime


class MailboxTestResult(BaseModel):
    ok: bool
    detail: str


class EmailMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    message_id: str
    thread_key: str | None
    from_address: str | None
    from_name: str | None
    subject: str | None
    body: str | None
    received_at: datetime | None
    classification: EmailClassification
    classification_confidence: float | None
    classification_reason: str | None
    status: EmailProcessingStatus
    error: str | None
    rfq_id: int | None
    quote_id: int | None
    attachments: list[dict[str, Any]] = []
    created_at: datetime


class IngestRunResult(BaseModel):
    fetched: int
    skipped_duplicates: int
    rfqs_created: int
    rate_replies_linked: int
    customer_replies_linked: int
    ignored: int
    failed: int
