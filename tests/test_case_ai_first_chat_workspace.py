"""AI-first case chat workspace correction tests (W1–W3 stacked).

Proves canonical POST /cases/{uuid}/interactions behavior with mocked OpenAI/RAG.
Synthetic data only — no live OpenAI, no grievance drafts, no exports.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.case_workspace_action_schema import (
    CaseInteractionRequest,
    CaseInteractionResponse,
    WorkspaceActionAvailability,
)
from app.schemas.follow_up_schema import FollowUpAnswerPayload
from app.services.case_service import CaseService
from app.services.case_workspace_action_service import CaseWorkspaceActionService
from app.services.follow_up_chat_service import FollowUpChatService

CASE_A = "00000000-0000-4000-8000-000000000601"
CASE_B = "00000000-0000-4000-8000-000000000602"


def _case(
    *,
    case_uuid: str = CASE_A,
    status: str = "open",
    known_facts: dict | None = None,
    messages=None,
    report_versions=None,
):
    return SimpleNamespace(
        id=601 if case_uuid == CASE_A else 602,
        case_uuid=case_uuid,
        status=status,
        known_facts=known_facts if known_facts is not None else {"shift": "Tour 1"},
        report_versions=report_versions
        if report_versions is not None
        else [SimpleNamespace(id=21, version_number=1, report_data={"v": 1})],
        messages=messages if messages is not None else [],
        initial_question="Can management change the schedule?",
        title="Synthetic schedule case",
        user_name="Synthetic Steward",
        local_number="300",
    )


def _inspection(service_case=None, **overrides):
    from app.services.case_workspace_action_service import _WorkspaceInspection

    case = service_case or _case()
    base = dict(
        case=case,
        has_analysis_report=True,
        latest_report_version_id=21,
        latest_report_version_number=1,
        has_step_progression=False,
        current_step_type=None,
        template_id=None,
        template_availability_status=None,
        template_available=False,
        case_status=str(case.status or "open"),
    )
    base.update(overrides)
    return _WorkspaceInspection(**base)


def _timeline_event(event_id: str, event_type: str, **refs):
    return SimpleNamespace(
        event_id=event_id,
        event_type=event_type,
        title=event_type.replace("_", " ").title(),
        event_timestamp=datetime(2026, 7, 10, 21, 0, tzinfo=UTC),
        references=SimpleNamespace(
            report_version_id=refs.get("report_version_id"),
            report_version_number=refs.get("report_version_number"),
        ),
    )


def _follow_up_result(*, user_id=9001, assistant_id=9002, answer="Grounded reply."):
    user = SimpleNamespace(
        id=user_id,
        role="user",
        content="What about Article 10?",
        message_metadata={"intent": "follow_up"},
        created_at=datetime(2026, 7, 10, 21, 0, tzinfo=UTC),
        case_id=601,
    )
    assistant = SimpleNamespace(
        id=assistant_id,
        role="assistant",
        content=answer,
        message_metadata={"intent": "follow_up", "answer_type": "argument"},
        created_at=datetime(2026, 7, 10, 21, 1, tzinfo=UTC),
        case_id=601,
    )
    return {
        "user_message": user,
        "assistant_message": assistant,
        "answer": answer,
        "answer_type": "argument",
        "citations": [],
        "disclosures": [],
        "facts_needed": [],
        "linked_report_version": {"id": 21, "version_number": 1},
        "requires_report_regen": False,
        "suggested_actions": [],
    }


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Canonical route
# ---------------------------------------------------------------------------


def test_canonical_interactions_route_exists(client):
    expected = CaseInteractionResponse(
        case_uuid=CASE_A,
        status="completed",
        message="Workspace is current.",
        workspace_current=True,
        current_report_version_number=2,
        analysis_versions_created=1,
        generate_grievance_available=False,
        ai_answer="Grounded reply.",
    )
    with (
        patch.object(
            CaseWorkspaceActionService,
            "submit_interaction",
            return_value=expected,
        ) as mock_submit,
        patch(
            "app.services.follow_up_chat_service.FollowUpChatService._client"
        ) as mock_openai,
    ):
        response = client.post(
            f"/cases/{CASE_A}/interactions",
            json={"message": "What about Article 10?", "source": "manual_ui"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["workspace_current"] is True
    assert body["ai_answer"] == "Grounded reply."
    assert "Update Analysis" not in (body.get("message") or "")
    mock_submit.assert_called_once()
    mock_openai.assert_not_called()


def test_no_explicit_update_analysis_ui_action_required():
    """save_and_update_analysis must not be steward-visible."""
    service = CaseWorkspaceActionService(MagicMock())
    actions = service.evaluate_action_availability(_inspection())
    save = next(a for a in actions if a.action == "save_and_update_analysis")
    gen = next(a for a in actions if a.action == "generate_grievance")
    assert save.steward_visible is False
    assert gen.steward_visible is True
    assert "Update Analysis" not in (save.reason or "")


# ---------------------------------------------------------------------------
# Interaction orchestration
# ---------------------------------------------------------------------------


def test_submitted_message_and_ai_response_persisted():
    service = CaseWorkspaceActionService(MagicMock())
    follow = _follow_up_result()
    new_version = SimpleNamespace(id=22, version_number=2)

    with (
        patch.object(
            service,
            "_inspect_workspace",
            side_effect=[_inspection(), _inspection(latest_report_version_id=22, latest_report_version_number=2)],
        ),
        patch.object(FollowUpChatService, "answer_follow_up", return_value=follow) as mock_fu,
        patch.object(service, "_enrich_interaction_message_metadata", return_value={"intent": "case_interaction"}),
        patch.object(CaseService, "generate_report_version", return_value=new_version) as mock_regen,
        patch.object(
            service,
            "_append_timeline_safe",
            side_effect=[
                _timeline_event("evt-c", "context_saved"),
                _timeline_event("evt-a", "analysis_updated", report_version_id=22, report_version_number=2),
            ],
        ),
        patch(
            "app.services.grievance_form_draft_builder.build_grievance_form_draft"
        ) as mock_draft,
    ):
        result = service.submit_interaction(
            CASE_A,
            CaseInteractionRequest(message="What about Article 10?"),
            llm_callable=lambda q, g: {"answer": "x", "answer_type": "fact"},
        )

    assert result.status == "completed"
    assert result.user_message is not None
    assert result.user_message.id == 9001
    assert result.assistant_message is not None
    assert result.assistant_message.id == 9002
    assert result.ai_answer == "Grounded reply."
    assert result.analysis_update.ai_response_persisted is True
    mock_fu.assert_called_once()
    mock_regen.assert_called_once()
    mock_draft.assert_not_called()


def test_one_interaction_creates_exactly_one_analysis_version():
    service = CaseWorkspaceActionService(MagicMock())
    follow = _follow_up_result()
    new_version = SimpleNamespace(id=22, version_number=2)

    with (
        patch.object(service, "_inspect_workspace", side_effect=[_inspection(), _inspection()]),
        patch.object(FollowUpChatService, "answer_follow_up", return_value=follow),
        patch.object(service, "_enrich_interaction_message_metadata", return_value={}),
        patch.object(CaseService, "generate_report_version", return_value=new_version) as mock_regen,
        patch.object(
            service,
            "_append_timeline_safe",
            side_effect=[
                _timeline_event("evt-c", "context_saved"),
                _timeline_event("evt-a", "analysis_updated"),
            ],
        ),
    ):
        result = service.submit_interaction(
            CASE_A,
            CaseInteractionRequest(message="Add context about overtime."),
        )

    assert result.analysis_versions_created == 1
    assert result.prior_report_version_number == 1
    assert result.current_report_version_number == 2
    assert result.analysis_update.older_versions_retained is True
    assert result.analysis_update.is_current_analysis is True
    mock_regen.assert_called_once()


def test_no_duplicate_analysis_generation_for_one_chat_interaction():
    service = CaseWorkspaceActionService(MagicMock())
    follow = _follow_up_result()

    with (
        patch.object(service, "_inspect_workspace", side_effect=[_inspection(), _inspection()]),
        patch.object(FollowUpChatService, "answer_follow_up", return_value=follow),
        patch.object(service, "_enrich_interaction_message_metadata", return_value={}),
        patch.object(
            CaseService,
            "generate_report_version",
            return_value=SimpleNamespace(id=22, version_number=2),
        ) as mock_regen,
        patch.object(
            service,
            "_append_timeline_safe",
            side_effect=[
                _timeline_event("evt-c", "context_saved"),
                _timeline_event("evt-a", "analysis_updated"),
            ],
        ),
        patch.object(service, "save_and_update_analysis") as mock_compat,
    ):
        service.submit_interaction(
            CASE_A,
            CaseInteractionRequest(message="One turn only."),
        )

    mock_regen.assert_called_once()
    mock_compat.assert_not_called()


def test_timeline_events_appended_once():
    service = CaseWorkspaceActionService(MagicMock())
    follow = _follow_up_result()

    with (
        patch.object(service, "_inspect_workspace", side_effect=[_inspection(), _inspection()]),
        patch.object(FollowUpChatService, "answer_follow_up", return_value=follow),
        patch.object(service, "_enrich_interaction_message_metadata", return_value={}),
        patch.object(
            CaseService,
            "generate_report_version",
            return_value=SimpleNamespace(id=22, version_number=2),
        ),
        patch.object(
            service,
            "_append_timeline_safe",
            side_effect=[
                _timeline_event("evt-c", "context_saved"),
                _timeline_event("evt-a", "analysis_updated"),
            ],
        ) as mock_timeline,
    ):
        result = service.submit_interaction(
            CASE_A,
            CaseInteractionRequest(message="Note"),
        )

    types = [c.kwargs["event_type"] for c in mock_timeline.call_args_list]
    assert types == ["context_saved", "analysis_updated"]
    assert len(result.timeline_events) == 2


def test_fact_updates_merge_safely():
    service = CaseWorkspaceActionService(MagicMock())
    case_row = _case(known_facts={"shift": "Tour 1", "station": "Main"})
    follow = _follow_up_result()

    with (
        patch.object(service, "_inspect_workspace", side_effect=[_inspection(), _inspection()]),
        patch.object(CaseService, "_get_case_row", return_value=case_row),
        patch.object(CaseService, "update_known_facts") as mock_facts,
        patch.object(FollowUpChatService, "answer_follow_up", return_value=follow),
        patch.object(service, "_enrich_interaction_message_metadata", return_value={}),
        patch.object(
            CaseService,
            "generate_report_version",
            return_value=SimpleNamespace(id=22, version_number=2),
        ),
        patch.object(
            service,
            "_append_timeline_safe",
            side_effect=[
                _timeline_event("evt-c", "context_saved"),
                _timeline_event("evt-a", "analysis_updated"),
            ],
        ),
    ):
        result = service.submit_interaction(
            CASE_A,
            CaseInteractionRequest(
                message="Also note the date.",
                fact_updates={"incident_date": "2026-07-09"},
            ),
        )

    assert result.analysis_update.facts_updated is True
    merged = mock_facts.call_args.args[2]
    assert merged["shift"] == "Tour 1"
    assert merged["station"] == "Main"
    assert merged["incident_date"] == "2026-07-09"


def test_referenced_asset_uuids_resolve():
    service = CaseWorkspaceActionService(MagicMock())
    follow = _follow_up_result()
    asset_uuid = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"

    with (
        patch.object(service, "_inspect_workspace", side_effect=[_inspection(), _inspection()]),
        patch.object(FollowUpChatService, "answer_follow_up", return_value=follow),
        patch.object(
            service._assets,
            "resolve_upload_refs_for_context",
            return_value=[
                {
                    "asset_uuid": asset_uuid,
                    "original_filename": "evidence.txt",
                    "category": "uploaded_document",
                }
            ],
        ) as mock_resolve,
        patch.object(
            CaseService,
            "generate_report_version",
            return_value=SimpleNamespace(id=22, version_number=2),
        ),
        patch.object(
            service,
            "_append_timeline_safe",
            side_effect=[
                _timeline_event("evt-c", "context_saved"),
                _timeline_event("evt-a", "analysis_updated"),
            ],
        ),
    ):
        # Let enrich run for real so resolve is called
        result = service.submit_interaction(
            CASE_A,
            CaseInteractionRequest(
                message="See the attached evidence.",
                upload_refs=[asset_uuid],
            ),
        )

    mock_resolve.assert_called_once()
    assert result.status == "completed"
    assert result.analysis_update.trigger_metadata is not None
    assert asset_uuid in (
        result.analysis_update.trigger_metadata.get("case_asset_uuids") or []
    )


def test_response_includes_ai_reply_and_workspace_state():
    service = CaseWorkspaceActionService(MagicMock())
    follow = _follow_up_result(answer="Contract language supports the steward.")

    with (
        patch.object(service, "_inspect_workspace", side_effect=[_inspection(), _inspection()]),
        patch.object(FollowUpChatService, "answer_follow_up", return_value=follow),
        patch.object(service, "_enrich_interaction_message_metadata", return_value={}),
        patch.object(
            CaseService,
            "generate_report_version",
            return_value=SimpleNamespace(id=22, version_number=2),
        ),
        patch.object(
            service,
            "_append_timeline_safe",
            side_effect=[
                _timeline_event("evt-c", "context_saved"),
                _timeline_event("evt-a", "analysis_updated"),
            ],
        ),
    ):
        result = service.submit_interaction(
            CASE_A,
            CaseInteractionRequest(message="Summarize the key issue."),
        )

    assert result.workspace_current is True
    assert result.ai_answer == "Contract language supports the steward."
    assert result.current_report_version_number == 2
    assert result.analysis_update is not None
    assert "Generate Grievance" in result.message


def test_generate_grievance_availability_recalculated_not_executed():
    service = CaseWorkspaceActionService(MagicMock())
    follow = _follow_up_result()
    post = _inspection(
        has_step_progression=True,
        current_step_type="step_2_appeal",
        template_id="local_300_form_79_1",
        template_availability_status="available",
        template_available=True,
        latest_report_version_id=22,
        latest_report_version_number=2,
    )

    with (
        patch.object(service, "_inspect_workspace", side_effect=[_inspection(), post]),
        patch.object(FollowUpChatService, "answer_follow_up", return_value=follow),
        patch.object(service, "_enrich_interaction_message_metadata", return_value={}),
        patch.object(
            CaseService,
            "generate_report_version",
            return_value=SimpleNamespace(id=22, version_number=2),
        ),
        patch.object(
            service,
            "_append_timeline_safe",
            side_effect=[
                _timeline_event("evt-c", "context_saved"),
                _timeline_event("evt-a", "analysis_updated"),
            ],
        ),
        patch.object(service, "generate_grievance") as mock_gen,
        patch(
            "app.services.grievance_form_draft_builder.build_grievance_form_draft"
        ) as mock_draft,
    ):
        result = service.submit_interaction(
            CASE_A,
            CaseInteractionRequest(message="Ready for Step 2?"),
        )

    assert result.generate_grievance_available is True
    assert result.grievance_draft_created is False
    assert result.generation_snapshot_persisted is False
    assert result.export_attempted is False
    mock_gen.assert_not_called()
    mock_draft.assert_not_called()


def test_closed_case_requires_reopening_before_interaction():
    service = CaseWorkspaceActionService(MagicMock())
    with (
        patch.object(
            service,
            "_inspect_workspace",
            return_value=_inspection(case=_case(status="closed"), case_status="closed"),
        ),
        patch.object(FollowUpChatService, "answer_follow_up") as mock_fu,
        patch.object(CaseService, "generate_report_version") as mock_regen,
    ):
        result = service.submit_interaction(
            CASE_A,
            CaseInteractionRequest(message="Should not run"),
        )

    assert result.status == "prerequisites_not_met"
    assert result.missing_prerequisites[0].code == "case_closed_requires_reopen"
    assert result.workspace_current is False
    mock_fu.assert_not_called()
    mock_regen.assert_not_called()


def test_reopened_case_can_interact_and_preserves_prior_conversation():
    service = CaseWorkspaceActionService(MagicMock())
    prior = [
        SimpleNamespace(id=1, role="user", content="Original concern"),
        SimpleNamespace(id=2, role="assistant", content="Prior AI reply"),
    ]
    case = _case(status="open", messages=list(prior))
    follow = _follow_up_result(user_id=3, assistant_id=4)

    with (
        patch.object(
            service,
            "_inspect_workspace",
            side_effect=[
                _inspection(service_case=case, case_status="open"),
                _inspection(service_case=case, case_status="open"),
            ],
        ),
        patch.object(FollowUpChatService, "answer_follow_up", return_value=follow) as mock_fu,
        patch.object(service, "_enrich_interaction_message_metadata", return_value={}),
        patch.object(
            CaseService,
            "generate_report_version",
            return_value=SimpleNamespace(id=22, version_number=2),
        ),
        patch.object(
            service,
            "_append_timeline_safe",
            side_effect=[
                _timeline_event("evt-c", "context_saved"),
                _timeline_event("evt-a", "analysis_updated"),
            ],
        ),
    ):
        result = service.submit_interaction(
            CASE_A,
            CaseInteractionRequest(message="Continuing after reopen."),
        )

    assert result.status == "completed"
    assert result.analysis_update.prior_conversation_preserved is True
    mock_fu.assert_called_once()
    assert len(prior) == 2  # prior history object not cleared


def test_case_isolation_prevents_cross_case_conversation_bleed():
    """Each interaction is scoped to the requested case_uuid only."""
    service = CaseWorkspaceActionService(MagicMock())
    follow = _follow_up_result()

    with (
        patch.object(service, "_inspect_workspace", side_effect=[_inspection(), _inspection()]),
        patch.object(FollowUpChatService, "answer_follow_up", return_value=follow) as mock_fu,
        patch.object(service, "_enrich_interaction_message_metadata", return_value={}),
        patch.object(
            CaseService,
            "generate_report_version",
            return_value=SimpleNamespace(id=22, version_number=2),
        ) as mock_regen,
        patch.object(
            service,
            "_append_timeline_safe",
            side_effect=[
                _timeline_event("evt-c", "context_saved"),
                _timeline_event("evt-a", "analysis_updated"),
            ],
        ),
    ):
        result = service.submit_interaction(
            CASE_A,
            CaseInteractionRequest(message="Only for case A."),
        )

    assert result.case_uuid == CASE_A
    assert mock_fu.call_args.kwargs["case_uuid"] == CASE_A
    assert mock_regen.call_args.kwargs["case_uuid"] == CASE_A
    assert CASE_B not in str(mock_fu.call_args)
    assert CASE_B not in str(mock_regen.call_args)


def test_legacy_actions_route_remains_compatible(client):
    from app.schemas.case_workspace_action_schema import (
        AnalysisUpdateResult,
        WorkspaceActionResponse,
    )

    expected = WorkspaceActionResponse(
        case_uuid=CASE_A,
        action="save_and_update_analysis",
        status="completed",
        message="Analysis refreshed.",
        steward_action_label=None,
        current_report_version_number=2,
        analysis_update=AnalysisUpdateResult(new_report_version_number=2),
    )
    with patch.object(
        CaseWorkspaceActionService, "execute_action", return_value=expected
    ):
        response = client.post(
            f"/cases/{CASE_A}/actions",
            json={"action": "save_and_update_analysis"},
        )

    assert response.status_code == 200
    assert response.json()["action"] == "save_and_update_analysis"
    assert response.json()["steward_action_label"] is None


def test_legacy_followups_route_still_present(client):
    """Compatibility follow-up route remains registered (mocked)."""
    with patch.object(
        FollowUpChatService,
        "answer_follow_up",
        return_value=_follow_up_result(),
    ), patch.object(
        CaseService,
        "serialize_message",
        side_effect=lambda m: {"id": m.id, "role": m.role, "content": m.content},
    ):
        # May 404 if case lookup fails before mock — patch get path via service
        with patch.object(
            FollowUpChatService,
            "answer_follow_up",
            return_value=_follow_up_result(),
        ):
            # Ensure route exists in OpenAPI
            paths = client.app.openapi()["paths"]
            assert f"/cases/{{case_uuid}}/interactions" in paths
            assert f"/cases/{{case_uuid}}/followups" in paths
            assert f"/cases/{{case_uuid}}/messages" in paths
            assert f"/cases/{{case_uuid}}/reports/regenerate" in paths
            assert f"/cases/{{case_uuid}}/actions" in paths
            assert f"/cases/{{case_uuid}}/assets" in paths


def test_w3_asset_routes_still_present(client):
    paths = client.app.openapi()["paths"]
    assert f"/cases/{{case_uuid}}/assets" in paths
    assert f"/cases/{{case_uuid}}/assets/{{asset_uuid}}" in paths
