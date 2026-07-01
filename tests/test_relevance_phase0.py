"""Phase-0 relevance utilities (no LLM/DB)."""

from app.retrieval_config import (
    DIRECTION_CONTRADICTION_PENALTY,
    EMBEDDING_FALLBACK_THRESHOLD,
    MIN_COMBINED_RETRIEVAL_SCORE,
    MIN_EMBEDDING_SIMILARITY,
)
from app.services.relevance_utils import (
    RetrievedChunk,
    build_dispute_frame_summary,
    collect_decomposed_issues,
    compute_direction_penalty,
    compute_substantive_score,
    merge_issue_retrieval_pools,
    passes_retrieval_gate,
    score_chunk_for_issue,
)


MULTI_ISSUE_ANALYSIS = {
    "primary_issue": "Management canceled approved leave",
    "legal_issues": [
        {
            "issue": "Cancellation of approved annual leave",
            "search_queries": ["annual leave cancellation"],
        }
    ],
    "remedial_issues": [
        {
            "issue_id": "remedy_custom",
            "issue": "Remedy for canceled leave",
            "search_queries": ["make whole remedy leave"],
        }
    ],
    "timeline_issues": [
        {"issue": "Grievance filing deadline", "search_queries": ["grievance time limit"]}
    ],
    "local_agreement_issues": [
        {"issue": "Local leave procedures", "search_queries": ["LMOU leave"]}
    ],
}


def test_collect_decomposed_issues_from_multi_issue_analysis():
    issues = collect_decomposed_issues(MULTI_ISSUE_ANALYSIS)
    issue_types = {item["issue_type"] for item in issues}
    assert issue_types == {"legal", "remedy", "timeline", "local_agreement"}
    assert len(issues) == 4
    remedy = next(i for i in issues if i["issue_type"] == "remedy")
    assert remedy["issue_id"] == "remedy_custom"
    assert remedy["search_queries"] == ["make whole remedy leave"]


def test_direction_penalty_management_vs_employee():
    dispute_frame = {
        "management_actions": ["canceled approved annual leave"],
        "employee_actions": ["requested steward assistance"],
    }
    management_text = (
        "Supervisor canceled previously approved annual leave citing operational need."
    )
    employee_text = "The employee requested steward assistance and union representation."
    mgmt_penalty = compute_direction_penalty(management_text, dispute_frame)
    employee_penalty = compute_direction_penalty(employee_text, dispute_frame)
    assert employee_penalty >= DIRECTION_CONTRADICTION_PENALTY
    assert employee_penalty > mgmt_penalty


def test_substantive_score_prefers_governing_rule(annual_leave_fixture):
    governing = compute_substantive_score(annual_leave_fixture["governing_passage"]["text"])
    distractor = compute_substantive_score(annual_leave_fixture["distractor_passage"]["text"])
    procedural = compute_substantive_score(
        "Step 1 grievance must be filed within 14 business days of the incident."
    )
    assert governing >= 0.5
    assert governing > procedural
    assert governing >= distractor


def test_merge_issue_retrieval_pools_diversity(mock_chunk_factory):
    def make_retrieved(text, issue_id, score, doc_id=1, page=1, chunk_index=0):
        chunk = mock_chunk_factory(text, chunk_index=chunk_index, page_number=page)
        chunk.source_document_id = doc_id
        retrieved = RetrievedChunk(chunk=chunk, combined_score=score)
        retrieved.retrieval_metadata = {"matched_issue_ids": [issue_id]}
        return retrieved

    pools = {
        "legal_1": [make_retrieved("Annual leave entitlement governing rule", "legal_1", 0.9, chunk_index=1)],
        "remedy_1": [
            make_retrieved("Make whole remedy for canceled leave", "remedy_1", 0.85, doc_id=2, page=2, chunk_index=2)
        ],
    }
    merged, metadata = merge_issue_retrieval_pools(pools, max_total=10)
    assert len(merged) == 2
    assert metadata["total_merged"] == 2
    assert metadata["per_issue_counts"]["legal_1"] == 1
    assert metadata["per_issue_counts"]["remedy_1"] == 1
    matched = set()
    for item in merged:
        matched.update(item.retrieval_metadata.get("matched_issue_ids", []))
    assert matched == {"legal_1", "remedy_1"}


