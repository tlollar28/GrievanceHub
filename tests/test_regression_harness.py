"""Regression scoring harness (no live API key for unit scoring)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "regression_questions.json"
REGRESSION_QUESTIONS = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _normalize_report(report_dict: dict) -> dict:
    if not report_dict:
        return {}
    inner = report_dict.get("report")
    if isinstance(inner, dict) and inner.get("report_title"):
        merged = {**report_dict, **inner}
    else:
        merged = dict(report_dict)
    return merged


def score_report_completeness(report_dict: dict) -> str:
    """Return PASS, PARTIAL, or FAIL for regression report quality."""
    report = _normalize_report(report_dict)
    if not report:
        return "FAIL"

    ranked = report.get("ranked_authorities") or []
    violations = report.get("key_contract_violations") or []
    retrieval_gaps = report.get("retrieval_gaps") or {}
    citation = report.get("citation_validation") or {}

    if not ranked:
        return "FAIL"

    citation_status = str(citation.get("status") or "").lower()
    if citation_status in {"failed", "fail", "needs review"}:
        return "FAIL"

    missing_sources = retrieval_gaps.get("missing_source_types") or []
    unresolved = retrieval_gaps.get("issues_without_supporting_authority") or []

    has_substance = bool(violations) or len(ranked) >= 2
    gap_burden = len(missing_sources) + len(unresolved)

    if has_substance and gap_burden == 0 and citation_status in {"passed", "pass", ""}:
        return "PASS"

    if has_substance or (ranked and citation_status in {"passed", "pass"}):
        return "PARTIAL"

    return "FAIL"


def test_regression_questions_fixture_has_eight_items():
    assert len(REGRESSION_QUESTIONS) == 8
    assert all("index" in item and "question" in item for item in REGRESSION_QUESTIONS)


def test_score_report_completeness_empty_is_fail():
    assert score_report_completeness({}) == "FAIL"
    assert score_report_completeness({"ranked_authorities": []}) == "FAIL"


def test_score_report_completeness_full_is_pass():
    report = {
        "ranked_authorities": [
            {"document_type": "CIM", "relevance_score": 90},
            {"document_type": "CONTRACT", "relevance_score": 88},
        ],
        "key_contract_violations": [{"direct_quote": "Employees shall be entitled to annual leave."}],
        "retrieval_gaps": {"missing_source_types": [], "issues_without_supporting_authority": []},
        "citation_validation": {"status": "Passed"},
    }
    assert score_report_completeness(report) == "PASS"


def test_score_report_completeness_partial_with_gaps():
    report = {
        "ranked_authorities": [{"document_type": "CIM", "relevance_score": 80}],
        "key_contract_violations": [{"direct_quote": "Grounded quote."}],
        "retrieval_gaps": {"missing_source_types": ["LMOU"], "issues_without_supporting_authority": []},
        "citation_validation": {"status": "Passed"},
    }
    assert score_report_completeness(report) == "PARTIAL"


@pytest.mark.integration
@pytest.mark.skipif(os.environ.get("RUN_REGRESSION") != "1", reason="Set RUN_REGRESSION=1 to run live DB regression")
def test_regression_live_pipeline_smoke():
    """Live pipeline against real DB; set RUN_REGRESSION=1 to enable."""
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    scorecard: list[tuple[int, str, str]] = []
    api_key = os.environ.get("GRIEVANCEHUB_API_KEY")
    assert api_key, "GRIEVANCEHUB_API_KEY must be set for live regression"
    auth_headers = {"Authorization": f"Bearer {api_key}"}

    for item in REGRESSION_QUESTIONS:
        index = item["index"]
        question = item["question"]
        response = client.get(
            "/sources/report/",
            params={"question": question, "limit_per_source": 3},
            headers=auth_headers,
        )
        assert response.status_code == 200, (
            f"question {index} failed: HTTP {response.status_code} {response.text[:500]}"
        )
        payload = response.json()
        score = score_report_completeness(payload)
        scorecard.append((index, score, question[:60]))

    print("\n=== Regression scorecard ===")
    for index, score, preview in scorecard:
        print(f"  [{index}] {score}: {preview}...")
    print("============================\n")

    assert scorecard

