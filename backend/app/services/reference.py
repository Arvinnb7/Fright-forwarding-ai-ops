"""Human-friendly reference numbers, sequential **per organization**.

In a multi-tenant deployment each customer must see their own sequence starting
at 1 — using the global row id would make a new tenant's first RFQ look like
"RFQ-2026-0147" and would leak our total volume across tenants.

The counter is the per-org, per-year row count + 1, taken inside the caller's
transaction. Concurrent writes are guarded by the ``(org_id, <number>)`` unique
constraints on the tables, which surface a conflict instead of silently issuing
a duplicate number.
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session


def _year_bounds(year: int) -> tuple[datetime, datetime]:
    start = datetime.combine(date(year, 1, 1), time.min, tzinfo=timezone.utc)
    end = datetime.combine(date(year, 12, 31), time.max, tzinfo=timezone.utc)
    return start, end


def sequence_for(
    db: Session, model: type, org_id: int, row_id: int, today: date | None = None
) -> int:
    """The per-organization sequence position of an **already flushed** row.

    Counts rows of the same organization and year up to and including this one,
    so the first record of a tenant is 1. Using ``id <= row_id`` (rather than a
    plain row count) keeps the number stable if an earlier record is later
    deleted, and avoids the row counting itself into the *next* slot.
    """
    year = (today or date.today()).year
    start, end = _year_bounds(year)
    position = db.execute(
        select(func.count(model.id)).where(
            model.org_id == org_id,
            model.created_at.between(start, end),
            model.id <= row_id,
        )
    ).scalar_one()
    return max(int(position or 0), 1)


def format_reference(prefix: str, sequence: int, today: date | None = None) -> str:
    year = (today or date.today()).year
    return f"{prefix}-{year}-{sequence:04d}"


def rfq_reference(sequence: int, today: date | None = None) -> str:
    return format_reference("RFQ", sequence, today)


def quote_number(sequence: int, today: date | None = None) -> str:
    return format_reference("Q", sequence, today)


def job_number(sequence: int, today: date | None = None) -> str:
    return format_reference("JOB", sequence, today)
