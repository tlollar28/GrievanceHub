"""Normalization tests for report export payloads."""

import json
from pathlib import Path

import pytest

from app.services.report_export.normalizer import InvalidReportDataError, normalize_export_payload

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "reports" / "sample_wrapper_report.json"


@pytest.fixture
def wrapper_payload():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_normalize_analysis_service_wrapper(wrapper_payload):
    ctx = normalize_export_payload(
        wrapper_payload,
        case_uuid="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        version_number=2,
    )
    assert ctx["case_uuid"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert ctx["version_number"] == 2
    assert ctx["report"]["report_title"] == "GrievanceHub Analysis Report"
    assert ctx["report"]["key_contract_violations"][0]["direct_quote"].startswith("Employees who have")


def test_normalize_inner_report_only(wrapper_payload):
    inner = wrapper_payload["report"]
    ctx = normalize_export_payload(inner, case_uuid="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    assert ctx["report"]["brand"] == "GrievanceHub"
    assert ctx["case_uuid"] == "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


def test_invalid_report_data_raises():
    with pytest.raises(InvalidReportDataError):
        normalize_export_payload({"question": "missing report"})


def test_invalid_report_schema_raises():
    with pytest.raises(InvalidReportDataError):
        normalize_export_payload({"report": {"brand": "GrievanceHub"}})
