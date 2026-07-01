"""NarrativeGenerator unit tests with mock authorities."""

from app.retrieval_config import MIN_KEY_AUTHORITY_RELEVANCE_SCORE
from app.services.narrative_generator import NarrativeGenerator

OLD_STATIC_WHY_SNIPPETS = (
    "Article 10 always supports the grievance.",
    "Management violated the contract without further review.",
    "CREA analysis indicates",
)


def _mock_authority(role="union_supporting", score=85, section="Article 10", quote="Employees shall be entitled to annual leave."):
    return {
        "role": role,
        "relevance_score": score,
        "article_or_section": section,
        "document_name": "NPMHU CIM v6",
        "document_type": "CIM",
        "page": 10,
        "chunk_index": 1,
        "direct_quote": quote,
        "why_relevant": "Supports the stated issue.",
        "citation": {"document_name": "NPMHU CIM v6", "page": 10, "chunk": 1},
    }


def test_quick_assessment_grounded_not_boilerplate():
    authority_groups = {
        "union_supporting": [_mock_authority()],
        "procedural_requirement": [],
        "information_right": [],
        "timeline_requirement": [],
        "remedy_support": [],
    }
    legal_issues = {
        "primary_issue": "Cancellation of approved annual leave",
        "grievability": "Possibly Grievable",
        "confidence": "Medium",
    }
    base = NarrativeGenerator.build_quick_assessment(
        question="Can management cancel approved leave?",
        legal_issues=legal_issues,
        authority_groups=authority_groups,
        evidence_items=[{"quote": "annual leave approved"}],
        known_facts=["Leave was approved in writing"],
        retrieval_gaps={"missing_source_types": ["LMOU"]},
    )
    assert "Retrieved authorities include:" in base["summary"]
    assert "Stated facts considered:" in base["why"]
    assert "No authorities were retrieved for: LMOU" in base["why"]
    for snippet in OLD_STATIC_WHY_SNIPPETS:
        assert snippet not in base["why"]


def test_recommended_remedy_requires_remedy_authority_or_notice():
    legal_issues = {"missing_facts": ["Whether leave was paid"]}
    empty = NarrativeGenerator.build_recommended_remedy(
        legal_issues=legal_issues,
        authority_groups={"remedy_support": []},
        evidence_items=[],
    )
    assert empty["statements"] == []
    assert empty["insufficient_notice"] is not None
    assert "No remedy_support authority" in empty["insufficient_notice"]

    with_remedy = NarrativeGenerator.build_recommended_remedy(
        legal_issues=legal_issues,
        authority_groups={"remedy_support": [_mock_authority(role="remedy_support", section="Remedy")]},
        evidence_items=[],
    )
    assert with_remedy["statements"]
    assert with_remedy["insufficient_notice"] is None


def test_strategic_tips_not_static_four_tips():
    authority_groups = {
        "information_right": [_mock_authority(role="information_right", section="Article 31")],
        "timeline_requirement": [_mock_authority(role="timeline_requirement", section="Article 15")],
        "procedural_requirement": [],
        "management_limiting": [],
    }
    tips = NarrativeGenerator.build_strategic_tips(
        legal_issues={"secondary_issues": []},
        authority_groups=authority_groups,
        issue_analysis={"facts_needed": ["Approval letter"]},
        retrieval_gaps={"missing_source_types": ["ELM"], "issues_without_supporting_authority": ["Local MOU leave rule"]},
    )
    titles = [t["title"] for t in tips]
    assert len(tips) != 4 or "Retrieve ELM language" in titles
    assert any("Information request" in title for title in titles)
    assert any("Retrieve ELM" in title for title in titles)
    assert all(t["provenance"]["generator"] == "narrative_generator" for t in tips)


def test_confidence_low_when_retrieval_gaps():
    ranked = [
        _mock_authority(score=MIN_KEY_AUTHORITY_RELEVANCE_SCORE + 5),
    ]
    confidence = NarrativeGenerator.compute_confidence(
        ranked_authorities=ranked,
        retrieval_gaps={
            "missing_source_types": ["CONTRACT"],
            "issues_without_supporting_authority": ["Remedy for canceled leave"],
        },
        citation_status="Passed",
    )
    assert confidence == "Medium"

    low = NarrativeGenerator.compute_confidence(
        ranked_authorities=[],
        retrieval_gaps={"missing_source_types": ["CONTRACT", "ELM"]},
        citation_status=None,
    )
    assert low == "Low"


def test_grievance_framework_preserves_actor():
    dispute_frame = "Management canceled previously approved annual leave without notice."
    text = NarrativeGenerator.build_grievance_framework(
        dispute_frame=dispute_frame,
        legal_issues={"primary_issue": "Leave cancellation rules"},
        likely_violations=[
            {"article_or_section": "Article 10", "issue": "Approved leave entitlement"}
        ],
    )
    assert dispute_frame in text
    assert text.startswith("Dispute frame: Management canceled")
