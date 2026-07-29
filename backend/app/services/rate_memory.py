"""Rate memory — what we already know about this lane.

The response-time promise only holds if the price is already in the building. A
desk that must email a carrier and wait has handed the clock back to somebody
else, and W2's numbers will say so. So when an enquiry arrives on a lane that
has been quoted before, the prior rates — and what was actually charged and
whether it was won — are put in front of the coordinator immediately.

Deliberate limits, because a suggestion becomes a price a customer is given:

* Nothing is auto-applied. A suggestion is a starting point a human accepts.
* Exact-lane matches and same-route-but-different-equipment matches are
  returned separately and labelled, never blended.
* Expired rates are still shown — a three-month-old price is real information
  when the alternative is no information — but they are marked as expired and
  ranked below live ones, never silently presented as current.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.partner_rate import PartnerRate, RateSource
from app.models.quote import Quote
from app.models.rfq import RFQ
from app.services.lanes import describe_lane

# Beyond this the number is history rather than a rate; still shown, but the UI
# and the caller can tell how stale it is.
DEFAULT_LOOKBACK_DAYS = 365
DEFAULT_LIMIT = 8


@dataclass
class RateSuggestion:
    rate_id: int
    match: str  # "exact" (same lane) or "route" (same route, different equipment)
    partner_name: str
    partner_type: str | None
    source: str
    lane: str
    cost_amount: float | None
    currency: str
    transit_time: str | None
    age_days: int
    validity_date: date | None
    is_expired: bool
    notes: str | None
    rfq_id: int | None
    rfq_reference: str | None
    quoted_selling_price: float | None
    outcome: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "rate_id": self.rate_id,
            "match": self.match,
            "partner_name": self.partner_name,
            "partner_type": self.partner_type,
            "source": self.source,
            "lane": self.lane,
            "cost_amount": self.cost_amount,
            "currency": self.currency,
            "transit_time": self.transit_time,
            "age_days": self.age_days,
            "validity_date": self.validity_date.isoformat() if self.validity_date else None,
            "is_expired": self.is_expired,
            "notes": self.notes,
            "rfq_id": self.rfq_id,
            "rfq_reference": self.rfq_reference,
            "quoted_selling_price": self.quoted_selling_price,
            "outcome": self.outcome,
        }


def _age_days(created_at: datetime, today: datetime) -> int:
    return max((today - created_at).days, 0)


def _outcome_for(quote: Quote | None) -> str | None:
    if quote is None:
        return None
    return quote.status.value


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return round(float(ordered[middle]), 2)
    return round((ordered[middle - 1] + ordered[middle]) / 2.0, 2)


def suggest_rates_for_rfq(
    db: Session,
    rfq: RFQ,
    *,
    limit: int = DEFAULT_LIMIT,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    today: datetime | None = None,
) -> dict[str, Any]:
    """Prior rates for this RFQ's lane, best and freshest first."""
    today = today or datetime.now(timezone.utc)
    lane = describe_lane(
        rfq.origin, rfq.destination, rfq.transport_mode, rfq.container_type
    )

    if not rfq.route_key:
        # No route, no lane. Matching on a half-known route would surface rates
        # from everywhere, which is worse than surfacing nothing.
        return {
            "lane": lane,
            "lane_known": False,
            "exact_matches": 0,
            "route_matches": 0,
            "median_cost": None,
            "suggestions": [],
        }

    cutoff = today.date() - timedelta(days=lookback_days)
    candidates = list(
        db.execute(
            select(PartnerRate)
            .where(
                PartnerRate.route_key == rfq.route_key,
                PartnerRate.cost_amount.is_not(None),
                PartnerRate.rfq_id.is_distinct_from(rfq.id),
            )
            .order_by(PartnerRate.created_at.desc())
        ).scalars().all()
    )
    candidates = [rate for rate in candidates if rate.created_at.date() >= cutoff]

    # What we charged and how it went, for the enquiries these rates came from.
    quote_by_rfq: dict[int, Quote] = {}
    rfq_ids = {rate.rfq_id for rate in candidates if rate.rfq_id is not None}
    if rfq_ids:
        for quote in db.execute(
            select(Quote).where(Quote.rfq_id.in_(rfq_ids)).order_by(Quote.id)
        ).scalars().all():
            quote_by_rfq[quote.rfq_id] = quote

    references: dict[int, str | None] = {}
    if rfq_ids:
        references = {
            row[0]: row[1]
            for row in db.execute(
                select(RFQ.id, RFQ.reference).where(RFQ.id.in_(rfq_ids))
            ).all()
        }

    suggestions: list[RateSuggestion] = []
    for rate in candidates:
        quote = quote_by_rfq.get(rate.rfq_id) if rate.rfq_id else None
        expired = bool(rate.validity_date and rate.validity_date < today.date())
        suggestions.append(
            RateSuggestion(
                rate_id=rate.id,
                match="exact" if rate.lane_key == rfq.lane_key else "route",
                partner_name=rate.partner_name,
                partner_type=rate.partner_type.value if rate.partner_type else None,
                source=rate.source.value if rate.source else RateSource.PARTNER_QUOTE.value,
                lane=describe_lane(
                    rate.origin, rate.destination, rate.transport_mode, rate.container_type
                ),
                cost_amount=rate.cost_amount,
                currency=rate.currency,
                transit_time=rate.transit_time,
                age_days=_age_days(rate.created_at, today),
                validity_date=rate.validity_date,
                is_expired=expired,
                notes=rate.notes,
                rfq_id=rate.rfq_id,
                rfq_reference=references.get(rate.rfq_id) if rate.rfq_id else None,
                quoted_selling_price=quote.selling_price if quote else None,
                outcome=_outcome_for(quote),
            )
        )

    # Exact lane first, then still-valid, then freshest. A live exact rate is
    # the one that lets a coordinator answer without asking anybody.
    suggestions.sort(
        key=lambda item: (item.match != "exact", item.is_expired, item.age_days)
    )

    exact = [item for item in suggestions if item.match == "exact"]
    return {
        "lane": lane,
        "lane_known": True,
        "exact_matches": len(exact),
        "route_matches": len(suggestions) - len(exact),
        # Median of exact-lane costs only — mixing equipment types would produce
        # a number that is not a price for anything.
        "median_cost": _median(
            [item.cost_amount for item in exact if item.cost_amount is not None]
        ),
        "suggestions": [item.as_dict() for item in suggestions[:limit]],
    }


