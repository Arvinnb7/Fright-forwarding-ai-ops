"""Orchestration for the quotation builder + human-approval flow.

Bridges the LangGraph quote graph (which pauses at the pricing interrupt) and the
database Quote record. The thread_id is derived from the quote id so the run can
be resumed in a later request.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from langgraph.types import Command
from sqlalchemy.orm import Session

from app.agents.quote_builder import get_quote_graph
from app.core.config import settings
from app.core.logging import get_logger
from app.llm.base import LLMClient
from app.models.enums import FollowUpStatus, QuoteStatus, RFQStatus
from app.models.follow_up import FollowUp
from app.models.partner_rate import PartnerRate
from app.models.quote import Quote
from app.models.rfq import RFQ
from app.schemas.quote import QuoteApprove, QuotePricingReview, QuoteStart
from app.services.context import rfq_context
from app.services.reference import sequence_for
from app.services.reference import quote_number as make_quote_number

log = get_logger("service.quote")


def _thread_config(quote_id: int, llm: LLMClient | None = None) -> dict:
    configurable: dict = {"thread_id": f"quote-{quote_id}"}
    if llm is not None:
        configurable["llm"] = llm
    return {"configurable": configurable}


def start_quote(
    db: Session, payload: QuoteStart, llm: LLMClient
) -> tuple[Quote, QuotePricingReview]:
    rfq = db.get(RFQ, payload.rfq_id)
    if rfq is None:
        raise ValueError("RFQ not found")

    rate: PartnerRate | None = None
    if payload.selected_rate_id is not None:
        rate = db.get(PartnerRate, payload.selected_rate_id)
        if rate is None or rate.rfq_id != rfq.id:
            raise ValueError("Selected rate not found for this RFQ")

    cost_amount = rate.cost_amount if rate else payload.cost_amount
    if cost_amount is None:
        raise ValueError("A cost amount (or a selected rate with a cost) is required")
    currency = payload.currency or (rate.currency if rate else settings.default_currency)
    markup_value = (
        payload.markup_value
        if payload.markup_value is not None
        else settings.default_markup_percent
    )
    validity = date.today() + timedelta(days=payload.validity_days)

    # Create the quote row first so we have an id → stable thread_id.
    quote = Quote(
        rfq_id=rfq.id,
        customer_id=rfq.customer_id,
        selected_rate_id=rate.id if rate else None,
        cost_amount=cost_amount,
        currency=currency,
        validity_date=validity,
        status=QuoteStatus.DRAFT,
    )
    db.add(quote)
    db.flush()
    quote.quote_number = make_quote_number(
        sequence_for(db, Quote, quote.org_id, quote.id)
    )
    db.commit()

    graph = get_quote_graph()
    config = _thread_config(quote.id, llm)
    graph.invoke(
        {
            "quote_id": quote.id,
            "quote_number": quote.quote_number,
            "rfq_context": rfq_context(rfq),
            "cost_amount": float(cost_amount),
            "currency": currency,
            "markup_type": payload.markup_type.value,
            "markup_value": float(markup_value),
            "validity_date": validity.isoformat(),
            "transit_time": rate.transit_time if rate else None,
        },
        config=config,
    )
    # The graph is now paused at the pricing interrupt. Read the computed draft.
    values = graph.get_state(config).values
    review = values["review"]

    quote.selling_price = review["selling_price"]
    quote.gross_margin = review["gross_margin"]
    quote.gross_margin_percentage = review["gross_margin_percentage"]
    quote.quote_text = review["draft_text"]
    quote.status = QuoteStatus.PENDING_APPROVAL
    db.commit()
    db.refresh(quote)

    log.info("quote_started", quote_id=quote.id, status=quote.status.value)
    return quote, QuotePricingReview(**review)


def approve_quote(db: Session, quote: Quote, payload: QuoteApprove, llm: LLMClient) -> Quote:
    graph = get_quote_graph()
    config = _thread_config(quote.id, llm)

    # Resume the paused graph with the human decision.
    graph.invoke(Command(resume=payload.model_dump()), config=config)
    values = graph.get_state(config).values

    if not values.get("approved"):
        quote.status = QuoteStatus.LOST if payload.lost_reason else QuoteStatus.DRAFT
        quote.lost_reason = payload.lost_reason
        db.commit()
        db.refresh(quote)
        log.info("quote_rejected", quote_id=quote.id)
        return quote

    quote.selling_price = values.get("final_selling_price")
    quote.gross_margin = values.get("final_gross_margin")
    quote.gross_margin_percentage = values.get("final_gross_margin_percentage")
    quote.quote_text = values.get("final_quote_text")

    if payload.mark_sent:
        quote.status = QuoteStatus.SENT
        quote.sent_at = datetime.now(timezone.utc)
        quote.next_follow_up_date = date.today() + timedelta(days=1)
        db.add(
            FollowUp(
                quote_id=quote.id,
                customer_id=quote.customer_id,
                due_date=quote.next_follow_up_date,
                status=FollowUpStatus.PENDING,
            )
        )
        if quote.rfq_id:
            rfq = db.get(RFQ, quote.rfq_id)
            if rfq:
                rfq.status = RFQStatus.QUOTED
    else:
        quote.status = QuoteStatus.APPROVED

    db.commit()
    db.refresh(quote)
    log.info("quote_approved", quote_id=quote.id, status=quote.status.value)
    return quote
