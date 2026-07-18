"""First-class Case Memory and Case Overview contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class CaseCloseRequest(BaseModel):
    outcome: str = Field(..., min_length=1)
    outcome_notes: str | None = None
    resolution_type: str = Field(
        ...,
        description="e.g. resolved, withdrawn, denied_final, settled_via_close",
    )
    close_date: datetime | None = None
    closed_by: str | None = None
    final_grievance_step: str | None = None
    supporting_document_refs: list[str] = Field(default_factory=list)


class CaseSettleRequest(BaseModel):
    settlement_notes: str | None = None
    settlement_date: datetime | None = None
    settlement_document_refs: list[str] = Field(
        default_factory=list,
        description="Future settlement document asset refs.",
    )
    settlement_amount: float | None = Field(
        default=None,
        description="Optional future settlement amount; not required.",
    )
    settled_by: str | None = None


class CaseReopenRequest(BaseModel):
    reason: str | None = None
    reopened_by: str | None = None
    source: Literal["manual_ui", "ai_command", "system"] = "manual_ui"


class RecordStepOutcomeRequest(BaseModel):
    """Steward decision at current/named step (resolve/close or continue)."""

    step_type: str | None = None
    outcome_type: str = "pending"
    decision_summary: str | None = None
    decision_date: str | None = None
    steward_notes: str | None = None
    close_case: bool = False
    close_step: bool = False
    appeal_to_next_step: bool = False
    decision_document_refs: list[str] = Field(default_factory=list)
    # When closing via this decision, optional structured close fields.
    resolution_type: str | None = None
    closed_by: str | None = None


class CaseOverview(BaseModel):
    """Auto-maintained Case Overview derived from Case Memory."""

    case_uuid: str
    employee: str | None = None
    case_number: str | None = None
    issue: str | None = None
    current_status: str
    current_step: str | None = None
    explicit_workflow_state: str | None = None
    current_recommendation: str | None = None
    recommendation_rationale: str | None = None
    recommendation_status: str | None = None
    ai_recommendation: dict[str, Any] | None = None
    steward_decision: dict[str, Any] | None = None
    supporting_evidence_count: int = 0
    supporting_evidence_refs: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    outstanding_issues: list[str] = Field(default_factory=list)
    evidence_count: int = 0
    analysis_report_count: int = 0
    official_grievance_count: int = 0
    management_response_count: int = 0
    management_response_status: str | None = None
    last_activity_at: datetime | None = None
    assigned_steward: str | None = None
    settlement_status: str | None = None
    outcome_status: str | None = None
    close_date: datetime | None = None
    reopen_count: int = 0
    latest_official_report_version: int | None = None
    latest_official_grievance_version: int | None = None
    latest_official_report_title: str | None = None
    latest_official_grievance_title: str | None = None
    source: Literal["case_memory"] = "case_memory"


class CaseMemoryResponse(BaseModel):
    case_uuid: str
    schema_version: str
    reopen_count: int
    memory: dict[str, Any]
    overview: CaseOverview
    updated_at: datetime | None = None
