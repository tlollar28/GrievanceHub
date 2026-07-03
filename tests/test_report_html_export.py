"""HTML export rendering tests."""

import json
from pathlib import Path

import pytest
from jinja2 import UndefinedError

from app.services.report_export.html_renderer import ReportHtmlRenderer
from app.services.report_export.normalizer import normalize_export_payload

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "reports" / "sample_wrapper_report.json"


@pytest.fixture
def export_context():
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return normalize_export_payload(
        payload,
        case_uuid="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        version_number=1,
    )


def test_required_sections_appear(export_context):
    html = ReportHtmlRenderer.render(export_context)
    assert "GrievanceHub Analysis Report" in html
    assert "Your Question" in html
    assert "Quick Assessment" in html
    assert "Key Contract Violations / Union Contentions" in html
    assert "Top Governing Authorities" in html
    assert "Management-Limiting Authority" in html
    assert "Recommended Remedy" in html
    assert "Detailed Analysis" in html
    assert "Limitations and Missing Sources" in html
    assert "Source References" in html
    assert "Citation Validation" in html


def test_grounded_quote_and_citation_appear(export_context):
    html = ReportHtmlRenderer.render(export_context)
    assert "Employees who have annual leave approved are entitled" in html
    assert "NPMHU CIM v6" in html
    assert "p. 137" in html
    assert "chunk" not in html.lower()


def test_management_limiting_separate_section(export_context):
    html = ReportHtmlRenderer.render(export_context)
    mgmt_index = html.index("Management-Limiting Authority")
    violations_index = html.index("Key Contract Violations / Union Contentions")
    top_index = html.index("Top Governing Authorities")
    assert violations_index < top_index < mgmt_index
    assert "Management retains the right to assign work." in html


def test_lmou_unindexed_disclosure(export_context):
    html = ReportHtmlRenderer.render(export_context)
    assert "LMOU" in html
    assert "not currently indexed" in html


def test_unavailable_authority_disclosure(export_context):
    html = ReportHtmlRenderer.render(export_context)
    assert "investigatory union representation" in html.lower()


def test_html_autoescaping_script_tags(export_context):
    export_context["report"]["your_question"] = '<script>alert("test")</script>'
    html = ReportHtmlRenderer.render(export_context)
    assert '<script>alert("test")</script>' not in html
    assert "&lt;script&gt;alert" in html


def test_markup_in_direct_quote_is_escaped(export_context):
    export_context["presentation"]["key_contract_violations"][0]["direct_quote"] = "<b>unsafe</b> quote"
    html = ReportHtmlRenderer.render(export_context)
    assert "<b>unsafe</b>" not in html
    assert "&lt;b&gt;unsafe&lt;/b&gt;" in html


def test_strict_undefined_raises_for_missing_template_data(export_context):
    del export_context["report"]["brand"]
    with pytest.raises(UndefinedError):
        ReportHtmlRenderer.render(export_context)


def test_self_contained_html_embeds_css(export_context):
    html = ReportHtmlRenderer.render(export_context)
    assert "<style>" in html
    assert "--gh-primary" in html
    assert "http://" not in html
    assert "https://" not in html
    assert "cdn" not in html.lower()


def test_grievancehub_branding_present_crea_absent(export_context):
    html = ReportHtmlRenderer.render(export_context)
    assert "GrievanceHub" in html
    assert "CREA" not in html


def test_dynamic_section_numbering_skips_empty_sections():
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    inner = payload["report"]
    inner["secondary_issues"] = []
    inner["union_supporting_authority"] = []
    inner["procedural_requirements"] = []
    inner["information_rights"] = []
    inner["timeline_requirements"] = []
    inner["remedy_authority"] = []
    ctx = normalize_export_payload(payload, case_uuid="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", version_number=1)
    html = ReportHtmlRenderer.render(ctx)
    assert "1." in html
    assert "Issues Presented" not in html


def test_grievance_template_placeholder_absent(export_context):
    html = ReportHtmlRenderer.render(export_context)
    assert "Grievance template matching is not yet available." not in html
    assert "Matching Grievance Templates" not in html


def test_human_readable_generated_timestamp(export_context):
    html = ReportHtmlRenderer.render(export_context)
    assert "July 1, 2026" in html
    assert "2026-07-01T12:00:00" not in html


def test_case_reference_instead_of_full_uuid(export_context):
    html = ReportHtmlRenderer.render(export_context)
    assert "Case Ref: AAAAAAAA" in html
    assert "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee" not in html
