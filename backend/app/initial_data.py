"""Bootstrap script: ensure the admin user and sample data exist.

Run automatically by the backend container on startup. Idempotent — safe to run
repeatedly.
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.logging import configure_logging, get_logger
from app.core.security import hash_password
from app.models.customer import Customer
from app.models.user import User

configure_logging()
log = get_logger("bootstrap")


def ensure_admin(db) -> None:
    existing = db.execute(
        select(User).where(User.email == settings.admin_email)
    ).scalar_one_or_none()
    if existing:
        return
    db.add(
        User(
            email=settings.admin_email,
            full_name=settings.user_full_name,
            hashed_password=hash_password(settings.admin_password),
            is_active=True,
            is_superuser=True,
        )
    )
    db.commit()
    log.info("admin_created", email=settings.admin_email)


def ensure_sample_customer(db) -> None:
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
        ensure_admin(db)
        ensure_sample_customer(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
