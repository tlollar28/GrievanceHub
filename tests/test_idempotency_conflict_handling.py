"""Unit tests for simulated idempotency-key conflict handling (W6 Batch 2).

These use MagicMock sessions and a synthetic ``IntegrityError`` to exercise
the savepoint + conflict-detection branch in isolation and deterministically,
independent of database timing. True overlapping-transaction behavior against
real PostgreSQL is covered separately in test_idempotency_concurrency.py.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from app.schemas.case_saved_artifact_schema import (
    SaveAndPrintGrievanceRequest,
    SaveAndPrintReportRequest,
)
from app.services.case_domain_event_service import CaseDomainEventService
from app.services.case_saved_artifact_service import CaseSavedArtifactService
from app.services.case_service import CaseService
from app.services.idempotency_conflict_utils import (
    CASE_DOMAIN_EVENTS_IDEMPOTENCY_INDEX,
    CASE_FORM_DRAFT_RECORDS_IDEMPOTENCY_INDEX,
    CASE_SAVED_ARTIFACTS_IDEMPOTENCY_INDEX,
    is_idempotency_conflict,
    violated_constraint_name,
)


def _integrity_error(constraint_name: str | None) -> IntegrityError:
    orig = SimpleNamespace(diag=SimpleNamespace(constraint_name=constraint_name))
    return IntegrityError("INSERT ...", {}, orig)


def _case_row(**overrides):
    base = dict(
        id=1,
        case_uuid="case-conflict-1",
        title="Conflict case",
        user_name="Steward A",
        local_number="300",
        initial_question="Q?",
        known_facts={},
        status="open",
        report_versions=[
            SimpleNamespace(
                id=10,
                version_number=1,
                report_data={"report": {"quick_assessment": {"summary": "S"}}},
                report_summary={"primary_issue": "Issue"},
                issue_analysis={},
                ranked_authorities=[],
                evidence_items=[],
                retrieval_gaps={},
                source_coverage_audit=[],
            )
        ],
    )
    base.update(overrides)
    return SimpleNamespace(**base)


# ----------------------------------------------------------------------
# Shared utility
# ----------------------------------------------------------------------


def test_violated_constraint_name_missing_diagnostics_returns_none():
    exc = IntegrityError("INSERT ...", {}, RuntimeError("no diag attribute"))
    assert violated_constraint_name(exc) is None


def test_is_idempotency_conflict_false_when_name_unrecognized():
    exc = _integrity_error("some_unrelated_constraint")
    assert is_idempotency_conflict(exc, CASE_SAVED_ARTIFACTS_IDEMPOTENCY_INDEX) is False


def test_is_idempotency_conflict_true_for_exact_match():
    exc = _integrity_error(CASE_SAVED_ARTIFACTS_IDEMPOTENCY_INDEX)
    assert is_idempotency_conflict(exc, CASE_SAVED_ARTIFACTS_IDEMPOTENCY_INDEX) is True


# ----------------------------------------------------------------------
# CaseDomainEventService.publish_payload
# ----------------------------------------------------------------------


def test_publish_payload_null_key_never_checks_existing_and_always_inserts():
    db = MagicMock()
    db.add.side_effect = lambda obj: setattr(obj, "id", 1)
    service = CaseDomainEventService(db)
    case = _case_row()

    with patch.object(CaseService, "_get_case_row", return_value=case):
        result = service.publish(
            case.case_uuid,
            event_type="evidence_uploaded",
            idempotency_key=None,
            apply_to_memory=False,
        )

    assert result.already_processed is True  # processing completed, not a replay
    assert db.commit.call_count == 1
    # No idempotency pre-check query is issued at all for a null key.
    db.query.assert_not_called()


def test_publish_payload_conflict_falls_back_to_winner_without_reraising():
    from app.database.models import CaseDomainEvent

    db = MagicMock()
    case = _case_row()
    # publish_payload guards its fast-path/post-conflict lookups with
    # isinstance(..., CaseDomainEvent) specifically to ignore non-model stubs
    # from MagicMock sessions, so the fake "winner" must be a real (if
    # unpersisted) model instance rather than a SimpleNamespace.
    winner = CaseDomainEvent(
        event_id="evt-winner",
        case_id=case.id,
        case_uuid=case.case_uuid,
        event_type="evidence_uploaded",
        occurred_at=datetime.now(timezone.utc),
        idempotency_key="same-key",
        processing_status="processed",
        processed_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
    )
    service = CaseDomainEventService(db)
    db.flush.side_effect = _integrity_error(CASE_DOMAIN_EVENTS_IDEMPOTENCY_INDEX)
    # First existence check (fast path) finds nothing; second (post-conflict)
    # finds the winner.
    db.query.return_value.filter.return_value.first.side_effect = [None, winner]

    with patch.object(CaseService, "_get_case_row", return_value=case):
        result = service.publish(
            case.case_uuid,
            event_type="evidence_uploaded",
            idempotency_key="same-key",
            apply_to_memory=False,
        )

    assert result.event_id == "evt-winner"
    assert result.already_processed is True
    db.commit.assert_not_called()


def test_publish_payload_unrelated_integrity_error_is_reraised():
    db = MagicMock()
    case = _case_row()
    service = CaseDomainEventService(db)
    db.flush.side_effect = _integrity_error("some_other_constraint")
    db.query.return_value.filter.return_value.first.return_value = None

    with patch.object(CaseService, "_get_case_row", return_value=case):
        with pytest.raises(IntegrityError):
            service.publish(
                case.case_uuid,
                event_type="evidence_uploaded",
                idempotency_key="same-key",
                apply_to_memory=False,
            )


# ----------------------------------------------------------------------
# CaseSavedArtifactService.save_and_print_report
# ----------------------------------------------------------------------


def test_save_and_print_report_conflict_falls_back_to_winner():
    db = MagicMock()
    case = _case_row()
    service = CaseSavedArtifactService(db)
    winner = SimpleNamespace(
        case_uuid=case.case_uuid,
        artifact_uuid="art-winner",
        artifact_type="analysis_report",
        title="Analysis Report v1",
        version_number=1,
        version_label="Analysis Report v1",
        grievance_step="step_1_initial",
        template_id=None,
        template_version=None,
        printed=False,
        pdf_status="pending",
        pdf_asset_uuid=None,
        is_latest_official=True,
        saved_by="Steward A",
        saved_at=datetime.now(timezone.utc),
        source_report_version_number=1,
        source_draft_record_uuid=None,
        key_summary_json={},
    )
    db.flush.side_effect = _integrity_error(CASE_SAVED_ARTIFACTS_IDEMPOTENCY_INDEX)

    with (
        patch.object(CaseService, "_get_case_row", return_value=case),
        patch.object(service, "_find_by_idempotency", side_effect=[None, winner]),
        patch.object(service, "_current_step_type", return_value="step_1_initial"),
        patch.object(service, "_next_artifact_version", return_value=1),
        patch.object(service, "_clear_latest_flag"),
    ):
        result = service.save_and_print_report(
            case.case_uuid,
            SaveAndPrintReportRequest(
                report_version_number=1,
                idempotency_key="same-key",
                prepare_pdf=False,
            ),
        )

    assert result.status == "idempotent_replay"
    assert result.artifact.artifact_uuid == "art-winner"
    db.commit.assert_not_called()


def test_save_and_print_report_unrelated_integrity_error_is_reraised():
    db = MagicMock()
    case = _case_row()
    service = CaseSavedArtifactService(db)
    db.flush.side_effect = _integrity_error("case_saved_artifacts_pkey")

    with (
        patch.object(CaseService, "_get_case_row", return_value=case),
        patch.object(service, "_find_by_idempotency", return_value=None),
        patch.object(service, "_current_step_type", return_value="step_1_initial"),
        patch.object(service, "_next_artifact_version", return_value=1),
        patch.object(service, "_clear_latest_flag"),
    ):
        with pytest.raises(IntegrityError):
            service.save_and_print_report(
                case.case_uuid,
                SaveAndPrintReportRequest(
                    report_version_number=1,
                    idempotency_key="same-key",
                    prepare_pdf=False,
                ),
            )


def test_save_and_print_report_conflict_with_no_recoverable_winner_reraises():
    """Defensive case: if the conflict fires but a winner row truly can't be
    found (e.g. transaction-visibility edge case), the original error must
    surface rather than be silently discarded."""
    db = MagicMock()
    case = _case_row()
    service = CaseSavedArtifactService(db)
    db.flush.side_effect = _integrity_error(CASE_SAVED_ARTIFACTS_IDEMPOTENCY_INDEX)

    with (
        patch.object(CaseService, "_get_case_row", return_value=case),
        patch.object(service, "_find_by_idempotency", side_effect=[None, None]),
        patch.object(service, "_current_step_type", return_value="step_1_initial"),
        patch.object(service, "_next_artifact_version", return_value=1),
        patch.object(service, "_clear_latest_flag"),
    ):
        with pytest.raises(IntegrityError):
            service.save_and_print_report(
                case.case_uuid,
                SaveAndPrintReportRequest(
                    report_version_number=1,
                    idempotency_key="same-key",
                    prepare_pdf=False,
                ),
            )


# ----------------------------------------------------------------------
# CaseSavedArtifactService.save_and_print_grievance
# ----------------------------------------------------------------------


def _grievance_winner(case_uuid: str):
    return SimpleNamespace(
        case_uuid=case_uuid,
        artifact_uuid="art-grievance-winner",
        artifact_type="grievance_form",
        title="Step 1 Grievance v1",
        version_number=1,
        version_label="Step 1 Grievance v1",
        grievance_step="step_1_initial",
        template_id="local_300_form_79_1",
        template_version="1.0",
        printed=False,
        pdf_status="pending",
        pdf_asset_uuid=None,
        is_latest_official=True,
        saved_by="Steward A",
        saved_at=datetime.now(timezone.utc),
        source_report_version_number=None,
        source_draft_record_uuid="draft-winner",
        key_summary_json={},
    )


@pytest.mark.parametrize(
    "conflicting_index",
    [CASE_FORM_DRAFT_RECORDS_IDEMPOTENCY_INDEX, CASE_SAVED_ARTIFACTS_IDEMPOTENCY_INDEX],
)
def test_save_and_print_grievance_conflict_falls_back_to_winner(conflicting_index):
    """Either table's unique index may be the one that reports the race
    first; both must resolve to the same graceful replay behavior."""
    db = MagicMock()
    case = _case_row()
    service = CaseSavedArtifactService(db)
    winner = _grievance_winner(case.case_uuid)
    step = SimpleNamespace(id=5, step_type="step_1_initial")
    db.flush.side_effect = _integrity_error(conflicting_index)

    with (
        patch.object(CaseService, "_get_case_row", return_value=case),
        patch.object(service, "_find_by_idempotency", side_effect=[None, winner]),
        patch.object(service, "_current_step_type", return_value="step_1_initial"),
        patch.object(service, "_require_or_ensure_step", return_value=step),
        patch.object(service, "_next_artifact_version", return_value=1),
        patch.object(service, "_clear_latest_flag"),
    ):
        result = service.save_and_print_grievance(
            case.case_uuid,
            SaveAndPrintGrievanceRequest(
                template_id="local_300_form_79_1",
                template_version="1.0",
                grievance_step="step_1_initial",
                field_values={"grievant_name": "Tester"},
                idempotency_key="same-key",
                prepare_pdf=False,
            ),
        )

    assert result.status == "idempotent_replay"
    assert result.artifact.artifact_uuid == "art-grievance-winner"
    db.commit.assert_not_called()


def test_save_and_print_grievance_unrelated_integrity_error_is_reraised():
    db = MagicMock()
    case = _case_row()
    service = CaseSavedArtifactService(db)
    step = SimpleNamespace(id=5, step_type="step_1_initial")
    db.flush.side_effect = _integrity_error("case_form_draft_records_pkey")

    with (
        patch.object(CaseService, "_get_case_row", return_value=case),
        patch.object(service, "_find_by_idempotency", return_value=None),
        patch.object(service, "_current_step_type", return_value="step_1_initial"),
        patch.object(service, "_require_or_ensure_step", return_value=step),
        patch.object(service, "_next_artifact_version", return_value=1),
        patch.object(service, "_clear_latest_flag"),
    ):
        with pytest.raises(IntegrityError):
            service.save_and_print_grievance(
                case.case_uuid,
                SaveAndPrintGrievanceRequest(
                    template_id="local_300_form_79_1",
                    template_version="1.0",
                    grievance_step="step_1_initial",
                    field_values={"grievant_name": "Tester"},
                    idempotency_key="same-key",
                    prepare_pdf=False,
                ),
            )
