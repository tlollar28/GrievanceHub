from app.services.knowledge_retrieval_service import KnowledgeRetrievalService
from app.services.relevance_utils import (
    RetrievedChunk,
    combine_retrieval_score,
    compute_keyword_overlap_score,
    compute_procedural_bonus,
    extract_issue_keywords,
    is_boilerplate_chunk,
)


def test_combined_score_ranks_governing_above_lwop_passage(
    annual_leave_fixture,
    mock_chunk_factory,
):
    issue_keywords = extract_issue_keywords(
        question=annual_leave_fixture["question"],
        analysis=annual_leave_fixture["analysis"],
    )

    governing_chunk = mock_chunk_factory(
        annual_leave_fixture["governing_passage"]["text"],
        chunk_index=242,
        page_number=137,
    )
    distractor_chunk = mock_chunk_factory(
        annual_leave_fixture["distractor_passage"]["text"],
        chunk_index=308,
        page_number=171,
    )

    def score_chunk(chunk, embedding_distance):
        text = chunk.text
        embedding_similarity = max(0.0, 1.0 - embedding_distance)
        keyword_overlap = compute_keyword_overlap_score(text, issue_keywords)
        procedural_bonus = compute_procedural_bonus(text, issue_keywords)
        return combine_retrieval_score(
            embedding_similarity=embedding_similarity,
            keyword_overlap=keyword_overlap,
            source_type="CIM",
            is_boilerplate=is_boilerplate_chunk(text),
            procedural_bonus=procedural_bonus,
        )

    governing_score = score_chunk(governing_chunk, 0.20)
    distractor_score = score_chunk(distractor_chunk, 0.18)

    assert governing_score > distractor_score


def test_score_chunk_match_via_service(annual_leave_fixture, mock_chunk_factory):
    issue_keywords = extract_issue_keywords(
        question=annual_leave_fixture["question"],
        analysis=annual_leave_fixture["analysis"],
    )

    governing = RetrievedChunk(
        chunk=mock_chunk_factory(annual_leave_fixture["governing_passage"]["text"]),
        best_embedding_distance=0.22,
        matched_query_count=2,
    )
    distractor = RetrievedChunk(
        chunk=mock_chunk_factory(annual_leave_fixture["distractor_passage"]["text"]),
        best_embedding_distance=0.19,
        matched_query_count=1,
    )

    governing_score = KnowledgeRetrievalService._score_chunk_match(
        governing,
        issue_keywords,
    )
    distractor_score = KnowledgeRetrievalService._score_chunk_match(
        distractor,
        issue_keywords,
    )

    assert governing_score > distractor_score
