"""Field-level scoring for RFQ extraction.

"The AI reads your emails" is worth nothing without a number attached, and the
number has to be one that would embarrass us if it were bad. So this scores per
field, against hand-written expected answers, and separates three failure modes
that are emphatically not equivalent in freight:

* **missed** — the field was there and we left it null. The coordinator asks the
  customer. Annoying, cheap.
* **wrong** — we filled it with something else. A quote goes out against the
  wrong weight or the wrong port.
* **invented** — the customer never said it and we produced a value anyway.
  This is the dangerous one, and it is reported separately as a *hallucination
  rate* rather than being averaged away into an accuracy figure.

A single headline percentage would hide that distinction, so the report prints
all three. Comparison is deliberately tolerant of formatting ("12,500 kg" and
"12500 KG" are the same answer) and intolerant of meaning ("Ningbo" is not
"Shanghai") — the place comparator is the same normaliser the product uses to
match lanes, so the eval measures what the system actually does.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from app.services.lanes import normalize_place

# ── Comparators ──────────────────────────────────────────────


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, Enum):
        value = value.value
    return str(value).strip()


def compare_place(expected: Any, actual: Any) -> bool:
    """Ports and cities, using the product's own lane normaliser."""
    return normalize_place(_text(expected)) == normalize_place(_text(actual))


def compare_code(expected: Any, actual: Any) -> bool:
    """Codes and enums: case and punctuation are noise, characters are not."""
    strip = lambda v: re.sub(r"[^a-z0-9]", "", _text(v).casefold())  # noqa: E731
    return strip(expected) == strip(actual)


def compare_measure(expected: Any, actual: Any) -> bool:
    """Quantities: "12,500 kg", "12500KG" and "12.5 t" are written differently.

    Only the first two are the same answer — a unit change is a different
    number, and silently accepting it would hide a real extraction error.
    """
    normalise = lambda v: re.sub(r"[\s,]", "", _text(v).casefold())  # noqa: E731
    return normalise(expected) == normalise(actual)


def compare_text(expected: Any, actual: Any) -> bool:
    """Free text (commodity, special handling): the expected words must be
    present, extra words are tolerated.

    "plastic household items" against "Plastic household items (assorted)" is a
    correct extraction; demanding an exact string would measure phrasing rather
    than comprehension.
    """
    expected_tokens = set(re.findall(r"[a-z0-9]+", _text(expected).casefold()))
    actual_tokens = set(re.findall(r"[a-z0-9]+", _text(actual).casefold()))
    if not expected_tokens:
        return not actual_tokens
    return expected_tokens <= actual_tokens


def compare_bool(expected: Any, actual: Any) -> bool:
    return bool(expected) == bool(actual)


# ── Field registry ───────────────────────────────────────────

# Scored fields and how each is compared. Fields not listed are ignored on
# purpose: `recommended_next_action` and `urgency_score` are advisory prose and
# a confidence number, and scoring them would reward fluency instead of accuracy.
FIELD_COMPARATORS: dict[str, Callable[[Any, Any], bool]] = {
    "origin": compare_place,
    "destination": compare_place,
    "pickup_address": compare_text,
    "delivery_address": compare_text,
    "transport_mode": compare_code,
    "shipment_type": compare_code,
    "container_type": compare_code,
    "commodity": compare_text,
    "hs_code": compare_code,
    "gross_weight": compare_measure,
    "cbm": compare_measure,
    "dimensions": compare_measure,
    "package_count": compare_measure,
    "incoterm": compare_code,
    "cargo_ready_date_text": compare_text,
    "customer_company": compare_text,
    "contact_name": compare_text,
    "contact_email": compare_code,
    "contact_phone": compare_measure,
    "temperature_requirement": compare_text,
    "special_handling": compare_text,
    "urgency": compare_code,
}

BOOLEAN_FIELDS = (
    "dangerous_goods",
    "insurance_required",
    "customs_required",
    "warehouse_required",
)

# Scored as sets, with their own precision and recall.
LIST_FIELDS = ("requested_charges",)


# ── Outcomes ─────────────────────────────────────────────────


class Outcome(str, Enum):
    CORRECT = "correct"  # expected a value, got the right one
    MISSED = "missed"  # expected a value, got null
    WRONG = "wrong"  # expected a value, got a different one
    INVENTED = "invented"  # expected null, got a value  ← the dangerous one
    CORRECTLY_EMPTY = "correctly_empty"  # expected null, got null


@dataclass
class FieldScore:
    outcomes: dict[Outcome, int] = field(
        default_factory=lambda: {outcome: 0 for outcome in Outcome}
    )

    def record(self, outcome: Outcome) -> None:
        self.outcomes[outcome] += 1

    @property
    def expected_values(self) -> int:
        return (
            self.outcomes[Outcome.CORRECT]
            + self.outcomes[Outcome.MISSED]
            + self.outcomes[Outcome.WRONG]
        )

    @property
    def produced_values(self) -> int:
        return (
            self.outcomes[Outcome.CORRECT]
            + self.outcomes[Outcome.WRONG]
            + self.outcomes[Outcome.INVENTED]
        )

    @property
    def precision(self) -> float | None:
        """Of the values produced, how many were right."""
        if self.produced_values == 0:
            return None
        return self.outcomes[Outcome.CORRECT] / self.produced_values

    @property
    def recall(self) -> float | None:
        """Of the values that were there to find, how many were found."""
        if self.expected_values == 0:
            return None
        return self.outcomes[Outcome.CORRECT] / self.expected_values

    @property
    def f1(self) -> float | None:
        precision, recall = self.precision, self.recall
        if precision is None or recall is None or precision + recall == 0:
            return None
        return 2 * precision * recall / (precision + recall)

    @property
    def opportunities_to_invent(self) -> int:
        return self.outcomes[Outcome.INVENTED] + self.outcomes[Outcome.CORRECTLY_EMPTY]

    @property
    def hallucination_rate(self) -> float | None:
        """How often a value was produced for something never stated."""
        if self.opportunities_to_invent == 0:
            return None
        return self.outcomes[Outcome.INVENTED] / self.opportunities_to_invent


def classify(expected: Any, actual: Any, comparator: Callable[[Any, Any], bool]) -> Outcome:
    """Place one (expected, actual) pair into exactly one outcome."""
    expected_present = expected is not None and _text(expected) != ""
    actual_present = actual is not None and _text(actual) != ""

    if not expected_present and not actual_present:
        return Outcome.CORRECTLY_EMPTY
    if not expected_present:
        return Outcome.INVENTED
    if not actual_present:
        return Outcome.MISSED
    return Outcome.CORRECT if comparator(expected, actual) else Outcome.WRONG


def score_list_field(expected: list | None, actual: list | None) -> tuple[int, int, int]:
    """Set overlap for list fields → (matched, produced, expected).

    Charges are compared as normalised text, so "Ocean freight" and "ocean
    freight" are one item, not two.
    """
    normalise = lambda items: {  # noqa: E731
        " ".join(re.findall(r"[a-z0-9]+", _text(item).casefold())) for item in (items or [])
    } - {""}
    expected_set, actual_set = normalise(expected), normalise(actual)
    return len(expected_set & actual_set), len(actual_set), len(expected_set)