def copy_rate_to_rfq(db: Session, source: PartnerRate, rfq: RFQ) -> PartnerRate:
    """Reuse a remembered rate on a new enquiry.

    A copy, not a link: the coordinator will adjust it, and the original has to
    stay exactly as the partner gave it.
    """
    copied = PartnerRate(
        rfq_id=rfq.id,
        partner_name=source.partner_name,
        partner_type=source.partner_type,
        source=source.source,
        origin=rfq.origin,
        destination=rfq.destination,
        transport_mode=rfq.transport_mode,
        container_type=rfq.container_type,
        lane_key=rfq.lane_key,
        route_key=rfq.route_key,
        cost_amount=source.cost_amount,
        currency=source.currency,
        included_charges=source.included_charges,
        excluded_charges=source.excluded_charges,
        transit_time=source.transit_time,
        validity_date=source.validity_date,
        free_time=source.free_time,
        notes=_reuse_note(source),
        risk_notes=source.risk_notes,
        reliability_score=source.reliability_score,
    )
    db.add(copied)
    db.commit()
    db.refresh(copied)
    return copied


def _reuse_note(source: PartnerRate) -> str:
    """Always record where a reused number came from — a price nobody can trace
    is a price nobody will stand behind."""
    origin = (
        f"tariff sheet ({source.partner_name})"
        if source.source == RateSource.TARIFF
        else f"rate #{source.id} on {describe_lane(source.origin, source.destination)}"
    )
    stamp = source.created_at.date().isoformat() if source.created_at else "unknown date"
    note = f"Reused from {origin}, entered {stamp}. Confirm before quoting."
    return f"{source.notes}\n{note}" if source.notes else note


def lane_coverage(db: Session, *, limit: int = 50) -> list[dict[str, Any]]:
    """Lanes we can already price, most-used first.

    This is the honest answer to "how much of my business can this actually
    quote instantly?" — and the gap list that says where to load a tariff.
    """
    today = date.today()
    rows = list(
        db.execute(
            select(PartnerRate).where(
                PartnerRate.lane_key.is_not(None), PartnerRate.cost_amount.is_not(None)
            )
        ).scalars().all()
    )

    grouped: dict[str, dict[str, Any]] = {}
    for rate in rows:
        entry = grouped.setdefault(
            rate.lane_key,
            {
                "lane_key": rate.lane_key,
                "lane": describe_lane(
                    rate.origin, rate.destination, rate.transport_mode, rate.container_type
                ),
                "rate_count": 0,
                "live_rate_count": 0,
                "partners": set(),
                "costs": [],
                "newest_days": None,
            },
        )
        entry["rate_count"] += 1
        entry["partners"].add(rate.partner_name)
        entry["costs"].append(rate.cost_amount)
        if not rate.validity_date or rate.validity_date >= today:
            entry["live_rate_count"] += 1
        age = (today - rate.created_at.date()).days
        if entry["newest_days"] is None or age < entry["newest_days"]:
            entry["newest_days"] = age

    enquiry_counts = {
        row[0]: row[1]
        for row in db.execute(
            select(RFQ.lane_key, func.count(RFQ.id))
            .where(RFQ.lane_key.is_not(None))
            .group_by(RFQ.lane_key)
        ).all()
    }

    coverage = [
        {
            "lane_key": entry["lane_key"],
            "lane": entry["lane"],
            "rate_count": entry["rate_count"],
            "live_rate_count": entry["live_rate_count"],
            "partner_count": len(entry["partners"]),
            "median_cost": _median(entry["costs"]),
            "newest_rate_days": entry["newest_days"],
            "enquiries": enquiry_counts.get(entry["lane_key"], 0),
        }
        for entry in grouped.values()
    ]
    coverage.sort(key=lambda item: (-item["enquiries"], -item["rate_count"]))
    return coverage[:limit]
