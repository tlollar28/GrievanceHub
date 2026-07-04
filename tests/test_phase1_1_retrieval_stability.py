"""Phase 1.1 retrieval stability — direction, backfill, and source-gap tests."""

from unittest.mock import MagicMock, patch

from app.retrieval_config import DIRECTION_CONTRADICTION_PENALTY
from app.services.analysis_service import AnalysisService
from app.services.authority_ranker import AuthorityRanker
from app.services.relevance_utils import (
    RetrievedChunk,
    build_source_type_backfill_queries,
    chunk_fails_actor_direction_gate,
    compute_actor_action_direction_mismatch,
    dispute_concerns_management_revoking_approved_leave,
    passage_describes_employee_initiated_leave_cancellation,
    passes_retrieval_gate,
)
from app.services.report_export.text_formatter import format_source_coverage_caveat


FROZEN_QUESTION = (
    "Management canceled previously approved annual leave without explanation and "
    "ignored the union's information request. What rules apply and what remedy is "
    "appropriate?"
)

WEAK_DISPUTE_FRAME = {
    "summary": "Union information request ignored.",
    "management_actions": ["Failed to respond to union information request."],
}

MANAGEMENT_REVOKE_FRAME = {
    "summary": "Management canceled approved leave.",
    "management_actions": ["Management canceled previously approved annual leave."],
}

P137_EMPLOYEE_CANCEL = (
    "Management should give reasonable consideration to requests for "
    "annual leave cancellation."
)

CONTRACT_10_5 = (
    "All advance commitments for granting annual leave must be honored "
    "except in serious emergency situations."
)

CIM_31_INFO = (
    "Upon the written request of the Union, the Employer will furnish "
    "such information as may be necessary for the Union to perform its duties."
)

P137_REJECT_SIGNALS = (
    "requests for annual leave cancellation",
    "can an employee cancel",
    "employee cancel annual leave",
)


def test_management_revocation_detected_from_question_when_frame_weak():
    assert not dispute_concerns_management_revoking_approved_leave(WEAK_DISPUTE_FRAME)
    assert dispute_concerns_management_revoking_approved_leave(
        WEAK_DISPUTE_FRAME,
        FROZEN_QUESTION,
    )


def test_p137_rejected_under_weak_frame_with_question():
    assert passage_describes_employee_initiated_leave_cancellation(P137_EMPLOYEE_CANCEL)
    assert (
        compute_actor_action_direction_mismatch(
            P137_EMPLOYEE_CANCEL,
            WEAK_DISPUTE_FRAME,
            FROZEN_QUESTION,
        )
        >= DIRECTION_CONTRADICTION_PENALTY
    )


def test_procedural_role_does_not_bypass_direction_filter(mock_chunk_factory):
    chunk = mock_chunk_factory(P137_EMPLOYEE_CANCEL)
    ranked = AuthorityRanker._apply_post_filters(
        [
            {
                "ref_id": "S1",
                "chunk": chunk,
                "relevance_score": 88,
                "role": "procedural_requirement",
                "direct_quote": "requests for annual leave cancellation",
            }
        ],
        issue_keywords=["leave", "cancel", "management", "approved"],
        dispute_frame=WEAK_DISPUTE_FRAME,
        question=FROZEN_QUESTION,
    )
    assert ranked == []


def test_management_limiting_role_does_not_bypass_direction_filter(mock_chunk_factory):
    chunk = mock_chunk_factory(P137_EMPLOYEE_CANCEL)
    ranked = AuthorityRanker._apply_post_filters(
        [
            {
                "ref_id": "S1",
                "chunk": chunk,
                "relevance_score": 90,
                "role": "management_limiting",
                "direct_quote": "requests for annual leave cancellation",
            }
        ],
        issue_keywords=["leave", "cancel", "management", "approved"],
        dispute_frame=WEAK_DISPUTE_FRAME,
        question=FROZEN_QUESTION,
    )
    assert ranked == []


def test_contract_entitlement_passage_retained_with_question(mock_chunk_factory):
    chunk = mock_chunk_factory(CONTRACT_10_5)
    ranked = AuthorityRanker._apply_post_filters(
        [
            {
                "ref_id": "S1",
                "chunk": chunk,
                "relevance_score": 95,
                "role": "union_supporting",
                "direct_quote": CONTRACT_10_5,
            }
        ],
        issue_keywords=["leave", "annual", "approved", "commitment", "emergency"],
        dispute_frame=WEAK_DISPUTE_FRAME,
        question=FROZEN_QUESTION,
    )
    assert len(ranked) == 1
    assert ranked[0]["role"] == "union_supporting"


def test_cim_information_passage_retained(mock_chunk_factory):
    chunk = mock_chunk_factory(CIM_31_INFO)
    ranked = AuthorityRanker._apply_post_filters(
        [
            {
                "ref_id": "S1",
                "chunk": chunk,
                "relevance_score": 92,
                "role": "information_right",
                "direct_quote": CIM_31_INFO[:120],
            }
        ],
        issue_keywords=["information", "union", "request", "furnish"],
        dispute_frame=WEAK_DISPUTE_FRAME,
        question=FROZEN_QUESTION,
    )
    assert len(ranked) == 1
    assert ranked[0]["role"] == "information_right"


