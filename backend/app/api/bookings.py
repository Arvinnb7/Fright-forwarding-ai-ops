"""Booking / job-file endpoints: convert, CRUD, documents, status-update drafts."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.shipment_ops import (
    booking_context,
    run_document_suggestions,
    run_status_update,
)
from app.api.files import file_response
from app.core.config import settings
from app.core.db import get_db
from app.core.deps import get_current_user
from app.llm import get_llm
from app.llm.base import LLMError
from app.models.booking import Booking
from app.models.customer import Customer
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.models.user import User
from app.schemas.booking import (
    BookingCreateFromQuote,
    BookingOut,
    BookingUpdate,
    DocumentCreate,
    DocumentOut,
    DocumentSuggestionsOut,
    DocumentUpdate,
    StatusUpdateDraftIn,
    StatusUpdateDraftOut,
)
from app.services.booking_service import create_booking_from_quote
from app.services.storage import StorageError, delete_file, read_bytes, save_bytes

router = APIRouter()


def _require_booking(db: Session, booking_id: int) -> Booking:
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking


@router.post("/from-quote", response_model=BookingOut, status_code=201)
def convert_quote(
    payload: BookingCreateFromQuote,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Booking:
    """Convert a sent/approved quote into a job file (marks it Won)."""
    try:
        return create_booking_from_quote(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("", response_model=list[BookingOut])
def list_bookings(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    limit: int = 100,
    offset: int = 0,
) -> list[Booking]:
    stmt = select(Booking).order_by(Booking.created_at.desc()).limit(limit).offset(offset)
    return list(db.execute(stmt).scalars().all())


@router.get("/{booking_id}", response_model=BookingOut)
def get_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Booking:
    return _require_booking(db, booking_id)


@router.patch("/{booking_id}", response_model=BookingOut)
def update_booking(
    booking_id: int,
    payload: BookingUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Booking:
    booking = _require_booking(db, booking_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(booking, field, value)
    db.commit()
    db.refresh(booking)
    return booking


# ── Documents ────────────────────────────────────────────────


@router.get("/{booking_id}/documents", response_model=list[DocumentOut])
def list_documents(
    booking_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[Document]:
    _require_booking(db, booking_id)
    stmt = select(Document).where(Document.booking_id == booking_id).order_by(Document.id)
    return list(db.execute(stmt).scalars().all())


@router.post("/{booking_id}/documents", response_model=DocumentOut, status_code=201)
def add_document(
    booking_id: int,
    payload: DocumentCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Document:
    _require_booking(db, booking_id)
    doc = Document(booking_id=booking_id, **payload.model_dump())
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


@router.patch("/documents/{document_id}", response_model=DocumentOut)
def update_document(
    document_id: int,
    payload: DocumentUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Document:
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(doc, field, value)
    db.commit()
    db.refresh(doc)
    return doc


@router.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    delete_file(doc.file_path, user.organization_id)
    db.delete(doc)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/documents/{document_id}/file", response_model=DocumentOut)
def upload_document_file(
    document_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Document:
    """Attach the actual file to a tracked document.

    Uploading also moves the document to 'Received' — the checklist and the
    files it tracks should never disagree.
    """
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    content = file.file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    limit = settings.max_upload_mb * 1024 * 1024
    if len(content) > limit:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {settings.max_upload_mb} MB upload limit",
        )

    previous = doc.file_path
    try:
        path, display_name = save_bytes(
            org_id=user.organization_id,
            category="documents",
            filename=file.filename,
            content=content,
        )
    except StorageError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    doc.file_path = path
    doc.file_name = display_name
    doc.file_size_bytes = len(content)
    doc.content_type = file.content_type or "application/octet-stream"
    if doc.status == DocumentStatus.REQUIRED:
        doc.status = DocumentStatus.RECEIVED
    db.commit()
    db.refresh(doc)
    # Only after the new file is safely committed.
    if previous and previous != path:
        delete_file(previous, user.organization_id)
    return doc


@router.get("/documents/{document_id}/file")
def download_document_file(
    document_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if not doc.file_path:
        raise HTTPException(status_code=404, detail="No file uploaded for this document")
    try:
        content = read_bytes(doc.file_path, user.organization_id)
    except StorageError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return file_response(
        content,
        filename=doc.file_name or f"document-{doc.id}",
        content_type=doc.content_type or "application/octet-stream",
    )


@router.post("/{booking_id}/documents/suggest", response_model=DocumentSuggestionsOut)
def suggest_documents(
    booking_id: int,
    create: bool = True,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> DocumentSuggestionsOut:
    """AI-suggest required documents; optionally create missing ones as Required."""
    booking = _require_booking(db, booking_id)
    try:
        suggestions = run_document_suggestions(
            shipment_context=booking_context(booking), llm=get_llm()
        )
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    created: list[Document] = []
    if create:
        existing = {
            d.document_type.lower()
            for d in db.execute(
                select(Document).where(Document.booking_id == booking_id)
            ).scalars()
        }
        for s in suggestions:
            if s["document_type"].lower() not in existing:
                doc = Document(
                    booking_id=booking_id,
                    document_type=s["document_type"],
                    notes=s.get("reason"),
                )
                db.add(doc)
                created.append(doc)
        db.commit()
        for doc in created:
            db.refresh(doc)

    return DocumentSuggestionsOut(
        suggestions=suggestions,  # type: ignore[arg-type]
        created=[DocumentOut.model_validate(d) for d in created],
    )


# ── Customer status update draft ─────────────────────────────


@router.post("/{booking_id}/status-update-draft", response_model=StatusUpdateDraftOut)
def status_update_draft(
    booking_id: int,
    payload: StatusUpdateDraftIn,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> StatusUpdateDraftOut:
    booking = _require_booking(db, booking_id)
    customer = db.get(Customer, booking.customer_id) if booking.customer_id else None
    try:
        draft = run_status_update(
            booking=booking,
            status=payload.status,
            etd=payload.etd,
            eta=payload.eta,
            extra_note=payload.extra_note,
            customer_name=customer.contact_name if customer else None,
            llm=get_llm(),
        )
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return StatusUpdateDraftOut(draft=draft)
