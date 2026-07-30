"""Speed-to-quote reporting schemas.

Rates are ``None`` rather than ``0`` when there is nothing to divide by, so the
dashboard can show "no data yet" instead of a zero that reads as failure.
"""
from __future__ import annotations

from pydantic import BaseModel


class ResponseBucket(BaseModel):
    label: str
    quoted: int
    won: int
    win_rate: float | None


class UnansweredRFQ(BaseModel):
    rfq_id: int
    reference: str | None
    lane: str
    asked_at: str
    waiting_hours: float


class DailyPoint(BaseModel):
    date: str
    rfqs: int
    quoted: int
    median_response_hours: float | None


class PerformanceReport(BaseModel):
    start_date: str
    end_date: str
    days: int

    rfqs_received: int
    rfqs_quoted: int
    response_rate: float | None
    median_response_hours: float | None
    p90_response_hours: float | None
    fastest_response_hours: float | None
    slowest_response_hours: float | None

    quotes_sent: int
    quotes_per_day: float
    active_users: int
    quotes_per_user_per_day: float | None

    quotes_won: int
    quotes_lost: int
    win_rate: float | None
    win_rate_by_response_time: list[ResponseBucket]

    follow_ups_due: int
    follow_ups_actioned: int
    follow_up_compliance: float | None

    unanswered_rfqs: list[UnansweredRFQ]
    unanswered_total: int
    daily: list[DailyPoint]


# ── ROI (see app/services/roi.py) ────────────────────────────


class RoiAssumptionsOut(BaseModel):
    gross_profit_per_shipment: float
    fast_response_hours: float
    subscription_per_user_per_month: float


class RoiMeasured(BaseModel):
    """Everything here comes from the customer's own records."""

    window_days: int
    enquiries_received: int
    enquiries_answered: int
    enquiries_unanswered: int
    response_rate: float | None
    median_response_hours: float | None
    p90_response_hours: float | None
    quotes_won: int
    quotes_lost: int
    win_rate: float | None
    fast_quotes: int
    fast_wins: int
    slow_quotes: int
    slow_wins: int
    enquiries_per_working_day: float


class RoiProjection(BaseModel):
    """Their win rates applied to every enquiry. No industry averages."""

    fast_win_rate: float
    slow_win_rate: float
    uplift_points: float
    additional_wins_in_window: float
    additional_wins_per_year: float
    annual_gross_profit: float
    seats: int
    annual_subscription: float
    net_annual_value: float
    return_multiple: float | None


class RoiReport(BaseModel):
    start_date: str
    end_date: str
    assumptions: RoiAssumptionsOut
    measured: RoiMeasured
    # None when there is not enough history; `blockers` then says what is missing
    # rather than a number being produced anyway.
    projection: RoiProjection | None
    confidence: str
    blockers: list[str]
    narrative: list[str]
