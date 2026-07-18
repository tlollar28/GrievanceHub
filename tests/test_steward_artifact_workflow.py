"""Approved steward workspace flow: temporary previews; artifacts begin at Save."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.schemas.case_saved_artifact_schema import SaveAndPrintReportRequest
from app.schemas.case_workspace_action_schema import CaseInteractionRequest
from app.services.case_saved_artifact_service import CaseSavedArtifactService
from app.services.case_service import CaseService
from app.services.case_workspace_action_service import CaseWorkspaceActionService
from app.services.follow_up_chat_service import FollowUpChatService

CASE_A = "11111111-1111-4111-8111-111111111111"


def _case(**overrides):
    base = dict(
        id=601,
        case_uuid=CASE_A,
        status="open",
        user_name="Steward A",
        initial_question="Was overtime improperly assigned?",
        known_facts={"grievant_name": "Pat Lee"},
        report_versions=[],
        messages=[],
        title="Overtime case",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _inspection(**overrides):
    base = dict(
        case=_case(),
        has_analysis_report=False,
        latest_report_version_id=None,
        latest_report_version_number=None,
        has_step_progression=True,
        current_step_type="step_1_initial",
        template_id=None,
        template_availability_status="unconfirmed_pending_steward_confirmation",
        template_available=False,
        case_status="open",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _follow_up_result(*, answer="Grounded reply."):
    user = SimpleNamespace(
        id=9001,
        role="user",
        content="Question",
        message_metadata={"intent": "follow_up"},
        created_at=datetime(2026, 7, 10, 21, 0, tzinfo=UTC),
        case_id=601,
    )
    assistant = SimpleNamespace(
        id=9002,
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
        "linked_report_version": None,
        "requires_report_regen": False,
        "suggested_actions": [],
    }


def _preview(*, suggested=1):
    return {
        "temporary": True,
        "persisted": False,
        "review_mode": "read_only",
        "editable": False,
        "suggested_version_number_if_saved": suggested,
        "report_data": {"report": {"quick_assessment": {"summary": "ok"}}},
        "ranked_authorities": [],
        "issue_analysis": {},
        "evidence_items": [],
        "retrieval_gaps": {},
        "source_coverage_audit": [],
        "report_summary": {"primary_issue": "overtime"},
    }


def test_chat_does_not_auto_generate_analysis_report():
    service = CaseWorkspaceActionService(MagicMock())
    follow = _follow_up_result()
    with (
        patch.object(
            service, "_inspect_workspace", side_effect=[_inspection(), _inspection()]
        ),
        patch.object(FollowUpChatService, "answer_follow_up", return_value=follow),
        patch.object(
            service,
            "_enrich_interaction_message_metadata",
            return_value={"analysis_auto_refreshed": False},
        ),
        patch.object(CaseService, "generate_report_version") as mock_regen,
        patch.object(CaseService, "build_analysis_report_preview") as mock_preview,
        patch.object(service, "_append_timeline_safe") as mock_timeline,
    ):
        result = service.submit_interaction(
            CASE_A, CaseInteractionRequest(message="What about Article 10?")
        )

    assert result.status == "completed"
    assert result.analysis_versions_created == 0
    mock_regen.assert_not_called()
    mock_preview.assert_not_called()
    mock_timeline.assert_not_called()


def test_generate_analysis_creates_temporary_preview_only():
    service = CaseWorkspaceActionService(MagicMock())
    preview = _preview()
    with (
        patch.object(service, "_inspect_workspace", return_value=_inspection()),
        patch.object(
            CaseService, "build_analysis_report_preview", return_value=preview
        ) as mock_preview,
        patch.object(CaseService, "generate_report_version") as mock_persist,
        patch.object(CaseService, "persist_report_version_from_preview") as mock_save,
        patch(
            "app.services.case_domain_event_service.CaseDomainEventService.publish"
        ) as mock_publish,
    ):
        result = service.generate_analysis_report(CASE_A)

    assert result.status == "completed"
    assert result.analysis_preview_ready is True
    assert result.analysis_editable is False
    assert result.analysis_preview == preview
    assert result.official_artifact_created is False
    assert result.current_report_version_number is None
    assert result.analysis_update.new_report_version_id is None
    mock_preview.assert_called_once()
    mock_persist.assert_not_called()
    mock_save.assert_not_called()
    mock_publish.assert_not_called()


def test_cancel_preview_leaves_no_version_artifact_or_ocr_side_effects():
    """Cancel is client-side discard; generate must not have persisted anything."""
    service = CaseWorkspaceActionService(MagicMock())
    with (
        patch.object(service, "_inspect_workspace", return_value=_inspection()),
        patch.object(
            CaseService, "build_analysis_report_preview", return_value=_preview()
        ),
        patch.object(CaseService, "persist_report_version_from_preview") as mock_save,
        patch(
            "app.services.case_domain_event_service.CaseDomainEventService.publish"
        ) as mock_publish,
        patch.object(service, "_append_timeline_safe") as mock_timeline,
    ):
        result = service.generate_analysis_report(CASE_A)
        # Steward Cancel: discard returned preview; no further service call.
        discarded = result.analysis_preview
        assert discarded is not None

    mock_save.assert_not_called()
    mock_publish.assert_not_called()
    mock_timeline.assert_not_called()


def test_save_preview_creates_v1_then_v2_without_cancelled_skips():
    db = MagicMock()
    service = CaseSavedArtifactService(db)
    case = _case(report_versions=[])
    created_versions = []

    def _persist(_db, case_uuid, preview, **kwargs):
        n = len(created_versions) + 1
        version = SimpleNamespace(
            id=100 + n,
            version_number=n,
            report_data=preview["report_data"],
            report_summary=preview["report_summary"],
            issue_analysis={},
            ranked_authorities=[],
            evidence_items=[],
            retrieval_gaps={},
            source_coverage_audit=[],
        )
        created_versions.append(version)
        case.report_versions = list(created_versions)
        return version

    captured_events = []

    def _publish(*args, **kwargs):
        captured_events.append(kwargs.get("event_type"))
        return SimpleNamespace(event_id="e1")

    with (
        patch.object(service, "_require_case", return_value=case),
        patch.object(CaseService, "persist_report_version_from_preview", side_effect=_persist),
        patch.object(CaseService, "get_case", return_value=case),
        patch.object(service, "_current_step_type", return_value="step_1_initial"),
        patch.object(
            service, "_next_artifact_version", side_effect=[1, 2]
        ),
        patch.object(service, "_clear_latest_flag"),
        patch.object(service, "_report_key_summary", return_value={"key_conclusions": "x"}),
        patch.object(service, "_append_timeline"),
        patch.object(service, "_find_by_idempotency", return_value=None),
        patch(
            "app.services.case_domain_event_service.CaseDomainEventService.publish",
            side_effect=_publish,
        ),
        patch("app.services.case_workflow_service.CaseWorkflowService.transition"),
    ):
        # Cancelled preview would never call save — only these two Saves.
        r1 = service.save_and_print_report(
            CASE_A,
            SaveAndPrintReportRequest(preview=_preview(suggested=1), prepare_pdf=False),
        )
        r2 = service.save_and_print_report(
            CASE_A,
            SaveAndPrintReportRequest(preview=_preview(suggested=2), prepare_pdf=False),
        )

    assert r1.status == "saved"
    assert r2.status == "saved"
    assert [v.version_number for v in created_versions] == [1, 2]
    assert captured_events == ["analysis_saved", "analysis_saved"]


def test_grievance_generate_is_temporary_draft_only():
    service = CaseWorkspaceActionService(MagicMock())
    case = _case()
    with (
        patch.object(service, "_inspect_workspace", return_value=_inspection()),
        patch.object(CaseService, "_get_case_row", return_value=case),
        patch(
            "app.services.case_domain_event_service.CaseDomainEventService.publish"
        ) as mock_publish,
        patch.object(service, "_append_timeline_safe") as mock_timeline,
    ):
        result = service.generate_grievance(CASE_A)

    assert result.status == "completed"
    assert result.grievance_generation.editable is True
    assert result.grievance_generation.official_artifact_created is False
    assert result.grievance_generation.field_values
    mock_publish.assert_not_called()
    mock_timeline.assert_not_called()


def test_grievance_cancel_creates_no_artifact():
    """Cancel discards the returned draft; Save is the only persistence path."""
    service = CaseWorkspaceActionService(MagicMock())
    with (
        patch.object(service, "_inspect_workspace", return_value=_inspection()),
        patch.object(CaseService, "_get_case_row", return_value=_case()),
    ):
        result = service.generate_grievance(CASE_A)
    draft = result.grievance_generation
    assert draft.official_artifact_created is False
    # No save-and-print call on Cancel — draft remains ephemeral.
    assert draft.field_values is not None


def test_artifacts_list_only_includes_saved_artifacts():
    db = MagicMock()
    service = CaseSavedArtifactService(db)
    rows = [
        SimpleNamespace(
            artifact_uuid="a1",
            case_uuid=CASE_A,
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
            saved_by="Steward",
            saved_at=datetime(2026, 7, 10, tzinfo=UTC),
            source_report_version_number=1,
            source_draft_record_uuid=None,
            key_summary_json={},
            content_json={},
        ),
    ]
    query = MagicMock()
    query.filter.return_value = query
    query.order_by.return_value = query
    query.all.return_value = rows
    db.query.return_value = query

    with patch.object(service, "_require_case", return_value=_case()):
        listed = service.list_artifacts(CASE_A)

    assert listed.count == 1
    assert listed.groups["analysis_reports"][0].title == "Analysis Report v1"
    assert listed.groups["grievances"] == []


def test_steward_ui_exposes_approved_controls():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    home = client.get("/ui")
    assert home.status_code == 200
    assert "New Case" in home.text
    workspace = client.get(f"/ui/cases/{CASE_A}")
    assert workspace.status_code == 200
    html = workspace.text
    assert "Generate Analysis Report" in html
    assert "Generate Grievance" in html
    assert "preview: analysisPreview" in html
    assert "prepare_pdf: preparePdf" in html
    assert "Analysis preview discarded" in html
    assert "Grievance draft discarded" in html


def test_reports_generate_route_returns_preview_not_version():
    from fastapi.testclient import TestClient

    from app.main import app
    from app.schemas.case_workspace_action_schema import WorkspaceActionResponse

    client = TestClient(app)
    expected = WorkspaceActionResponse(
        case_uuid=CASE_A,
        action="generate_analysis_report",
        status="completed",
        message="Temporary preview",
        analysis_preview_ready=True,
        analysis_editable=False,
        analysis_preview=_preview(),
        official_artifact_created=False,
    )
    with patch.object(
        CaseWorkspaceActionService, "generate_analysis_report", return_value=expected
    ):
        res = client.post(f"/cases/{CASE_A}/reports/generate", json={})
    assert res.status_code == 200
    body = res.json()
    assert body["persisted"] is False
    assert body["report_version"] is None
    assert body["preview"]["temporary"] is True
    assert body["preview"]["report_data"]
