"""Follow-up cadence (spec §8): Day 0 sent → follow-ups on days 1, 3, 5, 7.

When a follow-up is completed (marked Sent), the next one in the cadence is
scheduled automatically. After the final one, the cadence stops — the quote
goes cold unless the customer replies.
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import FollowUpStatus
from app.models.follow_up import FollowUp
from app.models.quote import Quote

# Days after the quote was sent on which each follow-up is due.
CADENCE_DAYS: list[int] = [1, 3, 5, 7]


def schedule_next_follow_up(db: Session, completed: FollowUp) -> FollowUp | None:
    """Schedule the next cadence step after `completed` was sent.

    Returns the new FollowUp, or None when the cadence is exhausted.
    Caller commits.
    """
    quote = db.get(Quote, completed.quote_id)
    if quote is None:
        return None

    existing = int(
        db.execute(
            select(func.count(FollowUp.id)).where(FollowUp.quote_id == quote.id)
        ).scalar_one()
    )
    if existing >= len(CADENCE_DAYS):
        quote.next_follow_up_date = None  # cadence exhausted → cold unless reply
        return None

    base = quote.sent_at.date() if quote.sent_at else date.today()
    due = base + timedelta(days=CADENCE_DAYS[existing])
    if due <= date.today():
        due = date.today() + timedelta(days=1)  # never schedule in the past

    next_fu = FollowUp(
        quote_id=quote.id,
        customer_id=quote.customer_id,
        due_date=due,
        status=FollowUpStatus.PENDING,
    )
    db.add(next_fu)
    quote.next_follow_up_date = due
    return next_fu
