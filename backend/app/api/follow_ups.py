"""Follow-up endpoints: list/due, draft a message, update status."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.follow_up import run_follow_up
from app.core.db import get_db
from app.core.deps import get_current_user
from app.llm import get_llm
from app.llm.base import LLMError
from app.models.enums import FollowUpStatus
from app.models.follow_up import FollowUp
from app.models.quote import Quote
from app.models.user import User
from app.schemas.follow_up import (
    FollowUpDraftIn,
    FollowUpDraftOut,
    FollowUpOut,
    FollowUpUpdate,
)
from app.services.context import quote_context

router = APIRouter()


def _require_follow_up(db: Session, follow_up_id: int) -> FollowUp:
    fu = db.get(FollowUp, follow_up_id)
    if fu is None:
        raise HTTPException(status_code=404, detail="Follow-up not found")
    return fu


@router.get("", response_model=list[FollowUpOut])
def list_follow_ups(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    due_only: bool = False,
) -> list[FollowUp]:
    stmt = select(FollowUp).order_by(FollowUp.due_date.asc().nullslast())
    if due_only:
        stmt = stmt.where(
            FollowUp.status.in_([FollowUpStatus.PENDING, FollowUpStatus.DUE]),
            FollowUp.due_date.is_not(None),
            FollowUp.due_date <= date.today(),
        )
    return list(db.execute(stmt).scalars().all())


@router.post("/{follow_up_id}/draft", response_model=FollowUpDraftOut)
def draft_follow_up(
    follow_up_id: int,
    payload: FollowUpDraftIn,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> FollowUpDraftOut:
    fu = _require_follow_up(db, follow_up_id)
    quote = db.get(Quote, fu.quote_id)
    if quote is None:
        raise HTTPException(status_code=404, detail="Linked quote not found")

    days_since = (date.today() - quote.sent_at.date()).days if quote.sent_at else None
    customer_name = quote.customer.contact_name if quote.customer else None
    try:
        draft = run_follow_up(
            context=quote_context(quote),
            follow_up_type=payload.follow_up_type,
            days_since_sent=days_since,
            customer_name=customer_name,
            llm=get_llm(),
        )
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if payload.save:
        fu.draft_message = draft
        db.commit()
    return FollowUpDraftOut(draft=draft)


@router.patch("/{follow_up_id}", response_model=FollowUpOut)
def update_follow_up(
    follow_up_id: int,
    payload: FollowUpUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> FollowUp:
    fu = _require_follow_up(db, follow_up_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(fu, field, value)
    db.commit()
    db.refresh(fu)
    return fu
