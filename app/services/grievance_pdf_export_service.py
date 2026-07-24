"""Fill the authoritative Step 1 and Step 2 grievance AcroForm PDFs."""

from __future__ import annotations

from io import BytesIO
import re
from typing import Any

from pypdf import PdfReader, PdfWriter
from pypdf.generic import BooleanObject, NameObject

from app.services.grievance_template_registry import (
    OFFICIAL_GRIEVANCE_WORKSHEET_STEP_1,
    OFFICIAL_STANDARD_GRIEVANCE_FORM_STEP_2,
    get_grievance_template_by_id,
    resolve_repo_relative_path,
)


class GrievancePdfExportError(ValueError):
    """Raised when an official grievance PDF cannot be filled safely."""


_STEP_1_TEMPLATE_ID = OFFICIAL_GRIEVANCE_WORKSHEET_STEP_1.template_id
_STEP_2_TEMPLATE_ID = OFFICIAL_STANDARD_GRIEVANCE_FORM_STEP_2.template_id

# Preserve older callers while making the official Step 2 AcroForm authoritative.
_TEMPLATE_ALIASES = {
    "local_300_form_79_1": _STEP_2_TEMPLATE_ID,
    "local_300_standard_grievance_form_79_1": _STEP_2_TEMPLATE_ID,
}

_YES = NameObject("/Yes")
_OFF = NameObject("/Off")


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(item) for item in value if item not in (None, ""))
    return str(value).strip()


def _first_value(field_values: dict[str, Any], *field_ids: str) -> str:
    for field_id in field_ids:
        value = _text(field_values.get(field_id))
        if value:
            return value
    return ""


def _combine_values(field_values: dict[str, Any], *field_ids: str) -> str:
    values: list[str] = []
    for field_id in field_ids:
        value = _text(field_values.get(field_id))
        if value and value not in values:
            values.append(value)
    return "; ".join(values)


def _is_truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    normalized = _text(value).lower()
    return normalized in {"1", "true", "yes", "y", "on", "attached"}


def _tokens(value: Any) -> set[str]:
    if isinstance(value, dict):
        raw_values = [key for key, selected in value.items() if _is_truthy(selected)]
    elif isinstance(value, (list, tuple, set)):
        raw_values = list(value)
    else:
        raw_values = re.split(r"[,;/|]+", _text(value))

    return {
        re.sub(r"[^A-Z0-9]+", " ", str(item).upper()).strip()
        for item in raw_values
        if str(item).strip()
    }


def _set_checkbox_group(
    values: dict[str, Any],
    *,
    field_names: dict[str, str],
    selected_tokens: set[str],
) -> None:
    selected_fields = {
        field_name
        for token, field_name in field_names.items()
        if token in selected_tokens
    }
    for field_name in set(field_names.values()):
        values[field_name] = _YES if field_name in selected_fields else _OFF


def _veteran_checkboxes(
    values: dict[str, Any],
    *,
    source_value: Any,
    yes_field: str,
    no_field: str,
) -> None:
    normalized = _text(source_value).lower()
    if normalized in {"yes", "y", "true", "1", "veteran"}:
        values[yes_field] = _YES
        values[no_field] = _OFF
    elif normalized in {"no", "n", "false", "0", "non-veteran", "nonveteran"}:
        values[yes_field] = _OFF
        values[no_field] = _YES
    else:
        values[yes_field] = _OFF
        values[no_field] = _OFF


