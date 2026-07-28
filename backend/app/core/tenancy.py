"""Automatic multi-tenant isolation.

Design decision (security-critical): tenant filtering is **not** left to each
route. A single forgotten `.where(Model.org_id == ...)` in a SaaS is a
cross-customer data leak, and there are dozens of query sites. Instead:

* every tenant-scoped model inherits :class:`TenantMixin` (an ``org_id`` column);
* a SQLAlchemy ``do_orm_execute`` listener injects ``with_loader_criteria`` into
  **every** ORM SELECT, including relationship and lazy loads;
* a ``before_flush`` listener stamps ``org_id`` on new rows automatically.

A query written without any tenant filter is therefore still safe.

**Where the active organization comes from.** It is stored on the Session
(``session.info``), not only in a ``ContextVar``: FastAPI runs sync endpoints and
sync dependencies in *separate* threadpool calls, and each call gets its own
copy of the context — so a ContextVar set inside an auth dependency would not be
visible to the endpoint. The session object is the thing that genuinely travels
through one request, so it is the source of truth. A ContextVar is kept as a
fallback for single-threaded callers (Celery tasks, CLI scripts, tests) via
:func:`organization_scope`.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

from sqlalchemy import ForeignKey, event, orm
from sqlalchemy.orm import Mapped, Session, mapped_column, with_loader_criteria

ORG_KEY = "org_id"
BYPASS_KEY = "bypass_tenant_filter"

# Fallback for code paths that are not inside a web request.
_current_org_id: ContextVar[int | None] = ContextVar("current_org_id", default=None)
_bypass_tenant_filter: ContextVar[bool] = ContextVar("bypass_tenant_filter", default=False)


class TenantMixin:
    """Adds the tenant foreign key. Any model inheriting this is auto-filtered."""

    @orm.declared_attr
    def org_id(cls) -> Mapped[int]:  # noqa: N805
        return mapped_column(
            ForeignKey("organizations.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        )


# ── Selecting the active organization ────────────────────────


def bind_session_to_org(session: Session, org_id: int) -> None:
    """Bind a request's session to an organization (called by the auth dependency)."""
    session.info[ORG_KEY] = org_id


def get_current_org_id(session: Session | None = None) -> int | None:
    if session is not None and session.info.get(ORG_KEY) is not None:
        return session.info[ORG_KEY]
    return _current_org_id.get()


def set_current_org_id(org_id: int | None) -> None:
    """Set the fallback context (workers, scripts, tests)."""
    _current_org_id.set(org_id)


@contextmanager
def organization_scope(org_id: int, session: Session | None = None) -> Iterator[None]:
    """Run a block as a specific organization.

    Used by Celery tasks and CLI scripts, which have no request. Pass the
    session as well when one is already open, so the binding is unambiguous.
    """
    token = _current_org_id.set(org_id)
    previous = session.info.get(ORG_KEY) if session is not None else None
    if session is not None:
        session.info[ORG_KEY] = org_id
    try:
        yield
    finally:
        _current_org_id.reset(token)
        if session is not None:
            if previous is None:
                session.info.pop(ORG_KEY, None)
            else:
                session.info[ORG_KEY] = previous


@contextmanager
def bypass_tenant_isolation(session: Session | None = None) -> Iterator[None]:
    """Temporarily disable the automatic filter.

    Only for operations that legitimately span tenants: authenticating a user by
    email before their organization is known, listing organizations for the
    scheduler, and bootstrap/migrations. Keep the block as small as possible.
    """
    token = _bypass_tenant_filter.set(True)
    previous = session.info.get(BYPASS_KEY) if session is not None else None
    if session is not None:
        session.info[BYPASS_KEY] = True
    try:
        yield
    finally:
        _bypass_tenant_filter.reset(token)
        if session is not None:
            if previous is None:
                session.info.pop(BYPASS_KEY, None)
            else:
                session.info[BYPASS_KEY] = previous


def _is_bypassed(session: Session | None) -> bool:
    if session is not None and session.info.get(BYPASS_KEY):
        return True
    return _bypass_tenant_filter.get()


def _tenant_models() -> list[type]:
    from app.core.db import Base

    return [
        mapper.class_
        for mapper in Base.registry.mappers
        if issubclass(mapper.class_, TenantMixin)
    ]


_installed = False


def install_tenant_guards() -> None:
    """Register the SELECT filter and the INSERT stamper. Idempotent."""
    global _installed
    if _installed:
        return
    _installed = True

    @event.listens_for(Session, "do_orm_execute")
    def _apply_tenant_filter(execute_state) -> None:  # type: ignore[no-untyped-def]
        if not execute_state.is_select:
            return
        if execute_state.is_column_load or execute_state.is_relationship_load:
            # Refreshing already-loaded rows; the originating load was filtered.
            return
        session = execute_state.session
        if _is_bypassed(session):
            return

        org_id = get_current_org_id(session)
        for model in _tenant_models():
            execute_state.statement = execute_state.statement.options(
                with_loader_criteria(
                    model,
                    # No tenant selected -> match nothing (fail closed).
                    (model.org_id == org_id) if org_id is not None else False,
                    include_aliases=True,
                )
            )

    @event.listens_for(Session, "before_flush")
    def _stamp_org_id(session: Session, _flush_context, _instances) -> None:  # type: ignore[no-untyped-def]
        org_id = get_current_org_id(session)
        for obj in session.new:
            if isinstance(obj, TenantMixin) and getattr(obj, "org_id", None) is None:
                if org_id is None:
                    raise RuntimeError(
                        f"Refusing to persist {type(obj).__name__} without an "
                        "organization. Bind the session (web request) or wrap the "
                        "operation in organization_scope() (worker/script)."
                    )
                obj.org_id = org_id
