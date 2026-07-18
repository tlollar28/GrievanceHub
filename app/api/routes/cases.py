from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.services.case_service import (
    CONVERSATION_HISTORY_DEFAULT_LIMIT,
    CaseNotFoundError,
    CaseReportRequiredError,
    CaseService,
    ReportVersionNotFoundError,
)
from app.services.case_asset_service import (
    CaseAssetCategoryNotExecutableError,
    CaseAssetNotFoundError,
    CaseAssetService,
    CaseAssetValidationError,
)
from app.services.case_saved_artifact_service import (
    CaseSavedArtifactNotFoundError,
    CaseSavedArtifactService,
    CaseSavedArtifactValidationError,
)
from app.services.follow_up_chat_service import FollowUpChatService
from app.services.saved_case_service import SavedCaseService
from app.schemas.saved_case_schema import (
    OpenCaseRequest,
    ReopenCaseRequest,
    SavedCaseStatusFilter,
)
from app.schemas.case_asset_schema import CaseAssetCategory
from app.schemas.case_memory_schema import (
    CaseCloseRequest,
    CaseSettleRequest,
    RecordStepOutcomeRequest,
)
from app.schemas.case_saved_artifact_schema import (
    SaveAndPrintGrievanceRequest,
    SaveAndPrintReportRequest,
)
from app.schemas.case_step_progression_schema import CaseStepOutcomeInput, StepType
from app.schemas.case_workspace_action_schema import (
    CaseInteractionRequest,
    CaseInteractionResponse,
    WorkspaceActionRequest,
    WorkspaceActionResponse,
)
from app.services.case_memory_service import CaseMemoryService
from app.services.case_domain_event_service import CaseDomainEventService
from app.services.case_history_context_service import CaseHistoryContextService
from app.services.case_workflow_service import (
    CaseWorkflowError,
    CaseWorkflowService,
)
from app.services.case_step_progression_persistence_service import (
    CaseStepProgressionPersistenceService,
)
from app.services.case_workspace_action_service import CaseWorkspaceActionService
from app.services.report_export_service import NoReportVersionError
from app.schemas.case_workflow_schema import WorkflowTransitionInput


router = APIRouter(
    prefix="/cases",
    tags=["Cases"],
)


class CreateCaseRequest(BaseModel):
    question: str = Field(..., min_length=1)
    user_name: str | None = None
    local_number: str | None = None
    known_facts: dict | None = None
    limit_per_source: int = 8


class AddMessageRequest(BaseModel):
    role: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    metadata: dict | None = None
    limit_per_source: int = 8


class UpdateFactsRequest(BaseModel):
    known_facts: dict


class UpdateStatusRequest(BaseModel):
    status: Literal["open", "closed", "settled", "archived"]
    reason: str | None = None


class CompareArtifactsRequest(BaseModel):
    left_artifact_uuid: str | None = None
    right_artifact_uuid: str | None = None
    artifact_type: Literal["analysis_report", "grievance_form"] | None = None
    left_version: int | None = None
    right_version: int | None = None


class RegenerateReportRequest(BaseModel):
    limit_per_source: int = 8


class FollowUpRequest(BaseModel):
    content: str = Field(..., min_length=1)
    report_version: int | None = None


def _serialize_message(message) -> dict:
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "metadata": message.message_metadata,
        "created_at": message.created_at.isoformat() if message.created_at else None,
    }


def _serialize_report_version(version, include_report: bool = True) -> dict:
    payload = {
        "id": version.id,
        "version_number": version.version_number,
        "trigger_message_id": version.trigger_message_id,
        "created_at": version.created_at.isoformat() if version.created_at else None,
        "retrieval_gaps": getattr(version, "retrieval_gaps", None),
        "source_coverage_audit": getattr(version, "source_coverage_audit", None),
        "report_summary": getattr(version, "report_summary", None),
    }
    if include_report:
        payload["report_data"] = version.report_data
        payload["ranked_authorities"] = version.ranked_authorities
        payload["issue_analysis"] = version.issue_analysis
        payload["evidence_items"] = version.evidence_items
    return payload


def _serialize_case_summary(case) -> dict:
    return CaseService.serialize_case_list_summary(case)


