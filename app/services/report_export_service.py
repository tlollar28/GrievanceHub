"""Orchestrates read-only case report export to HTML and PDF."""

from __future__ import annotations

import logging
import time
from uuid import UUID

from sqlalchemy.orm import Session

from app.services.case_service import CaseNotFoundError, CaseService, ReportVersionNotFoundError
from app.services.report_export.filename_utils import build_export_filename
from app.services.report_export.html_renderer import ReportHtmlRenderer
from app.services.report_export.normalizer import InvalidReportDataError, normalize_export_payload
from app.services.report_export.pdf_generator import PdfGenerationError, ReportPdfGenerator

logger = logging.getLogger(__name__)


class NoReportVersionError(Exception):
    pass


class ExportServiceError(Exception):
    pass


class InvalidCaseUuidError(ExportServiceError):
    pass


def _authorize_export(case_uuid: str) -> None:
    """Future integration point for steward authentication and case access checks."""
    return None


def _load_version(db: Session, case_uuid: str, version_number: int | None):
    case = CaseService.get_case(db, case_uuid)
    if not case.report_versions:
        raise NoReportVersionError(case_uuid)

    if version_number is None:
        return max(case.report_versions, key=lambda item: item.version_number)

    for version in case.report_versions:
        if version.version_number == version_number:
            return version
    raise ReportVersionNotFoundError(version_number)


class ReportExportService:
    @staticmethod
    def validate_case_uuid(case_uuid: str) -> None:
        try:
            UUID(case_uuid)
        except ValueError as exc:
            raise InvalidCaseUuidError("Invalid case UUID") from exc

    @staticmethod
    def load_export_context(
        db: Session,
        case_uuid: str,
        version_number: int | None = None,
    ) -> dict:
        ReportExportService.validate_case_uuid(case_uuid)
        _authorize_export(case_uuid)

        try:
            version = _load_version(db, case_uuid, version_number)
        except CaseNotFoundError as exc:
            raise CaseNotFoundError(case_uuid) from exc

        if not isinstance(version.report_data, dict):
            raise InvalidReportDataError("Stored report_data is not a dictionary")

        return normalize_export_payload(
            version.report_data,
            case_uuid=case_uuid,
            version_number=version.version_number,
        )

    @staticmethod
    def render_html_from_context(export_context: dict) -> str:
        return ReportHtmlRenderer.render(export_context)

    @staticmethod
    def render_pdf_from_html(html: str) -> bytes:
        return ReportPdfGenerator.html_to_pdf_bytes(html)

    @staticmethod
    def export_case_html(
        db: Session,
        case_uuid: str,
        version_number: int | None = None,
    ) -> tuple[str, str]:
        started = time.perf_counter()
        export_context = ReportExportService.load_export_context(
            db,
            case_uuid,
            version_number=version_number,
        )
        html = ReportExportService.render_html_from_context(export_context)
        filename = build_export_filename(
            case_uuid,
            export_context["version_number"],
            "html",
        )
        logger.info(
            "export_success format=html case_uuid=%s version=%s elapsed_ms=%.1f",
            case_uuid,
            export_context["version_number"],
            (time.perf_counter() - started) * 1000,
        )
        return html, filename

    @staticmethod
    def export_case_pdf(
        db: Session,
        case_uuid: str,
        version_number: int | None = None,
    ) -> tuple[bytes, str]:
        started = time.perf_counter()
        export_context = ReportExportService.load_export_context(
            db,
            case_uuid,
            version_number=version_number,
        )
        html = ReportExportService.render_html_from_context(export_context)
        try:
            pdf_bytes = ReportExportService.render_pdf_from_html(html)
        except PdfGenerationError as exc:
            logger.warning(
                "export_failure format=pdf case_uuid=%s version=%s error_class=%s",
                case_uuid,
                export_context["version_number"],
                type(exc).__name__,
            )
            raise
        filename = build_export_filename(
            case_uuid,
            export_context["version_number"],
            "pdf",
        )
        logger.info(
            "export_success format=pdf case_uuid=%s version=%s elapsed_ms=%.1f",
            case_uuid,
            export_context["version_number"],
            (time.perf_counter() - started) * 1000,
        )
        return pdf_bytes, filename
