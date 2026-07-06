"""Tests for grievance form draft builder (Phase 1.4B)."""

from __future__ import annotations

import pytest

from app.schemas.grievance_form_draft_schema import (
    GrievanceFormDraftCaseContext,
    GrievanceFormDraftFollowUpContext,
    GrievanceFormDraftInput,
    GrievanceFormDraftReportContent,
)
from app.services.grievance_form_draft_builder import (
    LOCAL_300_TEMPLATE_ID,
    build_grievance_form_draft,
    get_exact_template_field_mappings,
)
from app.services.grievance_template_registry import get_grievance_template_by_id

PROTECTED_NEVER_INVENT_FIELD_IDS = [
    "ssn_or_employee_id",
    "branch_grievance_number",
    "usps_number",
    "form_date",
    "step1_meeting_datetime",
    "step1_decision_datetime",
    "step2_designee_name_title",
    "signature_branch_president_or_steward",
]


def _minimal_report_content() -> GrievanceFormDraftReportContent:
    return GrievanceFormDraftReportContent(
        grievant_name="Jane Steward",
        installation_station_branch="Springfield Plant",
        local_branch_number="300",
        violation_articles_citations="Article 10.5",
        facts_what_happened="Management revoked approved annual leave without notice.",
        corrective_action_requested="Reinstate approved leave and pay any lost wages.",
        step2_union_rep="Alex Union Rep",
    )


def _minimal_prefill_input() -> GrievanceFormDraftInput:
    return GrievanceFormDraftInput(report_content=_minimal_report_content())


def _complete_required_input() -> GrievanceFormDraftInput:
    return GrievanceFormDraftInput(
        report_content=GrievanceFormDraftReportContent(
            grievant_name="Jane Steward",
            grievant_name_or_class="Jane Steward",
            installation_station_branch="Springfield Plant",
            local_branch_number="300",
            violation_articles_citations="Article 10.5",
            facts_what_happened="Management revoked approved annual leave without notice.",
            corrective_action_requested="Reinstate approved leave and pay any lost wages.",
            step2_union_rep="Alex Union Rep",
        ),
        steward_overrides={
            "form_date": "2026-07-01",
            "branch_grievance_number": "BR-2026-0042",
            "usps_number": "USPS-7788",
            "step2_designee_name_title": "District Manager, Springfield",
        },
    )


@pytest.fixture
def local_300_template():
    template = get_grievance_template_by_id(LOCAL_300_TEMPLATE_ID)
    assert template is not None
    return template


def test_draft_can_be_built_for_local_300_template():
    draft = build_grievance_form_draft(LOCAL_300_TEMPLATE_ID)
    assert draft.template_id == LOCAL_300_TEMPLATE_ID
    assert draft.fields
    assert draft.field_mappings


def test_draft_uses_step_2_appeal_template(local_300_template):
    draft = build_grievance_form_draft(LOCAL_300_TEMPLATE_ID)
    assert draft.step_level == "step_2_appeal"
    assert local_300_template.step_level == "step_2_appeal"


def test_step_1_usage_remains_unconfirmed(local_300_template):
    draft = build_grievance_form_draft(LOCAL_300_TEMPLATE_ID)
    assert (
        draft.step_1_usage_status
        == "unconfirmed_pending_steward_confirmation"
    )
    assert (
        local_300_template.step_1_usage_status
        == "unconfirmed_pending_steward_confirmation"
    )


def test_step_3_remains_deferred_separate_form_required(local_300_template):
    draft = build_grievance_form_draft(LOCAL_300_TEMPLATE_ID)
    assert draft.step_3_status == "deferred_separate_form_required"
    assert local_300_template.step_3_status == "deferred_separate_form_required"


def test_default_page_plan_is_pages_1_and_2():
    draft = build_grievance_form_draft(LOCAL_300_TEMPLATE_ID)
    assert draft.page_plan.default_pages == [1, 2]
    assert draft.page_plan.included_pages == [1, 2]


def test_page_3_not_included_by_default():
    draft = build_grievance_form_draft(LOCAL_300_TEMPLATE_ID)
    assert draft.page_plan.page_3_included is False
    assert 3 not in draft.page_plan.included_pages
    assert draft.page_plan.page_3_reason is None


