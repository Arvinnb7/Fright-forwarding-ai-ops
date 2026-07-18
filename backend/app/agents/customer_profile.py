"""Customer-profile agent — turns CRM stats into a short useful summary."""
from __future__ import annotations

from app.llm.base import LLMClient
from app.models.customer import Customer
from app.prompts import load_prompt
from app.schemas.customer import CustomerStats


def run_customer_profile(
    *, customer: Customer, stats: CustomerStats, llm: LLMClient
) -> str:
    system = load_prompt("customer_profile")
    user = (
        f"Customer record:\n"
        f"- Company: {customer.company_name}\n"
        f"- Contact: {customer.contact_name or 'n/a'}\n"
        f"- Location: {customer.city or ''} {customer.country or ''}\n"
        f"- Industry: {customer.industry or 'n/a'}\n"
        f"- Notes: {customer.notes or '(none)'}\n\n"
        f"History statistics (accurate, do not change):\n"
        f"- RFQs received: {stats.rfq_count}\n"
        f"- Quotes issued: {stats.quote_count}\n"
        f"- Won: {stats.won_count}  Lost: {stats.lost_count}\n"
        f"- Average margin: "
        f"{stats.average_margin_percentage if stats.average_margin_percentage is not None else 'n/a'}%\n"
        f"- Typical routes: {', '.join(stats.typical_routes) or 'n/a'}"
    )
    return llm.complete(system=system, user=user, max_tokens=500).strip()
