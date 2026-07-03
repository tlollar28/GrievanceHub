"""Generate Phase 3 presentation correction sample and live synthetic exports."""

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

REPORTS_DIR = ROOT / "data" / "reports"
DEMO_FIXTURE = ROOT / "tests" / "fixtures" / "reports" / "sample_demonstration_wrapper_report.json"
REGRESSION_FIXTURE = ROOT / "tests" / "fixtures" / "regression_questions.json"


def _pdf_stats(pdf_bytes: bytes) -> dict:
    reader = PdfReader(BytesIO(pdf_bytes))
    pages = len(reader.pages)
    last_text = (reader.pages[-1].extract_text() or "").strip()
    return {
        "bytes": len(pdf_bytes),
        "pages": pages,
        "last_page_chars": len(last_text),
        "starts_with_pdf": pdf_bytes.startswith(b"%PDF"),
    }


def _export_payload(payload: dict, case_uuid: str, version: int = 1) -> tuple[str, bytes, dict]:
    ctx = normalize_export_payload(payload, case_uuid=case_uuid, version_number=version)
    html = ReportHtmlRenderer.render(ctx)
    pdf = ReportPdfGenerator.html_to_pdf_bytes(html)
    stats = _pdf_stats(pdf)
    stats["top_authorities"] = len(ctx["presentation"]["top_governing_authorities"])
    stats["chunk_in_html"] = "chunk" in html.lower()
    return html, pdf, stats


def main() -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    demo_payload = json.loads(DEMO_FIXTURE.read_text(encoding="utf-8"))
    demo_html, demo_pdf, demo_stats = _export_payload(
        demo_payload,
        case_uuid="dddddddd-eeee-ffff-0000-111111111111",
    )
    demo_html_path = REPORTS_DIR / "phase3_sample_report_revised_2026-07-01.html"
    demo_pdf_path = REPORTS_DIR / "phase3_sample_report_revised_2026-07-01.pdf"
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
    live_html_path = REPORTS_DIR / "phase3_live_synthetic_report_2026-07-01.html"
    live_pdf_path = REPORTS_DIR / "phase3_live_synthetic_report_2026-07-01.pdf"
    live_html_path.write_text(live_html, encoding="utf-8")
    live_pdf_path.write_bytes(live_pdf)

    report = live_payload.get("report") or {}
    analysis = report.get("detailed_analysis") or {}
    depth = {
        "question_index": 1,
        "ranked_authorities_count": len(live_payload.get("ranked_authorities") or []),
        "top_authorities_exported": live_stats["top_authorities"],
        "quick_assessment_summary_chars": len((report.get("quick_assessment") or {}).get("summary") or ""),
        "key_violations_count": len(report.get("key_contract_violations") or []),
        "remedy_statements_count": len((report.get("recommended_remedy") or {}).get("statements") or []),
        "grievance_framework_chars": len(analysis.get("grievance_framework") or ""),
        "evidence_to_gather_count": len(analysis.get("evidence_to_gather") or []),
        "strategic_tips_count": len(analysis.get("strategic_tips") or []),
        "known_facts_count": len((report.get("limitations") or {}).get("known_facts") or []),
        "management_limiting_count": len(report.get("management_limiting_authority") or []),
    }

    summary = {
        "demo_stats": demo_stats,
        "live_stats": live_stats,
        "live_depth": depth,
        "demo_paths": {
            "html": str(demo_html_path),
            "pdf": str(demo_pdf_path),
        },
        "live_paths": {
            "html": str(live_html_path),
            "pdf": str(live_pdf_path),
        },
    }
    summary_path = REPORTS_DIR / "phase3_report_presentation_correction_2026-07-01.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
