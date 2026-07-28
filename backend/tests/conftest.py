"""Test fixtures: an in-memory DB and a fake LLM (no network, no Postgres)."""
from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db import Base
from app.llm.base import LLMClient


class FakeLLM(LLMClient):
    """Deterministic LLM stand-in. Returns canned responses set per-test."""

    provider = "fake"
    model = "fake-1"

    def __init__(self) -> None:
        self.structured_response: dict[str, Any] = {}
        self.text_response: str = ""
        self.calls: list[dict[str, Any]] = []

    def complete(self, *, system: str, user: str, max_tokens: int = 4096) -> str:
        self.calls.append({"kind": "complete", "system": system, "user": user})
        return self.text_response

    def complete_structured(
        self, *, system: str, user: str, schema: dict[str, Any], max_tokens: int = 8000
    ) -> dict[str, Any]:
        self.calls.append({"kind": "structured", "system": system, "user": user})
        return self.structured_response


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def db_session():
    """In-memory DB with one organization active.

    Business records are tenant-scoped, so the session is bound to an
    organization for the duration of the test — mirroring what the auth
    dependency does per request in the app.
    """
    import app.models  # noqa: F401  (registers tables + installs tenant guards)
    from app.core.tenancy import organization_scope
    from app.models.organization import Organization

    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    session = TestSession()
    org = Organization(name="Test Org", slug="test-org")
    session.add(org)
    session.commit()
    try:
        with organization_scope(org.id, session):
            yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
