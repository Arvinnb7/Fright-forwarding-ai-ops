"""RFQ endpoints: parse a raw inquiry, list, fetch, and edit RFQs."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.rfq_parser import run_rfq_parser
from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.logging import get_logger
from app.llm import get_llm
from app.llm.base import LLMError
from app.models.rfq import RFQ
from app.models.user import User
from app.schemas.rfq import RFQExtraction, RFQOut, RFQParseRequest, RFQUpdate
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
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    limit: int = 100,
    offset: int = 0,
) -> list[RFQ]:
    stmt = select(RFQ).order_by(RFQ.created_at.desc()).limit(limit).offset(offset)
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
