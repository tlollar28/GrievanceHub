"""Saved-case HTML and PDF export routes (local/development — no auth yet)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.services.case_saved_artifact_service import (
    CaseSavedArtifactService,
    CaseSavedArtifactValidationError,
)
from app.services.case_service import CaseNotFoundError, ReportVersionNotFoundError
from app.services.report_export.normalizer import InvalidReportDataError
from app.services.report_export.pdf_generator import PdfGenerationError
from app.services.report_export_service import (
    InvalidCaseUuidError,
    NoReportVersionError,
    ReportExportService,
)

router = APIRouter(tags=["Exports"])


def _html_headers(*, inline: bool, filename: str) -> dict[str, str]:
    disposition = "inline" if inline else "attachment"
    return {
        "Content-Disposition": f'{disposition}; filename="{filename}"',
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
    }


def _pdf_headers(filename: str, *, print_mode: str) -> dict[str, str]:
    return {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
        "X-GrievanceHub-Print-Mode": print_mode,
    }


def _serve_official_or_require_save(
    db: Session,
    case_uuid: str,
    *,
    version_number: int | None,
    working_draft: bool,
):
    """Official PDF print requires prior Save and Print persistence."""
    if working_draft:
        pdf_bytes, filename = ReportExportService.export_case_pdf(
            db,
            case_uuid,
            version_number=version_number,
        )
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers=_pdf_headers(filename, print_mode="working_draft_preview"),
        )

    artifact = CaseSavedArtifactService(db).find_official_pdf_for_report_version(
        case_uuid,
        version_number,
    )
    if artifact is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "Official print requires Save and Print first. "
                f"POST /cases/{case_uuid}/reports/save-and-print, then download "
                "the persisted artifact PDF. "
                "Pass working_draft=true only for non-official preview."
            ),
        )
    try:
        pdf_bytes, filename = CaseSavedArtifactService(db).get_artifact_pdf_bytes(
            case_uuid,
            artifact.artifact_uuid,
        )
    except CaseSavedArtifactValidationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers=_pdf_headers(filename, print_mode="official_saved_artifact"),
    )


def _handle_export_errors(exc: Exception) -> HTTPException:
    if isinstance(exc, InvalidCaseUuidError):
        return HTTPException(status_code=422, detail="Invalid case UUID")
    if isinstance(exc, CaseNotFoundError):
        return HTTPException(status_code=404, detail="Case not found")
    if isinstance(exc, ReportVersionNotFoundError):
        return HTTPException(status_code=404, detail="Report version not found")
    if isinstance(exc, NoReportVersionError):
        return HTTPException(status_code=404, detail="No report version available for export")
    if isinstance(exc, InvalidReportDataError):
        return HTTPException(status_code=500, detail="Report data is invalid for export")
    if isinstance(exc, PdfGenerationError):
        return HTTPException(status_code=500, detail="PDF generation failed")
    raise exc


@router.get("/cases/{case_uuid}/export/preview", response_class=HTMLResponse)
def preview_latest_report(case_uuid: str, db: Session = Depends(get_db)):
    try:
        html, _filename = ReportExportService.export_case_html(db, case_uuid)
    except Exception as exc:
        raise _handle_export_errors(exc) from exc
    return HTMLResponse(content=html, headers=_html_headers(inline=True, filename=_filename))


@router.get("/cases/{case_uuid}/export/html", response_class=HTMLResponse)
def download_latest_report_html(case_uuid: str, db: Session = Depends(get_db)):
    try:
        html, filename = ReportExportService.export_case_html(db, case_uuid)
    except Exception as exc:
        raise _handle_export_errors(exc) from exc
    return HTMLResponse(content=html, headers=_html_headers(inline=False, filename=filename))


@router.get("/cases/{case_uuid}/export/pdf")
def download_latest_report_pdf(
    case_uuid: str,
    working_draft: bool = Query(
        False,
        description="Non-official preview only. Official print requires Save and Print.",
    ),
    db: Session = Depends(get_db),
):
    try:
        return _serve_official_or_require_save(
            db,
            case_uuid,
            version_number=None,
            working_draft=working_draft,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise _handle_export_errors(exc) from exc


@router.get("/cases/{case_uuid}/versions/{version_number}/export/preview", response_class=HTMLResponse)
def preview_report_version(
    case_uuid: str,
    version_number: int,
    db: Session = Depends(get_db),
):
    try:
        html, _filename = ReportExportService.export_case_html(
            db,
            case_uuid,
            version_number=version_number,
        )
    except Exception as exc:
        raise _handle_export_errors(exc) from exc
    return HTMLResponse(content=html, headers=_html_headers(inline=True, filename=_filename))


@router.get("/cases/{case_uuid}/versions/{version_number}/export/html", response_class=HTMLResponse)
def download_report_version_html(
    case_uuid: str,
    version_number: int,
    db: Session = Depends(get_db),
):
    try:
        html, filename = ReportExportService.export_case_html(
            db,
            case_uuid,
            version_number=version_number,
        )
    except Exception as exc:
        raise _handle_export_errors(exc) from exc
    return HTMLResponse(content=html, headers=_html_headers(inline=False, filename=filename))


@router.get("/cases/{case_uuid}/versions/{version_number}/export/pdf")
def download_report_version_pdf(
    case_uuid: str,
    version_number: int,
    working_draft: bool = Query(
        False,
        description="Non-official preview only. Official print requires Save and Print.",
    ),
    db: Session = Depends(get_db),
):
    try:
        return _serve_official_or_require_save(
            db,
            case_uuid,
            version_number=version_number,
            working_draft=working_draft,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise _handle_export_errors(exc) from exc
