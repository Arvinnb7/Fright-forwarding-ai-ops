"""Partner rate + rate analysis schemas."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.enums import PartnerType


class PartnerRateCreate(BaseModel):
    partner_name: str
    partner_type: PartnerType | None = None
    cost_amount: float | None = None
    currency: str = "USD"
    included_charges: str | None = None
    excluded_charges: str | None = None
    transit_time: str | None = None
    validity_date: date | None = None
    free_time: str | None = None
    notes: str | None = None
    risk_notes: str | None = None
    reliability_score: float | None = None


class PartnerRateUpdate(BaseModel):
    partner_name: str | None = None
    partner_type: PartnerType | None = None
    cost_amount: float | None = None
    currency: str | None = None
    included_charges: str | None = None
    excluded_charges: str | None = None
    transit_time: str | None = None
    validity_date: date | None = None
    free_time: str | None = None
    notes: str | None = None
    risk_notes: str | None = None
    reliability_score: float | None = None


class PartnerRateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rfq_id: int
    partner_name: str
    partner_type: PartnerType | None
    cost_amount: float | None
    currency: str
    included_charges: str | None
    excluded_charges: str | None
    transit_time: str | None
    validity_date: date | None
    free_time: str | None
    notes: str | None
    risk_notes: str | None
    reliability_score: float | None
    created_at: datetime


# ── Rate analysis agent contract ─────────────────────────────


class RateOption(BaseModel):
    rate_id: int
    partner_name: str
    summary: str
    pros: list[str] = []
    cons: list[str] = []
    risk_notes: str | None = None


class RateAnalysis(BaseModel):
    cheapest_rate_id: int | None = None
    fastest_rate_id: int | None = None
    best_margin_rate_id: int | None = None
    lowest_risk_rate_id: int | None = None
    recommended_rate_id: int | None = None
    recommendation_reason: str | None = None
    tradeoffs: str | None = None
    options: list[RateOption] = []


def rate_analysis_schema(rate_ids: list[int]) -> dict[str, Any]:
    """JSON schema for the analysis, constraining rate ids to the real options."""
    id_enum = {"type": ["integer", "null"], "enum": [*rate_ids, None]}
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "cheapest_rate_id": id_enum,
            "fastest_rate_id": id_enum,
            "best_margin_rate_id": id_enum,
            "lowest_risk_rate_id": id_enum,
            "recommended_rate_id": id_enum,
            "recommendation_reason": {"type": ["string", "null"]},
            "tradeoffs": {"type": ["string", "null"]},
            "options": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "rate_id": {"type": "integer", "enum": rate_ids},
                        "partner_name": {"type": "string"},
                        "summary": {"type": "string"},
                        "pros": {"type": "array", "items": {"type": "string"}},
                        "cons": {"type": "array", "items": {"type": "string"}},
                        "risk_notes": {"type": ["string", "null"]},
                    },
                    "required": [
                        "rate_id",
                        "partner_name",
                        "summary",
                        "pros",
                        "cons",
                        "risk_notes",
                    ],
                },
            },
        },
        "required": [
            "cheapest_rate_id",
            "fastest_rate_id",
            "best_margin_rate_id",
            "lowest_risk_rate_id",
            "recommended_rate_id",
            "recommendation_reason",
            "tradeoffs",
            "options",
        ],
    }
