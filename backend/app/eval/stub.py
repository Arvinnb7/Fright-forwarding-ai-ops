"""Stub clients for exercising the harness without a provider.

These do **not** measure accuracy and must never be reported as if they did.
Their job is to prove the harness itself is sound, which is what CI can check
on every commit for free:

* the oracle returns the labels, so a correct harness must score 100% — if it
  does not, the corpus or the scoring is broken, not the model;
* the lazy and the fabricating clients produce known kinds of mistake, so the
  report demonstrably distinguishes *missed* from *invented*.

The real number needs a real provider and a real key; see `--help`.
"""
from __future__ import annotations

from typing import Any

from app.llm.base import LLMClient


class _Base(LLMClient):
    provider = "stub"
    model = "stub"

    def __init__(self, cases: list[dict[str, Any]]) -> None:
        # Keyed by the email text: the parser passes it through verbatim.
        self._by_email = {case["email"]: case for case in cases}

    def _case_for(self, user: str) -> dict[str, Any]:
        for email, case in self._by_email.items():
            if email in user:
                return case
        raise LookupError("Stub was asked about text that is not in the corpus.")

    def complete(self, *, system: str, user: str, max_tokens: int = 4096) -> str:
        return "stub draft"

    def complete_structured(
        self, *, system: str, user: str, schema: dict[str, Any], max_tokens: int = 8000
    ) -> dict[str, Any]:
        raise NotImplementedError


class OracleLLM(_Base):
    """Returns exactly the labelled answer. A sound harness scores 100%."""

    model = "stub-oracle"

    def complete_structured(
        self, *, system: str, user: str, schema: dict[str, Any], max_tokens: int = 8000
    ) -> dict[str, Any]:
        expected = dict(self._case_for(user)["expected"])
        allowed = set(schema.get("properties", {}))
        return {key: value for key, value in expected.items() if key in allowed}


class LazyLLM(_Base):
    """Extracts nothing. Should score high on hallucination safety and badly on
    recall — which is exactly the asymmetry the report is meant to show."""

    model = "stub-lazy"

    def complete_structured(
        self, *, system: str, user: str, schema: dict[str, Any], max_tokens: int = 8000
    ) -> dict[str, Any]:
        return {}


class FabricatingLLM(_Base):
    """Fills every field it is allowed to, whether or not the customer said so.

    The failure mode that matters most in freight, and the one a single accuracy
    percentage would disguise.
    """

    model = "stub-fabricating"

    def complete_structured(
        self, *, system: str, user: str, schema: dict[str, Any], max_tokens: int = 8000
    ) -> dict[str, Any]:
        case = self._case_for(user)
        properties = schema.get("properties", {})
        output: dict[str, Any] = {}
        for key, value in case["expected"].items():
            if key not in properties:
                continue
            # Where the truth is "nothing was said", say something anyway — but
            # something *plausible*, so this demonstrates confident invention
            # rather than malformed output the schema would have caught anyway.
            output[key] = value if value is not None else _plausible(properties[key])
        return output


def _plausible(field_schema: dict[str, Any]) -> Any:
    """A believable value of the right shape for a field."""
    allowed = [option for option in field_schema.get("enum", []) if option is not None]
    if allowed:
        return allowed[0]
    types = field_schema.get("type", "string")
    types = types if isinstance(types, list) else [types]
    if "boolean" in types:
        return True
    if "number" in types or "integer" in types:
        return 1
    if "array" in types:
        return ["Ocean freight"]
    return "Invented"
