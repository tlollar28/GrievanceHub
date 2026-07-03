"""Filename, header, route, and logging security tests."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.case_service import CaseNotFoundError
from app.services.report_export.filename_utils import build_export_filename
from app.services.report_export.normalizer import normalize_export_payload
from app.services.report_export_service import ReportExportService

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "reports" / "sample_wrapper_report.json"

CASE_UUID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def test_filename_sanitization_and_no_pii():
    filename = build_export_filename(CASE_UUID, 3, "pdf")
    assert filename == "grievancehub-report-aaaaaaaa-v3.pdf"
    assert "employee" not in filename.lower()


class _MockCaseVersion:
    def __enter__(self):
        self._patch = patch("app.services.report_export_service.CaseService.get_case")
        self.mock_get = self._patch.start()
        payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        version = SimpleNamespace(
            version_number=1,
            report_data=payload,
            created_at=datetime.now(timezone.utc),
        )
        self.mock_get.return_value = SimpleNamespace(report_versions=[version])
        return self

    def __exit__(self, *args):
        self._patch.stop()


class _MockCaseVersionsTwo:
    def __enter__(self):
        self._patch = patch("app.services.report_export_service.CaseService.get_case")
        self.mock_get = self._patch.start()
        payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        v1 = SimpleNamespace(version_number=1, report_data=payload, created_at=datetime.now(timezone.utc))
        v2_payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        v2_payload["report"]["generated_at"] = "2026-07-02T12:00:00+00:00"
        v2 = SimpleNamespace(version_number=2, report_data=v2_payload, created_at=datetime.now(timezone.utc))
        self.mock_get.return_value = SimpleNamespace(report_versions=[v1, v2])
        return self

    def __exit__(self, *args):
        self._patch.stop()


def test_html_preview_headers():
    client = TestClient(app)
    with _MockCaseVersion():
        response = client.get(f"/cases/{CASE_UUID}/export/preview")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "inline" in response.headers["content-disposition"]


def test_html_download_headers():
    client = TestClient(app)
    with _MockCaseVersion():
        response = client.get(f"/cases/{CASE_UUID}/export/html")
    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    assert response.headers["cache-control"] == "no-store"


def test_pdf_download_headers():
    client = TestClient(app)
    with _MockCaseVersion():
        response = client.get(f"/cases/{CASE_UUID}/export/pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["cache-control"] == "no-store"
    assert response.content.startswith(b"%PDF")


def test_latest_version_selected():
    client = TestClient(app)
    with _MockCaseVersionsTwo():
        response = client.get(f"/cases/{CASE_UUID}/export/html")
    assert response.status_code == 200
    assert "Version</dt><dd>2" in response.text or "Report Version</dt><dd>2" in response.text


def test_historical_version_selected():
    client = TestClient(app)
    with _MockCaseVersionsTwo():
        response = client.get(f"/cases/{CASE_UUID}/versions/1/export/html")
    assert response.status_code == 200
    assert "Version</dt><dd>1" in response.text or "Report Version</dt><dd>1" in response.text


def test_case_not_found():
    client = TestClient(app)
    with patch(
        "app.api.routes.exports.ReportExportService.export_case_html",
        side_effect=CaseNotFoundError(CASE_UUID),
    ):
        response = client.get(f"/cases/{CASE_UUID}/export/html")
    assert response.status_code == 404


def test_invalid_case_uuid():
    client = TestClient(app)
    response = client.get("/cases/not-a-uuid/export/html")
    assert response.status_code == 422


def test_version_not_found():
    client = TestClient(app)
    with _MockCaseVersion():
        response = client.get(f"/cases/{CASE_UUID}/versions/99/export/html")
    assert response.status_code == 404


def test_no_report_versions():
    client = TestClient(app)
    with patch("app.services.report_export_service.CaseService.get_case") as mock_get:
        mock_get.return_value = SimpleNamespace(report_versions=[])
        response = client.get(f"/cases/{CASE_UUID}/export/html")
    assert response.status_code == 404


def test_export_never_calls_analysis_service():
    client = TestClient(app)
    with _MockCaseVersion():
        with patch("app.services.analysis_service.AnalysisService.generate_report") as mock_generate:
            client.get(f"/cases/{CASE_UUID}/export/pdf")
    mock_generate.assert_not_called()


def test_logging_does_not_include_report_body(caplog):
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    db = MagicMock()
    with patch(
        "app.services.report_export_service.CaseService.get_case",
    ) as mock_get:
        version = SimpleNamespace(version_number=1, report_data=payload)
        mock_get.return_value = SimpleNamespace(report_versions=[version])
        with caplog.at_level(logging.INFO):
            ReportExportService.export_case_html(db, CASE_UUID)
    joined = " ".join(record.message for record in caplog.records)
    assert "Employees who have annual leave approved" not in joined
    assert "Can management cancel" not in joined
    assert CASE_UUID in joined
