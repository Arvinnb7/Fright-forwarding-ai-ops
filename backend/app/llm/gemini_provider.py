"""Google Gemini implementation of the LLM interface.

Optional provider: the `google-generativeai` package is not installed by
default. Install it and set `LLM_PROVIDER=gemini` to use it.
"""
from __future__ import annotations

import json
from typing import Any

from app.core.logging import get_logger
from app.llm.base import LLMClient, LLMError

log = get_logger("llm.gemini")

DEFAULT_MODEL = "gemini-1.5-pro"


class GeminiClient(LLMClient):
    provider = "gemini"

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        if not api_key:
            raise LLMError("GEMINI_API_KEY is not set.")
        try:
            import google.generativeai as genai
        except ImportError as exc:  # pragma: no cover
            raise LLMError(
                "The 'google-generativeai' package is not installed. "
                "Run `pip install google-generativeai`."
            ) from exc
        genai.configure(api_key=api_key)
        self._genai = genai
        self.model = model

    def complete(self, *, system: str, user: str, max_tokens: int = 4096) -> str:
        try:
            model = self._genai.GenerativeModel(
                self.model, system_instruction=system
            )
            resp = model.generate_content(
                user,
                generation_config={"max_output_tokens": max_tokens},
            )
        except Exception as exc:  # pragma: no cover
            raise LLMError(f"Gemini request failed: {exc}") from exc
        return resp.text or ""

    def complete_structured(
        self, *, system: str, user: str, schema: dict[str, Any], max_tokens: int = 8000
    ) -> dict[str, Any]:
        try:
            model = self._genai.GenerativeModel(
                self.model, system_instruction=system
            )
            resp = model.generate_content(
                user,
                generation_config={
                    "max_output_tokens": max_tokens,
                    "response_mime_type": "application/json",
                    "response_schema": schema,
                },
            )
        except Exception as exc:  # pragma: no cover
            raise LLMError(f"Gemini structured request failed: {exc}") from exc
        try:
            return json.loads(resp.text or "{}")
        except json.JSONDecodeError as exc:
            raise LLMError(f"Model did not return valid JSON: {exc}") from exc
