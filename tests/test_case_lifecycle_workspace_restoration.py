"""W4 Case Lifecycle and Workspace Restoration tests."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.schemas.saved_case_schema import SavedCaseSummary
from app.services.case_service import (
    AI_CONTEXT_RECENT_MESSAGE_LIMIT,
    AI_CONTEXT_SOURCE_GROUNDING_LIMIT,
    CaseService,
)
from app.services.case_step_progression_persistence_service import (
    CaseStepProgressionPersistenceService,
)
from app.services.case_step_progression_service import CaseStepProgressionError
from app.services.follow_up_chat_service import FollowUpChatService
from app.services.saved_case_service import SavedCaseService


def _summary(**overrides) -> SavedCaseSummary:
    base = dict(
        case_id=1,
        case_uuid="case-1",
        title="Case",
        workspace_status="open",
        legacy_case_status="open",
        has_step_progression=True,
        available_actions=["open_case", "view_timeline"],
    )
    base.update(overrides)
    return SavedCaseSummary(**base)


def _message(role, content, created_at=None, metadata=None, index=0):
    return SimpleNamespace(
        id=index + 1,
        role=role,
        content=content,
        created_at=created_at or datetime(2026, 1, 1, tzinfo=timezone.utc),
        message_metadata=metadata,
    )


def test_create_case_initializes_progression_transactionally():
    db = MagicMock()
    ensure = MagicMock(return_value=SimpleNamespace(current_step_type="step_1_initial"))

    with patch(
        "app.services.case_step_progression_persistence_service."
        "CaseStepProgressionPersistenceService.ensure_case_progression",
        ensure,
    ):
        case = CaseService.create_case(db, question="Can leave be canceled?")

    assert case.initial_question == "Can leave be canceled?"
    assert case.status == "open"
    db.add.assert_called()
    db.flush.assert_called()
    ensure.assert_called_once()
    assert ensure.call_args.kwargs.get("commit") is False
    db.commit.assert_called_once()
    db.refresh.assert_called_once()


def test_ensure_case_progression_is_idempotent():
    service = CaseStepProgressionPersistenceService(MagicMock())
    state = SimpleNamespace(current_step_type="step_1_initial")
    with (
        patch.object(service, "_has_progression", return_value=True),
        patch.object(service, "_build_progression_state", return_value=state) as build,
        patch.object(service, "create_case_progression") as create,
    ):
        result = service.ensure_case_progression("case-1")

    assert result is state
    build.assert_called_once_with("case-1")
    create.assert_not_called()


def test_create_case_progression_rejects_duplicates():
    service = CaseStepProgressionPersistenceService(MagicMock())
    with patch.object(service, "_has_progression", return_value=True):
        with pytest.raises(CaseStepProgressionError):
            service.create_case_progression("case-1")


def test_build_analysis_question_bounds_recent_messages():
    messages = [_message("user", f"turn-{i}", index=i) for i in range(20)]
    case = SimpleNamespace(
        initial_question="Root question",
        known_facts={"a": 1},
        messages=messages,
        report_versions=[
            SimpleNamespace(
                version_number=2,
                report_summary={"primary_issue": "Leave cancellation"},
            )
        ],
    )
    text = CaseService.build_analysis_question(case, recent_message_limit=4)
    assert "Root question" in text
    assert "Current analysis summary: Leave cancellation" in text
    assert "turn-19" in text
    assert "turn-16" in text
    assert "turn-0" not in text
    assert text.count("user:") == 4


def test_build_bounded_ai_context_caps_messages_and_keeps_facts():
    messages = [_message("user", f"m-{i}", index=i) for i in range(15)]
    case = SimpleNamespace(
        case_uuid="c1",
        title="T",
        status="open",
        initial_question="Initial?",
        known_facts={"approved": True},
        user_name=None,
        local_number=None,
        messages=messages,
        report_versions=[
            SimpleNamespace(version_number=1, report_summary={"primary_issue": "Issue"})
        ],
        assets=[],
    )
    ctx = CaseService.build_bounded_ai_context(case, recent_message_limit=5)
    assert ctx["initial_question"] == "Initial?"
    assert ctx["known_facts"]["approved"] is True
    assert ctx["message_count_total"] == 15
    assert len(ctx["recent_messages"]) == 5
    assert ctx["recent_messages"][0]["content"] == "m-10"
    assert "trusted_system_note" in ctx
    assert ctx["report_summary"]["primary_issue"] == "Issue"


def test_prior_followups_are_bounded():
    case = SimpleNamespace(
        messages=[
            _message(
                "user",
                f"q-{i}",
                metadata={"intent": "follow_up"},
                index=i,
            )
            for i in range(10)
        ]
    )
    prior = FollowUpChatService._prior_followups(case, limit=3)
    assert len(prior) == 3
    assert prior[0]["content"] == "q-7"
    assert prior[-1]["content"] == "q-9"


def test_workspace_empty_progression_shape():
    created = datetime(2026, 1, 1, tzinfo=timezone.utc)
    case = SimpleNamespace(
        id=1,
        case_uuid="empty-case",
        title="Empty",
        user_name=None,
        local_number=None,
        initial_question="Q?",
        known_facts={},
        status="open",
        created_at=created,
        updated_at=created,
        messages=[],
        report_versions=[],
        assets=[],
    )
    db = MagicMock()
    from app.services.case_step_progression_service import CaseStepProgressionNotFoundError

    with (
        patch.object(CaseService, "get_case", return_value=case),
        patch.object(CaseService, "get_case_for_workspace", return_value=case),
        patch.object(CaseService, "count_case_messages", return_value=0),
        patch.object(CaseService, "fetch_recent_case_messages", return_value=[]),
        patch.object(CaseService, "fetch_durable_conversation_signals", return_value=[]),
        patch(
            "app.services.case_step_progression_persistence_service."
            "CaseStepProgressionPersistenceService.get_progression",
            side_effect=CaseStepProgressionNotFoundError("empty-case"),
        ),
        patch(
            "app.services.case_workspace_action_service.CaseWorkspaceActionService."
            "build_inspection_from_loaded",
            return_value=SimpleNamespace(
                case=case,
                has_analysis_report=False,
                latest_report_version_id=None,
                latest_report_version_number=None,
                has_step_progression=False,
                current_step_type=None,
                template_id=None,
                template_availability_status=None,
                template_available=False,
                case_status="open",
            ),
        ),
        patch(
            "app.services.case_workspace_action_service.CaseWorkspaceActionService."
            "evaluate_action_availability",
            return_value=[],
        ),
        patch(
            "app.services.case_saved_artifact_service.CaseSavedArtifactService."
            "continuity_artifacts",
            return_value=[],
        ),
        patch(
            "app.services.case_saved_artifact_service.CaseSavedArtifactService."
            "list_steward_case_history",
            return_value=SimpleNamespace(
                model_dump=lambda mode="json": {
                    "case_uuid": "empty-case",
                    "label": "Official Case Record",
                    "count": 0,
                    "order": "oldest_first",
                    "events": [],
                }
            ),
        ),
        patch(
            "app.services.case_saved_artifact_service.CaseSavedArtifactService."
            "list_artifacts",
            return_value=SimpleNamespace(artifacts=[]),
        ),
    ):
        workspace = CaseService.get_case_workspace(db, "empty-case")

    assert workspace["current_analysis"] is None
    assert workspace["analysis_history"] == []
    assert workspace["messages"] == []
    assert workspace["message_count"] == 0
    assert workspace["conversation_history"]["embedded_in_workspace"] is False
    assert workspace["step_progression"]["has_step_progression"] is False
    assert workspace["outcomes"] == []
    assert workspace["draft_summaries"] == []
    assert workspace["timeline"] == []
    assert workspace["available_actions"] == []
    assert workspace["ai_continuity_context"]["message_count_total"] == 0


def test_open_case_ensures_progression_and_returns_workspace():
    summary = _summary(case_uuid="open-1", workspace_status="open")
    case_row = SimpleNamespace(status="open", case_uuid="open-1")
    workspace = {"case_uuid": "open-1", "ai_continuity_context": {}}

    with (
        patch.object(SavedCaseService, "get_saved_case", return_value=summary),
        patch.object(SavedCaseService, "_get_case_row", return_value=case_row),
        patch(
            "app.services.saved_case_service.CaseStepProgressionPersistenceService."
            "ensure_case_progression",
        ) as ensure,
        patch.object(CaseService, "get_case_workspace", return_value=workspace),
    ):
        result = SavedCaseService.open_case(MagicMock(), "open-1")

    ensure.assert_called_once()
    assert result.action_taken == "already_open"
    assert result.workspace == workspace


def test_reopen_does_not_duplicate_progression_when_missing():
    closed_summary = _summary(
        case_uuid="reopen-1",
        workspace_status="closed",
        legacy_case_status="closed",
    )
    open_summary = _summary(
        case_uuid="reopen-1",
        workspace_status="reopened",
        legacy_case_status="open",
    )
    progression = MagicMock()
    progression._has_progression.return_value = False
    workspace = {"case_uuid": "reopen-1"}

    with (
        patch.object(
            SavedCaseService,
            "get_saved_case",
            side_effect=[closed_summary, open_summary],
        ),
        patch.object(CaseService, "reopen_case"),
        patch(
            "app.services.saved_case_service.CaseStepProgressionPersistenceService",
            return_value=progression,
        ),
        patch.object(CaseService, "get_case_workspace", return_value=workspace),
    ):
        result = SavedCaseService.reopen_case(MagicMock(), "reopen-1", source="manual_ui")

    progression.ensure_case_progression.assert_called_once_with("reopen-1")
    progression.reopen_case.assert_not_called()
    assert result.action_taken == "reopened"
    assert result.workspace == workspace


def test_reopen_existing_progression_calls_reopen_once():
    closed_summary = _summary(
        case_uuid="reopen-2",
        workspace_status="closed",
        legacy_case_status="closed",
    )
    open_summary = _summary(
        case_uuid="reopen-2",
        workspace_status="reopened",
        legacy_case_status="open",
    )
    progression = MagicMock()
    progression._has_progression.return_value = True

    with (
        patch.object(
            SavedCaseService,
            "get_saved_case",
            side_effect=[closed_summary, open_summary],
        ),
        patch.object(CaseService, "reopen_case"),
        patch(
            "app.services.saved_case_service.CaseStepProgressionPersistenceService",
            return_value=progression,
        ),
        patch.object(CaseService, "get_case_workspace", return_value={"case_uuid": "reopen-2"}),
    ):
        SavedCaseService.reopen_case(MagicMock(), "reopen-2", reason="resume", source="ai_command")

    progression.ensure_case_progression.assert_called_once_with("reopen-2")
    progression.reopen_case.assert_called_once()


def test_ai_continuity_preserves_known_facts_after_reopen_context_build():
    case = SimpleNamespace(
        case_uuid="cont-1",
        title="Continuity",
        status="open",
        initial_question="Original concern",
        known_facts={"leave_approved": True, "date": "2026-01-02"},
        user_name=None,
        local_number=None,
        messages=[
            _message("user", "They canceled leave."),
            _message("assistant", "Gather approval."),
        ],
        report_versions=[
            SimpleNamespace(
                version_number=3,
                report_summary={"primary_issue": "Leave revocation"},
            )
        ],
        assets=[],
    )
    ctx = CaseService.build_bounded_ai_context(case)
    assert ctx["known_facts"]["leave_approved"] is True
    assert ctx["initial_question"] == "Original concern"
    assert ctx["latest_report_version"] == 3
    assert len(ctx["recent_messages"]) <= AI_CONTEXT_RECENT_MESSAGE_LIMIT


def test_primary_workspace_omits_full_transcript_but_keeps_continuity():
    created = datetime(2026, 1, 1, tzinfo=timezone.utc)
    history = [_message("user", f"old-{i}", index=i) for i in range(8)]
    recent = history[-3:]
    case = SimpleNamespace(
        id=9,
        case_uuid="lean-case",
        title="Lean",
        user_name=None,
        local_number=None,
        initial_question="Root?",
        known_facts={"k": 1},
        status="open",
        created_at=created,
        updated_at=created,
        messages=history,
        report_versions=[
            SimpleNamespace(
                id=1,
                version_number=1,
                trigger_message_id=None,
                created_at=created,
                ranked_authorities=[],
                issue_analysis={},
                evidence_items=[],
                retrieval_gaps={},
                source_coverage_audit=[],
                report_summary={"primary_issue": "Root issue"},
            )
        ],
        assets=[],
    )
    db = MagicMock()
    from app.services.case_step_progression_service import CaseStepProgressionNotFoundError

    with (
        patch.object(CaseService, "get_case_for_workspace", return_value=case),
        patch.object(CaseService, "count_case_messages", return_value=8),
        patch.object(CaseService, "fetch_recent_case_messages", return_value=recent),
        patch.object(
            CaseService,
            "fetch_durable_conversation_signals",
            return_value=[
                {
                    "message_id": 1,
                    "role": "user",
                    "fact_updates": {"leave_approved_in_writing": True},
                    "content_preview": "Old fact outside recent window",
                }
            ],
        ),
        patch(
            "app.services.case_step_progression_persistence_service."
            "CaseStepProgressionPersistenceService.get_progression",
            side_effect=CaseStepProgressionNotFoundError("lean-case"),
        ),
        patch(
            "app.services.case_workspace_action_service.CaseWorkspaceActionService."
            "build_inspection_from_loaded",
            return_value=SimpleNamespace(
                case=case,
                has_analysis_report=True,
                latest_report_version_id=1,
                latest_report_version_number=1,
                has_step_progression=False,
                current_step_type=None,
                template_id=None,
                template_availability_status=None,
                template_available=False,
                case_status="open",
            ),
        ),
        patch(
            "app.services.case_workspace_action_service.CaseWorkspaceActionService."
            "evaluate_action_availability",
            return_value=[],
        ),
        patch(
            "app.services.case_saved_artifact_service.CaseSavedArtifactService."
            "continuity_artifacts",
            return_value=[],
        ),
        patch(
            "app.services.case_saved_artifact_service.CaseSavedArtifactService."
            "list_steward_case_history",
            return_value=SimpleNamespace(
                model_dump=lambda mode="json": {
                    "case_uuid": "lean-case",
                    "label": "Official Case Record",
                    "count": 0,
                    "order": "oldest_first",
                    "events": [],
                }
            ),
        ),
        patch(
            "app.services.case_saved_artifact_service.CaseSavedArtifactService."
            "list_artifacts",
            return_value=SimpleNamespace(artifacts=[]),
        ),
    ):
        workspace = CaseService.get_case_workspace(db, "lean-case")

    assert workspace["messages"] == []
    assert workspace["message_count"] == 8
    assert workspace["conversation_history"]["embedded_in_workspace"] is False
    assert "/cases/lean-case/messages" in workspace["conversation_history"]["retrieval"]["path"]
    assert workspace["ai_continuity_context"]["known_facts"]["k"] == 1
    assert workspace["ai_continuity_context"]["message_count_total"] == 8
    assert len(workspace["ai_continuity_context"]["recent_messages"]) == 3
    assert workspace["ai_continuity_context"]["recent_messages"][0]["content"] == "old-5"
    assert workspace["ai_continuity_context"]["durable_conversation_signals"][0][
        "fact_updates"
    ]["leave_approved_in_writing"] is True
    assert "source_grounding" in workspace["ai_continuity_context"]
    assert "citations" in workspace["ai_continuity_context"]
    assert "draft_state" in workspace["ai_continuity_context"]
    assert "progression_state" in workspace["ai_continuity_context"]
    assert workspace["ai_continuity_context"]["persistence_notes"][
        "full_corpus_embedded"
    ] is False


def test_list_case_messages_is_paginated_and_case_scoped():
    case_a = SimpleNamespace(id=1, case_uuid="case-a")
    rows = [
        SimpleNamespace(
            id=i,
            role="user",
            content=f"a-{i}",
            message_metadata=None,
            created_at=datetime(2026, 1, i + 1, tzinfo=timezone.utc),
        )
        for i in range(1, 6)
    ]
    db = MagicMock()
    query = MagicMock()
    db.query.return_value = query
    query.filter.return_value = query
    query.order_by.return_value = query
    query.offset.return_value = query
    query.limit.return_value = query
    query.count.return_value = 5
    query.all.return_value = rows[1:4]

    with patch.object(CaseService, "_get_case_row", return_value=case_a):
        page = CaseService.list_case_messages(db, "case-a", limit=3, offset=1)

    assert page["case_uuid"] == "case-a"
    assert page["total"] == 5
    assert page["limit"] == 3
    assert page["offset"] == 1
    assert page["count"] == 3
    assert page["has_more"] is True
    assert [m["content"] for m in page["messages"]] == ["a-2", "a-3", "a-4"]
    # Filter must be applied against the case row id (isolation).
    assert query.filter.called


def test_list_case_messages_rejects_missing_case():
    from app.services.case_service import CaseNotFoundError

    with patch.object(CaseService, "_get_case_row", return_value=None):
        with pytest.raises(CaseNotFoundError):
            CaseService.list_case_messages(MagicMock(), "missing")


def test_case_a_cannot_use_case_b_uuid_for_history():
    """History lookup is keyed by case_uuid; wrong uuid yields not-found, not other case data."""
    from app.services.case_service import CaseNotFoundError

    db = MagicMock()
    with patch.object(CaseService, "_get_case_row", return_value=None) as get_row:
        with pytest.raises(CaseNotFoundError):
            CaseService.list_case_messages(db, "case-b")
    get_row.assert_called_once_with(db, "case-b")


def test_reopen_does_not_add_messages_or_regenerate_analysis():
    closed_summary = _summary(
        case_uuid="reopen-clean",
        workspace_status="closed",
        legacy_case_status="closed",
    )
    open_summary = _summary(
        case_uuid="reopen-clean",
        workspace_status="reopened",
        legacy_case_status="open",
    )
    progression = MagicMock()
    progression._has_progression.return_value = True
    add_message = MagicMock()
    generate = MagicMock()

    with (
        patch.object(
            SavedCaseService,
            "get_saved_case",
            side_effect=[closed_summary, open_summary],
        ),
        patch.object(CaseService, "reopen_case") as reopen_legacy,
        patch(
            "app.services.saved_case_service.CaseStepProgressionPersistenceService",
            return_value=progression,
        ),
        patch.object(CaseService, "get_case_workspace", return_value={"case_uuid": "reopen-clean"}),
        patch.object(CaseService, "add_message", add_message),
        patch.object(CaseService, "generate_report_version", generate),
    ):
        SavedCaseService.reopen_case(MagicMock(), "reopen-clean", source="manual_ui")

    reopen_legacy.assert_called_once()
    progression.ensure_case_progression.assert_called_once()
    progression.reopen_case.assert_called_once()
    add_message.assert_not_called()
    generate.assert_not_called()


def test_messages_history_route_is_registered():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    paths = set(client.get("/openapi.json").json()["paths"])
    assert "/cases/{case_uuid}/messages" in paths
    methods = set(client.get("/openapi.json").json()["paths"]["/cases/{case_uuid}/messages"])
    assert "get" in methods
    assert "post" in methods


def _report_version_with_grounding(**overrides):
    created = datetime(2026, 1, 1, tzinfo=timezone.utc)
    base = {
        "id": 11,
        "version_number": 2,
        "trigger_message_id": None,
        "created_at": created,
        "report_data": {
            "report": {
                "quick_assessment": {
                    "summary": "Likely grievable leave revocation",
                    "grievability": "Likely Grievable",
                    "confidence": "Medium",
                },
                "recommended_remedy": {"statements": ["Make steward whole"]},
                "detailed_analysis": {
                    "evidence_to_gather": ["approval record"],
                    "strategic_tips": ["Preserve timeline"],
                },
                "limitations": {"missing_facts": ["exact cancellation time"]},
                "citation_validation": {"status": "passed", "notes": []},
                "key_contract_violations": [
                    {
                        "article_or_section": "Article 10",
                        "issue": "Leave",
                        "role": "union_supporting",
                        "direct_quote": "Annual leave once approved...",
                        "citation": {
                            "document_type": "CONTRACT",
                            "document_name": "National Agreement",
                            "page": 42,
                            "chunk": 7,
                        },
                    }
                ],
                "secondary_issues": ["information request"],
            }
        },
        "ranked_authorities": [
            {
                "document_type": "CIM",
                "document_name": "CIM V6",
                "article_or_section": "Article 10",
                "page": 10,
                "chunk": 3,
                "role": "union_supporting",
                "direct_quote": "CIM leave guidance...",
                "relevance_score": 0.9,
            },
            {
                "document_type": "POLICY_MANUAL",
                "document_name": "Synthetic Future Manual",
                "article_or_section": "§12",
                "page": 2,
                "chunk": 1,
                "role": "background_only",
                "direct_quote": "Generic source type accepted...",
                "relevance_score": 0.4,
            },
        ],
        "issue_analysis": {
            "primary_issue": "Approved leave cancellation",
            "facts_needed": ["written approval"],
        },
        "evidence_items": [
            {
                "document_type": "ELM",
                "document_name": "ELM 55",
                "article_or_section": "512",
                "page": 5,
                "chunk": 2,
                "direct_quote": "ELM excerpt...",
                "what_it_supports": "Leave administration",
            }
        ],
        "retrieval_gaps": {
            "facts_still_needed": ["supervisor name"],
            "missing_source_types": ["LMOU"],
            "unindexed_sources_requested": ["LMOU"],
            "issues_without_supporting_authority": [],
        },
        "source_coverage_audit": [
            {
                "source_type": "ARBITRATION",
                "final_disposition": "rejected_not_indexed",
            }
        ],
        "report_summary": {
            "primary_issue": "Approved leave cancellation",
            "authority_count": 2,
            "has_source_gaps": True,
        },
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_ai_continuity_restores_source_grounding_and_citations():
    version = _report_version_with_grounding()
    case = SimpleNamespace(
        case_uuid="mem-1",
        title="Memory",
        status="open",
        initial_question="Can leave be revoked?",
        known_facts={"approved": True},
        user_name=None,
        local_number="300",
        messages=[_message("user", "Follow-up")],
        report_versions=[version],
        assets=[
            SimpleNamespace(
                asset_uuid="asset-1",
                case_uuid="mem-1",
                asset_category="uploaded_document",
                original_filename="approval.pdf",
                stored_filename="approval.pdf",
                stored_path="data/case_assets/mem-1/approval.pdf",
                mime_type="application/pdf",
                file_size=12,
                sha256="abc",
                uploaded_by="steward",
                source="api",
                version_number=1,
                parent_asset_uuid=None,
                report_version_id=11,
                report_version_number=2,
                draft_record_uuid=None,
                status="active",
                asset_metadata={"description": "Leave approval", "relevance": "core"},
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
        ],
    )
    draft = SimpleNamespace(
        draft_uuid="draft-1",
        step_type="step_2_appeal",
        template_id="local_300_form_79_1",
        draft_version=3,
        draft_status="draft",
        validation_status="incomplete",
        missing_required_field_ids=["grievant_name"],
        steward_override_field_ids=[],
        approval_status=None,
        export_status=None,
        report_version_number=2,
        created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    progression = SimpleNamespace(
        workspace_status="open",
        current_step_type="step_2_appeal",
        steps=[
            SimpleNamespace(
                step_type="step_1_initial",
                step_number=1,
                status="closed",
                is_closed=True,
                was_reopened=False,
                template_id=None,
                template_availability="unconfirmed_pending_steward_confirmation",
                outcomes=[
                    SimpleNamespace(
                        outcome_uuid="out-1",
                        step_type="step_1_initial",
                        outcome_type="denied",
                        decision_summary="Denied at Step 1",
                        decision_date=None,
                        appeal_to_next_step=True,
                        next_step_type="step_2_appeal",
                    )
                ],
            ),
            SimpleNamespace(
                step_type="step_2_appeal",
                step_number=2,
                status="open",
                is_closed=False,
                was_reopened=False,
                template_id="local_300_form_79_1",
                template_availability="available",
                outcomes=[],
            ),
        ],
        form_draft_history=[draft],
    )

    ctx = CaseService.build_bounded_ai_context(
        case,
        progression_state=progression,
        durable_message_signals=[
            {
                "message_id": 99,
                "role": "user",
                "fact_updates": {"cancellation_date": "2026-01-03"},
                "content_preview": "Older correction",
            }
        ],
        available_actions=[{"action": "generate_grievance", "available": False}],
    )

    assert ctx["schema_version"] == "w4_case_memory_v1"
    assert ctx["case_state"]["known_facts"]["approved"] is True
    assert ctx["analysis_state"]["has_current_analysis"] is True
    assert ctx["analysis_state"]["quick_assessment"]["grievability"] == "Likely Grievable"
    source_types = {item["source_type"] for item in ctx["source_grounding"]}
    assert "CONTRACT" in source_types
    assert "CIM" in source_types
    assert "ELM" in source_types
    # Generic extensibility: non-core type accepted without hardcoded branching.
    assert "POLICY_MANUAL" in source_types
    assert "ARBITRATION" in source_types
    assert any(c["document_name"] == "National Agreement" for c in ctx["citations"])
    assert any(c["source_type"] == "POLICY_MANUAL" for c in ctx["citations"])
    assert ctx["evidence_assets"][0]["asset_uuid"] == "asset-1"
    assert ctx["evidence_assets"][0]["content_embedded"] is False
    assert ctx["draft_state"]["has_drafts"] is True
    assert ctx["draft_state"]["drafts"][0]["template_id"] == "local_300_form_79_1"
    assert ctx["draft_state"]["drafts"][0]["draft_version"] == 3
    assert ctx["draft_state"]["drafts"][0]["field_state_persisted"] is False
    assert ctx["draft_state"]["drafts"][0]["populated_field_state"] is None
    assert ctx["draft_state"]["drafts"][0]["regenerated_on_reopen"] is False
    assert ctx["progression_state"]["current_step_type"] == "step_2_appeal"
    assert ctx["progression_state"]["outcomes"][0]["decision_summary"] == "Denied at Step 1"
    assert ctx["unresolved_items"]["facts_still_needed"] == ["supervisor name"]
    assert ctx["durable_conversation_signals"][0]["fact_updates"]["cancellation_date"] == (
        "2026-01-03"
    )
    assert ctx["persistence_notes"]["full_corpus_embedded"] is False
    assert ctx["persistence_notes"]["source_chunk_pk_persisted"] is False
    assert ctx["persistence_notes"]["source_types_are_generic"] is True
    assert ctx["persistence_notes"]["template_model_is_generic"] is True
    assert ctx["persistence_notes"]["important_decisions_survive_recent_window"] is True
    # Continuity package must not hardcode only NA/CIM/ELM as allowed types.
    assert "future authorized types" in ctx["trusted_system_note"]
    assert ctx["evidence"] is ctx["evidence_assets"]
    assert ctx["workflow_state"] is ctx["progression_state"]
    assert ctx["analysis_state"]["analytical_conclusions"]["grievability"] == (
        "Likely Grievable"
    )
    assert ctx["analysis_state"]["missing_evidence"]
    assert any(
        d["kind"] == "step_outcome" and d["decision_summary"] == "Denied at Step 1"
        for d in ctx["important_historical_decisions"]
    )
    assert any(
        d["kind"] == "durable_conversation_signal"
        for d in ctx["important_historical_decisions"]
    )


def test_continuity_package_does_not_embed_full_corpus_or_transcript():
    version = _report_version_with_grounding()
    case = SimpleNamespace(
        case_uuid="mem-2",
        title="T",
        status="open",
        initial_question="Q",
        known_facts={},
        user_name=None,
        local_number=None,
        messages=[_message("user", f"m-{i}", index=i) for i in range(30)],
        report_versions=[version],
        assets=[],
    )
    ctx = CaseService.build_bounded_ai_context(case, recent_message_limit=4)
    assert len(ctx["recent_messages"]) == 4
    assert len(ctx["source_grounding"]) <= AI_CONTEXT_SOURCE_GROUNDING_LIMIT
    assert all("full_text" not in item for item in ctx["source_grounding"])
    assert ctx["persistence_notes"]["full_transcript_embedded"] is False


def test_case_isolation_continuity_uses_only_attached_case_versions():
    foreign_version = _report_version_with_grounding(
        ranked_authorities=[
            {
                "document_type": "CONTRACT",
                "document_name": "OTHER CASE ONLY",
                "page": 1,
                "chunk": 1,
                "role": "union_supporting",
                "direct_quote": "should not leak",
            }
        ]
    )
    case_a = SimpleNamespace(
        case_uuid="case-a",
        title="A",
        status="open",
        initial_question="A?",
        known_facts={"a": 1},
        user_name=None,
        local_number=None,
        messages=[],
        report_versions=[],  # no analysis for A
        assets=[],
    )
    ctx = CaseService.build_bounded_ai_context(case_a)
    assert ctx["source_grounding"] == []
    assert ctx["citations"] == []
    assert foreign_version.ranked_authorities[0]["document_name"] == "OTHER CASE ONLY"


def test_future_source_types_fit_without_branching_logic():
    version = _report_version_with_grounding(
        ranked_authorities=[
            {
                "source_id": "synth_arb_2024_001",
                "document_type": "ARBITRATION",
                "document_name": "Synthetic Arbitration Award",
                "article_or_section": "Award §III",
                "page": 4,
                "chunk": 2,
                "role": "union_supporting",
                "direct_quote": "Management must honor approved leave...",
                "relevance_score": 0.88,
                "jurisdiction": "National",
                "version_or_effective_date": "2024-06-01",
                "retrieval_relationship": "embedding_retrieval",
            },
            {
                "source_id": "synth_supervisor_manual",
                "document_type": "SUPERVISOR_MANUAL",
                "document_name": "Synthetic Supervisor Manual",
                "page": 1,
                "chunk": 0,
                "role": "background_only",
                "direct_quote": "Procedural guidance only...",
                "relevance_score": 0.3,
            },
        ]
    )
    case = SimpleNamespace(
        case_uuid="ext-src",
        title="Ext",
        status="open",
        initial_question="Q",
        known_facts={},
        user_name=None,
        local_number=None,
        messages=[],
        report_versions=[version],
        assets=[],
    )
    ctx = CaseService.build_bounded_ai_context(case)
    source_types = {item["source_type"] for item in ctx["source_grounding"]}
    assert "ARBITRATION" in source_types
    assert "SUPERVISOR_MANUAL" in source_types
    arb = next(
        item
        for item in ctx["source_grounding"]
        if item.get("source_identifier") == "synth_arb_2024_001"
    )
    assert arb["source_type"] == "ARBITRATION"
    assert arb["jurisdiction"] == "National"
    assert arb["version_or_effective_date"] == "2024-06-01"
    assert arb["retrieval_relationship"] == "embedding_retrieval"


def test_future_template_types_fit_draft_continuity_model():
    case = SimpleNamespace(
        case_uuid="ext-tpl",
        title="T",
        status="open",
        initial_question="Q",
        known_facts={},
        user_name=None,
        local_number=None,
        messages=[],
        report_versions=[],
        assets=[],
    )
    # Real progression schema uses draft_id / validation_status (not draft_uuid).
    draft = SimpleNamespace(
        draft_id="draft-step3",
        step_type="step_3_appeal",
        template_id="future_step_3_form",
        template_version="1.0",
        draft_version=1,
        validation_status="incomplete",
        missing_required_field_ids=["issue_statement"],
        steward_override_field_ids=["local_number"],
        approval_status=None,
        export_status=None,
        report_version_number=None,
        created_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
    )
    progression = SimpleNamespace(
        workspace_status="open",
        current_step_type="step_3_appeal",
        steps=[
            SimpleNamespace(
                step_type="step_3_appeal",
                step_number=3,
                status="open",
                is_closed=False,
                was_reopened=False,
                template_id="future_step_3_form",
                template_availability="deferred_separate_form_required",
                outcomes=[],
            )
        ],
        form_draft_history=[draft],
        timeline=[],
    )
    ctx = CaseService.build_bounded_ai_context(case, progression_state=progression)
    assert ctx["draft_state"]["drafts"][0]["template_id"] == "future_step_3_form"
    assert ctx["draft_state"]["drafts"][0]["draft_uuid"] == "draft-step3"
    assert ctx["draft_state"]["drafts"][0]["grievance_step"] == "step_3_appeal"
    assert ctx["draft_state"]["drafts"][0]["template_version"] == "1.0"
    assert ctx["draft_state"]["drafts"][0]["populated_field_state"] is None
    assert ctx["draft_state"]["drafts"][0]["steward_edits"]["override_field_ids"] == [
        "local_number"
    ]
    assert ctx["workflow_state"]["current_step_type"] == "step_3_appeal"


def test_important_historical_decisions_survive_beyond_recent_window():
    case = SimpleNamespace(
        case_uuid="dec-1",
        title="Decisions",
        status="open",
        initial_question="Root",
        known_facts={"leave_approved": True},
        user_name=None,
        local_number=None,
        messages=[_message("user", "recent only", index=99)],
        report_versions=[],
        assets=[],
    )
    progression = SimpleNamespace(
        workspace_status="reopened",
        current_step_type="step_2_appeal",
        steps=[
            SimpleNamespace(
                step_type="step_1_initial",
                step_number=1,
                status="closed",
                is_closed=True,
                was_reopened=False,
                template_id=None,
                template_availability=None,
                outcomes=[
                    SimpleNamespace(
                        outcome_id="out-old",
                        step_type="step_1_initial",
                        outcome_type="denied",
                        decision_summary="Older Step 1 denial outside chat window",
                        decision_date="2025-12-01",
                        appeal_requested=True,
                        next_step_target="step_2_appeal",
                    )
                ],
            )
        ],
        form_draft_history=[],
        timeline=[
            SimpleNamespace(
                event_type="case_reopened",
                step_type=None,
                title="Case reopened",
                details="Steward resumed after months",
                event_timestamp=datetime(2026, 3, 1, tzinfo=timezone.utc),
            )
        ],
    )
    ctx = CaseService.build_bounded_ai_context(
        case,
        progression_state=progression,
        recent_message_limit=1,
        durable_message_signals=[
            {
                "message_id": 1,
                "role": "user",
                "fact_updates": {"written_approval_found": True},
                "content_preview": "Ancient fact update",
                "created_at": "2025-11-01T00:00:00+00:00",
            }
        ],
    )
    assert len(ctx["recent_messages"]) == 1
    summaries = [d.get("decision_summary") for d in ctx["important_historical_decisions"]]
    assert "Older Step 1 denial outside chat window" in summaries
    assert any(d.get("kind") == "timeline_event" for d in ctx["important_historical_decisions"])
    assert any(
        d.get("kind") == "durable_conversation_signal"
        and d.get("fact_updates", {}).get("written_approval_found") is True
        for d in ctx["important_historical_decisions"]
    )


def test_workspace_restore_reuses_loaded_case_without_inspect_reload():
    created = datetime(2026, 1, 1, tzinfo=timezone.utc)
    case = SimpleNamespace(
        id=3,
        case_uuid="reuse-1",
        title="Reuse",
        user_name=None,
        local_number=None,
        initial_question="Q?",
        known_facts={},
        status="open",
        created_at=created,
        updated_at=created,
        messages=[],
        report_versions=[],
        assets=[],
    )
    db = MagicMock()
    from app.services.case_step_progression_service import CaseStepProgressionNotFoundError

    with (
        patch.object(CaseService, "get_case_for_workspace", return_value=case),
        patch.object(CaseService, "count_case_messages", return_value=0),
        patch.object(CaseService, "fetch_recent_case_messages", return_value=[]),
        patch.object(CaseService, "fetch_durable_conversation_signals", return_value=[]),
        patch(
            "app.services.case_step_progression_persistence_service."
            "CaseStepProgressionPersistenceService.get_progression",
            side_effect=CaseStepProgressionNotFoundError("reuse-1"),
        ),
        patch(
            "app.services.case_workspace_action_service.CaseWorkspaceActionService."
            "build_inspection_from_loaded",
            return_value=SimpleNamespace(
                case=case,
                has_analysis_report=False,
                latest_report_version_id=None,
                latest_report_version_number=None,
                has_step_progression=False,
                current_step_type=None,
                template_id=None,
                template_availability_status=None,
                template_available=False,
                case_status="open",
            ),
        ) as build_inspect,
        patch(
            "app.services.case_workspace_action_service.CaseWorkspaceActionService."
            "_inspect_workspace",
        ) as inspect_reload,
        patch(
            "app.services.case_workspace_action_service.CaseWorkspaceActionService."
            "evaluate_action_availability",
            return_value=[],
        ),
        patch(
            "app.services.case_saved_artifact_service.CaseSavedArtifactService."
            "continuity_artifacts",
            return_value=[],
        ),
        patch(
            "app.services.case_saved_artifact_service.CaseSavedArtifactService."
            "list_steward_case_history",
            return_value=SimpleNamespace(
                model_dump=lambda mode="json": {
                    "case_uuid": "reuse-1",
                    "events": [],
                    "count": 0,
                    "label": "Official Case Record",
                    "order": "oldest_first",
                }
            ),
        ),
        patch(
            "app.services.case_saved_artifact_service.CaseSavedArtifactService."
            "list_artifacts",
            return_value=SimpleNamespace(artifacts=[]),
        ),
    ):
        CaseService.get_case_workspace(db, "reuse-1")

    build_inspect.assert_called_once()
    inspect_reload.assert_not_called()


def test_bounded_ai_context_section_contract():
    case = SimpleNamespace(
        case_uuid="sections",
        title="S",
        status="open",
        initial_question="Q",
        known_facts={},
        user_name=None,
        local_number=None,
        messages=[],
        report_versions=[],
        assets=[],
    )
    ctx = CaseService.build_bounded_ai_context(case)
    for key in (
        "case_state",
        "continuity_summary",
        "analysis_state",
        "source_grounding",
        "citations",
        "evidence",
        "draft_state",
        "workflow_state",
        "unresolved_items",
        "recent_messages",
        "important_historical_decisions",
    ):
        assert key in ctx
    assert ctx["limits"]["recent_message_limit"] == AI_CONTEXT_RECENT_MESSAGE_LIMIT
    assert ctx["persistence_notes"]["full_transcript_embedded"] is False
    assert ctx["persistence_notes"]["full_corpus_embedded"] is False
    assert ctx["persistence_notes"]["full_artifact_bodies_embedded"] is False
    assert "official_artifacts" in ctx


def test_follow_up_grounding_consumes_restored_case_memory():
    """Opening continuity must be what the AI interaction grounding consumes."""
    version = _report_version_with_grounding()
    case = SimpleNamespace(
        case_uuid="wire-1",
        title="Wired",
        status="open",
        initial_question="Leave canceled?",
        known_facts={"approved": True},
        user_name=None,
        local_number=None,
        messages=[
            _message(
                "assistant",
                "Older conclusion outside recent window",
                metadata={
                    "intent": "follow_up",
                    "answer_type": "remedy",
                    "conversational_meaning": {
                        "problem_discussed": "leave cancellation remedy",
                        "conclusion_reached": "Make steward whole",
                        "evidence_referenced": ["Article 10"],
                        "unresolved_questions": ["supervisor name"],
                    },
                },
                index=0,
            )
        ],
        report_versions=[version],
        assets=[],
        id=7,
    )
    restored = {
        "schema_version": "w4_case_memory_v1",
        "case_state": {"known_facts": {"approved": True}},
        "known_facts": {"approved": True},
        "continuity_summary": {"primary_issue": "Leave"},
        "important_historical_decisions": [{"kind": "step_outcome", "decision_summary": "Denied"}],
        "durable_conversation_signals": [{"message_id": 1, "fact_updates": {"x": 1}}],
        "official_artifacts": [
            {
                "artifact_uuid": "a1",
                "artifact_type": "analysis_report",
                "version": 1,
                "is_latest_official": False,
                "content_embedded": False,
            },
            {
                "artifact_uuid": "a2",
                "artifact_type": "analysis_report",
                "version": 2,
                "is_latest_official": True,
                "content_embedded": False,
            },
        ],
        "official_artifact_index": [
            {"artifact_uuid": "a1", "version": 1, "artifact_type": "analysis_report"},
            {"artifact_uuid": "a2", "version": 2, "artifact_type": "analysis_report"},
        ],
        "official_artifact_count": 2,
        "latest_official_report": {"artifact_uuid": "a2", "version": 2},
        "latest_official_grievance": None,
        "retrieved_case_memory": {
            "messages": [],
            "conversational_meaning": [
                {"problem_discussed": "leave cancellation remedy"}
            ],
            "official_artifacts": [],
            "comparison": None,
            "full_transcript_replayed": False,
        },
        "workflow_state": {"workspace_status": "open"},
        "draft_state": {"has_drafts": False},
        "evidence_assets": [],
        "ai_context_restored": True,
        "restore_action_required": False,
    }
    grounding = FollowUpChatService.build_grounding_package(
        case,
        version,
        restored_case_context=restored,
    )
    assert grounding["ai_context_restored"] is True
    assert grounding["case_is_system_of_record"] is True
    assert grounding["known_facts"]["approved"] is True
    assert grounding["official_artifact_count"] == 2
    assert len(grounding["official_artifact_index"]) == 2
    assert grounding["retrieved_case_memory"]["full_transcript_replayed"] is False
    assert grounding["important_historical_decisions"][0]["decision_summary"] == "Denied"


def test_answer_follow_up_builds_restored_context_before_llm():
    version = _report_version_with_grounding()
    case = SimpleNamespace(
        case_uuid="ans-1",
        title="A",
        status="open",
        initial_question="Q",
        known_facts={"k": 1},
        user_name=None,
        local_number=None,
        messages=[],
        report_versions=[version],
        assets=[],
        id=3,
    )
    captured = {}

    def fake_llm(question, grounding):
        captured["grounding"] = grounding
        return {
            "answer": "Use the restored case memory.",
            "answer_type": "fact",
            "citations": [],
            "disclosures": [],
            "facts_needed": [],
            "requires_report_regen": False,
            "suggested_actions": [],
        }

    with (
        patch.object(CaseService, "get_case_for_chat", return_value=case),
        patch.object(CaseService, "get_grounding_report_version", return_value=version),
        patch.object(
            CaseService,
            "build_restored_interaction_context",
            return_value={
                "known_facts": {"k": 1},
                "official_artifact_index": [{"artifact_uuid": "x", "version": 1}],
                "official_artifacts": [],
                "official_artifact_count": 1,
                "important_historical_decisions": [],
                "durable_conversation_signals": [],
                "retrieved_case_memory": {"full_transcript_replayed": False},
                "workflow_state": {},
                "draft_state": {},
                "evidence_assets": [],
                "case_state": {},
                "continuity_summary": {},
                "ai_context_restored": True,
            },
        ) as restore,
        patch.object(
            CaseService,
            "add_follow_up_exchange",
            return_value=(
                SimpleNamespace(id=1, role="user", content="hi", message_metadata={}),
                SimpleNamespace(id=2, role="assistant", content="ok", message_metadata={}),
            ),
        ),
    ):
        FollowUpChatService.answer_follow_up(
            MagicMock(),
            "ans-1",
            "What were we working on?",
            llm_callable=fake_llm,
        )

    restore.assert_called_once()
    assert captured["grounding"]["ai_context_restored"] is True
    assert captured["grounding"]["official_artifact_count"] == 1


def test_conversational_meaning_persisted_on_follow_up_exchange():
    answer = SimpleNamespace(
        answer="Gather the written approval and pursue make-whole relief.",
        answer_type="remedy",
        citations=[
            SimpleNamespace(
                model_dump=lambda: {
                    "document_type": "CONTRACT",
                    "document_name": "NA",
                    "article_or_section": "Article 10",
                    "page": 1,
                    "quote": "approved leave",
                }
            )
        ],
        disclosures=[],
        facts_needed=["supervisor name"],
        requires_report_regen=False,
        suggested_actions=["generate_grievance"],
    )
    version = SimpleNamespace(id=11, version_number=2)
    meaning = CaseService.build_conversational_meaning(
        question="What remedy should we seek for canceled leave?",
        answer=answer,
        report_version=version,
    )
    assert "canceled leave" in meaning["problem_discussed"].lower()
    assert "Article 10" in meaning["evidence_referenced"]
    assert meaning["decision_made"]["answer_type"] == "remedy"
    assert meaning["report_resulted"]["linked_report_version_number"] == 2
    assert meaning["unresolved_questions"] == ["supervisor name"]
    assert meaning["accepted"] is True

    case = SimpleNamespace(id=1, case_uuid="m1", updated_at=None)
    db = MagicMock()
    with patch.object(CaseService, "_get_case_row", return_value=case):
        CaseService.add_follow_up_exchange(
            db,
            "m1",
            "What remedy should we seek for canceled leave?",
            answer,
            version,
        )
    added = [c.args[0] for c in db.add.call_args_list]
    assistant = next(m for m in added if getattr(m, "role", None) == "assistant")
    assert assistant.message_metadata["conversational_meaning"]["problem_discussed"]
    assert assistant.message_metadata["conversational_meaning"]["evidence_referenced"]


def test_retrieve_relevant_case_memory_finds_older_conversation_and_versions():
    old = _message(
        "user",
        "We discussed the leave cancellation evidence packet last month",
        metadata={
            "intent": "follow_up",
            "conversational_meaning": {
                "problem_discussed": "leave cancellation evidence packet",
                "conclusion_reached": "Need written approval",
                "evidence_referenced": ["approval.pdf"],
            },
        },
        index=1,
    )
    recent = _message("user", "ok", index=20)
    case = SimpleNamespace(
        case_uuid="ret-1",
        id=5,
        messages=[old, recent],
        report_versions=[
            SimpleNamespace(
                version_number=1,
                report_summary={"primary_issue": "leave cancellation"},
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
            SimpleNamespace(
                version_number=2,
                report_summary={"primary_issue": "leave cancellation remedy"},
                created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            ),
        ],
    )
    index = [
        {
            "artifact_uuid": "g1",
            "artifact_type": "grievance_form",
            "title": "Step 2 Grievance v1",
            "version": 1,
            "version_label": "Step 2 Grievance v1",
        },
        {
            "artifact_uuid": "g2",
            "artifact_type": "grievance_form",
            "title": "Step 2 Grievance v2",
            "version": 2,
            "version_label": "Step 2 Grievance v2",
        },
    ]
    compare_payload = SimpleNamespace(
        model_dump=lambda mode="json": {
            "left": {"version_number": 1},
            "right": {"version_number": 2},
            "changed_summary_keys": ["key_field_values"],
        }
    )
    with (
        patch(
            "app.services.case_saved_artifact_service.CaseSavedArtifactService."
            "official_artifact_index",
            return_value=index,
        ),
        patch(
            "app.services.case_saved_artifact_service.CaseSavedArtifactService."
            "compare_artifacts",
            return_value=compare_payload,
        ),
    ):
        memory = CaseService.retrieve_relevant_case_memory(
            MagicMock(),
            case,
            "What changed between grievance v1 and v2 for leave cancellation?",
        )
    assert memory["full_transcript_replayed"] is False
    assert any("leave cancellation" in (m["content"] or "").lower() for m in memory["messages"])
    assert memory["conversational_meaning"]
    assert memory["comparison"]["changed_summary_keys"] == ["key_field_values"]
    assert any(a["version"] == 2 for a in memory["official_artifacts"])


def test_official_artifact_index_lists_all_versions_without_bodies():
    from app.services.case_saved_artifact_service import CaseSavedArtifactService

    rows = [
        SimpleNamespace(
            artifact_uuid="r1",
            artifact_type="analysis_report",
            title="Analysis Report v1",
            version_number=1,
            version_label="Analysis Report v1",
            grievance_step="step_2_appeal",
            saved_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            printed=True,
            is_latest_official=False,
            template_id=None,
            content_json={"huge": "body"},
        ),
        SimpleNamespace(
            artifact_uuid="r2",
            artifact_type="analysis_report",
            title="Analysis Report v2",
            version_number=2,
            version_label="Analysis Report v2",
            grievance_step="step_2_appeal",
            saved_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            printed=True,
            is_latest_official=True,
            template_id=None,
            content_json={"huge": "body2"},
        ),
    ]
    service = CaseSavedArtifactService(MagicMock())
    query = MagicMock()
    service.db.query.return_value = query
    query.filter.return_value = query
    query.order_by.return_value = query
    query.all.return_value = rows
    with patch.object(service, "_require_case", return_value=SimpleNamespace(id=1)):
        index = service.official_artifact_index("case-x")
    assert len(index) == 2
    assert [item["version"] for item in index] == [1, 2]
    assert all(item["content_embedded"] is False for item in index)
    assert "huge" not in str(index)


def test_compare_artifacts_across_versions():
    from app.schemas.case_saved_artifact_schema import CaseSavedArtifactDetail
    from app.services.case_saved_artifact_service import CaseSavedArtifactService

    left = CaseSavedArtifactDetail(
        artifact_uuid="g1",
        case_uuid="c1",
        artifact_type="grievance_form",
        title="Step 2 Grievance v1",
        version_number=1,
        version_label="Step 2 Grievance v1",
        printed=True,
        pdf_status="ready",
        is_latest_official=False,
        saved_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        key_summary={"key_field_values": {"remedy": "make whole"}, "field_count": 3},
        content_json={"field_values": {"remedy": "make whole"}},
    )
    right = CaseSavedArtifactDetail(
        artifact_uuid="g2",
        case_uuid="c1",
        artifact_type="grievance_form",
        title="Step 2 Grievance v2",
        version_number=2,
        version_label="Step 2 Grievance v2",
        printed=True,
        pdf_status="ready",
        is_latest_official=True,
        saved_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        key_summary={
            "key_field_values": {"remedy": "make whole plus overtime"},
            "field_count": 4,
        },
        content_json={"field_values": {"remedy": "make whole plus overtime"}},
    )
    service = CaseSavedArtifactService(MagicMock())
    with (
        patch.object(service, "get_artifact", side_effect=[left, right]),
    ):
        result = service.compare_artifacts("c1", "g1", "g2")
    assert result.version_delta == 1
    assert "key_field_values" in result.changed_summary_keys
    assert result.left.version_number == 1
    assert result.right.version_number == 2


def test_settle_and_reopen_preserve_artifacts_and_history():
    from app.services.case_step_progression_persistence_service import (
        CaseStepProgressionPersistenceService,
    )

    timeline = []

    def append_event(case, *, event_type, title, **kwargs):
        timeline.append({"event_type": event_type, "title": title})

    service = CaseStepProgressionPersistenceService(MagicMock())
    state_open = SimpleNamespace(
        workspace_status="open",
        current_step_type="step_2_appeal",
    )
    state_settled = SimpleNamespace(
        workspace_status="settled",
        current_step_type="step_2_appeal",
    )
    with (
        patch.object(
            service,
            "_get_case_row",
            return_value=SimpleNamespace(id=1, case_uuid="life-1"),
        ),
        patch.object(
            service,
            "get_progression",
            side_effect=[
                state_open,  # settle start
                state_settled,  # settle return
                state_settled,  # reopen start
                state_open,  # reopen return
            ],
        ),
        patch.object(service, "_append_timeline_event", side_effect=append_event),
    ):
        settled = service.settle_case("life-1", reason="settled at step 2")
        assert settled.workspace_status == "settled"
        reopened = service.reopen_case("life-1", source="manual_ui")
        assert reopened.workspace_status == "open"

    assert any(e["event_type"] == "case_settled" for e in timeline)
    assert any(e["title"] == "Case reopened" for e in timeline)


def test_close_settle_archive_never_delete_via_status_helpers():
    case = SimpleNamespace(case_uuid="keep-1", status="open", updated_at=None)
    db = MagicMock()
    with patch.object(CaseService, "_get_case_row", return_value=case):
        CaseService.settle_case(db, "keep-1")
        assert case.status == "settled"
        CaseService.archive_case(db, "keep-1")
        assert case.status == "archived"
        CaseService.reopen_case(db, "keep-1")
        assert case.status == "open"
    assert db.delete.call_count == 0


def test_official_print_requires_save_without_working_draft_flag():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    case_uuid = "11111111-1111-1111-1111-111111111111"
    with patch(
        "app.api.routes.exports.CaseSavedArtifactService.find_official_pdf_for_report_version",
        return_value=None,
    ):
        response = client.get(f"/cases/{case_uuid}/export/pdf")
    assert response.status_code == 409
    assert "Save and Print" in response.json()["detail"]


def test_steward_history_label_is_official_case_record():
    from app.services.case_saved_artifact_service import CaseSavedArtifactService

    service = CaseSavedArtifactService(MagicMock())
    query = MagicMock()
    service.db.query.return_value = query
    query.filter.return_value = query
    query.order_by.return_value = query
    query.limit.return_value = query
    query.all.return_value = []
    with patch.object(service, "_require_case", return_value=SimpleNamespace(id=1)):
        history = service.list_steward_case_history("case-label")
    assert history.label == "Official Case Record"


def test_bounded_context_no_transcript_replay_flag():
    case = SimpleNamespace(
        case_uuid="bound-1",
        title="B",
        status="open",
        initial_question="Q",
        known_facts={},
        user_name=None,
        local_number=None,
        messages=[_message("user", f"m-{i}", index=i) for i in range(40)],
        report_versions=[],
        assets=[],
    )
    ctx = CaseService.build_bounded_ai_context(case, recent_message_limit=5)
    assert len(ctx["recent_messages"]) == 5
    assert ctx["persistence_notes"]["no_transcript_replay"] is True
    assert ctx["retrieved_case_memory"]["full_transcript_replayed"] is False
    assert ctx["official_artifact_index"] is not None
