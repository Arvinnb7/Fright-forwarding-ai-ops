"""OpenAI implementation of the LLM interface.

Optional provider: the `openai` package is not installed by default. Install it
(`pip install openai`) and set `LLM_PROVIDER=openai` to use it.
"""
from __future__ import annotations

import json
from typing import Any

from app.core.logging import get_logger
from app.llm.base import LLMClient, LLMError

log = get_logger("llm.openai")

DEFAULT_MODEL = "gpt-4o"


class OpenAIClient(LLMClient):
    provider = "openai"

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        if not api_key:
            raise LLMError("OPENAI_API_KEY is not set.")
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover
            raise LLMError(
                "The 'openai' package is not installed. Run `pip install openai`."
            ) from exc
        self._client = OpenAI(api_key=api_key)
        self.model = model

    def complete(self, *, system: str, user: str, max_tokens: int = 4096) -> str:
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
        except Exception as exc:  # pragma: no cover
            raise LLMError(f"OpenAI request failed: {exc}") from exc
        return resp.choices[0].message.content or ""

    def complete_structured(
        self, *, system: str, user: str, schema: dict[str, Any], max_tokens: int = 8000
    ) -> dict[str, Any]:
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": "result", "schema": schema, "strict": True},
                },
            )
        except Exception as exc:  # pragma: no cover
            raise LLMError(f"OpenAI structured request failed: {exc}") from exc
        text = resp.choices[0].message.content or "{}"
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMError(f"Model did not return valid JSON: {exc}") from exc
