"""Email ingestion: mailbox → structured record.

This is what makes the product's core promise possible. The operator no longer
opens an inbox and copies text: an RFQ email becomes a parsed, structured RFQ
within one polling interval, so response time is bounded by the poll (minutes),
not by when somebody happens to look.

Guarantees:
* **Idempotent** — a message is keyed by its provider Message-ID per
  organization; re-fetching never creates a second RFQ.
* **Auditable** — every message is stored before any AI runs, with the
  classification and the reason for it.
* **Non-destructive** — the mailbox is opened read-only; nothing is sent,
  flagged or deleted. Drafts still require human approval (spec §12).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.agents.email_classifier import run_email_classifier
from app.agents.rfq_parser import run_rfq_parser
from app.core.config import settings
from app.core.logging import get_logger
from app.email import EmailError, FetchedEmail, get_email_client
from app.llm import get_llm
from app.llm.base import LLMClient
from app.models.customer import Customer
from app.models.email_message import (
    EmailClassification,
    EmailMessage,
    EmailProcessingStatus,
)
from app.models.enums import FollowUpStatus, QuoteStatus
from app.models.follow_up import FollowUp
from app.models.mailbox import MailboxConfig
from app.models.quote import Quote
from app.models.rfq import RFQ
from app.services.rfq_service import create_rfq_from_extraction
from app.services.storage import StorageError, save_bytes

log = get_logger("email.ingest")


@dataclass
class IngestResult:
    fetched: int = 0
    skipped_duplicates: int = 0
    rfqs_created: int = 0
    rate_replies_linked: int = 0
    customer_replies_linked: int = 0
    ignored: int = 0
    failed: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "fetched": self.fetched,
            "skipped_duplicates": self.skipped_duplicates,
            "rfqs_created": self.rfqs_created,
            "rate_replies_linked": self.rate_replies_linked,
            "customer_replies_linked": self.customer_replies_linked,
            "ignored": self.ignored,
            "failed": self.failed,
        }


def _already_ingested(db: Session, message_id: str) -> bool:
    return (
        db.execute(
            select(EmailMessage.id).where(EmailMessage.message_id == message_id)
        ).first()
        is not None
    )


def _match_customer(db: Session, from_address: str | None) -> Customer | None:
    """Best-effort link to a known customer by sender address, then domain."""
    if not from_address:
        return None
    exact = db.execute(
        select(Customer).where(Customer.email == from_address)
    ).scalar_one_or_none()
    if exact is not None:
        return exact
    domain = from_address.split("@")[-1].lower()
    if not domain or domain in {"gmail.com", "hotmail.com", "outlook.com", "yahoo.com"}:
        return None
    return db.execute(
        select(Customer).where(Customer.email.ilike(f"%@{domain}"))
    ).scalars().first()


def _find_related_rfq(db: Session, email: FetchedEmail, reference: str | None) -> RFQ | None:
    """Locate the RFQ a partner reply belongs to: reference first, then thread."""
    if reference:
        found = db.execute(
            select(RFQ).where(RFQ.reference == reference.strip())
        ).scalar_one_or_none()
        if found is not None:
            return found
    if email.thread_key:
        prior = db.execute(
            select(EmailMessage)
            .where(
                EmailMessage.thread_key == email.thread_key,
                EmailMessage.rfq_id.is_not(None),
            )
            .order_by(EmailMessage.id.desc())
        ).scalars().first()
        if prior is not None:
            return db.get(RFQ, prior.rfq_id)
    return None


def _find_related_quote(db: Session, email: FetchedEmail, reference: str | None) -> Quote | None:
    if reference:
        found = db.execute(
            select(Quote).where(Quote.quote_number == reference.strip())
        ).scalar_one_or_none()
        if found is not None:
            return found
    if email.thread_key:
        prior = db.execute(
            select(EmailMessage)
            .where(
                EmailMessage.thread_key == email.thread_key,
                EmailMessage.quote_id.is_not(None),
            )
            .order_by(EmailMessage.id.desc())
        ).scalars().first()
        if prior is not None:
            return db.get(Quote, prior.quote_id)
    # Otherwise: the newest quote sent to this sender's customer.
    customer = _match_customer(db, email.from_address)
    if customer is not None:
        return db.execute(
            select(Quote)
            .where(Quote.customer_id == customer.id, Quote.status == QuoteStatus.SENT)
            .order_by(Quote.sent_at.desc().nullslast())
        ).scalars().first()
    return None


def _pause_follow_ups(db: Session, quote: Quote) -> None:
    """A customer replied — stop chasing them.

    Continuing an automated follow-up cadence after the customer has answered is
    exactly the behaviour that makes such tools feel robotic, so pending
    follow-ups for the quote are closed and the next date cleared.
    """
    pending = db.execute(
        select(FollowUp).where(
            FollowUp.quote_id == quote.id,
            FollowUp.status.in_([FollowUpStatus.PENDING, FollowUpStatus.DUE]),
        )
    ).scalars().all()
    for follow_up in pending:
        follow_up.status = FollowUpStatus.REPLIED
    quote.next_follow_up_date = None


def _persist_attachments(db: Session, record: EmailMessage, email: FetchedEmail) -> None:
    """Write attachment bytes to storage and record where they went.

    Freight RFQs routinely carry the packing list or commercial invoice as an
    attachment, so dropping them would leave the coordinator opening the mail
    client anyway — which is the exact behaviour this feature removes.
    """
    if not email.attachments:
        return

    entries: list[dict] = []
    for metadata, attachment in zip(record.attachments, email.attachments):
        entry = dict(metadata)
        if attachment.content:
            try:
                path, display_name = save_bytes(
                    org_id=record.org_id,
                    category="email",
                    filename=attachment.filename,
                    content=attachment.content,
                )
                entry["path"] = path
                entry["filename"] = display_name
            except StorageError as exc:  # pragma: no cover - disk failure
                entry["error"] = str(exc)
        else:
            entry["error"] = "Too large to store; open it in the mail client."
        entries.append(entry)

    # Reassigned (not mutated) so SQLAlchemy sees the JSON column as dirty.
    record.attachments = entries
    db.commit()


def _store_message(db: Session, email: FetchedEmail) -> EmailMessage:
    record = EmailMessage(
        message_id=email.message_id,
        thread_key=email.thread_key,
        uid=email.uid,
        from_address=email.from_address,
        from_name=email.from_name,
        to_address=email.to_address,
        subject=email.subject,
        body=email.body,
        received_at=email.received_at,
        attachments=email.attachment_metadata(),
        status=EmailProcessingStatus.PENDING,
    )
    db.add(record)
    return record


def process_email(db: Session, email: FetchedEmail, llm: LLMClient) -> EmailMessage | None:
    """Store, classify and route a single message. Returns None if duplicate."""
    if _already_ingested(db, email.message_id):
        return None

    record = _store_message(db, email)
    try:
        # Committed *before* any AI runs, on purpose: if the model call fails or
        # times out, the customer's message is already durable and can be
        # reprocessed or handled by hand. Losing an RFQ because a provider had a
        # bad minute is not an acceptable failure mode.
        db.commit()
    except IntegrityError:
        # Concurrent poll inserted the same message first — the unique
        # constraint is the real idempotency guarantee.
        db.rollback()
        return None

    record_id = record.id
    _persist_attachments(db, record, email)

    try:
        triage = run_email_classifier(
            subject=email.subject,
            body=email.body,
            from_address=email.from_address,
            llm=llm,
        )
        record.classification = triage.classification
        record.classification_confidence = triage.confidence
        record.classification_reason = triage.reason

        if triage.classification == EmailClassification.NEW_RFQ:
            extraction = run_rfq_parser(email.body or email.subject or "", llm)
            customer = _match_customer(db, email.from_address)
            rfq = create_rfq_from_extraction(
                db,
                extraction,
                email.body or "",
                customer_id=customer.id if customer is not None else None,
            )
            # The clock that the whole ROI claim rests on: when the customer
            # actually asked, not when we got around to processing it.
            rfq.received_at = email.received_at or datetime.now(timezone.utc)
            record.rfq_id = rfq.id
            record.status = EmailProcessingStatus.PROCESSED

        elif triage.classification == EmailClassification.RATE_REPLY:
            rfq = _find_related_rfq(db, email, triage.mentions_reference)
            if rfq is not None:
                record.rfq_id = rfq.id
            record.status = EmailProcessingStatus.PROCESSED

        elif triage.classification == EmailClassification.CUSTOMER_REPLY:
            quote = _find_related_quote(db, email, triage.mentions_reference)
            if quote is not None:
                record.quote_id = quote.id
                record.rfq_id = quote.rfq_id
                _pause_follow_ups(db, quote)
            record.status = EmailProcessingStatus.PROCESSED

        else:
            record.status = EmailProcessingStatus.IGNORED

        db.commit()
    except Exception as exc:  # noqa: BLE001 - a bad message must never be lost
        # Undo whatever the AI branch had pending, then mark the (already
        # committed) message as failed so it is visible in the inbox and can be
        # retried, instead of disappearing.
        db.rollback()
        log.error(
            "email_processing_failed", message_id=email.message_id, error=str(exc)
        )
        stored = db.get(EmailMessage, record_id)
        if stored is None:  # pragma: no cover - defensive
            return None
        stored.status = EmailProcessingStatus.FAILED
        stored.error = str(exc)[:2000]
        db.commit()
        db.refresh(stored)
        return stored

    db.refresh(record)
    return record


def ingest_mailbox(db: Session, config: MailboxConfig, llm: LLMClient | None = None) -> IngestResult:
    """Poll one organization's mailbox and process everything new."""
    result = IngestResult()
    llm = llm or get_llm()
    client = get_email_client(config)

    try:
        messages = client.fetch_new(
            since_uid=config.last_seen_uid, limit=settings.email_fetch_batch_size
        )
    except EmailError as exc:
        config.last_error = str(exc)[:2000]
        config.last_polled_at = datetime.now(timezone.utc)
        db.commit()
        log.error("mailbox_poll_failed", mailbox=config.username, error=str(exc))
        raise

    for email in messages:
        result.fetched += 1
        record = process_email(db, email, llm)
        if record is None:
            result.skipped_duplicates += 1
        elif record.status == EmailProcessingStatus.FAILED:
            result.failed += 1
        elif record.classification == EmailClassification.NEW_RFQ:
            result.rfqs_created += 1
        elif record.classification == EmailClassification.RATE_REPLY:
            result.rate_replies_linked += 1
        elif record.classification == EmailClassification.CUSTOMER_REPLY:
            result.customer_replies_linked += 1
        else:
            result.ignored += 1

        # Advance the watermark even for duplicates/ignored mail so a poisonous
        # message can never wedge the poller in a loop.
        if email.uid is not None:
            config.last_seen_uid = max(config.last_seen_uid or 0, email.uid)

    config.last_polled_at = datetime.now(timezone.utc)
    config.last_error = None
    db.commit()
    log.info("mailbox_polled", mailbox=config.username, **result.as_dict())
    return result
