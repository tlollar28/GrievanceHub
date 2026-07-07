"""Database persistence tests for case step progression (Phase 1.4D).

Uses synthetic case ids and PostgreSQL when available. No OpenAI, no export, no
sensitive real grievance data.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, ProgrammingError

from app.database.models import (
    CaseFormDraftRecord,
    CaseReportVersion,
    CaseStep,
    CaseStepOutcome,
    CaseTimelineEventRecord,
    GrievanceCase,
)
from app.database.session import SessionLocal
from app.schemas.case_step_progression_schema import (
    CaseFormDraftHistoryInput,
    CaseStepOutcomeInput,
)
from app.schemas.grievance_form_draft_schema import (
    DraftValidationResult,
    GrievanceFormDraftCaseContext,
    GrievanceFormDraftFollowUpContext,
    GrievanceFormDraftInput,
    GrievanceFormDraftReportContent,
)
from app.services.case_step_progression_persistence_service import (
    CaseStepProgressionPersistenceService,
)
from app.services.grievance_form_draft_builder import LOCAL_300_TEMPLATE_ID
from app.services.grievance_template_registry import list_registered_grievance_templates

SYNTHETIC_CASE_UUID = "00000000-0000-4000-8000-000000000201"
SYNTHETIC_REPORT_VERSION_NUMBER = 2
SYNTHETIC_FOLLOW_UP_IDS = [8901, 8902]


def _db_available() -> bool:
    session = SessionLocal()
    try:
        session.execute(text("SELECT 1"))
        return True
    except OperationalError:
        return False
    finally:
        session.close()


def _tables_migrated(session) -> bool:
    try:
        session.query(CaseStep.id).limit(1).all()
        return True
    except ProgrammingError:
        session.rollback()
        return False


pytestmark = pytest.mark.skipif(
    not _db_available(),
    reason="PostgreSQL database not available for persistence tests",
)


@pytest.fixture
def db_session():
    session = SessionLocal()
    if not _tables_migrated(session):
        session.close()
        pytest.skip("Phase 1.4D migration not applied (run alembic upgrade head)")
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def persistence(db_session):
    return CaseStepProgressionPersistenceService(db_session)


@pytest.fixture
def synthetic_case(db_session):
    existing = (
        db_session.query(GrievanceCase)
        .filter(GrievanceCase.case_uuid == SYNTHETIC_CASE_UUID)
        .first()
    )
    if existing is not None:
        db_session.query(CaseTimelineEventRecord).filter(
            CaseTimelineEventRecord.case_id == existing.id
        ).delete(synchronize_session=False)
        db_session.query(CaseFormDraftRecord).filter(
            CaseFormDraftRecord.case_id == existing.id
        ).delete(synchronize_session=False)
        db_session.query(CaseStepOutcome).filter(
            CaseStepOutcome.case_id == existing.id
        ).delete(synchronize_session=False)
        db_session.query(CaseStep).filter(CaseStep.case_id == existing.id).delete(
            synchronize_session=False
        )
        db_session.query(CaseReportVersion).filter(
            CaseReportVersion.case_id == existing.id
        ).delete(synchronize_session=False)
        db_session.delete(existing)
        db_session.commit()

    now = datetime.utcnow()
    case = GrievanceCase(
        case_uuid=SYNTHETIC_CASE_UUID,
        title="Synthetic persistence test case",
        user_name="Synthetic Steward",
        local_number="300",
        initial_question="Synthetic question for Phase 1.4D persistence tests only.",
        known_facts={"synthetic": True},
        status="open",
        created_at=now,
        updated_at=now,
    )
    db_session.add(case)
    db_session.flush()
    yield case
    db_session.rollback()


@pytest.fixture
def synthetic_report_version(synthetic_case, db_session):
    row = CaseReportVersion(
        case_id=synthetic_case.id,
        version_number=SYNTHETIC_REPORT_VERSION_NUMBER,
        report_data={"synthetic": True, "title": "Synthetic GrievanceHub Analysis Report"},
        created_at=datetime.utcnow(),
    )
    db_session.add(row)
    db_session.flush()
    return row


def _minimal_report_input(report_version_id: int) -> GrievanceFormDraftInput:
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
            "branch_grievance_number": "SYN-PERSIST-001",
            "usps_number": "SYN-USPS-PERSIST-001",
            "step2_designee_name_title": "Synthetic District Manager",
        },
        case_context=GrievanceFormDraftCaseContext(
            case_uuid=SYNTHETIC_CASE_UUID,
            report_version_id=report_version_id,
            report_version_number=SYNTHETIC_REPORT_VERSION_NUMBER,
        ),
        follow_up_context=GrievanceFormDraftFollowUpContext(
            follow_up_message_ids=SYNTHETIC_FOLLOW_UP_IDS,
            steward_clarifications={"facts_what_happened": "Synthetic follow-up clarification."},
        ),
    )


@pytest.fixture
def base_time() -> datetime:
    return datetime(2026, 7, 6, 14, 0, 0, tzinfo=UTC)


def test_migration_tables_exist(db_session):
    assert _tables_migrated(db_session)


def test_create_case_step_record(persistence, synthetic_case, base_time):
    state = persistence.create_case_progression(
        SYNTHETIC_CASE_UUID,
        event_timestamp=base_time,
    )
    assert state.case_uuid == SYNTHETIC_CASE_UUID
    assert len(state.steps) == 1
    assert state.steps[0].step_type == "step_1_initial"


def test_step_1_outcome_persisted(persistence, synthetic_case, base_time):
    persistence.create_case_progression(SYNTHETIC_CASE_UUID, event_timestamp=base_time)
    outcome, stage = persistence.add_step_outcome(
        SYNTHETIC_CASE_UUID,
        "step_1_initial",
        CaseStepOutcomeInput(
            outcome_type="denied",
            decision_summary="Synthetic Step 1 denial for persistence testing.",
            decision_date="2026-07-01",
            decision_maker_name="Synthetic Supervisor",
            decision_maker_title="Plant Manager",
        ),
        event_timestamp=base_time + timedelta(hours=1),
    )
    assert outcome.outcome_type == "denied"
    assert stage.outcomes[-1].outcome_id == outcome.outcome_id


def test_step_1_resolved_close_persists_timeline(persistence, synthetic_case, base_time):
    persistence.create_case_progression(SYNTHETIC_CASE_UUID, event_timestamp=base_time)
    persistence.add_step_outcome(
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
    state = persistence.get_progression(SYNTHETIC_CASE_UUID)
    assert state.steps[0].is_closed
    assert state.workspace_status == "closed"
    assert any(event.event_type == "case_closed" for event in state.timeline)


def test_closed_case_reopen_persists(persistence, synthetic_case, base_time):
    persistence.create_case_progression(SYNTHETIC_CASE_UUID, event_timestamp=base_time)
    persistence.add_step_outcome(
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
    persistence.reopen_case(
        SYNTHETIC_CASE_UUID,
        event_timestamp=base_time + timedelta(days=1),
    )
    state = persistence.get_progression(SYNTHETIC_CASE_UUID)
    assert state.workspace_status == "open"
    assert state.reopened_at is not None


def test_reopen_preserves_close_history(persistence, synthetic_case, base_time):
    persistence.create_case_progression(SYNTHETIC_CASE_UUID, event_timestamp=base_time)
    close_time = base_time + timedelta(hours=3)
    persistence.close_case(SYNTHETIC_CASE_UUID, event_timestamp=close_time)
    persistence.reopen_case(
        SYNTHETIC_CASE_UUID,
        event_timestamp=base_time + timedelta(days=1),
    )
    close_events = [
        event
        for event in persistence.list_timeline_events(SYNTHETIC_CASE_UUID)
        if event.event_type == "case_closed"
    ]
    assert len(close_events) == 1
    assert close_events[0].event_timestamp == close_time.replace(tzinfo=UTC)


def test_step_1_denied_appeal_creates_step_2_same_case(persistence, synthetic_case, base_time):
    persistence.create_case_progression(SYNTHETIC_CASE_UUID, event_timestamp=base_time)
    persistence.add_step_outcome(
        SYNTHETIC_CASE_UUID,
        "step_1_initial",
        CaseStepOutcomeInput(
            outcome_type="denied",
            decision_summary="Synthetic Step 1 denial.",
            appeal_to_next_step=True,
        ),
        event_timestamp=base_time + timedelta(hours=4),
    )
    state = persistence.get_progression(SYNTHETIC_CASE_UUID)
    assert state.case_uuid == SYNTHETIC_CASE_UUID
    assert len(state.steps) == 2
    assert state.current_step_type == "step_2_appeal"


def test_step_2_references_step_1_outcome(persistence, synthetic_case, base_time):
    persistence.create_case_progression(SYNTHETIC_CASE_UUID, event_timestamp=base_time)
    outcome, _ = persistence.add_step_outcome(
        SYNTHETIC_CASE_UUID,
        "step_1_initial",
        CaseStepOutcomeInput(
            outcome_type="denied",
            decision_summary="Synthetic Step 1 denial for Step 2 context.",
            appeal_to_next_step=True,
        ),
        event_timestamp=base_time + timedelta(hours=1),
    )
    state = persistence.get_progression(SYNTHETIC_CASE_UUID)
    step_2 = state.steps[1]
    assert step_2.appealed_from_prior_step == "step_1_initial"
    assert step_2.prior_step_outcome_id == outcome.outcome_id


def test_step_2_references_local_300_template(persistence, synthetic_case, base_time):
    persistence.create_case_progression(SYNTHETIC_CASE_UUID, event_timestamp=base_time)
    persistence.appeal_to_next_step(
        SYNTHETIC_CASE_UUID,
        "step_1_initial",
        event_timestamp=base_time + timedelta(hours=1),
    )
    availability = persistence.get_step_template_availability("step_2_appeal")
    assert availability.template_available is True
    assert availability.template_id == LOCAL_300_TEMPLATE_ID
    step_2 = persistence.get_progression(SYNTHETIC_CASE_UUID).steps[1]
    assert step_2.template_id == LOCAL_300_TEMPLATE_ID


def test_step_1_template_not_available(persistence):
    availability = persistence.get_step_template_availability("step_1_initial")
    assert availability.template_available is False
    assert availability.template_id is None
    assert availability.availability_status == "unconfirmed_pending_steward_confirmation"


def test_step_3_template_not_available(persistence, synthetic_case, base_time):
    availability = persistence.get_step_template_availability("step_3_appeal")
    assert availability.template_available is False
    assert availability.availability_status == "deferred_separate_form_required"

    persistence.create_case_progression(SYNTHETIC_CASE_UUID, event_timestamp=base_time)
    persistence.appeal_to_next_step(
        SYNTHETIC_CASE_UUID,
        "step_1_initial",
        event_timestamp=base_time + timedelta(hours=1),
    )
    persistence.add_step_outcome(
        SYNTHETIC_CASE_UUID,
        "step_2_appeal",
        CaseStepOutcomeInput(
            outcome_type="denied",
            decision_summary="Synthetic Step 2 denial.",
            appeal_to_next_step=True,
        ),
        event_timestamp=base_time + timedelta(hours=2),
    )
    step_3 = persistence.get_progression(SYNTHETIC_CASE_UUID).steps[2]
    assert step_3.step_type == "step_3_appeal"
    assert step_3.template_availability == "deferred_separate_form_required"
    assert step_3.template_id is None


def test_timeline_oldest_first(persistence, synthetic_case, base_time):
    persistence.create_case_progression(SYNTHETIC_CASE_UUID, event_timestamp=base_time)
    persistence.close_case(
        SYNTHETIC_CASE_UUID,
        event_timestamp=base_time + timedelta(hours=1),
    )
    persistence.reopen_case(
        SYNTHETIC_CASE_UUID,
        event_timestamp=base_time + timedelta(hours=2),
    )
    ordered = persistence.list_timeline_events(SYNTHETIC_CASE_UUID, newest_first=False)
    timestamps = [event.event_timestamp for event in ordered]
    assert timestamps == sorted(timestamps)


def test_timeline_newest_first(persistence, synthetic_case, base_time):
    persistence.create_case_progression(SYNTHETIC_CASE_UUID, event_timestamp=base_time)
    persistence.close_case(
        SYNTHETIC_CASE_UUID,
        event_timestamp=base_time + timedelta(hours=1),
    )
    persistence.reopen_case(
        SYNTHETIC_CASE_UUID,
        event_timestamp=base_time + timedelta(hours=2),
    )
    ordered = persistence.list_timeline_events(SYNTHETIC_CASE_UUID, newest_first=True)
    timestamps = [event.event_timestamp for event in ordered]
    assert timestamps == sorted(timestamps, reverse=True)


def test_form_draft_record_links(
    persistence, synthetic_case, synthetic_report_version, base_time
):
    persistence.create_case_progression(SYNTHETIC_CASE_UUID, event_timestamp=base_time)
    persistence.appeal_to_next_step(
        SYNTHETIC_CASE_UUID,
        "step_1_initial",
        event_timestamp=base_time + timedelta(hours=1),
    )
    record = persistence.create_form_draft_record(
        SYNTHETIC_CASE_UUID,
        CaseFormDraftHistoryInput(
            step_type="step_2_appeal",
            template_id=LOCAL_300_TEMPLATE_ID,
            draft_version=1,
            report_version_id=synthetic_report_version.id,
            report_version_number=SYNTHETIC_REPORT_VERSION_NUMBER,
            follow_up_message_ids=SYNTHETIC_FOLLOW_UP_IDS,
            validation=DraftValidationResult(
                status="pending_required_fields",
                ready_for_steward_review=False,
            ),
        ),
        event_timestamp=base_time + timedelta(hours=2),
    )
    assert record.case_uuid == SYNTHETIC_CASE_UUID
    assert record.step_type == "step_2_appeal"
    assert record.report_version_id == synthetic_report_version.id
    assert record.follow_up_message_ids == SYNTHETIC_FOLLOW_UP_IDS
    assert record.template_id == LOCAL_300_TEMPLATE_ID
    assert record.draft_version == 1


def test_export_attempted_remains_false(persistence, synthetic_case, base_time, db_session):
    persistence.create_case_progression(SYNTHETIC_CASE_UUID, event_timestamp=base_time)
    persistence.appeal_to_next_step(
        SYNTHETIC_CASE_UUID,
        "step_1_initial",
        event_timestamp=base_time + timedelta(hours=1),
    )
    persistence.create_form_draft_record(
        SYNTHETIC_CASE_UUID,
        CaseFormDraftHistoryInput(
            step_type="step_2_appeal",
            template_id=LOCAL_300_TEMPLATE_ID,
            draft_version=1,
            validation=DraftValidationResult(
                status="ready_for_steward_review",
                ready_for_steward_review=True,
            ),
        ),
        event_timestamp=base_time + timedelta(hours=2),
    )
    row = (
        db_session.query(CaseFormDraftRecord)
        .filter(CaseFormDraftRecord.case_uuid == SYNTHETIC_CASE_UUID)
        .one()
    )
    assert row.export_attempted is False


def test_build_step_form_draft_persists_without_export(
    persistence, synthetic_case, synthetic_report_version, base_time
):
    persistence.create_case_progression(SYNTHETIC_CASE_UUID, event_timestamp=base_time)
    persistence.appeal_to_next_step(
        SYNTHETIC_CASE_UUID,
        "step_1_initial",
        event_timestamp=base_time + timedelta(hours=1),
    )
    draft, history = persistence.build_step_form_draft(
        SYNTHETIC_CASE_UUID,
        "step_2_appeal",
        _minimal_report_input(synthetic_report_version.id),
        event_timestamp=base_time + timedelta(hours=2),
    )
    assert draft.build_metadata.export_attempted is False
    assert history is not None
    assert history.template_id == LOCAL_300_TEMPLATE_ID


def test_no_registered_step_1_or_step_3_templates():
    templates = list_registered_grievance_templates()
    assert templates
    assert all(template.step_level == "step_2_appeal" for template in templates)
