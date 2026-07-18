"""Shipment-operations agents: document suggestions, status updates, issue drafts."""
from __future__ import annotations

from enum import Enum
from typing import Any

from app.core.config import settings
from app.llm.base import LLMClient
from app.models.booking import Booking
from app.models.issue import Issue
from app.prompts import load_prompt

# ── Document suggestions (structured) ────────────────────────

DOCUMENT_SUGGESTIONS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "suggestions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "document_type": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["document_type", "reason"],
            },
        }
    },
    "required": ["suggestions"],
}


def booking_context(booking: Booking) -> str:
    lines = [f"- Job number: {booking.job_number or booking.id}"]
    if booking.origin or booking.destination:
        lines.append(f"- Route: {booking.origin or '?'} → {booking.destination or '?'}")
    if booking.cargo_details:
        lines.append(f"- Cargo: {booking.cargo_details}")
    if booking.shipper:
        lines.append(f"- Shipper: {booking.shipper}")
    if booking.consignee:
        lines.append(f"- Consignee: {booking.consignee}")
    lines.append(f"- Current status: {booking.status.value}")
    if booking.etd:
        lines.append(f"- ETD: {booking.etd.isoformat()}")
    if booking.eta:
        lines.append(f"- ETA: {booking.eta.isoformat()}")
    return "\n".join(lines)


def run_document_suggestions(
    *, shipment_context: str, llm: LLMClient
) -> list[dict[str, str]]:
    system = load_prompt("document_suggestions")
    data = llm.complete_structured(
        system=system,
        user=f"Shipment:\n{shipment_context}",
        schema=DOCUMENT_SUGGESTIONS_SCHEMA,
    )
    return list(data.get("suggestions", []))


# ── Customer status update (draft) ───────────────────────────


def run_status_update(
    *,
    booking: Booking,
    status: str | None,
    etd: str | None,
    eta: str | None,
    extra_note: str | None,
    customer_name: str | None,
    llm: LLMClient,
) -> str:
    system = load_prompt("status_update")
    user = (
        f"Customer name: {customer_name or '[Customer Name]'}\n"
        f"Sender name: {settings.user_full_name}\n"
        f"Signature: {settings.email_signature}\n"
        f"Status to report: {status or booking.status.value}\n"
        f"ETD: {etd or (booking.etd.isoformat() if booking.etd else 'n/a')}\n"
        f"ETA: {eta or (booking.eta.isoformat() if booking.eta else 'n/a')}\n"
        f"Extra note: {extra_note or '(none)'}\n\n"
        f"Shipment context:\n{booking_context(booking)}"
    )
    return llm.complete(system=system, user=user, max_tokens=900).strip()


# ── Issue drafts ─────────────────────────────────────────────


class IssueDraftKind(str, Enum):
    ESCALATION = "escalation"
    CUSTOMER_EXPLANATION = "customer_explanation"


def run_issue_draft(
    *,
    issue: Issue,
    kind: IssueDraftKind,
    shipment_context: str | None,
    llm: LLMClient,
) -> str:
    system = load_prompt("issue_drafts")
    user = (
        f"Draft kind: {kind.value}\n"
        f"Sender name: {settings.user_full_name} ({settings.company_name})\n"
        f"Signature: {settings.email_signature}\n\n"
        f"Issue:\n"
        f"- Type: {issue.issue_type}\n"
        f"- Severity: {issue.severity.value}\n"
        f"- Description: {issue.description or '(none)'}\n"
        f"- Responsible party: {issue.responsible_party or 'n/a'}\n"
        f"- Next action: {issue.next_action or 'n/a'}\n"
        f"- Due date: {issue.due_date.isoformat() if issue.due_date else 'n/a'}\n\n"
        f"Shipment context:\n{shipment_context or '(no linked shipment)'}"
    )
    return llm.complete(system=system, user=user, max_tokens=900).strip()
