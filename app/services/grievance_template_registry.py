"""Static grievance form template registry (Phase 1.4A foundation).

Registers blank official templates and exposes lookup/validation helpers.
No form generation, export, or database persistence in this phase.
"""

from __future__ import annotations

from pathlib import Path

from app.config import (
    FORBIDDEN_GENERATED_FORM_PATH_PREFIXES,
    GENERATED_FORM_OUTPUT_DIR,
    PROJECT_ROOT,
)
from app.schemas.grievance_template_schema import (
    EditBeforePrintRequirement,
    GrievanceTemplateDefinition,
    TemplateAssetValidationResult,
    TemplateExportStrategy,
    TemplatePageDefinition,
)

_LOCAL_300_PDF = (
    "app/assets/grievance_templates/local_300/Standard_Grievance_Form-Local-300 (2).pdf"
)
_LOCAL_300_JPG_PAGE_1 = "app/assets/grievance_templates/local_300/IMG_5394.jpg"
_LOCAL_300_JPG_PAGE_2 = "app/assets/grievance_templates/local_300/IMG_5395.jpg"
_OFFICIAL_STEP_1_PDF = (
    "app/assets/grievance_templates/official/step_1/"
    "Grievance_Worksheet_Step_1.pdf"
)
_OFFICIAL_STEP_2_PDF = (
    "app/assets/grievance_templates/official/step_2/"
    "Standard_Grievance_Form_Step_2.pdf"
)

_STANDARD_EDIT_BEFORE_PRINT = EditBeforePrintRequirement()

_LOCAL_300_NEVER_INVENT_FIELDS: list[str] = [
    "ssn_or_employee_id",
    "ein",
    "social_security_number",
    "form_date",
    "branch_grievance_number",
    "usps_number",
    "step1_meeting_datetime",
    "step1_usps_representative",
    "step1_grievant_or_steward",
    "step1_decision_datetime",
    "step1_decision_by_name_title",
    "step1_supervisor_initials",
    "step2_designee_name_title",
    "management_names",
    "signatures",
    "signature_branch_president_or_steward",
    "admin_mh_initials",
    "admin_usps_initials",
    "phone_numbers",
    "grievant_phone",
    "installation_phone_office",
    "union_rep_phone_office",
    "union_rep_phone_other",
    "home_address",
    "city",
    "state",
    "zip",
    "union_business_address",
    "craft_seniority_date",
    "service_seniority_date",
    "duty_hours",
    "veteran_status",
    "off_days",
    "employment_status",
    "violation_local_mou_when_unindexed",
    "all_dates",
]

_LOCAL_300_PREFILLED_FIELDS: list[str] = [
    "grievant_name",
    "grievant_name_or_class",
    "installation_name",
    "installation_station_branch",
    "local_branch_number",
    "violation_national",
    "violation_articles_citations",
    "facts_what_happened",
    "facts_datetime_location",
    "corrective_action_requested",
    "step2_union_rep",
    "job_classification",
]

_LOCAL_300_STEWARD_INPUT_FIELDS: list[str] = [
    "form_date",
    "branch_grievance_number",
    "usps_number",
    "step2_designee_name_title",
    "installation_phone_office",
    "union_business_address",
    "union_rep_phone_office",
    "union_rep_phone_other",
    "step1_meeting_datetime",
    "step1_usps_representative",
    "step1_grievant_or_steward",
    "step1_decision_datetime",
    "step1_decision_by_name_title",
    "step1_supervisor_initials",
    "grievant_phone",
    "home_address",
    "city",
    "state",
    "zip",
    "ssn_or_employee_id",
    "craft_seniority_date",
    "service_seniority_date",
    "duty_hours",
    "veteran_status",
    "off_days",
    "employment_status",
    "violation_local_mou",
    "violation_other_grounds",
    "additional_sheet_attached",
    "signature_branch_president_or_steward",
    "admin_mh_initials",
    "admin_usps_initials",
    "facts_continued",
    "facts_continued_page3",
]

