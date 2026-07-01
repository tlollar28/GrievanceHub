from app.services.relevance_utils import (
    combine_retrieval_score,
    compute_distinctive_overlap_score,
    compute_keyword_overlap_score,
    extract_issue_keywords,
    is_boilerplate_chunk,
    verify_quote_in_chunk,
)


def test_distinctive_overlap_distinguishes_cancellation_from_lwop(
    annual_leave_fixture,
):
    issue_keywords = extract_issue_keywords(
        question=annual_leave_fixture["question"],
        analysis=annual_leave_fixture["analysis"],
    )

    governing = compute_distinctive_overlap_score(
        annual_leave_fixture["governing_passage"]["text"],
        issue_keywords,
    )
    distractor = compute_distinctive_overlap_score(
        annual_leave_fixture["distractor_passage"]["text"],
        issue_keywords,
    )

    assert governing > distractor


def test_keyword_overlap_schedule_change( schedule_change_fixture):
    issue_keywords = extract_issue_keywords(
        question=schedule_change_fixture["question"],
        analysis=schedule_change_fixture["analysis"],
    )

    governing_overlap = compute_keyword_overlap_score(
        schedule_change_fixture["governing_passage"]["text"],
        issue_keywords,
    )
    distractor_overlap = compute_keyword_overlap_score(
        schedule_change_fixture["distractor_passage"]["text"],
        issue_keywords,
    )

    assert governing_overlap > distractor_overlap


def test_boilerplate_detection():
    assert is_boilerplate_chunk("TABLE OF CONTENTS\nArticle 10 Leave ... 34")
    assert not is_boilerplate_chunk(
        "Employees who have annual leave approved are entitled to such annual leave."
    )


def test_verify_quote_in_chunk():
    chunk = "Employees who have annual leave approved are entitled to such annual leave except in emergency situations."
    assert verify_quote_in_chunk(
        "annual leave approved are entitled to such annual leave except in emergency",
        chunk,
    )
    assert not verify_quote_in_chunk("completely invented quote", chunk)


def test_combine_retrieval_score_prefers_issue_match():
    high = combine_retrieval_score(
        embedding_similarity=0.75,
        keyword_overlap=0.45,
        source_type="CIM",
        is_boilerplate=False,
    )
    low = combine_retrieval_score(
        embedding_similarity=0.78,
        keyword_overlap=0.10,
        source_type="CIM",
        is_boilerplate=False,
    )

    assert high > low
