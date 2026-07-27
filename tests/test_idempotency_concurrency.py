"""True PostgreSQL concurrency tests for idempotent replay (W6 Batch 2).

These tests use two separate SQLAlchemy sessions/connections in real OS
threads, synchronized with a ``threading.Barrier`` planted on the SQLAlchemy
``before_insert`` mapper event so both requests are guaranteed to have
already decided to insert -- past the app-level "does a row exist?" check --
before either one's INSERT reaches PostgreSQL. This exercises the actual
database-level unique-index race, not a lucky timing window, and proves the
service layer resolves it without duplicating rows or corrupting either
session's transaction.

Requires a real, reachable PostgreSQL database (the configured
``alembic.ini`` / app DB URL). Skips automatically -- not via a manual
opt-in flag -- when the database cannot be reached, since these tests
cannot mean anything against SQLite or mocks.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from datetime import datetime
from uuid import uuid4

import pytest
from sqlalchemy import event, text

from app.database.models import (
    CaseDomainEvent,
    CaseFormDraftRecord,
    CaseReportVersion,
    CaseSavedArtifact,
)
from app.database.session import SessionLocal
from app.schemas.case_saved_artifact_schema import (
    SaveAndPrintGrievanceRequest,
    SaveAndPrintReportRequest,
)
from app.services.case_domain_event_service import CaseDomainEventService
from app.services.case_saved_artifact_service import CaseSavedArtifactService
from app.services.case_service import CaseService
from app.services.case_step_progression_persistence_service import (
    CaseStepProgressionPersistenceService,
)

pytestmark = pytest.mark.integration


def _postgres_available() -> bool:
    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
        finally:
            db.close()
        return True
    except Exception:
        return False


if not _postgres_available():
    pytest.skip(
        "PostgreSQL is not reachable; true concurrency tests require a real database.",
        allow_module_level=True,
    )


@contextmanager
def _synchronized_insert(model, *, key_attr: str, key_value: str):
    """Pause exactly two racing flushes at the moment they attempt to INSERT.

    Registered on the SQLAlchemy mapper (not a single session), so it fires
    for whichever of the two threads' sessions reaches the contested insert,
    regardless of ordering. Only instances matching ``key_value`` synchronize,
    so unrelated inserts (e.g. from other fixtures) are unaffected.
    """
    barrier = threading.Barrier(2, timeout=15)

    def _pause(mapper, connection, target) -> None:
        if getattr(target, key_attr, None) == key_value:
            barrier.wait()

    event.listen(model, "before_insert", _pause)
    try:
        yield
    finally:
        event.remove(model, "before_insert", _pause)


def _run_concurrently(fn_a, fn_b):
    """Run two callables in separate threads; surface exceptions and hangs."""
    outcomes: dict[str, object] = {}
    errors: dict[str, BaseException] = {}

    def _wrap(name, fn):
        try:
            outcomes[name] = fn()
        except BaseException as exc:  # noqa: BLE001 - surfaced to the test below
            errors[name] = exc

    t_a = threading.Thread(target=_wrap, args=("a", fn_a))
    t_b = threading.Thread(target=_wrap, args=("b", fn_b))
    t_a.start()
    t_b.start()
    t_a.join(timeout=30)
    t_b.join(timeout=30)
    if t_a.is_alive() or t_b.is_alive():
        pytest.fail("Concurrent requests did not complete in time (possible deadlock).")
    if errors:
        raise AssertionError(f"Concurrent thread(s) raised: {errors}")
    return outcomes["a"], outcomes["b"]


def _assert_session_usable(db) -> None:
    """The session's transaction must not be left aborted by a losing race."""
    assert db.execute(text("SELECT 1")).scalar() == 1


def _new_case(*, with_report_version: bool = False, with_progression: bool = False):
    db = SessionLocal()
    try:
        case = CaseService.create_case(
            db,
            question="Concurrency test case for idempotent replay.",
            user_name="Concurrency Test",
            local_number="999",
        )
        case_uuid = case.case_uuid
        case_id = case.id
        version_number = None
        if with_report_version:
            version = CaseReportVersion(
                case_id=case_id,
                version_number=1,
                report_data={
                    "report": {
                        "quick_assessment": {
                            "summary": "Synthetic concurrency-test report.",
                            "grievability": "Likely Grievable",
                        }
                    }
                },
                report_summary={"primary_issue": "Synthetic issue", "authority_count": 0},
            )
            db.add(version)
            db.commit()
            db.refresh(version)
            version_number = version.version_number
        if with_progression:
            CaseStepProgressionPersistenceService(db).ensure_case_progression(
                case_uuid, commit=True
            )
        return case_uuid, case_id, version_number
    finally:
        db.close()


