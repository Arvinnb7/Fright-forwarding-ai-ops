"""The arithmetic behind the published response-time numbers.

These figures are put in front of a buyer to justify a purchase, so the maths is
pinned down here against hand-computed values, with no database involved.
"""
from __future__ import annotations

import pytest

from app.services.performance import (
    RESPONSE_BUCKETS,
    bucket_for,
    percentile,
    summarize_for_report,
)


class TestPercentile:
    def test_median_of_an_odd_sample_is_the_middle_value(self):
        assert percentile([1, 2, 3, 4, 5], 0.5) == 3.0

    def test_median_of_an_even_sample_interpolates(self):
        assert percentile([1, 2, 3, 4], 0.5) == 2.5

    def test_p90_matches_a_hand_computed_value(self):
        # 10 values, position = 0.9 * 9 = 8.1 → between 9 and 10, 10% along.
        assert percentile(list(range(1, 11)), 0.9) == pytest.approx(9.1)

    def test_order_does_not_matter(self):
        assert percentile([9, 1, 5, 3, 7], 0.5) == percentile([1, 3, 5, 7, 9], 0.5)

    def test_single_value(self):
        assert percentile([4.2], 0.5) == 4.2
        assert percentile([4.2], 0.9) == 4.2

    def test_empty_sample_is_none_not_zero(self):
        """Zero would read as 'instant response'; None reads as 'no data'."""
        assert percentile([], 0.5) is None

    def test_extremes(self):
        assert percentile([2, 4, 6], 0.0) == 2.0
        assert percentile([2, 4, 6], 1.0) == 6.0


class TestBuckets:
    @pytest.mark.parametrize(
        "hours,expected",
        [
            (0.0, "Under 1 hour"),
            (0.99, "Under 1 hour"),
            (1.0, "1–4 hours"),
            (3.99, "1–4 hours"),
            (4.0, "4–24 hours"),
            (23.9, "4–24 hours"),
            (24.0, "1–3 days"),
            (71.9, "1–3 days"),
            (72.0, "Over 3 days"),
            (2000.0, "Over 3 days"),
        ],
    )
    def test_boundaries_are_half_open(self, hours, expected):
        assert bucket_for(hours) == expected

    def test_buckets_are_contiguous_and_cover_everything(self):
        edges = [(low, high) for _, low, high in RESPONSE_BUCKETS]
        assert edges[0][0] == 0.0
        assert edges[-1][1] == float("inf")
        for (_, upper), (lower, _) in zip(edges, edges[1:]):
            assert upper == lower, "a response time would fall between buckets"


class TestSummary:
    def test_reports_no_data_rather_than_zeroes(self):
        lines = list(summarize_for_report({"response_rate": None}))
        assert lines == ["No enquiries were received in this period."]

    def test_states_the_response_rate_and_the_backlog(self):
        lines = list(
            summarize_for_report(
                {
                    "response_rate": 45.0,
                    "rfqs_received": 20,
                    "rfqs_quoted": 9,
                    "median_response_hours": 3.5,
                    "p90_response_hours": 40.0,
                    "unanswered_total": 11,
                }
            )
        )
        assert "9 of 20" in lines[0]
        assert "45.0%" in lines[0]
        assert "3.5h" in lines[1]
        assert "11 enquiries are still unanswered" in lines[2]
