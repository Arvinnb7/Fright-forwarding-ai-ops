"""Quotation Builder agent (LangGraph) with human-in-the-loop pricing approval.

Flow B: load RFQ + selected rate → calculate margin → generate quote draft →
**interrupt() for human pricing approval** → finalize.

The graph compiles with a durable Postgres checkpointer and runs under a
thread_id derived from the quote id, so the run pauses at the pricing step and
resumes in a later request once the coordinator approves (or edits) the price.
Pricing is never finalized without that human step (spec §12).
"""
from __future__ import annotations

from datetime import date
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.core.logging import get_logger
from app.llm.base import LLMClient
from app.prompts import load_prompt
from app.services.margin import MarginInput, MarkupType, calculate_margin

log = get_logger("agent.quote_builder")


class QuoteState(TypedDict, total=False):
    # Inputs
    quote_id: int
    quote_number: str
    rfq_context: str
    cost_amount: float
    currency: str
    markup_type: str
    markup_value: float
    validity_date: str | None  # ISO date
    transit_time: str | None
    # Computed draft (before approval)
    selling_price: float
    gross_margin: float
    gross_margin_percentage: float
    warnings: list[str]
    draft_text: str
    review: dict[str, Any]
    # Final (after approval)
    approved: bool
    final_selling_price: float | None
    final_gross_margin: float | None
    final_gross_margin_percentage: float | None
    final_quote_text: str | None


def _get_llm(config: dict[str, Any]) -> LLMClient:
    llm = (config or {}).get("configurable", {}).get("llm")
    if llm is None:
        raise RuntimeError("No LLM client provided to the quote builder graph.")
    return llm


def _margin_for(state: QuoteState, selling_override: float | None = None):
    validity = (
        date.fromisoformat(state["validity_date"]) if state.get("validity_date") else None
    )
    return calculate_margin(
        MarginInput(
            cost_amount=float(state.get("cost_amount") or 0.0),
            markup_type=MarkupType(state.get("markup_type", "percent")),
            markup_value=float(state.get("markup_value") or 0.0),
            currency=state.get("currency", "USD"),
            validity_date=validity,
            selling_price_override=selling_override,
        )
    )


def _draft_node(state: QuoteState, config: dict[str, Any]) -> QuoteState:
    llm = _get_llm(config)
    margin = _margin_for(state)
    system = load_prompt("quote_drafting")
    user = (
        f"Quote number: {state.get('quote_number', '')}\n"
        f"Selling price: {margin.selling_price} {margin.currency}\n"
        f"Transit time: {state.get('transit_time') or 'n/a'}\n"
        f"Validity date: {state.get('validity_date') or 'n/a'}\n\n"
        f"Shipment details:\n{state['rfq_context']}"
    )
    draft_text = llm.complete(system=system, user=user, max_tokens=2000).strip()
    review = {
        "quote_id": state.get("quote_id"),
        "cost_amount": margin.cost_amount,
        "selling_price": margin.selling_price,
        "gross_margin": margin.gross_margin,
        "gross_margin_percentage": margin.gross_margin_percentage,
        "currency": margin.currency,
        "warnings": margin.warnings,
        "draft_text": draft_text,
    }
    return {
        "selling_price": margin.selling_price,
        "gross_margin": margin.gross_margin,
        "gross_margin_percentage": margin.gross_margin_percentage,
        "warnings": margin.warnings,
        "draft_text": draft_text,
        "review": review,
    }


def _approval_node(state: QuoteState, config: dict[str, Any]) -> QuoteState:
    # Pause here until a human approves/edits the pricing. The value passed to
    # interrupt() is the review payload; resume delivers the decision.
    decision: dict[str, Any] = interrupt(state["review"])

    approved = bool(decision.get("approved"))
    if not approved:
        return {
            "approved": False,
            "final_selling_price": None,
            "final_gross_margin": None,
            "final_gross_margin_percentage": None,
            "final_quote_text": None,
        }

    override = decision.get("selling_price")
    if override is not None and float(override) != state.get("selling_price"):
        margin = _margin_for(state, selling_override=float(override))
        selling, gm, gmp = (
            margin.selling_price,
            margin.gross_margin,
            margin.gross_margin_percentage,
        )
    else:
        selling = state.get("selling_price")
        gm = state.get("gross_margin")
        gmp = state.get("gross_margin_percentage")

    return {
        "approved": True,
        "final_selling_price": selling,
        "final_gross_margin": gm,
        "final_gross_margin_percentage": gmp,
        "final_quote_text": decision.get("quote_text") or state.get("draft_text"),
    }


def build_quote_graph(checkpointer):
    graph = StateGraph(QuoteState)
    graph.add_node("draft", _draft_node)
    graph.add_node("approval", _approval_node)
    graph.add_edge(START, "draft")
    graph.add_edge("draft", "approval")
    graph.add_edge("approval", END)
    return graph.compile(checkpointer=checkpointer)


_compiled = None


def get_quote_graph():
    """Lazily compile the graph with the durable Postgres checkpointer."""
    global _compiled
    if _compiled is None:
        from app.agents.checkpointer import get_postgres_checkpointer

        _compiled = build_quote_graph(get_postgres_checkpointer())
    return _compiled
