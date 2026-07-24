"""Build editable grievance form drafts from registered templates (Phase 1.4B).

Deterministic draft assembly only — no OpenAI, no PDF/DOCX export, no persistence.

Prefill priority: steward overrides → reviewed follow-up clarifications → saved
analysis report content. Raw uploads and original steward concern are case
context only and must not drive field prefill directly.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.schemas.grievance_form_draft_schema import (
    DraftFieldValue,
    DraftPagePlan,
    DraftValidationResult,
    ExactTemplateFieldMapping,
    FieldProvenanceSource,
    GrievanceFormDraft,
    GrievanceFormDraftBuildMetadata,
    GrievanceFormDraftFollowUpContext,
    GrievanceFormDraftInput,
    GrievanceFormDraftReportContent,
    MissingRequiredField,
    ProtectedNeverInventWarning,
)
from app.schemas.grievance_template_schema import GrievanceTemplateDefinition
from app.services.grievance_template_registry import (
    LOCAL_300_STANDARD_GRIEVANCE_FORM_79_1,
    OFFICIAL_GRIEVANCE_WORKSHEET_STEP_1,
    OFFICIAL_STANDARD_GRIEVANCE_FORM_STEP_2,
    get_default_pages,
    get_grievance_template_by_id,
    get_optional_overflow_pages,
)

LOCAL_300_TEMPLATE_ID = LOCAL_300_STANDARD_GRIEVANCE_FORM_79_1.template_id
OFFICIAL_STEP_1_TEMPLATE_ID = OFFICIAL_GRIEVANCE_WORKSHEET_STEP_1.template_id
OFFICIAL_STEP_2_TEMPLATE_ID = OFFICIAL_STANDARD_GRIEVANCE_FORM_STEP_2.template_id

# Exact-template field mappings for Local 300 Form 79-1.
# Structured for future official PDF/DOCX placement — no coordinate mapping yet.
_LOCAL_300_FIELD_MAPPINGS: list[ExactTemplateFieldMapping] = [
    ExactTemplateFieldMapping(
        field_id="form_date",
        official_label="Date",
        page_number=1,
        section_name="Header / Filing Information",
        steward_editable=True,
        required_before_approval=True,
        protected_never_invent=True,
    ),
    ExactTemplateFieldMapping(
        field_id="branch_grievance_number",
        official_label="Branch Grievance Number",
        page_number=1,
        section_name="Header / Filing Information",
        steward_editable=True,
        required_before_approval=True,
        protected_never_invent=True,
    ),
    ExactTemplateFieldMapping(
        field_id="usps_number",
        official_label="USPS Number",
        page_number=1,
        section_name="Header / Filing Information",
        steward_editable=True,
        required_before_approval=True,
        protected_never_invent=True,
    ),
    ExactTemplateFieldMapping(
        field_id="installation_name",
        official_label="Installation Name",
        page_number=1,
        section_name="Installation / Branch",
        steward_editable=True,
        required_before_approval=False,
        protected_never_invent=False,
    ),
    ExactTemplateFieldMapping(
        field_id="installation_station_branch",
        official_label="Installation / Station / Branch",
        page_number=1,
        section_name="Installation / Branch",
        steward_editable=True,
        required_before_approval=True,
        protected_never_invent=False,
    ),
    ExactTemplateFieldMapping(
        field_id="local_branch_number",
        official_label="Local Branch Number",
        page_number=1,
        section_name="Installation / Branch",
        steward_editable=True,
        required_before_approval=False,
        protected_never_invent=False,
    ),
    ExactTemplateFieldMapping(
        field_id="installation_phone_office",
        official_label="Installation Phone (Office)",
        page_number=1,
        section_name="Installation / Branch",
        steward_editable=True,
        required_before_approval=False,
        protected_never_invent=True,
    ),
    ExactTemplateFieldMapping(
        field_id="grievant_name",
        official_label="Name of Grievant",
        page_number=1,
        section_name="Grievant Information",
        steward_editable=True,
        required_before_approval=False,
        protected_never_invent=False,
    ),
    ExactTemplateFieldMapping(
        field_id="grievant_name_or_class",
        official_label="Name of Grievant or Class",
        page_number=1,
        section_name="Grievant Information",
        steward_editable=True,
        required_before_approval=True,
        protected_never_invent=False,
    ),
    ExactTemplateFieldMapping(
        field_id="ssn_or_employee_id",
        official_label="SSN or Employee ID",
        page_number=1,
        section_name="Grievant Information",
        steward_editable=True,
        required_before_approval=False,
        protected_never_invent=True,
    ),
    ExactTemplateFieldMapping(
        field_id="job_classification",
        official_label="Job Classification",
        page_number=1,
        section_name="Grievant Information",
        steward_editable=True,
        required_before_approval=False,
        protected_never_invent=False,
    ),
    ExactTemplateFieldMapping(
        field_id="grievant_phone",
        official_label="Grievant Phone",
        page_number=1,
        section_name="Grievant Information",
        steward_editable=True,
        required_before_approval=False,
        protected_never_invent=True,
    ),
    ExactTemplateFieldMapping(
        field_id="home_address",
        official_label="Home Address",
        page_number=1,
        section_name="Grievant Information",
        steward_editable=True,
        required_before_approval=False,
        protected_never_invent=True,
    ),
    ExactTemplateFieldMapping(
        field_id="city",
        official_label="City",
        page_number=1,
        section_name="Grievant Information",
        steward_editable=True,
        required_before_approval=False,
        protected_never_invent=True,
    ),
    ExactTemplateFieldMapping(
        field_id="state",
        official_label="State",
        page_number=1,
        section_name="Grievant Information",
        steward_editable=True,
        required_before_approval=False,
        protected_never_invent=True,
    ),
    ExactTemplateFieldMapping(
        field_id="zip",
        official_label="ZIP",
        page_number=1,
        section_name="Grievant Information",
        steward_editable=True,
        required_before_approval=False,
        protected_never_invent=True,
    ),
    ExactTemplateFieldMapping(
        field_id="craft_seniority_date",
        official_label="Craft Seniority Date",
        page_number=1,
        section_name="Grievant Information",
        steward_editable=True,
        required_before_approval=False,
        protected_never_invent=True,
    ),
    ExactTemplateFieldMapping(
        field_id="service_seniority_date",
        official_label="Service Seniority Date",
        page_number=1,
        section_name="Grievant Information",
        steward_editable=True,
        required_before_approval=False,
        protected_never_invent=True,
    ),
    ExactTemplateFieldMapping(
        field_id="duty_hours",
        official_label="Duty Hours",
        page_number=1,
        section_name="Grievant Information",
        steward_editable=True,
        required_before_approval=False,
        protected_never_invent=True,
    ),
    ExactTemplateFieldMapping(
        field_id="veteran_status",
        official_label="Veteran Status",
        page_number=1,
        section_name="Grievant Information",
        steward_editable=True,
        required_before_approval=False,
        protected_never_invent=True,
    ),
    ExactTemplateFieldMapping(
        field_id="off_days",
        official_label="Off Days",
        page_number=1,
        section_name="Grievant Information",
        steward_editable=True,
        required_before_approval=False,
        protected_never_invent=True,
    ),
    ExactTemplateFieldMapping(
        field_id="employment_status",
        official_label="Employment Status",
        page_number=1,
        section_name="Grievant Information",
        steward_editable=True,
        required_before_approval=False,
        protected_never_invent=True,
    ),
    ExactTemplateFieldMapping(
        field_id="step1_meeting_datetime",
        official_label="Step 1 Meeting Date/Time",
        page_number=1,
        section_name="Step 1 Meeting Details",
        steward_editable=True,
        required_before_approval=False,
        protected_never_invent=True,
    ),
    ExactTemplateFieldMapping(
        field_id="step1_usps_representative",
        official_label="Step 1 USPS Representative",
        page_number=1,
        section_name="Step 1 Meeting Details",
        steward_editable=True,
        required_before_approval=False,
        protected_never_invent=True,
    ),
    ExactTemplateFieldMapping(
        field_id="step1_grievant_or_steward",
        official_label="Step 1 Grievant or Steward Participants",
        page_number=1,
        section_name="Step 1 Meeting Details",
        steward_editable=True,
        required_before_approval=False,
        protected_never_invent=True,
    ),
    ExactTemplateFieldMapping(
        field_id="step1_decision_datetime",
        official_label="Step 1 Decision Rendered Date/Time",
        page_number=1,
        section_name="Step 1 Decision Details",
        steward_editable=True,
        required_before_approval=False,
        protected_never_invent=True,
    ),
    ExactTemplateFieldMapping(
        field_id="step1_decision_by_name_title",
        official_label="Step 1 Decision By (Name/Title)",
        page_number=1,
        section_name="Step 1 Decision Details",
        steward_editable=True,
        required_before_approval=False,
        protected_never_invent=True,
    ),
    ExactTemplateFieldMapping(
        field_id="step1_supervisor_initials",
        official_label="Step 1 Supervisor Initials",
        page_number=1,
        section_name="Step 1 Decision Details",
        steward_editable=True,
        required_before_approval=False,
        protected_never_invent=True,
    ),
    ExactTemplateFieldMapping(
        field_id="step2_designee_name_title",
        official_label="Step 2 Designee (Name/Title)",
        page_number=1,
        section_name="Step 2 Appeal Information",
        steward_editable=True,
        required_before_approval=True,
        protected_never_invent=True,
    ),
    ExactTemplateFieldMapping(
        field_id="step2_union_rep",
        official_label="Union Representative",
        page_number=1,
        section_name="Step 2 Appeal Information",
        steward_editable=True,
        required_before_approval=False,
        protected_never_invent=False,
    ),
    ExactTemplateFieldMapping(
        field_id="union_business_address",
        official_label="Union Business Address",
        page_number=1,
        section_name="Union Representative",
        steward_editable=True,
        required_before_approval=False,
        protected_never_invent=True,
    ),
    ExactTemplateFieldMapping(
        field_id="union_rep_phone_office",
        official_label="Union Rep Phone (Office)",
        page_number=1,
        section_name="Union Representative",
        steward_editable=True,
        required_before_approval=False,
        protected_never_invent=True,
    ),
    ExactTemplateFieldMapping(
        field_id="union_rep_phone_other",
        official_label="Union Rep Phone (Other)",
        page_number=1,
        section_name="Union Representative",
        steward_editable=True,
        required_before_approval=False,
        protected_never_invent=True,
    ),
    ExactTemplateFieldMapping(
        field_id="violation_national",
        official_label="National Agreement Violation",
        page_number=1,
        section_name="Contract Provisions Violated",
        steward_editable=True,
        required_before_approval=False,
        protected_never_invent=False,
    ),
    ExactTemplateFieldMapping(
        field_id="violation_articles_citations",
        official_label="Articles / Citations Violated",
        page_number=1,
        section_name="Contract Provisions Violated",
        steward_editable=True,
        required_before_approval=True,
        protected_never_invent=False,
    ),
    ExactTemplateFieldMapping(
        field_id="violation_local_mou",
        official_label="Local MOU Violation",
        page_number=1,
        section_name="Contract Provisions Violated",
        steward_editable=True,
        required_before_approval=False,
        protected_never_invent=True,
    ),
    ExactTemplateFieldMapping(
        field_id="violation_other_grounds",
        official_label="Other Grounds",
        page_number=1,
        section_name="Contract Provisions Violated",
        steward_editable=True,
        required_before_approval=False,
        protected_never_invent=False,
    ),
    ExactTemplateFieldMapping(
        field_id="facts_what_happened",
        official_label="Facts — What Happened",
        page_number=1,
        section_name="Facts and Union Contentions",
        steward_editable=True,
        required_before_approval=True,
        protected_never_invent=False,
        may_overflow_continuation=True,
    ),
    ExactTemplateFieldMapping(
        field_id="facts_datetime_location",
        official_label="Facts — Date/Time/Location",
        page_number=1,
        section_name="Facts and Union Contentions",
        steward_editable=True,
        required_before_approval=False,
        protected_never_invent=False,
        may_overflow_continuation=True,
    ),
    ExactTemplateFieldMapping(
        field_id="corrective_action_requested",
        official_label="Corrective Action Requested",
        page_number=1,
        section_name="Remedy / Corrective Action",
        steward_editable=True,
        required_before_approval=True,
        protected_never_invent=False,
    ),
    ExactTemplateFieldMapping(
        field_id="additional_sheet_attached",
        official_label="Additional Sheet Attached",
        page_number=1,
        section_name="Continuation Pages",
        steward_editable=True,
        required_before_approval=False,
        protected_never_invent=True,
    ),
    ExactTemplateFieldMapping(
        field_id="facts_continued",
        official_label="Facts and Union Contentions (Continued)",
        page_number=2,
        section_name="Facts and Union Contentions (Continued)",
        steward_editable=True,
        required_before_approval=False,
        protected_never_invent=False,
        may_overflow_continuation=True,
    ),
    ExactTemplateFieldMapping(
        field_id="signature_branch_president_or_steward",
        official_label="Signature — Branch President or Steward",
        page_number=2,
        section_name="Signatures",
        steward_editable=True,
        required_before_approval=False,
        protected_never_invent=True,
    ),
    ExactTemplateFieldMapping(
        field_id="admin_mh_initials",
        official_label="Administration MH Initials",
        page_number=2,
        section_name="Administration",
        steward_editable=True,
        required_before_approval=False,
        protected_never_invent=True,
    ),
    ExactTemplateFieldMapping(
        field_id="admin_usps_initials",
        official_label="Administration USPS Initials",
        page_number=2,
        section_name="Administration",
        steward_editable=True,
        required_before_approval=False,
        protected_never_invent=True,
    ),
    ExactTemplateFieldMapping(
        field_id="facts_continued_page3",
        official_label="Facts and Union Contentions (Continued — Page 3)",
        page_number=3,
        section_name="Facts and Union Contentions (Continued — Optional Overflow)",
        steward_editable=True,
        required_before_approval=False,
        protected_never_invent=False,
        optional_overflow_page=True,
        may_overflow_continuation=True,
    ),
]

_LOCAL_300_MAPPING_BY_ID = {
    mapping.field_id: mapping for mapping in _LOCAL_300_FIELD_MAPPINGS
}


def _mapping_for_official_form(
    field_id: str,
    *,
    page_number: int = 1,
) -> ExactTemplateFieldMapping:
    return _LOCAL_300_MAPPING_BY_ID[field_id].model_copy(
        update={
            "page_number": page_number,
            "optional_overflow_page": False,
        }
    )


_OFFICIAL_STEP_1_FIELD_IDS = (
    "form_date",
    "branch_grievance_number",
    "grievant_name",
    "grievant_name_or_class",
    "ssn_or_employee_id",
    "job_classification",
    "grievant_phone",
    "home_address",
    "city",
    "state",
    "zip",
    "craft_seniority_date",
    "service_seniority_date",
    "duty_hours",
    "installation_name",
    "installation_station_branch",
    "veteran_status",
    "off_days",
    "employment_status",
    "violation_national",
    "violation_articles_citations",
    "violation_local_mou",
    "violation_other_grounds",
    "facts_what_happened",
    "corrective_action_requested",
    "additional_sheet_attached",
    "facts_continued",
)

_OFFICIAL_STEP_1_FIELD_MAPPINGS = [
    _mapping_for_official_form(
        field_id,
        page_number=2 if field_id == "facts_continued" else 1,
    )
    for field_id in _OFFICIAL_STEP_1_FIELD_IDS
] + [
    ExactTemplateFieldMapping(
        field_id="steward_name",
        official_label="Steward",
        page_number=1,
        section_name="Header / Filing Information",
        protected_never_invent=True,
    ),
    ExactTemplateFieldMapping(
        field_id="installation_city",
        official_label="Installation City",
        page_number=1,
        section_name="Installation",
        protected_never_invent=True,
    ),
    ExactTemplateFieldMapping(
        field_id="installation_state",
        official_label="Installation State",
        page_number=1,
        section_name="Installation",
        protected_never_invent=True,
    ),
    ExactTemplateFieldMapping(
        field_id="installation_zip",
        official_label="Installation ZIP",
        page_number=1,
        section_name="Installation",
        protected_never_invent=True,
    ),
    ExactTemplateFieldMapping(
        field_id="facts_dates",
        official_label="Facts of Grievance — Date(s)",
        page_number=1,
        section_name="Facts of Grievance",
        protected_never_invent=True,
    ),
    ExactTemplateFieldMapping(
        field_id="facts_time",
        official_label="Facts of Grievance — Time",
        page_number=1,
        section_name="Facts of Grievance",
        protected_never_invent=True,
    ),
    ExactTemplateFieldMapping(
        field_id="facts_location",
        official_label="Facts of Grievance — Location",
        page_number=1,
        section_name="Facts of Grievance",
        protected_never_invent=True,
    ),
    ExactTemplateFieldMapping(
        field_id="employee_level",
        official_label="Level",
        page_number=1,
        section_name="Employment Information",
        protected_never_invent=True,
    ),
    ExactTemplateFieldMapping(
        field_id="employee_step",
        official_label="Step",
        page_number=1,
        section_name="Employment Information",
        protected_never_invent=True,
    ),
]

_OFFICIAL_STEP_2_UNMAPPED_FIELD_IDS = {
    "step1_decision_datetime",
    "step1_supervisor_initials",
    "facts_continued",
    "signature_branch_president_or_steward",
    "admin_mh_initials",
    "admin_usps_initials",
    "facts_continued_page3",
}

_OFFICIAL_STEP_2_FIELD_MAPPINGS = [
    _mapping_for_official_form(mapping.field_id)
    for mapping in _LOCAL_300_FIELD_MAPPINGS
    if mapping.field_id not in _OFFICIAL_STEP_2_UNMAPPED_FIELD_IDS
] + [
    ExactTemplateFieldMapping(
        field_id="step1_decision_outcome",
        official_label="Step 1 Decision",
        page_number=1,
        section_name="Step 1 Decision Details",
        protected_never_invent=True,
    ),
    ExactTemplateFieldMapping(
        field_id="employee_level",
        official_label="Level",
        page_number=1,
        section_name="Employment Information",
        protected_never_invent=True,
    ),
    ExactTemplateFieldMapping(
        field_id="employee_step",
        official_label="Step",
        page_number=1,
        section_name="Employment Information",
        protected_never_invent=True,
    ),
]

_TEMPLATE_FIELD_MAPPINGS: dict[str, list[ExactTemplateFieldMapping]] = {
    LOCAL_300_TEMPLATE_ID: _LOCAL_300_FIELD_MAPPINGS,
    OFFICIAL_STEP_1_TEMPLATE_ID: _OFFICIAL_STEP_1_FIELD_MAPPINGS,
    OFFICIAL_STEP_2_TEMPLATE_ID: _OFFICIAL_STEP_2_FIELD_MAPPINGS,
}

# Report-content attributes used for safe prefill (primary drafting source).
_REPORT_PREFILL_FIELD_ATTRS: dict[str, str] = {
    "grievant_name": "grievant_name",
    "grievant_name_or_class": "grievant_name_or_class",
    "installation_name": "installation_name",
    "installation_station_branch": "installation_station_branch",
    "local_branch_number": "local_branch_number",
    "job_classification": "job_classification",
    "violation_national": "violation_national",
    "violation_articles_citations": "violation_articles_citations",
    "violation_local_mou": "violation_local_mou",
    "violation_other_grounds": "violation_other_grounds",
    "facts_what_happened": "facts_what_happened",
    "facts_datetime_location": "facts_datetime_location",
    "facts_continued": "facts_continued",
    "facts_continued_page3": "facts_continued_page3",
    "corrective_action_requested": "corrective_action_requested",
    "step2_union_rep": "step2_union_rep",
}


def get_exact_template_field_mappings(
    template_id: str,
) -> list[ExactTemplateFieldMapping]:
    """Return exact-template field mappings for a registered template."""
    return list(_TEMPLATE_FIELD_MAPPINGS.get(template_id, []))


def _normalize_value(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _report_content_from_input(
    draft_input: GrievanceFormDraftInput,
) -> GrievanceFormDraftReportContent:
    return draft_input.report_content or GrievanceFormDraftReportContent()


def _follow_up_context_from_input(
    draft_input: GrievanceFormDraftInput,
) -> GrievanceFormDraftFollowUpContext:
    return draft_input.follow_up_context or GrievanceFormDraftFollowUpContext()


def _resolve_input_value(
    field_id: str,
    draft_input: GrievanceFormDraftInput,
) -> tuple[str | None, FieldProvenanceSource | None]:
    override = _normalize_value(draft_input.steward_overrides.get(field_id))
    if override is not None:
        return override, "steward_override"

    follow_up = _follow_up_context_from_input(draft_input)
    follow_up_value = _normalize_value(follow_up.steward_clarifications.get(field_id))
    if follow_up_value is not None:
        return follow_up_value, "follow_up_input"

    report_content = _report_content_from_input(draft_input)

    if field_id == "violation_local_mou":
        if not report_content.lmou_indexed:
            return None, None
        return _normalize_value(report_content.violation_local_mou), "report_input"

    if field_id == "corrective_action_requested":
        remedy = _normalize_value(report_content.corrective_action_requested)
        if remedy is not None:
            return remedy, "report_input"
        return _normalize_value(report_content.recommended_remedy), "report_input"

    if field_id == "violation_articles_citations":
        direct = _normalize_value(report_content.violation_articles_citations)
        if direct is not None:
            return direct, "report_input"
        if report_content.key_violations:
            return "; ".join(report_content.key_violations), "report_input"
        return None, None

    if field_id == "facts_what_happened":
        direct = _normalize_value(report_content.facts_what_happened)
        if direct is not None:
            return direct, "report_input"
        if report_content.identified_facts:
            return " ".join(report_content.identified_facts), "report_input"
        framing = _normalize_value(report_content.issue_framing)
        if framing is not None:
            return framing, "report_input"
        return None, None

    attr = _REPORT_PREFILL_FIELD_ATTRS.get(field_id)
    if attr is None:
        return None, None
    return _normalize_value(getattr(report_content, attr)), "report_input"


def _build_page_plan(
    template: GrievanceTemplateDefinition,
    draft_input: GrievanceFormDraftInput,
) -> DraftPagePlan:
    default_pages = get_default_pages(template)
    overflow_pages = get_optional_overflow_pages(template)
    include_page_3 = (
        draft_input.request_page_3_overflow
        or draft_input.facts_overflow_needs_page_3
        or bool(
            _normalize_value(
                _report_content_from_input(draft_input).facts_continued_page3
            )
        )
    )
    included_pages = list(default_pages)
    page_3_reason: str | None = None
    if include_page_3 and 3 in overflow_pages:
        included_pages.append(3)
        if draft_input.request_page_3_overflow:
            page_3_reason = "steward_requested_overflow_page"
        elif draft_input.facts_overflow_needs_page_3:
            page_3_reason = "facts_contentions_overflow"
        else:
            page_3_reason = "page_3_content_provided"

    return DraftPagePlan(
        included_pages=included_pages,
        default_pages=default_pages,
        optional_overflow_pages=overflow_pages,
        page_3_included=3 in included_pages,
        page_3_reason=page_3_reason,
    )


def _validate_draft_fields(
    fields: dict[str, DraftFieldValue],
) -> DraftValidationResult:
    missing_required: list[MissingRequiredField] = []
    protected_warnings: list[ProtectedNeverInventWarning] = []

    for field in fields.values():
        mapping = field.mapping
        has_value = _normalize_value(field.value) is not None

        if mapping.protected_never_invent and not has_value:
            protected_warnings.append(
                ProtectedNeverInventWarning(
                    field_id=field.field_id,
                    official_label=mapping.official_label,
                    page_number=mapping.page_number,
                    reason=(
                        "Protected field left blank — automated prefill must not invent."
                    ),
                )
            )

        if mapping.required_before_approval and not has_value:
            missing_required.append(
                MissingRequiredField(
                    field_id=field.field_id,
                    official_label=mapping.official_label,
                    page_number=mapping.page_number,
                    section_name=mapping.section_name,
                )
            )

    if missing_required:
        status = "pending_required_fields"
        ready = False
    else:
        status = "ready_for_steward_review"
        ready = True

    return DraftValidationResult(
        status=status,
        missing_required_fields=missing_required,
        protected_field_warnings=protected_warnings,
        ready_for_steward_review=ready,
    )


def _build_field_values(
    template: GrievanceTemplateDefinition,
    mappings: list[ExactTemplateFieldMapping],
    draft_input: GrievanceFormDraftInput,
) -> dict[str, DraftFieldValue]:
    never_invent = set(template.never_invent_fields)
    prefilled = set(template.prefilled_fields)
    fields: dict[str, DraftFieldValue] = {}

    for mapping in mappings:
        field_id = mapping.field_id
        value, provenance = _resolve_input_value(field_id, draft_input)
        steward_edited = provenance == "steward_override"
        is_protected = mapping.protected_never_invent or field_id in never_invent

        if value is None:
            if is_protected:
                source: FieldProvenanceSource = "never_invent_protected"
            elif mapping.required_before_approval:
                source = "missing_required"
            else:
                source = "not_provided"
        else:
            if steward_edited:
                source = "steward_override"
            elif provenance == "follow_up_input":
                source = "follow_up_input"
            elif field_id in prefilled or provenance == "report_input":
                source = "report_input"
            else:
                source = provenance or "case_input"

        has_value = value is not None
        fields[field_id] = DraftFieldValue(
            field_id=field_id,
            value=value,
            source=source,
            mapping=mapping,
            is_missing_required=mapping.required_before_approval and not has_value,
            is_protected_never_invent=is_protected,
            steward_edited=steward_edited,
        )

    return fields


def build_grievance_form_draft(
    template_id: str,
    draft_input: GrievanceFormDraftInput | None = None,
) -> GrievanceFormDraft:
    """Build an editable grievance form draft from a registered template and input."""
    template = get_grievance_template_by_id(template_id)
    if template is None:
        raise ValueError(f"Unknown grievance template id: {template_id}")

    resolved_input = draft_input or GrievanceFormDraftInput()
    mappings = get_exact_template_field_mappings(template_id)
    if not mappings:
        raise ValueError(f"No exact-template field mappings registered for: {template_id}")

    fields = _build_field_values(template, mappings, resolved_input)
    page_plan = _build_page_plan(template, resolved_input)
    validation = _validate_draft_fields(fields)

    report_content = _report_content_from_input(resolved_input)
    follow_up_context = _follow_up_context_from_input(resolved_input)

    provided_inputs = [
        name
        for name, attr in _REPORT_PREFILL_FIELD_ATTRS.items()
        if _normalize_value(getattr(report_content, attr)) is not None
    ]
    if report_content.identified_facts:
        provided_inputs.append("identified_facts")
    if report_content.key_violations:
        provided_inputs.append("key_violations")
    if report_content.recommended_remedy:
        provided_inputs.append("recommended_remedy")

    prefill_from_report = bool(provided_inputs)
    prefill_from_follow_up = bool(follow_up_context.steward_clarifications)

    case_context = resolved_input.case_context
    linked_to_saved_case = case_context is not None and any(
        (
            case_context.case_uuid,
            case_context.case_id,
            case_context.report_version_id,
            case_context.report_version_number,
            case_context.steward_concern_summary,
            case_context.source_upload_refs,
        )
    )

    return GrievanceFormDraft(
        template_id=template.template_id,
        template_display_name=template.display_name,
        form_number=template.form_number,
        local=template.local,
        step_level=template.step_level,
        step_1_usage_status=template.step_1_usage_status,
        step_3_status=template.step_3_status,
        status=validation.status,
        fields=fields,
        field_mappings=mappings,
        page_plan=page_plan,
        validation=validation,
        edit_before_print=template.edit_before_print,
        case_context=case_context,
        report_content=report_content if resolved_input.report_content else None,
        follow_up_context=follow_up_context if resolved_input.follow_up_context else None,
        build_metadata=GrievanceFormDraftBuildMetadata(
            built_at=datetime.now(UTC),
            template_id=template.template_id,
            input_fields_provided=sorted(set(provided_inputs)),
            steward_override_fields=sorted(resolved_input.steward_overrides),
            export_attempted=False,
            case_context=case_context,
            report_content=report_content if resolved_input.report_content else None,
            follow_up_context=follow_up_context if resolved_input.follow_up_context else None,
            linked_to_saved_case_workflow=linked_to_saved_case,
            prefill_derived_from_report=prefill_from_report,
            prefill_includes_follow_up=prefill_from_follow_up,
            raw_uploads_used_for_prefill=False,
        ),
    )
