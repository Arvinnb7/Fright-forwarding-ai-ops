"""Issue / exception-tracker schemas."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.agents.shipment_ops import IssueDraftKind
from app.models.enums import IssueSeverity, IssueStatus


class IssueCreate(BaseModel):
    booking_id: int | None = None
    issue_type: str
    severity: IssueSeverity = IssueSeverity.MEDIUM
    description: str | None = None
    responsible_party: str | None = None
    next_action: str | None = None
    due_date: date | None = None


class IssueUpdate(BaseModel):
    issue_type: str | None = None
    severity: IssueSeverity | None = None
    description: str | None = None
    responsible_party: str | None = None
    next_action: str | None = None
    due_date: date | None = None
    status: IssueStatus | None = None
    resolution_notes: str | None = None


class IssueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    booking_id: int | None
    issue_type: str
    severity: IssueSeverity
    description: str | None
    responsible_party: str | None
    next_action: str | None
    due_date: date | None
    status: IssueStatus
    resolution_notes: str | None
    created_at: datetime
    updated_at: datetime


class IssueDraftIn(BaseModel):
    kind: IssueDraftKind = IssueDraftKind.ESCALATION


class IssueDraftOut(BaseModel):
    draft: str
