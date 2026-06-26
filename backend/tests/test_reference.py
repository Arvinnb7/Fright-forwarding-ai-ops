from datetime import date

from app.services.reference import job_number, quote_number, rfq_reference


def test_reference_formats():
    d = date(2026, 6, 26)
    assert rfq_reference(42, d) == "RFQ-2026-0042"
    assert quote_number(7, d) == "Q-2026-0007"
    assert job_number(21, d) == "JOB-2026-0021"
