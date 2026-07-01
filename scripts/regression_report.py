"""Regression scorecard: live report API + completeness scoring."""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from tests.test_regression_harness import _normalize_report, score_report_completeness

FIXTURE_PATH = ROOT / "tests" / "fixtures" / "regression_questions.json"
OUTPUT_PATH = ROOT / "data" / "reports" / "regression_scorecard.json"
BASE_URL = "http://127.0.0.1:8000"
HEALTH_URL = f"{BASE_URL}/health"
REPORT_PATH = "/sources/report/"

CATEGORY_KEYS = {
    "union_supporting": "union_supporting_authority",
    "procedural": "procedural_requirements",
    "information_rights": "information_rights",
    "timeline": "timeline_requirements",
    "remedy": "remedy_authority",
    "management_limiting": "management_limiting_authority",
}


def _empty_report_categories(payload: dict) -> list[str]:
    inner = payload.get("report") if isinstance(payload.get("report"), dict) else payload
    empty: list[str] = []
    for label, field in CATEGORY_KEYS.items():
        value = inner.get(field) or []
        if not value:
            empty.append(label)
    return empty


def _summarize_retrieval_gaps(gaps: dict | None) -> str:
    if not gaps:
        return "none"
    missing = gaps.get("missing_source_types") or []
    unresolved = gaps.get("issues_without_supporting_authority") or []
    parts: list[str] = []
    if missing:
        parts.append("missing_source_types=" + ", ".join(str(x) for x in missing))
    if unresolved:
        preview = "; ".join(str(x) for x in unresolved[:4])
        suffix = "..." if len(unresolved) > 4 else ""
        parts.append(
            f"issues_without_supporting_authority={len(unresolved)}: {preview}{suffix}"
        )
    return "; ".join(parts) if parts else "no missing sources or unresolved issues flagged"


def _explain_completeness(payload: dict, score: str) -> list[str]:
    """Explain why score is not PASS (mirrors score_report_completeness)."""
    report = _normalize_report(payload)
    reasons: list[str] = []

    ranked = report.get("ranked_authorities") or []
    violations = report.get("key_contract_violations") or []
    retrieval_gaps = report.get("retrieval_gaps") or {}
    citation = report.get("citation_validation") or {}

    citation_status = str(citation.get("status") or "").lower()
    missing_sources = retrieval_gaps.get("missing_source_types") or []
    unresolved = retrieval_gaps.get("issues_without_supporting_authority") or []
    has_substance = bool(violations) or len(ranked) >= 2
    gap_burden = len(missing_sources) + len(unresolved)

    if score == "PASS":
        return ["All PASS criteria met: substance, zero retrieval gap burden, citation OK."]

    if not ranked:
        reasons.append("FAIL/PARTIAL: no ranked_authorities.")
        return reasons

    if citation_status in {"failed", "fail", "needs review"}:
        reasons.append(f"citation_validation status is {citation.get('status')!r} (FAIL).")
        if score != "FAIL":
            reasons.append("Note: scored PARTIAL only if other rules apply; citation failure forces FAIL.")
        return reasons

    if score == "PARTIAL":
        reasons.append("PARTIAL instead of PASS because one or more PASS gates failed:")
        if gap_burden:
            reasons.append(
                f"retrieval gap burden {gap_burden} "
                f"(missing_source_types={missing_sources or []}, "
                f"unresolved_issues={len(unresolved)})."
            )
        if not has_substance:
            reasons.append(
                "has_substance=false: need key_contract_violations or at least 2 ranked_authorities."
            )
        if citation_status not in {"passed", "pass", ""}:
            reasons.append(f"citation_status={citation.get('status')!r} is not a passing status.")
        if has_substance and gap_burden == 0 and citation_status in {"passed", "pass", ""}:
            reasons.append("Unexpected: logic would expect PASS; re-check payload merge.")
        return reasons

    reasons.append("FAIL: insufficient substance and citation not sufficient for PARTIAL.")
    return reasons


def _authority_rows(payload: dict) -> list[dict]:
    ranked = payload.get("ranked_authorities") or []
    rows: list[dict] = []
    for item in ranked:
        quote = str(item.get("direct_quote") or "")
        rows.append(
            {
                "role": item.get("role"),
                "article_or_section": item.get("article_or_section"),
                "document_type": item.get("document_type"),
                "relevance_score": item.get("relevance_score"),
                "direct_quote_preview": quote[:120],
            }
        )
    return rows


