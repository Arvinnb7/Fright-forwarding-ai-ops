"""Import a partner's rate sheet, so covered lanes can be quoted immediately.

Every forwarder already has contract rates in a spreadsheet. Loading that sheet
converts "wait for the carrier to reply" into "answer now" for the lanes it
covers, which is the difference between the response-time claim being true and
being aspirational.

The import is written to be run repeatedly against the same file: rows that are
already present, unchanged, are skipped rather than duplicated, so re-uploading
a sheet after editing three lines adds three rates and not three hundred.
Rejected rows are reported individually with their line number — a silent
partial import of pricing data would be worse than a failure.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import PartnerType, TransportMode
from app.models.partner_rate import PartnerRate, RateSource
from app.services.lanes import lane_key, route_key

REQUIRED_COLUMNS = ["origin", "destination", "partner_name", "cost_amount"]
OPTIONAL_COLUMNS = [
    "transport_mode",
    "container_type",
    "partner_type",
    "currency",
    "transit_time",
    "validity_date",
    "included_charges",
    "excluded_charges",
    "free_time",
    "notes",
]
MAX_ROWS = 5000

TEMPLATE_HEADER = REQUIRED_COLUMNS + OPTIONAL_COLUMNS
TEMPLATE_EXAMPLE = [
    "Shanghai", "Jebel Ali", "Ocean Star Line", "1450",
    "Sea", "40HC", "Shipping line", "USD", "22 days", "2026-12-31",
    "Ocean freight, THC origin", "Destination charges, customs", "14 days free",
    "Contract rate 2026-Q3",
]


class TariffImportError(RuntimeError):
    """The file itself is unusable (wrong columns, not a CSV, too large)."""


@dataclass
class RowError:
    line: int
    reason: str


@dataclass
class ImportResult:
    created: int = 0
    skipped_duplicates: int = 0
    errors: list[RowError] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "created": self.created,
            "skipped_duplicates": self.skipped_duplicates,
            "rejected": len(self.errors),
            "errors": [{"line": e.line, "reason": e.reason} for e in self.errors],
        }


def _clean(value: str | None) -> str | None:
    text = (value or "").strip()
    return text or None


def _parse_amount(value: str | None) -> float:
    text = (value or "").strip().replace(",", "").replace("$", "")
    if not text:
        raise ValueError("cost_amount is required")
    amount = float(text)
    if amount < 0:
        raise ValueError("cost_amount cannot be negative")
    return amount


def _parse_date(value: str | None) -> date | None:
    text = _clean(value)
    if text is None:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"validity_date '{text}' is not a recognised date")


def _parse_enum(value: str | None, enum_cls, label: str):
    text = _clean(value)
    if text is None:
        return None
    for member in enum_cls:
        if member.value.casefold() == text.casefold():
            return member
    allowed = ", ".join(member.value for member in enum_cls)
    raise ValueError(f"{label} '{text}' is not one of: {allowed}")


def _duplicate_of(db: Session, candidate: PartnerRate) -> bool:
    """Same lane, same partner, same price, same validity — already loaded."""
    existing = db.execute(
        select(PartnerRate.id).where(
            PartnerRate.source == RateSource.TARIFF,
            PartnerRate.lane_key == candidate.lane_key,
            PartnerRate.partner_name == candidate.partner_name,
            PartnerRate.cost_amount == candidate.cost_amount,
            PartnerRate.validity_date.is_not_distinct_from(candidate.validity_date),
        )
    ).first()
    return existing is not None


def parse_tariff_csv(content: bytes) -> list[dict[str, str]]:
    """Decode and validate the file structure, before touching the database."""
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = content.decode("latin-1")
        except UnicodeDecodeError as exc:  # pragma: no cover
            raise TariffImportError("File is not readable text") from exc

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise TariffImportError("File is empty")

    headers = {(name or "").strip().casefold() for name in reader.fieldnames}
    missing = [column for column in REQUIRED_COLUMNS if column not in headers]
    if missing:
        raise TariffImportError(
            "Missing required column(s): "
            + ", ".join(missing)
            + f". Expected header: {','.join(TEMPLATE_HEADER)}"
        )

    rows = []
    for row in reader:
        rows.append({(k or "").strip().casefold(): (v or "") for k, v in row.items()})
        if len(rows) > MAX_ROWS:
            raise TariffImportError(f"File has more than {MAX_ROWS} rows")
    return rows


def import_tariff(db: Session, content: bytes) -> ImportResult:
    """Load a rate sheet. Valid rows are saved; bad rows are reported by line."""
    rows = parse_tariff_csv(content)
    result = ImportResult()

    for index, row in enumerate(rows, start=2):  # line 1 is the header
        if not any(value.strip() for value in row.values()):
            continue  # blank line
        try:
            origin = _clean(row.get("origin"))
            destination = _clean(row.get("destination"))
            partner_name = _clean(row.get("partner_name"))
            if not origin or not destination:
                raise ValueError("origin and destination are required")
            if not partner_name:
                raise ValueError("partner_name is required")

            mode = _parse_enum(row.get("transport_mode"), TransportMode, "transport_mode")
            partner_type = _parse_enum(row.get("partner_type"), PartnerType, "partner_type")
            container = _clean(row.get("container_type"))

            rate = PartnerRate(
                rfq_id=None,
                partner_name=partner_name,
                partner_type=partner_type,
                source=RateSource.TARIFF,
                origin=origin,
                destination=destination,
                transport_mode=mode,
                container_type=container,
                lane_key=lane_key(origin, destination, mode, container),
                route_key=route_key(origin, destination),
                cost_amount=_parse_amount(row.get("cost_amount")),
                currency=(_clean(row.get("currency")) or "USD").upper()[:8],
                transit_time=_clean(row.get("transit_time")),
                validity_date=_parse_date(row.get("validity_date")),
                included_charges=_clean(row.get("included_charges")),
                excluded_charges=_clean(row.get("excluded_charges")),
                free_time=_clean(row.get("free_time")),
                notes=_clean(row.get("notes")),
            )
        except ValueError as exc:
            result.errors.append(RowError(line=index, reason=str(exc)))
            continue

        if _duplicate_of(db, rate):
            result.skipped_duplicates += 1
            continue

        db.add(rate)
        result.created += 1

    db.commit()
    return result


def template_csv() -> str:
    """A ready-to-fill sheet, so nobody has to guess the column names."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(TEMPLATE_HEADER)
    writer.writerow(TEMPLATE_EXAMPLE)
    return buffer.getvalue()
