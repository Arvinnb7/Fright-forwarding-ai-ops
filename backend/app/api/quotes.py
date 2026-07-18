"""Quotation endpoints: start (with pricing pause), approve/reject, list, PDF."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.llm import get_llm
from app.llm.base import LLMError
from app.models.quote import Quote
from app.models.user import User
from app.schemas.quote import (
    QuoteApprove,
    QuoteOut,
    QuotePricingReview,
    QuoteStart,
)
from app.services.pdf import text_to_pdf
from app.services.quote_service import approve_quote, start_quote

router = APIRouter()


@router.post("/start", response_model=QuotePricingReview)
def start(
    payload: QuoteStart,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> QuotePricingReview:
    """Build a quote draft and pause for human pricing approval.

    Returns the computed margin + draft for the coordinator to review. The quote
    is created with status 'Pending approval'; nothing is finalized yet.
    """
    try:
        _, review = start_quote(db, payload, get_llm())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return review


@router.post("/{quote_id}/approve", response_model=QuoteOut)
def approve(
    quote_id: int,
    payload: QuoteApprove,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Quote:
    """Approve (and optionally mark sent) or reject a pending quote."""
    quote = db.get(Quote, quote_id)
    if quote is None:
        raise HTTPException(status_code=404, detail="Quote not found")
    try:
        return approve_quote(db, quote, payload, get_llm())
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("", response_model=list[QuoteOut])
def list_quotes(
    response: Response,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    search: str | None = None,
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Quote]:
    stmt = select(Quote)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(Quote.quote_number.ilike(like), Quote.lost_reason.ilike(like)))
    if status_filter:
        stmt = stmt.where(Quote.status == status_filter)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    response.headers["X-Total-Count"] = str(total)
    stmt = stmt.order_by(Quote.created_at.desc()).limit(limit).offset(offset)
    return list(db.execute(stmt).scalars().all())


@router.get("/{quote_id}", response_model=QuoteOut)
def get_quote(
    quote_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Quote:
    quote = db.get(Quote, quote_id)
    if quote is None:
        raise HTTPException(status_code=404, detail="Quote not found")
    return quote


@router.get("/{quote_id}/pdf")
def quote_pdf(
    quote_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Response:
    quote = db.get(Quote, quote_id)
    if quote is None:
        raise HTTPException(status_code=404, detail="Quote not found")
    title = f"Quotation {quote.quote_number or quote.id}"
    pdf = text_to_pdf(title, quote.quote_text or "(no quotation text)")
    filename = f"{quote.quote_number or 'quote'}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
