"""Rate memory — answering without waiting for a carrier.

W1 made enquiries arrive fast and W2 measures how fast they are answered. But a
coordinator who must email a carrier and wait has handed the clock straight back,
so the response-time claim only survives if a lane quoted once can be priced
again immediately. That is what these tests cover — including the cases where a
suggestion must *not* be offered, because a wrong suggestion becomes a wrong
price in front of a customer.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest

from tests.integration.conftest import requires_integration

pytestmark = requires_integration


def _signup(client, company: str) -> dict:
    res = client.post(
        "/api/auth/signup",
        json={
            "company_name": f"{company} {uuid.uuid4().hex[:6]}",
            "full_name": "Owner",
            "email": f"{uuid.uuid4().hex[:10]}@example.com",
            "password": "test-password-123",
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    return {
        "headers": {"Authorization": f"Bearer {body['access_token']}"},
        "org_id": body["organization"]["id"],
    }


class Desk:
    def __init__(self, client, org: dict) -> None:
        self.client = client
        self.org = org
        self.headers = org["headers"]

    def rfq(
        self,
        origin: str = "Shanghai",
        destination: str = "Jebel Ali",
        mode: str = "Sea",
        container: str | None = "40HC",
    ) -> dict:
        """An RFQ on an explicit lane (the fake parser is bypassed by a patch)."""
        created = self.client.post(
            "/api/rfqs/parse",
            json={"raw_message": f"Quote {origin} to {destination}", "persist": True},
            headers=self.headers,
        ).json()["rfq"]
        updated = self.client.patch(
            f"/api/rfqs/{created['id']}",
            json={
                "origin": origin,
                "destination": destination,
                "transport_mode": mode,
                "container_type": container,
            },
            headers=self.headers,
        )
        assert updated.status_code == 200, updated.text
        return updated.json()

    def add_rate(self, rfq_id: int, **kwargs) -> dict:
        payload = {"partner_name": "Ocean Star Line", "cost_amount": 1450.0, "currency": "USD"}
        payload.update(kwargs)
        res = self.client.post(
            f"/api/rfqs/{rfq_id}/rates", json=payload, headers=self.headers
        )
        assert res.status_code == 201, res.text
        return res.json()

    def suggestions(self, rfq_id: int) -> dict:
        res = self.client.get(
            f"/api/rfqs/{rfq_id}/rate-suggestions", headers=self.headers
        )
        assert res.status_code == 200, res.text
        return res.json()


@pytest.fixture
def desk(client):
    return Desk(client, _signup(client, "Lane Forwarding"))


# --------------------------------------------------------------------------
# The core behaviour
# --------------------------------------------------------------------------


def test_a_repeat_lane_surfaces_the_previous_rate(desk):
    """The whole point: the second enquiry on a lane can be answered at once."""
    first = desk.rfq()
    desk.add_rate(first["id"], partner_name="Ocean Star Line", cost_amount=1450.0,
                  transit_time="22 days")

    second = desk.rfq()
    memory = desk.suggestions(second["id"])

    assert memory["lane_known"] is True
    assert memory["exact_matches"] == 1
    assert memory["median_cost"] == 1450.0
    suggestion = memory["suggestions"][0]
    assert suggestion["match"] == "exact"
    assert suggestion["partner_name"] == "Ocean Star Line"
    assert suggestion["cost_amount"] == 1450.0
    assert suggestion["transit_time"] == "22 days"
    assert suggestion["rfq_reference"] == first["reference"]


def test_the_lane_matches_across_spelling_differences(desk):
    desk.add_rate(desk.rfq(origin="Port of Shanghai, China", destination="Jebel Ali")["id"])

    memory = desk.suggestions(desk.rfq(origin="SHANGHAI", destination="jebel ali, UAE")["id"])
    assert memory["exact_matches"] == 1


def test_a_different_lane_is_not_suggested(desk):
    """The expensive mistake this must never make."""
    desk.add_rate(desk.rfq(origin="Shanghai", destination="Jebel Ali")["id"])

    other = desk.rfq(origin="Ningbo", destination="Jebel Ali")
    memory = desk.suggestions(other["id"])

    assert memory["exact_matches"] == 0
    assert memory["route_matches"] == 0
    assert memory["suggestions"] == []


def test_same_route_but_different_equipment_is_offered_separately(desk):
    """A 20GP price is real context for a 40HC enquiry, but it is not the
    answer — so it is labelled, never counted as an exact match."""
    desk.add_rate(desk.rfq(container="20GP")["id"], cost_amount=900.0)

    memory = desk.suggestions(desk.rfq(container="40HC")["id"])
    assert memory["exact_matches"] == 0
    assert memory["route_matches"] == 1
    assert memory["suggestions"][0]["match"] == "route"
    # The median is exact-lane only; blending equipment would price nothing.
    assert memory["median_cost"] is None


def test_a_different_mode_on_the_same_route_is_not_an_exact_match(desk):
    desk.add_rate(desk.rfq(mode="Air")["id"], cost_amount=3.2)

    memory = desk.suggestions(desk.rfq(mode="Sea")["id"])
    assert memory["exact_matches"] == 0
    assert memory["route_matches"] == 1


def test_an_rfq_without_a_route_gets_no_suggestions(desk):
    """Matching on half a route would surface rates from everywhere."""
    rfq = desk.rfq()
    desk.client.patch(
        f"/api/rfqs/{rfq['id']}", json={"destination": None}, headers=desk.headers
    )

    memory = desk.suggestions(rfq["id"])
    assert memory["lane_known"] is False
    assert memory["suggestions"] == []


def test_an_rfq_never_suggests_its_own_rates(desk):
    rfq = desk.rfq()
    desk.add_rate(rfq["id"])

    assert desk.suggestions(rfq["id"])["suggestions"] == []


# --------------------------------------------------------------------------
# Honesty of the suggestion
# --------------------------------------------------------------------------


def test_expired_rates_are_shown_but_marked_and_ranked_last(desk):
    """Old pricing is information; presenting it as current would be a lie."""
    stale = desk.rfq()
    desk.add_rate(
        stale["id"],
        partner_name="Expired Line",
        cost_amount=1200.0,
        validity_date=(date.today() - timedelta(days=10)).isoformat(),
    )
    live = desk.rfq()
    desk.add_rate(
        live["id"],
        partner_name="Current Line",
        cost_amount=1500.0,
        validity_date=(date.today() + timedelta(days=30)).isoformat(),
    )

    memory = desk.suggestions(desk.rfq()["id"])
    names = [s["partner_name"] for s in memory["suggestions"]]
    assert names == ["Current Line", "Expired Line"]
    assert memory["suggestions"][0]["is_expired"] is False
    assert memory["suggestions"][1]["is_expired"] is True


def test_the_suggestion_shows_what_we_charged_and_whether_we_won(desk):
    """Cost alone is half the picture — the achieved price and the outcome are
    what make the next quote a decision rather than a guess."""
    won = desk.rfq()
    rate = desk.add_rate(won["id"], cost_amount=1500.0)
    review = desk.client.post(
        "/api/quotes/start",
        json={"rfq_id": won["id"], "selected_rate_id": rate["id"], "markup_value": 20},
        headers=desk.headers,
    ).json()
    quote = desk.client.post(
        f"/api/quotes/{review['quote_id']}/approve",
        json={"approved": True, "mark_sent": True},
        headers=desk.headers,
    ).json()

    suggestion = desk.suggestions(desk.rfq()["id"])["suggestions"][0]
    assert suggestion["quoted_selling_price"] == quote["selling_price"] == 1800.0
    assert suggestion["outcome"] == "Sent"


def test_reusing_a_rate_copies_it_and_records_where_it_came_from(desk):
    """A price nobody can trace is a price nobody will stand behind."""
    original_rfq = desk.rfq()
    original = desk.add_rate(original_rfq["id"], cost_amount=1450.0, notes="Contract Q3")

    target = desk.rfq()
    res = desk.client.post(
        f"/api/rfqs/{target['id']}/rates/from-history/{original['id']}",
        headers=desk.headers,
    )
    assert res.status_code == 201, res.text
    copied = res.json()

    assert copied["id"] != original["id"]
    assert copied["rfq_id"] == target["id"]
    assert copied["cost_amount"] == 1450.0
    assert "Contract Q3" in copied["notes"]
    assert "Reused from" in copied["notes"]
    assert "Confirm before quoting" in copied["notes"]

    # The original is untouched and still attached to its own enquiry.
    still_there = desk.client.get(
        f"/api/rfqs/{original_rfq['id']}/rates", headers=desk.headers
    ).json()
    assert [r["id"] for r in still_there] == [original["id"]]
    assert still_there[0]["notes"] == "Contract Q3"


def test_a_reused_rate_can_be_quoted_from_immediately(desk):
    """End to end: enquiry → remembered rate → quotation, with no partner email
    in between. This is the mechanism the response-time promise depends on."""
    desk.add_rate(desk.rfq()["id"], cost_amount=1500.0)

    new_rfq = desk.rfq()
    suggestion = desk.suggestions(new_rfq["id"])["suggestions"][0]
    copied = desk.client.post(
        f"/api/rfqs/{new_rfq['id']}/rates/from-history/{suggestion['rate_id']}",
        headers=desk.headers,
    ).json()

    review = desk.client.post(
        "/api/quotes/start",
        json={"rfq_id": new_rfq["id"], "selected_rate_id": copied["id"], "markup_value": 20},
        headers=desk.headers,
    )
    assert review.status_code == 200, review.text
    assert review.json()["selling_price"] == 1800.0


def test_editing_an_old_rfq_does_not_rewrite_what_a_partner_quoted_for(desk):
    """History has to stay true: the rate was given for the lane as it was."""
    old = desk.rfq(origin="Shanghai", destination="Jebel Ali")
    rate = desk.add_rate(old["id"])

    desk.client.patch(
        f"/api/rfqs/{old['id']}",
        json={"origin": "Ningbo", "destination": "Dammam"},
        headers=desk.headers,
    )

    # The rate still belongs to the lane it was quoted for.
    memory = desk.suggestions(desk.rfq(origin="Shanghai", destination="Jebel Ali")["id"])
    assert [s["rate_id"] for s in memory["suggestions"]] == [rate["id"]]
    assert memory["exact_matches"] == 1


def test_correcting_an_rfqs_route_makes_it_match_immediately(desk):
    """The lane key is maintained by the ORM, so no write path can forget it."""
    desk.add_rate(desk.rfq(origin="Shanghai", destination="Jebel Ali")["id"])

    mistyped = desk.rfq(origin="Shangai", destination="Jebel Ali")  # typo
    assert desk.suggestions(mistyped["id"])["exact_matches"] == 0

    desk.client.patch(
        f"/api/rfqs/{mistyped['id']}", json={"origin": "Shanghai"}, headers=desk.headers
    )
    assert desk.suggestions(mistyped["id"])["exact_matches"] == 1


# --------------------------------------------------------------------------
# Tariff import
# --------------------------------------------------------------------------


TARIFF_CSV = b"""origin,destination,partner_name,cost_amount,transport_mode,container_type,partner_type,currency,transit_time,validity_date,included_charges,excluded_charges,free_time,notes
Shanghai,Jebel Ali,Ocean Star Line,1450,Sea,40HC,Shipping line,USD,22 days,2026-12-31,Ocean freight,Destination charges,14 days,Contract 2026
Ningbo,Dubai,Ocean Star Line,1380,Sea,20GP,Shipping line,USD,24 days,2026-12-31,Ocean freight,,10 days,
Dubai,Muscat,Gulf Road Transport,650,Road,,Trucking company,AED,2 days,,,,,Door to door
"""


def test_importing_a_rate_sheet_makes_its_lanes_quotable(desk):
    res = desk.client.post(
        "/api/rates/tariff/import",
        files={"file": ("tariff.csv", TARIFF_CSV, "text/csv")},
        headers=desk.headers,
    )
    assert res.status_code == 200, res.text
    assert res.json() == {
        "created": 3,
        "skipped_duplicates": 0,
        "rejected": 0,
        "errors": [],
    }

    # A brand-new enquiry on a covered lane can be priced with no partner email.
    memory = desk.suggestions(desk.rfq()["id"])
    assert memory["exact_matches"] == 1
    suggestion = memory["suggestions"][0]
    assert suggestion["source"] == "Tariff"
    assert suggestion["cost_amount"] == 1450.0
    assert suggestion["rfq_id"] is None


def test_reimporting_the_same_sheet_does_not_duplicate(desk):
    """Rate sheets get re-sent with three lines changed; the import has to cope."""
    for _ in range(2):
        desk.client.post(
            "/api/rates/tariff/import",
            files={"file": ("tariff.csv", TARIFF_CSV, "text/csv")},
            headers=desk.headers,
        )
    second = desk.client.post(
        "/api/rates/tariff/import",
        files={"file": ("tariff.csv", TARIFF_CSV, "text/csv")},
        headers=desk.headers,
    ).json()

    assert second["created"] == 0
    assert second["skipped_duplicates"] == 3
    assert desk.suggestions(desk.rfq()["id"])["exact_matches"] == 1


def test_bad_rows_are_reported_by_line_and_good_rows_still_load(desk):
    """A silent partial import of pricing data would be worse than a failure."""
    csv_bytes = (
        b"origin,destination,partner_name,cost_amount,transport_mode,validity_date\n"
        b"Shanghai,Jebel Ali,Ocean Star Line,1450,Sea,2026-12-31\n"
        b"Shanghai,,Missing Destination,900,Sea,\n"
        b"Ningbo,Dubai,Bad Price,not-a-number,Sea,\n"
        b"Ningbo,Dubai,Bad Date,900,Sea,31st of never\n"
        b"Ningbo,Dubai,Bad Mode,900,Teleport,\n"
    )
    result = desk.client.post(
        "/api/rates/tariff/import",
        files={"file": ("tariff.csv", csv_bytes, "text/csv")},
        headers=desk.headers,
    ).json()

    assert result["created"] == 1
    assert result["rejected"] == 4
    assert [e["line"] for e in result["errors"]] == [3, 4, 5, 6]
    assert "destination" in result["errors"][0]["reason"]
    assert "validity_date" in result["errors"][2]["reason"]
    assert "Teleport" in result["errors"][3]["reason"]


def test_a_file_with_the_wrong_columns_is_rejected_outright(desk):
    res = desk.client.post(
        "/api/rates/tariff/import",
        files={"file": ("wrong.csv", b"from,to,price\nShanghai,Dubai,1000\n", "text/csv")},
        headers=desk.headers,
    )
    assert res.status_code == 400
    assert "destination" in res.json()["detail"]
    # The expected header is spelled out rather than left to guesswork.
    assert "origin,destination,partner_name,cost_amount" in res.json()["detail"]


def test_the_template_matches_what_the_importer_accepts(desk):
    template = desk.client.get(
        "/api/rates/tariff/template.csv", headers=desk.headers
    )
    assert template.status_code == 200

    result = desk.client.post(
        "/api/rates/tariff/import",
        files={"file": ("filled.csv", template.content, "text/csv")},
        headers=desk.headers,
    ).json()
    assert result["rejected"] == 0
    assert result["created"] == 1


def test_empty_upload_is_rejected(desk):
    res = desk.client.post(
        "/api/rates/tariff/import",
        files={"file": ("empty.csv", b"", "text/csv")},
        headers=desk.headers,
    )
    assert res.status_code == 400


# --------------------------------------------------------------------------
# Lane coverage
# --------------------------------------------------------------------------


def test_lane_coverage_shows_what_can_be_priced_now(desk):
    desk.client.post(
        "/api/rates/tariff/import",
        files={"file": ("tariff.csv", TARIFF_CSV, "text/csv")},
        headers=desk.headers,
    )
    desk.rfq()  # one enquiry on the Shanghai → Jebel Ali lane
    desk.rfq()

    lanes = desk.client.get("/api/rates/lanes", headers=desk.headers).json()
    assert len(lanes) == 3
    busiest = lanes[0]
    assert busiest["lane"].startswith("Shanghai → Jebel Ali")
    assert busiest["enquiries"] == 2
    assert busiest["rate_count"] == 1
    assert busiest["live_rate_count"] == 1
    assert busiest["median_cost"] == 1450.0


# --------------------------------------------------------------------------
# Isolation
# --------------------------------------------------------------------------


def test_rates_are_never_suggested_across_organizations(client):
    """Pricing is the most commercially sensitive data here — a leak would end
    the business, not just the account."""
    theirs = Desk(client, _signup(client, "Rival Forwarding"))
    theirs.client.post(
        "/api/rates/tariff/import",
        files={"file": ("tariff.csv", TARIFF_CSV, "text/csv")},
        headers=theirs.headers,
    )
    theirs.add_rate(theirs.rfq()["id"], partner_name="Secret Line", cost_amount=999.0)

    ours = Desk(client, _signup(client, "Our Forwarding"))
    memory = ours.suggestions(ours.rfq()["id"])

    assert memory["suggestions"] == []
    assert memory["exact_matches"] == 0
    assert ours.client.get("/api/rates/lanes", headers=ours.headers).json() == []

    # And a rate id from the other tenant cannot be copied by guessing it.
    their_rate = theirs.client.get(
        "/api/rates/lanes", headers=theirs.headers
    ).json()
    assert their_rate, "the other tenant should still see its own lanes"
    stolen = ours.client.post(
        f"/api/rfqs/{ours.rfq()['id']}/rates/from-history/999999",
        headers=ours.headers,
    )
    assert stolen.status_code == 404
