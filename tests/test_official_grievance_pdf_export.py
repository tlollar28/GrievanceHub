"""Official Step 1 and Step 2 AcroForm integration tests."""

from __future__ import annotations

from hashlib import sha256
from io import BytesIO

import pytest
from pypdf import PdfReader

from app.services.grievance_pdf_export_service import (
    GrievancePdfExportError,
    GrievancePdfExportService,
)
from app.services.grievance_template_registry import (
    OFFICIAL_GRIEVANCE_WORKSHEET_STEP_1,
    OFFICIAL_STANDARD_GRIEVANCE_FORM_STEP_2,
    resolve_repo_relative_path,
    validate_template_assets,
)


def test_official_grievance_templates_are_registered_assets():
    expected = {
        OFFICIAL_GRIEVANCE_WORKSHEET_STEP_1.template_id: (
            "step_1_initial",
            2,
            "67ceeb1bd29da665c82de11f786ab3681f9d83ab04dcb3e379579ac20cc0ddc7",
        ),
        OFFICIAL_STANDARD_GRIEVANCE_FORM_STEP_2.template_id: (
            "step_2_appeal",
            1,
            "2649cc9acade62e78be89d569ae8f857b6c1acd9ac5cca1ad229838ddad138a1",
        ),
    }

    for template in (
        OFFICIAL_GRIEVANCE_WORKSHEET_STEP_1,
        OFFICIAL_STANDARD_GRIEVANCE_FORM_STEP_2,
    ):
        step_level, page_count, expected_sha = expected[template.template_id]
        validation = validate_template_assets(template)
        path = resolve_repo_relative_path(template.preferred_blank_pdf)
        reader = PdfReader(path)
        if reader.is_encrypted:
            assert reader.decrypt("") != 0

        assert validation.all_assets_present is True
        assert template.step_level == step_level
        assert len(reader.pages) == page_count
        assert reader.get_fields()
        assert sha256(path.read_bytes()).hexdigest() == expected_sha


def test_step_1_export_fills_official_acroform_and_mirrored_fields():
    pdf_bytes = GrievancePdfExportService.render_pdf(
        template_id=OFFICIAL_GRIEVANCE_WORKSHEET_STEP_1.template_id,
        field_values={
            "form_date": "July 23, 2026",
            "branch_grievance_number": "G-123",
            "steward_name": "Alex Steward",
            "grievant_name_or_class": "Pat Lee",
            "facts_dates": "July 20, 2026",
            "facts_time": "08:00",
            "facts_location": "Main Plant",
            "facts_what_happened": "Management changed the schedule.",
            "facts_continued": "Continuation text.",
            "corrective_action_requested": "Restore the schedule.",
            "veteran_status": "yes",
            "off_days": ["Saturday", "Monday"],
            "employment_status": "MHA",
        },
    )

    reader = PdfReader(BytesIO(pdf_bytes))
    fields = reader.get_fields()

    assert len(reader.pages) == 2
    assert reader.trailer["/Root"]["/AcroForm"]["/NeedAppearances"].value is False
    assert fields["gff1.0a"]["/V"] == "July 23, 2026"
    assert fields["p2.date"]["/V"] == "July 23, 2026"
    assert fields["gff1.1"]["/V"] == "G-123"
    assert fields["gn.20"]["/V"] == "G-123"
    assert fields["gff2.0"]["/V"] == "Pat Lee"
    assert fields["p2.grievant"]["/V"] == "Pat Lee"
    assert fields["gff3.6"]["/V"] == "Management changed the schedule."
    assert fields["gff3.9"]["/V"] == "Continuation text."
    assert fields["gfcb.2"]["/V"] == "/Yes"
    assert fields["gfcb.3"]["/V"] == "/Off"
    assert fields["gfcb1.0"]["/V"] == "/Yes"
    assert fields["gfcb1.2"]["/V"] == "/Yes"
    assert fields["gfcb4.4"]["/V"] == "/Yes"
    assert fields["gfcb5"]["/V"] == "/Yes"


def test_step_2_export_replaces_legacy_alias_with_official_acroform():
    pdf_bytes = GrievancePdfExportService.render_pdf(
        template_id="local_300_form_79_1",
        field_values={
            "form_date": "07/23/2026",
            "local_branch_number": "300",
            "branch_grievance_number": "G-456",
            "usps_number": "USPS-9",
            "step2_designee_name_title": "Manager A",
            "grievant_name_or_class": "Pat Lee",
            "violation_articles_citations": "Article 15.2",
            "facts_datetime_location": "07/20/2026 08:00 Main Plant",
            "facts_what_happened": "Management denied the request.",
            "corrective_action_requested": "Make the grievant whole.",
            "veteran_status": "no",
            "off_days": "Sunday, Thursday",
            "employment_status": "FTR",
            "additional_sheet_attached": True,
        },
    )

    reader = PdfReader(BytesIO(pdf_bytes))
    fields = reader.get_fields()

    assert reader.is_encrypted is False
    assert len(reader.pages) == 1
    assert reader.trailer["/Root"]["/AcroForm"]["/NeedAppearances"].value is False
    assert fields["Local #"]["/V"] == "300"
    assert fields["Local Grievance No"]["/V"] == "G-456"
    assert fields["Grievant Name"]["/V"] == "Pat Lee"
    assert fields["Violations ART & SECT"]["/V"] == "Article 15.2"
    assert fields["Facts Contentions Date Time Location"]["/V"].startswith(
        "07/20/2026"
    )
    assert fields["VET YES"]["/V"] == "/Off"
    assert fields["VET NO"]["/V"] == "/Yes"
    assert fields["SUN"]["/V"] == "/Yes"
    assert fields["THU"]["/V"] == "/Yes"
    assert fields["FTR"]["/V"] == "/Yes"
    assert fields["Additional Sheets?"]["/V"] == "/Yes"


def test_step_3_export_is_not_implemented():
    with pytest.raises(GrievancePdfExportError, match="Unknown grievance template"):
        GrievancePdfExportService.render_pdf(
            template_id="step_3_template_deferred",
            field_values={},
        )
