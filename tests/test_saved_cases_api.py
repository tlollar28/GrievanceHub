"""API tests for saved cases list/open/reopen/timeline (Phase 1.4E)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.saved_case_schema import (
    OpenCaseResponse,
    ReopenCaseResponse,
    SavedCaseListResponse,
    SavedCaseSummary,
    SavedCaseTemplateAvailability,
    SavedCaseTimelineResponse,
)
from app.schemas.case_step_progression_schema import CaseTimelineEvent, CaseTimelineEventReferences
from app.services.case_service import CaseNotFoundError
from app.services.saved_case_service import SavedCaseService

SYNTHETIC_CASE_UUID = "00000000-0000-4000-8000-000000000301"
SYNTHETIC_CASE_ID = 301


def _summary(
    *,
    workspace_status: str = "open",
    legacy_status: str = "open",
    actions: list[str] | None = None,
    last_activity: datetime | None = None,
) -> SavedCaseSummary:
    return SavedCaseSummary(
        case_id=SYNTHETIC_CASE_ID,
        case_uuid=SYNTHETIC_CASE_UUID,
        case_number=str(SYNTHETIC_CASE_ID),
        title="Synthetic saved case",
        issue_summary="Synthetic issue summary for testing.",
        grievant_or_class="Synthetic Grievant",
        current_step_type="step_1_initial",
        current_step_status="open",
        workspace_status=workspace_status,  # type: ignore[arg-type]
        legacy_case_status=legacy_status,
        created_at=datetime(2026, 7, 1, 12, 0, tzinfo=UTC),
        last_activity_at=last_activity or datetime(2026, 7, 6, 12, 0, tzinfo=UTC),
        closed_at=None,
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


def _timeline_event(event_type: str, ts: datetime) -> CaseTimelineEvent:
    return CaseTimelineEvent(
        case_uuid=SYNTHETIC_CASE_UUID,
        event_type=event_type,  # type: ignore[arg-type]
        event_timestamp=ts,
        title=f"Synthetic {event_type}",
        references=CaseTimelineEventReferences(),
    )


@pytest.fixture
def client():
    return TestClient(app)


def test_list_saved_cases_returns_summaries(client):
    newer = _summary(last_activity=datetime(2026, 7, 6, 18, 0, tzinfo=UTC))
    older = _summary(
        workspace_status="closed",
        legacy_status="closed",
        actions=["open_case", "reopen_case", "view_timeline"],
        last_activity=datetime(2026, 7, 5, 10, 0, tzinfo=UTC),
    )
    older.case_uuid = "00000000-0000-4000-8000-000000000302"
    older.case_id = 302
    payload = SavedCaseListResponse(
        count=2,
        order="newest_first",
        status_filter="all",
        cases=[newer, older],
    )
    with patch.object(SavedCaseService, "list_saved_cases", return_value=payload):
        response = client.get("/cases/saved")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    assert body["order"] == "newest_first"
    assert body["cases"][0]["case_uuid"] == SYNTHETIC_CASE_UUID


def test_list_saved_cases_supports_oldest_first(client):
    with patch.object(
        SavedCaseService,
        "list_saved_cases",
        return_value=SavedCaseListResponse(
            count=0,
            order="oldest_first",
            status_filter="all",
            cases=[],
        ),
    ) as mock_list:
        response = client.get("/cases/saved?order=oldest_first")

    assert response.status_code == 200
    mock_list.assert_called_once()
    assert mock_list.call_args.kwargs["newest_first"] is False


def test_list_saved_cases_closed_filter(client):
    closed = _summary(
        workspace_status="closed",
        legacy_status="closed",
        actions=["open_case", "reopen_case", "view_timeline"],
    )
    with patch.object(
        SavedCaseService,
        "list_saved_cases",
        return_value=SavedCaseListResponse(
            count=1,
            order="newest_first",
            status_filter="closed",
            cases=[closed],
        ),
    ) as mock_list:
        response = client.get("/cases/saved?status=closed")

    assert response.status_code == 200
    assert mock_list.call_args.kwargs["status_filter"] == "closed"
    assert "reopen_case" in response.json()["cases"][0]["available_actions"]


def test_get_saved_case_detail(client):
    summary = _summary()
    with patch.object(SavedCaseService, "get_saved_case", return_value=summary):
        response = client.get(f"/cases/saved/{SYNTHETIC_CASE_UUID}")

    assert response.status_code == 200
    assert response.json()["case_uuid"] == SYNTHETIC_CASE_UUID


def test_get_saved_case_not_found(client):
    with patch.object(SavedCaseService, "get_saved_case", side_effect=CaseNotFoundError("x")):
        response = client.get("/cases/saved/missing-uuid")

    assert response.status_code == 404


def test_manual_open_open_case(client):
    with patch.object(
        SavedCaseService,
        "open_case",
        return_value=OpenCaseResponse(
            case=_summary(),
            action_taken="already_open",
            message="Case is open and ready (source=manual_ui).",
        ),
    ) as mock_open:
        response = client.post(
            f"/cases/saved/{SYNTHETIC_CASE_UUID}/open",
            json={"source": "manual_ui"},
        )

    assert response.status_code == 200
    mock_open.assert_called_once()
    assert mock_open.call_args.kwargs["source"] == "manual_ui"
    assert response.json()["action_taken"] == "already_open"


def test_closed_case_open_requires_reopen(client):
    with patch.object(
        SavedCaseService,
        "open_case",
        return_value=OpenCaseResponse(
            case=_summary(
                workspace_status="closed",
                legacy_status="closed",
                actions=["open_case", "reopen_case", "view_timeline"],
            ),
            action_taken="closed_requires_reopen",
            message="Case is closed. Use reopen_case to resume work on the same case workspace.",
        ),
    ):
        response = client.post(f"/cases/saved/{SYNTHETIC_CASE_UUID}/open")

    assert response.status_code == 200
    assert response.json()["action_taken"] == "closed_requires_reopen"


def test_manual_reopen_calls_shared_service(client):
    with patch.object(
        SavedCaseService,
        "reopen_case",
        return_value=ReopenCaseResponse(
            case=_summary(workspace_status="reopened"),
            action_taken="reopened",
            message="Case reopened on the same case workspace.",
            source="manual_ui",
        ),
    ) as mock_reopen:
        response = client.post(
            f"/cases/saved/{SYNTHETIC_CASE_UUID}/reopen",
            json={"source": "manual_ui", "reason": "Synthetic steward reopen."},
        )

    assert response.status_code == 200
    mock_reopen.assert_called_once()
    assert mock_reopen.call_args.kwargs["source"] == "manual_ui"
    assert mock_reopen.call_args.kwargs["reason"] == "Synthetic steward reopen."
    assert response.json()["action_taken"] == "reopened"


def test_ai_command_reopen_uses_same_service(client):
    with patch.object(
        SavedCaseService,
        "reopen_case",
        return_value=ReopenCaseResponse(
            case=_summary(workspace_status="reopened"),
            action_taken="reopened",
            message="Case reopened on the same case workspace.",
            source="ai_command",
        ),
    ) as mock_reopen:
        response = client.post(
            f"/cases/saved/{SYNTHETIC_CASE_UUID}/reopen",
            json={"source": "ai_command", "reason": "Reopen case 42"},
        )

    assert response.status_code == 200
    assert mock_reopen.call_args.kwargs["source"] == "ai_command"


def test_reopen_already_open_is_idempotent(client):
    with patch.object(
        SavedCaseService,
        "reopen_case",
        return_value=ReopenCaseResponse(
            case=_summary(),
            action_taken="already_open",
            message="Case is already open; no reopen timeline event added.",
            source="manual_ui",
        ),
    ):
        response = client.post(f"/cases/saved/{SYNTHETIC_CASE_UUID}/reopen")

    assert response.status_code == 200
    assert response.json()["action_taken"] == "already_open"


def test_timeline_oldest_first(client):
    events = [
        _timeline_event("case_created", datetime(2026, 7, 1, 12, 0, tzinfo=UTC)),
        _timeline_event("case_closed", datetime(2026, 7, 2, 12, 0, tzinfo=UTC)),
        _timeline_event("case_reopened", datetime(2026, 7, 3, 12, 0, tzinfo=UTC)),
    ]
    with patch.object(
        SavedCaseService,
        "get_case_timeline",
        return_value=SavedCaseTimelineResponse(
            case_uuid=SYNTHETIC_CASE_UUID,
            order="oldest_first",
            count=3,
            events=events,
        ),
    ) as mock_timeline:
        response = client.get(f"/cases/saved/{SYNTHETIC_CASE_UUID}/timeline")

    assert response.status_code == 200
    mock_timeline.assert_called_once()
    assert mock_timeline.call_args.kwargs["newest_first"] is False
    body = response.json()
    assert body["count"] == 3
    assert body["events"][0]["event_type"] == "case_created"


def test_timeline_newest_first(client):
    with patch.object(
        SavedCaseService,
        "get_case_timeline",
        return_value=SavedCaseTimelineResponse(
            case_uuid=SYNTHETIC_CASE_UUID,
            order="newest_first",
            count=0,
            events=[],
        ),
    ) as mock_timeline:
        response = client.get(
            f"/cases/saved/{SYNTHETIC_CASE_UUID}/timeline?order=newest_first"
        )

    assert response.status_code == 200
    assert mock_timeline.call_args.kwargs["newest_first"] is True


def test_saved_routes_do_not_shadow_legacy_get_case(client):
    summary = _summary()
    with patch.object(SavedCaseService, "get_saved_case", return_value=summary):
        saved_response = client.get(f"/cases/saved/{SYNTHETIC_CASE_UUID}")
    assert saved_response.status_code == 200
    assert "workspace_status" in saved_response.json()
