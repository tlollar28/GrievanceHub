"""Pydantic models for editable grievance form drafts (Phase 1.4B foundation).

Draft objects are internal, steward-reviewable structures designed for exact
official-template export in later phases. No PDF/DOCX export or persistence here.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.grievance_template_schema import (
    EditBeforePrintRequirement,
    Step1UsageStatus,
    Step3Status,
    StepLevel,
)

# Current Phase 1.4B draft lifecycle statuses.
DraftStatus = Literal[
    "draft",
    "pending_required_fields",
    "ready_for_steward_review",
]

# Future phases: approved, exported_pdf, exported_docx (not implemented in 1.4B).

FieldProvenanceSource = Literal[
    "case_input",
    "report_input",
    "follow_up_input",
    "steward_override",
    "not_provided",
    "missing_required",
    "never_invent_protected",
]


class ExactTemplateFieldMapping(BaseModel):
    """Metadata tying a draft field to the official blank template layout."""

    field_id: str
    official_label: str
    page_number: int = Field(..., ge=1)
    section_name: str
    steward_editable: bool = True
    required_before_approval: bool = False
    protected_never_invent: bool = False
    optional_overflow_page: bool = False
    may_overflow_continuation: bool = False


class DraftFieldValue(BaseModel):
    """One editable field value within a grievance form draft."""

    field_id: str
    value: str | None = None
    source: FieldProvenanceSource = "not_provided"
    mapping: ExactTemplateFieldMapping
    is_missing_required: bool = False
    is_protected_never_invent: bool = False
    steward_edited: bool = False


class MissingRequiredField(BaseModel):
    """A required field that must be supplied before steward review/export."""

    field_id: str
    official_label: str
    page_number: int
    section_name: str
    reason: str = "Required before steward review and approval."


class ProtectedNeverInventWarning(BaseModel):
    """A protected field left blank because automated prefill must not invent it."""

    field_id: str
    official_label: str
    page_number: int
    reason: str = "Protected field — steward must supply; automated prefill must not invent."


class DraftPagePlan(BaseModel):
    """Which official template pages are included in this draft package."""

    included_pages: list[int] = Field(default_factory=list)
    default_pages: list[int] = Field(default_factory=list)
    optional_overflow_pages: list[int] = Field(default_factory=list)
    page_3_included: bool = False
    page_3_reason: str | None = None


class DraftValidationResult(BaseModel):
    """Outcome of validating a draft against required-field and never-invent rules."""

    status: DraftStatus
    missing_required_fields: list[MissingRequiredField] = Field(default_factory=list)
    protected_field_warnings: list[ProtectedNeverInventWarning] = Field(default_factory=list)
    ready_for_steward_review: bool = False


class GrievanceFormDraftCaseContext(BaseModel):
    """Saved-case workspace linkage — not a direct prefill source.

    Raw uploaded files and the steward's original concern/scenario belong here
    as case context. They inform analysis report generation but do **not** feed
    grievance form field prefill directly. Form drafting uses the reviewed
    analysis report and follow-up Q&A instead (see ``GrievanceFormDraftReportContent``).
    """

    case_uuid: str | None = Field(
        default=None,
        description="Saved GrievanceCase workspace UUID.",
    )
    case_id: int | None = Field(
        default=None,
        description="Internal database case id when persisted in later phases.",
    )
    report_version_id: int | None = Field(
        default=None,
        description="CaseReportVersion.id selected when Create Official Form Draft is clicked.",
    )
    report_version_number: int | None = Field(
        default=None,
        description="Denormalized report version number for steward-facing display.",
    )
    steward_concern_summary: str | None = Field(
        default=None,
        description=(
            "Original steward concern/scenario from case creation. "
            "Case context only — not used for direct form prefill."
        ),
    )
    source_upload_refs: list[str] = Field(
        default_factory=list,
        description=(
            "References to uploaded source documents. Case context only — "
            "not used for direct form prefill."
        ),
    )
    draft_version: int = Field(
        default=1,
        ge=1,
        description="Monotonic draft revision within a case form instance (future CRUD).",
    )
    approval_status: str | None = Field(
        default=None,
        description="Future steward approval status; not set by Phase 1.4B builder.",
    )
    export_status: str | None = Field(
        default=None,
        description="Future final PDF/DOCX export status; not set by Phase 1.4B builder.",
    )


class GrievanceFormDraftReportContent(BaseModel):
    """Selected/saved analysis report content used to draft the grievance form.

    Primary prefill source after the steward reviews the GrievanceHub Analysis
    Report. Future phases will populate this from ``CaseReportVersion.report_data``
    (facts, violations/articles, citations, issue framing, remedy, gaps).
    """

    grievant_name: str | None = None
    grievant_name_or_class: str | None = None
    installation_name: str | None = None
    installation_station_branch: str | None = None
    local_branch_number: str | None = None
    job_classification: str | None = None
    violation_national: str | None = None
    violation_articles_citations: str | None = None
    violation_local_mou: str | None = None
    violation_other_grounds: str | None = None
    facts_what_happened: str | None = None
    facts_datetime_location: str | None = None
    facts_continued: str | None = None
    facts_continued_page3: str | None = None
    corrective_action_requested: str | None = None
    step2_union_rep: str | None = None
    identified_facts: list[str] = Field(
        default_factory=list,
        description="Structured facts from the saved report (future adapter).",
    )
    key_violations: list[str] = Field(
        default_factory=list,
        description="Key contract violations/articles from the saved report.",
    )
    citations_summary: str | None = Field(
        default=None,
        description="Grounded citations block from the saved report.",
    )
    issue_framing: str | None = Field(
        default=None,
        description="Dispute/issue framing narrative from the saved report.",
    )
    recommended_remedy: str | None = Field(
        default=None,
        description="Recommended or requested remedy from the saved report.",
    )
    missing_information_gaps: list[str] = Field(
        default_factory=list,
        description="Missing facts or retrieval gaps disclosed in the report.",
    )
    lmou_indexed: bool = False


class GrievanceFormDraftFollowUpContext(BaseModel):
    """Relevant follow-up Q&A after report review — secondary drafting source.

    Follow-up answers may clarify facts, remedy, or steward corrections before
    the official form draft is created. Not a substitute for the saved report.
    """

    follow_up_message_ids: list[int] = Field(
        default_factory=list,
        description="CaseMessage ids for follow-up Q&A included in draft context.",
    )
    steward_clarifications: dict[str, str] = Field(
        default_factory=dict,
        description="Field-id overrides derived from reviewed follow-up Q&A.",
    )
    follow_up_summaries: list[str] = Field(
        default_factory=list,
        description="Optional summaries of relevant follow-up exchanges.",
    )


class GrievanceFormDraftBuildMetadata(BaseModel):
    """Non-sensitive build trace for debugging and future audit."""

    built_at: datetime
    builder_version: str = "phase_1_4b"
    template_id: str
    input_fields_provided: list[str] = Field(default_factory=list)
    steward_override_fields: list[str] = Field(default_factory=list)
    export_attempted: bool = False
    case_context: GrievanceFormDraftCaseContext | None = None
    report_content: GrievanceFormDraftReportContent | None = None
    follow_up_context: GrievanceFormDraftFollowUpContext | None = None
    linked_to_saved_case_workflow: bool = False
    prefill_derived_from_report: bool = False
    prefill_includes_follow_up: bool = False
    raw_uploads_used_for_prefill: bool = False


class GrievanceFormDraft(BaseModel):
    """Internal editable grievance form draft tied to a registered template.

    Created only after the steward reviews the analysis report (and optional
    follow-up Q&A). Prefill comes from ``report_content`` and ``follow_up_context``,
    not from raw uploads or the original concern text alone.
    """

    template_id: str
    template_display_name: str
    form_number: str
    local: str
    step_level: StepLevel
    step_1_usage_status: Step1UsageStatus
    step_3_status: Step3Status
    status: DraftStatus
    fields: dict[str, DraftFieldValue] = Field(default_factory=dict)
    field_mappings: list[ExactTemplateFieldMapping] = Field(default_factory=list)
    page_plan: DraftPagePlan = Field(default_factory=DraftPagePlan)
    validation: DraftValidationResult
    edit_before_print: EditBeforePrintRequirement = Field(
        default_factory=EditBeforePrintRequirement,
    )
    build_metadata: GrievanceFormDraftBuildMetadata
    case_context: GrievanceFormDraftCaseContext | None = None
    report_content: GrievanceFormDraftReportContent | None = None
    follow_up_context: GrievanceFormDraftFollowUpContext | None = None


class GrievanceFormDraftInput(BaseModel):
    """Inputs for Create Official Form Draft (Phase 1.4B foundation).

    Workflow order: case created → uploads/concern → analysis report generated →
    steward reviews report → optional follow-up Q&A → Create Official Form Draft.

    ``report_content`` is the primary prefill source. ``follow_up_context`` may
    supply steward clarifications from reviewed follow-up Q&A. ``case_context``
    links the draft to the saved workspace (uploads/concern are context only).
    """

    report_content: GrievanceFormDraftReportContent | None = None
    follow_up_context: GrievanceFormDraftFollowUpContext | None = None
    case_context: GrievanceFormDraftCaseContext | None = None
    steward_overrides: dict[str, str] = Field(default_factory=dict)
    request_page_3_overflow: bool = False
    facts_overflow_needs_page_3: bool = False
