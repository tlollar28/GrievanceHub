"""Tests for SavedCaseApiClient and click/reopen workflow helpers (Phase 1.4F)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
import requests

from app.clients.saved_case_client import (
    SavedCaseApiClient,
    SavedCaseApiError,
    resolve_case_click_action,
)
from app.schemas.saved_case_schema import (
    OpenCaseResponse,
    ReopenCaseResponse,
    SavedCaseListResponse,
    SavedCaseSummary,
    SavedCaseTemplateAvailability,
    SavedCaseTimelineResponse,
)
from app.schemas.case_step_progression_schema import CaseTimelineEvent, CaseTimelineEventReferences

SYNTHETIC_CASE_UUID = "00000000-0000-4000-8000-000000000501"


def _summary(*, workspace_status: str = "open", actions: list[str] | None = None) -> SavedCaseSummary:
    return SavedCaseSummary(
        case_id=501,
        case_uuid=SYNTHETIC_CASE_UUID,
        case_number="501",
        title="Synthetic saved case",
        issue_summary="Synthetic issue summary.",
        grievant_or_class="Synthetic Grievant",
        current_step_type="step_1_initial",
        current_step_status="open",
        workspace_status=workspace_status,  # type: ignore[arg-type]
        legacy_case_status="closed" if workspace_status == "closed" else "open",
        created_at=datetime(2026, 7, 1, 12, 0, tzinfo=UTC),
        last_activity_at=datetime(2026, 7, 6, 12, 0, tzinfo=UTC),
        closed_at=datetime(2026, 7, 5, 12, 0, tzinfo=UTC) if workspace_status == "closed" else None,
        reopened_at=None,
        latest_outcome_summary=None,
        latest_outcome_type=None,
        template_availability=SavedCaseTemplateAvailability(
            step_type="step_1_initial",
            template_available=False,
            availability_status="unconfirmed_pending_steward_confirmation",
        ),
        available_actions=actions or ["open_case", "view_timeline"],
        has_step_progression=True,
    )


def _mock_response(status_code: int, json_body: dict) -> MagicMock:
    response = MagicMock(spec=requests.Response)
    response.status_code = status_code
    response.text = str(json_body)
    response.json.return_value = json_body
    return response


@pytest.fixture
def session():
    return MagicMock(spec=requests.Session)


@pytest.fixture
def client(session):
    return SavedCaseApiClient("http://testserver", session=session)


def test_resolve_click_action_open_case():
    assert resolve_case_click_action(_summary(workspace_status="open")) == "open_case"
    assert resolve_case_click_action(_summary(workspace_status="reopened")) == "open_case"


def test_resolve_click_action_closed_case():
    closed = _summary(
        workspace_status="closed",
        actions=["open_case", "reopen_case", "view_timeline"],
    )
    assert resolve_case_click_action(closed) == "reopen_case"


def test_list_saved_cases_parses_response(client, session):
    payload = SavedCaseListResponse(
        count=1,
        order="newest_first",
        status_filter="all",
        cases=[_summary()],
    ).model_dump(mode="json")
    session.request.return_value = _mock_response(200, payload)

    result = client.list_saved_cases(status="open", search="501")

    session.request.assert_called_once()
    call = session.request.call_args
    assert call.args[0] == "GET"
    assert call.args[1] == "http://testserver/cases/saved"
    assert call.kwargs["params"] == {"status": "open", "order": "newest_first", "search": "501"}
    assert result.count == 1
    assert result.cases[0].case_uuid == SYNTHETIC_CASE_UUID


def test_open_case_posts_manual_ui_source(client, session):
    payload = OpenCaseResponse(
        case=_summary(),
        action_taken="already_open",
        message="Case is open and ready (source=manual_ui).",
    ).model_dump(mode="json")
    session.request.return_value = _mock_response(200, payload)

    result = client.open_case(SYNTHETIC_CASE_UUID)

    call = session.request.call_args
    assert call.args[0] == "POST"
    assert call.args[1].endswith(f"/cases/saved/{SYNTHETIC_CASE_UUID}/open")
    assert call.kwargs["json"] == {"source": "manual_ui"}
    assert result.action_taken == "already_open"


def test_reopen_case_posts_shared_backend_path(client, session):
    payload = ReopenCaseResponse(
        case=_summary(workspace_status="reopened"),
        action_taken="reopened",
        message="Case reopened on the same case workspace.",
        source="manual_ui",
    ).model_dump(mode="json")
    session.request.return_value = _mock_response(200, payload)

    result = client.reopen_case(
        SYNTHETIC_CASE_UUID,
        reason="Steward requested reopen.",
        source="manual_ui",
    )

    call = session.request.call_args
    assert call.args[0] == "POST"
    assert call.args[1].endswith(f"/cases/saved/{SYNTHETIC_CASE_UUID}/reopen")
    assert call.kwargs["json"] == {
        "source": "manual_ui",
        "reason": "Steward requested reopen.",
    }
    assert result.action_taken == "reopened"


def test_get_timeline_default_oldest_first(client, session):
    event = CaseTimelineEvent(
        case_uuid=SYNTHETIC_CASE_UUID,
        event_type="case_created",
        event_timestamp=datetime(2026, 7, 1, 12, 0, tzinfo=UTC),
        title="Case created",
        references=CaseTimelineEventReferences(),
    )
    payload = SavedCaseTimelineResponse(
        case_uuid=SYNTHETIC_CASE_UUID,
        order="oldest_first",
        count=1,
        events=[event],
    ).model_dump(mode="json")
    session.request.return_value = _mock_response(200, payload)

    result = client.get_timeline(SYNTHETIC_CASE_UUID)

    assert session.request.call_args.kwargs["params"] == {"order": "oldest_first"}
    assert result.count == 1
    assert result.events[0].event_type == "case_created"


def test_activate_case_open_for_active_workspace(client):
    summary = _summary(workspace_status="open")
    open_response = OpenCaseResponse(
        case=summary,
        action_taken="already_open",
        message="Case is open and ready (source=manual_ui).",
    )
    with patch.object(client, "open_case", return_value=open_response) as mock_open:
        with patch.object(client, "reopen_case") as mock_reopen:
            result = client.activate_case(summary)

    mock_open.assert_called_once_with(SYNTHETIC_CASE_UUID, source="manual_ui")
    mock_reopen.assert_not_called()
    assert result.action_taken == "already_open"


def test_activate_case_reopen_for_closed_workspace(client):
    summary = _summary(
        workspace_status="closed",
        actions=["open_case", "reopen_case", "view_timeline"],
    )
    reopen_response = ReopenCaseResponse(
        case=_summary(workspace_status="reopened"),
        action_taken="reopened",
        message="Case reopened on the same case workspace.",
        source="manual_ui",
    )
    with patch.object(client, "reopen_case", return_value=reopen_response) as mock_reopen:
        with patch.object(client, "open_case") as mock_open:
            result = client.activate_case(summary)

    mock_reopen.assert_called_once_with(
        SYNTHETIC_CASE_UUID,
        reason=None,
        source="manual_ui",
    )
    mock_open.assert_not_called()
    assert result.action_taken == "reopened"


def test_run_action_view_timeline(client):
    timeline = SavedCaseTimelineResponse(
        case_uuid=SYNTHETIC_CASE_UUID,
        order="oldest_first",
        count=0,
        events=[],
    )
    with patch.object(client, "get_timeline", return_value=timeline) as mock_timeline:
        result = client.run_action(SYNTHETIC_CASE_UUID, "view_timeline")

    mock_timeline.assert_called_once_with(SYNTHETIC_CASE_UUID)
    assert result.count == 0


def test_api_error_raises_saved_case_api_error(client, session):
    session.request.return_value = _mock_response(404, {"detail": "Case not found"})

    with pytest.raises(SavedCaseApiError) as exc_info:
        client.get_saved_case("missing-uuid")

    assert exc_info.value.status_code == 404
    assert "Case not found" in exc_info.value.detail


def test_ai_command_reopen_uses_same_reopen_endpoint(client, session):
    payload = ReopenCaseResponse(
        case=_summary(workspace_status="reopened"),
        action_taken="reopened",
        message="Case reopened on the same case workspace.",
        source="ai_command",
    ).model_dump(mode="json")
    session.request.return_value = _mock_response(200, payload)

    result = client.reopen_case(SYNTHETIC_CASE_UUID, source="ai_command", reason="Reopen case 42")

    assert session.request.call_args.kwargs["json"]["source"] == "ai_command"
    assert result.source == "ai_command"
