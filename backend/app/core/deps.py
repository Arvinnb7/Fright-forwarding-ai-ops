"""Shared FastAPI dependencies (auth, tenancy, roles)."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import decode_access_token
from app.core.tenancy import (
    bind_session_to_org,
    bind_session_to_user,
    bypass_tenant_isolation,
)
from app.models.organization import Organization
from app.models.user import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=True)

# Methods that cannot change anything.
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the caller and activate their organization for this request.

    Setting the tenant context here is what makes every downstream query
    automatically scoped — routes never filter by organization themselves.
    """
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    subject = decode_access_token(token)
    if subject is None:
        raise credentials_error

    # These two lookups are deliberately cross-tenant: they are what establishes
    # the tenant for the remainder of the request.
    with bypass_tenant_isolation(db):
        user = db.get(User, int(subject))
        if user is None or not user.is_active:
            raise credentials_error
        organization = db.get(Organization, user.organization_id)

    if organization is None or not organization.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Organization is inactive."
        )

    # Bind the tenant to this request's session: every subsequent query in
    # this request is filtered automatically (see app/core/tenancy.py).
    bind_session_to_org(db, user.organization_id)
    # And the actor, so new records get an owner and changes get attributed
    # without every service having to pass a user around.
    bind_session_to_user(db, user.id, user.email)
    return user


def _bearer_token(request: Request) -> str | None:
    header = request.headers.get("Authorization") or ""
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def enforce_role_policy(request: Request, db: Session = Depends(get_db)) -> None:
    """Block read-only members from anything that changes state.

    Installed once on the API router rather than added route by route, for the
    same reason tenant filtering is: a permission you have to remember to apply
    is a permission that will eventually be missed, and every new endpoint would
    silently start out unguarded. Here a viewer is denied every unsafe method by
    default, and a route has to be deliberately exempted to behave otherwise.

    Requests without a usable token are left alone — the route's own auth
    dependency answers those, so unauthenticated endpoints (login, signup) keep
    working.
    """
    if request.method in SAFE_METHODS:
        return
    token = _bearer_token(request)
    if token is None:
        return
    subject = decode_access_token(token)
    if subject is None:
        return
    with bypass_tenant_isolation(db):
        user = db.get(User, int(subject))
    if user is not None and user.is_active and user.role == UserRole.VIEWER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your role is read-only and cannot change data.",
        )


def require_write(current_user: User = Depends(get_current_user)) -> User:
    """Any role except read-only viewers.

    Redundant with `enforce_role_policy` for unsafe methods, and deliberately
    so: it states the requirement at the endpoint that depends on it.
    """
    if current_user.role == UserRole.VIEWER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Read-only role.")
    return current_user


def require_pricing_approval(current_user: User = Depends(get_current_user)) -> User:
    """Guard for actions that commit money or customer-facing commitments."""
    if not current_user.can_approve_pricing:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your role does not permit approving pricing or sending.",
        )
    return current_user


def require_org_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_org_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Administrator role required."
        )
    return current_user
