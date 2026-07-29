"""The scoring behind any accuracy figure we publish.

If this is wrong, the number is wrong, and a wrong number is worse than no
number — it would be quoted to customers. So the comparators are pinned in both
directions: what must count as the same answer, and what must not.
"""
from __future__ import annotations

import pytest

from app.eval.runner import evaluate_case, load_corpus, run_evaluation
from app.eval.scoring import (
    Outcome,
    classify,
    compare_bool,
    compare_code,
    compare_measure,
    compare_place,
    compare_text,
    score_list_field,
)
from app.eval.stub import FabricatingLLM, LazyLLM, OracleLLM


class TestComparators:
    @pytest.mark.parametrize(
        "expected,actual",
        [
            ("Shanghai", "shanghai"),
            ("Shanghai", "Port of Shanghai"),
            ("Jebel Ali", "JEBEL ALI, UAE"),
        ],
    )
    def test_places_tolerate_formatting(self, expected, actual):
        assert compare_place(expected, actual)

    def test_places_do_not_tolerate_a_different_port(self):
        assert not compare_place("Jebel Ali", "Dubai")
        assert not compare_place("Shanghai", "Ningbo")

    @pytest.mark.parametrize(
        "expected,actual", [("12,500 kg", "12500 KG"), ("40HC", "40 hc"), ("6.4 CBM", "6.4cbm")]
    )
    def test_measures_ignore_punctuation_and_case(self, expected, actual):
        assert compare_measure(expected, actual)

    def test_measures_do_not_accept_a_changed_unit(self):
        """"12.5 t" and "12500 kg" are the same cargo but not the same
        extraction; accepting it would hide a real error."""
        assert not compare_measure("12500 kg", "12.5 t")
        assert not compare_measure("1760 lbs", "800 kg")

    def test_codes_ignore_separators(self):
        assert compare_code("6910.10", "691010")
        assert compare_code("FOB", "fob")
        assert not compare_code("FOB", "CIF")

    def test_free_text_allows_extra_words_but_not_missing_ones(self):
        assert compare_text("plastic household items", "Plastic household items (assorted)")
        assert not compare_text("plastic household items", "plastic items")
        assert not compare_text("ceramic tiles", "marble slabs")

    def test_booleans(self):
        assert compare_bool(True, True)
        assert compare_bool(False, None)  # unset means not flagged
        assert not compare_bool(True, False)


class TestClassification:
    """The distinction the whole report rests on."""

    def test_a_right_answer_is_correct(self):
        assert classify("Shanghai", "shanghai", compare_place) == Outcome.CORRECT

    def test_a_different_answer_is_wrong_not_missing(self):
        assert classify("Shanghai", "Ningbo", compare_place) == Outcome.WRONG

    def test_a_blank_where_something_was_stated_is_missed(self):
        assert classify("Shanghai", None, compare_place) == Outcome.MISSED
        assert classify("Shanghai", "", compare_place) == Outcome.MISSED

    def test_a_value_where_nothing_was_stated_is_invented(self):
        """The dangerous one: a number the customer never gave, used to price
        their shipment."""
        assert classify(None, "FOB", compare_code) == Outcome.INVENTED

    def test_correct_silence_is_a_right_answer(self):
        assert classify(None, None, compare_code) == Outcome.CORRECTLY_EMPTY
        assert classify(None, "", compare_code) == Outcome.CORRECTLY_EMPTY


class TestListScoring:
    def test_set_overlap(self):
        matched, produced, expected = score_list_field(
            ["Ocean freight", "Destination charges"], ["ocean freight", "Insurance"]
        )
        assert (matched, produced, expected) == (1, 2, 2)

    def test_empty_cases(self):
        assert score_list_field(None, None) == (0, 0, 0)
        assert score_list_field([], ["Ocean freight"]) == (0, 1, 0)


