"""Presentation-layer export tests for citations, authorities, and deduplication."""

import json
import re
from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfReader

from app.services.report_export.citation_formatter import (
    format_page_reference,
    format_source_reference_summary,
    format_steward_citation,
)
from app.services.report_export.html_renderer import ReportHtmlRenderer
from app.services.report_export.normalizer import normalize_export_payload
from app.services.report_export.pdf_generator import ReportPdfGenerator
from app.services.report_export.presentation import build_top_governing_authorities, format_generated_at
from app.services.report_export.text_formatter import (
    EMBEDDED_QUOTE_MAX_LENGTH,
    format_authority_support_label,
    format_citation_check_display,
    format_dispute_frame_sentence,
    format_display_quote,
    format_grievance_framework_display,
    format_source_coverage_caveat,
    normalize_article_section_label,
    rebuild_quick_assessment_display,
    sanitize_authority_description,
    sanitize_embedded_quotes_in_text,
    sanitize_public_text,
)
from tests.report_export_pdf_qa import assert_pdf_has_no_disclaimer_only_final_page

COVERAGE_FIXTURE = Path(__file__).parent / "fixtures" / "reports" / "sample_wrapper_report.json"
DEMO_FIXTURE = Path(__file__).parent / "fixtures" / "reports" / "sample_demonstration_wrapper_report.json"


@pytest.fixture
def coverage_context():
    payload = json.loads(COVERAGE_FIXTURE.read_text(encoding="utf-8"))
    return normalize_export_payload(
        payload,
        case_uuid="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        version_number=1,
    )


@pytest.fixture
def demo_context():
    payload = json.loads(DEMO_FIXTURE.read_text(encoding="utf-8"))
    return normalize_export_payload(
        payload,
        case_uuid="dddddddd-eeee-ffff-0000-111111111111",
        version_number=1,
    )


def test_citation_formatter_hierarchy():
    label = format_steward_citation(
        {
            "document_name": "NPMHU CIM v6",
            "document_type": "CIM",
            "page": 137,
            "chunk": 242,
        },
        article_or_section="Article 10, Section 3",
    )
    assert label == "NPMHU CIM v6 — Article 10, Section 3 — p. 137"
    assert "chunk" not in label
    assert "242" not in label


def test_citation_formatter_omits_placeholders():
    label = format_steward_citation(
        {
            "document_name": "Unknown",
            "document_type": "CIM",
            "page": None,
            "chunk": 1,
        },
        article_or_section="N/A",
    )
    assert label == "CIM"
    assert "Unknown" not in label
    assert "N/A" not in label


def test_top_authorities_max_five_and_dedupe(demo_context):
    authorities = demo_context["presentation"]["top_governing_authorities"]
    assert 1 <= len(authorities) <= 5
    assert len(authorities) == 4
    grouped = [item for item in authorities if item["article_or_section"] == "Article 10, Section 3"]
    assert len(grouped) == 1
    assert len(grouped[0]["direct_quotes"]) == 2


def test_management_limiting_not_in_top_authorities(coverage_context):
    top = coverage_context["presentation"]["top_governing_authorities"]
    roles = {(item.get("role") or "").lower() for item in top}
    assert "management_limiting" not in roles


def test_duplicate_full_quote_suppressed_in_violations(coverage_context):
    html = ReportHtmlRenderer.render(coverage_context)
    assert html.count("Employees who have annual leave approved are entitled") == 1
    assert "See Top Governing Authorities for the full grounded quotation." in html


def test_supporting_evidence_prefers_factual_items(coverage_context):
    evidence = coverage_context["presentation"]["supporting_evidence"]
    assert len(evidence) == 1
    assert "Written leave approval notice" in evidence[0]["what_it_supports"]


def test_duplicate_limitation_caveats_removed(coverage_context):
    caveats = coverage_context["presentation"]["limitations"]["caveats"]
    assert len(caveats) == 1
    assert "research draft" in caveats[0].lower()
    assert all("LMOU" not in caveat for caveat in caveats)


def test_authority_pluralization_in_source_references(demo_context):
    html = ReportHtmlRenderer.render(demo_context)
    assert "1 distinct authority, 2 retrieved passages" in html
    assert "3 distinct authorities, 3 retrieved passages" in html
    assert "2 authorities)" not in html


