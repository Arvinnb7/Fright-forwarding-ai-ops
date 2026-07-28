"""RFQ persistence and status logic."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.enums import RFQStatus
from app.models.rfq import RFQ
from app.schemas.rfq import RFQExtraction
from app.services.reference import rfq_reference, sequence_for


def _status_from_extraction(extraction: RFQExtraction) -> RFQStatus:
    if extraction.missing_fields:
        return RFQStatus.INCOMPLETE
    return RFQStatus.READY_FOR_PRICING


def create_rfq_from_extraction(
    db: Session,
    extraction: RFQExtraction,
    raw_message: str,
    customer_id: int | None = None,
) -> RFQ:
    """Persist a parsed extraction as a new RFQ record.

    The full extraction is also stored in `extracted_fields` (JSONB) so nothing
    the model produced is lost, even fields without a dedicated column.
    """
    rfq = RFQ(
        customer_id=customer_id,
        raw_message=raw_message,
        origin=extraction.origin,
        destination=extraction.destination,
        pickup_address=extraction.pickup_address,
        delivery_address=extraction.delivery_address,
        transport_mode=extraction.transport_mode,
        shipment_type=extraction.shipment_type,
        container_type=extraction.container_type,
        commodity=extraction.commodity,
        hs_code=extraction.hs_code,
        gross_weight=extraction.gross_weight,
        cbm=extraction.cbm,
        dimensions=extraction.dimensions,
        package_count=extraction.package_count,
        incoterm=extraction.incoterm,
        dangerous_goods=extraction.dangerous_goods,
        temperature_requirement=extraction.temperature_requirement,
        insurance_required=extraction.insurance_required,
        customs_required=extraction.customs_required,
        warehouse_required=extraction.warehouse_required,
        special_handling=extraction.special_handling,
        missing_fields=extraction.missing_fields,
        requested_charges=extraction.requested_charges,
        extracted_fields=extraction.model_dump(mode="json"),
        recommended_next_action=extraction.recommended_next_action,
        urgency=extraction.urgency,
        urgency_score=extraction.urgency_score,
        status=_status_from_extraction(extraction),
    )
    db.add(rfq)
    db.flush()  # assign id
    rfq.reference = rfq_reference(sequence_for(db, RFQ, rfq.org_id, rfq.id))
    db.commit()
    db.refresh(rfq)
    return rfq
