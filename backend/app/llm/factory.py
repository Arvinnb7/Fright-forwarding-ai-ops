"""Build the configured LLM client.

`get_llm()` returns a cached client based on settings. Tests (or future request
scoping) can override the client via `set_llm()`.
"""
from __future__ import annotations

from app.core.config import settings
from app.core.logging import get_logger
from app.llm.base import LLMClient, LLMError

log = get_logger("llm.factory")

_override: LLMClient | None = None
_cached: LLMClient | None = None


def set_llm(client: LLMClient | None) -> None:
    """Inject an LLM client (used by tests). Pass None to clear the override."""
    global _override, _cached
    _override = client
    _cached = None


def _build() -> LLMClient:
    provider = settings.llm_provider.lower()
    if provider == "anthropic":
        from app.llm.anthropic_provider import AnthropicClient

        return AnthropicClient(api_key=settings.anthropic_api_key, model=settings.llm_model)
    if provider == "openai":
        from app.llm.openai_provider import OpenAIClient

        return OpenAIClient(api_key=settings.openai_api_key, model=settings.llm_model)
    if provider == "gemini":
        from app.llm.gemini_provider import GeminiClient

        return GeminiClient(api_key=settings.gemini_api_key, model=settings.llm_model)
    raise LLMError(f"Unknown LLM provider: {settings.llm_provider!r}")


def get_llm() -> LLMClient:
    global _cached
    if _override is not None:
        return _override
    if _cached is None:
        _cached = _build()
        log.info("llm_client_ready", provider=_cached.provider, model=_cached.model)
    return _cached
