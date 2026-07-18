"""Explicit grievance workflow FSM contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

WorkflowState = Literal[
    "case_open",
    "step_1_analysis",
    "step_1_draft",
    "step_1_awaiting_steward_review",
    "step_1_official",
    "step_1_awaiting_management_response",
    "step_1_response_received",
    "step_1_decision_required",
    "step_1_resolved",
    "step_1_appealed",
    "step_2_analysis",
    "step_2_draft",
    "step_2_awaiting_steward_review",
    "step_2_official",
    "step_2_awaiting_management_response",
    "step_2_response_received",
    "step_2_decision_required",
    "step_2_resolved",
    "step_2_appealed",
    "step_3_analysis",
    "step_3_draft",
    "step_3_awaiting_steward_review",
    "step_3_official",
    "step_3_awaiting_management_response",
    "step_3_response_received",
    "step_3_decision_required",
    "step_3_resolved",
    "settled",
    "closed",
    "reopened",
]

class WorkflowTransitionInput(BaseModel):
    to_state: WorkflowState | str
    reason: str | None = None
    actor_id: str | None = None
    grievance_step: str | None = None
    allow_authorized_override: bool = False
    source_type: str | None = None
    source_uuid: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowStateView(BaseModel):
    case_uuid: str
    explicit_state: WorkflowState | str
    current_grievance_step: str | None = None
    case_status: str | None = None
    inferred: bool = False
    inference_confidence: Literal["confirmed", "inferred", "unknown"] = "confirmed"
    permitted_next_states: list[str] = Field(default_factory=list)
    updated_at: datetime | None = None


class WorkflowOutcomeInput(BaseModel):
    outcome: str
    outcome_notes: str | None = None
    resolution_type: str
    outcome_date: datetime | None = None
    recorded_by: str | None = None
    final_step: str | None = None
    supporting_artifact_ids: list[str] = Field(default_factory=list)
    resolved: bool = False
    appealed: bool = False
    next_step: str | None = None
    close_case: bool = False
    mark_settled: bool = False
