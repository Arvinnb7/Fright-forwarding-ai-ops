"""LangGraph checkpointer factory.

Flows that pause for human approval (e.g. quotation pricing) compile with a
durable Postgres checkpointer so the run can be resumed across requests. Simple
one-shot agents (e.g. the RFQ parser) don't need one.

We hold one long-lived psycopg connection for the app's lifetime. Do NOT use
`PostgresSaver.from_conn_string()` here: it returns a context manager whose
connection is closed when the manager is garbage-collected.
"""
from __future__ import annotations

from functools import lru_cache

from app.core.config import settings


@lru_cache
def get_postgres_checkpointer():
    """Return a durable PostgresSaver, creating its tables on first use."""
    from psycopg import Connection
    from psycopg.rows import dict_row
    from langgraph.checkpoint.postgres import PostgresSaver

    # langgraph expects a psycopg URL without the SQLAlchemy driver suffix.
    url = settings.sqlalchemy_database_uri.replace("postgresql+psycopg", "postgresql")
    conn = Connection.connect(
        url, autocommit=True, prepare_threshold=0, row_factory=dict_row
    )
    saver = PostgresSaver(conn)
    saver.setup()
    return saver
