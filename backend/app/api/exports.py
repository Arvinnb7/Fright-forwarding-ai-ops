"""CSV export endpoints (spec §13)."""
from __future__ import annotations

import csv
from io import StringIO
from typing import Any, Sequence

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.customer import Customer
from app.models.quote import Quote
from app.models.rfq import RFQ
from app.models.user import User

router = APIRouter()


def _csv_response(filename: str, header: Sequence[str], rows: list[Sequence[Any]]) -> Response:
    buf = StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    writer.writerows(rows)
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _enum_val(v: Any) -> Any:
    return getattr(v, "value", v)


@router.get("/rfqs.csv")
def export_rfqs(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> Response:
    rfqs = db.execute(select(RFQ).order_by(RFQ.id)).scalars().all()
    header = [
        "reference", "status", "origin", "destination", "transport_mode",
        "shipment_type", "container_type", "commodity", "incoterm",
        "gross_weight", "cbm", "urgency", "missing_fields", "created_at",
    ]
    rows = [
        [
            r.reference, _enum_val(r.status), r.origin, r.destination,
            _enum_val(r.transport_mode), _enum_val(r.shipment_type),
            r.container_type, r.commodity, r.incoterm, r.gross_weight, r.cbm,
            _enum_val(r.urgency), "; ".join(r.missing_fields or []),
            r.created_at.isoformat(),
        ]
        for r in rfqs
    ]
    return _csv_response("rfqs.csv", header, rows)


@router.get("/quotes.csv")
def export_quotes(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> Response:
    quotes = db.execute(select(Quote).order_by(Quote.id)).scalars().all()
    header = [
        "quote_number", "status", "cost_amount", "selling_price", "currency",
        "gross_margin", "gross_margin_percentage", "validity_date", "sent_at",
        "next_follow_up_date", "lost_reason", "created_at",
    ]
    rows = [
        [
            q.quote_number, _enum_val(q.status), q.cost_amount, q.selling_price,
            q.currency, q.gross_margin, q.gross_margin_percentage,
            q.validity_date.isoformat() if q.validity_date else "",
            q.sent_at.isoformat() if q.sent_at else "",
            q.next_follow_up_date.isoformat() if q.next_follow_up_date else "",
            q.lost_reason, q.created_at.isoformat(),
        ]
        for q in quotes
    ]
    return _csv_response("quotes.csv", header, rows)


@router.get("/customers.csv")
def export_customers(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> Response:
    customers = db.execute(select(Customer).order_by(Customer.id)).scalars().all()
    header = [
        "company_name", "contact_name", "email", "phone", "country", "city",
        "industry", "next_follow_up_date", "created_at",
    ]
    rows = [
        [
            c.company_name, c.contact_name, c.email, c.phone, c.country, c.city,
            c.industry,
            c.next_follow_up_date.isoformat() if c.next_follow_up_date else "",
            c.created_at.isoformat(),
        ]
        for c in customers
    ]
    return _csv_response("customers.csv", header, rows)
