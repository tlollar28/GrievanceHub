"""PDF export generation tests."""

import json
from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfReader

from app.services.report_export.html_renderer import ReportHtmlRenderer
from app.services.report_export.normalizer import normalize_export_payload
from app.services.report_export.pdf_generator import ForbiddenResourceError, ReportPdfGenerator

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "reports" / "sample_wrapper_report.json"


@pytest.fixture
def sample_html():
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    ctx = normalize_export_payload(
        payload,
        case_uuid="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        version_number=1,
    )
    return ReportHtmlRenderer.render(ctx)


def test_pdf_bytes_begin_with_pdf_magic(sample_html):
    pdf_bytes = ReportPdfGenerator.html_to_pdf_bytes(sample_html)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 0


def test_pdf_has_nonzero_page_count(sample_html):
    pdf_bytes = ReportPdfGenerator.html_to_pdf_bytes(sample_html)
    reader = PdfReader(BytesIO(pdf_bytes))
    assert len(reader.pages) > 0


def test_pdf_letter_size_layout_where_testable(sample_html):
    pdf_bytes = ReportPdfGenerator.html_to_pdf_bytes(sample_html)
    reader = PdfReader(BytesIO(pdf_bytes))
    page = reader.pages[0]
    width = float(page.mediabox.width)
    height = float(page.mediabox.height)
    assert 610 <= width <= 620
    assert 790 <= height <= 800


def test_forbidden_http_resource_rejected():
    with pytest.raises(ForbiddenResourceError):
        ReportPdfGenerator._deny_by_default_url_fetcher("http://example.com/style.css")


def test_forbidden_https_resource_rejected():
    with pytest.raises(ForbiddenResourceError):
        ReportPdfGenerator._deny_by_default_url_fetcher("https://example.com/font.woff")


def test_forbidden_file_resource_rejected():
    with pytest.raises(ForbiddenResourceError):
        ReportPdfGenerator._deny_by_default_url_fetcher("file:///C:/Windows/win.ini")


def test_forbidden_unknown_scheme_rejected():
    with pytest.raises(ForbiddenResourceError):
        ReportPdfGenerator._deny_by_default_url_fetcher("javascript:alert(1)")
