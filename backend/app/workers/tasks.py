"""Celery tasks: follow-up refresh + daily database backup."""
from __future__ import annotations

import os
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.logging import get_logger
from app.models.enums import FollowUpStatus
from app.models.follow_up import FollowUp
from app.workers.celery_app import celery_app

log = get_logger("worker")

BACKUP_DIR = Path("storage/backups")
BACKUP_KEEP = 14


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


@celery_app.task(name="app.workers.tasks.run_daily_backup")
def run_daily_backup() -> str:
    """Dump the database to storage/backups/ and keep the newest BACKUP_KEEP.

    Uses pg_dump custom format (restorable with pg_restore). Returns the path
    of the created backup file.
    """
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    target = BACKUP_DIR / f"{settings.postgres_db}-{stamp}.dump"

    env = {**os.environ, "PGPASSWORD": settings.postgres_password}
    cmd = [
        "pg_dump",
        "-h", settings.postgres_host,
        "-p", str(settings.postgres_port),
        "-U", settings.postgres_user,
        "-d", settings.postgres_db,
        "-F", "c",
        "-f", str(target),
    ]
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        log.error("backup_failed", stderr=result.stderr.strip())
        raise RuntimeError(f"pg_dump failed: {result.stderr.strip()}")

    # Rotate: keep the newest BACKUP_KEEP dumps.
    dumps = sorted(BACKUP_DIR.glob("*.dump"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in dumps[BACKUP_KEEP:]:
        old.unlink(missing_ok=True)

    log.info("backup_created", path=str(target), kept=min(len(dumps), BACKUP_KEEP))
    return str(target)
