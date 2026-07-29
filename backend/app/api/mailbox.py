"""Mailbox configuration + ingested email inbox."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.files import file_response
from app.core.db import get_db
from app.core.deps import get_current_user, require_org_admin
from app.core.logging import get_logger
from app.email import EmailError, get_email_client
from app.models.email_message import EmailClassification, EmailMessage
from app.models.mailbox import MailboxConfig
from app.models.user import User
from app.schemas.mailbox import (
    EmailMessageOut,
    IngestRunResult,
    MailboxConfigCreate,
    MailboxConfigOut,
    MailboxConfigUpdate,
    MailboxTestResult,
)
from app.services.email_ingest import ingest_mailbox
from app.services.storage import StorageError, read_bytes

router = APIRouter()
log = get_logger("api.mailbox")


def _get_config(db: Session) -> MailboxConfig | None:
    """The caller's mailbox (tenant filtering is automatic)."""
    return db.execute(select(MailboxConfig).order_by(MailboxConfig.id)).scalars().first()


def _require_config(db: Session) -> MailboxConfig:
    config = _get_config(db)
    if config is None:
        raise HTTPException(status_code=404, detail="No mailbox configured")
    return config


@router.get("/config", response_model=MailboxConfigOut | None)
def get_config(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> MailboxConfig | None:
    return _get_config(db)


@router.put("/config", response_model=MailboxConfigOut)
def upsert_config(
    payload: MailboxConfigCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_org_admin),
) -> MailboxConfig:
    """Create or replace this organization's mailbox connection.

    Admin-only: it holds a credential to the company's email account.
    """
    config = _get_config(db)
    if config is None:
        config = MailboxConfig(
            host=payload.host,
            port=payload.port,
            use_ssl=payload.use_ssl,
            username=payload.username,
            folder=payload.folder,
            is_enabled=payload.is_enabled,
            encrypted_password="",
        )
        db.add(config)
    else:
        config.host = payload.host
        config.port = payload.port
        config.use_ssl = payload.use_ssl
        config.username = payload.username
        config.folder = payload.folder
        config.is_enabled = payload.is_enabled
    config.set_password(payload.password)
    config.last_error = None
    db.commit()
    db.refresh(config)
    return config


@router.patch("/config", response_model=MailboxConfigOut)
def update_config(
    payload: MailboxConfigUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_org_admin),
) -> MailboxConfig:
    config = _require_config(db)
    data = payload.model_dump(exclude_unset=True)
    password = data.pop("password", None)
    for field, value in data.items():
        setattr(config, field, value)
    if password:
        config.set_password(password)
    db.commit()
    db.refresh(config)
    return config


@router.delete("/config", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_config(
    db: Session = Depends(get_db),
    _: User = Depends(require_org_admin),
) -> Response:
    config = _require_config(db)
    db.delete(config)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/test", response_model=MailboxTestResult)
def test_connection(
    db: Session = Depends(get_db),
    _: User = Depends(require_org_admin),
) -> MailboxTestResult:
    """Verify the stored credentials can open the mailbox (read-only)."""
    config = _require_config(db)
    try:
        get_email_client(config).verify()
    except EmailError as exc:
        return MailboxTestResult(ok=False, detail=str(exc))
    return MailboxTestResult(ok=True, detail="Mailbox reachable.")


@router.post("/sync", response_model=IngestRunResult)
def sync_now(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> IngestRunResult:
    """Poll the mailbox immediately instead of waiting for the scheduler."""
    config = _require_config(db)
    if not config.is_enabled:
        raise HTTPException(status_code=400, detail="Mailbox ingestion is disabled")
    try:
        result = ingest_mailbox(db, config)
    except EmailError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return IngestRunResult(**result.as_dict())


@router.get("/messages", response_model=list[EmailMessageOut])
def list_messages(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    classification: EmailClassification | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[EmailMessage]:
    stmt = select(EmailMessage).order_by(EmailMessage.received_at.desc().nullslast())
    if classification is not None:
        stmt = stmt.where(EmailMessage.classification == classification)
    return list(db.execute(stmt.limit(limit).offset(offset)).scalars().all())


@router.get("/messages/{message_id}", response_model=EmailMessageOut)
def get_message(
    message_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> EmailMessage:
    record = db.get(EmailMessage, message_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Message not found")
    return record


@router.get("/messages/{message_id}/attachments/{index}")
def download_attachment(
    message_id: int,
    index: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    """Download an attachment that arrived with an ingested email.

    Packing lists and invoices arrive attached, so they must be reachable from
    the record — otherwise the coordinator still has to open the mail client.
    """
    record = db.get(EmailMessage, message_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Message not found")
    attachments = record.attachments or []
    if index < 0 or index >= len(attachments):
        raise HTTPException(status_code=404, detail="Attachment not found")

    attachment = attachments[index]
    path = attachment.get("path")
    if not path:
        raise HTTPException(
            status_code=404,
            detail=attachment.get("error") or "Attachment content was not stored",
        )
    try:
        content = read_bytes(path, user.organization_id)
    except StorageError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return file_response(
        content,
        filename=attachment.get("filename") or "attachment",
        content_type=attachment.get("content_type") or "application/octet-stream",
    )