def _serialize_case_detail(case) -> dict:
    versions = sorted(case.report_versions, key=lambda v: v.version_number)
    latest = versions[-1] if versions else None
    return {
        **_serialize_case_summary(case),
        "messages": [_serialize_message(m) for m in sorted(case.messages, key=lambda m: m.created_at)],
        "latest_report": _serialize_report_version(latest) if latest else None,
        "report_versions": [
            _serialize_report_version(v, include_report=False) for v in versions
        ],
    }


@router.post("/")
def create_case(payload: CreateCaseRequest, db: Session = Depends(get_db)):
    case = CaseService.create_case(
        db=db,
        question=payload.question,
        user_name=payload.user_name,
        local_number=payload.local_number,
        known_facts=payload.known_facts,
    )
    # New cases open into continuous conversation. Analysis reports are created
    # only when the steward explicitly Generate Analysis Report.
    case = CaseService.get_case(db, case.case_uuid)
    return {
        "case": _serialize_case_detail(case),
        "report_version": None,
    }


@router.get("/")
def list_cases(status: str | None = None, db: Session = Depends(get_db)):
    cases = CaseService.list_cases(db, status=status)
    return {
        "count": len(cases),
        "cases": [_serialize_case_summary(case) for case in cases],
    }


@router.get("/saved")
def list_saved_cases(
    status: SavedCaseStatusFilter = "all",
    step: StepType | None = None,
    search: str | None = None,
    order: Literal["newest_first", "oldest_first"] = "newest_first",
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    return SavedCaseService.list_saved_cases(
        db,
        status_filter=status,
        step_filter=step,
        search=search,
        newest_first=order == "newest_first",
        limit=limit,
        offset=offset,
    ).model_dump(mode="json")


@router.get("/saved/{case_uuid}")
def get_saved_case(case_uuid: str, db: Session = Depends(get_db)):
    try:
        summary = SavedCaseService.get_saved_case(db, case_uuid)
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail="Case not found")
    return summary.model_dump(mode="json")


@router.post("/saved/{case_uuid}/open")
def open_saved_case(
    case_uuid: str,
    payload: OpenCaseRequest | None = None,
    db: Session = Depends(get_db),
):
    try:
        result = SavedCaseService.open_case(
            db,
            case_uuid,
            source=(payload.source if payload else "manual_ui"),
        )
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail="Case not found")
    return result.model_dump(mode="json")


@router.post("/saved/{case_uuid}/reopen")
def reopen_saved_case(
    case_uuid: str,
    payload: ReopenCaseRequest | None = None,
    db: Session = Depends(get_db),
):
    try:
        result = SavedCaseService.reopen_case(
            db,
            case_uuid,
            reason=payload.reason if payload else None,
            reopened_by=payload.reopened_by if payload else None,
            source=(payload.source if payload else "manual_ui"),
        )
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail="Case not found")
    return result.model_dump(mode="json")


@router.post("/saved/{case_uuid}/close")
def close_saved_case(
    case_uuid: str,
    payload: CaseCloseRequest,
    db: Session = Depends(get_db),
):
    try:
        return SavedCaseService.close_case_structured(
            db,
            case_uuid,
            outcome=payload.outcome,
            outcome_notes=payload.outcome_notes,
            resolution_type=payload.resolution_type,
            close_date=payload.close_date,
            closed_by=payload.closed_by,
            final_grievance_step=payload.final_grievance_step,
            supporting_document_refs=payload.supporting_document_refs,
        )
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail="Case not found")


@router.post("/saved/{case_uuid}/settle")
def settle_saved_case(
    case_uuid: str,
    payload: CaseSettleRequest | None = None,
    db: Session = Depends(get_db),
):
    try:
        return SavedCaseService.settle_case(
            db,
            case_uuid,
            settlement_notes=payload.settlement_notes if payload else None,
            settlement_date=payload.settlement_date if payload else None,
            settlement_document_refs=(
                payload.settlement_document_refs if payload else None
            ),
            settlement_amount=payload.settlement_amount if payload else None,
            settled_by=payload.settled_by if payload else None,
        )
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail="Case not found")


@router.post("/saved/{case_uuid}/archive")
def archive_saved_case(
    case_uuid: str,
    payload: UpdateStatusRequest | None = None,
    db: Session = Depends(get_db),
):
    try:
        result = SavedCaseService.archive_case(
            db,
            case_uuid,
            reason=payload.reason if payload else None,
        )
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail="Case not found")
    return result


