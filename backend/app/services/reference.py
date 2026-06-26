"""Human-friendly reference number generation.

References embed the year and the row id, e.g. RFQ-2026-0042. They are assigned
after the row is flushed so the id is available and uniqueness is guaranteed.
"""
from __future__ import annotations

from datetime import date


def rfq_reference(rfq_id: int, today: date | None = None) -> str:
    year = (today or date.today()).year
    return f"RFQ-{year}-{rfq_id:04d}"


def quote_number(quote_id: int, today: date | None = None) -> str:
    year = (today or date.today()).year
    return f"Q-{year}-{quote_id:04d}"


def job_number(booking_id: int, today: date | None = None) -> str:
    year = (today or date.today()).year
    return f"JOB-{year}-{booking_id:04d}"
