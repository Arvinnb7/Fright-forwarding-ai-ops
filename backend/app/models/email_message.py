"""An email pulled from a customer mailbox, plus what we decided to do with it.

Every fetched message is persisted before any AI runs, so ingestion is
auditable ("why did this RFQ appear?") and idempotent: re-fetching the same
message never creates a second RFQ.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.tenancy import TenantMixin
from app.models.base import TimestampMixin, enum_column

JSONType = JSON().with_variant(JSONB, "postgresql")


class EmailClassification(str, Enum):
    """What the message is, which decides how it is routed."""

    NEW_RFQ = "New RFQ"
    RATE_REPLY = "Partner rate reply"
    CUSTOMER_REPLY = "Customer reply"
    NOT_RELEVANT = "Not relevant"
    UNCLASSIFIED = "Unclassified"


class EmailProcessingStatus(str, Enum):
    PENDING = "Pending"
    PROCESSED = "Processed"
    IGNORED = "Ignored"
    FAILED = "Failed"


class EmailMessage(Base, TenantMixin, TimestampMixin):
    __tablename__ = "email_messages"
    # The provider's Message-ID makes ingestion idempotent within a tenant.
    __table_args__ = (
        UniqueConstraint("org_id", "message_id", name="uq_email_messages_org_message"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    message_id: Mapped[str] = mapped_column(String(512), index=True, nullable=False)
    thread_key: Mapped[str | None] = mapped_column(String(512), index=True)
    uid: Mapped[int | None] = mapped_column(index=True)

    from_address: Mapped[str | None] = mapped_column(String(320), index=True)
    from_name: Mapped[str | None] = mapped_column(String(255))
    to_address: Mapped[str | None] = mapped_column(String(320))
    subject: Mapped[str | None] = mapped_column(String(1024))
    body: Mapped[str | None] = mapped_column(Text)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    classification: Mapped[EmailClassification] = mapped_column(
        enum_column(EmailClassification), default=EmailClassification.UNCLASSIFIED
    )
    classification_confidence: Mapped[float | None] = mapped_column(Float)
    classification_reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[EmailProcessingStatus] = mapped_column(
        enum_column(EmailProcessingStatus), default=EmailProcessingStatus.PENDING
    )
    error: Mapped[str | None] = mapped_column(Text)

    # What this message produced or attached to.
    rfq_id: Mapped[int | None] = mapped_column(ForeignKey("rfqs.id"), index=True)
    quote_id: Mapped[int | None] = mapped_column(ForeignKey("quotes.id"), index=True)

    attachments: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, default=list)
