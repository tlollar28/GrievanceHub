"""Phase W1 workspace action contract — schema and service tests (synthetic data)."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from app.schemas.case_workspace_action_schema import (
    CaseGenerationSnapshotMetadata,
    WorkspaceActionRequest,
    WorkspaceInteractionPayload,
)
from app.services.case_service import CaseNotFoundError, CaseService
from app.services.case_step_progression_service import CaseStepProgressionNotFoundError
from app.services.case_workspace_action_service import (
    CaseWorkspaceActionService,
    _WorkspaceInspection,
)

SYNTHETIC_CASE_UUID = "00000000-0000-4000-8000-000000000401"


def _case(*, status: str = "open", report_versions: list | None = None):
    return SimpleNamespace(
        id=401,
        case_uuid=SYNTHETIC_CASE_UUID,
        status=status,
        report_versions=report_versions
        if report_versions is not None
        else [
            SimpleNamespace(id=11, version_number=1),
            SimpleNamespace(id=12, version_number=2),
        ],
        messages=[],
    )


def _inspection(**overrides) -> _WorkspaceInspection:
    base = dict(
        case=_case(),
        has_analysis_report=True,
        latest_report_version_id=12,
        latest_report_version_number=2,
        has_step_progression=True,
        current_step_type="step_2_appeal",
        template_id="local_300_standard_grievance_form_79_1",
        template_availability_status="available",
        template_available=True,
        case_status="open",
    )
    base.update(overrides)
    return _WorkspaceInspection(**base)


# ---------------------------------------------------------------------------
# Schema parsing
# ---------------------------------------------------------------------------


def test_valid_save_and_update_analysis_request_parsing():
    req = WorkspaceActionRequest.model_validate(
        {
            "action": "save_and_update_analysis",
            "interaction": {
                "message": "Management stated the schedule was changed on July 8.",
                "source": "manual_ui",
            },
        }
    )
    assert req.action == "save_and_update_analysis"
    assert req.interaction is not None
    assert "schedule was changed" in req.interaction.message


def test_valid_generate_grievance_request_parsing():
    req = WorkspaceActionRequest.model_validate(
        {"action": "generate_grievance", "interaction": None}
    )
    assert req.action == "generate_grievance"
    assert req.interaction is None


def test_optional_interaction_payload_fields():
    payload = WorkspaceInteractionPayload(
        clarification="Correct the date to July 9.",
        fact_updates={"incident_date": "2026-07-09"},
        upload_refs=["upload-ref-synthetic-1"],
        source="ai_command",
        pinned_report_version=2,
    )
    assert payload.message is None
    assert payload.fact_updates["incident_date"] == "2026-07-09"
    assert payload.upload_refs == ["upload-ref-synthetic-1"]
    assert payload.source == "ai_command"


def test_invalid_action_rejection():
    with pytest.raises(ValidationError):
        WorkspaceActionRequest.model_validate(
            {"action": "export_grievance_pdf", "interaction": None}
        )


def test_snapshot_metadata_validation():
    snap = CaseGenerationSnapshotMetadata(
        case_uuid=SYNTHETIC_CASE_UUID,
        grievance_step="step_2_appeal",
        analysis_report_version_id=12,
        analysis_report_version_number=2,
        included_follow_up_message_ids=[101, 102],
        included_upload_refs=["ref-a"],
        template_id="local_300_standard_grievance_form_79_1",
        draft_version=1,
        generated_at=datetime(2026, 7, 10, 12, 0, tzinfo=UTC),
        source_action="generate_grievance",
        interaction_id="interaction-synthetic-1",
        source_corpus_version_refs=[],
    )
    assert snap.case_uuid == SYNTHETIC_CASE_UUID
    assert snap.grievance_step == "step_2_appeal"
    assert snap.draft_version == 1
    assert snap.source_action == "generate_grievance"


def test_snapshot_rejects_invalid_draft_version():
    with pytest.raises(ValidationError):
        CaseGenerationSnapshotMetadata(
            case_uuid=SYNTHETIC_CASE_UUID,
            grievance_step="step_2_appeal",
            generated_at=datetime(2026, 7, 10, tzinfo=UTC),
            draft_version=0,
        )


# ---------------------------------------------------------------------------
# Service availability / prerequisites
# ---------------------------------------------------------------------------


def test_missing_case_structured_error():
    db = MagicMock()
    service = CaseWorkspaceActionService(db)
    with patch(
        "app.services.case_workspace_action_service.CaseService.get_case",
        side_effect=CaseNotFoundError(SYNTHETIC_CASE_UUID),
    ):
        result = service.save_and_update_analysis(SYNTHETIC_CASE_UUID, None)

    assert result.status == "case_not_found"
    assert result.missing_prerequisites[0].code == "case_not_found"
    assert result.analysis_update is None


def test_generate_grievance_reports_missing_progression_prerequisite():
    service = CaseWorkspaceActionService(MagicMock())
    inspection = _inspection(
        has_step_progression=False,
        current_step_type=None,
        template_id=None,
        template_availability_status=None,
        template_available=False,
    )
    availability = service._availability_generate_grievance(inspection)
    codes = {p.code for p in availability.missing_prerequisites}
    assert availability.available is False
    assert "step_progression_required" in codes
    assert "step_progression_init_deferred_to_w4" in codes


def test_step_1_template_unavailable():
    service = CaseWorkspaceActionService(MagicMock())
    inspection = _inspection(
        current_step_type="step_1_initial",
        template_id=None,
        template_availability_status="unconfirmed_pending_steward_confirmation",
        template_available=False,
    )
    availability = service._availability_generate_grievance(inspection)
    assert availability.available is False
    assert any(p.code == "template_unavailable" for p in availability.missing_prerequisites)


def test_step_2_template_available_when_prerequisites_represented():
    service = CaseWorkspaceActionService(MagicMock())
    inspection = _inspection()
    availability = service._availability_generate_grievance(inspection)
    assert availability.available is True
    assert availability.template_id == "local_300_standard_grievance_form_79_1"
    assert availability.template_availability == "available"
    assert availability.missing_prerequisites == []


def test_step_3_template_deferred():
    service = CaseWorkspaceActionService(MagicMock())
    inspection = _inspection(
        current_step_type="step_3_appeal",
        template_id=None,
        template_availability_status="deferred_separate_form_required",
        template_available=False,
    )
    availability = service._availability_generate_grievance(inspection)
    assert availability.available is False
    assert any(p.code == "template_deferred" for p in availability.missing_prerequisites)


def test_save_and_update_returns_completed_for_open_case():
    db = MagicMock()
    service = CaseWorkspaceActionService(db)
    prior = SimpleNamespace(id=11, version_number=1)
    new_version = SimpleNamespace(id=12, version_number=2)
    message = SimpleNamespace(id=501)

    with (
        patch.object(
            service,
            "_inspect_workspace",
            side_effect=[
                _inspection(
                    latest_report_version_id=11,
                    latest_report_version_number=1,
                ),
                _inspection(
                    latest_report_version_id=12,
                    latest_report_version_number=2,
                ),
            ],
        ),
        patch.object(
            service,
            "_persist_interaction",
            return_value=(
                message,
                True,
                False,
                {"intent": "update_analysis", "trigger": "update_analysis"},
            ),
        ),
        patch.object(
            CaseService,
            "generate_report_version",
            return_value=new_version,
        ) as mock_regen,
        patch.object(
            service,
            "_append_timeline_safe",
            side_effect=[
                SimpleNamespace(
                    event_id="evt-context",
                    event_type="context_saved",
                    title="Context saved",
                    event_timestamp=datetime(2026, 7, 10, tzinfo=UTC),
                    references=SimpleNamespace(
                        report_version_id=None,
                        report_version_number=None,
                    ),
                ),
                SimpleNamespace(
                    event_id="evt-analysis",
                    event_type="analysis_updated",
                    title="Analysis updated",
                    event_timestamp=datetime(2026, 7, 10, tzinfo=UTC),
                    references=SimpleNamespace(
                        report_version_id=12,
                        report_version_number=2,
                    ),
                ),
            ],
        ),
    ):
        result = service.save_and_update_analysis(
            SYNTHETIC_CASE_UUID,
            WorkspaceInteractionPayload(message="Synthetic clarification."),
        )

    assert result.status == "completed"
    assert result.steward_action_label is None
    save_avail = next(
        a for a in result.available_actions if a.action == "save_and_update_analysis"
    )
    assert save_avail.steward_visible is False
    assert result.analysis_update is not None
    assert result.analysis_update.interaction_saved is True
    assert result.analysis_update.new_report_version_id == 12
    assert result.analysis_update.prior_report_version_number == 1
    assert result.current_report_version_number == 2
    assert result.grievance_generation is None
    mock_regen.assert_called_once()
    assert any(a.action == "save_and_update_analysis" and a.available for a in result.available_actions)


def test_generate_grievance_returns_not_implemented_when_prereqs_met():
    db = MagicMock()
    service = CaseWorkspaceActionService(db)
    with patch.object(
        service,
        "_inspect_workspace",
        return_value=_inspection(),
    ):
        result = service.generate_grievance(SYNTHETIC_CASE_UUID, None)

    assert result.status == "not_implemented_in_w1"
    assert result.grievance_generation is not None
    assert result.grievance_generation.draft_created is False
    assert result.grievance_generation.export_attempted is False
    assert result.grievance_generation.snapshot is None


def test_generate_grievance_prerequisites_not_met_status():
    db = MagicMock()
    service = CaseWorkspaceActionService(db)
    with patch.object(
        service,
        "_inspect_workspace",
        return_value=_inspection(
            has_analysis_report=False,
            latest_report_version_id=None,
            latest_report_version_number=None,
            has_step_progression=False,
            current_step_type=None,
            template_available=False,
            template_id=None,
            template_availability_status=None,
        ),
    ):
        result = service.generate_grievance(SYNTHETIC_CASE_UUID, None)

    assert result.status == "prerequisites_not_met"
    codes = {p.code for p in result.missing_prerequisites}
    assert "analysis_report_required" in codes
    assert "step_progression_required" in codes


def test_inspect_workspace_does_not_initialize_progression():
    db = MagicMock()
    service = CaseWorkspaceActionService(db)
    case = _case()
    create_prog = MagicMock()
    with (
        patch(
            "app.services.case_workspace_action_service.CaseService.get_case",
            return_value=case,
        ),
        patch.object(
            service._progression,
            "get_progression",
            side_effect=CaseStepProgressionNotFoundError(SYNTHETIC_CASE_UUID),
        ) as get_prog,
    ):
        # Ensure W1 never auto-initializes progression even if method exists.
        service._progression.create_case_progression = create_prog
        inspection = service._inspect_workspace(SYNTHETIC_CASE_UUID)

    assert inspection.has_step_progression is False
    get_prog.assert_called_once()
    create_prog.assert_not_called()
