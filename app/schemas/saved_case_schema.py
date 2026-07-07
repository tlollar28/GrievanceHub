"""Pydantic models for saved case listing and open/reopen workflow (Phase 1.4E)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.case_step_progression_schema import (
    CaseTimelineEvent,
    StepTemplateAvailability,
    StepType,
)

SavedCaseWorkspaceStatus = Literal["open", "closed", "reopened", "appealed"]

SavedCaseStatusFilter = Literal["open", "closed", "reopened", "appealed", "all"]

SavedCaseAction = Literal[
    "open_case",
    "reopen_case",
    "continue_to_next_step",
    "view_timeline",
    "create_form_draft",
]

ReopenSource = Literal["manual_ui", "ai_command", "system"]


class SavedCaseTemplateAvailability(BaseModel):
    """Template buildability for the case's current step."""

    step_type: StepType | None = None
    template_available: bool = False
    template_id: str | None = None
    availability_status: StepTemplateAvailability | None = None


class SavedCaseSummary(BaseModel):
    """List/detail summary for a saved grievance case workspace."""

    case_id: int
    case_uuid: str
    case_number: str | None = Field(
        default=None,
        description="Display case number when available; never invented.",
    )
    title: str | None = None
    issue_summary: str | None = None
    grievant_or_class: str | None = None
    current_step_type: StepType | None = None
    current_step_status: str | None = None
    workspace_status: SavedCaseWorkspaceStatus
    legacy_case_status: str = Field(
        description="GrievanceCase.status column (open/closed) for compatibility.",
    )
    created_at: datetime | None = None
    last_activity_at: datetime | None = None
    closed_at: datetime | None = None
    reopened_at: datetime | None = None
    latest_outcome_summary: str | None = None
    latest_outcome_type: str | None = None
    template_availability: SavedCaseTemplateAvailability | None = None
    available_actions: list[SavedCaseAction] = Field(default_factory=list)
    has_step_progression: bool = False


class SavedCaseListResponse(BaseModel):
    count: int
    order: Literal["newest_first", "oldest_first"]
    status_filter: SavedCaseStatusFilter
    step_filter: StepType | None = None
    search: str | None = None
    cases: list[SavedCaseSummary]


class OpenCaseRequest(BaseModel):
    source: ReopenSource = "manual_ui"


class ReopenCaseRequest(BaseModel):
    reason: str | None = Field(
        default=None,
        description="Optional steward or AI-supplied reopen reason; never invented.",
    )
    source: ReopenSource = "manual_ui"


class OpenCaseResponse(BaseModel):
    case: SavedCaseSummary
    action_taken: Literal["already_open", "opened", "closed_requires_reopen"]
    message: str


class ReopenCaseResponse(BaseModel):
    case: SavedCaseSummary
    action_taken: Literal["reopened", "already_open"]
    message: str
    source: ReopenSource


class SavedCaseTimelineResponse(BaseModel):
    case_uuid: str
    order: Literal["newest_first", "oldest_first"]
    count: int
    events: list[CaseTimelineEvent]