def _build_step_1_values(field_values: dict[str, Any]) -> dict[str, Any]:
    grievant = _first_value(
        field_values,
        "grievant_name_or_class",
        "grievant_name",
    )
    form_date = _text(field_values.get("form_date"))
    grievance_number = _text(field_values.get("branch_grievance_number"))
    installation = _first_value(
        field_values,
        "installation_station_branch",
        "installation_name",
    )

    values: dict[str, Any] = {
        "gff1.0a": form_date,
        "p2.date": form_date,
        "gff1.1": grievance_number,
        "gn.20": grievance_number,
        "gff1.2": _text(field_values.get("steward_name")),
        "gff2.0": grievant,
        "p2.grievant": grievant,
        "gff2.1": _first_value(field_values, "ein", "ssn_or_employee_id"),
        "gff2.2": _text(field_values.get("grievant_phone")),
        "gff2.3": _text(field_values.get("home_address")),
        "gff2.4": _text(field_values.get("city")),
        "gff2.5": _text(field_values.get("state")),
        "gff2.6": _text(field_values.get("zip")),
        "gff2.7": _text(field_values.get("job_classification")),
        "gff2.8": _text(field_values.get("craft_seniority_date")),
        "gff2.9": _text(field_values.get("service_seniority_date")),
        "gff2.10": _text(field_values.get("duty_hours")),
        "gff2.11": installation,
        "gff2.12": _text(field_values.get("installation_city")),
        "gff2.13": _text(field_values.get("installation_state")),
        "gff2.14": _text(field_values.get("installation_zip")),
        "gff2.15": _text(field_values.get("employee_level")),
        "gff2.16": _text(field_values.get("employee_step")),
        "gff3.0": _combine_values(
            field_values,
            "violation_articles_citations",
            "violation_national",
        ),
        "gff3.1": _text(field_values.get("violation_local_mou")),
        "gff3.2": _text(field_values.get("violation_other_grounds")),
        "gff3.3": _text(field_values.get("facts_dates")),
        "gff3.4": _text(field_values.get("facts_time")),
        "gff3.5": _text(field_values.get("facts_location")),
        "gff3.6": _text(field_values.get("facts_what_happened")),
        "gff3.7": _text(field_values.get("corrective_action_requested")),
        "gff3.9": _text(field_values.get("facts_continued")),
    }

    _veteran_checkboxes(
        values,
        source_value=field_values.get("veteran_status"),
        yes_field="gfcb.2",
        no_field="gfcb.3",
    )
    _set_checkbox_group(
        values,
        field_names={
            "SAT": "gfcb1.0",
            "SATURDAY": "gfcb1.0",
            "SUN": "gfcb1.1",
            "SUNDAY": "gfcb1.1",
            "MON": "gfcb1.2",
            "MONDAY": "gfcb1.2",
            "TUE": "gfcb1.3",
            "TUESDAY": "gfcb1.3",
            "WED": "gfcb1.4",
            "WEDNESDAY": "gfcb1.4",
            "THU": "gfcb1.5",
            "THURSDAY": "gfcb1.5",
            "FRI": "gfcb1.6",
            "FRIDAY": "gfcb1.6",
        },
        selected_tokens=_tokens(field_values.get("off_days")),
    )
    _set_checkbox_group(
        values,
        field_names={
            "REG": "gfcb4.0",
            "REGULAR": "gfcb4.0",
            "FTR": "gfcb4.0",
            "UNASSIGNED REGULAR": "gfcb4.1",
            "UNAS REG": "gfcb4.1",
            "PTR": "gfcb4.2",
            "PTF": "gfcb4.3",
            "MHA": "gfcb4.4",
        },
        selected_tokens=_tokens(field_values.get("employment_status")),
    )
    values["gfcb5"] = (
        _YES
        if _is_truthy(field_values.get("additional_sheet_attached"))
        or bool(_text(field_values.get("facts_continued")))
        else _OFF
    )
    return values