def test_grouped_authority_shows_all_pages(demo_context):
    grouped = [
        item
        for item in demo_context["presentation"]["top_governing_authorities"]
        if item["article_or_section"] == "Article 10, Section 3"
    ]
    assert len(grouped) == 1
    assert grouped[0]["citation_label"].endswith("pp. 137\u2013138")
    html = ReportHtmlRenderer.render(demo_context)
    assert "pp. 137\u2013138" in html


def test_page_reference_formatting():
    assert format_page_reference([468]) == "p. 468"
    assert format_page_reference([468, 469]) == "pp. 468\u2013469"
    assert format_page_reference([468, 471]) == "pp. 468, 471"


def test_source_reference_summary_wording():
    assert (
        format_source_reference_summary(2, 3)
        == "2 distinct authorities, 3 retrieved passages"
    )
    assert (
        format_source_reference_summary(1, 1)
        == "1 distinct authority, 1 retrieved passage"
    )


def test_source_references_hide_internal_metadata(demo_context):
    html = ReportHtmlRenderer.render(demo_context)
    lowered = html.lower()
    assert "chunk" not in lowered
    assert "keyword_overlap" not in lowered
    assert "relevance_score" not in lowered


def test_pdf_has_no_footer_only_blank_page(demo_context):
    html = ReportHtmlRenderer.render(demo_context)
    pdf_bytes = ReportPdfGenerator.html_to_pdf_bytes(html)
    assert_pdf_has_no_disclaimer_only_final_page(pdf_bytes)
    reader = PdfReader(BytesIO(pdf_bytes))
    assert len(reader.pages) >= 1
    last_text = (reader.pages[-1].extract_text() or "").strip()
    assert "Citation check" in last_text or "Source References" in last_text


def test_build_top_authorities_from_report_sections_when_ranked_missing():
    payload = json.loads(COVERAGE_FIXTURE.read_text(encoding="utf-8"))
    payload["ranked_authorities"] = []
    report = payload["report"]
    top = build_top_governing_authorities(payload, report)
    assert len(top) >= 1


def test_fewer_than_five_top_authorities_is_valid(coverage_context):
    authorities = coverage_context["presentation"]["top_governing_authorities"]
    assert len(authorities) == 1
    assert len(authorities[0]["direct_quotes"]) == 2


def test_unknown_values_not_public_in_html(demo_context):
    html = ReportHtmlRenderer.render(demo_context)
    assert ">Unknown<" not in html
    assert "Unknown —" not in html
    assert "N/A" not in html
    assert ">None<" not in html


def test_identical_article_section_not_repeated():
    assert normalize_article_section_label("Article 10.5 Section 10.5") == "Article 10.5"
    assert normalize_article_section_label("Article 10 Section 10.5") == "Article 10, Section 10.5"


def test_missing_metadata_falls_back_to_source_title_and_page():
    label = format_steward_citation(
        {
            "document_name": "NPMHU-USPS Contract Interpretation Manual v6",
            "document_type": "CIM",
            "page": 137,
        },
        article_or_section="Unknown",
    )
    assert label == "NPMHU-USPS Contract Interpretation Manual v6 — p. 137"
    assert "Unknown" not in label


def test_dispute_frame_renders_sentence_not_dict():
    sentence = format_dispute_frame_sentence(
        {
            "actor": "management",
            "action": "canceled previously approved annual leave",
            "management_actions": [],
            "employee_actions": [],
        }
    )
    assert sentence == "Management canceled previously approved annual leave."
    assert "{" not in sentence


def test_grievance_framework_display_omits_raw_dict():
    rendered = format_grievance_framework_display(
        "Dispute frame: {'actor': 'management', 'action': 'test', 'management_actions': []}",
        {"dispute_frame": {"actor": "management", "action": "test", "management_actions": []}},
        [],
    )
    assert "{" not in rendered
    assert "'actor'" not in rendered


def test_internal_pipeline_terms_removed_from_remedy_notice():
    cleaned = sanitize_public_text(
        "No remedy_support authority was retrieved above the relevance gates. "
        "Confirm: Whether leave was approved."
    )
    assert "remedy_support" not in cleaned
    assert "relevance gate" not in cleaned.lower()
    assert "No sufficiently relevant contractual remedy authority was located." in cleaned
    assert "Confirm:" in cleaned


def test_metadata_uses_distinct_label_and_value_elements(demo_context):
    html = ReportHtmlRenderer.render(demo_context)
    assert "<dt>Case Reference</dt>" in html
    assert "<dd>" in html
    assert "Case Ref:" in html


