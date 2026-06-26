"""Celery tasks.

Phase 1 ships the scaffolding + a working follow-up refresh task. Report
generation and backups are added alongside their modules in later phases.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.logging import get_logger
from app.models.enums import FollowUpStatus
from app.models.follow_up import FollowUp
from app.workers.celery_app import celery_app

log = get_logger("worker")


@celery_app.task(name="app.workers.tasks.refresh_due_follow_ups")
def refresh_due_follow_ups() -> int:
    """Mark pending follow-ups whose due date has arrived as DUE.

    Returns the number of follow-ups transitioned (handy for logs/tests).
    """
    db = SessionLocal()
    try:
        today = date.today()
        stmt = select(FollowUp).where(
            FollowUp.status == FollowUpStatus.PENDING,
            FollowUp.due_date.is_not(None),
            FollowUp.due_date <= today,
        )
        due = list(db.execute(stmt).scalars().all())
        for fu in due:
            fu.status = FollowUpStatus.DUE
        db.commit()
        log.info("follow_ups_marked_due", count=len(due))
        return len(due)
    finally:
        db.close()
