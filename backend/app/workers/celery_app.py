"""Celery application + periodic schedule.

Background jobs cover follow-up reminders, report generation and backups. The
worker is started with `--beat`, so the schedule below runs inside the same
process for local use.
"""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "freight_ai_ops",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_track_started=True,
    timezone="UTC",
    beat_schedule={
        "poll-mailboxes": {
            "task": "app.workers.tasks.poll_mailboxes",
            "schedule": settings.email_poll_interval_minutes * 60.0,
        },
        "refresh-follow-ups-every-morning": {
            "task": "app.workers.tasks.refresh_due_follow_ups",
            "schedule": crontab(hour=6, minute=0),
        },
        "daily-database-backup": {
            "task": "app.workers.tasks.run_daily_backup",
            "schedule": crontab(hour=2, minute=0),
        },
    },
)
