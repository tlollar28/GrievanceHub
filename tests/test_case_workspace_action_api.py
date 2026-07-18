"""Phase W1 API route tests for POST /cases/{uuid}/actions."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.case_workspace_action_schema import (
    AnalysisUpdateResult,
    GrievanceGenerationResult,
    WorkspaceActionResponse,
)
from app.services.case_service import CaseService
from app.services.case_workspace_action_service import CaseWorkspaceActionService
from app.services.follow_up_chat_service import FollowUpChatService

SYNTHETIC_CASE_UUID = "00000000-0000-4000-8000-000000000402"


@pytest.fixture
def client():
    return TestClient(app)


def _w1_response(
    *,
    action: str = "save_and_update_analysis",
    status: str = "not_implemented_in_w1",
) -> WorkspaceActionResponse:
    return WorkspaceActionResponse(
        case_uuid=SYNTHETIC_CASE_UUID,
        action=action,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        message=CaseWorkspaceActionService.W1_NOT_IMPLEMENTED_MESSAGE,
        analysis_update=AnalysisUpdateResult() if action == "save_and_update_analysis" else None,
        grievance_generation=(
            GrievanceGenerationResult(
                draft_created=False,
                editable=True,
                official_artifact_created=False,
            )
            if action == "generate_grievance"
            else None
        ),
        interaction_accepted_for_later_phases=False,
    )


def test_route_calls_canonical_action_service(client):
    expected = _w1_response()
    with patch.object(
        CaseWorkspaceActionService,
        "execute_action",
        return_value=expected,
    ) as mock_execute:
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
    assert body["action"] == "save_and_update_analysis"
    assert body["status"] == "not_implemented_in_w1"
    assert body["analysis_update"]["interaction_saved"] is False
    mock_execute.assert_called_once()
    call_args = mock_execute.call_args
    assert call_args.args[0] == SYNTHETIC_CASE_UUID
    assert call_args.args[1].action == "save_and_update_analysis"


def test_route_generate_grievance_contract(client):
    expected = _w1_response(action="generate_grievance")
    with patch.object(
        CaseWorkspaceActionService,
        "execute_action",
        return_value=expected,
    ):
        response = client.post(
            f"/cases/{SYNTHETIC_CASE_UUID}/actions",
            json={"action": "generate_grievance", "interaction": None},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["action"] == "generate_grievance"
    assert body["grievance_generation"]["draft_created"] is False
    assert body["grievance_generation"]["export_attempted"] is False


def test_route_missing_case_returns_404(client):
    expected = WorkspaceActionResponse(
        case_uuid=SYNTHETIC_CASE_UUID,
        action="save_and_update_analysis",
        status="case_not_found",
        message="Case not found",
    )
    with patch.object(
        CaseWorkspaceActionService,
        "execute_action",
        return_value=expected,
    ):
        response = client.post(
            f"/cases/{SYNTHETIC_CASE_UUID}/actions",
            json={"action": "save_and_update_analysis"},
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Case not found"


def test_route_rejects_invalid_action(client):
    response = client.post(
        f"/cases/{SYNTHETIC_CASE_UUID}/actions",
        json={"action": "print_grievance"},
    )
    assert response.status_code == 422


def test_route_does_not_call_openai_or_create_report_or_draft(client):
    expected = _w1_response(action="generate_grievance")
    with (
        patch.object(
            CaseWorkspaceActionService,
            "execute_action",
            return_value=expected,
        ),
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
            json={"action": "generate_grievance"},
        )

    assert response.status_code == 200
    mock_regen.assert_not_called()
    mock_openai.assert_not_called()
    mock_draft.assert_not_called()


def test_legacy_messages_route_does_not_auto_generate_report(client):
    """POST /messages persists the message only; no automatic analysis report."""
    created = datetime(2026, 7, 1, tzinfo=timezone.utc)
    message = SimpleNamespace(
        id=1,
        role="user",
        content="legacy message",
        message_metadata=None,
        created_at=created,
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
        messages=[message],
        report_versions=[],
    )
    with (
        patch.object(CaseService, "add_message", return_value=message) as mock_add,
        patch.object(CaseService, "generate_report_version") as mock_regen,
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
        response = client.post(
            f"/cases/{SYNTHETIC_CASE_UUID}/messages",
            json={"role": "user", "content": "legacy message"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["report_version"] is None
    mock_add.assert_called_once()
    mock_regen.assert_not_called()


def test_legacy_followups_route_unchanged(client):
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


def test_legacy_regenerate_route_unchanged(client):
    created = datetime(2026, 7, 1, tzinfo=timezone.utc)
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
        patch.object(
            CaseService, "generate_report_version", return_value=version
        ) as mock_regen,
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
