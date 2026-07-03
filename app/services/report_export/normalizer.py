"""Normalize stored report payloads into plain dictionaries for Jinja rendering."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from app.schemas.report_schema import GrievanceHubReport
from app.services.report_export.presentation import prepare_presentation


class InvalidReportDataError(Exception):
    """Stored report JSON cannot be validated for export."""


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _extract_inner_report(raw: dict) -> dict:
    inner = raw.get("report")
    if isinstance(inner, dict) and inner.get("report_title"):
        return inner
    if raw.get("report_title"):
        return raw
    raise InvalidReportDataError("Missing GrievanceHub report payload")


def normalize_export_payload(
    raw: dict,
    *,
    case_uuid: str | None = None,
    version_number: int | None = None,
) -> dict[str, Any]:
    """Validate and flatten report data for template rendering."""
    if not isinstance(raw, dict):
        raise InvalidReportDataError("Report payload must be a dictionary")

    wrapper = raw if isinstance(raw.get("report"), dict) else {"report": raw}

    try:
        report_model = GrievanceHubReport.model_validate(_extract_inner_report(raw))
    except (ValidationError, InvalidReportDataError) as exc:
        raise InvalidReportDataError(str(exc)) from exc

    report = _json_safe(report_model.model_dump(mode="json"))
    case_info = report.setdefault("case_information", {})

    resolved_case_id = case_uuid or case_info.get("case_id")
    if resolved_case_id:
        case_info["case_id"] = resolved_case_id

    presentation = prepare_presentation(
        wrapper,
        report,
        case_uuid=resolved_case_id,
        version_number=version_number,
    )
    report["management_limiting_authority"] = presentation["management_limiting_authority"]

    return {
        "report": report,
        "presentation": presentation,
        "case_uuid": resolved_case_id,
        "version_number": version_number,
        "generated_at": report.get("generated_at"),
        "generated_at_display": presentation["generated_at_display"],
        "case_reference": presentation["case_reference"],
    }