def test_lmou_disclosure_deduplicated_in_demo(demo_context):
    html = ReportHtmlRenderer.render(demo_context)
    lmou_unindexed_count = html.lower().count("not currently indexed in grievancehub")
    assert lmou_unindexed_count == 1
    caveats = demo_context["presentation"]["limitations"]["caveats"]
    assert all("LMOU" not in caveat for caveat in caveats)


def test_primary_issue_included_when_available(demo_context):
    issues = demo_context["presentation"]["issues_presented"]
    assert issues[0] == "Cancellation of previously approved annual leave"
    assert any("information request" in issue.lower() for issue in issues)
    assert demo_context["presentation"]["primary_issue_available"] is True


def test_no_raw_dict_in_demo_html(demo_context):
    html = ReportHtmlRenderer.render(demo_context)
    assert "'actor'" not in html
    assert "&#39;actor&#39;" not in html


def test_quick_assessment_citations_deduped(demo_context):
    cited = demo_context["presentation"]["quick_assessment"]["cited_authorities"]
    assert len(cited) == len(set(item.lower() for item in cited))
    assert cited.count("Article 10, Section 3 (NPMHU CIM v6, p. 137)") == 1


def test_quick_assessment_summary_has_no_embedded_authority_clause(demo_context):
    summary = demo_context["presentation"]["quick_assessment"]["summary"]
    assert "Retrieved authorities include:" not in summary


def test_no_malformed_citation_punctuation_in_demo_html(demo_context):
    html = ReportHtmlRenderer.render(demo_context)
    assert "137);" not in html


def test_semantically_duplicate_issues_removed(demo_context):
    issues = demo_context["presentation"]["issues_presented"]
    assert "Cancellation of previously approved annual leave" in issues
    assert not any(
        issue.lower() == "cancellation of approved annual leave"
        for issue in issues
    )


def test_no_repeated_actor_prefix_in_framework(demo_context):
    framework = demo_context["presentation"]["grievance_framework_display"]
    assert "Management Management" not in framework


def test_management_supporting_facts_omitted_without_structured_field(demo_context):
    html = ReportHtmlRenderer.render(demo_context)
    assert demo_context["presentation"]["management_supporting_facts"] == []
    assert "Facts That May Support Management" not in html


def test_truncated_quote_receives_ellipsis():
    formatted = format_display_quote(
        "Upon the written request of the Union, the Employer will furnish such information, "
        "provided, however, that the Employer may require the Union to reimburse the USPS "
        "for any costs reasonably incurred in"
    )
    assert formatted is not None
    assert formatted.endswith("…")
    assert "reasonably incurred in…" in formatted
    assert " …" not in formatted


def test_generated_at_minutes_are_zero_padded():
    formatted = format_generated_at("2026-07-02T16:03:00+00:00")
    assert formatted is not None
    assert "12:03 PM" in formatted
    assert "12:3 PM" not in formatted


def test_generated_at_single_digit_hour_still_unpadded():
    formatted = format_generated_at("2026-07-02T13:05:00+00:00")
    assert formatted is not None
    assert "9:05 AM" in formatted
    assert "09:05 AM" not in formatted


def test_quote_truncation_uses_word_boundary_not_partial_word():
    long_quote = (
        "While not contractually obligated to do so, management should give reasonable "
        "consideration to requests for annual leave cancellation, unless otherwise "
        "provided in the Local Memorandum of Understanding."
    )
    truncated_input = long_quote[:200]
    assert truncated_input.endswith("Understandin")
    formatted = format_display_quote(
        truncated_input,
        known_quotes=[long_quote],
        max_length=EMBEDDED_QUOTE_MAX_LENGTH,
    )
    assert formatted is not None
    assert "Understandin…" not in formatted
    assert formatted.endswith(".")
    assert formatted.count("…") == 0


def test_quote_truncation_appends_single_ellipsis_without_space():
    long_quote = "word " * 80
    formatted = format_display_quote(long_quote, max_length=60)
    assert formatted is not None
    assert formatted.endswith("…")
    assert formatted.count("…") == 1
    assert " …" not in formatted
    assert not formatted.endswith("….")
    assert not formatted.endswith("....")


