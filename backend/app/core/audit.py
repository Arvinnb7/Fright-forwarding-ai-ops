"""Automatic audit recording.

Like tenant filtering and ownership, this is installed once on the ORM rather
than called from each service. An audit trail that depends on every code path
remembering to write to it is an audit trail with holes in it, and the holes
appear exactly where they matter — in a hurried fix to the pricing flow.

Only decisions worth reconstructing are recorded: money, customer-facing
commitments, shipment status, and who may do what. A corrected phone number is
noise, and a log of everything is read by nobody, which is the same as no log.

Two phases are needed because of when SQLAlchemy knows what:

* ``before_flush`` is the only point where the *previous* value of a changed
  field still exists;
* ``after_flush`` is the first point where a newly created row has an id.

So changes are computed in the first and written in the second, where they join
the transaction that caused them — an audit row can never be committed for a
change that was rolled back.
"""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from app.core.tenancy import get_current_actor, get_current_org_id

PENDING_KEY = "_pending_audit"

# model name -> fields whose change is a decision, not a detail.
AUDITED_FIELDS: dict[str, tuple[str, ...]] = {
    "Quote": ("status", "selling_price", "cost_amount", "sent_at", "lost_reason"),
    "RFQ": ("status", "first_quoted_at"),
    "Booking": ("status", "etd", "eta"),
    "Issue": ("status", "severity"),
    "User": ("role", "is_active"),
    "MailboxConfig": ("username", "host", "is_enabled"),
}

# Records whose creation is itself worth logging.
AUDITED_CREATIONS = ("Quote", "Booking", "User")

# Human-readable identifier per model, in preference order.
_REFERENCE_FIELDS = ("quote_number", "reference", "job_number", "email", "username")

_MAX_VALUE_CHARS = 500


def _reference_of(obj: Any) -> str | None:
    for field in _REFERENCE_FIELDS:
        value = getattr(obj, field, None)
        if value:
            return str(value)[:64]
    return None


def _render(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)[:_MAX_VALUE_CHARS]


def _changed_fields(obj: Any, fields: tuple[str, ...]) -> list[tuple[str, Any, Any]]:
    state = inspect(obj)
    changes: list[tuple[str, Any, Any]] = []
    for field in fields:
        attribute = state.attrs.get(field)
        if attribute is None:
            continue
        history = attribute.history
        if not history.has_changes():
            continue
        old = history.deleted[0] if history.deleted else None
        new = history.added[0] if history.added else None
        if old == new:
            continue
        changes.append((field, old, new))
    return changes


def _summarize(entity: str, reference: str | None, field: str, old: Any, new: Any) -> str:
    what = f"{entity} {reference}" if reference else entity
    old_text, new_text = _render(old), _render(new)
    if old_text is None:
        return f"{what}: {field} set to {new_text}"
    if new_text is None:
        return f"{what}: {field} cleared (was {old_text})"
    return f"{what}: {field} {old_text} → {new_text}"


_installed = False


def install_audit_trail() -> None:
    """Register the change recorder. Idempotent."""
    global _installed
    if _installed:
        return
    _installed = True

    from app.models.audit import AuditAction, AuditEvent

    @event.listens_for(Session, "before_flush")
    def _collect_changes(session: Session, _flush_context, _instances) -> None:  # type: ignore[no-untyped-def]
        org_id = get_current_org_id(session)
        if org_id is None:
            # Nothing to attribute this to. The tenancy guard rejects the write
            # anyway if it touches tenant data.
            return

        actor = get_current_actor(session) or {}
        common = {
            "org_id": org_id,
            "user_id": actor.get("id"),
            "actor": actor.get("email") or "system",
        }
        pending: list[dict[str, Any]] = session.info.setdefault(PENDING_KEY, [])

        for obj in session.new:
            entity = type(obj).__name__
            if entity in AUDITED_CREATIONS:
                pending.append(
                    {
                        **common,
                        "target": obj,  # id is assigned during the flush
                        "entity_type": entity,
                        "action": AuditAction.CREATED,
                        "summary": f"{entity} created",
                    }
                )

        for obj in session.dirty:
            entity = type(obj).__name__
            fields = AUDITED_FIELDS.get(entity)
            if not fields or not session.is_modified(obj, include_collections=False):
                continue
            reference = _reference_of(obj)
            for field, old, new in _changed_fields(obj, fields):
                pending.append(
                    {
                        **common,
                        "target": obj,
                        "entity_type": entity,
                        "entity_ref": reference,
                        "action": AuditAction.UPDATED,
                        "field": field,
                        "old_value": _render(old),
                        "new_value": _render(new),
                        "summary": _summarize(entity, reference, field, old, new),
                    }
                )

    @event.listens_for(Session, "after_flush")
    def _write_events(session: Session, _flush_context) -> None:  # type: ignore[no-untyped-def]
        pending = session.info.pop(PENDING_KEY, None)
        if not pending:
            return
        for entry in pending:
            target = entry.pop("target")
            entry.setdefault("entity_ref", _reference_of(target))
            session.add(
                AuditEvent(entity_id=getattr(target, "id", 0) or 0, **entry)
            )

    @event.listens_for(Session, "after_rollback")
    def _discard_pending(session: Session) -> None:  # type: ignore[no-untyped-def]
        """A change that was rolled back never happened; its audit row must not
        survive into the next flush."""
        session.info.pop(PENDING_KEY, None)
