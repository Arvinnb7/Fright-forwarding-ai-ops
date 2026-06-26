"""Compute deterministic daily metrics for the management report.

Counts and sums come from the database here (not the LLM) so the numbers are
always correct; the Report agent only turns them into prose.
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.booking import Booking
from app.models.enums import FollowUpStatus, QuoteStatus, RFQStatus
from app.models.follow_up import FollowUp
from app.models.quote import Quote
from app.models.rfq import RFQ

_ACTIVE_QUOTE_STATUSES = [
    QuoteStatus.PENDING_APPROVAL,
    QuoteStatus.APPROVED,
    QuoteStatus.SENT,
    QuoteStatus.FOLLOW_UP_DUE,
    QuoteStatus.NEGOTIATING,
]


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    end = datetime.combine(day, time.max, tzinfo=timezone.utc)
    return start, end


def compute_daily_metrics(db: Session, day: date | None = None) -> dict[str, Any]:
    day = day or date.today()
    start, end = _day_bounds(day)

    def count(stmt) -> int:
        return int(db.execute(stmt).scalar_one() or 0)

    rfqs_received = count(
        select(func.count(RFQ.id)).where(RFQ.created_at.between(start, end))
    )
    quotes_sent = count(
        select(func.count(Quote.id)).where(
            Quote.status == QuoteStatus.SENT, Quote.sent_at.between(start, end)
        )
    )
    pending_rates = count(
        select(func.count(RFQ.id)).where(RFQ.status == RFQStatus.WAITING_FOR_RATES)
    )
    confirmed_bookings = count(
        select(func.count(Booking.id)).where(Booking.created_at.between(start, end))
    )
    follow_ups_due = count(
        select(func.count(FollowUp.id)).where(
            FollowUp.status.in_([FollowUpStatus.PENDING, FollowUpStatus.DUE]),
            FollowUp.due_date.is_not(None),
            FollowUp.due_date <= day,
        )
    )
    lost_today = count(
        select(func.count(Quote.id)).where(
            Quote.status == QuoteStatus.LOST, Quote.updated_at.between(start, end)
        )
    )
    won_today = count(
        select(func.count(Quote.id)).where(
            Quote.status == QuoteStatus.WON, Quote.updated_at.between(start, end)
        )
    )

    pipeline = db.execute(
        select(func.coalesce(func.sum(Quote.selling_price), 0.0)).where(
            Quote.status.in_(_ACTIVE_QUOTE_STATUSES)
        )
    ).scalar_one()
    margin = db.execute(
        select(func.coalesce(func.sum(Quote.gross_margin), 0.0)).where(
            Quote.status.in_(_ACTIVE_QUOTE_STATUSES)
        )
    ).scalar_one()

    high_value = list(
        db.execute(
            select(Quote)
            .where(Quote.status.in_(_ACTIVE_QUOTE_STATUSES))
            .order_by(Quote.selling_price.desc().nullslast())
            .limit(5)
        ).scalars().all()
    )

    return {
        "date": day.isoformat(),
        "rfqs_received": rfqs_received,
        "quotes_sent": quotes_sent,
        "pending_rates": pending_rates,
        "confirmed_bookings": confirmed_bookings,
        "follow_ups_due": follow_ups_due,
        "lost_today": lost_today,
        "won_today": won_today,
        "estimated_pipeline": round(float(pipeline or 0.0), 2),
        "estimated_margin": round(float(margin or 0.0), 2),
        "high_value_opportunities": [
            {
                "quote_number": q.quote_number,
                "selling_price": q.selling_price,
                "currency": q.currency,
                "status": q.status.value,
            }
            for q in high_value
        ],
    }
