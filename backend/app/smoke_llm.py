"""Live smoke test against the real LLM provider.

This is the proof that the AI path works end-to-end with the configured
provider (not a mock): the RFQ parser's structured-output schema, the draft
generators, and the rate-analysis structured output all hit the real API.

Run it once after setting your API key in `.env`:

    python -m app.smoke_llm

Cost: roughly a few cents per run (3 small requests). Exit code 0 = all pass.

It reuses the exact production code paths (`run_rfq_parser`, `run_missing_info`,
`run_rate_analysis`, and the real provider client) — there is no parallel
"test-only" implementation, so a PASS here means the app itself works.
"""
from __future__ import annotations

import sys
import traceback
from dataclasses import dataclass, field

from app.core.config import settings

EXAMPLE_RFQ = """\
Hi,

Please quote for 1x40HC from Shanghai to Jebel Ali.
Commodity: plastic household items.
Gross weight: 12,500 kg.
Cargo ready by 15 July.
Need ocean freight and destination charges.

Regards,
Ahmed
"""


@dataclass
class _Result:
    name: str
    ok: bool
    detail: str = ""
    notes: list[str] = field(default_factory=list)


def _print(r: _Result) -> None:
    mark = "PASS" if r.ok else "FAIL"
    print(f"[{mark}] {r.name}")
    if r.detail:
        print(f"       {r.detail}")
    for n in r.notes:
        print(f"       - {n}")


def _check_key() -> str | None:
    provider = settings.llm_provider.lower()
    key = {
        "anthropic": settings.anthropic_api_key,
        "openai": settings.openai_api_key,
        "gemini": settings.gemini_api_key,
    }.get(provider, "")
    if not key:
        return (
            f"No API key configured for LLM_PROVIDER={provider!r}.\n"
            f"  Set the matching key in your .env (e.g. ANTHROPIC_API_KEY=sk-ant-...)\n"
            f"  then re-run:  python -m app.smoke_llm"
        )
    return None


def _smoke_rfq_parser(llm) -> _Result:
    from app.agents.rfq_parser import run_rfq_parser

    extraction = run_rfq_parser(EXAMPLE_RFQ, llm)
    notes: list[str] = []
    problems: list[str] = []

    def expect(cond: bool, label: str) -> None:
        (notes if cond else problems).append(
            f"{label}: {'ok' if cond else 'UNEXPECTED'}"
        )

    expect(extraction.origin == "Shanghai", f"origin={extraction.origin!r}")
    expect(extraction.destination == "Jebel Ali", f"destination={extraction.destination!r}")
    expect(
        extraction.transport_mode is not None
        and extraction.transport_mode.value == "Sea",
        f"transport_mode={extraction.transport_mode}",
    )
    expect(
        extraction.container_type is not None
        and "40" in extraction.container_type,
        f"container_type={extraction.container_type!r}",
    )
    expect(bool(extraction.missing_fields), f"missing_fields={extraction.missing_fields}")
    # Incoterm is absent from the message → post-processing must flag it.
    expect("Incoterm" in extraction.missing_fields, "Incoterm flagged as missing")

    return _Result(
        name="RFQ parser (structured output schema)",
        ok=not problems,
        detail="; ".join(problems) if problems else "extraction matches the spec example",
        notes=notes,
    )


def _smoke_missing_info(llm) -> _Result:
    from app.agents.missing_info import run_missing_info

    draft = run_missing_info(
        context="- Origin: Shanghai\n- Destination: Jebel Ali\n- Container type: 40HC",
        missing_fields=["Incoterm", "HS code", "Pickup address"],
        customer_name="Ahmed",
        llm=llm,
    )
    ok = len(draft) > 80 and "Incoterm" in draft
    return _Result(
        name="Missing-info draft (free-form generation)",
        ok=ok,
        detail=f"draft length={len(draft)} chars"
        + ("" if ok else " — draft too short or does not mention the missing items"),
    )


def _smoke_rate_analysis(llm) -> _Result:
    from types import SimpleNamespace

    from app.agents.rate_analysis import run_rate_analysis

    # Synthetic rates shaped like the ORM rows the agent renders.
    def rate(id_, name, cost, transit):
        return SimpleNamespace(
            id=id_, partner_name=name, partner_type=None, cost_amount=cost,
            currency="USD", transit_time=transit, validity_date=None,
            free_time=None, included_charges="Ocean freight",
            excluded_charges="Destination THC", notes=None, risk_notes=None,
            reliability_score=None,
        )

    analysis = run_rate_analysis(
        context="- Origin: Shanghai\n- Destination: Jebel Ali\n- 1x40HC, plastic goods",
        rates=[rate(101, "Carrier A", 1500.0, "30 days"), rate(102, "Carrier B", 1750.0, "22 days")],
        llm=llm,
    )
    problems = []
    if analysis.recommended_rate_id not in (101, 102):
        problems.append(f"recommended_rate_id={analysis.recommended_rate_id} not in input ids")
    if len(analysis.options) != 2:
        problems.append(f"expected 2 options, got {len(analysis.options)}")
    return _Result(
        name="Rate analysis (constrained structured output)",
        ok=not problems,
        detail="; ".join(problems)
        if problems
        else f"recommended={analysis.recommended_rate_id}; reason={analysis.recommendation_reason!r}",
    )


def main() -> int:
    print("Freight AI Ops — live LLM smoke test")
    print(f"Provider: {settings.llm_provider}  Model: {settings.llm_model}\n")

    key_error = _check_key()
    if key_error:
        print(f"[FAIL] {key_error}")
        return 2

    from app.llm import get_llm

    try:
        llm = get_llm()
    except Exception as exc:
        print(f"[FAIL] Could not initialise the LLM client: {exc}")
        return 2

    results: list[_Result] = []
    for step in (_smoke_rfq_parser, _smoke_missing_info, _smoke_rate_analysis):
        try:
            results.append(step(llm))
        except Exception as exc:
            traceback.print_exc()
            results.append(_Result(name=step.__name__, ok=False, detail=str(exc)))
        _print(results[-1])

    passed = sum(1 for r in results if r.ok)
    print(f"\n{passed}/{len(results)} steps passed.")
    if passed == len(results):
        print("The real-LLM path is verified. You can trust the AI features in the app.")
        return 0
    print("At least one step failed — see details above. Common causes: wrong/expired")
    print("API key, no network access, or a provider-side schema rejection (report it).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
