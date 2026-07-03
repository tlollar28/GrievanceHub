"""Generate final Phase 3 presentation verification exports."""

from __future__ import annotations

import json
import sys
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from fastapi.testclient import TestClient
from pypdf import PdfReader

from app.main import app
from app.services.report_export.html_renderer import ReportHtmlRenderer
from app.services.report_export.normalizer import normalize_export_payload
from app.services.report_export.pdf_generator import ReportPdfGenerator
from tests.report_export_pdf_qa import assert_pdf_has_no_disclaimer_only_final_page, is_disclaimer_only_page

REPORTS_DIR = ROOT / "data" / "reports"
DEMO_FIXTURE = ROOT / "tests" / "fixtures" / "reports" / "sample_demonstration_wrapper_report.json"
REGRESSION_FIXTURE = ROOT / "tests" / "fixtures" / "regression_questions.json"


def _pdf_stats(pdf_bytes: bytes) -> dict:
    reader = PdfReader(BytesIO(pdf_bytes))
    pages = [page.extract_text() or "" for page in reader.pages]
    last_text = pages[-1].strip() if pages else ""
    return {
        "bytes": len(pdf_bytes),
        "pages": len(pages),
        "last_page_chars": len(last_text),
        "starts_with_pdf": pdf_bytes.startswith(b"%PDF"),
        "final_page_disclaimer_only": is_disclaimer_only_page(last_text),
    }


def _html_checks(html: str) -> dict:
    lowered = html.lower()
    return {
        "contains_unknown_authority": ">unknown<" in lowered or "unknown —" in lowered,
        "contains_remedy_support": "remedy_support" in lowered,
        "contains_retrieval_gate": "relevance gate" in lowered,
        "contains_raw_dict": "'actor'" in html or "&#39;actor&#39;" in html,
        "contains_chunk": "chunk" in lowered,
        "contains_duplicate_article_section": "article 10.5 section 10.5" in lowered,
        "contains_management_management": "management management" in lowered,
        "contains_malformed_citation_punctuation": "137);" in html or "); article" in lowered,
        "contains_management_facts_section_without_structured_field": "facts that may support management" in lowered,
    }


def _export_payload(payload: dict, case_uuid: str, version: int = 1) -> tuple[str, bytes, dict]:
    ctx = normalize_export_payload(payload, case_uuid=case_uuid, version_number=version)
    html = ReportHtmlRenderer.render(ctx)
    pdf = ReportPdfGenerator.html_to_pdf_bytes(html)
    assert_pdf_has_no_disclaimer_only_final_page(pdf)
    stats = _pdf_stats(pdf)
    stats.update(_html_checks(html))
    stats["top_authorities"] = len(ctx["presentation"]["top_governing_authorities"])
    stats["primary_issue_available"] = ctx["presentation"].get("primary_issue_available")
    stats["quick_assessment_citations"] = ctx["presentation"]["quick_assessment"]["cited_authorities"]
    stats["issues_presented"] = ctx["presentation"]["issues_presented"]
    return html, pdf, stats


def main() -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    demo_payload = json.loads(DEMO_FIXTURE.read_text(encoding="utf-8"))
    demo_html, demo_pdf, demo_stats = _export_payload(
        demo_payload,
        case_uuid="dddddddd-eeee-ffff-0000-111111111111",
    )
    demo_html_path = REPORTS_DIR / "phase3_sample_report_final_2026-07-01.html"
    demo_pdf_path = REPORTS_DIR / "phase3_sample_report_final_2026-07-01.pdf"
    demo_html_path.write_text(demo_html, encoding="utf-8")
    demo_pdf_path.write_bytes(demo_pdf)

    questions = json.loads(REGRESSION_FIXTURE.read_text(encoding="utf-8"))
    q1 = next(item for item in questions if item["index"] == 1)
    client = TestClient(app)
    response = client.get(
        "/sources/report/",
        params={"question": q1["question"], "limit_per_source": 3},
    )
    response.raise_for_status()
    live_payload = response.json()

    live_html, live_pdf, live_stats = _export_payload(
        live_payload,
        case_uuid="live-synthetic-q1-export",
    )
    live_html_path = REPORTS_DIR / "phase3_live_synthetic_report_final_2026-07-01.html"
    live_pdf_path = REPORTS_DIR / "phase3_live_synthetic_report_final_2026-07-01.pdf"
    live_html_path.write_text(live_html, encoding="utf-8")
    live_pdf_path.write_bytes(live_pdf)

    summary = {
        "demo_stats": demo_stats,
        "live_stats": live_stats,
        "demo_paths": {"html": str(demo_html_path), "pdf": str(demo_pdf_path)},
        "live_paths": {"html": str(live_html_path), "pdf": str(live_pdf_path)},
    }
    json_path = REPORTS_DIR / "phase3_final_visual_qa_2026-07-02.json"
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
