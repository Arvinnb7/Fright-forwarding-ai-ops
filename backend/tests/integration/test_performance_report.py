"""Speed-to-quote reporting, against known timings.

Every figure here is asserted against a hand-computed value, because these are
the numbers a forwarder is asked to make a purchasing decision on. A dashboard
that flatters its own performance is worse than no dashboard: the pilot would
"succeed" whatever happened.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

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
    """Builds a tenant's history with exact, controlled timings."""

    def __init__(self, client, org: dict) -> None:
        self.client = client
        self.org = org
        self.headers = org["headers"]

    def add_rfq(
        self,
        *,
        asked_hours_ago: float,
        answered_after_hours: float | None = None,
        won: bool = False,
        lost: bool = False,
    ) -> int:
        """Create an RFQ, and optionally the quotation that answered it."""
        from sqlalchemy import select

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

        asked_at = datetime.now(timezone.utc) - timedelta(hours=asked_hours_ago)
        db = SessionLocal()
        try:
            with organization_scope(self.org["org_id"], db):
                row = db.get(RFQ, rfq["id"])
                row.received_at = asked_at
                if answered_after_hours is not None:
                    sent_at = asked_at + timedelta(hours=answered_after_hours)
                    row.first_quoted_at = sent_at
                    status = (
                        QuoteStatus.WON if won else QuoteStatus.LOST if lost
                        else QuoteStatus.SENT
                    )
                    db.add(
                        Quote(
                            rfq_id=row.id,
                            selling_price=1800.0,
                            cost_amount=1500.0,
                            gross_margin=300.0,
                            status=status,
                            sent_at=sent_at,
                        )
                    )
                db.commit()
                assert db.execute(select(RFQ.id).where(RFQ.id == row.id)).first()
        finally:
            db.close()
        return rfq["id"]

    def report(self, days: int = 30) -> dict:
        res = self.client.get(f"/api/reports/performance?days={days}", headers=self.headers)
        assert res.status_code == 200, res.text
        return res.json()


@pytest.fixture
def desk(client):
    return Desk(client, _signup(client, "Speed Forwarding"))


# --------------------------------------------------------------------------
# The headline numbers
# --------------------------------------------------------------------------


def test_response_rate_counts_unanswered_enquiries(desk):
    """The number that starts the sales conversation: how many never got a
    reply at all."""
    for _ in range(3):
        desk.add_rfq(asked_hours_ago=48, answered_after_hours=2)
    for _ in range(7):
        desk.add_rfq(asked_hours_ago=48)  # never answered

    report = desk.report()
    assert report["rfqs_received"] == 10
    assert report["rfqs_quoted"] == 3
    assert report["response_rate"] == 30.0
    assert report["unanswered_total"] == 7


def test_median_and_p90_response_time(desk):
    # Five known response times: 1, 2, 3, 4, 100 hours.
    # median = 3; p90 position = 0.9 * 4 = 3.6 → 4 + 0.6 * 96 = 61.6
    for hours in (1, 2, 3, 4, 100):
        desk.add_rfq(asked_hours_ago=200, answered_after_hours=hours)

    report = desk.report()
    assert report["median_response_hours"] == 3.0
    assert report["p90_response_hours"] == pytest.approx(61.6, abs=0.05)
    assert report["fastest_response_hours"] == 1.0
    assert report["slowest_response_hours"] == 100.0


def test_response_time_is_measured_from_when_the_customer_asked(desk):
    """If the clock started when we processed the email, every number here
    would be flattering and useless."""
    desk.add_rfq(asked_hours_ago=72, answered_after_hours=48)

    report = desk.report()
    assert report["median_response_hours"] == 48.0


def test_win_rate_by_response_speed(desk):
    """The chart that closes the sale — fast answers should visibly convert
    better, and the tool must be able to show whether they actually do."""
    # Under 1 hour: 3 quoted, 2 won.
    desk.add_rfq(asked_hours_ago=100, answered_after_hours=0.5, won=True)
    desk.add_rfq(asked_hours_ago=100, answered_after_hours=0.75, won=True)
    desk.add_rfq(asked_hours_ago=100, answered_after_hours=0.9, lost=True)
    # Over 3 days: 4 quoted, 1 won.
    for _ in range(3):
        desk.add_rfq(asked_hours_ago=300, answered_after_hours=100, lost=True)
    desk.add_rfq(asked_hours_ago=300, answered_after_hours=100, won=True)

    buckets = {b["label"]: b for b in desk.report()["win_rate_by_response_time"]}
    assert buckets["Under 1 hour"]["quoted"] == 3
    assert buckets["Under 1 hour"]["won"] == 2
    assert buckets["Under 1 hour"]["win_rate"] == pytest.approx(66.7, abs=0.1)
    assert buckets["Over 3 days"]["quoted"] == 4
    assert buckets["Over 3 days"]["win_rate"] == 25.0
    # An empty bucket reports no data, not a 0% win rate.
    assert buckets["1–4 hours"]["quoted"] == 0
    assert buckets["1–4 hours"]["win_rate"] is None


