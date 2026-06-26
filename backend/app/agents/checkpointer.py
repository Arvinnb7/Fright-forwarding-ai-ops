"""LangGraph checkpointer factory.

Flows that pause for human approval (e.g. quotation pricing) compile with a
durable Postgres checkpointer so the run can be resumed across requests. Simple
one-shot agents (e.g. the RFQ parser) don't need one.
"""
from __future__ import annotations

from functools import lru_cache

from app.core.config import settings


@lru_cache
def get_postgres_checkpointer():
    """Return a durable PostgresSaver, creating tables on first use.

    Imported lazily so tests and one-shot agents don't require a live DB.
    """
    from langgraph.checkpoint.postgres import PostgresSaver

    # langgraph expects a psycopg-style URL without the SQLAlchemy driver suffix.
    url = settings.sqlalchemy_database_uri.replace("postgresql+psycopg", "postgresql")
    saver = PostgresSaver.from_conn_string(url)
    cm = saver.__enter__()  # keep the connection open for the app lifetime
    cm.setup()
    return cm
