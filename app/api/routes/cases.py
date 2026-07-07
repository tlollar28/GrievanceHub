from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.services.case_service import (
    CaseNotFoundError,
    CaseReportRequiredError,
    CaseService,
    ReportVersionNotFoundError,
)
from app.services.follow_up_chat_service import FollowUpChatService
from app.services.saved_case_service import SavedCaseService
from app.schemas.saved_case_schema import (
    OpenCaseRequest,
    ReopenCaseRequest,
    SavedCaseStatusFilter,
)
from app.schemas.case_step_progression_schema import StepType


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
    status: Literal["open", "closed"]


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
    report_version = CaseService.generate_report_version(
        db=db,
        case_uuid=case.case_uuid,
        limit_per_source=payload.limit_per_source,
    )
    case = CaseService.get_case(db, case.case_uuid)
    return {
        "case": _serialize_case_detail(case),
        "report_version": _serialize_report_version(report_version),
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
    db: Session = Depends(get_db),
):
    return SavedCaseService.list_saved_cases(
        db,
        status_filter=status,
        step_filter=step,
        search=search,
        newest_first=order == "newest_first",
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
            source=(payload.source if payload else "manual_ui"),
        )
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail="Case not found")
    return result.model_dump(mode="json")


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


@router.get("/{case_uuid}/workspace")
def get_case_workspace(case_uuid: str, db: Session = Depends(get_db)):
    try:
        workspace = CaseService.get_case_workspace(db, case_uuid)
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail="Case not found")
    return workspace


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
        report_version = CaseService.generate_report_version(
            db=db,
            case_uuid=case_uuid,
            limit_per_source=payload.limit_per_source,
            trigger_message_id=message.id,
        )
        case = CaseService.get_case(db, case_uuid)
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail="Case not found")

    return {
        "message": _serialize_message(message),
        "report_version": _serialize_report_version(report_version),
        "case": _serialize_case_detail(case),
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