def _server_healthy(timeout: float = 2.0) -> bool:
    try:
        req = urllib.request.Request(HEALTH_URL, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _start_uvicorn() -> subprocess.Popen:
    python = sys.executable
    return subprocess.Popen(
        [python, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _ensure_server() -> tuple[str, subprocess.Popen | None]:
    if _server_healthy():
        return "existing", None
    proc = _start_uvicorn()
    for _ in range(90):
        if _server_healthy(timeout=3.0):
            return "started", proc
        time.sleep(1)
    proc.terminate()
    raise RuntimeError("Could not start uvicorn on 127.0.0.1:8000")


def _fetch_report_http(question: str, limit_per_source: int = 8) -> dict:
    params = urllib.parse.urlencode({"question": question, "limit_per_source": limit_per_source})
    url = f"{BASE_URL}{REPORT_PATH}?{params}"
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=600) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _fetch_report_testclient(question: str, limit_per_source: int = 8) -> dict:
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    response = client.get(
        REPORT_PATH,
        params={"question": question, "limit_per_source": limit_per_source},
    )
    if response.status_code != 200:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text[:500]}")
    return response.json()


def _analyze_question(index: int, question: str, limit_per_source: int, mode: str) -> dict:
    if mode == "http":
        payload = _fetch_report_http(question, limit_per_source)
    else:
        payload = _fetch_report_testclient(question, limit_per_source)

    report = _normalize_report(payload)
    score = score_report_completeness(payload)
    gaps = payload.get("retrieval_gaps") or report.get("retrieval_gaps") or {}
    citation = report.get("citation_validation") or {}

    return {
        "index": index,
        "question": question,
        "completeness_score": score,
        "why_not_pass": _explain_completeness(payload, score),
        "ranked_authorities_count": len(payload.get("ranked_authorities") or []),
        "ranked_authorities": _authority_rows(payload),
        "key_contract_violations_count": len(report.get("key_contract_violations") or []),
        "empty_authority_categories": _empty_report_categories(payload),
        "retrieval_gaps_summary": _summarize_retrieval_gaps(gaps),
        "retrieval_gaps": gaps,
        "citation_validation_status": citation.get("status"),
        "citation_validation": citation,
    }


def main() -> int:
    questions = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    limit_per_source = 8

    server_proc: subprocess.Popen | None = None
    mode = "http"
    try:
        server_mode, server_proc = _ensure_server()
        print(f"Using API at {BASE_URL} ({server_mode})")
    except RuntimeError as exc:
        print(f"Warning: {exc}; falling back to TestClient")
        mode = "testclient"

    started = datetime.now(timezone.utc).isoformat()
    entries: list[dict] = []

    for item in questions:
        index = item["index"]
        question = item["question"]
        print(f"\n[{index}/8] Running regression report...")
        try:
            entry = _analyze_question(index, question, limit_per_source, mode)
        except Exception as exc:
            entry = {
                "index": index,
                "question": question,
                "error": str(exc),
                "completeness_score": "FAIL",
                "why_not_pass": [f"Request failed: {exc}"],
            }
        entries.append(entry)
        print(
            f"  completeness={entry.get('completeness_score')} "
            f"ranked={entry.get('ranked_authorities_count', 'n/a')} "
            f"violations={entry.get('key_contract_violations_count', 'n/a')}"
        )

    scorecard = {
        "generated_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "api_mode": mode,
        "base_url": BASE_URL if mode == "http" else "TestClient",
        "limit_per_source": limit_per_source,
        "questions": entries,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(scorecard, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {OUTPUT_PATH}")

    print("\n=== Regression scorecard summary ===")
    for entry in entries:
        idx = entry["index"]
        score = entry.get("completeness_score", "ERROR")
        print(f"\n[{idx}] {score}")
        if entry.get("error"):
            print(f"  error: {entry['error']}")
            continue
        print(f"  ranked_authorities: {entry.get('ranked_authorities_count')}")
        print(f"  key_contract_violations: {entry.get('key_contract_violations_count')}")
        print(f"  empty categories: {entry.get('empty_authority_categories')}")
        print(f"  retrieval_gaps: {entry.get('retrieval_gaps_summary')}")
        print(f"  citation_validation: {entry.get('citation_validation_status')}")
        if score != "PASS":
            for line in entry.get("why_not_pass") or []:
                print(f"  -> {line}")
        for auth in entry.get("ranked_authorities") or []:
            print(
                f"  - {auth.get('role')} | {auth.get('article_or_section')} | "
                f"{auth.get('document_type')} | score={auth.get('relevance_score')} | "
                f"\"{auth.get('direct_quote_preview')}\""
            )

    if server_proc is not None:
        server_proc.terminate()
        server_proc.wait(timeout=10)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
