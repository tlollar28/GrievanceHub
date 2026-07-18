"""Official Save-and-Print artifact contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

ArtifactType = Literal["analysis_report", "grievance_form"]
PdfStatus = Literal["pending", "ready", "failed"]


class SaveAndPrintReportRequest(BaseModel):
    report_version_number: int | None = Field(
        default=None,
        description=(
            "Optional existing persisted report version. Prefer ``preview`` from "
            "Generate Analysis Report — versions are created only on Save."
        ),
    )
    preview: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Temporary analysis preview payload from Generate Analysis Report. "
            "When provided, Save creates the next CaseReportVersion then the artifact."
        ),
    )
    title: str | None = None
    saved_by: str | None = None
    grievance_step: str | None = None
    idempotency_key: str | None = Field(default=None, max_length=120)
    prepare_pdf: bool = True


class SaveAndPrintGrievanceRequest(BaseModel):
    template_id: str = Field(..., min_length=1)
    template_version: str | None = None
    grievance_step: str | None = None
    field_values: dict[str, Any] = Field(default_factory=dict)
    steward_override_field_ids: list[str] = Field(default_factory=list)
    missing_required_field_ids: list[str] = Field(default_factory=list)
    validation_status: str | None = None
    draft_status: str | None = "ready_for_steward_review"
    content_snapshot: dict[str, Any] | None = None
    working_draft_uuid: str | None = None
    title: str | None = None
    saved_by: str | None = None
    idempotency_key: str | None = Field(default=None, max_length=120)
    prepare_pdf: bool = True


class CaseSavedArtifactSummary(BaseModel):
    artifact_uuid: str
    case_uuid: str
    artifact_type: ArtifactType
    title: str
    version_number: int
    version_label: str
    grievance_step: str | None = None
    template_id: str | None = None
    template_version: str | None = None
    printed: bool = False
    pdf_status: PdfStatus | str = "pending"
    pdf_asset_uuid: str | None = None
    is_latest_official: bool = True
    saved_by: str | None = None
    saved_at: datetime
    source_report_version_number: int | None = None
    source_draft_record_uuid: str | None = None
    key_summary: dict[str, Any] | None = None
    retrieval: dict[str, str] | None = None


class CaseSavedArtifactDetail(CaseSavedArtifactSummary):
    content_json: dict[str, Any]
    pdf_download_path: str | None = None


class SaveAndPrintResponse(BaseModel):
    case_uuid: str
    status: Literal["saved", "saved_pdf_failed", "idempotent_replay"]
    message: str
    artifact: CaseSavedArtifactSummary
    print_ready: bool = False
    pdf_error: str | None = None
    export_path: str | None = None


class CaseSavedArtifactListResponse(BaseModel):
    case_uuid: str
    count: int
    artifacts: list[CaseSavedArtifactSummary]
    groups: dict[str, list[CaseSavedArtifactSummary]] = Field(
        default_factory=dict,
        description=(
            "Document-library grouping for the Artifacts section: "
            "analysis_reports, grievances, and optionally evidence/management_responses "
            "when included by the listing helper."
        ),
    )


class CaseHistoryItem(BaseModel):
    """Steward-facing case timeline item (bounded, artifact-aware)."""

    event_id: str
    event_type: str
    title: str
    details: str | None = None
    event_timestamp: datetime
    icon: str = "case"
    clickable: bool = False
    artifact_uuid: str | None = None
    artifact_type: str | None = None
    asset_uuid: str | None = None
    report_version_number: int | None = None
    draft_uuid: str | None = None
    retrieval_path: str | None = None
    context_path: str | None = None
    record_class: Literal["working_draft", "official_record", "lifecycle", "other"] = (
        "other"
    )
    display_label: str | None = None


class CaseHistoryResponse(BaseModel):
    case_uuid: str
    label: str = "Official Case Record"
    count: int
    order: Literal["oldest_first", "newest_first"] = "oldest_first"
    events: list[CaseHistoryItem]


class ArtifactCompareResponse(BaseModel):
    """Bounded comparison of two official artifacts on the same case."""

    case_uuid: str
    artifact_type: ArtifactType | str
    left: CaseSavedArtifactDetail
    right: CaseSavedArtifactDetail
    changed_summary_keys: list[str] = Field(default_factory=list)
    left_only_summary_keys: list[str] = Field(default_factory=list)
    right_only_summary_keys: list[str] = Field(default_factory=list)
    version_delta: int | None = None
    retrieval_note: str = (
        "Both official versions were retrieved automatically from the case record."
    )