LOCAL_300_STANDARD_GRIEVANCE_FORM_79_1 = GrievanceTemplateDefinition(
    template_id="local_300_standard_grievance_form_79_1",
    display_name="Local 300 Standard Grievance Form 79-1",
    local="Local 300",
    form_number="79-1",
    step_level="step_2_appeal",
    step_1_usage_status="unconfirmed_pending_steward_confirmation",
    step_3_status="deferred_separate_form_required",
    preferred_blank_pdf=_LOCAL_300_PDF,
    reference_jpgs=[_LOCAL_300_JPG_PAGE_1, _LOCAL_300_JPG_PAGE_2],
    page_definitions=[
        TemplatePageDefinition(
            page_number=1,
            label="Page 1",
            description="Main Step 2 appeal grievance form",
            required_in_default_package=True,
            optional_overflow_only=False,
        ),
        TemplatePageDefinition(
            page_number=2,
            label="Page 2",
            description="Facts and Union Contentions continued from Page 1",
            required_in_default_package=True,
            optional_overflow_only=False,
        ),
        TemplatePageDefinition(
            page_number=3,
            label="Page 3",
            description=(
                "Facts and Union Contentions continued from Page 2; "
                "optional overflow only"
            ),
            required_in_default_package=False,
            optional_overflow_only=True,
        ),
    ],
    default_generated_pages=[1, 2],
    optional_overflow_pages=[3],
    export_strategy=TemplateExportStrategy(
        preferred_exact_format_source="pdf_blank",
        steward_editable_draft_format="html_jinja",
        official_blank_pdf_is_master_for_approved_export=True,
        reference_jpgs_role="backup_reference_qa",
        notes=[
            "Use the PDF as the preferred exact-format source.",
            "Use HTML/Jinja or equivalent app-rendered draft form for steward-editable draft workflow.",
            "Use the official blank PDF as the master/reference for approved exact-format export later.",
            "Keep JPGs as backup/reference/QA assets.",
        ],
    ),
    edit_before_print=_STANDARD_EDIT_BEFORE_PRINT,
    prefilled_fields=_LOCAL_300_PREFILLED_FIELDS,
    steward_input_fields=_LOCAL_300_STEWARD_INPUT_FIELDS,
    never_invent_fields=_LOCAL_300_NEVER_INVENT_FIELDS,
)

OFFICIAL_GRIEVANCE_WORKSHEET_STEP_1 = GrievanceTemplateDefinition(
    template_id="official_grievance_worksheet_step_1",
    display_name="Official Grievance Worksheet — Step 1",
    local="NPMHU",
    form_number="Grievance Worksheet",
    step_level="step_1_initial",
    step_1_usage_status="confirmed",
    step_3_status="not_applicable",
    preferred_blank_pdf=_OFFICIAL_STEP_1_PDF,
    page_definitions=[
        TemplatePageDefinition(
            page_number=1,
            label="Step 1 Worksheet",
            description="Steward worksheet to prepare for the Step 1 meeting",
        ),
        TemplatePageDefinition(
            page_number=2,
            label="Facts Continuation",
            description="What Happened continuation from page 1",
        ),
    ],
    default_generated_pages=[1, 2],
    export_strategy=TemplateExportStrategy(
        preferred_exact_format_source="pdf_blank",
        steward_editable_draft_format="html_jinja",
        official_blank_pdf_is_master_for_approved_export=True,
        notes=[
            "Fill the official AcroForm fields directly.",
            "Preserve the original two-page worksheet layout.",
            "Protected fields remain blank until supplied by a steward.",
        ],
    ),
    edit_before_print=_STANDARD_EDIT_BEFORE_PRINT,
    prefilled_fields=_LOCAL_300_PREFILLED_FIELDS,
    steward_input_fields=sorted(
        set(_LOCAL_300_STEWARD_INPUT_FIELDS)
        | {
            "steward_name",
            "facts_dates",
            "facts_time",
            "facts_location",
            "installation_city",
            "installation_state",
            "installation_zip",
        }
    ),
    never_invent_fields=sorted(
        set(_LOCAL_300_NEVER_INVENT_FIELDS)
        | {
            "steward_name",
            "facts_dates",
            "facts_time",
            "facts_location",
            "installation_city",
            "installation_state",
            "installation_zip",
        }
    ),
)

