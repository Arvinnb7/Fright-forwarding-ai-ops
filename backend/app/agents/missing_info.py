"""Missing Info agent — drafts a customer email requesting absent details.

Single LLM step (a draft generator), so it's a plain agent function rather than a
multi-node graph. Always returns an editable draft; nothing is sent.
"""
from __future__ import annotations

from app.core.config import settings
from app.llm.base import LLMClient
from app.prompts import load_prompt


def run_missing_info(
    *,
    context: str,
    missing_fields: list[str],
    customer_name: str | None,
    llm: LLMClient,
) -> str:
    system = load_prompt("missing_info")
    user = (
        f"Customer name: {customer_name or '[Customer Name]'}\n"
        f"Sender name: {settings.user_full_name}\n"
        f"Signature: {settings.email_signature}\n\n"
        f"Shipment details known so far:\n{context}\n\n"
        f"Missing information to request:\n"
        + "\n".join(f"- {m}" for m in missing_fields)
    )
    return llm.complete(system=system, user=user, max_tokens=1200).strip()
