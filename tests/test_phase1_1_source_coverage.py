"""Phase 1.1 — source coverage, direction, and remedy grounding tests."""

from unittest.mock import MagicMock, patch

from app.services.analysis_service import AnalysisService
from app.services.authority_ranker import AuthorityRanker
from app.services.relevance_utils import (
    build_source_type_backfill_queries,
    compute_actor_action_direction_mismatch,
    compute_direction_penalty,
    dispute_concerns_management_revoking_approved_leave,
    passage_describes_employee_initiated_leave_cancellation,
    passage_expresses_remedy_relief,
)
from app.retrieval_config import DIRECTION_CONTRADICTION_PENALTY


MANAGEMENT_REVOKE_FRAME = {
    "summary": "Management canceled approved leave.",
    "management_actions": ["Management canceled previously approved annual leave."],
    "employee_actions": ["Employee had approved annual leave."],
}


def test_employee_initiated_leave_cancellation_detected():
    text = (
        "Under what circumstances can an employee cancel annual leave that "
        "has already been approved? management should give reasonable "
        "consideration to requests for annual leave cancellation."
    )
    assert passage_describes_employee_initiated_leave_cancellation(text)
    assert dispute_concerns_management_revoking_approved_leave(MANAGEMENT_REVOKE_FRAME)


def test_management_revocation_passage_not_employee_initiated():
    text = (
        "Employees who have annual leave approved are entitled to such "
        "annual leave except in emergency situations."
    )
    assert not passage_describes_employee_initiated_leave_cancellation(text)


def test_actor_action_direction_mismatch_penalizes_employee_cancel_passage():
    employee_cancel = (
        "Question: can an employee cancel annual leave that has already been "
        "approved? Answer: management should give reasonable consideration to "
        "requests for annual leave cancellation."
    )
    management_rule = (
        "Employees who have annual leave approved are entitled to such "
        "annual leave except in emergency situations."
    )
    assert (
        compute_actor_action_direction_mismatch(employee_cancel, MANAGEMENT_REVOKE_FRAME)
        >= DIRECTION_CONTRADICTION_PENALTY
    )
    assert compute_actor_action_direction_mismatch(management_rule, MANAGEMENT_REVOKE_FRAME) == 0.0


def test_direction_penalty_filters_employee_cancel_under_management_revoke_dispute():
    employee_cancel = (
        "An employee may request cancellation of previously approved annual leave."
    )
    penalty = compute_direction_penalty(employee_cancel, MANAGEMENT_REVOKE_FRAME)
    assert penalty >= DIRECTION_CONTRADICTION_PENALTY


def test_passage_expresses_remedy_relief():
    assert passage_expresses_remedy_relief(
        "The appropriate remedy shall be to make the employee whole."
    )
    assert not passage_expresses_remedy_relief(
        "Management should give reasonable consideration to requests for leave."
    )
    assert not passage_expresses_remedy_relief(
        "Employees who have annual leave approved are entitled to such leave."
    )


def test_post_filters_reject_false_remedy_authority(mock_chunk_factory):
    chunk = mock_chunk_factory(
        "The appropriate remedy for a contract violation shall be to make "
        "the employee whole including restoration of canceled leave."
    )
    ranked = AuthorityRanker._apply_post_filters(
        [
            {
                "ref_id": "S1",
                "chunk": chunk,
                "relevance_score": 90,
                "role": "remedy_support",
                "direct_quote": "appropriate remedy for a contract violation shall be to make the employee whole",
            }
        ],
        issue_keywords=["remedy", "leave", "cancel", "management", "whole"],
        dispute_frame=MANAGEMENT_REVOKE_FRAME,
    )
    assert ranked
    assert ranked[0]["role"] == "remedy_support"


def test_remedy_reclassification_helper_procedural():
    from app.services.relevance_utils import passage_expresses_remedy_relief

    text = "Step 1 grievance must be filed within 14 business days of the incident."
    assert not passage_expresses_remedy_relief(text)


