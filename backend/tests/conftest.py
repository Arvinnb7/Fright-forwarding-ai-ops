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
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