def test_concurrent_analysis_save_creates_one_artifact():
    """Two concurrent Save requests, same idempotency_key -> one artifact."""
    case_uuid, _case_id, version_number = _new_case(with_report_version=True)
    key = f"concurrency-report-{uuid4()}"

    session_a = SessionLocal()
    session_b = SessionLocal()
    try:
        request = SaveAndPrintReportRequest(
            report_version_number=version_number,
            grievance_step="step_1_initial",
            idempotency_key=key,
            prepare_pdf=False,
        )
        with _synchronized_insert(
            CaseSavedArtifact, key_attr="idempotency_key", key_value=key
        ):
            result_a, result_b = _run_concurrently(
                lambda: CaseSavedArtifactService(session_a).save_and_print_report(
                    case_uuid, request
                ),
                lambda: CaseSavedArtifactService(session_b).save_and_print_report(
                    case_uuid, request
                ),
            )

        statuses = sorted([result_a.status, result_b.status])
        assert statuses == ["idempotent_replay", "saved"], statuses
        assert result_a.artifact.artifact_uuid == result_b.artifact.artifact_uuid

        _assert_session_usable(session_a)
        _assert_session_usable(session_b)

        verify = SessionLocal()
        try:
            artifact_count = verify.execute(
                text(
                    "SELECT count(*) FROM case_saved_artifacts "
                    "WHERE case_uuid = :c AND idempotency_key = :k"
                ),
                {"c": case_uuid, "k": key},
            ).scalar()
            assert artifact_count == 1

            event_count = verify.execute(
                text(
                    "SELECT count(*) FROM case_domain_events "
                    "WHERE case_uuid = :c AND source_uuid = :a "
                    "AND event_type IN ('analysis_saved', 'analysis_saved_and_printed')"
                ),
                {"c": case_uuid, "a": result_a.artifact.artifact_uuid},
            ).scalar()
            assert event_count == 1, "domain event must not be duplicated by the race"

            timeline_count = verify.execute(
                text(
                    "SELECT count(*) FROM case_timeline_events "
                    "WHERE case_uuid = :c AND export_ref = :a "
                    "AND event_type IN "
                    "('analysis_report_saved', 'analysis_report_saved_and_printed')"
                ),
                {"c": case_uuid, "a": result_a.artifact.artifact_uuid},
            ).scalar()
            assert timeline_count == 1, "steward timeline must not be duplicated by the race"
        finally:
            verify.close()
    finally:
        session_a.close()
        session_b.close()


def test_concurrent_grievance_save_creates_one_artifact():
    """Two concurrent grievance Save requests, same key -> one artifact."""
    case_uuid, _case_id, _v = _new_case(with_progression=True)
    key = f"concurrency-grievance-{uuid4()}"

    session_a = SessionLocal()
    session_b = SessionLocal()
    try:
        request = SaveAndPrintGrievanceRequest(
            template_id="local_300_form_79_1",
            template_version="1.0",
            grievance_step="step_1_initial",
            field_values={"grievant_name": "Concurrency Tester"},
            idempotency_key=key,
            prepare_pdf=False,
        )
        with _synchronized_insert(
            CaseFormDraftRecord, key_attr="idempotency_key", key_value=key
        ):
            result_a, result_b = _run_concurrently(
                lambda: CaseSavedArtifactService(session_a).save_and_print_grievance(
                    case_uuid, request
                ),
                lambda: CaseSavedArtifactService(session_b).save_and_print_grievance(
                    case_uuid, request
                ),
            )

        statuses = sorted([result_a.status, result_b.status])
        assert statuses == ["idempotent_replay", "saved"], statuses
        assert result_a.artifact.artifact_uuid == result_b.artifact.artifact_uuid

        _assert_session_usable(session_a)
        _assert_session_usable(session_b)

        verify = SessionLocal()
        try:
            draft_count = verify.execute(
                text(
                    "SELECT count(*) FROM case_form_draft_records "
                    "WHERE case_uuid = :c AND idempotency_key = :k"
                ),
                {"c": case_uuid, "k": key},
            ).scalar()
            assert draft_count == 1, "draft record must not be duplicated by the race"

            artifact_count = verify.execute(
                text(
                    "SELECT count(*) FROM case_saved_artifacts "
                    "WHERE case_uuid = :c AND idempotency_key = :k"
                ),
                {"c": case_uuid, "k": key},
            ).scalar()
            assert artifact_count == 1
        finally:
            verify.close()
    finally:
        session_a.close()
        session_b.close()