def test_build_dispute_frame_summary():
    frame = {
        "summary": "Leave was canceled after approval.",
        "management_actions": ["Canceled approved leave"],
        "union_concerns": ["Whether cancellation was permitted"],
        "information_sought": ["Written approval records"],
    }
    summary = build_dispute_frame_summary(frame)
    assert "Dispute summary: Leave was canceled after approval." in summary
    assert "Management actions described: Canceled approved leave" in summary
    assert "Information or records sought: Written approval records" in summary


def test_score_chunk_for_issue_applies_direction_penalty(mock_chunk_factory):
    chunk = mock_chunk_factory(
        "The employee filed a grievance after management canceled approved leave.",
        chunk_index=10,
        page_number=5,
    )
    chunk.source_document_id = 3
    dispute_frame = {
        "management_actions": ["canceled approved leave"],
        "employee_actions": [],
    }
    issue = {"issue_id": "legal_1", "issue": "leave cancellation"}
    keywords = ["annual", "leave", "cancel", "approved", "management"]

    low_penalty_frame = {
        "management_actions": ["canceled approved leave"],
        "employee_actions": ["filed grievance"],
    }
    aligned = RetrievedChunk(chunk=chunk, best_embedding_distance=0.2)
    score_aligned = score_chunk_for_issue(
        aligned,
        issue_keywords=keywords,
        dispute_frame=low_penalty_frame,
        issue=issue,
    )
    meta_aligned = aligned.retrieval_metadata.get("direction_penalty", 0.0)

    misaligned = RetrievedChunk(chunk=chunk, best_embedding_distance=0.2)
    score_misaligned = score_chunk_for_issue(
        misaligned,
        issue_keywords=keywords,
        dispute_frame=dispute_frame,
        issue=issue,
    )
    meta_misaligned = misaligned.retrieval_metadata.get("direction_penalty", 0.0)

    assert meta_misaligned >= meta_aligned
    assert score_misaligned <= score_aligned

def test_passes_retrieval_gate_embedding_fallback(mock_chunk_factory):
    substantive = (
        "Employees shall be entitled to use annual leave as scheduled unless "
        "management cancels with just cause and proper notice."
    )
    chunk = mock_chunk_factory(substantive, chunk_index=20, page_number=3)
    retrieved = RetrievedChunk(chunk=chunk, best_embedding_distance=0.30, matched_query_count=2)
    low_combined = MIN_COMBINED_RETRIEVAL_SCORE - 0.05
    assert passes_retrieval_gate(retrieved, low_combined) is True

    boilerplate_chunk = mock_chunk_factory("Table of contents article 1 article 2", chunk_index=21)
    boilerplate = RetrievedChunk(
        chunk=boilerplate_chunk,
        best_embedding_distance=0.20,
        matched_query_count=2,
    )
    assert passes_retrieval_gate(boilerplate, low_combined) is False


def test_direction_penalty_leave_policy_chunk_not_overpenalized():
    dispute_frame = {
        "management_actions": ["canceled approved annual leave"],
        "employee_actions": ["requested annual leave in writing"],
    }
    leave_policy = (
        "Annual leave requests shall be submitted in writing. Approved leave "
        "remains on the schedule unless management cancels for operational need."
    )
    penalty = compute_direction_penalty(leave_policy, dispute_frame)
    assert penalty < DIRECTION_CONTRADICTION_PENALTY


def test_global_keywords_boost_narrow_issue_keywords(mock_chunk_factory):
    chunk = mock_chunk_factory(
        "Supervisor canceled previously approved annual leave without explanation.",
        chunk_index=30,
        page_number=8,
    )
    chunk.source_document_id = 9
    narrow_keywords = ["cancellation"]
    global_keywords = ["annual", "leave", "approved", "cancel", "supervisor", "management"]
    dispute_frame = {
        "management_actions": ["canceled approved annual leave"],
        "employee_actions": [],
    }
    issue = {"issue_id": "legal_1", "issue": "leave cancellation"}

    narrow_only = RetrievedChunk(chunk=chunk, best_embedding_distance=0.25)
    narrow_score = score_chunk_for_issue(
        narrow_only,
        issue_keywords=narrow_keywords,
        dispute_frame=dispute_frame,
        issue=issue,
    )

    with_global = RetrievedChunk(chunk=chunk, best_embedding_distance=0.25)
    boosted_score = score_chunk_for_issue(
        with_global,
        issue_keywords=narrow_keywords,
        dispute_frame=dispute_frame,
        issue=issue,
        global_keywords=global_keywords,
    )

    assert boosted_score >= narrow_score
    assert with_global.keyword_overlap >= narrow_only.keyword_overlap

