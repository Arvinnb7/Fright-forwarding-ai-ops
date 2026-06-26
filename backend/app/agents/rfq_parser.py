"""RFQ Parser agent (LangGraph).

Flow A, step 1–4: parse a raw customer message into a structured RFQ, validate
the extraction, and consolidate the list of missing fields.

The graph is intentionally small but real: it establishes the pattern (typed
state, injectable LLM via config, post-processing node) the other agents reuse.
"""
from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.core.logging import get_logger
from app.llm.base import LLMClient
from app.prompts import load_prompt
from app.schemas.rfq import RFQ_EXTRACTION_SCHEMA, RFQExtraction

log = get_logger("agent.rfq_parser")

# Fields that, if absent, almost always need to be requested before pricing.
_PRICING_CRITICAL = {
    "commodity": "Commodity description",
    "gross_weight": "Gross weight",
    "incoterm": "Incoterm",
    "origin": "Origin",
    "destination": "Destination",
}


class RFQParserState(TypedDict, total=False):
    raw_message: str
    extraction: dict[str, Any]
    error: str | None


def _get_llm(config: dict[str, Any]) -> LLMClient:
    llm = (config or {}).get("configurable", {}).get("llm")
    if llm is None:  # pragma: no cover - guarded by callers
        raise RuntimeError("No LLM client provided to the RFQ parser graph.")
    return llm


def _extract_node(state: RFQParserState, config: dict[str, Any]) -> RFQParserState:
    llm = _get_llm(config)
    system = load_prompt("rfq_parser")
    raw = state["raw_message"]
    data = llm.complete_structured(
        system=system,
        user=f"Customer inquiry:\n\n{raw}",
        schema=RFQ_EXTRACTION_SCHEMA,
    )
    # Validate / normalize through the Pydantic contract.
    extraction = RFQExtraction.model_validate(data)
    return {"extraction": extraction.model_dump(mode="json")}


def _post_process_node(state: RFQParserState, config: dict[str, Any]) -> RFQParserState:
    extraction = dict(state["extraction"])
    missing = list(extraction.get("missing_fields") or [])
    # Make sure pricing-critical gaps are always flagged, even if the model
    # forgot them.
    for field, label in _PRICING_CRITICAL.items():
        if not extraction.get(field) and label not in missing:
            missing.append(label)
    extraction["missing_fields"] = missing
    return {"extraction": extraction}


def build_rfq_parser_graph():
    graph = StateGraph(RFQParserState)
    graph.add_node("extract", _extract_node)
    graph.add_node("post_process", _post_process_node)
    graph.add_edge(START, "extract")
    graph.add_edge("extract", "post_process")
    graph.add_edge("post_process", END)
    return graph.compile()


# Compiled once; the LLM is injected per-invocation via config.
_compiled = build_rfq_parser_graph()


def run_rfq_parser(raw_message: str, llm: LLMClient) -> RFQExtraction:
    """Parse a raw customer message into a validated RFQExtraction."""
    result = _compiled.invoke(
        {"raw_message": raw_message},
        config={"configurable": {"llm": llm}},
    )
    return RFQExtraction.model_validate(result["extraction"])
