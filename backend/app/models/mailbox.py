"""Per-organization mailbox connection used for automatic RFQ intake.

IMAP is deliberately the first (and currently only) transport: it works with any
company mail server on day one via an app password, whereas Gmail/Outlook OAuth
requires a weeks-long provider verification before a single customer can be
onboarded.

Access is **read-only**. The system never sends, deletes or marks mail; it
tracks the last processed UID and leaves the user's mailbox untouched.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.crypto import decrypt_secret, encrypt_secret
from app.core.db import Base
from app.core.tenancy import TenantMixin
from app.models.base import TimestampMixin


class MailboxConfig(Base, TenantMixin, TimestampMixin):
    __tablename__ = "mailbox_configs"

    id: Mapped[int] = mapped_column(primary_key=True)

    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, default=993, nullable=False)
    use_ssl: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    # Never stored in plaintext — see app/core/crypto.py.
    encrypted_password: Mapped[str] = mapped_column(Text, nullable=False)
    folder: Mapped[str] = mapped_column(String(128), default="INBOX", nullable=False)

    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Watermark so each message is fetched exactly once, without mutating the
    # mailbox (no \Seen flags, no deletions).
    last_seen_uid: Mapped[int | None] = mapped_column(Integer)
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)

    def set_password(self, plaintext: str) -> None:
        self.encrypted_password = encrypt_secret(plaintext)

    def get_password(self) -> str:
        return decrypt_secret(self.encrypted_password)
