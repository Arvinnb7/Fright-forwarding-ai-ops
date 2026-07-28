"""Bootstrap: ensure a default organization, its admin user, and sample data.

Run automatically by the backend container on startup. Idempotent — safe to run
repeatedly. In the SaaS deployment new tenants arrive via /api/auth/signup; this
bootstrap exists so a fresh install is usable immediately.
"""
from __future__ import annotations

from sqlalchemy import func, select

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.logging import configure_logging, get_logger
from app.core.tenancy import bypass_tenant_isolation, organization_scope
from app.models.customer import Customer
from app.models.organization import Organization
from app.models.user import User
from app.services.org_service import create_organization_with_admin

configure_logging()
log = get_logger("bootstrap")


def ensure_admin(db) -> Organization:
    """Create the default organization + admin if they don't exist yet."""
    with bypass_tenant_isolation(db):
        user = db.execute(
            select(User).where(func.lower(User.email) == settings.admin_email.lower())
        ).scalar_one_or_none()
        if user is not None:
            return db.get(Organization, user.organization_id)

    org, user = create_organization_with_admin(
        db,
        company_name=settings.company_name,
        email=settings.admin_email,
        password=settings.admin_password,
        full_name=settings.user_full_name,
    )
    log.info("bootstrap_organization_created", org_id=org.id, email=user.email)
    return org


def ensure_sample_customer(db, org: Organization) -> None:
    with organization_scope(org.id, db):
        existing = db.execute(
            select(Customer).where(Customer.company_name == "Sample Trading LLC")
        ).scalar_one_or_none()
        if existing:
            return
        db.add(
            Customer(
                company_name="Sample Trading LLC",
                contact_name="Ahmed",
                email="ahmed@sample-trading.example",
                country="UAE",
                city="Dubai",
                industry="Distribution",
                notes="Sample seed customer.",
            )
        )
        db.commit()
        log.info("sample_customer_created")


def main() -> None:
    db = SessionLocal()
    try:
        org = ensure_admin(db)
        ensure_sample_customer(db, org)
    finally:
        db.close()


if __name__ == "__main__":
    main()
