"""Email intake: mailbox configs, ingested messages, RFQ received_at, file metadata.

Written defensively (see ``app/core/schema_guards.py``) because a fresh install
already has these objects from the metadata-driven baseline, while an existing
install does not.

Revision ID: 0003_email_intake
Revises: 0002_multi_tenancy
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.core.schema_guards import has_column, has_constraint, has_index, has_table

revision = "0003_email_intake"
down_revision = "0002_multi_tenancy"
branch_labels = None
depends_on = None

# Must match app/models/email_message.py, or a migrated database and a freshly
# created one would diverge.
JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB, "postgresql")


def upgrade() -> None:
    if not has_table("mailbox_configs"):
        op.create_table(
            "mailbox_configs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("org_id", sa.Integer(), nullable=False),
            sa.Column("host", sa.String(length=255), nullable=False),
            sa.Column("port", sa.Integer(), nullable=False, server_default="993"),
            sa.Column("use_ssl", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("username", sa.String(length=255), nullable=False),
            sa.Column("encrypted_password", sa.Text(), nullable=False),
            sa.Column("folder", sa.String(length=128), nullable=False, server_default="INBOX"),
            sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("last_seen_uid", sa.Integer(), nullable=True),
            sa.Column("last_polled_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
    if not has_index("mailbox_configs", "ix_mailbox_configs_org_id"):
        op.create_index("ix_mailbox_configs_org_id", "mailbox_configs", ["org_id"])
    if not has_constraint("mailbox_configs", "fk_mailbox_configs_organization"):
        op.create_foreign_key(
            "fk_mailbox_configs_organization", "mailbox_configs", "organizations",
            ["org_id"], ["id"], ondelete="CASCADE",
        )

    if not has_table("email_messages"):
        op.create_table(
            "email_messages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("org_id", sa.Integer(), nullable=False),
            sa.Column("message_id", sa.String(length=512), nullable=False),
            sa.Column("thread_key", sa.String(length=512), nullable=True),
            sa.Column("uid", sa.Integer(), nullable=True),
            sa.Column("from_address", sa.String(length=320), nullable=True),
            sa.Column("from_name", sa.String(length=255), nullable=True),
            sa.Column("to_address", sa.String(length=320), nullable=True),
            sa.Column("subject", sa.String(length=1024), nullable=True),
            sa.Column("body", sa.Text(), nullable=True),
            sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("classification", sa.String(length=64), nullable=False),
            sa.Column("classification_confidence", sa.Float(), nullable=True),
            sa.Column("classification_reason", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=64), nullable=False),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("rfq_id", sa.Integer(), nullable=True),
            sa.Column("quote_id", sa.Integer(), nullable=True),
            sa.Column("attachments", JSON_TYPE, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
    for index, columns in [
        ("ix_email_messages_org_id", ["org_id"]),
        ("ix_email_messages_message_id", ["message_id"]),
        ("ix_email_messages_thread_key", ["thread_key"]),
        ("ix_email_messages_uid", ["uid"]),
        ("ix_email_messages_from_address", ["from_address"]),
        ("ix_email_messages_received_at", ["received_at"]),
        ("ix_email_messages_rfq_id", ["rfq_id"]),
        ("ix_email_messages_quote_id", ["quote_id"]),
    ]:
        if not has_index("email_messages", index):
            op.create_index(index, "email_messages", columns)
    if not has_constraint("email_messages", "uq_email_messages_org_message"):
        op.create_unique_constraint(
            "uq_email_messages_org_message", "email_messages", ["org_id", "message_id"]
        )
    for name, target, column in [
        ("fk_email_messages_organization", "organizations", "org_id"),
        ("fk_email_messages_rfq", "rfqs", "rfq_id"),
        ("fk_email_messages_quote", "quotes", "quote_id"),
    ]:
        if not has_constraint("email_messages", name):
            op.create_foreign_key(
                name, "email_messages", target, [column], ["id"],
                ondelete="CASCADE" if target == "organizations" else None,
            )

    if not has_column("rfqs", "received_at"):
        op.add_column("rfqs", sa.Column("received_at", sa.DateTime(timezone=True), nullable=True))
    if not has_index("rfqs", "ix_rfqs_received_at"):
        op.create_index("ix_rfqs_received_at", "rfqs", ["received_at"])
    # Existing rows: the creation time is the best available proxy for "asked".
    op.get_bind().execute(
        sa.text("UPDATE rfqs SET received_at = created_at WHERE received_at IS NULL")
    )

    # Documents gain real files (uploads and email attachments), so the row now
    # records what was stored alongside the storage path.
    for column, spec in [
        ("file_name", sa.String(length=255)),
        ("file_size_bytes", sa.Integer()),
        ("content_type", sa.String(length=128)),
    ]:
        if not has_column("documents", column):
            op.add_column("documents", sa.Column(column, spec, nullable=True))


def downgrade() -> None:
    for column in ("file_name", "file_size_bytes", "content_type"):
        if has_column("documents", column):
            op.drop_column("documents", column)
    if has_index("rfqs", "ix_rfqs_received_at"):
        op.drop_index("ix_rfqs_received_at", table_name="rfqs")
    if has_column("rfqs", "received_at"):
        op.drop_column("rfqs", "received_at")
    if has_table("email_messages"):
        op.drop_table("email_messages")
    if has_table("mailbox_configs"):
        op.drop_table("mailbox_configs")
