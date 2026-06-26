"""Follow-Up agent — drafts a customer follow-up message in the chosen tone."""
from __future__ import annotations

from enum import Enum

from app.core.config import settings
from app.llm.base import LLMClient
from app.prompts import load_prompt


class FollowUpType(str, Enum):
    POLITE = "polite"
    SHORT_WHATSAPP = "short_whatsapp"
    DISCOUNT_RESPONSE = "discount_response"
    REVISED = "revised"
    FINAL = "final"
    LOST_REASON_REQUEST = "lost_reason_request"


def run_follow_up(
    *,
    context: str,
    follow_up_type: FollowUpType,
    days_since_sent: int | None,
    customer_name: str | None,
    llm: LLMClient,
) -> str:
    system = load_prompt("follow_up")
    user = (
        f"Follow-up type: {follow_up_type.value}\n"
        f"Days since the quote was sent: {days_since_sent if days_since_sent is not None else 'n/a'}\n"
        f"Customer name: {customer_name or '[Customer Name]'}\n"
        f"Sender name: {settings.user_full_name}\n"
        f"Signature: {settings.email_signature}\n\n"
        f"Quotation context:\n{context}"
    )
    return llm.complete(system=system, user=user, max_tokens=900).strip()
