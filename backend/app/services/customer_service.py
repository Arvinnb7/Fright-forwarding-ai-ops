"""Customer history statistics — deterministic, computed from the database."""
from __future__ import annotations

from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.enums import QuoteStatus
from app.models.quote import Quote
from app.models.rfq import RFQ
from app.schemas.customer import CustomerStats


def compute_customer_stats(db: Session, customer: Customer) -> CustomerStats:
    rfq_count = int(
        db.execute(
            select(func.count(RFQ.id)).where(RFQ.customer_id == customer.id)
        ).scalar_one()
    )
    quote_count = int(
        db.execute(
            select(func.count(Quote.id)).where(Quote.customer_id == customer.id)
        ).scalar_one()
    )
    won_count = int(
        db.execute(
            select(func.count(Quote.id)).where(
                Quote.customer_id == customer.id, Quote.status == QuoteStatus.WON
            )
        ).scalar_one()
    )
    lost_count = int(
        db.execute(
            select(func.count(Quote.id)).where(
                Quote.customer_id == customer.id, Quote.status == QuoteStatus.LOST
            )
        ).scalar_one()
    )
    avg_margin = db.execute(
        select(func.avg(Quote.gross_margin_percentage)).where(
            Quote.customer_id == customer.id,
            Quote.gross_margin_percentage.is_not(None),
        )
    ).scalar_one()

    routes = db.execute(
        select(RFQ.origin, RFQ.destination).where(
            RFQ.customer_id == customer.id,
            RFQ.origin.is_not(None),
            RFQ.destination.is_not(None),
        )
    ).all()
    top_routes = [
        f"{o} → {d}" for (o, d), _ in Counter(routes).most_common(3)
    ]

    return CustomerStats(
        rfq_count=rfq_count,
        quote_count=quote_count,
        won_count=won_count,
        lost_count=lost_count,
        average_margin_percentage=round(float(avg_margin), 1) if avg_margin is not None else None,
        typical_routes=top_routes,
    )
