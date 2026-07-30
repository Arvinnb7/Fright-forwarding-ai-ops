"""What answering faster would be worth, using the customer's own numbers.

An ROI calculator that always produces an encouraging figure is marketing with
arithmetic on top, and a buyer who later checks it will never trust anything
else the product says. So this one is built to be able to say *no*:

* the win-rate uplift comes from **their** data — how much better they convert
  when they answer quickly, measured on their own quotes — never from an
  industry benchmark;
* if they do not have enough decided quotes to measure that, it refuses to
  project and says what is missing instead of substituting a benchmark;
* if their fast quotes do not convert better than their slow ones, the model
  reports no benefit. That is a real possible answer;
* the two assumptions it cannot measure (gross profit per shipment, and what
  counts as "fast") are inputs, stated on the output, not buried constants.

Everything else is measured. The output separates the two so a reader can see
exactly which numbers are theirs and which are ours.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.services.performance import RESPONSE_BUCKETS, compute_performance

# Below this there is not enough evidence to say anything about conversion, and
# a projection built on three quotes is a guess wearing a suit.
MIN_DECIDED_QUOTES = 10
MIN_DECIDED_PER_GROUP = 4
MIN_ENQUIRIES = 20


@dataclass
class RoiAssumptions:
    """The inputs the system cannot know. Defaults are conservative and are
    always echoed back on the result so a reader can challenge them."""

    gross_profit_per_shipment: float = 400.0
    fast_response_hours: float = 4.0
    subscription_per_user_per_month: float = 99.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "gross_profit_per_shipment": self.gross_profit_per_shipment,
            "fast_response_hours": self.fast_response_hours,
            "subscription_per_user_per_month": self.subscription_per_user_per_month,
        }


def _bucket_bounds(label: str) -> tuple[float, float]:
    for name, low, high in RESPONSE_BUCKETS:
        if name == label:
            return low, high
    return 0.0, 0.0


def _split_by_speed(
    buckets: list[dict[str, Any]], threshold_hours: float
) -> tuple[dict[str, int], dict[str, int]]:
    """Group the response-time buckets into 'fast' and 'slow' at the threshold."""
    fast = {"quoted": 0, "won": 0}
    slow = {"quoted": 0, "won": 0}
    for bucket in buckets:
        _, high = _bucket_bounds(bucket["label"])
        target = fast if high <= threshold_hours else slow
        target["quoted"] += bucket["quoted"]
        target["won"] += bucket["won"]
    return fast, slow


def compute_roi(
    db: Session,
    start: date,
    end: date,
    assumptions: RoiAssumptions | None = None,
    *,
    active_users: int | None = None,
) -> dict[str, Any]:
    """Measure the desk, then model what closing the gap would be worth."""
    assumptions = assumptions or RoiAssumptions()
    performance = compute_performance(db, start, end)
    days = max(performance["days"], 1)

    received = performance["rfqs_received"]
    quoted = performance["rfqs_quoted"]
    won = performance["quotes_won"]
    lost = performance["quotes_lost"]
    decided = won + lost

    fast, slow = _split_by_speed(
        performance["win_rate_by_response_time"], assumptions.fast_response_hours
    )
    measured: dict[str, Any] = {
        "window_days": days,
        "enquiries_received": received,
        "enquiries_answered": quoted,
        "enquiries_unanswered": performance["unanswered_total"],
        "response_rate": performance["response_rate"],
        "median_response_hours": performance["median_response_hours"],
        "p90_response_hours": performance["p90_response_hours"],
        "quotes_won": won,
        "quotes_lost": lost,
        "win_rate": performance["win_rate"],
        "fast_quotes": fast["quoted"],
        "fast_wins": fast["won"],
        "slow_quotes": slow["quoted"],
        "slow_wins": slow["won"],
        "enquiries_per_working_day": round(received / days, 2) if days else 0.0,
    }

    blockers = _insufficient_data(received, decided, fast, slow)
    if blockers:
        return {
            "start_date": performance["start_date"],
            "end_date": performance["end_date"],
            "assumptions": assumptions.as_dict(),
            "measured": measured,
            "projection": None,
            "confidence": "insufficient_data",
            "blockers": blockers,
            "narrative": [
                "Not enough history yet to say what faster answers would be worth here.",
                *blockers,
                "Keep running for a few more weeks; the numbers above are already real.",
            ],
        }

    fast_win_rate = fast["won"] / fast["quoted"]
    slow_win_rate = slow["won"] / slow["quoted"] if slow["quoted"] else 0.0

    # The counterfactual: every enquiry answered, and answered inside the fast
    # threshold — converting at the rate this desk already achieves when it is
    # fast. Nothing here is borrowed from another company.
    projected_wins_in_window = received * fast_win_rate
    additional_wins_in_window = max(projected_wins_in_window - won, 0.0)

    per_year = 365.0 / days
    additional_wins_per_year = additional_wins_in_window * per_year
    annual_gross_profit = additional_wins_per_year * assumptions.gross_profit_per_shipment

    seats = active_users if active_users is not None else max(measured_users(performance), 1)
    annual_subscription = seats * assumptions.subscription_per_user_per_month * 12

    projection = {
        "fast_win_rate": round(fast_win_rate * 100, 1),
        "slow_win_rate": round(slow_win_rate * 100, 1),
        "uplift_points": round((fast_win_rate - slow_win_rate) * 100, 1),
        "additional_wins_in_window": round(additional_wins_in_window, 1),
        "additional_wins_per_year": round(additional_wins_per_year, 1),
        "annual_gross_profit": round(annual_gross_profit, 2),
        "seats": seats,
        "annual_subscription": round(annual_subscription, 2),
        "net_annual_value": round(annual_gross_profit - annual_subscription, 2),
        "return_multiple": (
            round(annual_gross_profit / annual_subscription, 1)
            if annual_subscription > 0
            else None
        ),
    }

    return {
        "start_date": performance["start_date"],
        "end_date": performance["end_date"],
        "assumptions": assumptions.as_dict(),
        "measured": measured,
        "projection": projection,
        "confidence": "measured" if decided >= 2 * MIN_DECIDED_QUOTES else "indicative",
        "blockers": [],
        "narrative": list(_narrate(measured, projection, assumptions)),
    }


def measured_users(performance: dict[str, Any]) -> int:
    return int(performance.get("active_users") or 1)


def _insufficient_data(
    received: int, decided: int, fast: dict[str, int], slow: dict[str, int]
) -> list[str]:
    """Say precisely what is missing, rather than projecting anyway."""
    blockers = []
    if received < MIN_ENQUIRIES:
        blockers.append(
            f"Only {received} enquiries in this period; at least {MIN_ENQUIRIES} are "
            "needed before a response-rate gap means anything."
        )
    if decided < MIN_DECIDED_QUOTES:
        blockers.append(
            f"Only {decided} quotations have been marked won or lost; at least "
            f"{MIN_DECIDED_QUOTES} are needed to measure a win rate."
        )
    if fast["quoted"] < MIN_DECIDED_PER_GROUP:
        blockers.append(
            f"Only {fast['quoted']} enquiries were answered quickly; at least "
            f"{MIN_DECIDED_PER_GROUP} are needed to know how well fast answers convert."
        )
    if slow["quoted"] < MIN_DECIDED_PER_GROUP:
        blockers.append(
            f"Only {slow['quoted']} enquiries were answered slowly; without a "
            "comparison group there is nothing to compare fast answers against."
        )
    return blockers


def _narrate(measured: dict[str, Any], projection: dict[str, Any], assumptions: RoiAssumptions):
    """Plain sentences for the one-pager — including the unflattering ones."""
    yield (
        f"Over {measured['window_days']} days you received "
        f"{measured['enquiries_received']} enquiries and answered "
        f"{measured['enquiries_answered']} of them "
        f"({measured['response_rate']}%). "
        f"{measured['enquiries_unanswered']} were never answered."
    )
    if measured["median_response_hours"] is not None:
        yield (
            f"Median time to first quotation was "
            f"{measured['median_response_hours']}h "
            f"(90th percentile {measured['p90_response_hours']}h)."
        )

    if projection["uplift_points"] <= 0:
        yield (
            f"Your own data does not show faster answers converting better: "
            f"{projection['fast_win_rate']}% within "
            f"{assumptions.fast_response_hours:g}h against "
            f"{projection['slow_win_rate']}% after. On this evidence, speed is not "
            "what is costing you these deals — look at pricing or lane coverage "
            "before buying anything to make you faster."
        )
        return

    yield (
        f"When you answer within {assumptions.fast_response_hours:g}h you win "
        f"{projection['fast_win_rate']}% of the time, against "
        f"{projection['slow_win_rate']}% when you are slower — "
        f"{projection['uplift_points']} points."
    )
    yield (
        f"Answering every enquiry at that speed would have won about "
        f"{projection['additional_wins_in_window']} more shipments in this period, "
        f"or roughly {projection['additional_wins_per_year']} a year."
    )
    yield (
        f"At {assumptions.gross_profit_per_shipment:,.0f} gross profit per shipment "
        f"— your figure, not ours — that is about "
        f"{projection['annual_gross_profit']:,.0f} a year, against "
        f"{projection['annual_subscription']:,.0f} for "
        f"{projection['seats']} seat(s)."
    )


def render_one_pager(roi: dict[str, Any], company: str) -> str:
    """The one-pager, as text — generated from the numbers above, not written
    in advance and decorated with them."""
    lines = [
        f"Response-time review — {company}",
        f"Period: {roi['start_date']} to {roi['end_date']}",
        "",
        "MEASURED (from your own records)",
    ]
    measured = roi["measured"]
    lines += [
        f"  Enquiries received                {measured['enquiries_received']}",
        f"  Answered                          {measured['enquiries_answered']}"
        f" ({measured['response_rate']}%)",
        f"  Never answered                    {measured['enquiries_unanswered']}",
        f"  Median time to first quotation    {measured['median_response_hours']}h",
        f"  90th percentile                   {measured['p90_response_hours']}h",
        f"  Quotations won / lost             {measured['quotes_won']} / {measured['quotes_lost']}",
        "",
    ]

    if roi["projection"] is None:
        lines.append("NOT YET ENOUGH DATA TO PROJECT A VALUE")
        lines += [f"  - {blocker}" for blocker in roi["blockers"]]
    else:
        projection = roi["projection"]
        assumptions = roi["assumptions"]
        lines += [
            "ASSUMED (change these if they are wrong)",
            f"  Gross profit per shipment         "
            f"{assumptions['gross_profit_per_shipment']:,.0f}",
            f"  'Fast' means answered within      "
            f"{assumptions['fast_response_hours']:g}h",
            f"  Subscription per user per month   "
            f"{assumptions['subscription_per_user_per_month']:,.0f}",
            "",
            "PROJECTED (your win rates applied to every enquiry)",
            f"  Win rate when fast                {projection['fast_win_rate']}%",
            f"  Win rate when slow                {projection['slow_win_rate']}%",
            f"  Additional shipments per year     {projection['additional_wins_per_year']}",
            f"  Additional gross profit per year  {projection['annual_gross_profit']:,.0f}",
            f"  Subscription per year             {projection['annual_subscription']:,.0f}",
            f"  Net                               {projection['net_annual_value']:,.0f}",
            "",
        ]

    lines += ["", "IN PLAIN WORDS"]
    lines += [f"  {sentence}" for sentence in roi["narrative"]]
    lines += [
        "",
        "The projection uses this company's own win rates by response speed. No",
        "industry averages are used in the arithmetic. If the measured uplift were",
        "zero or negative, this page would say so.",
    ]
    return "\n".join(lines)
