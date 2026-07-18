"""First-class Case Memory domain tests."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.database.models import CaseMemoryRecord
from app.services.case_memory_service import CASE_MEMORY_SCHEMA, CaseMemoryService
from app.services.case_service import CaseService


def _case(**overrides):
    base = dict(
        id=1,
        case_uuid="mem-case-1",
        title="Leave case",
        initial_question="Can approved leave be canceled?",
        known_facts={"approved": True},
        status="open",
        user_name="Steward A",
        local_number="300-1",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _service_with_row(memory=None, reopen_count=0):
    db = MagicMock()
    case = _case()
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    row = CaseMemoryRecord(
        id=9,
        case_id=1,
        case_uuid="mem-case-1",
        schema_version=CASE_MEMORY_SCHEMA,
        memory_json=memory
        or {
            "schema_version": CASE_MEMORY_SCHEMA,
            "facts": {"approved": True},
            "status": "open",
            "open_questions": [],
            "conversation_meanings": [],
            "analysis_reports": [],
            "grievance_history": [],
            "uploaded_documents": [],
            "official_artifacts": {"latest": {}, "all": []},
            "relationships": [],
            "reopen_count": reopen_count,
        },
        workflow_state="case_open",
        reopen_count=reopen_count,
        created_at=now,
        updated_at=now,
    )
    service = CaseMemoryService(db)

    def _publish(case_uuid, **kwargs):
        from app.schemas.case_domain_event_schema import CaseDomainEventRecord

        event = CaseDomainEventRecord(
            event_id=str(kwargs.get("idempotency_key") or "evt"),
            case_uuid=case_uuid,
            event_type=kwargs["event_type"],
            occurred_at=now,
            actor_id=kwargs.get("actor_id"),
            grievance_step=kwargs.get("grievance_step"),
            source_type=kwargs.get("source_type"),
            source_uuid=kwargs.get("source_uuid"),
            metadata=kwargs.get("metadata") or {},
            idempotency_key=kwargs.get("idempotency_key"),
            processing_status="processed",
            already_processed=False,
        )
        service.apply_event(event, commit=False)
        return event

    with patch.object(CaseService, "_get_case_row", return_value=case):
        query = MagicMock()
        db.query.return_value = query
        query.filter.return_value = query
        query.first.return_value = row
        with patch(
            "app.services.case_domain_event_service.CaseDomainEventService.publish",
            side_effect=_publish,
        ):
            yield service, db, row, case


def test_case_memory_updates_after_conversation_meaning():
    for service, _db, row, _case in _service_with_row():
        memory = service.record_conversation(
            "mem-case-1",
            meaning={
                "problem_discussed": "leave cancellation",
                "conclusion_reached": "Pursue make-whole",
                "unresolved_questions": ["supervisor name"],
                "decision_made": {"answer_type": "remedy"},
                "accepted": True,
                "rejected": False,
            },
            message_ids=[1, 2],
            report_version_number=2,
        )
        assert memory["conversation_meanings"]
        assert memory["open_questions"] == ["supervisor name"]
        assert memory["important_conclusions"][-1]["conclusion"] == "Pursue make-whole"
        assert any(
            r["kind"] == "conversation_to_report" for r in memory["relationships"]
        )
        assert row.memory_json["conversation_meanings"]


def test_reports_and_grievances_update_case_memory():
    for service, _db, _row, _case in _service_with_row():
        service.record_report(
            "mem-case-1",
            report_version_number=1,
            report_summary={"primary_issue": "Leave revocation"},
            primary_issue="Leave revocation",
            recommendation="Make steward whole",
            official=True,
            artifact_uuid="art-r1",
        )
        memory = service.record_grievance(
            "mem-case-1",
            grievance_step="step_2_appeal",
            version_number=1,
            artifact_uuid="art-g1",
            title="Step 2 Grievance v1",
            saved_and_printed=True,
        )
        assert memory["analysis_reports"][-1]["official"] is True
        assert memory["grievance_history"][-1]["saved_and_printed"] is True
        assert memory["current_recommendation"] == "Make steward whole"
        assert memory["official_artifacts"]["latest"]["grievance_form"]["version"] == 1


def test_evidence_and_workflow_update_case_memory():
    for service, _db, _row, _case in _service_with_row():
        service.record_evidence(
            "mem-case-1",
            asset_uuid="a1",
            filename="approval.pdf",
            management_response=False,
        )
        service.record_evidence(
            "mem-case-1",
            asset_uuid="a2",
            filename="mgmt response.pdf",
            management_response=True,
        )
        memory = service.record_outcome(
            "mem-case-1",
            step_type="step_1_initial",
            outcome_type="denied",
            decision_summary="Denied at Step 1",
            appeal_to_next_step=True,
        )
        overview = service._overview_from_memory("mem-case-1", memory)
        assert overview.evidence_count == 2
        assert overview.management_response_count == 1
        assert memory["workflow_state"]["awaiting_appeal"] is True


def test_close_settle_reopen_preserve_and_restore_memory():
    for service, _db, row, _case in _service_with_row():
        service.record_report(
            "mem-case-1",
            report_version_number=1,
            primary_issue="Issue",
            official=True,
            artifact_uuid="r1",
        )
        closed = service.record_close(
            "mem-case-1",
            outcome="Resolved",
            outcome_notes="Paid overtime",
            resolution_type="resolved",
            close_date=datetime(2026, 2, 1, tzinfo=timezone.utc),
            closed_by="Steward A",
            final_grievance_step="step_1_initial",
        )
        assert closed["status"] == "closed"
        assert closed["closure"]["outcome_notes"] == "Paid overtime"
        assert closed["analysis_reports"]  # preserved

        settled = service.record_settle(
            "mem-case-1",
            settlement_notes="Settled at Step 2",
            settlement_date=datetime(2026, 3, 1, tzinfo=timezone.utc),
            settled_by="Steward A",
        )
        assert settled["status"] == "settled"
        assert settled["settlement"]["settlement_notes"] == "Settled at Step 2"
        assert settled["analysis_reports"]  # preserved

        reopened = service.record_reopen(
            "mem-case-1",
            reason="New evidence",
            reopened_by="Steward A",
            source="manual_ui",
        )
        assert reopened["status"] == "open"
        assert reopened["reopen_count"] == 1
        assert row.reopen_count == 1
        assert reopened["reopen_history"][-1]["reason_reopened"] == "New evidence"
        assert reopened["analysis_reports"]  # still present


def test_case_overview_reflects_case_memory():
    for service, _db, _row, _case in _service_with_row():
        service.record_conversation(
            "mem-case-1",
            meaning={
                "problem_discussed": "leave",
                "unresolved_questions": ["date of cancellation"],
                "conclusion_reached": "Likely grievable",
                "decision_made": {"answer_type": "fact"},
            },
        )
        service.record_report(
            "mem-case-1",
            report_version_number=2,
            primary_issue="Leave cancellation",
            recommendation="Make whole",
            official=True,
            artifact_uuid="r2",
        )
        overview = service.get_overview("mem-case-1")
        assert overview.source == "case_memory"
        assert overview.issue == "Leave cancellation"
        assert overview.current_recommendation == "Make whole"
        assert "date of cancellation" in overview.open_questions
        assert overview.analysis_report_count >= 1


def test_ai_foundation_is_bounded_and_not_transcript_replay():
    for service, _db, _row, _case in _service_with_row():
        foundation = service.to_ai_foundation("mem-case-1")
        assert foundation["restored_from"] == "case_memory"
        assert foundation["case_is_system_of_record"] is True
        assert foundation["full_transcript_embedded"] is False
        assert foundation["full_artifact_bodies_embedded"] is False
        assert "facts" in foundation


def test_retrieval_marks_enrichment_not_rebuild():
    case = SimpleNamespace(
        case_uuid="ret-mem",
        id=3,
        messages=[],
        report_versions=[],
        known_facts={},
    )
    with (
        patch(
            "app.services.case_saved_artifact_service.CaseSavedArtifactService."
            "official_artifact_index",
            return_value=[],
        ),
    ):
        memory = CaseService.retrieve_relevant_case_memory(
            MagicMock(), case, "any leftover evidence?"
        )
    # Enrichment flags are applied in build_restored_interaction_context.
    assert memory["full_transcript_replayed"] is False


def test_case_memory_isolation_by_case_uuid():
    db = MagicMock()
    service = CaseMemoryService(db)
    with patch.object(CaseService, "_get_case_row", return_value=None):
        try:
            service.load("other-case")
            raised = False
        except Exception:
            raised = True
    assert raised is True


def test_memory_and_overview_routes_registered():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    paths = set(client.get("/openapi.json").json()["paths"])
    assert "/cases/{case_uuid}/memory" in paths
    assert "/cases/{case_uuid}/overview" in paths
    assert "/cases/{case_uuid}/outcomes" in paths
    assert "/cases/saved/{case_uuid}/close" in paths


def test_create_case_initializes_case_memory():
    db = MagicMock()
    ensure_prog = MagicMock(return_value=SimpleNamespace(current_step_type="step_1_initial"))
    ensure_mem = MagicMock()
    publish = MagicMock()
    with (
        patch(
            "app.services.case_step_progression_persistence_service."
            "CaseStepProgressionPersistenceService.ensure_case_progression",
            ensure_prog,
        ),
        patch(
            "app.services.case_memory_service.CaseMemoryService.ensure_for_case",
            ensure_mem,
        ),
        patch(
            "app.services.case_domain_event_service.CaseDomainEventService.publish",
            publish,
        ),
    ):
        case = CaseService.create_case(db, question="Can leave be canceled?")
    assert case.initial_question == "Can leave be canceled?"
    ensure_mem.assert_called_once()
    assert ensure_mem.call_args.kwargs.get("commit") is False
    publish.assert_called_once()
    assert publish.call_args.kwargs.get("event_type") == "case_created"
