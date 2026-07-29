"""Speed-to-quote metrics — the numbers the commercial case is made of.

Freight enquiries are won or lost on the clock long before they are won or lost
on price: the first credible responder takes most of the business, and an
enquiry answered days later has usually already been priced by someone else.
This module measures exactly that, from the database, with no model in the
loop, so the figures can be put in front of a buyer and defended.

Two definitions matter and are applied consistently:

* **Asked at** — when the customer wrote (``RFQ.received_at``), falling back to
  when the record was created for RFQs entered by hand. Never the time we got
  around to processing it, which would flatter every number here.
* **Answered at** — when the *first* quotation was sent
  (``RFQ.first_quoted_at``). A revised quote sent later cannot retroactively
  make a slow response look fast.

Everything is computed inside the caller's organization scope, so a hosted
deployment reports each customer only their own performance.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Iterable, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.tenancy import get_current_org_id
from app.models.enums import FollowUpStatus, QuoteStatus
from app.models.follow_up import FollowUp
from app.models.quote import Quote
from app.models.rfq import RFQ
from app.models.user import User

# Response-time buckets. The boundaries are the ones the industry data is
# quoted against (under an hour, same working session, same day, next day,
# later), so the table can be read straight into a sales conversation.
RESPONSE_BUCKETS: list[tuple[str, float, float]] = [
    ("Under 1 hour", 0.0, 1.0),
    ("1–4 hours", 1.0, 4.0),
    ("4–24 hours", 4.0, 24.0),
    ("1–3 days", 24.0, 72.0),
    ("Over 3 days", 72.0, float("inf")),
]

# Follow-ups that were dealt with, rather than left sitting past their date.
_ACTIONED_FOLLOW_UP_STATUSES = [
    FollowUpStatus.SENT,
    FollowUpStatus.REPLIED,
    FollowUpStatus.COLD,
    FollowUpStatus.CLOSED,
]

_UNANSWERED_SAMPLE = 10


def percentile(values: Sequence[float], fraction: float) -> float | None:
    """Linear-interpolated percentile (the convention spreadsheets use).

    Written as a pure function so the arithmetic behind a published median or
    p90 can be checked without a database.
    """
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    position = fraction * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return float(ordered[lower] * (1 - weight) + ordered[upper] * weight)


def bucket_for(hours: float) -> str:
    for label, low, high in RESPONSE_BUCKETS:
        if low <= hours < high:
            return label
    return RESPONSE_BUCKETS[-1][0]


def _day_range(start: date, end: date) -> tuple[datetime, datetime]:
    return (
        datetime.combine(start, time.min, tzinfo=timezone.utc),
        datetime.combine(end, time.max, tzinfo=timezone.utc),
    )


def _asked_at_column():
    """When the customer asked, with a fallback for hand-entered RFQs."""
    return func.coalesce(RFQ.received_at, RFQ.created_at)


def _hours_between(asked: datetime, answered: datetime) -> float:
    return max((answered - asked).total_seconds() / 3600.0, 0.0)


def _round(value: float | None, digits: int = 1) -> float | None:
    return None if value is None else round(value, digits)


def _rate(numerator: int, denominator: int) -> float | None:
    """A percentage, or None when there is nothing to divide by.

    Reporting 0% for an empty period would read as failure rather than as
    "no data", which is the kind of number that destroys trust in a dashboard.
    """
    if denominator <= 0:
        return None
    return round(100.0 * numerator / denominator, 1)


def compute_performance(
    db: Session, start: date, end: date, *, now: datetime | None = None
) -> dict[str, Any]:
    """Speed and conversion metrics for the RFQs received in [start, end]."""
    now = now or datetime.now(timezone.utc)
    window_start, window_end = _day_range(start, end)
    days = (end - start).days + 1
    asked_at = _asked_at_column()

    rfq_rows = db.execute(
        select(RFQ.id, asked_at, RFQ.first_quoted_at, RFQ.reference, RFQ.origin, RFQ.destination)
        .where(asked_at.between(window_start, window_end))
        .order_by(asked_at)
    ).all()

    won_rfq_ids = {
        row[0]
        for row in db.execute(
            select(Quote.rfq_id).where(
                Quote.rfq_id.is_not(None), Quote.status == QuoteStatus.WON
            )
        ).all()
    }

    response_hours: list[float] = []
    per_bucket: dict[str, dict[str, int]] = {
        label: {"quoted": 0, "won": 0} for label, _, _ in RESPONSE_BUCKETS
    }
    unanswered: list[dict[str, Any]] = []
    daily: dict[date, dict[str, Any]] = {
        start + timedelta(days=offset): {"rfqs": 0, "quoted": 0, "hours": []}
        for offset in range(days)
    }

    for rfq_id, asked, answered, reference, origin, destination in rfq_rows:
        day = asked.date()
        if day in daily:
            daily[day]["rfqs"] += 1

        if answered is None:
            unanswered.append(
                {
                    "rfq_id": rfq_id,
                    "reference": reference,
                    "lane": f"{origin or '?'} → {destination or '?'}",
                    "asked_at": asked.isoformat(),
                    "waiting_hours": _round(_hours_between(asked, now)),
                }
            )
            continue

        hours = _hours_between(asked, answered)
        response_hours.append(hours)
        label = bucket_for(hours)
        per_bucket[label]["quoted"] += 1
        if rfq_id in won_rfq_ids:
            per_bucket[label]["won"] += 1
        if day in daily:
            daily[day]["quoted"] += 1
            daily[day]["hours"].append(hours)

    rfqs_received = len(rfq_rows)
    rfqs_quoted = len(response_hours)

    quotes_sent = int(
        db.execute(
            select(func.count(Quote.id)).where(
                Quote.sent_at.between(window_start, window_end)
            )
        ).scalar_one()
        or 0
    )
    quotes_won = int(
        db.execute(
            select(func.count(Quote.id)).where(
                Quote.status == QuoteStatus.WON,
                Quote.sent_at.between(window_start, window_end),
            )
        ).scalar_one()
        or 0
    )
    quotes_lost = int(
        db.execute(
            select(func.count(Quote.id)).where(
                Quote.status == QuoteStatus.LOST,
                Quote.sent_at.between(window_start, window_end),
            )
        ).scalar_one()
        or 0
    )

    # `User` is deliberately outside the automatic tenant filter (it has to be
    # readable before the organization is known, at login), so this one has to
    # be scoped by hand — otherwise a hosted deployment would divide by every
    # user on the platform.
    org_id = get_current_org_id(db)
    active_users = int(
        db.execute(
            select(func.count(User.id)).where(
                User.is_active.is_(True), User.organization_id == org_id
            )
        ).scalar_one()
        or 0
    )

    follow_ups_due = list(
        db.execute(
            select(FollowUp.status).where(
                FollowUp.due_date.is_not(None),
                FollowUp.due_date.between(start, end),
            )
        ).scalars().all()
    )
    follow_ups_actioned = sum(
        1 for status in follow_ups_due if status in _ACTIONED_FOLLOW_UP_STATUSES
    )

    unanswered.sort(key=lambda item: item["waiting_hours"], reverse=True)

    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "days": days,
        # ── Speed ────────────────────────────────────────────
        "rfqs_received": rfqs_received,
        "rfqs_quoted": rfqs_quoted,
        "response_rate": _rate(rfqs_quoted, rfqs_received),
        "median_response_hours": _round(percentile(response_hours, 0.5)),
        "p90_response_hours": _round(percentile(response_hours, 0.9)),
        "fastest_response_hours": _round(min(response_hours)) if response_hours else None,
        "slowest_response_hours": _round(max(response_hours)) if response_hours else None,
        # ── Throughput ───────────────────────────────────────
        "quotes_sent": quotes_sent,
        "quotes_per_day": round(quotes_sent / days, 2) if days else 0.0,
        "active_users": active_users,
        "quotes_per_user_per_day": (
            round(quotes_sent / days / active_users, 2) if days and active_users else None
        ),
        # ── Conversion ───────────────────────────────────────
        "quotes_won": quotes_won,
        "quotes_lost": quotes_lost,
        "win_rate": _rate(quotes_won, quotes_won + quotes_lost),
        "win_rate_by_response_time": [
            {
                "label": label,
                "quoted": per_bucket[label]["quoted"],
                "won": per_bucket[label]["won"],
                "win_rate": _rate(per_bucket[label]["won"], per_bucket[label]["quoted"]),
            }
            for label, _, _ in RESPONSE_BUCKETS
        ],
        # ── Discipline ───────────────────────────────────────
        "follow_ups_due": len(follow_ups_due),
        "follow_ups_actioned": follow_ups_actioned,
        "follow_up_compliance": _rate(follow_ups_actioned, len(follow_ups_due)),
        # ── What to do about it ──────────────────────────────
        "unanswered_rfqs": unanswered[:_UNANSWERED_SAMPLE],
        "unanswered_total": len(unanswered),
        "daily": [
            {
                "date": day.isoformat(),
                "rfqs": values["rfqs"],
                "quoted": values["quoted"],
                "median_response_hours": _round(percentile(values["hours"], 0.5)),
            }
            for day, values in sorted(daily.items())
        ],
    }


def summarize_for_report(metrics: dict[str, Any]) -> Iterable[str]:
    """Plain-language lines for the daily report and the ROI one-pager."""
    if metrics["response_rate"] is None:
        yield "No enquiries were received in this period."
        return
    yield (
        f"{metrics['rfqs_quoted']} of {metrics['rfqs_received']} enquiries were "
        f"answered ({metrics['response_rate']}%)."
    )
    if metrics["median_response_hours"] is not None:
        yield (
            f"Median response time {metrics['median_response_hours']}h, "
            f"90th percentile {metrics['p90_response_hours']}h."
        )
    if metrics["unanswered_total"]:
        yield (
            f"{metrics['unanswered_total']} enquiries are still unanswered — "
            "each one is a quote a competitor is writing instead."
        )
