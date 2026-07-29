"""Booking / job-file, document and status-update schemas."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, computed_field

from app.models.enums import BookingStatus, DocumentStatus


class BookingCreateFromQuote(BaseModel):
    quote_id: int
    shipper: str | None = None
    consignee: str | None = None
    notify_party: str | None = None
    assigned_to: str | None = None
    etd: date | None = None
    eta: date | None = None


class BookingUpdate(BaseModel):
    shipper: str | None = None
    consignee: str | None = None
    notify_party: str | None = None
    cargo_details: str | None = None
    assigned_to: str | None = None
    status: BookingStatus | None = None
    etd: date | None = None
    eta: date | None = None


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_number: str | None
    quote_id: int | None
    customer_id: int | None
    shipper: str | None
    consignee: str | None
    notify_party: str | None
    origin: str | None
    destination: str | None
    cargo_details: str | None
    agreed_price: float | None
    estimated_cost: float | None
    estimated_margin: float | None
    currency: str
    assigned_to: str | None
    status: BookingStatus
    etd: date | None
    eta: date | None
    created_at: datetime
    updated_at: datetime


class DocumentCreate(BaseModel):
    document_type: str
    status: DocumentStatus = DocumentStatus.REQUIRED
    notes: str | None = None


class DocumentUpdate(BaseModel):
    document_type: str | None = None
    status: DocumentStatus | None = None
    notes: str | None = None


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    booking_id: int
    document_type: str
    status: DocumentStatus
    notes: str | None
    file_name: str | None = None
    file_size_bytes: int | None = None
    content_type: str | None = None
    created_at: datetime
    updated_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_file(self) -> bool:
        return bool(self.file_name)


class DocumentSuggestion(BaseModel):
    document_type: str
    reason: str


class DocumentSuggestionsOut(BaseModel):
    suggestions: list[DocumentSuggestion]
    created: list[DocumentOut] = []


class StatusUpdateDraftIn(BaseModel):
    # Defaults to the booking's current status; can be overridden, plus extras.
    status: str | None = None
    etd: str | None = None
    eta: str | None = None
    extra_note: str | None = None


class StatusUpdateDraftOut(BaseModel):
    draft: str
