"""Partner rate entry and comparison."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.rate_analysis import run_rate_analysis
from app.core.config import settings
from app.core.db import get_db
from app.core.deps import get_current_user
from app.llm import get_llm
from app.llm.base import LLMError
from app.models.partner_rate import PartnerRate
from app.models.rfq import RFQ
from app.models.user import User
from app.schemas.rate import (
    LaneCoverage,
    LaneRateMemory,
    PartnerRateCreate,
    PartnerRateOut,
    PartnerRateUpdate,
    RateAnalysis,
    TariffImportResult,
)
from app.services.context import rfq_context
from app.services.lanes import lane_fields
from app.services.rate_memory import copy_rate_to_rfq, lane_coverage, suggest_rates_for_rfq
from app.services.tariff_import import TariffImportError, import_tariff, template_csv

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
    rfq = _require_rfq(db, rfq_id)
    # The lane is copied from the RFQ now, not read through the relationship
    # later: this rate is what the partner quoted for *these* details, and a
    # later edit to the RFQ must not rewrite that.
    rate = PartnerRate(rfq_id=rfq_id, **lane_fields(rfq), **payload.model_dump())
    db.add(rate)
    db.commit()
    db.refresh(rate)
    return rate


@router.get("/rfqs/{rfq_id}/rate-suggestions", response_model=LaneRateMemory)
def rate_suggestions(
    rfq_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    limit: int = 8,
) -> dict:
    """What we already know about this lane.

    The point of the whole feature: if this lane has been priced before, the
    coordinator can answer now instead of emailing a carrier and waiting.
    Nothing here is applied automatically — a suggestion is a starting point.
    """
    rfq = _require_rfq(db, rfq_id)
    return suggest_rates_for_rfq(db, rfq, limit=max(1, min(limit, 50)))


@router.post(
    "/rfqs/{rfq_id}/rates/from-history/{rate_id}",
    response_model=PartnerRateOut,
    status_code=201,
)
def reuse_rate(
    rfq_id: int,
    rate_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> PartnerRate:
    """Copy a remembered rate onto this RFQ so it can be quoted from."""
    rfq = _require_rfq(db, rfq_id)
    source = _require_rate(db, rate_id)
    if source.rfq_id == rfq_id:
        raise HTTPException(status_code=400, detail="That rate is already on this RFQ")
    return copy_rate_to_rfq(db, source, rfq)


@router.get("/rates/lanes", response_model=list[LaneCoverage])
def lanes(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    limit: int = 50,
) -> list[dict]:
    """Lanes that can already be priced, busiest first."""
    return lane_coverage(db, limit=max(1, min(limit, 200)))


@router.get("/rates/tariff/template.csv")
def tariff_template(_: User = Depends(get_current_user)) -> Response:
    """A ready-to-fill rate sheet, so nobody has to guess the column names."""
    return Response(
        content=template_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="tariff-template.csv"'},
    )


@router.post("/rates/tariff/import", response_model=TariffImportResult)
def import_tariff_sheet(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    """Load a partner rate sheet so its lanes can be quoted instantly.

    Re-uploading the same sheet is safe: unchanged rows are skipped rather than
    duplicated, and rejected rows are reported with their line number instead of
    being silently dropped.
    """
    content = file.file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    limit = settings.max_upload_mb * 1024 * 1024
    if len(content) > limit:
        raise HTTPException(
            status_code=413, detail=f"File exceeds the {settings.max_upload_mb} MB limit"
        )
    try:
        return import_tariff(db, content).as_dict()
    except TariffImportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
