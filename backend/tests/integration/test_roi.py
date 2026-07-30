"""The ROI model, including the cases where it must refuse to flatter.

A calculator that always produces an encouraging number is marketing with
arithmetic on top, and the first buyer who checks it stops believing anything
else the product says. So the tests that matter most here are the ones where it
declines: not enough history, and a desk whose fast answers do not actually
convert better.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from tests.integration.conftest import requires_integration

pytestmark = requires_integration


def _signup(client, company: str = "ROI Forwarding") -> dict:
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
    """Builds a history with exact response times and outcomes."""

    def __init__(self, client, org: dict) -> None:
        self.client = client
        self.org = org
        self.headers = org["headers"]

    def add(self, *, answered_after_hours: float | None, outcome: str | None = None) -> None:
        from app.core.db import SessionLocal
        from app.core.tenancy import organization_scope
        from app.models.enums import QuoteStatus
        from app.models.quote import Quote
        from app.models.rfq import RFQ

        rfq = self.client.post(
            "/api/rfqs/parse",
            json={"raw_message": "Quote 40HC Shanghai to Jebel Ali", "persist": True},
            headers=self.headers,
        ).json()["rfq"]

        asked_at = datetime.now(timezone.utc) - timedelta(days=10)
        db = SessionLocal()
        try:
            with organization_scope(self.org["org_id"], db):
                row = db.get(RFQ, rfq["id"])
                row.received_at = asked_at
                if answered_after_hours is not None:
                    sent_at = asked_at + timedelta(hours=answered_after_hours)
                    row.first_quoted_at = sent_at
                    status = {
                        "won": QuoteStatus.WON,
                        "lost": QuoteStatus.LOST,
                        None: QuoteStatus.SENT,
                    }[outcome]
                    db.add(
                        Quote(
                            rfq_id=row.id,
                            cost_amount=1500.0,
                            selling_price=1800.0,
                            status=status,
                            sent_at=sent_at,
                        )
                    )
                db.commit()
        finally:
            db.close()

    def roi(self, **params) -> dict:
        query = "&".join(f"{key}={value}" for key, value in params.items())
        res = self.client.get(
            f"/api/reports/roi{'?' + query if query else ''}", headers=self.headers
        )
        assert res.status_code == 200, res.text
        return res.json()


@pytest.fixture
def desk(client):
    return Desk(client, _signup(client))


def _speed_advantage(desk: Desk) -> None:
    """A desk that genuinely converts better when it answers quickly."""
    for _ in range(8):
        desk.add(answered_after_hours=1.0, outcome="won")
    for _ in range(2):
        desk.add(answered_after_hours=1.0, outcome="lost")
    for _ in range(2):
        desk.add(answered_after_hours=60.0, outcome="won")
    for _ in range(8):
        desk.add(answered_after_hours=60.0, outcome="lost")
    for _ in range(10):
        desk.add(answered_after_hours=None)  # never answered


# --------------------------------------------------------------------------
# The refusals
# --------------------------------------------------------------------------


def test_a_new_customer_gets_no_projection_and_is_told_why(desk):
    """Week one of a pilot. A number here would be invented."""
    for _ in range(3):
        desk.add(answered_after_hours=1.0, outcome="won")

    roi = desk.roi()
    assert roi["projection"] is None
    assert roi["confidence"] == "insufficient_data"
    assert roi["blockers"], "it must say what is missing"
    assert any("enquiries" in blocker for blocker in roi["blockers"])
    # The measured half is still real and still shown.
    assert roi["measured"]["enquiries_received"] == 3


def test_no_comparison_group_means_no_projection(desk):
    """Everything answered fast is good news, but it says nothing about what
    being slow costs — so there is nothing to project from."""
    for _ in range(12):
        desk.add(answered_after_hours=1.0, outcome="won")
    for _ in range(12):
        desk.add(answered_after_hours=1.0, outcome="lost")

    roi = desk.roi()
    assert roi["projection"] is None
    assert any("comparison" in blocker or "slowly" in blocker for blocker in roi["blockers"])


def test_a_desk_whose_speed_does_not_help_is_told_so(desk):
    """The unflattering answer the model must be able to give: speed is not
    what is losing these deals."""
    for _ in range(3):
        desk.add(answered_after_hours=1.0, outcome="won")
    for _ in range(9):
        desk.add(answered_after_hours=1.0, outcome="lost")
    for _ in range(9):
        desk.add(answered_after_hours=60.0, outcome="won")
    for _ in range(3):
        desk.add(answered_after_hours=60.0, outcome="lost")

    roi = desk.roi()
    projection = roi["projection"]
    assert projection is not None
    assert projection["uplift_points"] < 0
    assert projection["additional_wins_per_year"] == 0.0
    assert projection["annual_gross_profit"] == 0.0
    narrative = " ".join(roi["narrative"])
    assert "does not show faster answers converting better" in narrative
    assert "before buying anything" in narrative


# --------------------------------------------------------------------------
# The projection, when it is warranted
# --------------------------------------------------------------------------


def test_the_projection_uses_the_customers_own_win_rates(desk):
    _speed_advantage(desk)

    roi = desk.roi(days=30, gross_profit_per_shipment=500)
    projection = roi["projection"]

    # 8 of 10 fast quotes won; 2 of 10 slow ones.
    assert projection["fast_win_rate"] == 80.0
    assert projection["slow_win_rate"] == 20.0
    assert projection["uplift_points"] == 60.0

    # 30 enquiries at an 80% win rate would be 24 wins against 10 actual.
    assert roi["measured"]["enquiries_received"] == 30
    assert roi["measured"]["quotes_won"] == 10
    assert projection["additional_wins_in_window"] == pytest.approx(14.0, abs=0.1)


def test_the_annual_figure_scales_the_window_and_uses_the_stated_assumption(desk):
    _speed_advantage(desk)

    roi = desk.roi(days=30, gross_profit_per_shipment=500)
    projection = roi["projection"]

    expected_per_year = 14.0 * (365 / 30)
    assert projection["additional_wins_per_year"] == pytest.approx(expected_per_year, abs=0.5)
    assert projection["annual_gross_profit"] == pytest.approx(
        expected_per_year * 500, rel=0.01
    )
    # The assumption is echoed back so it can be challenged.
    assert roi["assumptions"]["gross_profit_per_shipment"] == 500


def test_changing_the_assumption_changes_only_the_money_not_the_measurement(desk):
    _speed_advantage(desk)

    cheap = desk.roi(days=30, gross_profit_per_shipment=100)
    rich = desk.roi(days=30, gross_profit_per_shipment=1000)

    assert cheap["measured"] == rich["measured"]
    assert (
        cheap["projection"]["additional_wins_per_year"]
        == rich["projection"]["additional_wins_per_year"]
    )
    assert rich["projection"]["annual_gross_profit"] > cheap["projection"]["annual_gross_profit"]


def test_the_threshold_for_fast_is_an_input_not_a_hidden_constant(desk):
    _speed_advantage(desk)

    strict = desk.roi(days=30, fast_response_hours=4)
    loose = desk.roi(days=30, fast_response_hours=72)

    # With a 72h threshold, the slow group is swallowed and there is no
    # comparison left — so it refuses rather than projecting from one group.
    assert strict["projection"] is not None
    assert loose["projection"] is None
    assert strict["assumptions"]["fast_response_hours"] == 4


def test_the_subscription_cost_is_included_so_the_net_is_visible(desk):
    _speed_advantage(desk)

    roi = desk.roi(days=30, gross_profit_per_shipment=500, subscription_per_user_per_month=99)
    projection = roi["projection"]

    assert projection["annual_subscription"] == pytest.approx(projection["seats"] * 99 * 12)
    assert projection["net_annual_value"] == pytest.approx(
        projection["annual_gross_profit"] - projection["annual_subscription"], rel=0.01
    )
    assert projection["return_multiple"] > 1


# --------------------------------------------------------------------------
# The one-pager
# --------------------------------------------------------------------------


def test_the_one_pager_separates_measured_from_assumed(desk):
    _speed_advantage(desk)

    from app.services.roi import render_one_pager

    page = render_one_pager(desk.roi(days=30), "Acme Forwarding")

    assert "MEASURED (from your own records)" in page
    assert "ASSUMED (change these if they are wrong)" in page
    assert "PROJECTED" in page
    assert "No" in page and "industry averages are used in the arithmetic" in page


def test_the_one_pager_downloads_as_a_pdf(desk):
    _speed_advantage(desk)

    res = desk.client.get("/api/reports/roi.pdf?days=30", headers=desk.headers)
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.content.startswith(b"%PDF")
    assert "response-time-review" in res.headers["content-disposition"]


def test_the_one_pager_still_renders_when_there_is_nothing_to_project(desk):
    desk.add(answered_after_hours=1.0, outcome="won")

    from app.services.roi import render_one_pager

    page = render_one_pager(desk.roi(), "Acme Forwarding")
    assert "NOT YET ENOUGH DATA TO PROJECT A VALUE" in page
    assert "MEASURED" in page


def test_roi_is_scoped_to_the_callers_organization(client):
    busy = Desk(client, _signup(client, "Busy Forwarding"))
    _speed_advantage(busy)

    quiet = Desk(client, _signup(client, "Quiet Forwarding"))
    roi = quiet.roi()

    assert roi["measured"]["enquiries_received"] == 0
    assert roi["projection"] is None
