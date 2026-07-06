"""Tests for grievance template registry foundation (Phase 1.4A)."""

from pathlib import Path

import pytest

from app.config import DATA_DIR, GENERATED_FORM_OUTPUT_DIR, GRIEVANCE_TEMPLATE_DIR, PROJECT_ROOT
from app.schemas.grievance_template_schema import GrievanceTemplateDefinition
from app.services.grievance_template_registry import (
    LOCAL_300_STANDARD_GRIEVANCE_FORM_79_1,
    edit_before_print_required,
    get_default_pages,
    get_grievance_template_by_id,
    get_generated_form_output_dir,
    get_optional_overflow_pages,
    get_protected_never_invent_fields,
    is_safe_generated_form_output_path,
    list_registered_grievance_templates,
    validate_template_assets,
)

LOCAL_300_TEMPLATE_ID = "local_300_standard_grievance_form_79_1"
LOCAL_300_PDF = (
    "data/templates/grievance/local_300/Standard_Grievance_Form-Local-300 (2).pdf"
)
LOCAL_300_JPGS = [
    "data/templates/grievance/local_300/IMG_5394.jpg",
    "data/templates/grievance/local_300/IMG_5395.jpg",
]


@pytest.fixture
def local_300_template() -> GrievanceTemplateDefinition:
    template = get_grievance_template_by_id(LOCAL_300_TEMPLATE_ID)
    assert template is not None
    return template


def test_local_300_template_is_registered(local_300_template):
    registered_ids = [item.template_id for item in list_registered_grievance_templates()]
    assert LOCAL_300_TEMPLATE_ID in registered_ids
    assert local_300_template.template_id == LOCAL_300_TEMPLATE_ID


def test_local_300_step_level_is_step_2_appeal(local_300_template):
    assert local_300_template.step_level == "step_2_appeal"


def test_local_300_step_1_usage_unconfirmed(local_300_template):
    assert (
        local_300_template.step_1_usage_status
        == "unconfirmed_pending_steward_confirmation"
    )


def test_local_300_step_3_deferred(local_300_template):
    assert local_300_template.step_3_status == "deferred_separate_form_required"


def test_local_300_preferred_pdf_path(local_300_template):
    assert local_300_template.preferred_blank_pdf == LOCAL_300_PDF


def test_local_300_reference_jpg_paths(local_300_template):
    assert local_300_template.reference_jpgs == LOCAL_300_JPGS


def test_local_300_default_pages(local_300_template):
    assert get_default_pages(local_300_template) == [1, 2]
    assert local_300_template.default_generated_pages == [1, 2]


def test_local_300_page_3_optional_overflow_only(local_300_template):
    assert get_optional_overflow_pages(local_300_template) == [3]
    page_3 = next(
        page for page in local_300_template.page_definitions if page.page_number == 3
    )
    assert page_3.optional_overflow_only is True
    assert page_3.required_in_default_package is False


def test_local_300_pdf_is_preferred_export_source(local_300_template):
    strategy = local_300_template.export_strategy
    assert strategy.preferred_exact_format_source == "pdf_blank"
    assert strategy.official_blank_pdf_is_master_for_approved_export is True
    assert strategy.steward_editable_draft_format == "html_jinja"


def test_local_300_jpgs_are_backup_reference_assets(local_300_template):
    assert local_300_template.export_strategy.reference_jpgs_role == "backup_reference_qa"
    assert "backup" in local_300_template.export_strategy.notes[3].lower()


def test_edit_before_print_requirement_represented(local_300_template):
    assert edit_before_print_required(local_300_template) is True
    rule = local_300_template.edit_before_print
    assert rule.generated_forms_are_drafts_first is True
    assert rule.steward_must_edit_all_fields_before_export is True
    assert rule.required_fields_validated_before_approval is True
    assert rule.steward_approval_required_before_pdf_docx_export is True
    assert rule.track_draft_vs_steward_edited_text is True
    assert rule.no_one_click_final_export_from_unreviewed_draft is True


def test_generated_output_path_not_inside_template_dir():
    output_dir = get_generated_form_output_dir()
    assert output_dir == GENERATED_FORM_OUTPUT_DIR
    assert GRIEVANCE_TEMPLATE_DIR not in output_dir.parents
    assert output_dir != GRIEVANCE_TEMPLATE_DIR
    assert "generated" in str(output_dir)
    assert is_safe_generated_form_output_path(output_dir / "case-uuid" / "draft.pdf") is True


def test_generated_output_rejected_under_templates_or_static():
    assert (
        is_safe_generated_form_output_path(
            GRIEVANCE_TEMPLATE_DIR / "local_300" / "filled.pdf"
        )
        is False
    )
    assert (
        is_safe_generated_form_output_path(
            PROJECT_ROOT / "app" / "static" / "forms" / "filled.pdf"
        )
        is False
    )
    assert (
        is_safe_generated_form_output_path(DATA_DIR / "templates" / "grievance" / "x.pdf")
        is False
    )


def test_protected_never_invent_fields_represented(local_300_template):
    protected = get_protected_never_invent_fields(local_300_template)
    assert "ssn_or_employee_id" in protected
    assert "branch_grievance_number" in protected
    assert "usps_number" in protected
    assert "step1_meeting_datetime" in protected
    assert "step1_decision_datetime" in protected
    assert "signature_branch_president_or_steward" in protected
    assert "violation_local_mou_when_unindexed" in protected
    assert len(protected) >= 10


def test_prefill_and_steward_input_fields_represented(local_300_template):
    assert "grievant_name" in local_300_template.prefilled_fields
    assert "corrective_action_requested" in local_300_template.prefilled_fields
    assert "form_date" in local_300_template.steward_input_fields
    assert "branch_grievance_number" in local_300_template.steward_input_fields
    assert "additional_sheet_attached" in local_300_template.steward_input_fields


def test_validate_template_assets_passes_for_committed_blank_files(local_300_template):
    result = validate_template_assets(local_300_template, project_root=PROJECT_ROOT)
    assert result.template_id == LOCAL_300_TEMPLATE_ID
    assert result.all_assets_present is True
    assert result.preferred_blank_pdf_exists is True
    assert result.reference_jpgs_exist == [True, True]
    assert result.missing_paths == []


def test_get_grievance_template_by_id_unknown_returns_none():
    assert get_grievance_template_by_id("nonexistent_template") is None


def test_registry_singleton_matches_constant():
    assert (
        get_grievance_template_by_id(LOCAL_300_TEMPLATE_ID)
        is LOCAL_300_STANDARD_GRIEVANCE_FORM_79_1
    )