def test_quote_truncation_never_ends_with_partial_word():
    long_quote = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron pi rho sigma tau upsilon phi chi psi omega"
    formatted = format_display_quote(long_quote, max_length=40)
    assert formatted is not None
    tail = formatted.rstrip("…")
    assert tail[-1].isalpha()
    last_word = tail.rsplit(" ", 1)[-1]
    assert last_word in long_quote


def test_embedded_quote_sanitizer_restores_known_full_quote():
    full_quote = (
        "While not contractually obligated to do so, management should give reasonable "
        "consideration to requests for annual leave cancellation, unless otherwise "
        "provided in the Local Memorandum of Understanding."
    )
    embedded = f'Use separate treatment. "{full_quote[:200]}".'
    sanitized = sanitize_embedded_quotes_in_text(embedded, known_quotes=[full_quote])
    assert "Understandin…" not in sanitized
    assert "Local Memorandum of Understanding." in sanitized
    assert '…".' not in sanitized


def test_live_style_quick_assessment_normalization():
    qa = rebuild_quick_assessment_display(
        {
            "summary": (
                "Cancellation of previously approved annual leave. Retrieved authorities include: "
                "Article 10.5 (NPMHU National Agreement 2022-2025, p. 44); "
                "Article 10 (NPMHU-USPS Contract Interpretation Manual v6, p. 137); "
                "Article 10 (NPMHU-USPS Contract Interpretation Manual v6, p. 137); "
                "Article 31 (NPMHU-USPS Contract Interpretation Manual v6, p. 468)."
            ),
            "cited_authorities": [],
            "why": "",
            "grievability": "Likely Grievable",
            "confidence": "Medium",
        },
        [
            {
                "article_or_section": "Article 10.5",
                "citation": {
                    "document_name": "NPMHU National Agreement 2022-2025",
                    "document_type": "CONTRACT",
                    "page": 44,
                },
            },
            {
                "article_or_section": "Article 10",
                "citation": {
                    "document_name": "NPMHU-USPS Contract Interpretation Manual v6",
                    "document_type": "CIM",
                    "page": 137,
                },
            },
        ],
    )
    assert "137);" not in qa["summary"]
    assert "Retrieved authorities include:" not in qa["summary"]
    assert "Article 10 (" not in qa["summary"]
    assert qa["summary"] == "Cancellation of previously approved annual leave."
    assert len(qa["cited_authorities"]) == 2


def test_sanitize_authority_description_removes_unsupported_remedy_claim():
    quote = (
        "All advance commitments for granting annual leave must be honored except "
        "in serious emergency situations."
    )
    cleaned = sanitize_authority_description(
        "This authority can be used to argue that employees are entitled to "
        "compensation or alternatives if their leave is canceled improperly.",
        direct_quote=quote,
    )
    assert "compensation or alternatives" not in cleaned.lower()
    assert "must be honored" in cleaned.lower() or "advance commitments" in cleaned.lower()


def test_authority_support_label_limits_overconfidence():
    label = format_authority_support_label(
        "High",
        missing_facts_count=1,
        remedy_authority_found=False,
        union_supporting_count=2,
    )
    assert "Strong for the cited contractual rule" in label
    assert "steward review" in label.lower()
    assert label.count("High") == 0

    limited = format_authority_support_label(
        "High",
        missing_facts_count=1,
        remedy_authority_found=False,
        union_supporting_count=0,
    )
    assert "no union-supporting contractual rule was retained" in limited.lower()


def test_source_coverage_caveat_plain_english():
    caveat = format_source_coverage_caveat(
        {
            "source_type": "ELM",
            "passages_found": 0,
            "passages_retained_in_pool": 0,
            "passages_ranked": 0,
        }
    )
    assert "searched" in caveat.lower()
    assert "no relevant passage" in caveat.lower()
    assert "0 queries" not in caveat
    assert "survived retrieval" not in caveat


def test_citation_check_display_is_steward_neutral():
    display = format_citation_check_display({"status": "Passed"})
    assert display["heading"] == "Citation check"
    assert "Validation" not in display["message"]
    assert "matched to the retrieved source passages" in display["message"]


def test_steward_report_repair_wording_in_html(demo_context):
    html = ReportHtmlRenderer.render(demo_context)
    lowered = html.lower()
    assert "confidence:" not in lowered
    assert "authority support:" in lowered
    assert "citation check" in lowered
    assert "citation validation" not in lowered
    assert "compensation or alternatives" not in lowered
    assert "ranked authorities" not in lowered
    assert "survived retrieval" not in lowered
