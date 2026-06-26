"""Rate Request agent — drafts a partner-specific rate-request message."""
from __future__ import annotations

from app.core.config import settings
from app.llm.base import LLMClient
from app.models.enums import PartnerType, TransportMode
from app.prompts import load_prompt


def run_rate_request(
    *,
    context: str,
    partner_type: PartnerType,
    transport_mode: TransportMode | None,
    partner_name: str | None,
    llm: LLMClient,
) -> str:
    system = load_prompt("rate_request")
    mode = transport_mode.value if transport_mode else "(not specified)"
    user = (
        f"Partner type: {partner_type.value}\n"
        f"Partner name: {partner_name or '[Partner Name]'}\n"
        f"Transport mode: {mode}\n"
        f"Sender name: {settings.user_full_name} ({settings.company_name})\n"
        f"Signature: {settings.email_signature}\n\n"
        f"Shipment details:\n{context}"
    )
    return llm.complete(system=system, user=user, max_tokens=1500).strip()
