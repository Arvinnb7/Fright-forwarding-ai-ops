"""Anthropic (Claude) implementation of the LLM interface.

Follows current Claude API rules:
  * adaptive thinking (`thinking={"type": "adaptive"}`) — `budget_tokens`,
    `temperature`, `top_p` are removed on current models;
  * structured output via `output_config.format` (no assistant prefill);
  * guards `stop_reason == "refusal"` before reading content.
"""
from __future__ import annotations

import json
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.logging import get_logger
from app.llm.base import LLMClient, LLMError

log = get_logger("llm.anthropic")

DEFAULT_MODEL = "claude-opus-4-8"


class AnthropicClient(LLMClient):
    provider = "anthropic"

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        if not api_key:
            raise LLMError(
                "ANTHROPIC_API_KEY is not set. Add it to your .env to use the "
                "Anthropic provider."
            )
        # Imported lazily so the package is only required when actually used.
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=16),
        reraise=True,
    )
    def _create(self, **kwargs: Any):
        return self._client.messages.create(**kwargs)

    def _first_text(self, response: Any) -> str:
        if getattr(response, "stop_reason", None) == "refusal":
            raise LLMError("The model declined to respond to this request.")
        for block in response.content:
            if block.type == "text":
                return block.text
        return ""

    def complete(self, *, system: str, user: str, max_tokens: int = 4096) -> str:
        try:
            response = self._create(
                model=self.model,
                max_tokens=max_tokens,
                thinking={"type": "adaptive"},
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except LLMError:
            raise
        except Exception as exc:  # pragma: no cover - network/provider errors
            log.error("anthropic_complete_failed", error=str(exc))
            raise LLMError(f"Anthropic request failed: {exc}") from exc
        return self._first_text(response)

    def complete_structured(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any],
        max_tokens: int = 8000,
    ) -> dict[str, Any]:
        try:
            response = self._create(
                model=self.model,
                max_tokens=max_tokens,
                thinking={"type": "adaptive"},
                system=system,
                messages=[{"role": "user", "content": user}],
                output_config={"format": {"type": "json_schema", "schema": schema}},
            )
        except LLMError:
            raise
        except Exception as exc:  # pragma: no cover - network/provider errors
            log.error("anthropic_structured_failed", error=str(exc))
            raise LLMError(f"Anthropic structured request failed: {exc}") from exc

        text = self._first_text(response)
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMError(f"Model did not return valid JSON: {exc}") from exc
