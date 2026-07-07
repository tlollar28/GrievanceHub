"""Service tests for saved case list/open/reopen/timeline (Phase 1.4E).

Uses synthetic PostgreSQL data when available. No OpenAI, no export, no sensitive data.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, ProgrammingError

from app.database.models import (
    CaseStep,
    CaseStepOutcome,
    CaseTimelineEventRecord,
    GrievanceCase,
)
from app.database.session import SessionLocal
from app.schemas.case_step_progression_schema import CaseStepOutcomeInput
from app.services.case_step_progression_persistence_service import (
    CaseStepProgressionPersistenceService,
)
from app.services.saved_case_service import SavedCaseService

SYNTHETIC_CASE_UUID = "00000000-0000-4000-8000-000000000401"


def _db_available() -> bool:
    session = SessionLocal()
    try:
        session.execute(text("SELECT 1"))
        return True
    except OperationalError:
        return False
    finally:
        session.close()


def _tables_ready(session) -> bool:
    try:
        session.query(CaseStep.id).limit(1).all()
        return True
    except ProgrammingError:
        session.rollback()
        return False


pytestmark = pytest.mark.skipif(
    not _db_available(),
    reason="PostgreSQL database not available for saved case service tests",
)


@pytest.fixture
def db_session():
    session = SessionLocal()
    if not _tables_ready(session):
        session.close()
        pytest.skip("Phase 1.4D migration not applied")
    try:
        yield session
    finally:
        session.rollback()
        session.close()


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
        db_session.query(CaseStepOutcome).filter(
            CaseStepOutcome.case_id == existing.id
        ).delete(synchronize_session=False)
        db_session.query(CaseStep).filter(CaseStep.case_id == existing.id).delete(
            synchronize_session=False
        )
        db_session.delete(existing)
        db_session.commit()

    now = datetime.utcnow()
    case = GrievanceCase(
        case_uuid=SYNTHETIC_CASE_UUID,
        title="Synthetic saved case service test",
        user_name="Synthetic Steward",
        local_number="300",
        initial_question="Synthetic question for saved case service tests.",
        known_facts={"grievant_name": "Synthetic Grievant"},
        status="open",
        created_at=now,
        updated_at=now,
    )
    db_session.add(case)
    db_session.flush()
    yield case
    db_session.rollback()


@pytest.fixture
def base_time() -> datetime:
    return datetime(2026, 7, 6, 16, 0, 0, tzinfo=UTC)


@pytest.fixture
def progression(db_session, synthetic_case, base_time):
    service = CaseStepProgressionPersistenceService(db_session)
    return service.create_case_progression(
        SYNTHETIC_CASE_UUID,
        event_timestamp=base_time,
    )


def test_saved_cases_list_newest_first(db_session, synthetic_case, progression, base_time):
    persistence = CaseStepProgressionPersistenceService(db_session)
    persistence.close_case(
        SYNTHETIC_CASE_UUID,
        event_timestamp=base_time + timedelta(hours=1),
    )

    case_b_uuid = "00000000-0000-4000-8000-000000000402"
    existing_b = (
        db_session.query(GrievanceCase)
        .filter(GrievanceCase.case_uuid == case_b_uuid)
        .first()
    )
    if existing_b is not None:
        db_session.delete(existing_b)
        db_session.flush()
    older = GrievanceCase(
        case_uuid=case_b_uuid,
        title="Older synthetic case",
        initial_question="Older synthetic case question.",
        status="open",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow() - timedelta(days=2),
    )
    db_session.add(older)
    db_session.commit()

    result = SavedCaseService.list_saved_cases(db_session, newest_first=True)
    uuids = [item.case_uuid for item in result.cases]
    assert SYNTHETIC_CASE_UUID in uuids
    assert case_b_uuid in uuids
    assert result.order == "newest_first"


def test_saved_cases_list_oldest_first(db_session, synthetic_case, progression):
    result = SavedCaseService.list_saved_cases(db_session, newest_first=False)
    assert result.order == "oldest_first"
    timestamps = [item.last_activity_at for item in result.cases if item.last_activity_at]
    assert timestamps == sorted(timestamps)


def test_closed_case_exposes_reopen_action(db_session, synthetic_case, progression, base_time):
    persistence = CaseStepProgressionPersistenceService(db_session)
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
    summary = SavedCaseService.get_saved_case(db_session, SYNTHETIC_CASE_UUID)
    assert summary.workspace_status == "closed"
    assert "reopen_case" in summary.available_actions


def test_open_case_does_not_offer_reopen_when_open(db_session, synthetic_case, progression):
    summary = SavedCaseService.get_saved_case(db_session, SYNTHETIC_CASE_UUID)
    assert summary.workspace_status == "open"
    assert "reopen_case" not in summary.available_actions
    assert "open_case" in summary.available_actions


def test_manual_reopen_preserves_case_uuid(db_session, synthetic_case, progression, base_time):
    persistence = CaseStepProgressionPersistenceService(db_session)
    persistence.close_case(SYNTHETIC_CASE_UUID, event_timestamp=base_time + timedelta(hours=1))

    result = SavedCaseService.reopen_case(
        db_session,
        SYNTHETIC_CASE_UUID,
        reason="Synthetic manual reopen.",
        source="manual_ui",
    )
    assert result.action_taken == "reopened"
    assert result.case.case_uuid == SYNTHETIC_CASE_UUID
    assert result.source == "manual_ui"


def test_ai_reopen_uses_same_service(db_session, synthetic_case, progression, base_time):
    persistence = CaseStepProgressionPersistenceService(db_session)
    persistence.close_case(SYNTHETIC_CASE_UUID, event_timestamp=base_time + timedelta(hours=1))

    result = SavedCaseService.reopen_case(
        db_session,
        SYNTHETIC_CASE_UUID,
        reason="Reopen the denied Step 1 case",
        source="ai_command",
    )
    assert result.action_taken == "reopened"
    assert result.source == "ai_command"
    assert result.case.case_uuid == SYNTHETIC_CASE_UUID


def test_reopen_creates_timeline_event(db_session, synthetic_case, progression, base_time):
    persistence = CaseStepProgressionPersistenceService(db_session)
    persistence.close_case(SYNTHETIC_CASE_UUID, event_timestamp=base_time + timedelta(hours=1))

    SavedCaseService.reopen_case(
        db_session,
        SYNTHETIC_CASE_UUID,
        source="manual_ui",
    )

    timeline = SavedCaseService.get_case_timeline(db_session, SYNTHETIC_CASE_UUID)
    reopen_events = [e for e in timeline.events if e.event_type == "case_reopened"]
    assert len(reopen_events) == 1


def test_reopen_preserves_close_history(db_session, synthetic_case, progression, base_time):
    persistence = CaseStepProgressionPersistenceService(db_session)
    persistence.close_case(SYNTHETIC_CASE_UUID, event_timestamp=base_time + timedelta(hours=2))
    SavedCaseService.reopen_case(db_session, SYNTHETIC_CASE_UUID, source="manual_ui")

    timeline = SavedCaseService.get_case_timeline(db_session, SYNTHETIC_CASE_UUID)
    close_events = [e for e in timeline.events if e.event_type == "case_closed"]
    assert len(close_events) == 1


def test_reopen_already_open_is_idempotent(db_session, synthetic_case, progression):
    first = SavedCaseService.reopen_case(db_session, SYNTHETIC_CASE_UUID, source="manual_ui")
    second = SavedCaseService.reopen_case(db_session, SYNTHETIC_CASE_UUID, source="ai_command")
    assert first.action_taken == "already_open"
    assert second.action_taken == "already_open"

    timeline = SavedCaseService.get_case_timeline(db_session, SYNTHETIC_CASE_UUID)
    reopen_events = [e for e in timeline.events if e.event_type == "case_reopened"]
    assert len(reopen_events) == 0


def test_timeline_oldest_first(db_session, synthetic_case, progression, base_time):
    persistence = CaseStepProgressionPersistenceService(db_session)
    persistence.close_case(SYNTHETIC_CASE_UUID, event_timestamp=base_time + timedelta(hours=1))
    persistence.reopen_case(
        SYNTHETIC_CASE_UUID,
        source="manual_ui",
        event_timestamp=base_time + timedelta(hours=2),
    )

    timeline = SavedCaseService.get_case_timeline(
        db_session,
        SYNTHETIC_CASE_UUID,
        newest_first=False,
    )
    timestamps = [event.event_timestamp for event in timeline.events]
    assert timestamps == sorted(timestamps)


def test_timeline_newest_first(db_session, synthetic_case, progression, base_time):
    persistence = CaseStepProgressionPersistenceService(db_session)
    persistence.close_case(SYNTHETIC_CASE_UUID, event_timestamp=base_time + timedelta(hours=1))
    persistence.reopen_case(
        SYNTHETIC_CASE_UUID,
        source="manual_ui",
        event_timestamp=base_time + timedelta(hours=2),
    )

    timeline = SavedCaseService.get_case_timeline(
        db_session,
        SYNTHETIC_CASE_UUID,
        newest_first=True,
    )
    timestamps = [event.event_timestamp for event in timeline.events]
    assert timestamps == sorted(timestamps, reverse=True)


def test_status_filter_closed(db_session, synthetic_case, progression, base_time):
    persistence = CaseStepProgressionPersistenceService(db_session)
    persistence.close_case(SYNTHETIC_CASE_UUID, event_timestamp=base_time + timedelta(hours=1))

    result = SavedCaseService.list_saved_cases(db_session, status_filter="closed")
    assert all(item.workspace_status == "closed" for item in result.cases)
    assert any(item.case_uuid == SYNTHETIC_CASE_UUID for item in result.cases)


def test_step_filter(db_session, synthetic_case, progression):
    result = SavedCaseService.list_saved_cases(
        db_session,
        step_filter="step_1_initial",
    )
    assert all(item.current_step_type == "step_1_initial" for item in result.cases)