@pytest.mark.parametrize(
    "overflow_kwargs,expected_reason",
    [
        ({"request_page_3_overflow": True}, "steward_requested_overflow_page"),
        ({"facts_overflow_needs_page_3": True}, "facts_contentions_overflow"),
        (
            {
                "report_content": GrievanceFormDraftReportContent(
                    facts_continued_page3="Additional union contentions continue here."
                )
            },
            "page_3_content_provided",
        ),
    ],
)
def test_page_3_included_only_when_overflow_requested_or_needed(
    overflow_kwargs,
    expected_reason,
):
    draft_input = GrievanceFormDraftInput(**overflow_kwargs)
    draft = build_grievance_form_draft(LOCAL_300_TEMPLATE_ID, draft_input)
    assert draft.page_plan.page_3_included is True
    assert draft.page_plan.included_pages == [1, 2, 3]
    assert draft.page_plan.page_3_reason == expected_reason


def test_safe_fields_prefilled_when_provided():
    draft_input = _minimal_prefill_input()
    draft = build_grievance_form_draft(LOCAL_300_TEMPLATE_ID, draft_input)

    assert draft.fields["grievant_name"].value == "Jane Steward"
    assert draft.fields["grievant_name"].source == "report_input"
    assert draft.fields["installation_station_branch"].value == "Springfield Plant"
    assert draft.fields["violation_articles_citations"].value == "Article 10.5"
    assert draft.fields["facts_what_happened"].value == (
        "Management revoked approved annual leave without notice."
    )
    assert draft.fields["corrective_action_requested"].value == (
        "Reinstate approved leave and pay any lost wages."
    )
    assert draft.fields["step2_union_rep"].value == "Alex Union Rep"


def test_protected_fields_not_invented_when_missing():
    draft = build_grievance_form_draft(LOCAL_300_TEMPLATE_ID, _minimal_prefill_input())

    for field_id in PROTECTED_NEVER_INVENT_FIELD_IDS:
        field = draft.fields[field_id]
        assert field.value is None, f"{field_id} should not be invented"
        assert field.is_protected_never_invent is True

    protected_ids = {item.field_id for item in draft.validation.protected_field_warnings}
    for field_id in PROTECTED_NEVER_INVENT_FIELD_IDS:
        assert field_id in protected_ids


def test_missing_required_fields_reported():
    draft = build_grievance_form_draft(LOCAL_300_TEMPLATE_ID, _minimal_prefill_input())

    missing_ids = {
        item.field_id for item in draft.validation.missing_required_fields
    }
    assert "form_date" in missing_ids
    assert "branch_grievance_number" in missing_ids
    assert "usps_number" in missing_ids
    assert "step2_designee_name_title" in missing_ids


def test_draft_status_pending_required_fields_when_missing():
    draft = build_grievance_form_draft(LOCAL_300_TEMPLATE_ID, _minimal_prefill_input())
    assert draft.status == "pending_required_fields"
    assert draft.validation.ready_for_steward_review is False


def test_draft_status_ready_for_steward_review_when_required_supplied():
    draft = build_grievance_form_draft(
        LOCAL_300_TEMPLATE_ID,
        _complete_required_input(),
    )
    assert draft.status == "ready_for_steward_review"
    assert draft.validation.ready_for_steward_review is True
    assert draft.validation.missing_required_fields == []


def test_field_provenance_tracked_for_prefill_and_missing():
    draft_input = _minimal_prefill_input()
    draft = build_grievance_form_draft(LOCAL_300_TEMPLATE_ID, draft_input)

    assert draft.fields["facts_what_happened"].source == "report_input"
    assert draft.fields["form_date"].source == "never_invent_protected"
    assert draft.fields["branch_grievance_number"].source == "never_invent_protected"


def test_steward_overrides_tracked_as_steward_supplied_provenance():
    draft = build_grievance_form_draft(
        LOCAL_300_TEMPLATE_ID,
        _complete_required_input(),
    )

    assert draft.fields["form_date"].value == "2026-07-01"
    assert draft.fields["form_date"].source == "steward_override"
    assert draft.fields["form_date"].steward_edited is True
    assert draft.fields["branch_grievance_number"].source == "steward_override"
    assert "form_date" in draft.build_metadata.steward_override_fields


