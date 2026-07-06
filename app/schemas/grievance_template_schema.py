"""Pydantic models for grievance form template registry (Phase 1.4A foundation)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


StepLevel = Literal["step_1_initial", "step_2_appeal", "step_3_appeal"]

Step1UsageStatus = Literal[
    "confirmed",
    "unconfirmed_pending_steward_confirmation",
    "not_applicable",
]

Step3Status = Literal[
    "available",
    "deferred_separate_form_required",
    "not_applicable",
]


class TemplatePageDefinition(BaseModel):
    """One page of a multi-page grievance form template."""

    page_number: int = Field(..., ge=1)
    label: str
    description: str
    required_in_default_package: bool = True
    optional_overflow_only: bool = False


class TemplateExportStrategy(BaseModel):
    """How blank assets and export formats relate for a registered template."""

    preferred_exact_format_source: Literal["pdf_blank", "docx_blank", "html_jinja"] = "pdf_blank"
    steward_editable_draft_format: Literal["html_jinja", "docx_blank"] = "html_jinja"
    official_blank_pdf_is_master_for_approved_export: bool = True
    reference_jpgs_role: Literal["backup_reference_qa"] = "backup_reference_qa"
    notes: list[str] = Field(default_factory=list)


class EditBeforePrintRequirement(BaseModel):
    """Steward must review and approve before any final export."""

    required: bool = True
    generated_forms_are_drafts_first: bool = True
    steward_must_edit_all_fields_before_export: bool = True
    required_fields_validated_before_approval: bool = True
    steward_approval_required_before_pdf_docx_export: bool = True
    track_draft_vs_steward_edited_text: bool = True
    no_one_click_final_export_from_unreviewed_draft: bool = True


class GrievanceTemplateDefinition(BaseModel):
    """Static registry entry for one official grievance form template."""

    template_id: str
    display_name: str
    local: str
    form_number: str
    step_level: StepLevel
    step_1_usage_status: Step1UsageStatus
    step_3_status: Step3Status
    preferred_blank_pdf: str = Field(
        description="Repo-relative path to the preferred blank PDF asset.",
    )
    reference_jpgs: list[str] = Field(
        default_factory=list,
        description="Repo-relative paths to backup/reference JPG scans.",
    )
    page_definitions: list[TemplatePageDefinition] = Field(default_factory=list)
    default_generated_pages: list[int] = Field(default_factory=list)
    optional_overflow_pages: list[int] = Field(default_factory=list)
    export_strategy: TemplateExportStrategy = Field(default_factory=TemplateExportStrategy)
    edit_before_print: EditBeforePrintRequirement = Field(
        default_factory=EditBeforePrintRequirement,
    )
    prefilled_fields: list[str] = Field(default_factory=list)
    steward_input_fields: list[str] = Field(default_factory=list)
    never_invent_fields: list[str] = Field(default_factory=list)


class TemplateAssetValidationResult(BaseModel):
    """Outcome of checking that registered template asset paths exist on disk."""

    template_id: str
    all_assets_present: bool
    preferred_blank_pdf_exists: bool
    reference_jpgs_exist: list[bool]
    missing_paths: list[str] = Field(default_factory=list)
