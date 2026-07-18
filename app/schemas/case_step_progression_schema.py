"""Pydantic models for grievance case step progression (Phase 1.4C foundation).

Models a same-case workspace lifecycle across Step 1 → Step 2 → Step 3 with
timestamped timeline history, decision/outcome capture, close/reopen behavior,
and form draft history linkage. No database persistence or API routes in this phase.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from app.schemas.grievance_form_draft_schema import DraftStatus, DraftValidationResult
from app.schemas.grievance_template_schema import StepLevel

StepType = StepLevel

StepStatus = Literal[
    "not_started",
    "open",
    "analysis_generated",
    "follow_up_active",
    "draft_form_created",
    "meeting_or_hearing_held",
    "decision_added",
    "closed_resolved",
    "closed_withdrawn",
    "reopened",
    "appealed_to_next_step",
]

OutcomeType = Literal[
    "pending",
    "resolved",
    "granted",
    "partially_granted",
    "denied",
    "withdrawn",
    "settled",
    "appealed",
    "closed_no_appeal",
    "unknown",
]

TimelineEventType = Literal[
    "case_created",
    "case_opened",
    "case_reopened",
    "case_closed",
    "case_settled",
    "case_archived",
    "files_uploaded",
    "concern_added",
    "analysis_report_generated",
    "analysis_report_saved",
    "analysis_report_saved_and_printed",
    "context_saved",
    "analysis_updated",
    "follow_up_added",
    "form_draft_created",
    "grievance_form_saved",
    "grievance_form_saved_and_printed",
    "grievance_revision_created",
    "missing_fields_updated",
    "steward_edit_added",
    "step_meeting_or_hearing_held",
    "step_decision_added",
    "step_closed",
    "step_reopened",
    "step_changed",
    "important_case_decision_recorded",
    "appealed_to_next_step",
    "export_created_later",
    "management_response_uploaded",
]

CaseWorkspaceStatus = Literal["open", "closed", "settled", "archived"]

StepTemplateAvailability = Literal[
    "available",
    "unavailable",
    "deferred_separate_form_required",
    "unconfirmed_pending_steward_confirmation",
]


class CaseTimelineEventReferences(BaseModel):
    """Optional links from a timeline event to related case artifacts."""

    report_version_id: int | None = None
    report_version_number: int | None = None
    follow_up_message_ids: list[int] = Field(default_factory=list)
    form_draft_id: str | None = None
    upload_refs: list[str] = Field(default_factory=list)
    outcome_id: str | None = None
    prior_step_type: StepType | None = None
    next_step_type: StepType | None = None
    export_ref: str | None = None


class CaseTimelineEvent(BaseModel):
    """One timestamped entry in the case workspace history."""

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    case_uuid: str
    step_type: StepType | None = None
    event_type: TimelineEventType
    event_timestamp: datetime
    title: str
    details: str | None = None
    references: CaseTimelineEventReferences = Field(
        default_factory=CaseTimelineEventReferences,
    )


class CaseStepOutcomeRecord(BaseModel):
    """Management decision/outcome captured for a grievance step."""

    outcome_id: str = Field(default_factory=lambda: str(uuid4()))
    step_type: StepType
    outcome_type: OutcomeType = "pending"
    decision_summary: str | None = None
    decision_date: str | None = Field(
        default=None,
        description="Steward-supplied decision date when known; never invented.",
    )
    decision_maker_name: str | None = None
    decision_maker_title: str | None = None
    decision_document_refs: list[str] = Field(default_factory=list)
    steward_notes: str | None = None
    step_closed: bool = False
    case_closed: bool = False
    appeal_requested: bool = False
    next_step_target: StepType | None = None
    recorded_at: datetime


class CaseStepStage(BaseModel):
    """One grievance step/stage within the same saved case workspace."""

    step_type: StepType
    step_number: int = Field(..., ge=1, le=3)
    status: StepStatus = "open"
    is_closed: bool = False
    was_reopened: bool = False
    appealed_from_prior_step: StepType | None = None
    prior_step_outcome_id: str | None = None
    report_version_id: int | None = None
    report_version_number: int | None = None
    follow_up_message_ids: list[int] = Field(default_factory=list)
    form_draft_ids: list[str] = Field(default_factory=list)
    export_refs: list[str] = Field(default_factory=list)
    template_id: str | None = None
    template_availability: StepTemplateAvailability | None = None
    outcomes: list[CaseStepOutcomeRecord] = Field(default_factory=list)
    opened_at: datetime
    closed_at: datetime | None = None
    reopened_at: datetime | None = None


class CaseFormDraftHistoryRecord(BaseModel):
    """Saved metadata for an editable grievance form draft within a case step."""

    draft_id: str = Field(default_factory=lambda: str(uuid4()))
    case_uuid: str
    step_type: StepType
    template_id: str
    draft_version: int = Field(default=1, ge=1)
    report_version_id: int | None = None
    report_version_number: int | None = None
    follow_up_message_ids: list[int] = Field(default_factory=list)
    validation_status: DraftStatus
    missing_required_field_ids: list[str] = Field(default_factory=list)
    steward_override_field_ids: list[str] = Field(default_factory=list)
    approval_status: str | None = None
    export_status: str | None = None
    created_at: datetime


class CaseStepProgressionState(BaseModel):
    """In-memory case step progression aggregate for one saved workspace."""

    case_uuid: str
    workspace_status: CaseWorkspaceStatus = "open"
    current_step_type: StepType
    steps: list[CaseStepStage] = Field(default_factory=list)
    timeline: list[CaseTimelineEvent] = Field(default_factory=list)
    form_draft_history: list[CaseFormDraftHistoryRecord] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None
    reopened_at: datetime | None = None


class CaseStepOutcomeInput(BaseModel):
    """Steward-supplied outcome/decision fields for a step."""

    outcome_type: OutcomeType = "pending"
    decision_summary: str | None = None
    decision_date: str | None = None
    decision_maker_name: str | None = None
    decision_maker_title: str | None = None
    decision_document_refs: list[str] = Field(default_factory=list)
    steward_notes: str | None = None
    close_step: bool = False
    close_case: bool = False
    appeal_to_next_step: bool = False


class CaseFormDraftHistoryInput(BaseModel):
    """Input for recording a form draft against a case step."""

    step_type: StepType
    template_id: str
    draft_version: int = Field(default=1, ge=1)
    report_version_id: int | None = None
    report_version_number: int | None = None
    follow_up_message_ids: list[int] = Field(default_factory=list)
    validation: DraftValidationResult
    steward_override_field_ids: list[str] = Field(default_factory=list)
    approval_status: str | None = None
    export_status: str | None = None


class StepTemplateAvailabilityInfo(BaseModel):
    """Whether an official template is buildable for a grievance step."""

    step_type: StepType
    template_available: bool
    template_id: str | None = None
    availability_status: StepTemplateAvailability
    notes: list[str] = Field(default_factory=list)
