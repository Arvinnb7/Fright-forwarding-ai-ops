"""Shipment document tracked against a booking."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import TimestampMixin, enum_column
from app.core.tenancy import TenantMixin
from app.models.enums import DocumentStatus

if TYPE_CHECKING:
    from app.models.booking import Booking


class Document(Base, TenantMixin, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id"), index=True, nullable=False)

    document_type: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        enum_column(DocumentStatus), default=DocumentStatus.REQUIRED
    )
    # Storage-relative path (see app/services/storage.py) plus the metadata
    # needed to serve the file back with its original name.
    file_path: Mapped[str | None] = mapped_column(String(512))
    file_name: Mapped[str | None] = mapped_column(String(255))
    file_size_bytes: Mapped[int | None] = mapped_column(Integer)
    content_type: Mapped[str | None] = mapped_column(String(128))
    notes: Mapped[str | None] = mapped_column(Text)

    booking: Mapped["Booking"] = relationship(back_populates="documents")
