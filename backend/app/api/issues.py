"""Issue / exception-tracker endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.shipment_ops import booking_context, run_issue_draft
from app.core.db import get_db
from app.core.deps import get_current_user
from app.llm import get_llm
from app.llm.base import LLMError
from app.models.booking import Booking
from app.models.issue import Issue
from app.models.user import User
from app.schemas.issue import (
    IssueCreate,
    IssueDraftIn,
    IssueDraftOut,
    IssueOut,
    IssueUpdate,
)

router = APIRouter()


def _require_issue(db: Session, issue_id: int) -> Issue:
    issue = db.get(Issue, issue_id)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")
    return issue


@router.post("", response_model=IssueOut, status_code=201)
def create_issue(
    payload: IssueCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Issue:
    if payload.booking_id is not None and db.get(Booking, payload.booking_id) is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    issue = Issue(**payload.model_dump())
    db.add(issue)
    db.commit()
    db.refresh(issue)
    return issue


@router.get("", response_model=list[IssueOut])
def list_issues(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    open_only: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> list[Issue]:
    stmt = select(Issue).order_by(Issue.created_at.desc())
    if open_only:
        stmt = stmt.where(Issue.status.in_(["Open", "In progress"]))
    return list(db.execute(stmt.limit(limit).offset(offset)).scalars().all())


@router.patch("/{issue_id}", response_model=IssueOut)
def update_issue(
    issue_id: int,
    payload: IssueUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Issue:
    issue = _require_issue(db, issue_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(issue, field, value)
    db.commit()
    db.refresh(issue)
    return issue


@router.post("/{issue_id}/draft", response_model=IssueDraftOut)
def issue_draft(
    issue_id: int,
    payload: IssueDraftIn,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> IssueDraftOut:
    """Draft an escalation or customer-explanation message for this issue."""
    issue = _require_issue(db, issue_id)
    booking = db.get(Booking, issue.booking_id) if issue.booking_id else None
    try:
        draft = run_issue_draft(
            issue=issue,
            kind=payload.kind,
            shipment_context=booking_context(booking) if booking else None,
            llm=get_llm(),
        )
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return IssueDraftOut(draft=draft)
