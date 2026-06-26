"""Provider-neutral LLM interface used by every agent.

Two operations cover all current needs:
  * `complete`            — free-form text generation (drafts, messages, reports)
  * `complete_structured` — JSON output validated against a JSON schema
                            (RFQ extraction, rate analysis, ...)
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLMError(RuntimeError):
    """Raised when the underlying provider call fails."""


class LLMClient(ABC):
    """Abstract LLM client. Implementations live alongside this module."""

    #: Human-readable provider name (e.g. "anthropic").
    provider: str = "abstract"
    model: str = ""

    @abstractmethod
    def complete(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int = 4096,
    ) -> str:
        """Return generated text for the given system + user prompt."""

    @abstractmethod
    def complete_structured(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any],
        max_tokens: int = 8000,
    ) -> dict[str, Any]:
        """Return a JSON object conforming to `schema`."""