OFFICIAL_STANDARD_GRIEVANCE_FORM_STEP_2 = GrievanceTemplateDefinition(
    template_id="official_standard_grievance_form_step_2",
    display_name="Official Standard Grievance Form — Step 2",
    local="NPMHU",
    form_number="Standard Grievance Form",
    step_level="step_2_appeal",
    step_1_usage_status="not_applicable",
    step_3_status="deferred_separate_form_required",
    preferred_blank_pdf=_OFFICIAL_STEP_2_PDF,
    page_definitions=[
        TemplatePageDefinition(
            page_number=1,
            label="Step 2 Appeal",
            description="Official standard form used to appeal a grievance to Step 2",
        ),
    ],
    default_generated_pages=[1],
    export_strategy=TemplateExportStrategy(
        preferred_exact_format_source="pdf_blank",
        steward_editable_draft_format="html_jinja",
        official_blank_pdf_is_master_for_approved_export=True,
        notes=[
            "Fill the official AcroForm fields directly.",
            "Preserve the original one-page Step 2 appeal layout.",
            "Protected fields remain blank until supplied by a steward.",
        ],
    ),
    edit_before_print=_STANDARD_EDIT_BEFORE_PRINT,
    prefilled_fields=_LOCAL_300_PREFILLED_FIELDS,
    steward_input_fields=_LOCAL_300_STEWARD_INPUT_FIELDS,
    never_invent_fields=_LOCAL_300_NEVER_INVENT_FIELDS,
)

_REGISTERED_TEMPLATES: dict[str, GrievanceTemplateDefinition] = {
    LOCAL_300_STANDARD_GRIEVANCE_FORM_79_1.template_id: LOCAL_300_STANDARD_GRIEVANCE_FORM_79_1,
    OFFICIAL_GRIEVANCE_WORKSHEET_STEP_1.template_id: OFFICIAL_GRIEVANCE_WORKSHEET_STEP_1,
    OFFICIAL_STANDARD_GRIEVANCE_FORM_STEP_2.template_id: OFFICIAL_STANDARD_GRIEVANCE_FORM_STEP_2,
}


def list_registered_grievance_templates() -> list[GrievanceTemplateDefinition]:
    """Return all registered grievance templates in stable template_id order."""
    return [
        _REGISTERED_TEMPLATES[template_id]
        for template_id in sorted(_REGISTERED_TEMPLATES)
    ]


def get_grievance_template_by_id(template_id: str) -> GrievanceTemplateDefinition | None:
    """Return one registered template by id, or None if not registered."""
    return _REGISTERED_TEMPLATES.get(template_id)


def get_default_pages(template: GrievanceTemplateDefinition) -> list[int]:
    """Return page numbers included in the default generated package."""
    return list(template.default_generated_pages)


def get_optional_overflow_pages(template: GrievanceTemplateDefinition) -> list[int]:
    """Return page numbers that are optional overflow-only continuations."""
    return list(template.optional_overflow_pages)


def get_protected_never_invent_fields(template: GrievanceTemplateDefinition) -> list[str]:
    """Return field ids that must never be invented by automated prefill."""
    return list(template.never_invent_fields)


def edit_before_print_required(template: GrievanceTemplateDefinition) -> bool:
    """Return whether steward edit-before-print is required for this template."""
    return template.edit_before_print.required


def resolve_repo_relative_path(relative_path: str, *, project_root: Path | None = None) -> Path:
    """Resolve a repo-relative asset path to an absolute filesystem path."""
    root = project_root or PROJECT_ROOT
    return (root / relative_path).resolve()


def validate_template_assets(
    template: GrievanceTemplateDefinition,
    *,
    project_root: Path | None = None,
) -> TemplateAssetValidationResult:
    """Verify that registered blank PDF and reference JPG paths exist."""
    root = project_root or PROJECT_ROOT
    missing_paths: list[str] = []

    pdf_path = resolve_repo_relative_path(template.preferred_blank_pdf, project_root=root)
    pdf_exists = pdf_path.is_file()
    if not pdf_exists:
        missing_paths.append(template.preferred_blank_pdf)

    jpg_exists: list[bool] = []
    for jpg_relative in template.reference_jpgs:
        jpg_path = resolve_repo_relative_path(jpg_relative, project_root=root)
        exists = jpg_path.is_file()
        jpg_exists.append(exists)
        if not exists:
            missing_paths.append(jpg_relative)

    return TemplateAssetValidationResult(
        template_id=template.template_id,
        all_assets_present=not missing_paths,
        preferred_blank_pdf_exists=pdf_exists,
        reference_jpgs_exist=jpg_exists,
        missing_paths=missing_paths,
    )


def is_safe_generated_form_output_path(path: Path | str) -> bool:
    """Return False when a path would write generated forms into protected template/static dirs."""
    candidate = Path(path).resolve()
    for prefix in FORBIDDEN_GENERATED_FORM_PATH_PREFIXES:
        forbidden_root = prefix.resolve()
        try:
            candidate.relative_to(forbidden_root)
        except ValueError:
            continue
        return False
    return True


def get_generated_form_output_dir() -> Path:
    """Return the configured directory for generated filled grievance forms."""
    return GENERATED_FORM_OUTPUT_DIR
