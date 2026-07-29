"""Lane matching — the line between "we quoted this before" and a wrong price.

A false match here surfaces a rate from a different lane as a suggestion, which
ends up in front of a customer. These tests pin down both directions: the noise
that must be ignored, and the differences that must never be collapsed.
"""
from __future__ import annotations

import pytest

from app.services.lanes import (
    describe_lane,
    lane_key,
    normalize_equipment,
    normalize_place,
    route_key,
)


class TestPlaceNormalisation:
    @pytest.mark.parametrize(
        "written",
        [
            "Shanghai",
            "shanghai",
            "SHANGHAI",
            "  Shanghai  ",
            "Shanghai, China",
            "Shanghai,China",
            "Port of Shanghai",
            "Shanghai Port",
            "Shanghai (CNSHA)",
            "Shanghai Seaport",
        ],
    )
    def test_the_same_port_written_many_ways(self, written):
        assert normalize_place(written) == "shanghai"

    def test_multi_word_places_keep_their_words(self):
        assert normalize_place("Jebel Ali") == "jebel ali"
        assert normalize_place("JEBEL ALI, UAE") == "jebel ali"
        assert normalize_place("Port of Jebel Ali") == "jebel ali"

    def test_accents_are_folded(self):
        assert normalize_place("Málaga") == normalize_place("Malaga")

    def test_nearby_but_different_ports_stay_different(self):
        """The expensive mistake: quoting the Jebel Ali rate for Dubai."""
        assert normalize_place("Dubai") != normalize_place("Jebel Ali")
        assert normalize_place("Shanghai") != normalize_place("Ningbo")
        assert normalize_place("New York") != normalize_place("Newark")

    def test_facility_words_collapse_to_the_city(self):
        """"Dubai Airport" and "Dubai" are the same place; what separates an
        air rate from a sea rate is the mode, which is part of the lane key."""
        assert normalize_place("Dubai Airport") == normalize_place("Dubai")
        assert lane_key("Shanghai", "Dubai Airport", "Air") != lane_key(
            "Shanghai", "Dubai", "Sea"
        )

    def test_empty_input(self):
        assert normalize_place(None) == ""
        assert normalize_place("") == ""
        assert normalize_place("   ") == ""


class TestEquipmentNormalisation:
    @pytest.mark.parametrize("written", ["40HC", "40 HC", "40'HC", "1x40HC", "2 x 40 hc"])
    def test_container_written_many_ways(self, written):
        assert normalize_equipment(written) == "40hc"

    def test_different_equipment_stays_different(self):
        assert normalize_equipment("40HC") != normalize_equipment("20GP")
        assert normalize_equipment("40HC") != normalize_equipment("40RF")

    def test_unspecified(self):
        assert normalize_equipment(None) == ""


class TestLaneKey:
    def test_matches_across_spelling_differences(self):
        assert lane_key("Port of Shanghai, China", "Jebel Ali", "Sea", "1x40HC") == lane_key(
            "SHANGHAI", "jebel ali, uae", "Sea", "40 HC"
        )

    def test_direction_matters(self):
        assert lane_key("Shanghai", "Jebel Ali", "Sea", "40HC") != lane_key(
            "Jebel Ali", "Shanghai", "Sea", "40HC"
        )

    def test_mode_and_equipment_are_part_of_the_lane(self):
        base = lane_key("Shanghai", "Dubai", "Sea", "40HC")
        assert base != lane_key("Shanghai", "Dubai", "Air", "40HC")
        assert base != lane_key("Shanghai", "Dubai", "Sea", "20GP")

    def test_an_incomplete_route_has_no_lane(self):
        """An RFQ missing its destination must not match every stored rate."""
        assert lane_key(None, "Dubai", "Sea", "40HC") is None
        assert lane_key("Shanghai", None, "Sea", "40HC") is None
        assert lane_key("", "", "Sea", "40HC") is None

    def test_accepts_an_enum_mode(self):
        from app.models.enums import TransportMode

        assert lane_key("Shanghai", "Dubai", TransportMode.SEA, "40HC") == lane_key(
            "Shanghai", "Dubai", "Sea", "40HC"
        )

    def test_route_key_ignores_mode_and_equipment(self):
        assert route_key("Shanghai", "Jebel Ali") == route_key(
            "port of shanghai", "JEBEL ALI, UAE"
        )
        assert route_key("Shanghai", None) is None


class TestDescription:
    def test_reads_like_a_lane(self):
        assert (
            describe_lane("Shanghai", "Jebel Ali", "Sea", "40HC")
            == "Shanghai → Jebel Ali (Sea 40HC)"
        )

    def test_missing_parts_are_visible_not_hidden(self):
        assert describe_lane(None, "Dubai") == "? → Dubai"
