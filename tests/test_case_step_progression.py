"""Stateless grievance-step rules and progression architecture tests."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from app.schemas.grievance_form_draft_schema import (
    GrievanceFormDraftCaseContext,
    GrievanceFormDraftFollowUpContext,
    GrievanceFormDraftInput,
    GrievanceFormDraftReportContent,
)
from app.services.case_step_progression_errors import CaseStepProgressionError
from app.services.case_step_progression_rules import (
    build_step_form_draft,
    get_step_template_availability,
    list_buildable_template_ids_for_step,
    registered_templates_for_step,
)
from app.services.grievance_form_draft_builder import (
    OFFICIAL_STEP_1_TEMPLATE_ID,
    OFFICIAL_STEP_2_TEMPLATE_ID,
)

SYNTHETIC_CASE_UUID = "00000000-0000-4000-8000-000000000101"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _minimal_report_input() -> GrievanceFormDraftInput:
    return GrievanceFormDraftInput(
        report_content=GrievanceFormDraftReportContent(
            grievant_name_or_class="Synthetic Grievant",
            installation_station_branch="Synthetic Plant",
            local_branch_number="300",
            violation_articles_citations="Article 10.5",
            facts_what_happened="Synthetic management action for testing only.",
            corrective_action_requested="Synthetic remedy request.",
            step2_union_rep="Synthetic Union Rep",
        ),
        steward_overrides={
            "form_date": "2026-07-06",
            "branch_grievance_number": "SYN-001",
            "usps_number": "SYN-USPS-001",
            "step2_designee_name_title": "Synthetic District Manager",
        },
        case_context=GrievanceFormDraftCaseContext(
            case_uuid=SYNTHETIC_CASE_UUID,
            report_version_id=9001,
            report_version_number=2,
        ),
        follow_up_context=GrievanceFormDraftFollowUpContext(
            follow_up_message_ids=[8801, 8802],
            steward_clarifications={
                "facts_what_happened": "Synthetic follow-up clarification."
            },
        ),
    )


def test_step_1_and_step_2_official_templates_remain_available():
    step_1 = get_step_template_availability("step_1_initial")
    step_2 = get_step_template_availability("step_2_appeal")

    assert step_1.template_available is True
    assert step_1.template_id == OFFICIAL_STEP_1_TEMPLATE_ID
    assert step_2.template_available is True
    assert step_2.template_id == OFFICIAL_STEP_2_TEMPLATE_ID
    assert list_buildable_template_ids_for_step("step_1_initial") == [
        OFFICIAL_STEP_1_TEMPLATE_ID
    ]
    assert list_buildable_template_ids_for_step("step_2_appeal") == [
        OFFICIAL_STEP_2_TEMPLATE_ID
    ]


def test_step_3_remains_tracking_only_without_an_official_form():
    availability = get_step_template_availability("step_3_appeal")

    assert availability.template_available is False
    assert availability.template_id is None
    assert availability.availability_status == "deferred_separate_form_required"
    assert list_buildable_template_ids_for_step("step_3_appeal") == []
    assert registered_templates_for_step("step_3_appeal") == []


@pytest.mark.parametrize(
    ("step_type", "template_id"),
    [
        ("step_1_initial", OFFICIAL_STEP_1_TEMPLATE_ID),
        ("step_2_appeal", OFFICIAL_STEP_2_TEMPLATE_ID),
    ],
)
def test_stateless_draft_builder_preserves_supported_behavior(step_type, template_id):
    draft = build_step_form_draft(
        SYNTHETIC_CASE_UUID,
        step_type,
        _minimal_report_input(),
    )

    assert draft.template_id == template_id
    assert draft.step_level == step_type
    assert draft.case_context.case_uuid == SYNTHETIC_CASE_UUID
    assert draft.build_metadata.export_attempted is False


def test_stateless_draft_builder_rejects_step_3():
    with pytest.raises(
        CaseStepProgressionError,
        match="No buildable official template",
    ):
        build_step_form_draft(
            SYNTHETIC_CASE_UUID,
            "step_3_appeal",
            _minimal_report_input(),
        )


def test_dead_in_memory_progression_service_is_removed():
    dead_module = (
        REPOSITORY_ROOT
        / "app"
        / "services"
        / "case_step_progression_service.py"
    )
    rules_source = (
        REPOSITORY_ROOT
        / "app"
        / "services"
        / "case_step_progression_rules.py"
    ).read_text(encoding="utf-8")

    assert not dead_module.exists()
    assert "CaseStepProgressionService" not in rules_source
    assert "self._states" not in rules_source


def test_production_routers_do_not_depend_on_stateless_rules_or_dead_service():
    routes = REPOSITORY_ROOT / "app" / "api" / "routes"
    for route_path in routes.glob("*.py"):
        source = route_path.read_text(encoding="utf-8")
        assert "CaseStepProgressionService" not in source
        assert "case_step_progression_service" not in source
        assert "case_step_progression_rules" not in source


def test_case_workflow_service_remains_explicit_workflow_authority():
    workflow_source = (
        REPOSITORY_ROOT / "app" / "services" / "case_workflow_service.py"
    ).read_text(encoding="utf-8")
    case_routes = (
        REPOSITORY_ROOT / "app" / "api" / "routes" / "cases.py"
    ).read_text(encoding="utf-8")

    assert "class CaseWorkflowService" in workflow_source
    assert "def transition(" in workflow_source
    assert "CaseWorkflowService(db).get_state" in case_routes
    assert "CaseWorkflowService(db).transition" in case_routes


@pytest.mark.parametrize(
    "module_name",
    [
        "app.api.routes.cases",
        "app.services.case_service",
        "app.services.case_saved_artifact_service",
        "app.services.case_step_progression_persistence_service",
        "app.services.case_workspace_action_service",
        "app.services.saved_case_service",
    ],
)
def test_moved_helpers_have_complete_production_import_coverage(module_name):
    assert importlib.import_module(module_name) is not None
