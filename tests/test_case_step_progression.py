"""Tests for case step progression foundation (Phase 1.4C)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.schemas.case_step_progression_schema import (
    CaseFormDraftHistoryInput,
    CaseStepOutcomeInput,
)
from app.schemas.grievance_form_draft_schema import (
    GrievanceFormDraftCaseContext,
    GrievanceFormDraftFollowUpContext,
    GrievanceFormDraftInput,
    GrievanceFormDraftReportContent,
)
from app.services.case_step_progression_service import (
    CaseStepProgressionError,
    CaseStepProgressionService,
)
from app.services.grievance_form_draft_builder import LOCAL_300_TEMPLATE_ID
from app.services.grievance_template_registry import list_registered_grievance_templates

SYNTHETIC_CASE_UUID = "00000000-0000-4000-8000-000000000101"
SYNTHETIC_REPORT_VERSION_ID = 9001
SYNTHETIC_REPORT_VERSION_NUMBER = 2
SYNTHETIC_FOLLOW_UP_IDS = [8801, 8802]


@pytest.fixture
def service() -> CaseStepProgressionService:
    svc = CaseStepProgressionService()
    yield svc
    svc.clear()


@pytest.fixture
def base_time() -> datetime:
    return datetime(2026, 7, 6, 12, 0, 0, tzinfo=UTC)


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
            report_version_id=SYNTHETIC_REPORT_VERSION_ID,
            report_version_number=SYNTHETIC_REPORT_VERSION_NUMBER,
        ),
        follow_up_context=GrievanceFormDraftFollowUpContext(
            follow_up_message_ids=SYNTHETIC_FOLLOW_UP_IDS,
            steward_clarifications={"facts_what_happened": "Synthetic follow-up clarification."},
        ),
    )


def test_step_1_stage_can_be_created(service, base_time):
    state = service.create_case_progression(
        SYNTHETIC_CASE_UUID,
        event_timestamp=base_time,
    )
    assert state.case_uuid == SYNTHETIC_CASE_UUID
    assert state.current_step_type == "step_1_initial"
    assert len(state.steps) == 1
    assert state.steps[0].step_type == "step_1_initial"
    assert state.steps[0].step_number == 1
    assert state.workspace_status == "open"


def test_step_1_outcome_can_be_added(service, base_time):
    service.create_case_progression(SYNTHETIC_CASE_UUID, event_timestamp=base_time)
    outcome, stage = service.add_step_outcome(
        SYNTHETIC_CASE_UUID,
        "step_1_initial",
        CaseStepOutcomeInput(
            outcome_type="denied",
            decision_summary="Synthetic Step 1 denial for testing.",
            decision_date="2026-07-01",
            decision_maker_name="Synthetic Supervisor",
            decision_maker_title="Plant Manager",
        ),
        event_timestamp=base_time + timedelta(hours=1),
    )
    assert outcome.outcome_type == "denied"
    assert outcome.decision_summary == "Synthetic Step 1 denial for testing."
    assert stage.outcomes[-1].outcome_id == outcome.outcome_id


def test_step_1_resolved_outcome_can_close_case_and_step(service, base_time):
    service.create_case_progression(SYNTHETIC_CASE_UUID, event_timestamp=base_time)
    service.add_step_outcome(
        SYNTHETIC_CASE_UUID,
        "step_1_initial",
        CaseStepOutcomeInput(
            outcome_type="resolved",
            decision_summary="Synthetic resolution at Step 1.",
            close_step=True,
            close_case=True,
        ),
        event_timestamp=base_time + timedelta(hours=2),
    )
    state = service.get_progression(SYNTHETIC_CASE_UUID)
    step_1 = state.steps[0]
    assert step_1.is_closed
    assert state.workspace_status == "closed"
    assert any(event.event_type == "case_closed" for event in state.timeline)


def test_closed_case_can_be_reopened(service, base_time):
    service.create_case_progression(SYNTHETIC_CASE_UUID, event_timestamp=base_time)
    service.add_step_outcome(
        SYNTHETIC_CASE_UUID,
        "step_1_initial",
        CaseStepOutcomeInput(
            outcome_type="closed_no_appeal",
            decision_summary="Synthetic close without appeal.",
            close_step=True,
            close_case=True,
        ),
        event_timestamp=base_time + timedelta(hours=1),
    )
    service.reopen_case(
        SYNTHETIC_CASE_UUID,
        event_timestamp=base_time + timedelta(days=1),
    )
    state = service.get_progression(SYNTHETIC_CASE_UUID)
    assert state.case_uuid == SYNTHETIC_CASE_UUID
    assert state.workspace_status == "open"
    assert state.reopened_at is not None


def test_closed_step_can_be_reopened(service, base_time):
    service.create_case_progression(SYNTHETIC_CASE_UUID, event_timestamp=base_time)
    service.close_step(
        SYNTHETIC_CASE_UUID,
        "step_1_initial",
        reason="resolved",
        event_timestamp=base_time + timedelta(hours=1),
    )
    service.reopen_step(
        SYNTHETIC_CASE_UUID,
        "step_1_initial",
        event_timestamp=base_time + timedelta(hours=2),
    )
    step_1 = service.get_progression(SYNTHETIC_CASE_UUID).steps[0]
    assert step_1.was_reopened
    assert not step_1.is_closed
    assert step_1.status == "reopened"


def test_reopen_adds_timestamped_history_event(service, base_time):
    service.create_case_progression(SYNTHETIC_CASE_UUID, event_timestamp=base_time)
    service.close_case(SYNTHETIC_CASE_UUID, event_timestamp=base_time + timedelta(hours=1))
    reopen_time = base_time + timedelta(days=2)
    service.reopen_case(SYNTHETIC_CASE_UUID, event_timestamp=reopen_time)

    state = service.get_progression(SYNTHETIC_CASE_UUID)
    reopen_events = [event for event in state.timeline if event.event_type == "case_reopened"]
    assert len(reopen_events) == 1
    assert reopen_events[0].event_timestamp == reopen_time


def test_reopen_preserves_prior_close_history(service, base_time):
    service.create_case_progression(SYNTHETIC_CASE_UUID, event_timestamp=base_time)
    close_time = base_time + timedelta(hours=3)
    service.close_case(SYNTHETIC_CASE_UUID, event_timestamp=close_time)
    service.reopen_case(
        SYNTHETIC_CASE_UUID,
        event_timestamp=base_time + timedelta(days=1),
    )

    state = service.get_progression(SYNTHETIC_CASE_UUID)
    close_events = [event for event in state.timeline if event.event_type == "case_closed"]
    assert len(close_events) == 1
    assert close_events[0].event_timestamp == close_time


def test_history_events_have_timestamps(service, base_time):
    state = service.create_case_progression(SYNTHETIC_CASE_UUID, event_timestamp=base_time)
    for event in state.timeline:
        assert event.event_timestamp is not None
        assert event.event_timestamp.tzinfo is not None


def test_history_sorts_oldest_first(service, base_time):
    service.create_case_progression(SYNTHETIC_CASE_UUID, event_timestamp=base_time)
    service.close_case(SYNTHETIC_CASE_UUID, event_timestamp=base_time + timedelta(hours=1))
    service.reopen_case(SYNTHETIC_CASE_UUID, event_timestamp=base_time + timedelta(hours=2))

    state = service.get_progression(SYNTHETIC_CASE_UUID)
    ordered = service.sort_timeline_oldest_first(state)
    timestamps = [event.event_timestamp for event in ordered]
    assert timestamps == sorted(timestamps)


def test_history_sorts_newest_first(service, base_time):
    service.create_case_progression(SYNTHETIC_CASE_UUID, event_timestamp=base_time)
    service.close_case(SYNTHETIC_CASE_UUID, event_timestamp=base_time + timedelta(hours=1))
    service.reopen_case(SYNTHETIC_CASE_UUID, event_timestamp=base_time + timedelta(hours=2))

    state = service.get_progression(SYNTHETIC_CASE_UUID)
    ordered = service.sort_timeline_newest_first(state)
    timestamps = [event.event_timestamp for event in ordered]
    assert timestamps == sorted(timestamps, reverse=True)


def test_same_case_id_preserved_after_reopen(service, base_time):
    service.create_case_progression(SYNTHETIC_CASE_UUID, event_timestamp=base_time)
    service.close_case(SYNTHETIC_CASE_UUID, event_timestamp=base_time + timedelta(hours=1))
    service.reopen_case(SYNTHETIC_CASE_UUID, event_timestamp=base_time + timedelta(hours=2))
    assert service.get_progression(SYNTHETIC_CASE_UUID).case_uuid == SYNTHETIC_CASE_UUID


def test_step_1_denied_appeal_transitions_to_step_2_same_case(service, base_time):
    service.create_case_progression(SYNTHETIC_CASE_UUID, event_timestamp=base_time)
    service.add_step_outcome(
        SYNTHETIC_CASE_UUID,
        "step_1_initial",
        CaseStepOutcomeInput(
            outcome_type="denied",
            decision_summary="Synthetic Step 1 denial.",
            appeal_to_next_step=True,
        ),
        event_timestamp=base_time + timedelta(hours=4),
    )
    state = service.get_progression(SYNTHETIC_CASE_UUID)
    assert state.case_uuid == SYNTHETIC_CASE_UUID
    assert len(state.steps) == 2
    assert state.current_step_type == "step_2_appeal"


def test_step_2_references_prior_step_1_outcome(service, base_time):
    service.create_case_progression(SYNTHETIC_CASE_UUID, event_timestamp=base_time)
    outcome, _ = service.add_step_outcome(
        SYNTHETIC_CASE_UUID,
        "step_1_initial",
        CaseStepOutcomeInput(
            outcome_type="denied",
            decision_summary="Synthetic Step 1 denial for Step 2 context.",
            appeal_to_next_step=True,
        ),
        event_timestamp=base_time + timedelta(hours=1),
    )
    state = service.get_progression(SYNTHETIC_CASE_UUID)
    step_2 = state.steps[1]
    assert step_2.appealed_from_prior_step == "step_1_initial"
    assert step_2.prior_step_outcome_id == outcome.outcome_id
    prior = service.get_prior_step_outcome(state, "step_1_initial")
    assert prior is not None
    assert prior.decision_summary == "Synthetic Step 1 denial for Step 2 context."


def test_step_2_can_reference_local_300_template(service, base_time):
    service.create_case_progression(SYNTHETIC_CASE_UUID, event_timestamp=base_time)
    service.appeal_to_next_step(
        SYNTHETIC_CASE_UUID,
        "step_1_initial",
        event_timestamp=base_time + timedelta(hours=1),
    )
    availability = service.get_step_template_availability("step_2_appeal")
    assert availability.template_available is True
    assert availability.template_id == LOCAL_300_TEMPLATE_ID

    step_2 = service.get_progression(SYNTHETIC_CASE_UUID).steps[1]
    assert step_2.template_id == LOCAL_300_TEMPLATE_ID


def test_step_1_template_not_available(service):
    availability = service.get_step_template_availability("step_1_initial")
    assert availability.template_available is False
    assert availability.template_id is None
    assert availability.availability_status == "unconfirmed_pending_steward_confirmation"
    assert service.list_buildable_template_ids_for_step("step_1_initial") == []


def test_step_3_template_not_available(service, base_time):
    availability = service.get_step_template_availability("step_3_appeal")
    assert availability.template_available is False
    assert availability.availability_status == "deferred_separate_form_required"
    assert service.list_buildable_template_ids_for_step("step_3_appeal") == []

    service.create_case_progression(SYNTHETIC_CASE_UUID, event_timestamp=base_time)
    service.appeal_to_next_step(
        SYNTHETIC_CASE_UUID,
        "step_1_initial",
        event_timestamp=base_time + timedelta(hours=1),
    )
    service.add_step_outcome(
        SYNTHETIC_CASE_UUID,
        "step_2_appeal",
        CaseStepOutcomeInput(
            outcome_type="denied",
            decision_summary="Synthetic Step 2 denial.",
            appeal_to_next_step=True,
        ),
        event_timestamp=base_time + timedelta(hours=2),
    )
    step_3 = service.get_progression(SYNTHETIC_CASE_UUID).steps[2]
    assert step_3.step_type == "step_3_appeal"
    assert step_3.template_availability == "deferred_separate_form_required"
    assert step_3.template_id is None


def test_draft_history_links_case_step_report_followups_template_version(service, base_time):
    service.create_case_progression(SYNTHETIC_CASE_UUID, event_timestamp=base_time)
    service.appeal_to_next_step(
        SYNTHETIC_CASE_UUID,
        "step_1_initial",
        event_timestamp=base_time + timedelta(hours=1),
    )
    draft_input = _minimal_report_input()
    _, history = service.build_step_form_draft(
        SYNTHETIC_CASE_UUID,
        "step_2_appeal",
        draft_input,
        event_timestamp=base_time + timedelta(hours=2),
    )
    assert history is not None
    assert history.case_uuid == SYNTHETIC_CASE_UUID
    assert history.step_type == "step_2_appeal"
    assert history.report_version_id == SYNTHETIC_REPORT_VERSION_ID
    assert history.report_version_number == SYNTHETIC_REPORT_VERSION_NUMBER
    assert history.follow_up_message_ids == SYNTHETIC_FOLLOW_UP_IDS
    assert history.template_id == LOCAL_300_TEMPLATE_ID
    assert history.draft_version == 1


def test_draft_creation_adds_timeline_event(service, base_time):
    service.create_case_progression(SYNTHETIC_CASE_UUID, event_timestamp=base_time)
    service.appeal_to_next_step(
        SYNTHETIC_CASE_UUID,
        "step_1_initial",
        event_timestamp=base_time + timedelta(hours=1),
    )
    service.build_step_form_draft(
        SYNTHETIC_CASE_UUID,
        "step_2_appeal",
        _minimal_report_input(),
        event_timestamp=base_time + timedelta(hours=2),
    )
    state = service.get_progression(SYNTHETIC_CASE_UUID)
    draft_events = [
        event for event in state.timeline if event.event_type == "form_draft_created"
    ]
    assert len(draft_events) == 1
    assert draft_events[0].references.form_draft_id is not None


def test_step_1_draft_build_is_rejected(service, base_time):
    service.create_case_progression(SYNTHETIC_CASE_UUID, event_timestamp=base_time)
    with pytest.raises(CaseStepProgressionError, match="No buildable official template"):
        service.build_step_form_draft(
            SYNTHETIC_CASE_UUID,
            "step_1_initial",
            _minimal_report_input(),
        )


def test_step_3_draft_build_is_rejected(service, base_time):
    service.create_case_progression(SYNTHETIC_CASE_UUID, event_timestamp=base_time)
    service.appeal_to_next_step(
        SYNTHETIC_CASE_UUID,
        "step_1_initial",
        event_timestamp=base_time + timedelta(hours=1),
    )
    service.appeal_to_next_step(
        SYNTHETIC_CASE_UUID,
        "step_2_appeal",
        event_timestamp=base_time + timedelta(hours=2),
    )
    with pytest.raises(CaseStepProgressionError, match="No buildable official template"):
        service.build_step_form_draft(
            SYNTHETIC_CASE_UUID,
            "step_3_appeal",
            _minimal_report_input(),
        )


def test_no_registered_step_1_or_step_3_templates():
    templates = list_registered_grievance_templates()
    assert templates
    assert all(template.step_level == "step_2_appeal" for template in templates)


def test_build_step_form_draft_does_not_export(service, base_time):
    service.create_case_progression(SYNTHETIC_CASE_UUID, event_timestamp=base_time)
    service.appeal_to_next_step(
        SYNTHETIC_CASE_UUID,
        "step_1_initial",
        event_timestamp=base_time + timedelta(hours=1),
    )
    draft, _ = service.build_step_form_draft(
        SYNTHETIC_CASE_UUID,
        "step_2_appeal",
        _minimal_report_input(),
    )
    assert draft.build_metadata.export_attempted is False


def test_record_form_draft_history_without_builder(service, base_time):
    from app.schemas.grievance_form_draft_schema import DraftValidationResult

    service.create_case_progression(SYNTHETIC_CASE_UUID, event_timestamp=base_time)
    record = service.record_form_draft_created(
        SYNTHETIC_CASE_UUID,
        CaseFormDraftHistoryInput(
            step_type="step_1_initial",
            template_id="synthetic_template_ref_only",
            draft_version=1,
            report_version_id=SYNTHETIC_REPORT_VERSION_ID,
            follow_up_message_ids=SYNTHETIC_FOLLOW_UP_IDS,
            validation=DraftValidationResult(
                status="pending_required_fields",
                ready_for_steward_review=False,
            ),
        ),
        event_timestamp=base_time + timedelta(hours=1),
    )
    assert record.template_id == "synthetic_template_ref_only"
    assert record.report_version_id == SYNTHETIC_REPORT_VERSION_ID
