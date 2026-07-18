"""Customer / CRM endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.agents.customer_profile import run_customer_profile
from app.core.db import get_db
from app.core.deps import get_current_user
from app.llm import get_llm
from app.llm.base import LLMError
from app.models.customer import Customer
from app.models.user import User
from app.schemas.customer import (
    CustomerCreate,
    CustomerOut,
    CustomerProfile,
    CustomerUpdate,
)
from app.services.customer_service import compute_customer_stats

router = APIRouter()


def _require_customer(db: Session, customer_id: int) -> Customer:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.post("", response_model=CustomerOut, status_code=201)
def create_customer(
    payload: CustomerCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Customer:
    customer = Customer(**payload.model_dump())
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


@router.get("", response_model=list[CustomerOut])
def list_customers(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Customer]:
    stmt = select(Customer).order_by(Customer.company_name)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            or_(
                Customer.company_name.ilike(like),
                Customer.contact_name.ilike(like),
                Customer.email.ilike(like),
            )
        )
    return list(db.execute(stmt.limit(limit).offset(offset)).scalars().all())


@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Customer:
    return _require_customer(db, customer_id)


@router.patch("/{customer_id}", response_model=CustomerOut)
def update_customer(
    customer_id: int,
    payload: CustomerUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Customer:
    customer = _require_customer(db, customer_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(customer, field, value)
    db.commit()
    db.refresh(customer)
    return customer


@router.post("/{customer_id}/profile", response_model=CustomerProfile)
def profile_summary(
    customer_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> CustomerProfile:
    """Deterministic stats + an AI-written profile paragraph."""
    customer = _require_customer(db, customer_id)
    stats = compute_customer_stats(db, customer)
    try:
        summary = run_customer_profile(customer=customer, stats=stats, llm=get_llm())
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return CustomerProfile(stats=stats, summary=summary)
