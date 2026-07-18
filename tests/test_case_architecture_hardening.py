"""Architecture hardening: domain events, workflow, recommendations, jump-to-context."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.database.models import (
    CaseDomainEvent,
    CaseMemoryRecord,
    CaseTimelineEventRecord,
)
from app.schemas.case_domain_event_schema import CaseDomainEventRecord
from app.services.case_domain_event_service import CaseDomainEventService
from app.services.case_history_context_service import CaseHistoryContextService
from app.services.case_memory_service import (
    CASE_MEMORY_SCHEMA,
    REQUIRED_SECTIONS,
    CaseMemoryService,
)
from app.services.case_service import CaseService
from app.services.case_workflow_service import CaseWorkflowError, CaseWorkflowService


def _case(**overrides):
    base = dict(
        id=1,
        case_uuid="hard-case-1",
        title="Leave case",
        initial_question="Can approved leave be canceled?",
        known_facts={"approved": True},
        status="open",
        user_name="Steward A",
        local_number="300-1",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _memory_row(memory=None, reopen_count=0, workflow_state="case_open"):
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return CaseMemoryRecord(
        id=9,
        case_id=1,
        case_uuid="hard-case-1",
        schema_version=CASE_MEMORY_SCHEMA,
        memory_json=memory
        or {
            "schema_version": CASE_MEMORY_SCHEMA,
            "facts": {"approved": True},
            "status": "open",
            "current_grievance_step": "step_1_initial",
            "workflow": {"explicit_state": workflow_state},
            "open_questions": [],
            "conversation_meanings": [],
            "analysis_reports": [],
            "grievance_history": [],
            "uploaded_documents": [],
            "official_artifacts": {"latest": {}, "all": []},
            "relationships": [],
            "reopen_count": reopen_count,
        },
        workflow_state=workflow_state,
        reopen_count=reopen_count,
        created_at=now,
        updated_at=now,
    )


class _QueryStub:
    def __init__(self, first=None, all_rows=None):
        self._first = first
        self._all = all_rows or []

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def first(self):
        return self._first

    def all(self):
        return list(self._all)


def test_normalize_memory_provides_required_sections_and_defaults():
    service = CaseMemoryService(MagicMock())
    legacy = {
        "schema_version": "case_memory_v1",
        "facts": {"a": 1},
        "status": "open",
        "important_decisions": [{"decision": "x"}],
        "current_recommendation": "Pursue Step 1",
    }
    memory = service.normalize_memory(legacy)
    for section in REQUIRED_SECTIONS:
        assert section in memory
    assert memory["identity_and_facts"]["facts"]["a"] == 1
    assert memory["decisions"][0]["decision"] == "x"
    assert memory["recommendations"]["current"]["recommendation"] == "Pursue Step 1"
    assert memory["workflow"]["explicit_state"]


def test_apply_event_updates_only_relevant_sections_idempotently():
    db = MagicMock()
    row = _memory_row()
    case = _case()
    service = CaseMemoryService(db)
    with patch.object(CaseService, "_get_case_row", return_value=case):
        db.query.side_effect = lambda model: _QueryStub(first=row)

        event = CaseDomainEventRecord(
            event_id="e1",
            case_uuid="hard-case-1",
            event_type="evidence_uploaded",
            occurred_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            metadata={
                "asset_uuid": "asset-1",
                "filename": "clock.pdf",
                "summary": "Clock rings",
            },
        )
        memory = service.apply_event(event, commit=False)
        assert len(memory["evidence"]["summaries"]) == 1
        decisions_before = list(memory.get("decisions") or [])

        # Duplicate delivery must not grow evidence.
        memory2 = service.apply_event(event, commit=False)
        assert len(memory2["evidence"]["summaries"]) == 1
        assert memory2.get("decisions") == decisions_before


def test_domain_event_publish_is_idempotent():
    db = MagicMock()
    case = _case()
    existing = CaseDomainEvent(
        event_id="existing",
        case_id=1,
        case_uuid="hard-case-1",
        event_type="evidence_uploaded",
        occurred_at=datetime.utcnow(),
        idempotency_key="evidence:hard-case-1:a1",
        processing_status="processed",
        metadata_json={},
        schema_version="case_domain_event_v1",
        created_at=datetime.utcnow(),
    )
    service = CaseDomainEventService(db)
    with patch.object(CaseService, "_get_case_row", return_value=case):
        db.query.side_effect = lambda model: _QueryStub(first=existing)
        result = service.publish(
            "hard-case-1",
            event_type="evidence_uploaded",
            source_uuid="a1",
            idempotency_key="evidence:hard-case-1:a1",
            commit=False,
        )
    assert result.already_processed is True
    assert result.event_id == "existing"


def test_workflow_rejects_step_skip_and_closed_without_reopen():
    db = MagicMock()
    row = _memory_row(workflow_state="case_open")
    case = _case()
    service = CaseWorkflowService(db)
    with patch.object(CaseService, "_get_case_row", return_value=case):
        with patch.object(CaseMemoryService, "load", return_value=row.memory_json):
            with patch.object(CaseMemoryService, "_persist", return_value=row.memory_json):
                with patch.object(CaseMemoryService, "get_row", return_value=row):
                    with pytest.raises(CaseWorkflowError):
                        service.transition(
                            "hard-case-1",
                            "step_2_analysis",
                            commit=False,
                            publish_event=False,
                        )

    closed_memory = dict(row.memory_json)
    closed_memory["workflow"] = {"explicit_state": "closed"}
    closed_memory["status"] = "closed"
    with patch.object(CaseService, "_get_case_row", return_value=case):
        with patch.object(CaseMemoryService, "load", return_value=closed_memory):
            with patch.object(CaseMemoryService, "_persist", return_value=closed_memory):
                with patch.object(CaseMemoryService, "get_row", return_value=row):
                    with pytest.raises(CaseWorkflowError):
                        service.transition(
                            "hard-case-1",
                            "step_1_analysis",
                            commit=False,
                            publish_event=False,
                        )


def test_workflow_step1_resolve_close_without_step2():
    db = MagicMock()
    memory = {
        "schema_version": CASE_MEMORY_SCHEMA,
        "status": "open",
        "current_grievance_step": "step_1_initial",
        "workflow": {"explicit_state": "step_1_decision_required"},
        "facts": {},
        "open_questions": [],
        "decisions": [],
        "official_artifacts": {"latest": {}, "all": []},
        "recommendations": {"current": {"status": "no_recommendation"}, "history": []},
    }
    row = _memory_row(memory=memory, workflow_state="step_1_decision_required")
    case = _case()
    persisted = {}

    def _persist(case_uuid, mem, commit=True):
        persisted.update(mem)
        return mem

    service = CaseWorkflowService(db)
    with patch.object(CaseService, "_get_case_row", return_value=case):
        with patch.object(CaseMemoryService, "load", return_value=memory):
            with patch.object(CaseMemoryService, "_persist", side_effect=_persist):
                with patch.object(CaseMemoryService, "get_row", return_value=row):
                    with patch(
                        "app.services.case_domain_event_service.CaseDomainEventService.publish"
                    ):
                        service.transition(
                            "hard-case-1",
                            "step_1_resolved",
                            commit=False,
                            publish_event=False,
                        )
                        view = service.transition(
                            "hard-case-1",
                            "closed",
                            commit=False,
                            publish_event=False,
                        )
    assert view.explicit_state == "closed"
    assert persisted.get("status") == "closed"


def test_recommendation_structured_and_distinct_from_steward_decision():
    db = MagicMock()
    row = _memory_row()
    case = _case()
    service = CaseMemoryService(db)
    with patch.object(CaseService, "_get_case_row", return_value=case):
        db.query.side_effect = lambda model: _QueryStub(first=row)
        service.apply_event(
            CaseDomainEventRecord(
                event_id="rec1",
                case_uuid="hard-case-1",
                event_type="analysis_generated",
                occurred_at=datetime.utcnow(),
                metadata={
                    "report_version_number": 1,
                    "recommendation": "Proceed to Step 1 filing",
                    "rationale": "Leave cancellation appears grievable",
                    "unresolved_questions": ["Confirm cancellation date"],
                },
            ),
            commit=False,
        )
        service.apply_event(
            CaseDomainEventRecord(
                event_id="out1",
                case_uuid="hard-case-1",
                event_type="outcome_recorded",
                occurred_at=datetime.utcnow(),
                metadata={
                    "outcome_type": "denied",
                    "decision_summary": "Steward will appeal",
                    "appeal_to_next_step": True,
                    "step_type": "step_1_initial",
                },
            ),
            commit=False,
        )
        overview = service.get_overview("hard-case-1")
    assert overview.ai_recommendation is not None
    assert overview.ai_recommendation.get("kind") == "ai_recommendation"
    assert overview.steward_decision is not None
    assert overview.steward_decision.get("kind") == "steward_decision"
    assert overview.recommendation_rationale


def test_jump_to_context_is_bounded_and_read_only():
    db = MagicMock()
    case = _case()
    event = CaseTimelineEventRecord(
        id=3,
        event_uuid="evt-1",
        case_id=1,
        case_uuid="hard-case-1",
        event_type="analysis_report_saved_and_printed",
        event_timestamp=datetime(2026, 1, 3, tzinfo=timezone.utc),
        title="Analysis Report v1 saved and printed",
        details="Official",
        report_version_number=1,
        export_ref="art-1",
        follow_up_message_ids=[10, 11],
        created_at=datetime.utcnow(),
    )
    neighbor = CaseTimelineEventRecord(
        id=4,
        event_uuid="evt-2",
        case_id=1,
        case_uuid="hard-case-1",
        event_type="management_response_uploaded",
        event_timestamp=datetime(2026, 1, 4, tzinfo=timezone.utc),
        title="Management response uploaded",
        details=None,
        upload_refs=["asset-mgmt"],
        created_at=datetime.utcnow(),
    )
    msg_rows = [
        SimpleNamespace(
            id=10,
            role="user",
            content="x" * 800,
            created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        ),
        SimpleNamespace(
            id=11,
            role="assistant",
            content="short",
            created_at=datetime(2026, 1, 2, 1, tzinfo=timezone.utc),
        ),
    ]

    def _query(model):
        if model is CaseTimelineEventRecord:
            # first() for selected event, all() for siblings
            stub = _QueryStub(first=event, all_rows=[event, neighbor])
            return stub
        if model.__name__ == "CaseMessage":
            return _QueryStub(all_rows=msg_rows)
        if model.__name__ == "CaseSavedArtifact":
            return _QueryStub(
                first=SimpleNamespace(
                    artifact_uuid="art-1",
                    artifact_type="analysis_report",
                    title="Analysis Report v1",
                    version_number=1,
                    version_label="Analysis Report v1",
                    grievance_step="step_1_initial",
                    printed=True,
                    pdf_asset_uuid="pdf-1",
                    is_latest_official=True,
                    key_summary_json={"primary_issue": "leave"},
                )
            )
        if model is CaseMemoryRecord:
            return _QueryStub(first=_memory_row())
        return _QueryStub()

    service = CaseHistoryContextService(db)
    with patch.object(CaseService, "_get_case_row", return_value=case):
        db.query.side_effect = _query
        with patch.object(
            CaseMemoryService,
            "load",
            return_value={
                "decisions": [],
                "recommendations": {
                    "current": {
                        "recommendation": "Proceed",
                        "kind": "ai_recommendation",
                        "status": "current",
                    },
                    "history": [],
                },
            },
        ):
            ctx = service.jump_to_context("hard-case-1", "evt-1", conversation_window=4)

    assert ctx.mutates_current_memory is False
    assert ctx.related_artifact["artifact_uuid"] == "art-1"
    assert ctx.related_conversation.full_transcript_replayed is False
    assert ctx.related_conversation.bounded is True
    assert len(ctx.related_conversation.messages[0]["content"]) <= 501
    assert ctx.next_event["event_id"] == "evt-2"
    assert ctx.record_class == "official_record"


def test_jump_to_context_case_isolation():
    db = MagicMock()
    with patch.object(CaseService, "_get_case_row", return_value=None):
        with pytest.raises(Exception):
            CaseHistoryContextService(db).jump_to_context("other", "evt")


def test_jump_to_context_supports_artifact_only_history_ids():
    db = MagicMock()
    case = _case()
    artifact = SimpleNamespace(
        artifact_uuid="art-only-1",
        artifact_type="analysis_report",
        title="Analysis Report v1",
        version_number=1,
        version_label="Analysis Report v1",
        grievance_step="step_1_initial",
        printed=True,
        pdf_asset_uuid="pdf-1",
        is_latest_official=True,
        key_summary_json={"primary_issue": "leave"},
        saved_at=datetime(2026, 1, 3, tzinfo=timezone.utc),
    )

    def _query(model):
        if model is CaseTimelineEventRecord:
            return _QueryStub(first=None, all_rows=[])
        if model.__name__ == "CaseSavedArtifact":
            return _QueryStub(first=artifact)
        if model.__name__ == "CaseMessage":
            return _QueryStub(all_rows=[])
        return _QueryStub()

    service = CaseHistoryContextService(db)
    with patch.object(CaseService, "_get_case_row", return_value=case):
        db.query.side_effect = _query
        ctx = service.jump_to_context("hard-case-1", "art-only-1")
    assert ctx.mutates_current_memory is False
    assert ctx.related_artifact["artifact_uuid"] == "art-only-1"
    assert ctx.record_class == "official_record"


def test_memory_does_not_embed_full_bodies_from_events():
    db = MagicMock()
    row = _memory_row()
    case = _case()
    service = CaseMemoryService(db)
    with patch.object(CaseService, "_get_case_row", return_value=case):
        db.query.side_effect = lambda model: _QueryStub(first=row)
        memory = service.apply_event(
            CaseDomainEventRecord(
                event_id="body1",
                case_uuid="hard-case-1",
                event_type="analysis_saved_and_printed",
                occurred_at=datetime.utcnow(),
                metadata={
                    "report_version_number": 2,
                    "artifact_uuid": "art-body",
                    "report_summary": {
                        "primary_issue": "Leave",
                        "report_data": {"huge": True},
                        "full_text": "SHOULD_NOT_PERSIST",
                    },
                    "recommendation": "Make whole",
                },
            ),
            commit=False,
        )
    report = memory["reports"]["items"][-1]
    assert "full_text" not in (report.get("report_summary") or {})
    assert "report_data" not in (report.get("report_summary") or {})
    assert "SHOULD_NOT_PERSIST" not in str(memory)


def test_hardening_routes_registered():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    paths = set(client.get("/openapi.json").json()["paths"])
    assert "/cases/{case_uuid}/workflow" in paths
    assert "/cases/{case_uuid}/workflow/transitions" in paths
    assert "/cases/{case_uuid}/domain-events" in paths
    assert "/cases/{case_uuid}/history/{event_id}/context" in paths
