"""Response-time instrumentation: rfqs.first_quoted_at.

Backfilled from the existing quotation history (the earliest ``sent_at`` per
RFQ), so a company that has been using the system already sees a real baseline
on day one instead of an empty chart.

Revision ID: 0004_response_time
Revises: 0003_email_intake
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.core.schema_guards import has_column, has_index

revision = "0004_response_time"
down_revision = "0003_email_intake"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not has_column("rfqs", "first_quoted_at"):
        op.add_column(
            "rfqs", sa.Column("first_quoted_at", sa.DateTime(timezone=True), nullable=True)
        )
    if not has_index("rfqs", "ix_rfqs_first_quoted_at"):
        op.create_index("ix_rfqs_first_quoted_at", "rfqs", ["first_quoted_at"])

    # The first quotation actually sent is the answer the customer received.
    op.get_bind().execute(
        sa.text(
            """
            UPDATE rfqs
               SET first_quoted_at = earliest.sent_at
              FROM (
                    SELECT rfq_id, MIN(sent_at) AS sent_at
                      FROM quotes
                     WHERE rfq_id IS NOT NULL AND sent_at IS NOT NULL
                     GROUP BY rfq_id
                   ) AS earliest
             WHERE rfqs.id = earliest.rfq_id
               AND rfqs.first_quoted_at IS NULL
            """
        )
    )


def downgrade() -> None:
    if has_index("rfqs", "ix_rfqs_first_quoted_at"):
        op.drop_index("ix_rfqs_first_quoted_at", table_name="rfqs")
    if has_column("rfqs", "first_quoted_at"):
        op.drop_column("rfqs", "first_quoted_at")