class TestCorpus:
    """The corpus is a data file people will edit. Guard its shape."""

    def test_it_loads_and_is_substantial(self):
        cases = load_corpus()
        assert len(cases) >= 40

    def test_every_case_is_well_formed(self):
        for case in load_corpus():
            assert case["id"], "each case needs an id"
            assert case["email"].strip(), f"{case['id']} has no email text"
            assert case["expected"], f"{case['id']} has no labels"
            assert case.get("tags"), f"{case['id']} has no tags"
            assert case.get("note"), f"{case['id']} should say what it tests"

    def test_ids_are_unique(self):
        ids = [case["id"] for case in load_corpus()]
        assert len(set(ids)) == len(ids)

    def test_it_contains_explicit_nulls(self):
        """Without labelled absences there is nothing to catch invention with."""
        nulls = sum(
            1
            for case in load_corpus()
            for value in case["expected"].values()
            if value is None
        )
        assert nulls >= 20, "the corpus must test what should NOT be extracted"

    def test_it_covers_the_ways_freight_email_is_actually_written(self):
        tags = {tag for case in load_corpus() for tag in case["tags"]}
        for required in (
            "telegraphic",
            "forwarded",
            "non-native",
            "incomplete",
            "noise",
            "trap",
            "dangerous-goods",
            "not-an-rfq",
        ):
            assert required in tags, f"no case covers {required!r}"

    def test_every_labelled_field_is_actually_scored(self):
        """A label nobody compares is a false sense of coverage."""
        from app.eval.scoring import BOOLEAN_FIELDS, FIELD_COMPARATORS, LIST_FIELDS

        known = set(FIELD_COMPARATORS) | set(BOOLEAN_FIELDS) | set(LIST_FIELDS)
        for case in load_corpus():
            unknown = set(case["expected"]) - known
            assert not unknown, f"{case['id']} labels unscored field(s): {unknown}"


class TestHarness:
    """End-to-end through the real parser graph, with stub providers."""

    def test_a_perfect_extractor_scores_100_percent(self):
        cases = load_corpus()
        report = run_evaluation(OracleLLM(cases), cases)

        assert report.accuracy == 1.0
        assert report.precision == 1.0
        assert report.recall == 1.0
        assert report.hallucination_rate == 0.0
        assert report.failed_cases == []

    def test_an_extractor_that_finds_nothing_is_safe_but_useless(self):
        """Recall collapses; the hallucination rate stays clean. The report has
        to show that trade-off rather than average it away."""
        cases = load_corpus()
        report = run_evaluation(LazyLLM(cases), cases)

        assert report.recall < 0.1
        assert report.hallucination_rate == 0.0

    def test_a_confident_fabricator_looks_accurate_and_is_dangerous(self):
        """The reason a single accuracy percentage is not good enough: this
        scores respectably while inventing a value for every field the customer
        never mentioned."""
        cases = load_corpus()
        report = run_evaluation(FabricatingLLM(cases), cases)

        assert report.recall == 1.0
        assert report.accuracy > 0.7, "a naive reading would call this good"
        assert report.hallucination_rate == 1.0, "and this is what it really is"

    def test_a_provider_that_crashes_is_reported_not_swallowed(self):
        class BrokenLLM:
            provider = "broken"
            model = "broken"

            def complete(self, **_kwargs):
                raise RuntimeError("provider unavailable")

            def complete_structured(self, **_kwargs):
                raise RuntimeError("provider unavailable")

        cases = load_corpus()[:3]
        report = run_evaluation(BrokenLLM(), cases)

        assert len(report.failed_cases) == 3
        assert "provider unavailable" in report.failed_cases[0].failure

    def test_mistakes_are_reported_with_enough_detail_to_act_on(self):
        case = {
            "id": "x",
            "tags": [],
            "email": "…",
            "expected": {"origin": "Shanghai", "incoterm": None},
        }
        result = evaluate_case(case, {"origin": "Ningbo", "incoterm": "FOB"})

        assert result.outcomes["origin"] == Outcome.WRONG
        assert result.outcomes["incoterm"] == Outcome.INVENTED
        assert any("expected 'Shanghai'" in m and "'Ningbo'" in m for m in result.mistakes)
        assert any("incoterm: invented" in m for m in result.mistakes)

    def test_the_report_serializes_for_ci(self):
        cases = load_corpus()[:5]
        payload = run_evaluation(OracleLLM(cases), cases).as_dict()

        assert payload["cases"] == 5
        assert payload["accuracy"] == 1.0
        assert "per_field" in payload
        assert payload["outcomes"]["invented"] == 0