@router.get("/saved/{case_uuid}/timeline")
def get_saved_case_timeline(
    case_uuid: str,
    order: Literal["oldest_first", "newest_first"] = "oldest_first",
    db: Session = Depends(get_db),
):
    try:
        timeline = SavedCaseService.get_case_timeline(
            db,
            case_uuid,
            newest_first=order == "newest_first",
        )
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail="Case not found")
    return timeline.model_dump(mode="json")


@router.get("/saved/{case_uuid}/history")
def get_saved_case_history(
    case_uuid: str,
    order: Literal["oldest_first", "newest_first"] = "oldest_first",
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Steward-facing Official Case Record (meaningful events + artifact links)."""
    try:
        history = CaseSavedArtifactService(db).list_steward_case_history(
            case_uuid,
            order=order,
            limit=limit,
        )
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail="Case not found")
    return history.model_dump(mode="json")


@router.get("/{case_uuid}/workspace")
def get_case_workspace(case_uuid: str, db: Session = Depends(get_db)):
    try:
        workspace = CaseService.get_case_workspace(db, case_uuid)
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail="Case not found")
    return workspace


@router.get("/{case_uuid}/memory")
def get_case_memory(case_uuid: str, db: Session = Depends(get_db)):
    """Durable Case Memory (system of record for AI understanding)."""
    try:
        service = CaseMemoryService(db)
        row = service.get_row(case_uuid)
        memory = service.load(case_uuid)
        overview = service.get_overview(case_uuid)
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail="Case not found")
    return {
        "case_uuid": case_uuid,
        "schema_version": row.schema_version,
        "reopen_count": row.reopen_count,
        "memory": memory,
        "overview": overview.model_dump(mode="json"),
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.get("/{case_uuid}/overview")
def get_case_overview(case_uuid: str, db: Session = Depends(get_db)):
    """Auto-maintained Case Overview derived from Case Memory."""
    try:
        overview = CaseMemoryService(db).get_overview(case_uuid)
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail="Case not found")
    return overview.model_dump(mode="json")


@router.get("/{case_uuid}/workflow")
def get_case_workflow(case_uuid: str, db: Session = Depends(get_db)):
    """Explicit grievance workflow state (not inferred solely from artifacts)."""
    try:
        return CaseWorkflowService(db).get_state(case_uuid).model_dump(mode="json")
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail="Case not found")


@router.post("/{case_uuid}/workflow/transitions")
def transition_case_workflow(
    case_uuid: str,
    payload: WorkflowTransitionInput,
    db: Session = Depends(get_db),
):
    try:
        view = CaseWorkflowService(db).transition(
            case_uuid,
            str(payload.to_state),
            reason=payload.reason,
            actor_id=payload.actor_id,
            grievance_step=payload.grievance_step,
            allow_authorized_override=payload.allow_authorized_override,
            source_type=payload.source_type,
            source_uuid=payload.source_uuid,
            metadata=payload.metadata,
            commit=True,
        )
        return view.model_dump(mode="json")
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail="Case not found")
    except CaseWorkflowError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{case_uuid}/domain-events")
def list_case_domain_events(
    case_uuid: str,
    limit: int = Query(default=100, ge=1, le=200),
    event_type: str | None = None,
    db: Session = Depends(get_db),
):
    """Internal domain events (not a substitute for Official Case Record)."""
    try:
        events = CaseDomainEventService(db).list_events(
            case_uuid, limit=limit, event_type=event_type
        )
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail="Case not found")
    return {
        "case_uuid": case_uuid,
        "count": len(events),
        "events": [e.model_dump(mode="json") for e in events],
    }


@router.get("/{case_uuid}/history/{event_id}/context")
def jump_to_history_context(
    case_uuid: str,
    event_id: str,
    conversation_window: int = Query(default=8, ge=2, le=20),
    db: Session = Depends(get_db),
):
    """Jump-to-context for an Official Case Record event (read-only)."""
    try:
        context = CaseHistoryContextService(db).jump_to_context(
            case_uuid,
            event_id,
            conversation_window=conversation_window,
        )
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail="Case or event not found")
    return context.model_dump(mode="json")


@router.post("/{case_uuid}/outcomes")
def record_case_outcome(
    case_uuid: str,
    payload: RecordStepOutcomeRequest,
    db: Session = Depends(get_db),
):
    """Record step decision; may close without Step 2 or appeal to next step."""
    try:
        progression = CaseStepProgressionPersistenceService(db)
        progression.ensure_case_progression(case_uuid)
        state = progression.get_progression(case_uuid)
        step_type = payload.step_type or state.current_step_type
        outcome, step = progression.add_step_outcome(
            case_uuid,
            step_type,  # type: ignore[arg-type]
            CaseStepOutcomeInput(
                outcome_type=payload.outcome_type,  # type: ignore[arg-type]
                decision_summary=payload.decision_summary,
                decision_date=payload.decision_date,
                steward_notes=payload.steward_notes,
                close_case=payload.close_case,
                close_step=payload.close_step or payload.close_case,
                appeal_to_next_step=payload.appeal_to_next_step,
                decision_document_refs=payload.decision_document_refs,
            ),
        )
        CaseMemoryService(db).record_outcome(
            case_uuid,
            step_type=step_type,
            outcome_type=payload.outcome_type,
            decision_summary=payload.decision_summary,
            appeal_to_next_step=payload.appeal_to_next_step,
            close_case=payload.close_case,
        )
        workflow = CaseWorkflowService(db)
        if payload.appeal_to_next_step:
            prefix = (
                "step_1"
                if step_type and "step_1" in step_type
                else "step_2"
                if step_type and "step_2" in step_type
                else "step_3"
            )
            try:
                workflow.transition(
                    case_uuid,
                    f"{prefix}_appealed",
                    reason="outcome_appeal",
                    grievance_step=step_type,
                    allow_authorized_override=True,
                    commit=True,
                )
                next_state = (
                    "step_2_analysis"
                    if prefix == "step_1"
                    else "step_3_analysis"
                    if prefix == "step_2"
                    else "step_3_decision_required"
                )
                if prefix in {"step_1", "step_2"}:
                    workflow.transition(
                        case_uuid,
                        next_state,
                        reason="appeal_advances_same_case",
                        allow_authorized_override=True,
                        commit=True,
                    )
            except CaseWorkflowError:
                pass
        elif payload.close_case:
            CaseService.close_case(db, case_uuid)
            CaseMemoryService(db).record_close(
                case_uuid,
                outcome=payload.decision_summary or payload.outcome_type,
                outcome_notes=payload.steward_notes,
                resolution_type=payload.resolution_type or payload.outcome_type,
                close_date=None,
                closed_by=payload.closed_by,
                final_grievance_step=step_type,
            )
            try:
                workflow.transition(
                    case_uuid,
                    "closed",
                    reason="outcome_close",
                    grievance_step=step_type,
                    allow_authorized_override=True,
                    commit=True,
                )
            except CaseWorkflowError:
                pass
        else:
            prefix = (
                "step_1"
                if step_type and "step_1" in step_type
                else "step_2"
                if step_type and "step_2" in step_type
                else "step_3"
            )
            try:
                workflow.transition(
                    case_uuid,
                    f"{prefix}_resolved",
                    reason="outcome_resolved",
                    grievance_step=step_type,
                    allow_authorized_override=True,
                    commit=True,
                )
            except CaseWorkflowError:
                pass
        return {
            "case_uuid": case_uuid,
            "outcome": outcome.model_dump(mode="json"),
            "step": step.model_dump(mode="json"),
            "workflow": CaseWorkflowService(db).get_state(case_uuid).model_dump(
                mode="json"
            ),
            "case_overview": CaseMemoryService(db).get_overview(case_uuid).model_dump(
                mode="json"
            ),
            "workspace": CaseService.get_case_workspace(db, case_uuid),
        }
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail="Case not found")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{case_uuid}/reports/generate")
def generate_analysis_report(
    case_uuid: str,
    payload: RegenerateReportRequest | None = None,
    db: Session = Depends(get_db),
):
    """Explicit Generate Analysis Report — temporary read-only preview only.

    Does not create a report version, CaseSavedArtifact, or Official Case
    Record event. Versioning and artifacts begin only on Save / Save and Print.
    """
    service = CaseWorkspaceActionService(db)
    result = service.generate_analysis_report(
        case_uuid,
        limit_per_source=(payload.limit_per_source if payload else 8),
    )
    if result.status == "case_not_found":
        raise HTTPException(status_code=404, detail="Case not found")
    if result.status == "prerequisites_not_met":
        raise HTTPException(status_code=400, detail=result.message)
    body = result.model_dump(mode="json")
    body["review_mode"] = "read_only"
    body["editable"] = False
    body["persisted"] = False
    body["report_version"] = None
    body["preview"] = result.analysis_preview
    return body


@router.post("/{case_uuid}/reports/save-and-print")
def save_and_print_report(
    case_uuid: str,
    payload: SaveAndPrintReportRequest | None = None,
    db: Session = Depends(get_db),
):
    try:
        result = CaseSavedArtifactService(db).save_and_print_report(
            case_uuid,
            payload or SaveAndPrintReportRequest(),
        )
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail="Case not found")
    except ReportVersionNotFoundError:
        raise HTTPException(status_code=404, detail="Report version not found")
    except NoReportVersionError:
        raise HTTPException(status_code=404, detail="No analysis report available")
    except CaseSavedArtifactValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result.model_dump(mode="json")


@router.post("/{case_uuid}/grievances/save-and-print")
def save_and_print_grievance(
    case_uuid: str,
    payload: SaveAndPrintGrievanceRequest,
    db: Session = Depends(get_db),
):
    try:
        result = CaseSavedArtifactService(db).save_and_print_grievance(case_uuid, payload)
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail="Case not found")
    except CaseSavedArtifactValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result.model_dump(mode="json")


@router.get("/{case_uuid}/artifacts")
def list_case_artifacts(
    case_uuid: str,
    artifact_type: Literal["analysis_report", "grievance_form"] | None = None,
    db: Session = Depends(get_db),
):
    try:
        result = CaseSavedArtifactService(db).list_artifacts(
            case_uuid, artifact_type=artifact_type
        )
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail="Case not found")
    return result.model_dump(mode="json")


@router.get("/{case_uuid}/artifacts/{artifact_uuid}")
def get_case_artifact(
    case_uuid: str,
    artifact_uuid: str,
    db: Session = Depends(get_db),
):
    try:
        result = CaseSavedArtifactService(db).get_artifact(case_uuid, artifact_uuid)
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail="Case not found")
    except CaseSavedArtifactNotFoundError:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return result.model_dump(mode="json")


@router.get("/{case_uuid}/artifacts/{artifact_uuid}/pdf")
def get_case_artifact_pdf(
    case_uuid: str,
    artifact_uuid: str,
    db: Session = Depends(get_db),
):
    try:
        pdf_bytes, filename = CaseSavedArtifactService(db).get_artifact_pdf_bytes(
            case_uuid, artifact_uuid
        )
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail="Case not found")
    except CaseSavedArtifactNotFoundError:
        raise HTTPException(status_code=404, detail="Artifact not found")
    except CaseSavedArtifactValidationError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.post("/{case_uuid}/artifacts/compare")
def compare_case_artifacts(
    case_uuid: str,
    payload: CompareArtifactsRequest,
    db: Session = Depends(get_db),
):
    """Automatically retrieve two official artifact versions for comparison."""
    service = CaseSavedArtifactService(db)
    try:
        if payload.left_artifact_uuid and payload.right_artifact_uuid:
            result = service.compare_artifacts(
                case_uuid,
                payload.left_artifact_uuid,
                payload.right_artifact_uuid,
            )
        elif (
            payload.artifact_type
            and payload.left_version is not None
            and payload.right_version is not None
        ):
            result = service.compare_artifact_versions(
                case_uuid,
                payload.artifact_type,
                payload.left_version,
                payload.right_version,
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Provide left_artifact_uuid + right_artifact_uuid, or "
                    "artifact_type + left_version + right_version."
                ),
            )
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail="Case not found")
    except CaseSavedArtifactNotFoundError:
        raise HTTPException(status_code=404, detail="Artifact not found")
    except CaseSavedArtifactValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result.model_dump(mode="json")


@router.get("/{case_uuid}/assets")
def list_case_assets(
    case_uuid: str,
    category: CaseAssetCategory | None = None,
    db: Session = Depends(get_db),
):
    """List first-class case assets (uploads and future generated artifacts)."""
    service = CaseAssetService(db)
    try:
        result = service.list_assets(case_uuid, category=category)
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail="Case not found")
    return result.model_dump(mode="json")


@router.post("/{case_uuid}/assets")
async def upload_case_asset(
    case_uuid: str,
    file: UploadFile = File(...),
    category: CaseAssetCategory = Form("uploaded_document"),
    uploaded_by: str | None = Form(None),
    source: str = Form("api"),
    db: Session = Depends(get_db),
):
    """Upload a case asset. Only ``uploaded_document`` is executable in W3."""
    service = CaseAssetService(db)
    content = await file.read()
    try:
        result = service.create_asset(
            case_uuid,
            category=category,
            filename=file.filename,
            content=content,
            mime_type=file.content_type,
            uploaded_by=uploaded_by,
            source=source,
        )
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail="Case not found")
    except CaseAssetCategoryNotExecutableError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except CaseAssetValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result.model_dump(mode="json")


@router.get("/{case_uuid}/assets/{asset_uuid}")
def get_case_asset(
    case_uuid: str,
    asset_uuid: str,
    db: Session = Depends(get_db),
):
    """Return metadata for one case asset (no file body)."""
    service = CaseAssetService(db)
    try:
        asset = service.get_asset(case_uuid, asset_uuid)
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail="Case not found")
    except CaseAssetNotFoundError:
        raise HTTPException(status_code=404, detail="Case asset not found")
    return asset.model_dump(mode="json")


@router.post(
    "/{case_uuid}/interactions",
    response_model=CaseInteractionResponse,
)
def submit_case_interaction(
    case_uuid: str,
    payload: CaseInteractionRequest,
    db: Session = Depends(get_db),
):
    """Submit a case-scoped conversational request.

    The interaction uses bounded case context and indexed-source retrieval,
    persists the conversation, reports retrieval and Case Memory status, and
    does not create a report or grievance artifact.
    """
    service = CaseWorkspaceActionService(db)
    result = service.submit_interaction(case_uuid, payload)
    if result.status == "case_not_found":
        raise HTTPException(status_code=404, detail="Case not found")
    return result.model_dump(mode="json")


@router.post(
    "/{case_uuid}/actions",
    response_model=WorkspaceActionResponse,
)
def execute_case_workspace_action(
    case_uuid: str,
    payload: WorkspaceActionRequest,
    db: Session = Depends(get_db),
):
    """Execute an explicit case-workspace action.

    Supported actions generate an analysis preview, generate an editable
    grievance draft, or execute the existing analysis-refresh compatibility
    operation. Artifact persistence remains separate from preview generation.
    """
    service = CaseWorkspaceActionService(db)
    result = service.execute_action(case_uuid, payload)
    if result.status == "case_not_found":
        raise HTTPException(status_code=404, detail="Case not found")
    return result.model_dump(mode="json")


@router.post("/{case_uuid}/reports/regenerate")
def regenerate_case_report(
    case_uuid: str,
    payload: RegenerateReportRequest | None = None,
    db: Session = Depends(get_db),
):
    try:
        report_version = CaseService.generate_report_version(
            db=db,
            case_uuid=case_uuid,
            limit_per_source=(payload.limit_per_source if payload else 8),
        )
        case = CaseService.get_case(db, case_uuid)
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail="Case not found")

    return {
        "report_version": _serialize_report_version(report_version),
        "case": _serialize_case_detail(case),
    }


@router.get("/{case_uuid}")
def get_case(case_uuid: str, db: Session = Depends(get_db)):
    try:
        case = CaseService.get_case(db, case_uuid)
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail="Case not found")
    return _serialize_case_detail(case)


@router.get("/{case_uuid}/messages")
def list_case_messages(
    case_uuid: str,
    limit: int = CONVERSATION_HISTORY_DEFAULT_LIMIT,
    offset: int = 0,
    order: Literal["oldest_first", "newest_first"] = "oldest_first",
    db: Session = Depends(get_db),
):
    """Paginated conversation history for a single case (case-scoped)."""
    try:
        return CaseService.list_case_messages(
            db,
            case_uuid,
            limit=limit,
            offset=offset,
            newest_first=order == "newest_first",
        )
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail="Case not found")


@router.post("/{case_uuid}/messages")
def add_case_message(
    case_uuid: str,
    payload: AddMessageRequest,
    db: Session = Depends(get_db),
):
    try:
        message = CaseService.add_message(
            db=db,
            case_uuid=case_uuid,
            role=payload.role,
            content=payload.content,
            metadata=payload.metadata,
        )
        case = CaseService.get_case(db, case_uuid)
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail="Case not found")

    return {
        "message": _serialize_message(message),
        "report_version": None,
        "case": _serialize_case_detail(case),
        "note": (
            "Message saved. Analysis reports are created only via "
            "POST /cases/{case_uuid}/reports/generate."
        ),
    }


@router.post("/{case_uuid}/followups")
def post_case_followup(
    case_uuid: str,
    payload: FollowUpRequest,
    db: Session = Depends(get_db),
):
    try:
        result = FollowUpChatService.answer_follow_up(
            db=db,
            case_uuid=case_uuid,
            content=payload.content,
            report_version_number=payload.report_version,
        )
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail="Case not found")
    except ReportVersionNotFoundError:
        raise HTTPException(status_code=404, detail="Report version not found")
    except CaseReportRequiredError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {
        "user_message": CaseService.serialize_message(result["user_message"]),
        "assistant_message": CaseService.serialize_message(result["assistant_message"]),
        "answer": result["answer"],
        "answer_type": result["answer_type"],
        "citations": result["citations"],
        "disclosures": result["disclosures"],
        "facts_needed": result["facts_needed"],
        "linked_report_version": result["linked_report_version"],
        "requires_report_regen": result["requires_report_regen"],
        "suggested_actions": result["suggested_actions"],
    }


@router.get("/{case_uuid}/followups")
def list_case_followups(case_uuid: str, db: Session = Depends(get_db)):
    try:
        thread = FollowUpChatService.list_follow_up_thread(db, case_uuid)
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail="Case not found")
    return thread


@router.patch("/{case_uuid}/facts")
def update_case_facts(
    case_uuid: str,
    payload: UpdateFactsRequest,
    db: Session = Depends(get_db),
):
    try:
        case = CaseService.update_known_facts(db, case_uuid, payload.known_facts)
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail="Case not found")
    return _serialize_case_summary(case)


@router.patch("/{case_uuid}/status")
def update_case_status(
    case_uuid: str,
    payload: UpdateStatusRequest,
    db: Session = Depends(get_db),
):
    try:
        if payload.status == "closed":
            case = CaseService.close_case(db, case_uuid)
            from app.services.case_step_progression_persistence_service import (
                CaseStepProgressionPersistenceService,
            )

            CaseStepProgressionPersistenceService(db).ensure_case_progression(case_uuid)
            CaseStepProgressionPersistenceService(db).close_case(
                case_uuid, reason=payload.reason
            )
        elif payload.status == "settled":
            case = CaseService.settle_case(db, case_uuid)
            from app.services.case_step_progression_persistence_service import (
                CaseStepProgressionPersistenceService,
            )

            CaseStepProgressionPersistenceService(db).ensure_case_progression(case_uuid)
            CaseStepProgressionPersistenceService(db).settle_case(
                case_uuid, reason=payload.reason
            )
        elif payload.status == "archived":
            case = CaseService.archive_case(db, case_uuid)
            from app.services.case_step_progression_persistence_service import (
                CaseStepProgressionPersistenceService,
            )

            CaseStepProgressionPersistenceService(db).ensure_case_progression(case_uuid)
            CaseStepProgressionPersistenceService(db).archive_case(
                case_uuid, reason=payload.reason
            )
        else:
            case = CaseService.reopen_case(db, case_uuid)
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail="Case not found")
    return _serialize_case_summary(case)


@router.get("/{case_uuid}/versions")
def list_report_versions(case_uuid: str, db: Session = Depends(get_db)):
    try:
        versions = CaseService.list_report_versions(db, case_uuid)
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail="Case not found")
    return {
        "case_uuid": case_uuid,
        "count": len(versions),
        "versions": [_serialize_report_version(v, include_report=False) for v in versions],
    }


@router.get("/{case_uuid}/versions/{version_number}")
def get_report_version(
    case_uuid: str,
    version_number: int,
    db: Session = Depends(get_db),
):
    try:
        version = CaseService.get_report_version(db, case_uuid, version_number)
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail="Case not found")
    except ReportVersionNotFoundError:
        raise HTTPException(status_code=404, detail="Report version not found")
    return _serialize_report_version(version)