def test_concurrent_domain_event_publish_creates_one_event():
    """Two concurrent domain-event publications, same key -> one event row."""
    case_uuid, _case_id, _v = _new_case()
    key = f"concurrency-event-{uuid4()}"

    session_a = SessionLocal()
    session_b = SessionLocal()
    try:
        with _synchronized_insert(
            CaseDomainEvent, key_attr="idempotency_key", key_value=key
        ):
            result_a, result_b = _run_concurrently(
                lambda: CaseDomainEventService(session_a).publish(
                    case_uuid,
                    event_type="evidence_uploaded",
                    idempotency_key=key,
                    apply_to_memory=False,
                ),
                lambda: CaseDomainEventService(session_b).publish(
                    case_uuid,
                    event_type="evidence_uploaded",
                    idempotency_key=key,
                    apply_to_memory=False,
                ),
            )

        # Both requests must resolve to the exact same durable event row.
        # (already_processed is not a reliable winner/loser signal here: with
        # apply_to_memory=False the winner also finishes processing
        # synchronously before commit, so both sides legitimately report
        # already_processed=True once the race is resolved.)
        assert result_a.event_id == result_b.event_id

        _assert_session_usable(session_a)
        _assert_session_usable(session_b)

        verify = SessionLocal()
        try:
            event_count = verify.execute(
                text(
                    "SELECT count(*) FROM case_domain_events "
                    "WHERE case_uuid = :c AND idempotency_key = :k"
                ),
                {"c": case_uuid, "k": key},
            ).scalar()
            assert event_count == 1
        finally:
            verify.close()
    finally:
        session_a.close()
        session_b.close()


def test_different_idempotency_keys_create_separate_artifacts():
    """Sanity check: distinct keys on one case are never conflated."""
    case_uuid, _case_id, version_number = _new_case(with_report_version=True)

    db = SessionLocal()
    try:
        service = CaseSavedArtifactService(db)
        first = service.save_and_print_report(
            case_uuid,
            SaveAndPrintReportRequest(
                report_version_number=version_number,
                grievance_step="step_1_initial",
                idempotency_key=f"key-one-{uuid4()}",
                prepare_pdf=False,
            ),
        )
        second = service.save_and_print_report(
            case_uuid,
            SaveAndPrintReportRequest(
                report_version_number=version_number,
                grievance_step="step_1_initial",
                idempotency_key=f"key-two-{uuid4()}",
                prepare_pdf=False,
            ),
        )
        assert first.artifact.artifact_uuid != second.artifact.artifact_uuid
        assert first.status == "saved"
        assert second.status == "saved"
    finally:
        db.close()


def test_same_idempotency_key_allowed_on_different_cases():
    """Same key on two different cases must not collide (scope is per-case)."""
    case_uuid_1, _c1, version_1 = _new_case(with_report_version=True)
    case_uuid_2, _c2, version_2 = _new_case(with_report_version=True)
    shared_key = f"shared-key-{uuid4()}"

    db = SessionLocal()
    try:
        service = CaseSavedArtifactService(db)
        first = service.save_and_print_report(
            case_uuid_1,
            SaveAndPrintReportRequest(
                report_version_number=version_1,
                grievance_step="step_1_initial",
                idempotency_key=shared_key,
                prepare_pdf=False,
            ),
        )
        second = service.save_and_print_report(
            case_uuid_2,
            SaveAndPrintReportRequest(
                report_version_number=version_2,
                grievance_step="step_1_initial",
                idempotency_key=shared_key,
                prepare_pdf=False,
            ),
        )
        assert first.status == "saved"
        assert second.status == "saved"
        assert first.artifact.artifact_uuid != second.artifact.artifact_uuid
    finally:
        db.close()
