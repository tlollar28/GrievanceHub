from types import SimpleNamespace

from app.services.analysis_service import AnalysisService


def _chunk(source_type: str):
    doc = SimpleNamespace(source_type=source_type)
    return SimpleNamespace(source_document=doc)


def test_missing_elm_not_flagged_when_governing_cim_in_pool():
    issue_analysis = {
        "possible_sources": ["CONTRACT", "CIM", "ELM", "LMOU"],
        "legal_issues": [{"issue_id": "legal_1", "issue": "Discipline standards"}],
        "information_rights_issues": [
            {"issue_id": "information_1", "issue": "Personnel file access"},
        ],
    }
    ranked = [
        {"document_type": "CIM", "legal_issue": "Suspension", "direct_quote": "x"},
    ]
    gaps = AnalysisService._build_retrieval_gaps(
        issue_analysis=issue_analysis,
        ranked_authorities=ranked,
        issue_keywords=["suspension"],
        all_chunks=[_chunk("CIM"), _chunk("CIM")],
        retrieval_gaps_from_krs=[],
        indexed_source_types={"CONTRACT", "CIM", "ELM"},
    )
    assert "ELM" not in gaps["missing_source_types"]
    assert "CONTRACT" not in gaps["missing_source_types"]


def test_lmou_not_missing_when_not_indexed():
    issue_analysis = {
        "possible_sources": ["CONTRACT", "CIM", "LMOU"],
        "local_agreement_issues": [
            {"issue_id": "local_1", "issue": "Local leave procedure"},
        ],
    }
    gaps = AnalysisService._build_retrieval_gaps(
        issue_analysis=issue_analysis,
        ranked_authorities=[{"document_type": "CIM", "legal_issue": "leave"}],
        issue_keywords=["leave"],
        all_chunks=[_chunk("CIM")],
        indexed_source_types={"CONTRACT", "CIM"},
    )
    assert "LMOU" not in gaps["missing_source_types"]
