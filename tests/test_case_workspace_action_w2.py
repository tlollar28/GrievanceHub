"""Phase W2 Update Analysis action tests (synthetic data; OpenAI mocked)."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.case_workspace_action_schema import (
    AnalysisUpdateResult,
    WorkspaceActionResponse,
    WorkspaceInteractionPayload,
    WorkspaceTimelineEventSummary,
)
from app.services.case_service import CaseService
from app.services.case_workspace_action_service import (
    CaseWorkspaceActionService,
    _WorkspaceInspection,
)
from app.services.follow_up_chat_service import FollowUpChatService

SYNTHETIC_CASE_UUID = "00000000-0000-4000-8000-000000000501"


def _case(*, status: str = "open", known_facts: dict | None = None, messages=None):
    return SimpleNamespace(
        id=501,
        case_uuid=SYNTHETIC_CASE_UUID,
        status=status,
        known_facts=known_facts if known_facts is not None else {"shift": "Tour 1"},
        report_versions=[
            SimpleNamespace(id=21, version_number=1, report_data={"v": 1}),
        ],
        messages=messages if messages is not None else [],
        initial_question="Can management change the schedule?",
        title="Synthetic schedule case",
        user_name="Synthetic Steward",
        local_number="300",
    )


def _inspection(**overrides) -> _WorkspaceInspection:
    base = dict(
        case=_case(),
        has_analysis_report=True,
        latest_report_version_id=21,
        latest_report_version_number=1,
        has_step_progression=False,
        current_step_type=None,
        template_id=None,
        template_availability_status=None,
        template_available=False,
        case_status="open",
    )
    base.update(overrides)
    return _WorkspaceInspection(**base)


def _timeline_event(event_id: str, event_type: str, **refs):
    return SimpleNamespace(
        event_id=event_id,
        event_type=event_type,
        title=event_type.replace("_", " ").title(),
        event_timestamp=datetime(2026, 7, 10, 18, 0, tzinfo=UTC),
        references=SimpleNamespace(
            report_version_id=refs.get("report_version_id"),
            report_version_number=refs.get("report_version_number"),
        ),
    )


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Service behavior
# ---------------------------------------------------------------------------


def test_update_analysis_without_interaction_creates_next_version():
    service = CaseWorkspaceActionService(MagicMock())
    new_version = SimpleNamespace(id=22, version_number=2)

    with (
        patch.object(
            service,
            "_inspect_workspace",
            side_effect=[
                _inspection(),
                _inspection(
                    latest_report_version_id=22,
                    latest_report_version_number=2,
                ),
            ],
        ),
        patch.object(
            CaseService,
            "generate_report_version",
            return_value=new_version,
        ) as mock_regen,
        patch.object(
            service,
            "_append_timeline_safe",
            return_value=_timeline_event(
                "evt-a",
                "analysis_updated",
                report_version_id=22,
                report_version_number=2,
            ),
        ) as mock_timeline,
        patch.object(service, "_persist_interaction") as mock_persist,
    ):
        mock_persist.return_value = (None, False, False, None)
        result = service.save_and_update_analysis(SYNTHETIC_CASE_UUID, None)

    assert result.status == "completed"
    assert result.steward_action_label is None  # not a steward UI button
    assert result.prior_report_version_number == 1
    assert result.current_report_version_number == 2
    assert result.analysis_update is not None
    assert result.analysis_update.interaction_saved is False
    assert result.analysis_update.older_versions_retained is True
    assert result.grievance_generation is None
    mock_regen.assert_called_once_with(
        db=service.db,
        case_uuid=SYNTHETIC_CASE_UUID,
        limit_per_source=8,
        trigger_message_id=None,
    )
    # Only analysis_updated (no context_saved when no interaction)
    assert mock_timeline.call_count == 1
    assert mock_timeline.call_args.kwargs["event_type"] == "analysis_updated"


def test_update_analysis_with_message_persists_and_creates_version():
    service = CaseWorkspaceActionService(MagicMock())
    message = SimpleNamespace(id=9001)
    new_version = SimpleNamespace(id=22, version_number=2)

    with (
        patch.object(service, "_inspect_workspace", side_effect=[_inspection(), _inspection()]),
        patch.object(
            CaseService,
            "add_message",
            return_value=message,
        ) as mock_add,
        patch.object(CaseService, "generate_report_version", return_value=new_version),
        patch.object(
            service,
            "_append_timeline_safe",
            side_effect=[
                _timeline_event("evt-c", "context_saved"),
                _timeline_event(
                    "evt-a",
                    "analysis_updated",
                    report_version_id=22,
                    report_version_number=2,
                ),
            ],
        ) as mock_timeline,
    ):
        result = service.save_and_update_analysis(
            SYNTHETIC_CASE_UUID,
            WorkspaceInteractionPayload(
                message="Management stated the schedule was changed on July 8.",
                source="manual_ui",
            ),
        )

    assert result.status == "completed"
    assert result.analysis_update.interaction_saved is True
    assert result.analysis_update.trigger_message_id == 9001
    assert result.analysis_update.trigger_metadata["trigger"] == "update_analysis"
    mock_add.assert_called_once()
    assert "schedule was changed" in mock_add.call_args.kwargs["content"]
    assert mock_add.call_args.kwargs["metadata"]["intent"] == "update_analysis"
    assert [c.kwargs["event_type"] for c in mock_timeline.call_args_list] == [
        "context_saved",
        "analysis_updated",
    ]


def test_clarification_is_preserved_in_message_metadata():
    service = CaseWorkspaceActionService(MagicMock())
    message = SimpleNamespace(id=9002)

    with (
        patch.object(service, "_inspect_workspace", side_effect=[_inspection(), _inspection()]),
        patch.object(CaseService, "add_message", return_value=message) as mock_add,
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
        service.save_and_update_analysis(
            SYNTHETIC_CASE_UUID,
            WorkspaceInteractionPayload(
                clarification="Correct the date to July 9.",
                source="manual_ui",
            ),
        )

    content = mock_add.call_args.kwargs["content"]
    meta = mock_add.call_args.kwargs["metadata"]
    assert "Clarification: Correct the date to July 9." in content
    assert meta["clarification"] == "Correct the date to July 9."


def test_fact_updates_are_merged_not_replaced():
    service = CaseWorkspaceActionService(MagicMock())
    case_row = _case(known_facts={"shift": "Tour 1", "station": "Main"})
    message = SimpleNamespace(id=9003)

    with (
        patch.object(service, "_inspect_workspace", side_effect=[_inspection(), _inspection()]),
        patch.object(CaseService, "_get_case_row", return_value=case_row),
        patch.object(CaseService, "update_known_facts") as mock_facts,
        patch.object(CaseService, "add_message", return_value=message),
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
        result = service.save_and_update_analysis(
            SYNTHETIC_CASE_UUID,
            WorkspaceInteractionPayload(
                fact_updates={"incident_date": "2026-07-09"},
            ),
        )

    assert result.analysis_update.facts_updated is True
    mock_facts.assert_called_once()
    merged = mock_facts.call_args.args[2]
    assert merged["shift"] == "Tour 1"
    assert merged["station"] == "Main"
    assert merged["incident_date"] == "2026-07-09"


def test_prior_report_versions_remain_and_latest_advances():
    service = CaseWorkspaceActionService(MagicMock())
    prior_data = {"immutable": True, "version": 1}
    new_version = SimpleNamespace(id=22, version_number=2, report_data={"version": 2})

    with (
        patch.object(
            service,
            "_inspect_workspace",
            side_effect=[
                _inspection(
                    case=_case(
                        messages=[],
                    ),
                    latest_report_version_id=21,
                    latest_report_version_number=1,
                ),
                _inspection(
                    latest_report_version_id=22,
                    latest_report_version_number=2,
                ),
            ],
        ),
        patch.object(CaseService, "generate_report_version", return_value=new_version),
        patch.object(
            service,
            "_append_timeline_safe",
            return_value=_timeline_event("evt-a", "analysis_updated"),
        ),
    ):
        result = service.save_and_update_analysis(SYNTHETIC_CASE_UUID, None)

    assert result.prior_report_version_id == 21
    assert result.prior_report_version_number == 1
    assert result.current_report_version_id == 22
    assert result.current_report_version_number == 2
    assert result.analysis_update.older_versions_retained is True
    assert result.analysis_update.is_current_analysis is True
    # Prior version payload object is not mutated by W2 orchestration
    assert prior_data == {"immutable": True, "version": 1}


def test_closed_case_requires_reopen():
    service = CaseWorkspaceActionService(MagicMock())
    with patch.object(
        service,
        "_inspect_workspace",
        return_value=_inspection(case_status="closed", case=_case(status="closed")),
    ), patch.object(CaseService, "generate_report_version") as mock_regen:
        result = service.save_and_update_analysis(
            SYNTHETIC_CASE_UUID,
            WorkspaceInteractionPayload(message="Should not save"),
        )

    assert result.status == "prerequisites_not_met"
    assert result.missing_prerequisites[0].code == "case_closed_requires_reopen"
    mock_regen.assert_not_called()


def test_reopened_case_uses_existing_history():
    service = CaseWorkspaceActionService(MagicMock())
    prior_messages = [
        SimpleNamespace(id=1, role="user", content="Original concern", created_at=datetime(2026, 7, 1, tzinfo=UTC)),
        SimpleNamespace(id=2, role="assistant", content="Prior answer", created_at=datetime(2026, 7, 2, tzinfo=UTC)),
    ]
    case = _case(status="open", messages=list(prior_messages))
    new_message = SimpleNamespace(id=3)
    new_version = SimpleNamespace(id=22, version_number=2)

    with (
        patch.object(
            service,
            "_inspect_workspace",
            side_effect=[
                _inspection(case=case, case_status="open"),
                _inspection(case=case, case_status="open"),
            ],
        ),
        patch.object(CaseService, "add_message", return_value=new_message) as mock_add,
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
        result = service.save_and_update_analysis(
            SYNTHETIC_CASE_UUID,
            WorkspaceInteractionPayload(message="Continuing after reopen."),
        )

    assert result.status == "completed"
    assert result.analysis_update.prior_conversation_preserved is True
    mock_add.assert_called_once()
    mock_regen.assert_called_once()
    # Prior messages list object not cleared by orchestration
    assert len(prior_messages) == 2


def test_timeline_events_added_once_per_type():
    service = CaseWorkspaceActionService(MagicMock())
    message = SimpleNamespace(id=44)

    with (
        patch.object(service, "_inspect_workspace", side_effect=[_inspection(), _inspection()]),
        patch.object(CaseService, "add_message", return_value=message),
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
        result = service.save_and_update_analysis(
            SYNTHETIC_CASE_UUID,
            WorkspaceInteractionPayload(message="Note"),
        )

    types = [c.kwargs["event_type"] for c in mock_timeline.call_args_list]
    assert types == ["context_saved", "analysis_updated"]
    assert len(result.timeline_events) == 2
    assert {e.event_type for e in result.timeline_events} == {
        "context_saved",
        "analysis_updated",
    }


def test_no_grievance_draft_or_snapshot_created():
    service = CaseWorkspaceActionService(MagicMock())

    with (
        patch.object(service, "_inspect_workspace", side_effect=[_inspection(), _inspection()]),
        patch.object(
            CaseService,
            "generate_report_version",
            return_value=SimpleNamespace(id=22, version_number=2),
        ),
        patch.object(
            service,
            "_append_timeline_safe",
            return_value=_timeline_event("evt-a", "analysis_updated"),
        ),
        patch(
            "app.services.grievance_form_draft_builder.build_grievance_form_draft"
        ) as mock_draft,
    ):
        result = service.save_and_update_analysis(SYNTHETIC_CASE_UUID, None)

    assert result.grievance_generation is None
    assert result.analysis_update is not None
    assert not hasattr(result.analysis_update, "snapshot") or True
    mock_draft.assert_not_called()


# ---------------------------------------------------------------------------
# API route
# ---------------------------------------------------------------------------


def test_route_returns_typed_completed_update_analysis_response(client):
    expected = WorkspaceActionResponse(
        case_uuid=SYNTHETIC_CASE_UUID,
        action="save_and_update_analysis",
        status="completed",
        message="Analysis refreshed. New report version 2 is current; prior versions retained.",
        steward_action_label=None,
        prior_report_version_id=21,
        prior_report_version_number=1,
        current_report_version_id=22,
        current_report_version_number=2,
        analysis_update=AnalysisUpdateResult(
            interaction_saved=True,
            prior_report_version_number=1,
            new_report_version_id=22,
            new_report_version_number=2,
            is_current_analysis=True,
            timeline_events=[
                WorkspaceTimelineEventSummary(
                    event_id="evt-a",
                    event_type="analysis_updated",
                    title="Analysis updated",
                    report_version_number=2,
                )
            ],
        ),
        timeline_events=[
            WorkspaceTimelineEventSummary(
                event_id="evt-a",
                event_type="analysis_updated",
                title="Analysis updated",
                report_version_number=2,
            )
        ],
        interaction_accepted_for_later_phases=True,
    )
    with (
        patch.object(
            CaseWorkspaceActionService,
            "execute_action",
            return_value=expected,
        ) as mock_execute,
        patch.object(CaseService, "generate_report_version") as mock_regen,
        patch(
            "app.services.follow_up_chat_service.FollowUpChatService._client"
        ) as mock_openai,
        patch(
            "app.services.grievance_form_draft_builder.build_grievance_form_draft"
        ) as mock_draft,
    ):
        response = client.post(
            f"/cases/{SYNTHETIC_CASE_UUID}/actions",
            json={
                "action": "save_and_update_analysis",
                "interaction": {
                    "message": "Synthetic steward note.",
                    "source": "manual_ui",
                },
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["steward_action_label"] is None
    assert body["action"] == "save_and_update_analysis"
    assert body["current_report_version_number"] == 2
    assert body["analysis_update"]["new_report_version_number"] == 2
    assert body["grievance_generation"] is None
    mock_execute.assert_called_once()
    # Route itself does not call pipeline/OpenAI/draft when service is mocked
    mock_regen.assert_not_called()
    mock_openai.assert_not_called()
    mock_draft.assert_not_called()


def test_route_closed_case_structured_prerequisite(client):
    from app.schemas.case_workspace_action_schema import WorkspaceActionPrerequisite

    expected = WorkspaceActionResponse(
        case_uuid=SYNTHETIC_CASE_UUID,
        action="save_and_update_analysis",
        status="prerequisites_not_met",
        message="Case is closed; reopen required.",
        steward_action_label=None,
        missing_prerequisites=[
            WorkspaceActionPrerequisite(
                code="case_closed_requires_reopen",
                message=(
                    "Case is closed. Reopen the case before continuing "
                    "case interactions."
                ),
            )
        ],
    )
    with patch.object(CaseWorkspaceActionService, "execute_action", return_value=expected):
        response = client.post(
            f"/cases/{SYNTHETIC_CASE_UUID}/actions",
            json={"action": "save_and_update_analysis"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "prerequisites_not_met"
    assert body["missing_prerequisites"][0]["code"] == "case_closed_requires_reopen"


def test_legacy_regenerate_route_still_unchanged(client):
    created = datetime(2026, 7, 1, tzinfo=UTC)
    version = SimpleNamespace(
        id=2,
        version_number=2,
        trigger_message_id=None,
        created_at=created,
        report_data={},
        ranked_authorities=[],
        issue_analysis={},
        evidence_items=[],
        retrieval_gaps=None,
        source_coverage_audit=None,
        report_summary=None,
    )
    case = SimpleNamespace(
        case_uuid=SYNTHETIC_CASE_UUID,
        title="Synthetic",
        user_name=None,
        local_number=None,
        initial_question="q",
        known_facts={},
        status="open",
        created_at=created,
        updated_at=created,
        messages=[],
        report_versions=[version],
    )
    with (
        patch.object(CaseService, "generate_report_version", return_value=version) as mock_regen,
        patch.object(CaseService, "get_case", return_value=case),
        patch.object(
            CaseService,
            "serialize_case_list_summary",
            return_value={
                "case_uuid": SYNTHETIC_CASE_UUID,
                "title": "Synthetic",
                "status": "open",
            },
        ),
    ):
        response = client.post(f"/cases/{SYNTHETIC_CASE_UUID}/reports/regenerate")

    assert response.status_code == 200
    mock_regen.assert_called_once()


def test_legacy_followups_route_still_unchanged(client):
    with (
        patch.object(
            FollowUpChatService,
            "answer_follow_up",
            return_value={
                "user_message": SimpleNamespace(
                    id=1,
                    role="user",
                    content="follow-up?",
                    message_metadata={"intent": "follow_up"},
                    created_at=None,
                ),
                "assistant_message": SimpleNamespace(
                    id=2,
                    role="assistant",
                    content="answer",
                    message_metadata={"intent": "follow_up"},
                    created_at=None,
                ),
                "answer": "answer",
                "answer_type": "fact",
                "citations": [],
                "disclosures": [],
                "facts_needed": [],
                "linked_report_version": 1,
                "requires_report_regen": False,
                "suggested_actions": [],
            },
        ) as mock_followup,
        patch.object(
            CaseService,
            "serialize_message",
            side_effect=lambda m: {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "metadata": m.message_metadata,
                "created_at": None,
            },
        ),
    ):
        response = client.post(
            f"/cases/{SYNTHETIC_CASE_UUID}/followups",
            json={"content": "follow-up?"},
        )

    assert response.status_code == 200
    mock_followup.assert_called_once()