def test_build_issue_type_backfill_queries_information_rights():
    from app.services.relevance_utils import build_issue_type_backfill_queries

    issue = {
        "issue_id": "information_1",
        "issue_type": "information_rights",
        "issue": "Union access to records",
    }
    queries = build_issue_type_backfill_queries(issue)
    assert queries
    assert any("union right to information" in q.lower() for q in queries)
    assert any("Union access to records" in q for q in queries)
    assert not any("Q1" in q or "Q6" in q or "Q7" in q for q in queries)


def test_build_issue_type_backfill_queries_skips_unknown_type():
    from app.services.relevance_utils import build_issue_type_backfill_queries

    assert build_issue_type_backfill_queries({"issue_type": "unknown"}) == []


def test_append_passing_chunks_to_pool_tags_issue_and_skips_duplicates(mock_chunk_factory):
    from app.services.knowledge_retrieval_service import KnowledgeRetrievalService
    from app.retrieval_config import MIN_COMBINED_RETRIEVAL_SCORE

    chunk = mock_chunk_factory(
        "The Employer shall furnish information to the union upon written request.",
        chunk_index=5,
        page_number=2,
    )
    chunk.source_document_id = 11
    issue = {
        "issue_id": "information_1",
        "issue_type": "information_rights",
        "issue": "Union information rights",
    }
    retrieved = RetrievedChunk(chunk=chunk, best_embedding_distance=0.2)
    retrieved.retrieval_metadata = {"matched_issue_ids": ["information_1"]}
    chunk_map = {(11, 2, 5): retrieved}
    pool: list[RetrievedChunk] = []

    KnowledgeRetrievalService._append_passing_chunks_to_pool(
        chunk_map,
        pool,
        issue_keywords_for_issue=["union", "information", "records", "request"],
        dispute_frame={"union_concerns": ["information access"]},
        issue=issue,
        global_keywords=["union", "information"],
    )

    assert len(pool) == 1
    assert pool[0].retrieval_metadata.get("matched_issue_ids") == ["information_1"]
    assert pool[0].combined_score >= MIN_COMBINED_RETRIEVAL_SCORE

    KnowledgeRetrievalService._append_passing_chunks_to_pool(
        chunk_map,
        pool,
        issue_keywords_for_issue=["union", "information"],
        dispute_frame={},
        issue=issue,
        global_keywords=["union"],
    )
    assert len(pool) == 1


def test_backfill_empty_issue_pools_skips_non_empty_and_unindexed_lmou(mock_chunk_factory):
    from app.services.knowledge_retrieval_service import KnowledgeRetrievalService

    existing = RetrievedChunk(
        chunk=mock_chunk_factory("Existing governing rule text.", chunk_index=1),
        combined_score=0.9,
    )
    issue_pools = {"legal_1": [existing], "local_1": []}
    decomposed = [
        {"issue_id": "legal_1", "issue_type": "legal", "issue": "Legal issue"},
        {"issue_id": "local_1", "issue_type": "local_agreement", "issue": "Local MOU"},
        {"issue_id": "info_1", "issue_type": "information_rights", "issue": "Info rights"},
    ]

    class FakeDB:
        pass

    calls = {"count": 0}

    def fake_retrieve(db, queries, limit_per_source, issue=None, allowed_source_types=None):
        calls["count"] += 1
        return {}

    original = KnowledgeRetrievalService._retrieve_queries_into_pool
    KnowledgeRetrievalService._retrieve_queries_into_pool = staticmethod(fake_retrieve)
    try:
        KnowledgeRetrievalService._backfill_empty_issue_pools(
            db=FakeDB(),
            issue_pools=issue_pools,
            decomposed_issues=decomposed,
            dispute_frame={},
            issue_keywords=["union"],
            limit_per_source=3,
            indexed_source_types={"CONTRACT", "CIM", "ELM"},
        )
    finally:
        KnowledgeRetrievalService._retrieve_queries_into_pool = original

    assert calls["count"] == 1
    assert issue_pools["legal_1"] == [existing]

