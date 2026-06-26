"""Follow-up scheduled against a quote."""
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import TimestampMixin, enum_column
from app.models.enums import FollowUpStatus

if TYPE_CHECKING:
    from app.models.quote import Quote


class FollowUp(Base, TimestampMixin):
    __tablename__ = "follow_ups"

    id: Mapped[int] = mapped_column(primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id"), index=True, nullable=False)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), index=True)

    due_date: Mapped[date | None] = mapped_column(Date, index=True)
    status: Mapped[FollowUpStatus] = mapped_column(
        enum_column(FollowUpStatus), default=FollowUpStatus.PENDING
    )
    draft_message: Mapped[str | None] = mapped_column(Text)
    sent_manually: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)

    quote: Mapped["Quote"] = relationship(back_populates="follow_ups")
