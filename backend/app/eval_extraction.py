"""Measure how accurately the RFQ parser reads real-shaped freight enquiries.

    python -m app.eval_extraction              # against your configured provider
    python -m app.eval_extraction --stub       # harness self-check, no API key
    python -m app.eval_extraction --json       # machine-readable, for CI
    python -m app.eval_extraction --min-accuracy 0.85 --max-hallucination 0.05

"The AI reads your emails" is a claim, not a number. This turns it into one, per
field, against 40 hand-labelled cases written to look like the correspondence a
freight desk actually receives — telegraphic one-liners, forwarded chains,
non-native English, signature-block noise, pasted tables, replies that are not
enquiries at all, and traps like "delivered to our office" (which is not DDP)
and "Ningbo, NOT Shanghai".

**The corpus is synthetic**, because no customer email archive was available
when it was written. It is stored as a plain JSONL file precisely so a pilot
customer's own labelled emails can replace it without touching any code — and
the number should be re-measured on that before it is quoted to anyone.

Three failure modes are reported separately, because they are not equally bad:
a *missed* field costs a follow-up question, a *wrong* field costs a wrong
quotation, and an *invented* field is a number the customer never gave being
used to price their shipment. The last is reported as a hallucination rate and
is the figure to look at first.
"""
from __future__ import annotations

import argparse
import json
import sys

from app.eval.runner import EvalReport, load_corpus, run_evaluation
from app.eval.stub import FabricatingLLM, LazyLLM, OracleLLM

_STUBS = {"oracle": OracleLLM, "lazy": LazyLLM, "fabricating": FabricatingLLM}


def _percent(value: float | None) -> str:
    return "  n/a" if value is None else f"{value * 100:5.1f}%"


def print_report(report: EvalReport, *, verbose: bool) -> None:
    totals = report.totals
    print()
    print("=" * 74)
    print(f"RFQ extraction accuracy — {len(report.cases)} cases, "
          f"{sum(totals.values())} field judgements")
    print("=" * 74)
    print(f"  Accuracy (all judgements right)   {_percent(report.accuracy)}")
    print(f"  Precision (produced values right) {_percent(report.precision)}")
    print(f"  Recall (available values found)   {_percent(report.recall)}")
    print(f"  Hallucination rate                {_percent(report.hallucination_rate)}"
          "   ← invented, never stated")
    print()
    for outcome, count in totals.items():
        print(f"  {outcome.value:<16} {count:>5}")
    if report.charges_recall is not None:
        print(f"  requested charges  precision {_percent(report.charges_precision)}"
              f"  recall {_percent(report.charges_recall)}")
    if report.failed_cases:
        print(f"  cases that failed to parse at all: {len(report.failed_cases)}")

    print()
    print(f"  {'field':<24}{'prec':>7}{'recall':>8}{'F1':>8}{'halluc':>9}")
    print("  " + "-" * 56)
    for name, score in sorted(report.per_field.items()):
        print(
            f"  {name:<24}{_percent(score.precision):>7}{_percent(score.recall):>8}"
            f"{_percent(score.f1):>8}{_percent(score.hallucination_rate):>9}"
        )

    mistakes = [case for case in report.cases if case.mistakes or case.failure]
    if mistakes:
        print()
        print(f"  {len(mistakes)} case(s) with at least one mistake:")
        for case in mistakes if verbose else mistakes[:10]:
            label = f"{case.case_id} [{', '.join(case.tags)}]"
            print(f"    • {label}")
            if case.failure:
                print(f"        parse failed: {case.failure}")
            for mistake in case.mistakes:
                print(f"        {mistake}")
        if not verbose and len(mistakes) > 10:
            print(f"    … {len(mistakes) - 10} more (use --verbose)")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.eval_extraction",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--stub",
        nargs="?",
        const="oracle",
        choices=sorted(_STUBS),
        help="Run without a provider. 'oracle' must score 100%% (a harness "
             "self-check); 'lazy' and 'fabricating' demonstrate that missed and "
             "invented values are scored differently. Never an accuracy claim.",
    )
    parser.add_argument("--json", action="store_true", help="Machine-readable output.")
    parser.add_argument("--verbose", action="store_true", help="List every mistake.")
    parser.add_argument("--tag", help="Only run cases carrying this tag.")
    parser.add_argument(
        "--min-accuracy", type=float, default=None,
        help="Exit non-zero below this accuracy (regression gate).",
    )
    parser.add_argument(
        "--max-hallucination", type=float, default=None,
        help="Exit non-zero above this hallucination rate.",
    )
    args = parser.parse_args()

    cases = load_corpus()
    if args.tag:
        cases = [case for case in cases if args.tag in case.get("tags", [])]
        if not cases:
            print(f"No cases tagged {args.tag!r}.", file=sys.stderr)
            return 2

    if args.stub:
        llm = _STUBS[args.stub](cases)
        if not args.json:
            print(f"Running against the '{args.stub}' stub — this measures the "
                  "harness, not the model.")
    else:
        from app.core.config import settings
        from app.llm import get_llm
        from app.llm.base import LLMError

        try:
            llm = get_llm()
        except LLMError as exc:
            print(f"No usable LLM provider: {exc}", file=sys.stderr)
            return 2
        key_names = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "gemini": "GEMINI_API_KEY",
        }
        key_name = key_names.get(settings.llm_provider.lower(), "the provider API key")
        if not getattr(settings, key_name.lower(), ""):
            print(
                f"{key_name} is not set, so the real number cannot be measured.\n"
                f"Set it in .env, or run `python -m app.eval_extraction --stub` "
                f"to check the harness itself.",
                file=sys.stderr,
            )
            return 2
        if not args.json:
            print(f"Running {len(cases)} cases against {llm.provider}/{llm.model}. "
                  "This costs roughly a few cents.")

    report = run_evaluation(llm, cases)

    if args.json:
        print(json.dumps(report.as_dict(), indent=2))
    else:
        print_report(report, verbose=args.verbose)

    exit_code = 0
    if args.min_accuracy is not None:
        accuracy = report.accuracy or 0.0
        if accuracy < args.min_accuracy:
            print(
                f"FAIL: accuracy {accuracy:.1%} is below the required "
                f"{args.min_accuracy:.1%}.",
                file=sys.stderr,
            )
            exit_code = 1
    if args.max_hallucination is not None:
        rate = report.hallucination_rate or 0.0
        if rate > args.max_hallucination:
            print(
                f"FAIL: hallucination rate {rate:.1%} exceeds the allowed "
                f"{args.max_hallucination:.1%}.",
                file=sys.stderr,
            )
            exit_code = 1
    if report.failed_cases:
        print(
            f"FAIL: {len(report.failed_cases)} case(s) could not be parsed at all.",
            file=sys.stderr,
        )
        exit_code = 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
