"""Follow-up schemas."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.agents.follow_up import FollowUpType
from app.models.enums import FollowUpStatus


class FollowUpOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    quote_id: int
    customer_id: int | None
    due_date: date | None
    status: FollowUpStatus
    draft_message: str | None
    sent_manually: bool
    notes: str | None
    created_at: datetime
    updated_at: datetime


class FollowUpUpdate(BaseModel):
    due_date: date | None = None
    status: FollowUpStatus | None = None
    draft_message: str | None = None
    sent_manually: bool | None = None
    notes: str | None = None


class FollowUpDraftIn(BaseModel):
    follow_up_type: FollowUpType = FollowUpType.POLITE
    save: bool = True  # store the draft on the follow-up record


class FollowUpDraftOut(BaseModel):
    draft: str
