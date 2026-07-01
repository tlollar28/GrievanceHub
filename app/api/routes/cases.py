from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.services.case_service import (
    CaseNotFoundError,
    CaseService,
    ReportVersionNotFoundError,
)


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
    }
    if include_report:
        payload["report_data"] = version.report_data
        payload["ranked_authorities"] = version.ranked_authorities
        payload["issue_analysis"] = version.issue_analysis
        payload["evidence_items"] = version.evidence_items
    return payload


def _serialize_case_summary(case) -> dict:
    latest_version = None
    if case.report_versions:
        latest_version = max(case.report_versions, key=lambda v: v.version_number)
    return {
        "case_uuid": case.case_uuid,
        "title": case.title,
        "user_name": case.user_name,
        "local_number": case.local_number,
        "initial_question": case.initial_question,
        "known_facts": case.known_facts,
        "status": case.status,
        "created_at": case.created_at.isoformat() if case.created_at else None,
        "updated_at": case.updated_at.isoformat() if case.updated_at else None,
        "latest_report_version": latest_version.version_number if latest_version else None,
    }


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
