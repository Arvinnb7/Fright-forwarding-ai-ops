"""Customer / CRM schemas."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class CustomerCreate(BaseModel):
    company_name: str
    contact_name: str | None = None
    email: str | None = None
    phone: str | None = None
    country: str | None = None
    city: str | None = None
    industry: str | None = None
    notes: str | None = None
    next_follow_up_date: date | None = None


class CustomerUpdate(BaseModel):
    company_name: str | None = None
    contact_name: str | None = None
    email: str | None = None
    phone: str | None = None
    country: str | None = None
    city: str | None = None
    industry: str | None = None
    notes: str | None = None
    next_follow_up_date: date | None = None


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_name: str
    contact_name: str | None
    email: str | None
    phone: str | None
    country: str | None
    city: str | None
    industry: str | None
    notes: str | None
    next_follow_up_date: date | None
    created_at: datetime
    updated_at: datetime


class CustomerStats(BaseModel):
    rfq_count: int
    quote_count: int
    won_count: int
    lost_count: int
    average_margin_percentage: float | None
    typical_routes: list[str]


class CustomerProfile(BaseModel):
    stats: CustomerStats
    summary: str
