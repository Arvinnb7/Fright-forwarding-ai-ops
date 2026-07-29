"""Story-driven demo dataset — makes every page look alive for a walkthrough.

    python -m app.demo_data

Idempotent: if the demo customers already exist it exits without changes.
Runs fully offline: AI-generated *texts* in the seed are canned placeholders
(marked as such); the real AI path runs when you use the app with your API key.
The numbers, statuses and workflow transitions are produced by the same
production services the app uses (quote graph included), not raw inserts.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.logging import configure_logging, get_logger
from app.llm.base import LLMClient
from app.llm.factory import set_llm
from app.models.customer import Customer
from app.models.document import Document
from app.models.enums import (
    DocumentStatus,
    FollowUpStatus,
    IssueSeverity,
    RFQStatus,
)
from app.models.follow_up import FollowUp
from app.models.issue import Issue
from app.models.partner_rate import PartnerRate
from app.schemas.booking import BookingCreateFromQuote
from app.schemas.quote import QuoteApprove, QuoteStart
from app.schemas.rfq import RFQExtraction
from app.services.booking_service import create_booking_from_quote
from app.services.quote_service import approve_quote, start_quote
from app.services.rfq_service import create_rfq_from_extraction

configure_logging()
log = get_logger("demo_data")

MARKER_CUSTOMER = "Gulf Star Trading LLC"


class _SeedLLM(LLMClient):
    """Offline stand-in used ONLY while seeding demo drafts."""

    provider = "seed"
    model = "seed-offline"

    def complete(self, *, system: str, user: str, max_tokens: int = 4096) -> str:
        return (
            "[DEMO DRAFT — regenerate with your AI provider from the app]\n\n"
            "Dear Customer,\n\nPlease find our quotation attached covering the "
            "requested scope. Rates are subject to the stated validity and "
            "standard trading conditions.\n\nBest regards,"
        )

    def complete_structured(
        self, *, system: str, user: str, schema: dict[str, Any], max_tokens: int = 8000
    ) -> dict[str, Any]:  # pragma: no cover - not used during seeding
        raise RuntimeError("Structured calls are not used by the demo seeder.")


def _extraction(**kwargs: Any) -> RFQExtraction:
    return RFQExtraction.model_validate(kwargs)


def seed() -> None:
    """Seed the bootstrap organization with a demo story.

    Multi-tenant: everything is created inside the default organization's scope
    (the one `app.initial_data` creates), never across tenants.
    """
    from app.core.tenancy import organization_scope
    from app.initial_data import ensure_admin

    db = SessionLocal()
    llm = _SeedLLM()
    set_llm(llm)
    org = ensure_admin(db)  # idempotent; returns the bootstrap organization
    with organization_scope(org.id, db):
        _seed_within_org(db, llm)


# Four weeks of enquiry history: (days ago, hours to first quote or None if it
# was never answered, outcome). Shaped to show a real desk's problem — a third
# of enquiries never answered, and a visible fall in win rate as the response
# slows — so the Performance page has something honest to display on day one.
_HISTORY: list[tuple[int, float | None, str]] = [
    (26, 0.4, "won"), (25, 0.6, "won"), (24, 0.8, "lost"), (22, 0.3, "won"),
    (21, 0.9, "won"),
    (20, 1.5, "won"), (19, 2.0, "lost"), (18, 3.2, "won"), (17, 2.6, "lost"),
    (16, 6.0, "won"), (15, 11.0, "lost"), (14, 20.0, "lost"),
    (12, 30.0, "lost"), (11, 52.0, "lost"),
    (10, 96.0, "lost"), (9, 120.0, "lost"), (8, 80.0, "won"),
    (27, None, "unanswered"), (23, None, "unanswered"), (19, None, "unanswered"),
    (13, None, "unanswered"), (9, None, "unanswered"), (6, None, "unanswered"),
    (4, None, "unanswered"),
]

_HISTORY_LANES = [
    ("Shanghai", "Jebel Ali", "Sea", "FCL", "40HC"),
    ("Ningbo", "Dubai", "Sea", "FCL", "20GP"),
    ("Shenzhen", "Dubai", "Air", "Air Cargo", None),
    ("Dubai", "Muscat", "Road", "Trucking", None),
    ("Mundra", "Jebel Ali", "Sea", "FCL", "20GP"),
]


def _seed_response_history(db, customer_ids: list[int]) -> None:
    """Historical RFQs with controlled timings, for the Performance page.

    Written directly rather than through the quote graph: this is history, and
    the point is the timestamps, not re-running the approval workflow 24 times.
    """
    from datetime import datetime, timezone

    from app.models.enums import QuoteStatus
    from app.models.quote import Quote
    from app.models.rfq import RFQ
    from app.services.reference import quote_number, sequence_for

    now = datetime.now(timezone.utc)
    for index, (days_ago, answer_hours, outcome) in enumerate(_HISTORY):
        origin, destination, mode, shipment, container = _HISTORY_LANES[
            index % len(_HISTORY_LANES)
        ]
        asked_at = now - timedelta(days=days_ago, hours=index % 8)
        rfq = create_rfq_from_extraction(
            db,
            _extraction(
                origin=origin, destination=destination, transport_mode=mode,
                shipment_type=shipment, container_type=container,
                commodity="General cargo", missing_fields=[],
                urgency="Normal", urgency_score=0.4,
                recommended_next_action="Quote from partner rates.",
            ),
            f"Please quote {container or ''} {origin} to {destination}.".strip(),
            customer_id=customer_ids[index % len(customer_ids)],
        )
        rfq.received_at = asked_at

        if answer_hours is None:
            rfq.status = RFQStatus.NEW
            db.commit()
            continue

        sent_at = asked_at + timedelta(hours=answer_hours)
        rfq.first_quoted_at = sent_at
        rfq.status = RFQStatus.WON if outcome == "won" else RFQStatus.LOST
        cost = 1400.0 + (index % 5) * 120
        quote = Quote(
            rfq_id=rfq.id,
            customer_id=rfq.customer_id,
            cost_amount=cost,
            selling_price=round(cost * 1.2, 2),
            gross_margin=round(cost * 0.2, 2),
            gross_margin_percentage=16.7,
            status=QuoteStatus.WON if outcome == "won" else QuoteStatus.LOST,
            sent_at=sent_at,
            lost_reason=None if outcome == "won" else "Quoted after the customer had booked.",
        )
        db.add(quote)
        db.flush()
        quote.quote_number = quote_number(
            sequence_for(db, Quote, quote.org_id, quote.id)
        )
        db.commit()


def _seed_within_org(db, llm) -> None:
    try:
        exists = db.execute(
            select(Customer).where(Customer.company_name == MARKER_CUSTOMER)
        ).scalar_one_or_none()
        if exists:
            print("Demo data already present — nothing to do.")
            return

        # ── Customers ────────────────────────────────────────
        gulf = Customer(
            company_name=MARKER_CUSTOMER, contact_name="Ahmed Al Rashidi",
            email="ahmed@gulfstar.example", phone="+971-50-000-0001",
            country="UAE", city="Dubai", industry="Consumer goods distribution",
            notes="Price sensitive; responds fastest on WhatsApp.",
        )
        shen = Customer(
            company_name="Shenzhen Electro Export Co", contact_name="Li Wei",
            email="liwei@sz-electro.example", country="China", city="Shenzhen",
            industry="Electronics",
        )
        muscat = Customer(
            company_name="Muscat Foods LLC", contact_name="Salim Al Busaidi",
            email="salim@muscatfoods.example", country="Oman", city="Muscat",
            industry="F&B", notes="Needs reefer expertise; margin-tolerant.",
        )
        db.add_all([gulf, shen, muscat])
        db.commit()

        # ── 1. Fresh incomplete RFQ (today's inbox) ──────────
        create_rfq_from_extraction(
            db,
            _extraction(
                contact_name="Ahmed Al Rashidi", origin="Shanghai",
                destination="Jebel Ali", transport_mode="Sea",
                shipment_type="FCL", container_type="40HC",
                commodity="Plastic household items", gross_weight="12500 kg",
                cargo_ready_date_text="15 July",
                requested_charges=["Ocean freight", "Destination charges"],
                missing_fields=["Incoterm", "HS code", "Pickup address"],
                urgency="Normal", urgency_score=0.4,
                recommended_next_action="Request Incoterm and HS code before pricing.",
            ),
            "Hi, please quote 1x40HC Shanghai to Jebel Ali, plastic household "
            "items, 12,500 kg, ready 15 July. Need ocean freight + destination "
            "charges. Regards, Ahmed",
            customer_id=gulf.id,
        )

        # ── 2. Ready-for-pricing road freight (UAE → Oman) ───
        rfq_road = create_rfq_from_extraction(
            db,
            _extraction(
                origin="Dubai", destination="Muscat", transport_mode="Road",
                shipment_type="Trucking", commodity="Packaged food products",
                gross_weight="18 t", package_count="22 pallets", incoterm="DAP",
                pickup_address="JAFZA, Dubai", delivery_address="Ghala, Muscat",
                cargo_ready_date_text="next Monday",
                requested_charges=["Door-to-door trucking"],
                missing_fields=[], urgency="High", urgency_score=0.7,
                recommended_next_action="Request trucker rates today.",
            ),
            "Need a full truck Dubai JAFZA to Muscat Ghala, 22 pallets packaged "
            "food, 18 tons, DAP, pickup Monday.",
            customer_id=muscat.id,
        )
        rfq_road.status = RFQStatus.READY_FOR_PRICING

        # ── 3. Waiting for partner rates (air) ───────────────
        rfq_air = create_rfq_from_extraction(
            db,
            _extraction(
                origin="Shenzhen", destination="Dubai", transport_mode="Air",
                shipment_type="Air Cargo", commodity="Consumer electronics",
                gross_weight="850 kg", cbm="4.2", incoterm="FOB",
                requested_charges=["Air freight", "Customs clearance"],
                missing_fields=[], urgency="Critical", urgency_score=0.9,
                recommended_next_action="Chase airline rates — customer needs uplift this week.",
            ),
            "Urgent: 850 kg electronics SZX to DXB, need rate + clearance, FOB.",
            customer_id=shen.id,
        )
        rfq_air.status = RFQStatus.WAITING_FOR_RATES
        db.add(
            PartnerRate(
                rfq_id=rfq_air.id, partner_name="SkyBridge Cargo",
                partner_type="Airline", cost_amount=2.85, currency="USD",
                included_charges="Airport-to-airport per kg",
                excluded_charges="Clearance, delivery",
                transit_time="2 days", notes="Awaiting second airline reply.",
            )
        )
        db.commit()

        # ── 4. Quoted + follow-up due today ──────────────────
        rfq_sea = create_rfq_from_extraction(
            db,
            _extraction(
                origin="Ningbo", destination="Jebel Ali", transport_mode="Sea",
                shipment_type="LCL", commodity="Kitchenware",
                gross_weight="3200 kg", cbm="9.5", incoterm="CIF",
                requested_charges=["Ocean freight", "Insurance"],
                missing_fields=[], urgency="Normal", urgency_score=0.5,
                recommended_next_action="Price with consolidator rate.",
            ),
            "Please quote LCL Ningbo to Jebel Ali, 9.5 cbm kitchenware, CIF.",
            customer_id=gulf.id,
        )
        rate_sea = PartnerRate(
            rfq_id=rfq_sea.id, partner_name="OceanLink Consolidators",
            partner_type="Overseas agent", cost_amount=780.0, currency="USD",
            transit_time="24 days", included_charges="W/M all-in to CFS",
            reliability_score=0.85,
        )
        db.add(rate_sea)
        db.commit()
        quote_sent, _ = start_quote(
            db, QuoteStart(rfq_id=rfq_sea.id, selected_rate_id=rate_sea.id,
                           markup_value=22), llm,
        )
        quote_sent = approve_quote(
            db, quote_sent, QuoteApprove(approved=True, mark_sent=True), llm
        )
        fu = db.execute(
            select(FollowUp).where(FollowUp.quote_id == quote_sent.id)
        ).scalar_one()
        fu.due_date = date.today()
        fu.status = FollowUpStatus.DUE
        quote_sent.next_follow_up_date = date.today()
        db.commit()

        # ── 5. Quote pending human approval (live interrupt) ─
        rfq_pending = create_rfq_from_extraction(
            db,
            _extraction(
                origin="Jebel Ali", destination="Dammam", transport_mode="Sea",
                shipment_type="FCL", container_type="20GP",
                commodity="Auto spare parts", gross_weight="9800 kg",
                incoterm="FOB", requested_charges=["Ocean freight"],
                missing_fields=[], urgency="Normal", urgency_score=0.5,
                recommended_next_action="Compare two carrier offers, then quote.",
            ),
            "Quote 1x20GP Jebel Ali to Dammam, auto spare parts, FOB.",
            customer_id=gulf.id,
        )
        rate_p = PartnerRate(
            rfq_id=rfq_pending.id, partner_name="Gulf Feeder Line",
            partner_type="Shipping line", cost_amount=640.0, currency="USD",
            transit_time="5 days",
        )
        db.add(rate_p)
        db.commit()
        start_quote(
            db, QuoteStart(rfq_id=rfq_pending.id, selected_rate_id=rate_p.id,
                           markup_value=18), llm,
        )  # left paused → shows the human-approval step live in the UI

        # ── 6. Won → booking in transit + docs + open issue ──
        rfq_won = create_rfq_from_extraction(
            db,
            _extraction(
                origin="Shenzhen", destination="Jebel Ali", transport_mode="Sea",
                shipment_type="FCL", container_type="40HC",
                commodity="LED lighting fixtures", gross_weight="14200 kg",
                incoterm="FOB", requested_charges=["Ocean freight", "Destination charges"],
                missing_fields=[], urgency="Normal", urgency_score=0.5,
                recommended_next_action="Book with carrier after confirmation.",
            ),
            "Confirmed order: 1x40HC LED fixtures Shenzhen to Jebel Ali, FOB.",
            customer_id=shen.id,
        )
        rate_w = PartnerRate(
            rfq_id=rfq_won.id, partner_name="BlueWave Shipping",
            partner_type="Shipping line", cost_amount=1450.0, currency="USD",
            transit_time="19 days", free_time="14 days destination",
        )
        db.add(rate_w)
        db.commit()
        quote_won, _ = start_quote(
            db, QuoteStart(rfq_id=rfq_won.id, selected_rate_id=rate_w.id,
                           markup_value=20), llm,
        )
        quote_won = approve_quote(
            db, quote_won, QuoteApprove(approved=True, mark_sent=True), llm
        )
        booking = create_booking_from_quote(
            db,
            BookingCreateFromQuote(
                quote_id=quote_won.id, shipper="Shenzhen Electro Export Co",
                consignee="Gulf Star Trading LLC (Jebel Ali branch)",
                assigned_to="Operations desk",
                etd=date.today() - timedelta(days=6),
                eta=date.today() + timedelta(days=13),
            ),
        )
        booking.status = "In transit"
        db.add_all([
            Document(booking_id=booking.id, document_type="Commercial Invoice",
                     status=DocumentStatus.RECEIVED),
            Document(booking_id=booking.id, document_type="Packing List",
                     status=DocumentStatus.RECEIVED),
            Document(booking_id=booking.id, document_type="Bill of Lading",
                     status=DocumentStatus.REQUIRED,
                     notes="Draft B/L under review with carrier."),
            Document(booking_id=booking.id, document_type="Certificate of Origin",
                     status=DocumentStatus.MISSING,
                     notes="Chasing shipper — needed before arrival."),
        ])
        db.add(
            Issue(
                booking_id=booking.id, issue_type="Missing document",
                severity=IssueSeverity.HIGH,
                description="Certificate of Origin not yet received from shipper; "
                            "risk of clearance delay at Jebel Ali.",
                responsible_party="Shipper (Shenzhen Electro)",
                next_action="Escalate to shipper; request scan by Thursday.",
                due_date=date.today() + timedelta(days=2),
            )
        )
        db.commit()

        # ── 7. A lost quote (win/loss history for CRM) ───────
        rfq_lost = create_rfq_from_extraction(
            db,
            _extraction(
                origin="Mundra", destination="Jebel Ali", transport_mode="Sea",
                shipment_type="FCL", container_type="20GP",
                commodity="Ceramic tiles", incoterm="CFR",
                requested_charges=["Ocean freight"], missing_fields=[],
                urgency="Low", urgency_score=0.2,
                recommended_next_action="Quote from standing tariff.",
            ),
            "Rate check: 1x20GP tiles Mundra to Jebel Ali.",
            customer_id=gulf.id,
        )
        rate_l = PartnerRate(
            rfq_id=rfq_lost.id, partner_name="Indus Container Line",
            partner_type="Shipping line", cost_amount=520.0, currency="USD",
            transit_time="7 days",
        )
        db.add(rate_l)
        db.commit()
        quote_lost, _ = start_quote(
            db, QuoteStart(rfq_id=rfq_lost.id, selected_rate_id=rate_l.id,
                           markup_value=15), llm,
        )
        approve_quote(
            db, quote_lost,
            QuoteApprove(approved=False,
                         lost_reason="Customer's own NVOCC undercut by $60."),
            llm,
        )
        rfq_lost.status = RFQStatus.LOST
        db.commit()

        # ── 8. Four weeks of response-time history ───────────
        _seed_response_history(db, [gulf.id, shen.id, muscat.id])

        print(
            "Demo data created:\n"
            "  3 customers · 7 RFQs across statuses · quotes (sent / pending "
            "approval / won / lost)\n"
            "  1 booking in transit with a 4-document checklist and 1 open "
            "high-severity issue\n"
            "  1 follow-up due today\n"
            f"  {len(_HISTORY)} enquiries of response-time history over four "
            "weeks, for the Performance page\n\n"
            "Note: draft texts in demo records are canned placeholders — "
            "regenerate any draft in the app to see your real AI provider.\n"
            "Log in and open the Dashboard."
        )
    finally:
        set_llm(None)
        db.close()


if __name__ == "__main__":
    try:
        seed()
    except Exception as exc:  # pragma: no cover
        log.error("demo_seed_failed", error=str(exc))
        sys.exit(1)
