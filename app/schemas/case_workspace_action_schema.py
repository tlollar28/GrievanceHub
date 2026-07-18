"""Typed contracts for case chat and explicit artifact-generation actions."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.case_step_progression_schema import (
    StepTemplateAvailability,
    StepType,
)

# ---------------------------------------------------------------------------
# Action types and shared literals
# ---------------------------------------------------------------------------

WorkspaceActionType = Literal[
    "save_and_update_analysis",
    "generate_analysis_report",
    "generate_grievance",
]

InteractionSource = Literal["manual_ui", "ai_command", "system"]

WorkspaceActionExecutionStatus = Literal[
    "not_implemented_in_w1",
    "prerequisites_not_met",
    "case_not_found",
    "invalid_request",
    # Reserved / used by W2+ execution:
    "accepted",
    "completed",
]

RetrievalStatus = Literal["ok", "empty", "failed", "skipped"]
CaseMemoryUpdateStatus = Literal[
    "updated", "projection_failed", "failed", "unknown", "not_applicable"
]

PrerequisiteCode = Literal[
    "case_not_found",
    "case_closed_requires_reopen",
    "analysis_report_required",
    "step_progression_required",
    "template_unavailable",
    "template_deferred",
    "step_progression_init_deferred_to_w4",  # historical; no longer emitted after W4
    "action_not_implemented_in_w1",
    "interaction_content_required",
]

# ---------------------------------------------------------------------------
# Interaction payload (shared by /interactions and compatibility /actions)
# ---------------------------------------------------------------------------


class WorkspaceInteractionPayload(BaseModel):
    """Steward chat/context payload for a case-scoped AI interaction.

    On the canonical ``POST /cases/{case_uuid}/interactions`` route, submitting
    this payload persists conversation and may update Case Memory. It does not
    generate an analysis report or grievance.
    """

    message: str | None = Field(
        default=None,
        description="New steward question, note, or free-text context.",
    )
    clarification: str | None = Field(
        default=None,
        description="Clarification or correction relative to prior case context.",
    )
    fact_updates: dict | None = Field(
        default=None,
        description="Partial known_facts updates merged into cumulative case facts.",
    )
    upload_refs: list[str] = Field(
        default_factory=list,
        description=(
            "Case asset UUIDs (preferred) or legacy upload refs. "
            "File bodies are uploaded via POST /cases/{uuid}/assets; "
            "chat interactions consume asset metadata as case context."
        ),
    )
    source: InteractionSource = Field(
        default="manual_ui",
        description="Origin of the interaction (manual UI or future AI command).",
    )
    pinned_report_version: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Optional report version number to pin for historical grounding. "
            "Does not create a new analysis version."
        ),
    )


# ---------------------------------------------------------------------------
# Canonical case interaction request/response
# ---------------------------------------------------------------------------


class CaseInteractionRequest(BaseModel):
    """Canonical POST /cases/{case_uuid}/interactions request body.

    One submitted interaction = one persisted AI turn (and Case Memory updates).
    Analysis reports and grievances require separate explicit steward actions.
    """

    message: str | None = Field(
        default=None,
        description="Steward chat message (question, context, correction).",
    )
    clarification: str | None = Field(
        default=None,
        description="Optional clarification relative to prior case context.",
    )
    fact_updates: dict | None = Field(
        default=None,
        description="Partial known_facts updates to merge safely.",
    )
    upload_refs: list[str] = Field(
        default_factory=list,
        description="Referenced case asset UUIDs or legacy upload refs.",
    )
    source: InteractionSource = Field(default="manual_ui")
    pinned_report_version: int | None = Field(default=None, ge=1)

    def to_interaction_payload(self) -> WorkspaceInteractionPayload:
        return WorkspaceInteractionPayload(
            message=self.message,
            clarification=self.clarification,
            fact_updates=self.fact_updates,
            upload_refs=list(self.upload_refs),
            source=self.source,
            pinned_report_version=self.pinned_report_version,
        )


class CaseInteractionMessageSummary(BaseModel):
    """Persisted conversation message returned with an interaction response."""

    id: int
    role: str
    content: str
    metadata: dict[str, Any] | None = None
    created_at: datetime | None = None


class CaseInteractionResponse(BaseModel):
    """Typed envelope for POST /cases/{case_uuid}/interactions.

    A successful interaction persists conversation, reflects case context, reports
    retrieval and Case Memory status, and recalculates action availability. No
    analysis report or grievance artifact is created automatically.
    """

    case_uuid: str
    status: WorkspaceActionExecutionStatus
    message: str
    workspace_current: bool = False
    user_message: CaseInteractionMessageSummary | None = None
    assistant_message: CaseInteractionMessageSummary | None = None
    ai_answer: str | None = None
    answer_type: str | None = None
    citations: list[dict[str, Any]] = Field(default_factory=list)
    disclosures: list[str] = Field(default_factory=list)
    facts_needed: list[str] = Field(default_factory=list)
    retrieval_status: RetrievalStatus | None = None
    retrieval_error: bool = False
    case_memory_update_status: CaseMemoryUpdateStatus = "not_applicable"
    prior_report_version_id: int | None = None
    prior_report_version_number: int | None = None
    current_report_version_id: int | None = None
    current_report_version_number: int | None = None
    analysis_update: "AnalysisUpdateResult | None" = None
    available_actions: list["WorkspaceActionAvailability"] = Field(default_factory=list)
    generate_grievance_available: bool = False
    missing_prerequisites: list["WorkspaceActionPrerequisite"] = Field(
        default_factory=list
    )
    timeline_events: list["WorkspaceTimelineEventSummary"] = Field(default_factory=list)
    grievance_draft_created: bool = False
    generation_snapshot_persisted: bool = False
    export_attempted: bool = False
    analysis_versions_created: int = Field(
        default=0,
        description="Number of new analysis versions created by this interaction (0 or 1).",
    )



# ---------------------------------------------------------------------------
# Request (compatibility /actions)
# ---------------------------------------------------------------------------


class WorkspaceActionRequest(BaseModel):
    """POST /cases/{case_uuid}/actions request body.

    Primary steward-facing action on this route is ``generate_grievance`` (W5).
    ``save_and_update_analysis`` remains an internal/compatibility analysis
    refresh primitive — not a steward UI button. Prefer
    ``POST /cases/{case_uuid}/interactions`` for case chat.
    """

    action: WorkspaceActionType
    interaction: WorkspaceInteractionPayload | None = Field(
        default=None,
        description=(
            "Optional context. Prefer POST /interactions for chat. "
            "For generate_grievance, W5 will save-first when present."
        ),
    )


# ---------------------------------------------------------------------------
# Prerequisites and action availability
# ---------------------------------------------------------------------------


class WorkspaceActionPrerequisite(BaseModel):
    """One structured missing or blocking prerequisite for an action."""

    code: PrerequisiteCode
    message: str
    resolved_in_phase: str | None = Field(
        default=None,
        description="Phase expected to satisfy this prerequisite when deferred.",
    )
    details: dict | None = None


class WorkspaceActionAvailability(BaseModel):
    """Whether a workspace action is available for the current case."""

    action: WorkspaceActionType
    available: bool
    reason: str | None = None
    steward_visible: bool = Field(
        default=True,
        description=(
            "When False, future UI must not render this as a steward button. "
            "Chat uses POST /interactions; save_and_update_analysis is internal."
        ),
    )
    missing_prerequisites: list[WorkspaceActionPrerequisite] = Field(
        default_factory=list
    )
    current_step_type: StepType | None = None
    template_id: str | None = None
    template_availability: StepTemplateAvailability | None = None


# ---------------------------------------------------------------------------
# Case generation snapshot (provenance; not persisted until W5)
# ---------------------------------------------------------------------------


class CaseGenerationSnapshotMetadata(BaseModel):
    """Immutable provenance record for a grievance generation.

    Snapshots identify the exact case state used to generate a draft.
    Reopening a case does not mutate an old snapshot. Newer context produces
    newer report versions and newer grievance snapshots/drafts.

    **Future persistence (recommended):** store this JSON on the draft record
    (e.g. ``case_form_draft_records.generation_snapshot``) rather than a
    dedicated ``case_generation_snapshots`` table.
    """

    case_uuid: str
    grievance_step: StepType
    analysis_report_version_id: int | None = None
    analysis_report_version_number: int | None = None
    included_follow_up_message_ids: list[int] = Field(default_factory=list)
    included_upload_refs: list[str] = Field(
        default_factory=list,
        description="Upload refs or future upload ids included in generation.",
    )
    template_id: str | None = None
    draft_version: int | None = Field(default=None, ge=1)
    generated_at: datetime
    source_action: WorkspaceActionType = "generate_grievance"
    interaction_id: str | None = Field(
        default=None,
        description="Optional context revision or interaction id that triggered generation.",
    )
    source_corpus_version_refs: list[str] = Field(
        default_factory=list,
        description="Future source corpus/version references if later needed.",
    )


# ---------------------------------------------------------------------------
# Result contracts
# ---------------------------------------------------------------------------


class WorkspaceTimelineEventSummary(BaseModel):
    """Compact timeline reference returned with interaction/analysis responses."""

    event_id: str
    event_type: str
    title: str
    event_timestamp: datetime | None = None
    report_version_id: int | None = None
    report_version_number: int | None = None


class AnalysisUpdateResult(BaseModel):
    """Conversation or analysis-update details returned by workspace actions."""

    steward_action_label: str | None = Field(
        default=None,
        description="Steward-facing label for an explicit action when applicable.",
    )
    interaction_saved: bool = False
    prior_conversation_preserved: bool = True
    facts_updated: bool = False
    ai_response_persisted: bool = False
    case_memory_update_status: CaseMemoryUpdateStatus = "not_applicable"
    prior_report_version_id: int | None = None
    prior_report_version_number: int | None = None
    new_report_version_id: int | None = None
    new_report_version_number: int | None = None
    is_current_analysis: bool = False
    older_versions_retained: bool = True
    trigger_message_id: int | None = None
    trigger_metadata: dict | None = Field(
        default=None,
        description=(
            "Trigger metadata on the steward message. "
            "No CaseReportVersion.trigger_type column — linkage is via "
            "trigger_message_id plus message metadata."
        ),
    )
    timeline_events: list[WorkspaceTimelineEventSummary] = Field(default_factory=list)
    message: str = "Workspace action completed."


class GrievanceGenerationResult(BaseModel):
    """Contract for Generate Grievance draft preview and Save outcomes."""

    context_saved_first: bool = False
    analysis_reflected_latest_context: bool = False
    draft_created: bool = True
    draft_id: str | None = None
    draft_version: int | None = None
    template_id: str | None = None
    step_type: StepType | None = None
    draft_status: str | None = "ready_for_steward_review"
    editable: bool = True
    field_values: dict[str, Any] = Field(default_factory=dict)
    official_artifact_created: bool = False
    snapshot: CaseGenerationSnapshotMetadata | None = None
    export_attempted: bool = False
    message: str = (
        "Editable grievance draft ready for steward review. "
        "Save or Save and Print to create an official artifact. "
        "Full Local 300 overlay PDF filling remains W5."
    )


# ---------------------------------------------------------------------------
# Response envelope (compatibility /actions)
# ---------------------------------------------------------------------------


class WorkspaceActionResponse(BaseModel):
    """Typed envelope returned by POST /cases/{case_uuid}/actions."""

    case_uuid: str
    action: WorkspaceActionType
    status: WorkspaceActionExecutionStatus
    message: str
    steward_action_label: str | None = Field(
        default=None,
        description=(
            "Steward-facing label when applicable (Generate Grievance). "
            "None for internal save_and_update_analysis — not a UI button."
        ),
    )
    available_actions: list[WorkspaceActionAvailability] = Field(default_factory=list)
    missing_prerequisites: list[WorkspaceActionPrerequisite] = Field(
        default_factory=list
    )
    prior_report_version_id: int | None = None
    prior_report_version_number: int | None = None
    current_report_version_id: int | None = None
    current_report_version_number: int | None = None
    analysis_update: AnalysisUpdateResult | None = None
    grievance_generation: GrievanceGenerationResult | None = None
    grievance_draft_created: bool = False
    analysis_preview_ready: bool = False
    analysis_editable: bool = False
    analysis_preview: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Temporary read-only analysis preview. Not persisted until Save. "
            "Cancel discards this payload client-side; no version/artifact/OCR."
        ),
    )
    official_artifact_created: bool = False
    timeline_events: list[WorkspaceTimelineEventSummary] = Field(default_factory=list)
    interaction_accepted_for_later_phases: bool = Field(
        default=False,
        description=(
            "True when an interaction payload was present on the request. "
            "Prefer POST /interactions for chat."
        ),
    )
