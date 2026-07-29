"""Run the extraction evaluation and report it.

Deliberately runs the **production** parser (`run_rfq_parser`, the real prompt,
the real schema, the real post-processing) rather than a parallel test-only
path, so a score here is a statement about the shipped system.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from app.agents.rfq_parser import run_rfq_parser
from app.eval.scoring import (
    BOOLEAN_FIELDS,
    FIELD_COMPARATORS,
    LIST_FIELDS,
    FieldScore,
    Outcome,
    classify,
    compare_bool,
    score_list_field,
)
from app.llm.base import LLMClient

CORPUS_PATH = Path(__file__).parent / "corpus" / "rfq_extraction.jsonl"


@dataclass
class CaseResult:
    case_id: str
    tags: list[str]
    outcomes: dict[str, Outcome]
    errors: list[str] = field(default_factory=list)
    failure: str | None = None

    @property
    def mistakes(self) -> list[str]:
        return self.errors


@dataclass
class EvalReport:
    per_field: dict[str, FieldScore]
    cases: list[CaseResult]
    list_matched: int = 0
    list_produced: int = 0
    list_expected: int = 0

    # ── Headline numbers ─────────────────────────────────────

    @property
    def totals(self) -> dict[Outcome, int]:
        combined = {outcome: 0 for outcome in Outcome}
        for score in self.per_field.values():
            for outcome, count in score.outcomes.items():
                combined[outcome] += count
        return combined

    @property
    def accuracy(self) -> float | None:
        """Share of every judgement that was right, including correct nulls.

        Correct silence counts: choosing not to fill a field the customer never
        mentioned is a right answer, and the most valuable one.
        """
        totals = self.totals
        judged = sum(totals.values())
        if judged == 0:
            return None
        return (totals[Outcome.CORRECT] + totals[Outcome.CORRECTLY_EMPTY]) / judged

    @property
    def precision(self) -> float | None:
        totals = self.totals
        produced = totals[Outcome.CORRECT] + totals[Outcome.WRONG] + totals[Outcome.INVENTED]
        return totals[Outcome.CORRECT] / produced if produced else None

    @property
    def recall(self) -> float | None:
        totals = self.totals
        available = totals[Outcome.CORRECT] + totals[Outcome.WRONG] + totals[Outcome.MISSED]
        return totals[Outcome.CORRECT] / available if available else None

    @property
    def hallucination_rate(self) -> float | None:
        """The number that decides whether this is safe to put in front of a
        customer: how often a value was produced for something never stated."""
        totals = self.totals
        opportunities = totals[Outcome.INVENTED] + totals[Outcome.CORRECTLY_EMPTY]
        return totals[Outcome.INVENTED] / opportunities if opportunities else None

    @property
    def charges_precision(self) -> float | None:
        return self.list_matched / self.list_produced if self.list_produced else None

    @property
    def charges_recall(self) -> float | None:
        return self.list_matched / self.list_expected if self.list_expected else None

    @property
    def failed_cases(self) -> list[CaseResult]:
        return [case for case in self.cases if case.failure]

    def as_dict(self) -> dict[str, Any]:
        return {
            "cases": len(self.cases),
            "failed_cases": len(self.failed_cases),
            "judgements": sum(self.totals.values()),
            "accuracy": self.accuracy,
            "precision": self.precision,
            "recall": self.recall,
            "hallucination_rate": self.hallucination_rate,
            "outcomes": {o.value: c for o, c in self.totals.items()},
            "charges_precision": self.charges_precision,
            "charges_recall": self.charges_recall,
            "per_field": {
                name: {
                    "precision": score.precision,
                    "recall": score.recall,
                    "f1": score.f1,
                    "hallucination_rate": score.hallucination_rate,
                    "outcomes": {o.value: c for o, c in score.outcomes.items()},
                }
                for name, score in sorted(self.per_field.items())
            },
        }


def load_corpus(path: Path | None = None) -> list[dict[str, Any]]:
    """Read the labelled cases.

    JSONL and file-based on purpose: swapping this for a customer's own emails
    during a pilot is dropping in a different file, not editing code.
    """
    source = path or CORPUS_PATH
    cases = []
    for number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            cases.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{source.name} line {number} is not valid JSON: {exc}") from exc
    return cases


def _describe(value: Any) -> str:
    return "∅" if value in (None, "") else repr(value)


def evaluate_case(case: dict[str, Any], extraction: dict[str, Any]) -> CaseResult:
    """Compare one extraction against its labels."""
    result = CaseResult(case_id=case["id"], tags=case.get("tags", []), outcomes={})
    expected = case["expected"]

    for name, gold in expected.items():
        if name in LIST_FIELDS:
            continue
        actual = extraction.get(name)
        if name in BOOLEAN_FIELDS:
            # Booleans default to False, so "expected null" is meaningless here:
            # the question is only whether the flag matches.
            outcome = (
                Outcome.CORRECT if compare_bool(gold, actual) else Outcome.WRONG
            )
        else:
            comparator = FIELD_COMPARATORS.get(name)
            if comparator is None:
                continue
            outcome = classify(gold, actual, comparator)

        result.outcomes[name] = outcome
        if outcome in (Outcome.WRONG, Outcome.MISSED, Outcome.INVENTED):
            result.errors.append(
                f"{name}: {outcome.value} — expected {_describe(gold)}, "
                f"got {_describe(actual)}"
            )
    return result


def run_evaluation(
    llm: LLMClient,
    cases: Iterable[dict[str, Any]] | None = None,
    *,
    on_case: Any = None,
) -> EvalReport:
    """Parse every case with the production parser and score the results."""
    cases = list(cases if cases is not None else load_corpus())
    per_field: dict[str, FieldScore] = {}
    results: list[CaseResult] = []
    list_matched = list_produced = list_expected = 0

    for case in cases:
        try:
            extraction = run_rfq_parser(case["email"], llm).model_dump(mode="json")
        except Exception as exc:  # noqa: BLE001 - a crash is a result, not a stop
            # A case that cannot be parsed at all is a failure of the system, so
            # it stays in the report instead of aborting the run.
            results.append(
                CaseResult(
                    case_id=case["id"],
                    tags=case.get("tags", []),
                    outcomes={},
                    failure=f"{type(exc).__name__}: {exc}",
                )
            )
            if on_case:
                on_case(results[-1])
            continue

        result = evaluate_case(case, extraction)
        for name, outcome in result.outcomes.items():
            per_field.setdefault(name, FieldScore()).record(outcome)

        for name in LIST_FIELDS:
            if name in case["expected"]:
                matched, produced, expected_count = score_list_field(
                    case["expected"][name], extraction.get(name)
                )
                list_matched += matched
                list_produced += produced
                list_expected += expected_count

        results.append(result)
        if on_case:
            on_case(result)

    return EvalReport(
        per_field=per_field,
        cases=results,
        list_matched=list_matched,
        list_produced=list_produced,
        list_expected=list_expected,
    )
