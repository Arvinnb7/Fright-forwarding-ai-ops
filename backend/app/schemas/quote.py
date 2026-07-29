"""Quotation schemas, including the human-approval payloads."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import QuoteStatus
from app.services.margin import MarkupType


class QuoteStart(BaseModel):
    rfq_id: int
    selected_rate_id: int | None = None
    cost_amount: float | None = None  # used if no rate selected
    currency: str | None = None
    markup_type: MarkupType = MarkupType.PERCENT
    markup_value: float | None = None  # defaults to company default
    validity_days: int = 14


class QuotePricingReview(BaseModel):
    """What the coordinator reviews while the graph is paused for approval."""

    quote_id: int
    cost_amount: float | None
    selling_price: float | None
    gross_margin: float | None
    gross_margin_percentage: float | None
    currency: str
    warnings: list[str]
    draft_text: str


class QuoteApprove(BaseModel):
    approved: bool
    # Optional human edits applied on approval.
    selling_price: float | None = None
    quote_text: str | None = None
    mark_sent: bool = False
    lost_reason: str | None = None  # when rejecting


class QuoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    quote_number: str | None
    rfq_id: int | None
    customer_id: int | None
    selected_rate_id: int | None
    cost_amount: float | None
    selling_price: float | None
    currency: str
    gross_margin: float | None
    gross_margin_percentage: float | None
    validity_date: date | None
    quote_text: str | None
    status: QuoteStatus
    sent_at: datetime | None
    next_follow_up_date: date | None
    lost_reason: str | None
    owner_id: int | None
    created_at: datetime
    updated_at: datetime
