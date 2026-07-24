"""Deterministic golden-query checks for retrieval routing and thresholds.

These tests do not call OpenAI. They validate domain routing, authority
labeling, and that the agent candidate floor (0.45) does not bypass the
final combined-score gate. A correct no-result outcome is preferred to
irrelevant evidence.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.retrieval_config import (
    MIN_COMBINED_RETRIEVAL_SCORE,
    RETRIEVAL_MIN_CANDIDATE_SIMILARITY,
)
from app.services.relevance_utils import RetrievedChunk, combine_retrieval_score, passes_retrieval_gate
from app.services.retrieval.models import RetrievalRequest
from app.services.retrieval.orchestrator import RetrievalOrchestrator
from tests.test_retrieval_agents import AUTH, EMBEDDING, StubSession


GOLDEN_QUERIES = (
    ("clear_contract", "Article 10 annual leave entitlement under the national agreement", ("contract",)),
    ("clear_supervisor", "How should a supervisor conduct a Step 1 grievance meeting?", ("supervisor_manual",)),
    ("combined", "Contract overtime rules and supervisor attendance control documentation", ("contract", "supervisor_manual")),
    ("article_number", "What does Article 8 say about overtime?", ("contract",)),
    ("grievance_handling", "supervisor guide to handling grievances informal discussion", ("supervisor_manual",)),
    ("step_1_meeting", "Step 1 meeting procedures for supervisors", ("supervisor_manual",)),
    ("attendance_control", "attendance control and time and attendance documentation F-21", ("supervisor_manual",)),
    ("safety", "employee safety responsibilities EL-801 supervisor handbook", ("supervisor_manual",)),
    ("annual_leave", "national agreement approved annual leave may not be cancelled except emergency", ("contract",)),
    ("arbitration", "arbitration award persuasive authority for overtime dispute", ("contract",)),
)


@pytest.mark.parametrize("case_id,query,expected_domains", GOLDEN_QUERIES)
def test_golden_query_domain_routing(case_id, query, expected_domains):
    domains = RetrievalOrchestrator._route_domains("auto", None, query)
    assert tuple(domains) == expected_domains


def test_ambiguous_and_irrelevant_queries_default_to_contract_without_forcing_hits():
    ambiguous = RetrievalOrchestrator._route_domains(
        "auto", None, "What are the requirements?"
    )
    irrelevant = RetrievalOrchestrator._route_domains(
        "auto", None, "recipe for chocolate chip cookies"
    )
    no_evidence = RetrievalOrchestrator._route_domains(
        "auto", None, "zzzxxyyqq nonextant pseudolegal gibberish 99999"
    )
    assert ambiguous == ("contract",)
    assert irrelevant == ("contract",)
    assert no_evidence == ("contract",)


def test_candidate_floor_does_not_bypass_final_combined_gate():
    assert RETRIEVAL_MIN_CANDIDATE_SIMILARITY == 0.45
    assert RETRIEVAL_MIN_CANDIDATE_SIMILARITY < 0.62
    # Similarity above the agent candidate floor but below legacy embedding floor,
    # with no keyword support, must remain rejectable by the shared gate.
    weak_score = combine_retrieval_score(
        embedding_similarity=0.46,
        keyword_overlap=0.0,
        source_type="UNKNOWN",
        is_boilerplate=False,
    )
    retrieved = RetrievedChunk(
        chunk=SimpleNamespace(text="generic text without issue keywords"),
        best_embedding_distance=0.54,
        matched_query_count=1,
        retrieval_metadata={},
    )
    retrieved.combined_score = weak_score
    assert weak_score < MIN_COMBINED_RETRIEVAL_SCORE
    assert not passes_retrieval_gate(
        retrieved,
        weak_score,
        dispute_frame={},
        question="irrelevant cookies",
    )


def test_supervisor_evidence_role_never_presented_as_controlling_contract():
    from pathlib import Path

    from app.services.retrieval import supervisor_manual_agent as module

    source = Path(module.__file__).read_text(encoding="utf-8")
    assert "supervisory_guidance_non_controlling" in source
    assert "controlling_contract_language" not in source


def test_no_evidence_query_returns_empty_results_on_empty_corpus():
    session = StubSession([])
    result = RetrievalOrchestrator(
        embedding_provider=lambda _query: EMBEDDING
    ).retrieve(
        session,
        RetrievalRequest(
            query="zzzxxyyqq nonextant pseudolegal gibberish 99999",
            domain="combined",
        ),
        AUTH,
    )
    assert result.status in {"no_eligible_sources", "no_relevant_results"}
    assert result.results == ()


def test_threshold_decision_unchanged():
    """Keep the candidate floor at 0.45 unless quality evidence changes it."""
    assert RETRIEVAL_MIN_CANDIDATE_SIMILARITY == 0.45
    assert MIN_COMBINED_RETRIEVAL_SCORE == 0.30