def test_edit_before_print_requirement_carried_into_draft():
    draft = build_grievance_form_draft(LOCAL_300_TEMPLATE_ID)
    rule = draft.edit_before_print
    assert rule.required is True
    assert rule.generated_forms_are_drafts_first is True
    assert rule.steward_must_edit_all_fields_before_export is True
    assert rule.steward_approval_required_before_pdf_docx_export is True
    assert rule.no_one_click_final_export_from_unreviewed_draft is True


def test_exact_template_mapping_metadata_exists():
    mappings = get_exact_template_field_mappings(LOCAL_300_TEMPLATE_ID)
    assert mappings
    assert all(item.official_label for item in mappings)
    assert all(item.page_number >= 1 for item in mappings)
    assert all(item.section_name for item in mappings)

    draft = build_grievance_form_draft(LOCAL_300_TEMPLATE_ID)
    facts_field = draft.fields["facts_what_happened"]
    assert facts_field.mapping.official_label == "Facts — What Happened"
    assert facts_field.mapping.page_number == 1
    assert facts_field.mapping.section_name == "Facts and Union Contentions"
    assert facts_field.mapping.may_overflow_continuation is True


def test_page_3_field_marked_optional_overflow():
    mappings = get_exact_template_field_mappings(LOCAL_300_TEMPLATE_ID)
    page_3_fields = [item for item in mappings if item.page_number == 3]
    assert len(page_3_fields) == 1
    assert page_3_fields[0].field_id == "facts_continued_page3"
    assert page_3_fields[0].optional_overflow_page is True


def test_lmou_violation_not_prefilled_when_unindexed():
    draft_input = GrievanceFormDraftInput(
        report_content=GrievanceFormDraftReportContent(
            violation_local_mou="Local MOU Section 4.2",
            lmou_indexed=False,
        ),
    )
    draft = build_grievance_form_draft(LOCAL_300_TEMPLATE_ID, draft_input)
    assert draft.fields["violation_local_mou"].value is None
    assert draft.fields["violation_local_mou"].is_protected_never_invent is True


def test_lmou_violation_prefilled_when_indexed_and_provided():
    draft_input = GrievanceFormDraftInput(
        report_content=GrievanceFormDraftReportContent(
            violation_local_mou="Local MOU Section 4.2",
            lmou_indexed=True,
        ),
    )
    draft = build_grievance_form_draft(LOCAL_300_TEMPLATE_ID, draft_input)
    assert draft.fields["violation_local_mou"].value == "Local MOU Section 4.2"
    assert draft.fields["violation_local_mou"].source == "report_input"


def test_build_metadata_confirms_no_export_attempted():
    draft = build_grievance_form_draft(LOCAL_300_TEMPLATE_ID)
    assert draft.build_metadata.export_attempted is False


def test_unknown_template_raises():
    with pytest.raises(ValueError, match="Unknown grievance template"):
        build_grievance_form_draft("nonexistent_template")


def test_draft_fields_preserve_official_label_and_page_metadata():
    draft = build_grievance_form_draft(LOCAL_300_TEMPLATE_ID, _complete_required_input())
    designee = draft.fields["step2_designee_name_title"]
    assert designee.mapping.official_label == "Step 2 Designee (Name/Title)"
    assert designee.mapping.page_number == 1
    assert designee.mapping.section_name == "Step 2 Appeal Information"

    continued = draft.fields["facts_continued"]
    assert continued.mapping.page_number == 2
    assert continued.mapping.section_name.startswith("Facts and Union Contentions")


def test_draft_without_case_context_is_not_linked_to_saved_case_workflow():
    draft = build_grievance_form_draft(LOCAL_300_TEMPLATE_ID)
    assert draft.case_context is None
    assert draft.build_metadata.case_context is None
    assert draft.build_metadata.linked_to_saved_case_workflow is False


