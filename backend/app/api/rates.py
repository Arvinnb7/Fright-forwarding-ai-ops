"""Partner rate entry and comparison."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.rate_analysis import run_rate_analysis
from app.core.db import get_db
from app.core.deps import get_current_user
from app.llm import get_llm
from app.llm.base import LLMError
from app.models.partner_rate import PartnerRate
from app.models.rfq import RFQ
from app.models.user import User
from app.schemas.rate import (
    PartnerRateCreate,
    PartnerRateOut,
    PartnerRateUpdate,
    RateAnalysis,
)
from app.services.context import rfq_context

router = APIRouter()


def _require_rfq(db: Session, rfq_id: int) -> RFQ:
    rfq = db.get(RFQ, rfq_id)
    if rfq is None:
        raise HTTPException(status_code=404, detail="RFQ not found")
    return rfq


def _require_rate(db: Session, rate_id: int) -> PartnerRate:
    rate = db.get(PartnerRate, rate_id)
    if rate is None:
        raise HTTPException(status_code=404, detail="Rate not found")
    return rate


@router.post("/rfqs/{rfq_id}/rates", response_model=PartnerRateOut, status_code=201)
def add_rate(
    rfq_id: int,
    payload: PartnerRateCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> PartnerRate:
    _require_rfq(db, rfq_id)
    rate = PartnerRate(rfq_id=rfq_id, **payload.model_dump())
    db.add(rate)
    db.commit()
    db.refresh(rate)
    return rate


@router.get("/rfqs/{rfq_id}/rates", response_model=list[PartnerRateOut])
def list_rates(
    rfq_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[PartnerRate]:
    _require_rfq(db, rfq_id)
    stmt = select(PartnerRate).where(PartnerRate.rfq_id == rfq_id).order_by(PartnerRate.id)
    return list(db.execute(stmt).scalars().all())


@router.patch("/rates/{rate_id}", response_model=PartnerRateOut)
def update_rate(
    rate_id: int,
    payload: PartnerRateUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> PartnerRate:
    rate = _require_rate(db, rate_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(rate, field, value)
    db.commit()
    db.refresh(rate)
    return rate


@router.delete(
    "/rates/{rate_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_rate(
    rate_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Response:
    rate = _require_rate(db, rate_id)
    db.delete(rate)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/rfqs/{rfq_id}/rates/analyze", response_model=RateAnalysis)
def analyze_rates(
    rfq_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> RateAnalysis:
    """Compare all rates on an RFQ and return a recommendation (advisory)."""
    rfq = _require_rfq(db, rfq_id)
    rates = list(
        db.execute(
            select(PartnerRate).where(PartnerRate.rfq_id == rfq_id).order_by(PartnerRate.id)
        ).scalars().all()
    )
    if not rates:
        raise HTTPException(status_code=400, detail="No rates to analyze for this RFQ")
    try:
        return run_rate_analysis(context=rfq_context(rfq), rates=rates, llm=get_llm())
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
