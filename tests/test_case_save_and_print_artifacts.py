"""Save and Print + steward case history + official artifact continuity tests."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.case_saved_artifact_schema import (
    SaveAndPrintGrievanceRequest,
    SaveAndPrintReportRequest,
)
from app.services.case_saved_artifact_service import CaseSavedArtifactService
from app.services.case_service import CaseService


def _case_row(**overrides):
    base = dict(
        id=1,
        case_uuid="case-sp-1",
        title="Leave case",
        user_name="Steward A",
        local_number="300",
        initial_question="Can leave be canceled?",
        known_facts={"approved": True},
        status="open",
        report_versions=[
            SimpleNamespace(
                id=10,
                version_number=2,
                report_data={"report": {"quick_assessment": {"summary": "Likely grievable", "grievability": "Likely Grievable"}}},
                report_summary={"primary_issue": "Leave revocation", "authority_count": 1},
                issue_analysis={"primary_issue": "Leave revocation"},
                ranked_authorities=[],
                evidence_items=[],
                retrieval_gaps={},
                source_coverage_audit=[],
            )
        ],
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_save_and_print_report_persists_before_pdf_and_versions():
    db = MagicMock()
    case = _case_row()
    service = CaseSavedArtifactService(db)
    created = []

    def _add(obj):
        created.append(obj)
        if hasattr(obj, "artifact_uuid") and not getattr(obj, "id", None):
            obj.id = len(created)

    db.add.side_effect = _add
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = (0,)
    db.query.return_value.filter.return_value.all.return_value = []

    with (
        patch.object(CaseService, "_get_case_row", return_value=case),
        patch.object(service, "_current_step_type", return_value="step_2_appeal"),
        patch.object(service, "_find_by_idempotency", return_value=None),
        patch.object(service, "_next_artifact_version", side_effect=[1, 2]),
        patch.object(service, "_clear_latest_flag"),
        patch.object(service, "_append_timeline"),
        patch(
            "app.services.case_saved_artifact_service.ReportExportService.export_case_pdf",
            return_value=(b"%PDF-report", "report.pdf"),
        ),
        patch.object(
            service._assets,
            "store_system_generated_file",
            return_value=SimpleNamespace(asset_uuid="pdf-1"),
        ),
    ):
        first = service.save_and_print_report(
            "case-sp-1",
            SaveAndPrintReportRequest(idempotency_key="rep-1", prepare_pdf=True),
        )
        second = service.save_and_print_report(
            "case-sp-1",
            SaveAndPrintReportRequest(idempotency_key="rep-2", prepare_pdf=True),
        )

    assert first.status == "saved"
    assert first.print_ready is True
    assert first.artifact.version_number == 1
    assert second.artifact.version_number == 2
    assert db.commit.call_count == 2


def test_save_and_print_report_keeps_artifact_when_pdf_fails():
    db = MagicMock()
    case = _case_row()
    service = CaseSavedArtifactService(db)
    db.add.side_effect = lambda obj: setattr(obj, "id", 1)

    with (
        patch.object(CaseService, "_get_case_row", return_value=case),
        patch.object(service, "_current_step_type", return_value="step_2_appeal"),
        patch.object(service, "_find_by_idempotency", return_value=None),
        patch.object(service, "_next_artifact_version", return_value=1),
        patch.object(service, "_clear_latest_flag"),
        patch.object(service, "_append_timeline"),
        patch(
            "app.services.case_saved_artifact_service.ReportExportService.export_case_pdf",
            side_effect=RuntimeError("weasyprint missing"),
        ),
    ):
        result = service.save_and_print_report(
            "case-sp-1",
            SaveAndPrintReportRequest(prepare_pdf=True),
        )

    assert result.status == "saved_pdf_failed"
    assert result.print_ready is False
    assert result.artifact is not None
    db.commit.assert_called_once()


def test_save_and_print_idempotent_replay_does_not_duplicate():
    db = MagicMock()
    service = CaseSavedArtifactService(db)
    existing = SimpleNamespace(
        case_uuid="case-sp-1",
        artifact_uuid="art-1",
        artifact_type="analysis_report",
        title="Analysis Report v1",
        version_number=1,
        version_label="Analysis Report v1",
        grievance_step="step_2_appeal",
        template_id=None,
        template_version=None,
        printed=True,
        pdf_status="ready",
        pdf_asset_uuid="pdf-1",
        is_latest_official=True,
        saved_by="Steward A",
        saved_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        source_report_version_number=2,
        source_draft_record_uuid=None,
        key_summary_json={"primary_issue": "Leave"},
    )
    with (
        patch.object(CaseService, "_get_case_row", return_value=_case_row()),
        patch.object(service, "_find_by_idempotency", return_value=existing),
    ):
        result = service.save_and_print_report(
            "case-sp-1",
            SaveAndPrintReportRequest(idempotency_key="same"),
        )
    assert result.status == "idempotent_replay"
    db.commit.assert_not_called()


def test_save_and_print_grievance_persists_field_values():
    db = MagicMock()
    case = _case_row()
    service = CaseSavedArtifactService(db)
    captured = {}

    def _add(obj):
        captured[type(obj).__name__] = obj
        obj.id = 1

    db.add.side_effect = _add
    step = SimpleNamespace(id=5, step_type="step_2_appeal")

    with (
        patch.object(CaseService, "_get_case_row", return_value=case),
        patch.object(service, "_find_by_idempotency", return_value=None),
        patch.object(service, "_next_artifact_version", return_value=1),
        patch.object(service, "_clear_latest_flag"),
        patch.object(service, "_append_timeline"),
        patch.object(service, "_require_or_ensure_step", return_value=step),
        patch.object(
            service,
            "_render_grievance_fields_pdf",
            return_value=b"%PDF-grievance",
        ),
        patch.object(
            service._assets,
            "store_system_generated_file",
            return_value=SimpleNamespace(asset_uuid="g-pdf-1"),
        ),
    ):
        result = service.save_and_print_grievance(
            "case-sp-1",
            SaveAndPrintGrievanceRequest(
                template_id="local_300_form_79_1",
                template_version="1.0",
                grievance_step="step_2_appeal",
                field_values={
                    "grievant_name": "Synthetic Worker",
                    "corrective_action_requested": "Make whole",
                },
                steward_override_field_ids=["grievant_name"],
                prepare_pdf=True,
            ),
        )

    draft = captured["CaseFormDraftRecord"]
    artifact = captured["CaseSavedArtifact"]
    assert draft.field_values["grievant_name"] == "Synthetic Worker"
    assert draft.is_official is True
    assert draft.template_version == "1.0"
    assert artifact.content_json["field_values"]["corrective_action_requested"] == "Make whole"
    assert result.print_ready is True
    assert result.artifact.artifact_type == "grievance_form"


def test_continuity_includes_official_artifacts_bounded():
    case = SimpleNamespace(
        case_uuid="case-a",
        title="A",
        status="open",
        initial_question="Q",
        known_facts={},
        user_name=None,
        local_number=None,
        messages=[],
        report_versions=[],
        assets=[],
    )
    artifacts = [
        {
            "artifact_uuid": "a1",
            "artifact_type": "analysis_report",
            "title": "Analysis Report v1",
            "version": 1,
            "is_latest_official": True,
            "printed": True,
            "content_embedded": False,
        },
        {
            "artifact_uuid": "g1",
            "artifact_type": "grievance_form",
            "title": "Step 2 Grievance v1",
            "version": 1,
            "is_latest_official": True,
            "printed": True,
            "key_field_values": {"grievant_name": "Synthetic"},
            "content_embedded": False,
        },
    ]
    ctx = CaseService.build_bounded_ai_context(case, official_artifacts=artifacts)
    assert ctx["latest_official_report"]["artifact_uuid"] == "a1"
    assert ctx["latest_official_grievance"]["key_field_values"]["grievant_name"] == "Synthetic"
    assert ctx["persistence_notes"]["full_artifact_bodies_embedded"] is False
    assert all(item.get("content_embedded") is False for item in ctx["official_artifacts"])


def test_case_history_filters_and_isolates_by_case_uuid():
    db = MagicMock()
    service = CaseSavedArtifactService(db)
    rows = [
        SimpleNamespace(
            event_uuid="e1",
            event_type="analysis_report_saved_and_printed",
            title="Saved Analysis Report v1",
            details=None,
            event_timestamp=datetime(2026, 1, 2, tzinfo=timezone.utc),
            export_ref="art-1",
            report_version_number=2,
            draft_record_uuid=None,
            upload_refs=None,
            case_uuid="case-a",
        ),
        SimpleNamespace(
            event_uuid="e2",
            event_type="context_saved",
            title="noise",
            details=None,
            event_timestamp=datetime(2026, 1, 3, tzinfo=timezone.utc),
            export_ref=None,
            report_version_number=None,
            draft_record_uuid=None,
            upload_refs=None,
            case_uuid="case-a",
        ),
    ]
    query = MagicMock()
    db.query.return_value = query
    query.filter.return_value = query
    query.order_by.return_value = query
    query.limit.return_value = query
    query.all.side_effect = [
        [rows[0]],  # filtered steward events
        [
            SimpleNamespace(
                artifact_uuid="art-1",
                artifact_type="analysis_report",
                version_label="Analysis Report v1",
                saved_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
                printed=True,
                case_uuid="case-a",
            )
        ],
    ]

    with patch.object(CaseService, "_get_case_row", return_value=_case_row(case_uuid="case-a")):
        history = service.list_steward_case_history("case-a", order="oldest_first")

    assert history.count == 1
    assert history.events[0].clickable is True
    assert history.events[0].retrieval_path.endswith("/artifacts/art-1")
    # Isolation: filter includes case_uuid
    assert query.filter.called


def test_saved_case_list_is_paginated_summary_only():
    from app.services.saved_case_service import SavedCaseService
    from app.schemas.saved_case_schema import SavedCaseSummary

    summaries = [
        SavedCaseSummary(
            case_id=i,
            case_uuid=f"c-{i}",
            title=f"T{i}",
            workspace_status="open",
            legacy_case_status="open",
            last_activity_at=datetime(2026, 1, i + 1, tzinfo=timezone.utc),
        )
        for i in range(1, 6)
    ]
    db = MagicMock()
    expected_page = [summaries[2], summaries[1]]

    with patch.object(
        SavedCaseService,
        "_query_saved_case_page",
        return_value=(expected_page, 5),
    ) as query_page:
        page = SavedCaseService.list_saved_cases(db, limit=2, offset=2)

    assert page.total == 5
    assert page.count == 2
    assert page.has_more is True
    assert page.payload_mode == "summary_only"
    # newest_first: c-5..c-1; offset 2 limit 2 => c-3, c-2
    assert [c.case_uuid for c in page.cases] == ["c-3", "c-2"]
    query_page.assert_called_once_with(
        db,
        status_filter="all",
        step_filter=None,
        search=None,
        newest_first=True,
        limit=2,
        offset=2,
    )


def test_steward_ui_routes_registered():
    client = TestClient(app)
    paths = set(client.get("/openapi.json").json()["paths"])
    assert "/ui" in paths
    assert "/ui/cases/{case_uuid}" in paths
    assert "/cases/{case_uuid}/reports/save-and-print" in paths
    assert "/cases/{case_uuid}/grievances/save-and-print" in paths
    assert "/cases/saved/{case_uuid}/history" in paths


def test_workspace_marks_automatic_context_restore():
    created = datetime(2026, 1, 1, tzinfo=timezone.utc)
    case = SimpleNamespace(
        id=1,
        case_uuid="auto-1",
        title="Auto",
        user_name=None,
        local_number=None,
        initial_question="Q",
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
            side_effect=CaseStepProgressionNotFoundError("auto-1"),
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
            return_value=[{"artifact_uuid": "a1", "artifact_type": "analysis_report", "is_latest_official": True}],
        ),
        patch(
            "app.services.case_saved_artifact_service.CaseSavedArtifactService."
            "list_steward_case_history",
            return_value=SimpleNamespace(
                model_dump=lambda mode="json": {"events": [], "count": 0}
            ),
        ),
        patch(
            "app.services.case_saved_artifact_service.CaseSavedArtifactService."
            "list_artifacts",
            return_value=SimpleNamespace(artifacts=[]),
        ),
    ):
        workspace = CaseService.get_case_workspace(db, "auto-1")

    assert workspace["ai_context_restored"] is True
    assert workspace["restore_action_required"] is False
    assert workspace["ai_continuity_context"]["official_artifacts"][0]["artifact_uuid"] == "a1"
