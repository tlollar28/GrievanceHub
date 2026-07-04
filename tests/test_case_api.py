"""Case workspace API route tests."""

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.case_service import CaseNotFoundError, CaseReportRequiredError, CaseService

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "reports" / "sample_wrapper_report.json"
CASE_UUID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def _report_version(version_number=1, **overrides):
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    created = datetime(2026, 1, 1, tzinfo=timezone.utc)
    base = {
        "id": version_number,
        "version_number": version_number,
        "trigger_message_id": None,
        "created_at": created,
        "report_data": payload,
        "ranked_authorities": payload.get("ranked_authorities", []),
        "issue_analysis": payload.get("issue_analysis", {}),
        "evidence_items": [],
        "retrieval_gaps": payload.get("retrieval_gaps"),
        "source_coverage_audit": payload.get("retrieval_gaps", {}).get("source_coverage_audit"),
        "report_summary": {
            "primary_issue": "Approved annual leave cancellation",
            "articles": ["CIM Article 10"],
            "source_types_found": ["CIM"],
            "authority_count": 1,
            "has_remedy_authority": False,
            "has_source_gaps": True,
            "message_count": 0,
        },
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _sample_case(**overrides):
    created = datetime(2026, 1, 1, tzinfo=timezone.utc)
    version = _report_version()
    base = {
        "case_uuid": CASE_UUID,
        "title": "Leave cancellation",
        "user_name": "Test Steward",
        "local_number": "300",
        "initial_question": "Can management cancel approved leave?",
        "known_facts": {},
        "status": "open",
        "created_at": created,
        "updated_at": created,
        "messages": [],
        "report_versions": [version],
    }
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture
def client():
    return TestClient(app)


def test_list_cases_includes_report_summary(client):
    case = _sample_case()
    with patch.object(CaseService, "list_cases", return_value=[case]):
        response = client.get("/cases/")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    summary = body["cases"][0]
    assert summary["case_uuid"] == CASE_UUID
    assert summary["report_summary"]["authority_count"] == 1
    assert summary["report_summary"]["articles"] == ["CIM Article 10"]
    assert summary["retrieval_gaps_summary"]["has_gaps"] is True


def test_get_workspace_returns_expected_aggregate(client):
    case = _sample_case()
    expected = {
        "case_uuid": case.case_uuid,
        "title": case.title,
        "user_name": case.user_name,
        "local_number": case.local_number,
        "initial_question": case.initial_question,
        "known_facts": case.known_facts,
        "status": case.status,
        "created_at": case.created_at.isoformat(),
        "updated_at": case.updated_at.isoformat(),
        "messages": [],
        "report_versions": [
            CaseService.serialize_report_version_summary(case.report_versions[0])
        ],
        "latest_report_version": 1,
        "latest_report": CaseService.serialize_report_version_summary(case.report_versions[0]),
        "retrieval_gaps": case.report_versions[0].retrieval_gaps,
        "source_coverage_audit": case.report_versions[0].source_coverage_audit,
        "report_summary": case.report_versions[0].report_summary,
        "retrieval_gaps_summary": CaseService.build_retrieval_gaps_summary(
            case.report_versions[0].retrieval_gaps
        ),
        "exports": CaseService.build_export_metadata(CASE_UUID, 1),
    }

    with patch.object(CaseService, "get_case_workspace", return_value=expected):
        response = client.get(f"/cases/{CASE_UUID}/workspace")

    assert response.status_code == 200
    body = response.json()
    assert body["case_uuid"] == CASE_UUID
    assert body["latest_report_version"] == 1
    assert body["report_summary"]["authority_count"] == 1
    assert body["retrieval_gaps"]["unindexed_sources_requested"] == ["LMOU"]
    assert body["exports"]["preview_url"].endswith("/export/preview")


def test_get_case_by_uuid_404_when_missing(client):
    with patch.object(CaseService, "get_case", side_effect=CaseNotFoundError(CASE_UUID)):
        response = client.get(f"/cases/{CASE_UUID}")
    assert response.status_code == 404


def test_workspace_404_when_missing(client):
    with patch.object(CaseService, "get_case_workspace", side_effect=CaseNotFoundError(CASE_UUID)):
        response = client.get(f"/cases/{CASE_UUID}/workspace")
    assert response.status_code == 404


def test_reopen_case_sets_status_open(client):
    case = _sample_case(status="open")
    with patch.object(CaseService, "reopen_case", return_value=case):
        response = client.patch(f"/cases/{CASE_UUID}/status", json={"status": "open"})

    assert response.status_code == 200
    assert response.json()["status"] == "open"


def test_regenerate_report_creates_incremented_version(client):
    v1 = _report_version(1)
    v2 = _report_version(
        2,
        report_summary={
            **v1.report_summary,
            "authority_count": 2,
        },
    )
    case = _sample_case(report_versions=[v1, v2])

    with patch.object(
        CaseService,
        "generate_report_version",
        return_value=v2,
    ) as mock_generate, patch.object(CaseService, "get_case", return_value=case):
        response = client.post(f"/cases/{CASE_UUID}/reports/regenerate", json={"limit_per_source": 8})

    assert response.status_code == 200
    mock_generate.assert_called_once()
    body = response.json()
    assert body["report_version"]["version_number"] == 2
    assert body["report_version"]["report_summary"]["authority_count"] == 2
    assert body["case"]["latest_report_version"] == 2


def test_export_html_does_not_call_retrieval(client):
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    version = SimpleNamespace(
        version_number=1,
        report_data=payload,
        created_at=datetime.now(timezone.utc),
    )
    with patch.object(
        CaseService,
        "get_case",
        return_value=SimpleNamespace(report_versions=[version]),
    ), patch(
        "app.services.case_service.KnowledgeRetrievalService.search_all",
    ) as mock_search:
        response = client.get(f"/cases/{CASE_UUID}/export/html")

    assert response.status_code == 200
    mock_search.assert_not_called()


def test_regenerate_report_404_when_missing(client):
    with patch.object(
        CaseService,
        "generate_report_version",
        side_effect=CaseNotFoundError(CASE_UUID),
    ):
        response = client.post(f"/cases/{CASE_UUID}/reports/regenerate")

    assert response.status_code == 404


def test_post_followup_persists_messages_no_new_report_version(client):
    user_msg = SimpleNamespace(
        id=10,
        role="user",
        content="What evidence am I missing?",
        message_metadata={"intent": "follow_up"},
        created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    assistant_msg = SimpleNamespace(
        id=11,
        role="assistant",
        content="Gather written leave approval.",
        message_metadata={"intent": "follow_up", "answer_type": "missing_evidence"},
        created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    expected = {
        "user_message": user_msg,
        "assistant_message": assistant_msg,
        "answer": assistant_msg.content,
        "answer_type": "missing_evidence",
        "citations": [],
        "disclosures": [],
        "facts_needed": ["Written leave approval"],
        "linked_report_version": {"id": 1, "version_number": 1},
        "requires_report_regen": False,
        "suggested_actions": [],
    }

    with patch(
        "app.api.routes.cases.FollowUpChatService.answer_follow_up",
        return_value=expected,
    ) as mock_answer, patch.object(
        CaseService,
        "generate_report_version",
    ) as mock_regen:
        response = client.post(
            f"/cases/{CASE_UUID}/followups",
            json={"content": "What evidence am I missing?"},
        )

    assert response.status_code == 200
    mock_answer.assert_called_once()
    mock_regen.assert_not_called()
    body = response.json()
    assert body["answer_type"] == "missing_evidence"
    assert body["linked_report_version"]["version_number"] == 1


def test_post_followup_404_when_case_missing(client):
    with patch(
        "app.api.routes.cases.FollowUpChatService.answer_follow_up",
        side_effect=CaseNotFoundError(CASE_UUID),
    ):
        response = client.post(
            f"/cases/{CASE_UUID}/followups",
            json={"content": "Follow-up question?"},
        )
    assert response.status_code == 404


def test_post_followup_400_when_no_report_version(client):
    with patch(
        "app.api.routes.cases.FollowUpChatService.answer_follow_up",
        side_effect=CaseReportRequiredError("Case has no saved report version"),
    ):
        response = client.post(
            f"/cases/{CASE_UUID}/followups",
            json={"content": "Follow-up question?"},
        )
    assert response.status_code == 400


def test_post_followup_422_when_empty_question(client):
    response = client.post(
        f"/cases/{CASE_UUID}/followups",
        json={"content": ""},
    )
    assert response.status_code == 422


def test_get_followups_returns_thread(client):
    thread = {
        "case_uuid": CASE_UUID,
        "linked_report_version": {"id": 1, "version_number": 1},
        "messages": [
            {
                "id": 10,
                "role": "user",
                "content": "What evidence am I missing?",
                "metadata": {"intent": "follow_up"},
                "created_at": "2026-01-02T00:00:00+00:00",
            }
        ],
    }
    with patch(
        "app.api.routes.cases.FollowUpChatService.list_follow_up_thread",
        return_value=thread,
    ):
        response = client.get(f"/cases/{CASE_UUID}/followups")

    assert response.status_code == 200
    body = response.json()
    assert body["case_uuid"] == CASE_UUID
    assert len(body["messages"]) == 1
    assert body["linked_report_version"]["version_number"] == 1


def test_get_followups_404_when_case_missing(client):
    with patch(
        "app.api.routes.cases.FollowUpChatService.list_follow_up_thread",
        side_effect=CaseNotFoundError(CASE_UUID),
    ):
        response = client.get(f"/cases/{CASE_UUID}/followups")
    assert response.status_code == 404
