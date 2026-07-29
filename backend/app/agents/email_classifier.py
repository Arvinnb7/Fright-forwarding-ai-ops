"""Email triage agent — decides what an incoming message is.

Structured output constrained to the routing categories, so the ingestion
pipeline can branch on a validated enum rather than free text.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.llm.base import LLMClient
from app.models.email_message import EmailClassification
from app.prompts import load_prompt

_CATEGORIES = [
    EmailClassification.NEW_RFQ.value,
    EmailClassification.RATE_REPLY.value,
    EmailClassification.CUSTOMER_REPLY.value,
    EmailClassification.NOT_RELEVANT.value,
]

EMAIL_CLASSIFICATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "classification": {"type": "string", "enum": _CATEGORIES},
        "confidence": {"type": "number"},
        "reason": {"type": "string"},
        "mentions_reference": {"type": ["string", "null"]},
    },
    "required": ["classification", "confidence", "reason", "mentions_reference"],
}

# Enough context to classify without paying for a whole quotation thread.
_MAX_BODY_CHARS = 4000


class EmailTriage(BaseModel):
    classification: EmailClassification
    confidence: float = 0.0
    reason: str = ""
    mentions_reference: str | None = None


def run_email_classifier(
    *,
    subject: str | None,
    body: str | None,
    from_address: str | None,
    llm: LLMClient,
) -> EmailTriage:
    system = load_prompt("email_classifier")
    user = (
        f"From: {from_address or 'unknown'}\n"
        f"Subject: {subject or '(no subject)'}\n\n"
        f"Body:\n{(body or '')[:_MAX_BODY_CHARS]}"
    )
    data = llm.complete_structured(
        system=system, user=user, schema=EMAIL_CLASSIFICATION_SCHEMA
    )
    return EmailTriage.model_validate(data)
