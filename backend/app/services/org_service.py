"""Organization onboarding: signup and member management."""
from __future__ import annotations

import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.core.tenancy import bypass_tenant_isolation
from app.models.organization import Organization
from app.models.user import User, UserRole


class SignupError(ValueError):
    """Raised when an organization or user cannot be created."""


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "org"


def _unique_slug(db: Session, name: str) -> str:
    base = _slugify(name)[:48]
    with bypass_tenant_isolation(db):
        taken = set(
            db.execute(
                select(Organization.slug).where(Organization.slug.like(f"{base}%"))
            ).scalars()
        )
    if base not in taken:
        return base
    for n in range(2, 1000):
        candidate = f"{base}-{n}"
        if candidate not in taken:
            return candidate
    raise SignupError("Could not allocate an organization slug.")


def email_exists(db: Session, email: str) -> bool:
    with bypass_tenant_isolation(db):
        return (
            db.execute(
                select(func.count(User.id)).where(func.lower(User.email) == email.lower())
            ).scalar_one()
            or 0
        ) > 0


def create_organization_with_admin(
    db: Session,
    *,
    company_name: str,
    email: str,
    password: str,
    full_name: str | None = None,
) -> tuple[Organization, User]:
    """Create a new tenant and its first administrator.

    Runs with tenant isolation bypassed because no organization exists yet —
    this is the one legitimate "before a tenant" write path.
    """
    if email_exists(db, email):
        raise SignupError("An account with this email already exists.")

    with bypass_tenant_isolation(db):
        org = Organization(
            name=company_name,
            slug=_unique_slug(db, company_name),
            company_name=company_name,
        )
        db.add(org)
        db.flush()

        user = User(
            email=email.lower(),
            full_name=full_name,
            hashed_password=hash_password(password),
            organization_id=org.id,
            role=UserRole.ADMIN,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(org)
        db.refresh(user)
    return org, user


def add_member(
    db: Session,
    *,
    organization_id: int,
    email: str,
    password: str,
    role: UserRole,
    full_name: str | None = None,
) -> User:
    """Add a user to an existing organization (admin action)."""
    if email_exists(db, email):
        raise SignupError("An account with this email already exists.")
    user = User(
        email=email.lower(),
        full_name=full_name,
        hashed_password=hash_password(password),
        organization_id=organization_id,
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
