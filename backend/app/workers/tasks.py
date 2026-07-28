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
from app.core.tenancy import bypass_tenant_isolation, organization_scope
from app.models.enums import FollowUpStatus
from app.models.follow_up import FollowUp
from app.models.organization import Organization
from app.workers.celery_app import celery_app

log = get_logger("worker")

BACKUP_DIR = Path("storage/backups")
BACKUP_KEEP = 14


def _active_org_ids(db) -> list[int]:
    """All active tenants. Background jobs have no request context, so they
    must iterate organizations and scope each pass explicitly."""
    with bypass_tenant_isolation(db):
        return list(
            db.execute(
                select(Organization.id).where(Organization.is_active.is_(True))
            ).scalars().all()
        )


@celery_app.task(name="app.workers.tasks.refresh_due_follow_ups")
def refresh_due_follow_ups() -> int:
    """Mark pending follow-ups whose due date has arrived as DUE, per tenant.

    Returns the total number of follow-ups transitioned across organizations.
    """
    db = SessionLocal()
    try:
        today = date.today()
        total = 0
        for org_id in _active_org_ids(db):
            with organization_scope(org_id, db):
                stmt = select(FollowUp).where(
                    FollowUp.status == FollowUpStatus.PENDING,
                    FollowUp.due_date.is_not(None),
                    FollowUp.due_date <= today,
                )
                due = list(db.execute(stmt).scalars().all())
                for fu in due:
                    fu.status = FollowUpStatus.DUE
                db.commit()
                total += len(due)
        log.info("follow_ups_marked_due", count=total)
        return total
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
