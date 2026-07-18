"""Convert a won quote into an operational booking / job file."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.booking import Booking
from app.models.enums import BookingStatus, QuoteStatus, RFQStatus
from app.models.quote import Quote
from app.models.rfq import RFQ
from app.schemas.booking import BookingCreateFromQuote
from app.services.reference import job_number as make_job_number


def _cargo_details_from_rfq(rfq: RFQ | None) -> str | None:
    if rfq is None:
        return None
    parts: list[str] = []
    if rfq.commodity:
        parts.append(rfq.commodity)
    if rfq.container_type:
        parts.append(f"{rfq.container_type}")
    if rfq.gross_weight:
        parts.append(f"{rfq.gross_weight}")
    if rfq.cbm:
        parts.append(f"{rfq.cbm} CBM")
    if rfq.package_count:
        parts.append(f"{rfq.package_count} pkgs")
    return ", ".join(parts) or None


def create_booking_from_quote(db: Session, payload: BookingCreateFromQuote) -> Booking:
    """Create the job file from a quote — the manual 'customer confirmed' action.

    Marks the quote (and its RFQ) as Won: converting IS the human confirmation
    step required by spec §12.
    """
    quote = db.get(Quote, payload.quote_id)
    if quote is None:
        raise ValueError("Quote not found")
    if quote.status in (QuoteStatus.DRAFT, QuoteStatus.PENDING_APPROVAL):
        raise ValueError(
            "Quote has not been approved/sent yet — approve it before booking."
        )

    rfq = db.get(RFQ, quote.rfq_id) if quote.rfq_id else None

    booking = Booking(
        quote_id=quote.id,
        customer_id=quote.customer_id,
        origin=rfq.origin if rfq else None,
        destination=rfq.destination if rfq else None,
        cargo_details=_cargo_details_from_rfq(rfq),
        agreed_price=quote.selling_price,
        estimated_cost=quote.cost_amount,
        estimated_margin=quote.gross_margin,
        currency=quote.currency,
        shipper=payload.shipper,
        consignee=payload.consignee,
        notify_party=payload.notify_party,
        assigned_to=payload.assigned_to,
        etd=payload.etd,
        eta=payload.eta,
        status=BookingStatus.BOOKING_CONFIRMED,
    )
    db.add(booking)
    db.flush()
    booking.job_number = make_job_number(booking.id)

    quote.status = QuoteStatus.WON
    if rfq is not None:
        rfq.status = RFQStatus.WON

    db.commit()
    db.refresh(booking)
    return booking
