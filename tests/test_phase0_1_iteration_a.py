"""Phase 0.1 Iteration A — scope, disclosure, and topic-mismatch tests."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.analysis_service import AnalysisService
from app.services.authority_ranker import AuthorityRanker
from app.services.narrative_generator import NarrativeGenerator
from app.services.relevance_utils import (
    compute_authority_topics_unavailable,
    compute_topic_mismatch_penalty,
    compute_unindexed_sources_requested,
    is_decomposed_issue_in_scope,
    question_requests_investigatory_representation,
    ranked_authorities_cover_investigatory_representation,
)


def _chunk(source_type: str):
    doc = SimpleNamespace(source_type=source_type)
    return SimpleNamespace(source_document=doc)


# --- A1: timeline issue scope ---


def test_timeline_issue_out_of_scope_for_discipline_question():
    question = (
        "Management issued a seven-day suspension for failure to follow instructions. "
        "What contractual standards govern just cause?"
    )
    issue = {
        "issue_type": "timeline",
        "issue": "Grievance filing deadlines",
    }
    assert is_decomposed_issue_in_scope(question, issue) is False


def test_timeline_issue_in_scope_when_question_mentions_untimely():
    question = (
        "Management argues the grievance filed on May 20 was untimely. "
        "What rules govern the filing deadline?"
    )
    issue = {
        "issue_type": "timeline",
        "issue": "Grievance filing deadlines",
    }
    assert is_decomposed_issue_in_scope(question, issue) is True


def test_build_retrieval_gaps_no_false_timeline_unresolved():
    issue_analysis = {
        "primary_issue": "Just-cause suspension standards",
        "possible_sources": ["CIM"],
        "legal_issues": [{"issue_id": "legal_1", "issue": "Just cause"}],
    }
    ranked = [
        {
            "document_type": "CIM",
            "legal_issue": "Just cause discipline",
            "direct_quote": "No employee may be disciplined except for just cause.",
        }
    ]
    gaps_from_krs = [
        {
            "issue_type": "timeline",
            "issue": "Grievance filing deadlines",
            "reason": "no_ranked_authority_for_issue",
        }
    ]
    question = (
        "What contractual standards should be examined when determining "
        "whether the discipline meets the just-cause requirement?"
    )
    gaps = AnalysisService._build_retrieval_gaps(
        issue_analysis=issue_analysis,
        ranked_authorities=ranked,
        issue_keywords=["just", "cause", "discipline"],
        all_chunks=[_chunk("CIM")],
        retrieval_gaps_from_krs=gaps_from_krs,
        indexed_source_types={"CIM"},
        question=question,
    )
    assert gaps["issues_without_supporting_authority"] == []


def test_ensure_multi_issue_coverage_skips_out_of_scope_timeline():
    decomposed = [
        {
            "issue_id": "timeline_1",
            "issue_type": "timeline",
            "issue": "Grievance filing deadlines",
        }
    ]
    gaps = AuthorityRanker._ensure_multi_issue_coverage(
        ranked=[],
        decomposed_issues=decomposed,
        chunks=[],
        question="What just-cause standards apply to this suspension?",
        primary_issue="Just-cause suspension",
    )
    assert gaps == []


# --- A2: LMOU unindexed disclosure ---


def test_lmou_requested_but_unindexed_disclosed():
    question = (
        "Which parts of the issue may require review of the applicable LMOU "
        "or established local practice?"
    )
    issue_analysis = {
        "primary_issue": "Holiday scheduling",
        "local_agreement_issues": [
            {"issue_id": "local_1", "issue": "Local holiday posting practice"},
        ],
    }
    requested = compute_unindexed_sources_requested(
        question=question,
        issue_analysis=issue_analysis,
        indexed_source_types={"CONTRACT", "CIM"},
    )
    assert requested == ["LMOU"]


def test_lmou_not_in_missing_source_types_when_unindexed():
    issue_analysis = {
        "possible_sources": ["CONTRACT", "CIM", "LMOU"],
        "local_agreement_issues": [
            {"issue_id": "local_1", "issue": "Local leave procedure"},
        ],
    }
    gaps = AnalysisService._build_retrieval_gaps(
        issue_analysis=issue_analysis,
        ranked_authorities=[{"document_type": "CIM", "legal_issue": "leave"}],
        issue_keywords=["leave", "lmou"],
        all_chunks=[_chunk("CIM")],
        indexed_source_types={"CONTRACT", "CIM"},
        question="Review applicable LMOU provisions for leave.",
    )
    assert "LMOU" not in gaps["missing_source_types"]
    assert gaps["unindexed_sources_requested"] == ["LMOU"]


def test_limitations_mention_unindexed_lmou():
    retrieval_gaps = {
        "unindexed_sources_requested": ["LMOU"],
        "missing_source_types": [],
        "issues_without_supporting_authority": [],
    }
    limitations = NarrativeGenerator.build_limitations(
        legal_issues={},
        issue_analysis={"primary_issue": "Holiday schedule"},
        retrieval_gaps=retrieval_gaps,
        known_facts=[],
    )
    assert any("not currently indexed" in c for c in limitations["caveats"])


def test_past_practice_question_triggers_lmou_disclosure():
    question = (
        "Management ended a seniority-based work selection procedure without notice. "
        "What evidence is needed to establish a binding past practice, and what "
        "source gaps should be identified?"
    )
    requested = compute_unindexed_sources_requested(
        question=question,
        issue_analysis={"primary_issue": "Change in work assignment past practice"},
        indexed_source_types={"CONTRACT", "CIM"},
    )
    assert requested == ["LMOU"]


def test_build_retrieval_gaps_lmou_disclosed_for_established_practice_question():
    question = (
        "For several years, management allowed Mail Handlers to select recurring "
        "work assignments by seniority. Management ended the procedure without "
        "notice. What evidence is needed to establish a binding past practice, "
        "and what source gaps should be identified?"
    )
    gaps = AnalysisService._build_retrieval_gaps(
        issue_analysis={
            "primary_issue": "Change in work assignment procedure",
            "legal_issues": [{"issue_id": "legal_1", "issue": "Past practice"}],
        },
        ranked_authorities=[
            {
                "document_type": "CIM",
                "legal_issue": "Past practice",
                "direct_quote": "If a binding past practice clarifies a contract provision.",
            }
        ],
        issue_keywords=["past", "practice", "seniority"],
        all_chunks=[_chunk("CIM")],
        indexed_source_types={"CONTRACT", "CIM"},
        question=question,
    )
    assert gaps["unindexed_sources_requested"] == ["LMOU"]
    assert "LMOU" not in gaps["missing_source_types"]


# --- A3: investigatory representation disclosure ---


def test_representation_topic_unavailable_when_not_ranked():
    question = (
        "A supervisor questioned a Mail Handler about alleged misconduct. "
        "The employee requested a Union representative, but the supervisor "
        "continued questioning alone."
    )
    ranked = [
        {
            "legal_issue": "Information rights",
            "direct_quote": "Upon written request the Employer will furnish information.",
            "why_it_matters": "Article 31 information.",
        }
    ]
    assert question_requests_investigatory_representation(question)
    assert not ranked_authorities_cover_investigatory_representation(ranked)
    unavailable = compute_authority_topics_unavailable(question, ranked)
    assert unavailable == ["investigatory_union_representation"]


def test_inspection_service_not_counted_as_supervisor_representation():
    ranked = [
        {
            "legal_issue": "Inspection Service interrogation",
            "direct_quote": (
                "If an employee requests a steward during an interrogation "
                "by the Inspection Service, such request will be granted."
            ),
            "why_it_matters": "Article 17 only.",
        }
    ]
    question = (
        "A supervisor questioned a Mail Handler about misconduct and refused "
        "a Union representative."
    )
    assert not ranked_authorities_cover_investigatory_representation(ranked)
    assert compute_authority_topics_unavailable(question, ranked) == [
        "investigatory_union_representation"
    ]


def test_legal_issue_label_alone_does_not_satisfy_representation_coverage():
    """LLM legal_issue text must not suppress unavailable-authority disclosure."""
    ranked = [
        {
            "legal_issue": "Employee's right to union representation during questioning",
            "direct_quote": (
                "For minor offenses by an employee, management has a responsibility "
                "to discuss such matters with the employee."
            ),
            "why_it_matters": "Minor discussion only.",
        }
    ]
    question = (
        "A supervisor questioned a Mail Handler about alleged misconduct. "
        "The employee requested a Union representative, but the supervisor "
        "continued questioning alone."
    )
    assert not ranked_authorities_cover_investigatory_representation(ranked)
    assert compute_authority_topics_unavailable(question, ranked) == [
        "investigatory_union_representation"
    ]


def test_build_retrieval_gaps_includes_unavailable_representation_topic():
    question = (
        "A supervisor questioned a Mail Handler about alleged misconduct. "
        "The employee requested a Union representative, but the supervisor "
        "continued questioning alone."
    )
    gaps = AnalysisService._build_retrieval_gaps(
        issue_analysis={"primary_issue": "Union representation during questioning"},
        ranked_authorities=[
            {
                "document_type": "CIM",
                "legal_issue": "Union representation during questioning",
                "direct_quote": "For minor offenses management may discuss matters privately.",
            }
        ],
        issue_keywords=["union", "representative", "questioning"],
        all_chunks=[_chunk("CIM")],
        indexed_source_types={"CIM"},
        question=question,
    )
    assert gaps["authority_topics_unavailable_in_index"] == [
        "investigatory_union_representation"
    ]


def test_limitations_include_unavailable_topic_caveat():
    retrieval_gaps = {
        "authority_topics_unavailable_in_index": [
            "investigatory_union_representation"
        ],
        "missing_source_types": [],
        "issues_without_supporting_authority": [],
    }
    limitations = NarrativeGenerator.build_limitations(
        legal_issues={},
        issue_analysis={},
        retrieval_gaps=retrieval_gaps,
        known_facts=[],
    )
    joined = " ".join(limitations["caveats"]).lower()
    assert "weingarten" in joined or "investigatory" in joined


# --- A4: topic mismatch filtering ---


def test_excessing_chunk_penalized_for_higher_level_question():
    chunk = (
        "Mail handlers will be excessed from the losing installation by "
        "inverse seniority in their craft by status."
    )
    question = (
        "A Level 4 Mail Handler performed higher-level duties but was paid "
        "at the regular level."
    )
    penalty = compute_topic_mismatch_penalty(
        chunk,
        question=question,
        primary_issue="Higher-level pay entitlement",
    )
    assert penalty >= 0.75


def test_driving_privilege_filtered_for_discipline_question(mock_chunk_factory):
    chunk = mock_chunk_factory(
        "Every reasonable effort will be made to reassign such employee to non-driving duties."
    )
    ranked = AuthorityRanker._apply_post_filters(
        [
            {
                "ref_id": "S1",
                "chunk": chunk,
                "relevance_score": 85,
                "role": "background_only",
                "direct_quote": (
                    "Every reasonable effort will be made to reassign such "
                    "employee to non-driving duties."
                ),
            }
        ],
        issue_keywords=["just", "cause", "discipline", "suspension"],
        question=(
            "What contractual standards govern whether discipline meets "
            "the just-cause requirement?"
        ),
        primary_issue="Just-cause suspension standards",
    )
    assert ranked == []


def test_background_only_excluded_when_substantive_exists():
    ranked = [
        {"role": "union_supporting", "relevance_score": 95},
        {"role": "union_supporting", "relevance_score": 90},
        {"role": "background_only", "relevance_score": 85},
    ]
    exported = AuthorityRanker._exclude_background_when_substantive(ranked)
    assert len(exported) == 2
    assert all(item["role"] != "background_only" for item in exported)


def test_coverage_floor_skips_topic_mismatch_candidate(mock_chunk_factory):
    excess_chunk = mock_chunk_factory(
        "When excessing occurs in a craft, the sole criteria for selecting "
        "employees to be excessed is seniority.",
        chunk_index=1,
    )
    excess_chunk.retrieval_metadata = {
        "matched_issue_ids": ["legal_1"],
        "combined_score": 0.82,
    }

    promoted = AuthorityRanker._promote_per_issue_coverage_floor(
        [],
        [
            {
                "issue_id": "legal_1",
                "issue_type": "legal",
                "issue": "Temporary section reassignment",
            }
        ],
        [excess_chunk],
        issue_keywords=["temporary", "reassignment", "section"],
        dispute_frame={},
        max_authorities=5,
        question=(
            "Management temporarily moved a Mail Handler to another section "
            "for three weeks."
        ),
        primary_issue="Temporary reassignment impact on overtime",
    )
    assert promoted == []


@patch.object(AuthorityRanker, "_client")
def test_no_weingarten_invention_in_ranked_output(mock_client, mock_chunk_factory):
    """Ranker must not inject synthetic Weingarten text."""
    chunk = mock_chunk_factory(
        "For minor offenses management may discuss matters with the employee."
    )
    mock_completion = MagicMock()
    mock_completion.choices = [
        MagicMock(
            message=MagicMock(
                content=(
                    '{"ranked_authorities": [{"ref_id": "S1", "relevance_score": 90, '
                    '"role": "union_supporting", "legal_issue": "Weingarten rights", '
                    '"article_or_section": "Unknown", "authority_type": "Union-Supporting", '
                    '"direct_quote": "Weingarten rights require union representation.", '
                    '"why_it_matters": "Invented."}]}'
                )
            )
        )
    ]
    mock_client.return_value.chat.completions.create.return_value = mock_completion

    ranked = AuthorityRanker.rank_authorities(
        question="Employee requested union rep during supervisor questioning.",
        chunks=[chunk],
        issue_analysis={
            "primary_issue": "Union representation during questioning",
            "legal_issues": [],
        },
        issue_keywords=["union", "representative", "questioning"],
    )
    for item in ranked:
        quote = (item.get("direct_quote") or "").lower()
        assert "weingarten rights require" not in quote


def test_casual_assignment_mismatch_for_past_practice_question():
    chunk = (
        "The appropriate representatives of the affected Unions will be informed "
        "in advance of the reasons for establishing the combination full-time assignments."
    )
    question = (
        "Management ended a seniority-based recurring work assignment procedure. "
        "What evidence is needed to establish a binding past practice?"
    )
    penalty = compute_topic_mismatch_penalty(
        chunk,
        question=question,
        primary_issue="Change in work assignment past practice",
    )
    assert penalty >= 0.75


def test_transfer_denial_mismatch_for_past_practice_question():
    chunk = "The denial of a transfer request is a grievable matter."
    question = (
        "Management ended a seniority-based work assignment procedure. "
        "What evidence is needed to establish a binding past practice?"
    )
    penalty = compute_topic_mismatch_penalty(
        chunk,
        question=question,
        primary_issue="Past practice in work assignment selection",
    )
    assert penalty >= 0.75


def test_article_5_past_practice_not_penalized():
    chunk = (
        "If a binding past practice clarifies or implements a contract provision, "
        "it becomes, in effect, an unwritten part of that provision."
    )
    question = (
        "What evidence is needed to establish a binding past practice when "
        "management changed a seniority-based work assignment procedure?"
    )
    penalty = compute_topic_mismatch_penalty(
        chunk,
        question=question,
        primary_issue="Past practice in work assignments",
    )
    assert penalty < 0.75


def test_casual_assignment_filtered_for_past_practice_question(mock_chunk_factory):
    chunk = mock_chunk_factory(
        "The appropriate representatives of the affected Unions will be informed "
        "in advance of the reasons for establishing the combination full-time assignments."
    )
    ranked = AuthorityRanker._apply_post_filters(
        [
            {
                "ref_id": "S1",
                "chunk": chunk,
                "relevance_score": 83,
                "role": "information_right",
                "direct_quote": (
                    "The appropriate representatives of the affected Unions will be "
                    "informed in advance of the reasons for establishing the combination "
                    "full-time assignments."
                ),
            }
        ],
        issue_keywords=["past", "practice", "seniority", "assignment"],
        question=(
            "What evidence is needed to establish a binding past practice when "
            "management changed work assignment selection by seniority?"
        ),
        primary_issue="Past practice in work assignment procedure",
    )
    assert ranked == []
