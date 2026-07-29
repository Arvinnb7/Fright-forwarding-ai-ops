"""Lane identity on rates and RFQs, and rates that outlive their RFQ.

`partner_rates.rfq_id` becomes nullable so an imported tariff can exist without
an enquiry behind it — that is what lets a covered lane be quoted immediately
instead of waiting for a carrier to reply.

The lane keys are backfilled through the application's own normaliser rather
than re-implemented in SQL, so stored keys and freshly computed ones can never
drift apart and silently stop matching.

Revision ID: 0005_lane_rate_memory
Revises: 0004_response_time
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.core.schema_guards import has_column, has_index
from app.services.lanes import lane_key, route_key

revision = "0005_lane_rate_memory"
down_revision = "0004_response_time"
branch_labels = None
depends_on = None

_RATE_COLUMNS = [
    ("source", sa.String(length=64)),
    ("origin", sa.String(length=255)),
    ("destination", sa.String(length=255)),
    ("transport_mode", sa.String(length=64)),
    ("container_type", sa.String(length=64)),
    ("lane_key", sa.String(length=512)),
    ("route_key", sa.String(length=512)),
]


def upgrade() -> None:
    for column, spec in _RATE_COLUMNS:
        if not has_column("partner_rates", column):
            op.add_column("partner_rates", sa.Column(column, spec, nullable=True))
    for column in ("lane_key", "route_key", "validity_date"):
        index = f"ix_partner_rates_{column}"
        if not has_index("partner_rates", index):
            op.create_index(index, "partner_rates", [column])

    for column in ("lane_key", "route_key"):
        if not has_column("rfqs", column):
            op.add_column("rfqs", sa.Column(column, sa.String(length=512), nullable=True))
        index = f"ix_rfqs_{column}"
        if not has_index("rfqs", index):
            op.create_index(index, "rfqs", [column])

    bind = op.get_bind()

    # Existing rates were entered against an RFQ; inherit its lane so the
    # history that already exists becomes searchable rather than starting empty.
    bind.execute(
        sa.text(
            """
            UPDATE partner_rates
               SET origin = COALESCE(partner_rates.origin, rfqs.origin),
                   destination = COALESCE(partner_rates.destination, rfqs.destination),
                   transport_mode = COALESCE(partner_rates.transport_mode, rfqs.transport_mode),
                   container_type = COALESCE(partner_rates.container_type, rfqs.container_type)
              FROM rfqs
             WHERE partner_rates.rfq_id = rfqs.id
            """
        )
    )
    bind.execute(
        sa.text(
            "UPDATE partner_rates SET source = 'Partner quote' WHERE source IS NULL"
        )
    )

    _backfill_lane_keys(bind, "partner_rates")
    _backfill_lane_keys(bind, "rfqs")

    op.alter_column(
        "partner_rates", "source", existing_type=sa.String(length=64), nullable=False
    )
    # Tariff rates have no enquiry behind them.
    op.alter_column(
        "partner_rates", "rfq_id", existing_type=sa.Integer(), nullable=True
    )

    # Repair: when 0002 replaced the global unique constraints on the reference
    # columns with per-organization ones, it dropped the backing indexes without
    # reliably re-creating the plain lookup index. Databases upgraded through
    # that revision were left without them, so every lookup by reference — the
    # path that attaches a partner's rate reply to its RFQ — became a table
    # scan. Fresh installs have them from the ORM metadata; this brings existing
    # installs back in line.
    for table, column in (
        ("rfqs", "reference"),
        ("quotes", "quote_number"),
        ("bookings", "job_number"),
    ):
        index = f"ix_{table}_{column}"
        if has_column(table, column) and not has_index(table, index):
            op.create_index(index, table, [column])


def _backfill_lane_keys(bind, table: str) -> None:
    rows = bind.execute(
        sa.text(
            f"SELECT id, origin, destination, transport_mode, container_type FROM {table}"
        )
    ).fetchall()
    for row in rows:
        bind.execute(
            sa.text(
                f"UPDATE {table} SET lane_key = :lane, route_key = :route WHERE id = :id"
            ),
            {
                "lane": lane_key(row[1], row[2], row[3], row[4]),
                "route": route_key(row[1], row[2]),
                "id": row[0],
            },
        )


def downgrade() -> None:
    op.alter_column(
        "partner_rates", "rfq_id", existing_type=sa.Integer(), nullable=False
    )
    for column in ("lane_key", "route_key"):
        index = f"ix_rfqs_{column}"
        if has_index("rfqs", index):
            op.drop_index(index, table_name="rfqs")
        if has_column("rfqs", column):
            op.drop_column("rfqs", column)
    for column, _ in _RATE_COLUMNS:
        index = f"ix_partner_rates_{column}"
        if has_index("partner_rates", index):
            op.drop_index(index, table_name="partner_rates")
        if has_column("partner_rates", column):
            op.drop_column("partner_rates", column)