def test_post_filters_exclude_employee_initiated_leave_cancellation(mock_chunk_factory):
    chunk = mock_chunk_factory(
        "Question: can an employee cancel annual leave that has already been "
        "approved? requests for annual leave cancellation."
    )
    ranked = AuthorityRanker._apply_post_filters(
        [
            {
                "ref_id": "S1",
                "chunk": chunk,
                "relevance_score": 85,
                "role": "union_supporting",
                "direct_quote": "requests for annual leave cancellation",
            }
        ],
        issue_keywords=["leave", "cancel", "management", "approved"],
        dispute_frame=MANAGEMENT_REVOKE_FRAME,
    )
    assert ranked == []


def test_post_filters_retain_management_entitlement_passage(mock_chunk_factory):
    chunk = mock_chunk_factory(
        "Employees who have annual leave approved are entitled to such "
        "annual leave except in emergency situations."
    )
    ranked = AuthorityRanker._apply_post_filters(
        [
            {
                "ref_id": "S1",
                "chunk": chunk,
                "relevance_score": 92,
                "role": "union_supporting",
                "direct_quote": (
                    "Employees who have annual leave approved are entitled to such "
                    "annual leave except in emergency situations."
                ),
            }
        ],
        issue_keywords=["leave", "cancel", "management", "approved", "emergency"],
        dispute_frame=MANAGEMENT_REVOKE_FRAME,
    )
    assert len(ranked) == 1
    assert ranked[0]["role"] == "union_supporting"


def test_build_source_type_backfill_queries_not_frozen_question():
    issue = {
        "issue_type": "legal",
        "issue": "Schedule change notice requirements",
        "search_queries": ["schedule change notice"],
    }
    contract_queries = build_source_type_backfill_queries(issue, {}, "CONTRACT")
    elm_queries = build_source_type_backfill_queries(issue, {}, "ELM")
    assert contract_queries
    assert elm_queries
    assert not any("Management canceled" in q for q in contract_queries + elm_queries)


def test_source_coverage_audit_summary():
    audit = [
        {
            "source_type": "CONTRACT",
            "searched": True,
            "queries_issued": ["national agreement leave entitlement"],
            "passages_found": 0,
            "passages_retained": 0,
            "disposition": "no_embedding_matches",
        },
        {
            "source_type": "CIM",
            "searched": True,
            "queries_issued": ["union information request"],
            "passages_found": 2,
            "passages_retained": 2,
            "disposition": "retained_in_pool",
        },
    ]
    ranked = [
        {"document_type": "CIM", "page": 468, "chunk_index": 467, "legal_issue": "info"},
    ]
    summary = AnalysisService._summarize_source_coverage_audit(audit, ranked, [])
    by_type = {entry["source_type"]: entry for entry in summary}
    assert by_type["CONTRACT"]["final_disposition"] == "searched_no_matches"
    assert by_type["CIM"]["passages_ranked"] == 1


def test_no_forced_source_diversity_in_audit():
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
    summary = AnalysisService._summarize_source_coverage_audit(audit, [], [])
    assert summary[0]["passages_ranked"] == 0
    assert summary[0]["final_disposition"] == "searched_no_matches"


@patch.object(AuthorityRanker, "_client")
def test_honest_no_remedy_when_only_procedural_language(mock_client, mock_chunk_factory):
    mock_completion = MagicMock()
    mock_completion.choices = [
        MagicMock(
            message=MagicMock(
                content='{"ranked_authorities": [{"ref_id": "S1", "relevance_score": 80, '
                '"role": "remedy_support", "legal_issue": "Leave", "article_or_section": "Art 10", '
                '"authority_type": "Remedy", "direct_quote": "requests for annual leave cancellation", '
                '"why_it_matters": "test"}]}'
            )
        )
    ]
    mock_client.return_value.chat.completions.create.return_value = mock_completion

    chunk = mock_chunk_factory(
        "management should give reasonable consideration to requests for "
        "annual leave cancellation."
    )
    ranked = AuthorityRanker.rank_authorities(
        question="Management canceled approved leave.",
        chunks=[chunk],
        issue_analysis={
            "primary_issue": "Leave cancellation",
            "legal_issues": [{"issue": "Leave cancellation"}],
            "dispute_frame": MANAGEMENT_REVOKE_FRAME,
        },
        issue_keywords=["leave", "cancel", "management"],
    )
    remedy_roles = [item["role"] for item in ranked if item["role"] == "remedy_support"]
    assert remedy_roles == []
