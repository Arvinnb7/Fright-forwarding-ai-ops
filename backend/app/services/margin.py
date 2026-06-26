"""Margin & selling-price calculator.

Pure functions — no DB, no LLM — so the commercial maths is deterministic and
fully unit-tested. The AI never sets price; it only recommends. This module is
the single source of truth for converting cost into selling price.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class MarkupType(str, Enum):
    PERCENT = "percent"
    FIXED = "fixed"


@dataclass
class MarginInput:
    cost_amount: float
    markup_type: MarkupType = MarkupType.PERCENT
    markup_value: float = 0.0
    currency: str = "USD"
    cost_currency: str | None = None  # if different from `currency` → mismatch warning
    min_profit: float | None = None
    validity_date: date | None = None
    # Optional explicit selling price (overrides markup when provided).
    selling_price_override: float | None = None


@dataclass
class MarginResult:
    cost_amount: float
    selling_price: float
    gross_margin: float
    gross_margin_percentage: float
    currency: str
    warnings: list[str] = field(default_factory=list)


def _round2(x: float) -> float:
    return round(x + 0.0, 2)


def calculate_margin(data: MarginInput, today: date | None = None) -> MarginResult:
    """Compute selling price + margin and surface risk warnings.

    Warnings (per spec §6) are advisory — they never block; the human decides.
    """
    warnings: list[str] = []
    cost = float(data.cost_amount)

    if data.selling_price_override is not None:
        selling = float(data.selling_price_override)
    elif data.markup_type == MarkupType.FIXED:
        selling = cost + float(data.markup_value)
    else:  # percent
        selling = cost * (1 + float(data.markup_value) / 100.0)

    selling = _round2(selling)
    margin = _round2(selling - cost)
    margin_pct = _round2((margin / selling) * 100.0) if selling else 0.0

    # ── Warnings ─────────────────────────────────────────────
    if selling < cost:
        warnings.append("Selling price is below cost.")
    if margin <= 0:
        warnings.append("Margin is zero or negative.")
    elif margin_pct < 5:
        warnings.append(f"Margin is very low ({margin_pct:.1f}%).")
    if data.min_profit is not None and margin < float(data.min_profit):
        warnings.append(
            f"Margin {margin:.2f} is below the minimum profit threshold "
            f"{float(data.min_profit):.2f}."
        )
    if data.cost_currency and data.cost_currency != data.currency:
        warnings.append(
            f"Currency mismatch: cost in {data.cost_currency}, "
            f"selling in {data.currency}."
        )
    if data.validity_date is not None and data.validity_date < (today or date.today()):
        warnings.append(f"Rate validity expired on {data.validity_date.isoformat()}.")

    return MarginResult(
        cost_amount=_round2(cost),
        selling_price=selling,
        gross_margin=margin,
        gross_margin_percentage=margin_pct,
        currency=data.currency,
        warnings=warnings,
    )
