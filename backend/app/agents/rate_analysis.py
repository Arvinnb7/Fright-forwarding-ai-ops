"""Rate Analysis agent — compares partner rates and recommends an option.

Uses structured output so the recommendation references real rate ids. The
recommendation is advisory; the coordinator chooses.
"""
from __future__ import annotations

from app.llm.base import LLMClient
from app.models.partner_rate import PartnerRate
from app.prompts import load_prompt
from app.schemas.rate import RateAnalysis, rate_analysis_schema


def _render_rate(r: PartnerRate) -> str:
    parts = [
        f"rate_id={r.id}",
        f"partner={r.partner_name}",
        f"type={r.partner_type.value if r.partner_type else 'n/a'}",
        f"cost={r.cost_amount} {r.currency}" if r.cost_amount is not None else "cost=n/a",
        f"transit={r.transit_time or 'n/a'}",
        f"validity={r.validity_date.isoformat() if r.validity_date else 'n/a'}",
        f"free_time={r.free_time or 'n/a'}",
        f"included={r.included_charges or 'n/a'}",
        f"excluded={r.excluded_charges or 'n/a'}",
        f"reliability={r.reliability_score if r.reliability_score is not None else 'n/a'}",
    ]
    line = "; ".join(parts)
    if r.notes:
        line += f"\n  notes: {r.notes}"
    if r.risk_notes:
        line += f"\n  risk: {r.risk_notes}"
    return line


def run_rate_analysis(
    *,
    context: str,
    rates: list[PartnerRate],
    llm: LLMClient,
) -> RateAnalysis:
    if not rates:
        return RateAnalysis()
    rate_ids = [r.id for r in rates]
    system = load_prompt("rate_analysis")
    rendered = "\n".join(f"- {_render_rate(r)}" for r in rates)
    user = f"Shipment:\n{context}\n\nRate offers:\n{rendered}"
    data = llm.complete_structured(
        system=system, user=user, schema=rate_analysis_schema(rate_ids)
    )
    return RateAnalysis.model_validate(data)
