"""Celery task logic + durable LangGraph checkpointer against live Postgres."""
from __future__ import annotations

from datetime import date, timedelta

from tests.integration.conftest import requires_integration

pytestmark = requires_integration


def test_refresh_due_follow_ups(integration_env):
    from app.core.db import SessionLocal
    from app.models.enums import FollowUpStatus
    from app.models.follow_up import FollowUp
    from app.models.quote import Quote
    from app.workers.tasks import refresh_due_follow_ups

    db = SessionLocal()
    quote = Quote(status="Draft")
    db.add(quote)
    db.flush()
    due = FollowUp(
        quote_id=quote.id,
        due_date=date.today() - timedelta(days=1),
        status=FollowUpStatus.PENDING,
    )
    future = FollowUp(
        quote_id=quote.id,
        due_date=date.today() + timedelta(days=5),
        status=FollowUpStatus.PENDING,
    )
    db.add_all([due, future])
    db.commit()
    due_id, future_id = due.id, future.id
    db.close()

    processed = refresh_due_follow_ups()
    assert processed >= 1

    db = SessionLocal()
    try:
        assert db.get(FollowUp, due_id).status == FollowUpStatus.DUE
        assert db.get(FollowUp, future_id).status == FollowUpStatus.PENDING
    finally:
        db.close()


def test_postgres_checkpointer_tables(integration_env):
    from sqlalchemy import text

    from app.agents.checkpointer import get_postgres_checkpointer
    from app.core.db import engine

    saver = get_postgres_checkpointer()
    assert saver is not None
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_name LIKE 'checkpoint%'"
            )
        ).fetchall()
    assert rows, "checkpointer should create its tables on setup"
