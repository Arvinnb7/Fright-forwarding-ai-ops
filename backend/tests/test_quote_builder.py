"""Quote builder graph: pause at pricing interrupt, then resume on approval.

Uses an in-memory checkpointer so the test needs no Postgres.
"""
from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.agents.quote_builder import build_quote_graph

INITIAL = {
    "quote_id": 1,
    "quote_number": "Q-2026-0001",
    "rfq_context": "- Origin: Shanghai\n- Destination: Jebel Ali",
    "cost_amount": 1500.0,
    "currency": "USD",
    "markup_type": "percent",
    "markup_value": 20.0,
    "validity_date": None,
    "transit_time": "30 days",
}


def _graph(fake_llm):
    fake_llm.text_response = "QUOTATION DRAFT — total as provided."
    g = build_quote_graph(MemorySaver())
    return g, {"configurable": {"thread_id": "quote-1", "llm": fake_llm}}


def test_graph_pauses_at_pricing_interrupt(fake_llm):
    g, cfg = _graph(fake_llm)
    g.invoke(INITIAL, config=cfg)
    state = g.get_state(cfg)
    # Paused before completing: the approval node is still pending.
    assert state.next == ("approval",)
    review = state.values["review"]
    assert review["selling_price"] == 1800.0
    assert review["gross_margin"] == 300.0
    assert round(review["gross_margin_percentage"], 1) == 16.7
    assert review["draft_text"]


def test_resume_approves_with_price_edit(fake_llm):
    g, cfg = _graph(fake_llm)
    g.invoke(INITIAL, config=cfg)
    g.invoke(Command(resume={"approved": True, "selling_price": 2000}), config=cfg)
    values = g.get_state(cfg).values
    assert values["approved"] is True
    assert values["final_selling_price"] == 2000.0
    assert values["final_gross_margin"] == 500.0  # recomputed against cost 1500


def test_resume_rejects(fake_llm):
    g, cfg = _graph(fake_llm)
    g.invoke(INITIAL, config=cfg)
    g.invoke(Command(resume={"approved": False}), config=cfg)
    values = g.get_state(cfg).values
    assert values["approved"] is False
    assert values.get("final_selling_price") is None