def test_win_rate_ignores_quotes_still_in_play(desk):
    desk.add_rfq(asked_hours_ago=50, answered_after_hours=1, won=True)
    desk.add_rfq(asked_hours_ago=50, answered_after_hours=1, lost=True)
    desk.add_rfq(asked_hours_ago=50, answered_after_hours=1)  # still Sent

    report = desk.report()
    assert report["quotes_won"] == 1
    assert report["quotes_lost"] == 1
    assert report["win_rate"] == 50.0, "an undecided quote must not count as a loss"


def test_throughput_per_day_and_per_user(desk):
    for _ in range(6):
        desk.add_rfq(asked_hours_ago=24, answered_after_hours=1)

    report = desk.report(days=3)
    assert report["quotes_sent"] == 6
    assert report["quotes_per_day"] == 2.0
    assert report["active_users"] == 1
    assert report["quotes_per_user_per_day"] == 2.0


# --------------------------------------------------------------------------
# Honesty of the reporting
# --------------------------------------------------------------------------


def test_an_empty_period_reports_no_data_not_zero(desk):
    report = desk.report()
    assert report["rfqs_received"] == 0
    assert report["response_rate"] is None
    assert report["median_response_hours"] is None
    assert report["win_rate"] is None


def test_only_the_first_quotation_counts_as_the_response(desk):
    """A revised quote sent days later must not make a slow answer look fast —
    nor a fast one look slow."""
    from datetime import timedelta as td

    from app.core.db import SessionLocal
    from app.core.tenancy import organization_scope
    from app.models.enums import QuoteStatus
    from app.models.quote import Quote
    from app.models.rfq import RFQ

    rfq_id = desk.add_rfq(asked_hours_ago=200, answered_after_hours=2)

    db = SessionLocal()
    try:
        with organization_scope(desk.org["org_id"], db):
            row = db.get(RFQ, rfq_id)
            db.add(
                Quote(
                    rfq_id=rfq_id,
                    selling_price=1900.0,
                    status=QuoteStatus.SENT,
                    sent_at=row.first_quoted_at + td(hours=90),
                )
            )
            db.commit()
    finally:
        db.close()

    report = desk.report()
    assert report["median_response_hours"] == 2.0
    assert report["quotes_sent"] == 2, "both quotations were still sent"


def test_rfqs_outside_the_window_are_excluded(desk):
    desk.add_rfq(asked_hours_ago=24, answered_after_hours=1)
    desk.add_rfq(asked_hours_ago=24 * 40, answered_after_hours=1)  # 40 days ago

    assert desk.report(days=7)["rfqs_received"] == 1
    assert desk.report(days=60)["rfqs_received"] == 2


def test_hand_entered_rfqs_without_an_email_date_still_count(desk):
    """RFQs typed in from a phone call have no email timestamp; excluding them
    would quietly inflate the response rate."""
    rfq = desk.client.post(
        "/api/rfqs/parse",
        json={"raw_message": "Phone enquiry: 40HC Shanghai to Dubai", "persist": True},
        headers=desk.headers,
    ).json()["rfq"]

    from app.core.db import SessionLocal
    from app.core.tenancy import organization_scope
    from app.models.rfq import RFQ

    db = SessionLocal()
    try:
        with organization_scope(desk.org["org_id"], db):
            db.get(RFQ, rfq["id"]).received_at = None
            db.commit()
    finally:
        db.close()

    report = desk.report()
    assert report["rfqs_received"] == 1
    assert report["response_rate"] == 0.0


def test_unanswered_list_is_actionable_and_worst_first(desk):
    desk.add_rfq(asked_hours_ago=5)
    desk.add_rfq(asked_hours_ago=100)
    desk.add_rfq(asked_hours_ago=50)

    unanswered = desk.report()["unanswered_rfqs"]
    assert [round(item["waiting_hours"]) for item in unanswered] == [100, 50, 5]
    assert unanswered[0]["reference"].startswith("RFQ-")
    assert "→" in unanswered[0]["lane"]


