"""Multi-tenancy: organizations, per-org scoping, roles, per-org numbering.

Two starting states must both work (see ``app/core/schema_guards.py``):

* **Fresh install** — ``0001_baseline`` created the schema from current ORM
  metadata, so the tenancy objects already exist and each step is a no-op.
* **Existing single-tenant install** — the objects are missing and are created
  here; every existing row is assigned to one "Default Organization" so no data
  is lost and the app keeps working after the upgrade.

Revision ID: 0002_multi_tenancy
Revises: 0001_baseline
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.core.schema_guards import (
    has_column,
    has_constraint,
    has_index,
    has_table,
    unique_constraints_on,
    unique_indexes_on,
)

revision = "0002_multi_tenancy"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None

TENANT_TABLES = [
    "customers",
    "rfqs",
    "partner_rates",
    "quotes",
    "bookings",
    "documents",
    "issues",
    "follow_ups",
]

# (table, column, per-organization unique constraint name)
SCOPED_UNIQUES = [
    ("rfqs", "reference", "uq_rfqs_org_reference"),
    ("quotes", "quote_number", "uq_quotes_org_number"),
    ("bookings", "job_number", "uq_bookings_org_job"),
]


def _default_org_id(bind) -> int:
    """The organization that inherits pre-existing rows (created if needed)."""
    existing = bind.execute(
        sa.text("SELECT id FROM organizations WHERE slug = 'default'")
    ).scalar()
    if existing is not None:
        return int(existing)
    return int(
        bind.execute(
            sa.text(
                "INSERT INTO organizations (name, slug, is_active, company_name, "
                "created_at, updated_at) "
                "VALUES (:name, 'default', true, :name, now(), now()) RETURNING id"
            ),
            {"name": "Default Organization"},
        ).scalar_one()
    )


def upgrade() -> None:
    bind = op.get_bind()

    if not has_table("organizations"):
        op.create_table(
            "organizations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("slug", sa.String(length=64), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("company_name", sa.String(length=255), nullable=True),
            sa.Column("email_signature", sa.String(length=512), nullable=True),
            sa.Column("default_markup_percent", sa.Float(), nullable=True),
            sa.Column("default_currency", sa.String(length=8), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
    if not has_index("organizations", "ix_organizations_slug"):
        op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)

    # Only needed when there is legacy data to adopt; harmless otherwise.
    needs_backfill = any(not has_column(t, "org_id") for t in TENANT_TABLES) or not has_column(
        "users", "organization_id"
    )
    default_org_id = _default_org_id(bind) if needs_backfill else None

    # ── users: organization membership + role ────────────────
    if not has_column("users", "organization_id"):
        op.add_column("users", sa.Column("organization_id", sa.Integer(), nullable=True))
        bind.execute(
            sa.text("UPDATE users SET organization_id = :org WHERE organization_id IS NULL"),
            {"org": default_org_id},
        )
        op.alter_column("users", "organization_id", nullable=False)
    if not has_column("users", "role"):
        op.add_column("users", sa.Column("role", sa.String(length=64), nullable=True))
        bind.execute(sa.text("UPDATE users SET role = 'admin' WHERE role IS NULL"))
        op.alter_column("users", "role", nullable=False, server_default="coordinator")
    if not has_index("users", "ix_users_organization_id"):
        op.create_index("ix_users_organization_id", "users", ["organization_id"])
    if not has_constraint("users", "fk_users_organization"):
        op.create_foreign_key(
            "fk_users_organization", "users", "organizations",
            ["organization_id"], ["id"], ondelete="CASCADE",
        )
    if has_column("users", "is_superuser"):
        op.drop_column("users", "is_superuser")  # superseded by `role`

    # ── tenant scoping on business tables ────────────────────
    for table in TENANT_TABLES:
        if not has_column(table, "org_id"):
            op.add_column(table, sa.Column("org_id", sa.Integer(), nullable=True))
            bind.execute(
                sa.text(f"UPDATE {table} SET org_id = :org WHERE org_id IS NULL"),
                {"org": default_org_id},
            )
            op.alter_column(table, "org_id", nullable=False)
        if not has_index(table, f"ix_{table}_org_id"):
            op.create_index(f"ix_{table}_org_id", table, ["org_id"])
        if not has_constraint(table, f"fk_{table}_organization"):
            op.create_foreign_key(
                f"fk_{table}_organization", table, "organizations",
                ["org_id"], ["id"], ondelete="CASCADE",
            )

    # ── reference numbers become unique per organization ─────
    for table, column, new_name in SCOPED_UNIQUES:
        for name in unique_constraints_on(table, column):
            op.drop_constraint(name, table, type_="unique")
        for name in unique_indexes_on(table, column):
            op.drop_index(name, table_name=table)
        if not has_constraint(table, new_name):
            op.create_unique_constraint(new_name, table, ["org_id", column])
        if not has_index(table, f"ix_{table}_{column}"):
            op.create_index(f"ix_{table}_{column}", table, [column])


def downgrade() -> None:
    for table, column, new_name in SCOPED_UNIQUES:
        if has_constraint(table, new_name):
            op.drop_constraint(new_name, table, type_="unique")
        op.create_unique_constraint(f"uq_{table}_{column}", table, [column])

    for table in TENANT_TABLES:
        if has_constraint(table, f"fk_{table}_organization"):
            op.drop_constraint(f"fk_{table}_organization", table, type_="foreignkey")
        if has_index(table, f"ix_{table}_org_id"):
            op.drop_index(f"ix_{table}_org_id", table_name=table)
        if has_column(table, "org_id"):
            op.drop_column(table, "org_id")

    if not has_column("users", "is_superuser"):
        op.add_column(
            "users",
            sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default=sa.true()),
        )
    if has_constraint("users", "fk_users_organization"):
        op.drop_constraint("fk_users_organization", "users", type_="foreignkey")
    if has_index("users", "ix_users_organization_id"):
        op.drop_index("ix_users_organization_id", table_name="users")
    if has_column("users", "role"):
        op.drop_column("users", "role")
    if has_column("users", "organization_id"):
        op.drop_column("users", "organization_id")

    if has_index("organizations", "ix_organizations_slug"):
        op.drop_index("ix_organizations_slug", table_name="organizations")
    if has_table("organizations"):
        op.drop_table("organizations")