def _build_step_2_values(field_values: dict[str, Any]) -> dict[str, Any]:
    grievant = _first_value(
        field_values,
        "grievant_name_or_class",
        "grievant_name",
    )
    local_number = _text(field_values.get("local_branch_number"))
    union_rep = _text(field_values.get("step2_union_rep"))

    values: dict[str, Any] = {
        "Local #": local_number,
        "Date": _text(field_values.get("form_date")),
        "Local Grievance No": _text(field_values.get("branch_grievance_number")),
        "USPS GATS No": _text(field_values.get("usps_number")),
        "Step 2 Designee Name & Title": _text(
            field_values.get("step2_designee_name_title")
        ),
        "Installation": _text(field_values.get("installation_name")),
        "Phone 1": _text(field_values.get("installation_phone_office")),
        "Origin Local/Branch #": local_number,
        "Business Address": _text(field_values.get("union_business_address")),
        "Authorized Union Rep": union_rep,
        "Phone 2": _text(field_values.get("union_rep_phone_office")),
        "Phone 3": _text(field_values.get("union_rep_phone_other")),
        "Step 1 mtg: Date/Time": _text(
            field_values.get("step1_meeting_datetime")
        ),
        "USPS Rep Name": _text(field_values.get("step1_usps_representative")),
        "Grievant and/or Steward": _text(
            field_values.get("step1_grievant_or_steward")
        ),
        "Grievant Name": grievant,
        "Phone 4": _text(field_values.get("grievant_phone")),
        "Home Address": _text(field_values.get("home_address")),
        "City": _text(field_values.get("city")),
        "State": _text(field_values.get("state")),
        "ZIP": _text(field_values.get("zip")),
        "Job Clasification": _text(field_values.get("job_classification")),
        "Craft Seniority Date": _text(
            field_values.get("craft_seniority_date")
        ),
        "Service Seniority Date": _text(
            field_values.get("service_seniority_date")
        ),
        "Duty Hours": _text(field_values.get("duty_hours")),
        "Installation, Stations or Branch": _text(
            field_values.get("installation_station_branch")
        ),
        "EIN": _first_value(field_values, "ein", "ssn_or_employee_id"),
        "Level": _text(field_values.get("employee_level")),
        "Step": _text(field_values.get("employee_step")),
        "Decision": _text(field_values.get("step1_decision_outcome")),
        "SDO Name": _text(field_values.get("step1_decision_by_name_title")),
        "Violations ART & SECT": _combine_values(
            field_values,
            "violation_articles_citations",
            "violation_national",
        ),
        "Local (ART & SECT)": _text(field_values.get("violation_local_mou")),
        "Other Grounds": _text(field_values.get("violation_other_grounds")),
        "Facts Contentions Date Time Location": _first_value(
            field_values,
            "facts_datetime_location",
            "facts_date_time_location",
        ),
        "What Happened": _text(field_values.get("facts_what_happened")),
        "Corrective Action Requested": _text(
            field_values.get("corrective_action_requested")
        ),
        "Union Representative Printed Name": union_rep,
    }

    _veteran_checkboxes(
        values,
        source_value=field_values.get("veteran_status"),
        yes_field="VET YES",
        no_field="VET NO",
    )
    _set_checkbox_group(
        values,
        field_names={
            "SAT": "SAT",
            "SATURDAY": "SAT",
            "SUN": "SUN",
            "SUNDAY": "SUN",
            "MON": "MON",
            "MONDAY": "MON",
            "TUE": "TUE",
            "TUESDAY": "TUE",
            "WED": "WED",
            "WEDNESDAY": "WED",
            "THU": "THU",
            "THURSDAY": "THU",
            "FRI": "FRI",
            "FRIDAY": "FRI",
        },
        selected_tokens=_tokens(field_values.get("off_days")),
    )
    _set_checkbox_group(
        values,
        field_names={
            "UNASSIGNED REGULAR": "UNAS REG",
            "UNAS REG": "UNAS REG",
            "FTR": "FTR",
            "MHA": "MHA",
            "PTR": "PTR",
            "PTF": "PTF",
        },
        selected_tokens=_tokens(field_values.get("employment_status")),
    )
    values["Additional Sheets?"] = (
        _YES
        if _is_truthy(field_values.get("additional_sheet_attached"))
        or bool(_text(field_values.get("facts_continued")))
        or bool(_text(field_values.get("facts_continued_page3")))
        else _OFF
    )
    return values


class GrievancePdfExportService:
    """Render steward-reviewed values into an official grievance AcroForm."""

    @staticmethod
    def resolve_template_id(template_id: str) -> str:
        return _TEMPLATE_ALIASES.get(template_id, template_id)

    @classmethod
    def build_acroform_values(
        cls,
        template_id: str,
        field_values: dict[str, Any],
    ) -> dict[str, Any]:
        resolved_template_id = cls.resolve_template_id(template_id)
        if resolved_template_id == _STEP_1_TEMPLATE_ID:
            return _build_step_1_values(field_values)
        if resolved_template_id == _STEP_2_TEMPLATE_ID:
            return _build_step_2_values(field_values)
        raise GrievancePdfExportError(
            f"Template does not support official AcroForm export: {template_id}"
        )

    @classmethod
    def render_pdf(
        cls,
        *,
        template_id: str,
        field_values: dict[str, Any],
    ) -> bytes:
        resolved_template_id = cls.resolve_template_id(template_id)
        template = get_grievance_template_by_id(resolved_template_id)
        if template is None:
            raise GrievancePdfExportError(
                f"Unknown grievance template id: {template_id}"
            )

        template_path = resolve_repo_relative_path(template.preferred_blank_pdf)
        if not template_path.is_file():
            raise GrievancePdfExportError(
                f"Official grievance template is missing: {template.preferred_blank_pdf}"
            )

        reader = PdfReader(template_path)
        if reader.is_encrypted and reader.decrypt("") == 0:
            raise GrievancePdfExportError(
                f"Official grievance template cannot be decrypted: {template_id}"
            )
        if not reader.get_fields():
            raise GrievancePdfExportError(
                f"Official grievance template has no AcroForm fields: {template_id}"
            )

        writer = PdfWriter(clone_from=reader)
        pdf_values = cls.build_acroform_values(resolved_template_id, field_values)
        for page in writer.pages:
            writer.update_page_form_field_values(
                page,
                pdf_values,
                auto_regenerate=False,
            )
        acroform = writer.root_object.get("/AcroForm")
        if acroform is not None:
            acroform.get_object()[NameObject("/NeedAppearances")] = BooleanObject(
                False
            )

        output = BytesIO()
        writer.write(output)
        pdf_bytes = output.getvalue()
        if not pdf_bytes.startswith(b"%PDF"):
            raise GrievancePdfExportError("Official grievance PDF serialization failed.")
        return pdf_bytes