def test_embedding_fallback_rejects_direction_mismatch(mock_chunk_factory):
    chunk = mock_chunk_factory(P137_EMPLOYEE_CANCEL)
    retrieved = RetrievedChunk(
        chunk=chunk,
        best_embedding_distance=0.25,
        matched_query_count=2,
    )
    assert chunk_fails_actor_direction_gate(
        P137_EMPLOYEE_CANCEL,
        WEAK_DISPUTE_FRAME,
        FROZEN_QUESTION,
    )
    assert not passes_retrieval_gate(
        retrieved,
        0.1,
        dispute_frame=WEAK_DISPUTE_FRAME,
        question=FROZEN_QUESTION,
    )


def test_dispute_aware_contract_backfill_queries():
    issue = {
        "issue_type": "legal",
        "issue": "Management revocation of approved annual leave",
    }
    queries = build_source_type_backfill_queries(
        issue,
        WEAK_DISPUTE_FRAME,
        "CONTRACT",
        question=FROZEN_QUESTION,
    )
    joined = " ".join(queries).lower()
    assert "advance commitments" in joined or "annual leave" in joined
    assert not any("Management canceled" in q for q in queries)


def test_source_gap_wording_when_contract_ranked():
    entry = {
        "source_type": "CONTRACT",
        "passages_found": 0,
        "passages_retained_in_pool": 0,
        "passages_ranked": 1,
    }
    caveat = format_source_coverage_caveat(entry)
    assert "no relevant passage was located" not in caveat.lower()
    assert "included" in caveat.lower()


def test_source_gap_wording_when_contract_not_ranked():
    entry = {
        "source_type": "CONTRACT",
        "passages_found": 0,
        "passages_retained_in_pool": 0,
        "passages_ranked": 0,
    }
    caveat = format_source_coverage_caveat(entry)
    assert "no relevant passage was located" in caveat.lower()


def test_audit_summary_reflects_ranked_contract():
    audit = [
        {
            "source_type": "CONTRACT",
            "searched": True,
            "queries_issued": ["contract leave"],
            "passages_found": 0,
            "passages_retained": 0,
            "disposition": "no_embedding_matches",
        }
    ]
    ranked = [
        {
            "document_type": "CONTRACT",
            "page": 44,
            "chunk_index": 43,
            "legal_issue": "Leave commitment",
        }
    ]
    summary = AnalysisService._summarize_source_coverage_audit(audit, ranked, [])
    contract = next(item for item in summary if item["source_type"] == "CONTRACT")
    assert contract["passages_ranked"] == 1
    assert contract["final_disposition"] == "authorities_ranked"


def test_ensure_management_revocation_promotes_contract_from_pool(mock_chunk_factory):
    contract_chunk = mock_chunk_factory(
        CONTRACT_10_5,
        source_type="CONTRACT",
        page_number=44,
    )
    contract_chunk.retrieval_metadata = {"combined_score": 0.82}
    ranked = [
        {
            "ref_id": "S1",
            "chunk": mock_chunk_factory(CIM_31_INFO, source_type="CIM", page_number=468),
            "document_type": "CIM",
            "relevance_score": 90,
            "role": "information_right",
            "direct_quote": (
                "Upon the written request of the Union, the Employer will furnish "
                "such information"
            ),
        }
    ]
    result = AuthorityRanker._ensure_management_revocation_authority_mix(
        ranked,
        [contract_chunk],
        issue_keywords=["leave", "annual", "approved", "commitment", "information", "union"],
        dispute_frame=WEAK_DISPUTE_FRAME,
        question=FROZEN_QUESTION,
        primary_issue="Leave and information",
    )
    assert any(
        str(item.get("document_type") or "").upper() == "CONTRACT" for item in result
    )



@patch.object(AuthorityRanker, "_client")
def test_ranker_excludes_p137_even_when_llm_labels_procedural(
    mock_client,
    mock_chunk_factory,
):
    mock_completion = MagicMock()
    mock_completion.choices = [
        MagicMock(
            message=MagicMock(
                content=(
                    '{"ranked_authorities": ['
                    '{"ref_id": "S1", "relevance_score": 85, '
                    '"role": "procedural_requirement", "legal_issue": "Leave", '
                    '"article_or_section": "Article 10", '
                    '"authority_type": "Procedural", '
                    '"direct_quote": "requests for annual leave cancellation", '
                    '"why_it_matters": "test"}'
                    "]}"
                )
            )
        )
    ]
    mock_client.return_value.chat.completions.create.return_value = mock_completion

    chunk = mock_chunk_factory(P137_EMPLOYEE_CANCEL)
    ranked = AuthorityRanker.rank_authorities(
        question=FROZEN_QUESTION,
        chunks=[chunk],
        issue_analysis={
            "primary_issue": "Leave and information",
            "legal_issues": [{"issue": "Leave cancellation"}],
            "dispute_frame": WEAK_DISPUTE_FRAME,
        },
        issue_keywords=["leave", "cancel", "management", "information"],
    )
    assert ranked == []