def test_optional_case_workflow_metadata_carried_into_draft():
    case_context = GrievanceFormDraftCaseContext(
        case_uuid="00000000-0000-4000-8000-000000000001",
        case_id=42,
        report_version_id=7,
        report_version_number=2,
        steward_concern_summary="Synthetic concern about revoked annual leave.",
        source_upload_refs=["upload-ref-schedule-001", "upload-ref-leave-002"],
        draft_version=1,
    )
    follow_up_context = GrievanceFormDraftFollowUpContext(
        follow_up_message_ids=[101, 102],
    )
    draft_input = GrievanceFormDraftInput(
        report_content=_minimal_report_content(),
        case_context=case_context,
        follow_up_context=follow_up_context,
    )
    draft = build_grievance_form_draft(LOCAL_300_TEMPLATE_ID, draft_input)

    assert draft.case_context == case_context
    assert draft.follow_up_context == follow_up_context
    assert draft.build_metadata.case_context == case_context
    assert draft.build_metadata.follow_up_context == follow_up_context
    assert draft.build_metadata.linked_to_saved_case_workflow is True
    assert draft.case_context.case_uuid == "00000000-0000-4000-8000-000000000001"
    assert draft.case_context.report_version_id == 7
    assert draft.case_context.report_version_number == 2
    assert draft.follow_up_context.follow_up_message_ids == [101, 102]
    assert draft.case_context.steward_concern_summary == (
        "Synthetic concern about revoked annual leave."
    )
    assert draft.case_context.source_upload_refs == [
        "upload-ref-schedule-001",
        "upload-ref-leave-002",
    ]
    assert draft.case_context.draft_version == 1
    assert draft.case_context.approval_status is None
    assert draft.case_context.export_status is None


def test_case_context_with_only_template_selection_is_not_linked():
    draft_input = GrievanceFormDraftInput(
        case_context=GrievanceFormDraftCaseContext(draft_version=1),
    )
    draft = build_grievance_form_draft(LOCAL_300_TEMPLATE_ID, draft_input)
    assert draft.case_context is not None
    assert draft.case_context.draft_version == 1
    assert draft.build_metadata.linked_to_saved_case_workflow is False


def test_case_context_alone_does_not_prefill_form_fields():
    draft_input = GrievanceFormDraftInput(
        case_context=GrievanceFormDraftCaseContext(
            case_uuid="00000000-0000-4000-8000-000000000002",
            steward_concern_summary="Raw concern text should not prefill the form.",
            source_upload_refs=["upload-ref-only-001"],
        ),
    )
    draft = build_grievance_form_draft(LOCAL_300_TEMPLATE_ID, draft_input)

    assert draft.fields["facts_what_happened"].value is None
    assert draft.fields["violation_articles_citations"].value is None
    assert draft.build_metadata.raw_uploads_used_for_prefill is False
    assert draft.build_metadata.prefill_derived_from_report is False


def test_report_content_is_primary_prefill_source():
    draft = build_grievance_form_draft(LOCAL_300_TEMPLATE_ID, _minimal_prefill_input())

    assert draft.report_content is not None
    assert draft.build_metadata.prefill_derived_from_report is True
    assert draft.fields["facts_what_happened"].source == "report_input"


def test_follow_up_clarifications_prefill_with_follow_up_provenance():
    draft_input = GrievanceFormDraftInput(
        report_content=GrievanceFormDraftReportContent(
            facts_what_happened="Initial report facts.",
        ),
        follow_up_context=GrievanceFormDraftFollowUpContext(
            follow_up_message_ids=[201],
            steward_clarifications={
                "corrective_action_requested": "Clarified remedy from follow-up Q&A.",
            },
        ),
    )
    draft = build_grievance_form_draft(LOCAL_300_TEMPLATE_ID, draft_input)

    assert draft.fields["corrective_action_requested"].value == (
        "Clarified remedy from follow-up Q&A."
    )
    assert draft.fields["corrective_action_requested"].source == "follow_up_input"
    assert draft.build_metadata.prefill_includes_follow_up is True


def test_report_structured_fields_can_prefill_form_fields():
    draft_input = GrievanceFormDraftInput(
        report_content=GrievanceFormDraftReportContent(
            key_violations=["Article 10.5", "Section 12.1"],
            identified_facts=["Leave was approved.", "Leave was revoked without notice."],
            recommended_remedy="Reinstate approved leave.",
            missing_information_gaps=["Exact revocation date unknown."],
        ),
    )
    draft = build_grievance_form_draft(LOCAL_300_TEMPLATE_ID, draft_input)

    assert draft.fields["violation_articles_citations"].value == "Article 10.5; Section 12.1"
    assert "Leave was approved." in draft.fields["facts_what_happened"].value
    assert draft.fields["corrective_action_requested"].value == "Reinstate approved leave."
