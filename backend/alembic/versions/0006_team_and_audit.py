"""Ownership on work records, and the audit trail.

`owner_id` is nullable everywhere and left NULL for existing rows: inventing an
owner for historical work would put a name against decisions that person may
never have made, which is exactly the failure an audit trail exists to prevent.

Revision ID: 0006_team_and_audit
Revises: 0005_lane_rate_memory
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.core.schema_guards import has_column, has_constraint, has_index, has_table

revision = "0006_team_and_audit"
down_revision = "0005_lane_rate_memory"
branch_labels = None
depends_on = None

OWNED_TABLES = ("rfqs", "quotes", "bookings")


def upgrade() -> None:
    for table in OWNED_TABLES:
        if not has_column(table, "owner_id"):
            op.add_column(table, sa.Column("owner_id", sa.Integer(), nullable=True))
        index = f"ix_{table}_owner_id"
        if not has_index(table, index):
            op.create_index(index, table, ["owner_id"])
        constraint = f"fk_{table}_owner"
        if not has_constraint(table, constraint):
            # SET NULL, not CASCADE: removing a member must never delete the
            # shipments they handled.
            op.create_foreign_key(
                constraint, table, "users", ["owner_id"], ["id"], ondelete="SET NULL"
            )

    if not has_table("audit_events"):
        op.create_table(
            "audit_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("org_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=True),
            # Stored, not joined: the record must stay readable after the person
            # who made the change has left and their account has been removed.
            sa.Column("actor", sa.String(length=255), nullable=False),
            sa.Column("entity_type", sa.String(length=64), nullable=False),
            sa.Column("entity_id", sa.Integer(), nullable=False),
            sa.Column("entity_ref", sa.String(length=64), nullable=True),
            sa.Column("action", sa.String(length=64), nullable=False),
            sa.Column("field", sa.String(length=64), nullable=True),
            sa.Column("old_value", sa.Text(), nullable=True),
            sa.Column("new_value", sa.Text(), nullable=True),
            sa.Column("summary", sa.Text(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )
    for index, columns in [
        ("ix_audit_events_org_id", ["org_id"]),
        ("ix_audit_events_user_id", ["user_id"]),
        ("ix_audit_events_entity_type", ["entity_type"]),
        ("ix_audit_events_entity_id", ["entity_id"]),
    ]:
        if not has_index("audit_events", index):
            op.create_index(index, "audit_events", columns)
    for name, target, column, ondelete in [
        ("fk_audit_events_organization", "organizations", "org_id", "CASCADE"),
        ("fk_audit_events_user", "users", "user_id", "SET NULL"),
    ]:
        if not has_constraint("audit_events", name):
            op.create_foreign_key(
                name, "audit_events", target, [column], ["id"], ondelete=ondelete
            )


def downgrade() -> None:
    if has_table("audit_events"):
        op.drop_table("audit_events")
    for table in OWNED_TABLES:
        constraint = f"fk_{table}_owner"
        if has_constraint(table, constraint):
            op.drop_constraint(constraint, table, type_="foreignkey")
        index = f"ix_{table}_owner_id"
        if has_index(table, index):
            op.drop_index(index, table_name=table)
        if has_column(table, "owner_id"):
            op.drop_column(table, "owner_id")