def test_daily_series_covers_every_day_in_the_window(desk):
    desk.add_rfq(asked_hours_ago=1, answered_after_hours=0.5)

    report = desk.report(days=7)
    assert len(report["daily"]) == 7
    assert report["daily"][-1]["date"] == date.today().isoformat()
    assert sum(point["rfqs"] for point in report["daily"]) == 1


def test_follow_up_compliance(desk):
    """Chasing quotes is the other half of the discipline being sold."""
    from app.core.db import SessionLocal
    from app.core.tenancy import organization_scope
    from app.models.enums import FollowUpStatus, QuoteStatus
    from app.models.follow_up import FollowUp
    from app.models.quote import Quote

    db = SessionLocal()
    try:
        with organization_scope(desk.org["org_id"], db):
            quote = Quote(selling_price=1000.0, status=QuoteStatus.SENT)
            db.add(quote)
            db.flush()
            for status in (
                FollowUpStatus.SENT,
                FollowUpStatus.REPLIED,
                FollowUpStatus.DUE,
                FollowUpStatus.PENDING,
            ):
                db.add(
                    FollowUp(
                        quote_id=quote.id,
                        due_date=date.today() - timedelta(days=1),
                        status=status,
                    )
                )
            db.commit()
    finally:
        db.close()

    report = desk.report()
    assert report["follow_ups_due"] == 4
    assert report["follow_ups_actioned"] == 2
    assert report["follow_up_compliance"] == 50.0


# --------------------------------------------------------------------------
# Live wiring and isolation
# --------------------------------------------------------------------------


def test_the_clock_is_stamped_by_the_real_approval_flow(client):
    """End to end through the API, not by writing the column directly."""
    org = _signup(client, "Live Clock")
    headers = org["headers"]

    rfq = client.post(
        "/api/rfqs/parse",
        json={"raw_message": "Quote 40HC Shanghai to Jebel Ali", "persist": True},
        headers=headers,
    ).json()["rfq"]
    rate = client.post(
        f"/api/rfqs/{rfq['id']}/rates",
        json={"partner_name": "Carrier A", "cost_amount": 1500, "currency": "USD"},
        headers=headers,
    ).json()
    review = client.post(
        "/api/quotes/start",
        json={"rfq_id": rfq["id"], "selected_rate_id": rate["id"], "markup_value": 20},
        headers=headers,
    ).json()
    client.post(
        f"/api/quotes/{review['quote_id']}/approve",
        json={"approved": True, "mark_sent": True},
        headers=headers,
    )

    report = client.get("/api/reports/performance", headers=headers).json()
    assert report["rfqs_quoted"] == 1
    assert report["response_rate"] == 100.0
    assert report["median_response_hours"] is not None
    assert report["median_response_hours"] < 1.0


def test_performance_is_scoped_to_the_callers_organization(client):
    """A hosted deployment must never show one forwarder another's numbers."""
    busy = Desk(client, _signup(client, "Busy Forwarding"))
    for _ in range(5):
        busy.add_rfq(asked_hours_ago=10, answered_after_hours=1, won=True)

    quiet = Desk(client, _signup(client, "Quiet Forwarding"))
    report = quiet.report()

    assert report["rfqs_received"] == 0
    assert report["quotes_sent"] == 0
    assert report["quotes_won"] == 0
    assert busy.report()["rfqs_received"] == 5


def test_csv_export_matches_the_daily_series(desk):
    desk.add_rfq(asked_hours_ago=2, answered_after_hours=1)

    res = desk.client.get("/api/reports/performance.csv?days=7", headers=desk.headers)
    assert res.status_code == 200
    assert "attachment" in res.headers["content-disposition"]
    lines = res.text.strip().splitlines()
    assert lines[0] == "date,rfqs_received,rfqs_quoted,median_response_hours"
    assert len(lines) == 8  # header + 7 days
    assert lines[-1].startswith(date.today().isoformat())
    assert lines[-1].endswith(",1,1,1.0")


def test_invalid_windows_are_rejected(desk):
    assert desk.client.get(
        "/api/reports/performance?days=0", headers=desk.headers
    ).status_code == 400
    assert desk.client.get(
        "/api/reports/performance?start_date=2026-05-01&end_date=2026-04-01",
        headers=desk.headers,
    ).status_code == 400
