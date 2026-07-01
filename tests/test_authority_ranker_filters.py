from unittest.mock import MagicMock, patch

from app.services.authority_ranker import AuthorityRanker


def _mock_ranker_response():
    return {
        "ranked_authorities": [
            {
                "ref_id": "S1",
                "relevance_score": 90,
                "role": "union_supporting",
                "legal_issue": "Leave cancellation",
                "article_or_section": "Article 10",
                "authority_type": "Union-Supporting",
                "direct_quote": (
                    "Employees who have annual leave approved are entitled to such "
                    "annual leave except in emergency situations."
                ),
                "why_it_matters": "Limits management cancellation.",
            },
            {
                "ref_id": "S2",
                "relevance_score": 88,
                "role": "union_supporting",
                "legal_issue": "Extended absence leave usage",
                "article_or_section": "Article 10",
                "authority_type": "Union-Supporting",
                "direct_quote": (
                    "An employee who is on extended absence may use annual and/or sick "
                    "leave in conjunction with LWOP prior to exhausting his/her leave balances"
                ),
                "why_it_matters": "Mislabeled extended absence rule.",
            },
        ]
    }


@patch.object(AuthorityRanker, "_client")
def test_post_filters_demote_or_drop_mislabeled_lwop_passage(
    mock_client,
    annual_leave_fixture,
    mock_chunk_factory,
):
    mock_completion = MagicMock()
    mock_completion.choices = [
        MagicMock(message=MagicMock(content=str(_mock_ranker_response()).replace("'", '"')))
    ]
    mock_client.return_value.chat.completions.create.return_value = mock_completion

    chunks = [
        mock_chunk_factory(
            annual_leave_fixture["governing_passage"]["text"],
            chunk_index=242,
        ),
        mock_chunk_factory(
            annual_leave_fixture["distractor_passage"]["text"],
            chunk_index=308,
        ),
    ]

    ranked = AuthorityRanker._apply_post_filters(
        [
            {
                "ref_id": "S1",
                "chunk": chunks[0],
                "relevance_score": 90,
                "role": "union_supporting",
                "direct_quote": (
                    "Employees who have annual leave approved are entitled to such "
                    "annual leave except in emergency situations."
                ),
            },
            {
                "ref_id": "S2",
                "chunk": chunks[1],
                "relevance_score": 88,
                "role": "union_supporting",
                "direct_quote": (
                    "An employee who is on extended absence may use annual and/or sick "
                    "leave in conjunction with LWOP prior to exhausting his/her leave balances"
                ),
            },
        ],
        issue_keywords=[
            "management",
            "cancel",
            "previously",
            "approved",
            "annual",
            "leave",
            "emergency",
        ],
    )

    ref_ids = {item["ref_id"] for item in ranked}
    assert "S1" in ref_ids

    s2 = next((item for item in ranked if item["ref_id"] == "S2"), None)
    if s2 is not None:
        assert s2["role"] == "background_only"


def test_management_limiting_preserved_with_lower_threshold(
    mock_chunk_factory,
):
    chunk = mock_chunk_factory(
        "Management retains the right to assign work and determine methods."
    )

    ranked = AuthorityRanker._apply_post_filters(
        [
            {
                "ref_id": "S1",
                "chunk": chunk,
                "relevance_score": 55,
                "role": "management_limiting",
                "direct_quote": "Management retains the right to assign work",
            }
        ],
        issue_keywords=["management", "assign", "work", "schedule"],
    )

    assert len(ranked) == 1
    assert ranked[0]["role"] == "management_limiting"

def test_promote_per_issue_coverage_floor_adds_tagged_issue(mock_chunk_factory):
    from app.services.authority_ranker import ISSUE_TYPE_DEFAULT_ROLES

    probation_chunk = mock_chunk_factory(
        "The Employer shall have the right to separate from its employ any probationary employee.",
        chunk_index=1,
    )
    probation_chunk.retrieval_metadata = {
        "matched_issue_ids": ["legal_1"],
        "combined_score": 0.82,
    }
    info_chunk = mock_chunk_factory(
        "Upon the written request of the Union, the Employer will furnish such information.",
        chunk_index=2,
    )
    info_chunk.retrieval_metadata = {
        "matched_issue_ids": ["information_1"],
        "combined_score": 0.88,
    }

    ranked = [
        {
            "ref_id": "S1",
            "chunk": probation_chunk,
            "document_name": "CIM",
            "document_type": "CIM",
            "page": 1,
            "chunk_index": 1,
            "relevance_score": 99,
            "role": "management_limiting",
            "legal_issue": "Probation",
            "article_or_section": "12.1",
            "authority_type": "Management-Limiting",
            "direct_quote": (
                "The Employer shall have the right to separate from its employ any probationary employee."
            ),
            "why_it_matters": "Limits grievance rights.",
            "retrieval_metadata": probation_chunk.retrieval_metadata,
        }
    ]

    decomposed = [
        {
            "issue_id": "legal_1",
            "issue_type": "legal",
            "issue": "Probation termination provisions",
        },
        {
            "issue_id": "information_1",
            "issue_type": "information_rights",
            "issue": "Union information rights",
        },
    ]

    promoted = AuthorityRanker._promote_per_issue_coverage_floor(
        ranked,
        decomposed,
        [probation_chunk, info_chunk],
        issue_keywords=["union", "information", "probation", "termination"],
        dispute_frame={"union_concerns": ["information access"]},
        max_authorities=5,
    )

    assert len(promoted) == 2
    roles = {item["role"] for item in promoted}
    assert ISSUE_TYPE_DEFAULT_ROLES["information_rights"] in roles


def test_promote_per_issue_coverage_floor_skips_when_no_valid_candidate(mock_chunk_factory):
    chunk = mock_chunk_factory("Table of contents article 1 article 2 index", chunk_index=3)
    chunk.retrieval_metadata = {
        "matched_issue_ids": ["remedy_1"],
        "combined_score": 0.2,
    }

    promoted = AuthorityRanker._promote_per_issue_coverage_floor(
        [],
        [{"issue_id": "remedy_1", "issue_type": "remedy", "issue": "Remedy"}],
        [chunk],
        issue_keywords=["remedy"],
        dispute_frame={},
        max_authorities=5,
    )

    assert promoted == []

