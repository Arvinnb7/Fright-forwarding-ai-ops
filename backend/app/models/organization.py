"""Organization — the tenant boundary for the SaaS deployment.

Every business record belongs to exactly one organization. Isolation between
organizations is enforced automatically at the query layer (see
`app/core/tenancy.py`), not by remembering to filter in each route.
"""
from __future__ import annotations

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import TimestampMixin


class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Company defaults used in generated documents. These override the
    # process-wide .env defaults so each tenant brands its own output.
    company_name: Mapped[str | None] = mapped_column(String(255))
    email_signature: Mapped[str | None] = mapped_column(String(512))
    default_markup_percent: Mapped[float | None] = mapped_column()
    default_currency: Mapped[str | None] = mapped_column(String(8))
