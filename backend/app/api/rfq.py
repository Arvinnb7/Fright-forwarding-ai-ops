"""RFQ endpoints: parse a raw inquiry, list, fetch, and edit RFQs."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from pydantic import BaseModel

from app.agents.missing_info import run_missing_info
from app.agents.rate_request import run_rate_request
from app.agents.rfq_parser import run_rfq_parser
from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.logging import get_logger
from app.llm import get_llm
from app.llm.base import LLMError
from app.models.enums import PartnerType
from app.models.rfq import RFQ
from app.models.user import User
from app.schemas.rfq import RFQExtraction, RFQOut, RFQParseRequest, RFQUpdate
from app.services.context import rfq_context
from app.services.rfq_service import create_rfq_from_extraction

router = APIRouter()
log = get_logger("api.rfq")


@router.post("/parse")
def parse_rfq(
    payload: RFQParseRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    """Run the RFQ parser agent on raw text.

    Returns the structured extraction (always) and, when `persist` is true, the
    created RFQ record. The extraction is editable in the UI before anything is
    treated as final.
    """
    try:
        extraction: RFQExtraction = run_rfq_parser(payload.raw_message, get_llm())
    except LLMError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc

    response: dict = {"extraction": extraction.model_dump(mode="json")}
    if payload.persist:
        rfq = create_rfq_from_extraction(
            db, extraction, payload.raw_message, payload.customer_id
        )
        response["rfq"] = RFQOut.model_validate(rfq).model_dump(mode="json")
    return response


@router.get("", response_model=list[RFQOut])
def list_rfqs(
    response: Response,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    search: str | None = None,
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[RFQ]:
    stmt = select(RFQ)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            or_(
                RFQ.reference.ilike(like),
                RFQ.origin.ilike(like),
                RFQ.destination.ilike(like),
                RFQ.commodity.ilike(like),
            )
        )
    if status_filter:
        stmt = stmt.where(RFQ.status == status_filter)
    total = db.execute(
        select(func.count()).select_from(stmt.subquery())
    ).scalar_one()
    response.headers["X-Total-Count"] = str(total)
    stmt = stmt.order_by(RFQ.created_at.desc()).limit(limit).offset(offset)
    return list(db.execute(stmt).scalars().all())


@router.get("/{rfq_id}", response_model=RFQOut)
def get_rfq(
    rfq_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> RFQ:
    rfq = db.get(RFQ, rfq_id)
    if rfq is None:
        raise HTTPException(status_code=404, detail="RFQ not found")
    return rfq


class _DraftOut(BaseModel):
    draft: str


class _RateRequestIn(BaseModel):
    partner_type: PartnerType
    partner_name: str | None = None


def _require_rfq(db: Session, rfq_id: int) -> RFQ:
    rfq = db.get(RFQ, rfq_id)
    if rfq is None:
        raise HTTPException(status_code=404, detail="RFQ not found")
    return rfq


@router.post("/{rfq_id}/missing-info-draft", response_model=_DraftOut)
def missing_info_draft(
    rfq_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> _DraftOut:
    """Draft a customer email requesting the RFQ's missing information."""
    rfq = _require_rfq(db, rfq_id)
    customer_name = rfq.customer.contact_name if rfq.customer else None
    try:
        draft = run_missing_info(
            context=rfq_context(rfq),
            missing_fields=rfq.missing_fields or [],
            customer_name=customer_name,
            llm=get_llm(),
        )
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _DraftOut(draft=draft)


@router.post("/{rfq_id}/rate-request-draft", response_model=_DraftOut)
def rate_request_draft(
    rfq_id: int,
    payload: _RateRequestIn,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> _DraftOut:
    """Draft a partner-specific rate-request message for this RFQ."""
    rfq = _require_rfq(db, rfq_id)
    try:
        draft = run_rate_request(
            context=rfq_context(rfq),
            partner_type=payload.partner_type,
            transport_mode=rfq.transport_mode,
            partner_name=payload.partner_name,
            llm=get_llm(),
        )
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _DraftOut(draft=draft)


@router.patch("/{rfq_id}", response_model=RFQOut)
def update_rfq(
    rfq_id: int,
    payload: RFQUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> RFQ:
    rfq = db.get(RFQ, rfq_id)
    if rfq is None:
        raise HTTPException(status_code=404, detail="RFQ not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(rfq, field, value)
    db.commit()
    db.refresh(rfq)
    return rfq
