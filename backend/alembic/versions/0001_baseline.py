"""Baseline schema — create all tables from the ORM metadata.

The initial migration is metadata-driven so the schema is guaranteed to match
the models. Subsequent migrations are produced with `alembic revision
--autogenerate` and contain explicit operations.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-01-01
"""
from __future__ import annotations

from alembic import op

from app.core.db import Base
import app.models  # noqa: F401  (registers all tables on Base.metadata)

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
