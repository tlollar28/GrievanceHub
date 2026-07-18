"""Follow-up Q&A service tests with mocked LLM responses."""

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.case_service import (
    CaseReportRequiredError,
    CaseService,
    ReportVersionNotFoundError,
)
from app.services.follow_up_chat_service import FOLLOW_UP_INTENT, FollowUpChatService

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "reports" / "sample_wrapper_report.json"
CASE_UUID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def _load_fixture():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _report_version(**overrides):
    payload = _load_fixture()
    created = datetime(2026, 1, 1, tzinfo=timezone.utc)
    base = SimpleNamespace(
        id=1,
        version_number=1,
        trigger_message_id=None,
        created_at=created,
        report_data=payload,
        ranked_authorities=payload.get("ranked_authorities", []),
        issue_analysis=payload.get("issue_analysis", {}),
        evidence_items=payload.get("report", {}).get("supporting_evidence", []),
        retrieval_gaps=payload.get("retrieval_gaps"),
        source_coverage_audit=payload.get("retrieval_gaps", {}).get("source_coverage_audit"),
        report_summary={
            "primary_issue": "Approved annual leave cancellation",
            "articles": ["CIM Article 10"],
            "source_types_found": ["CIM"],
            "authority_count": 2,
            "has_remedy_authority": False,
            "has_source_gaps": True,
            "message_count": 1,
        },
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def _sample_case(**overrides):
    created = datetime(2026, 1, 1, tzinfo=timezone.utc)
    values = {
        "case_uuid": CASE_UUID,
        "title": "Leave cancellation",
        "user_name": "Test Steward",
        "local_number": "300",
        "initial_question": "Can management cancel approved leave?",
        "known_facts": {"approved_in_writing": True},
        "status": "open",
        "created_at": created,
        "updated_at": created,
        "messages": [],
        "report_versions": [_report_version()],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _message(role, content, metadata=None, message_id=1):
    return SimpleNamespace(
        id=message_id,
        role=role,
        content=content,
        message_metadata=metadata,
        created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )


def _mock_llm_response(**overrides):
    base = {
        "answer": "The steward should gather written leave approval and cancellation notice.",
        "answer_type": "missing_evidence",
        "citations": [],
        "disclosures": [],
        "facts_needed": ["Written leave approval"],
        "requires_report_regen": False,
        "suggested_actions": [],
    }
    base.update(overrides)
    return base


def test_build_grounding_package_from_saved_version():
    case = _sample_case()
    version = case.report_versions[0]
    package = FollowUpChatService.build_grounding_package(case, version)

    assert package["case_uuid"] == CASE_UUID
    assert package["report_version_number"] == 1
    assert package["report_summary"]["has_remedy_authority"] is False
    assert package["retrieval_gaps"]["unindexed_sources_requested"] == ["LMOU"]
    assert package["evidence_to_gather"] == ["Written leave approval", "Cancellation notice"]
    assert package["saved_quotes"]
    assert package["key_violations"]


def test_missing_evidence_question_uses_report_checklist():
    case = _sample_case()
    version = case.report_versions[0]
    grounding = FollowUpChatService.build_grounding_package(case, version)

    def fake_llm(question, _grounding):
        assert "missing" in question.lower() or "evidence" in question.lower()
        assert grounding["evidence_to_gather"]
        return _mock_llm_response(
            answer="Missing items: " + ", ".join(grounding["evidence_to_gather"]),
            answer_type="missing_evidence",
            facts_needed=grounding["evidence_to_gather"],
        )

    answer = FollowUpChatService.generate_answer(
        "What evidence am I missing?",
        grounding,
        llm_callable=fake_llm,
    )

    assert answer.answer_type == "missing_evidence"
    assert "Written leave approval" in answer.answer
    assert "Written leave approval" in answer.facts_needed


def test_authority_lookup_cites_saved_quote():
    case = _sample_case()
    version = case.report_versions[0]
    grounding = FollowUpChatService.build_grounding_package(case, version)
    saved_quote = grounding["saved_quotes"][0]

    def fake_llm(_question, _grounding):
        return _mock_llm_response(
            answer_type="citation",
            citations=[
                {
                    "document_type": "CIM",
                    "document_name": "NPMHU CIM v6",
                    "article_or_section": "Article 10, Section 3",
                    "page": 137,
                    "quote": saved_quote,
                }
            ],
        )

    answer = FollowUpChatService.generate_answer(
        "Does Article 10 help here?",
        grounding,
        llm_callable=fake_llm,
    )

    assert answer.citations
    assert answer.citations[0].grounded is True
    assert answer.citations[0].document_type == "CIM"


def test_no_hallucinated_grievant_facts():
    case = _sample_case()
    grounding = FollowUpChatService.build_grounding_package(case, case.report_versions[0])

    def fake_llm(_question, _grounding):
        return _mock_llm_response(
            answer="The grievant's name is unknown from the saved case record.",
            answer_type="uncertainty",
            facts_needed=["Grievant name"],
        )

    answer = FollowUpChatService.generate_answer(
        "What is the grievant's name?",
        grounding,
        llm_callable=fake_llm,
    )

    assert "unknown" in answer.answer.lower() or answer.facts_needed


def test_remedy_follow_up_discloses_no_explicit_authority():
    case = _sample_case()
    grounding = FollowUpChatService.build_grounding_package(case, case.report_versions[0])

    def fake_llm(_question, _grounding):
        return _mock_llm_response(
            answer="Consider proposed relief based on violation context.",
            answer_type="remedy",
        )

    answer = FollowUpChatService.generate_answer(
        "What remedy should I request?",
        grounding,
        llm_callable=fake_llm,
    )

    assert any("remedy authority" in item.lower() for item in answer.disclosures)


def test_lmou_not_indexed_disclosure():
    case = _sample_case()
    grounding = FollowUpChatService.build_grounding_package(case, case.report_versions[0])

    def fake_llm(_question, _grounding):
        return _mock_llm_response(answer="No indexed LMOU authority is in the saved report.")

    answer = FollowUpChatService.generate_answer(
        "Is there anything in the LMOU?",
        grounding,
        llm_callable=fake_llm,
    )

    assert any("LMOU" in item for item in answer.disclosures)


def test_citation_validation_rejects_ungrounded_quote():
    case = _sample_case()
    grounding = FollowUpChatService.build_grounding_package(case, case.report_versions[0])

    def fake_llm(_question, _grounding):
        return _mock_llm_response(
            citations=[
                {
                    "document_type": "CONTRACT",
                    "document_name": "National Agreement",
                    "article_or_section": "Article 99",
                    "page": 1,
                    "quote": "This quote does not exist in the saved report.",
                }
            ]
        )

    answer = FollowUpChatService.generate_answer(
        "Quote test",
        grounding,
        llm_callable=fake_llm,
    )

    # Ungrounded citations are removed from the steward-facing response.
    assert answer.citations == []
    assert any("could not be verified" in item for item in answer.disclosures)


def test_separate_contract_and_cim_citations():
    citations = FollowUpChatService.validate_citations(
        [
            {
                "document_type": "CONTRACT",
                "document_name": "National Agreement",
                "article_or_section": "Article 10.5",
                "page": 44,
                "quote": "All advance commitments for granting annual leave must be honored except in serious emergency situations.",
            },
            {
                "document_type": "CIM",
                "document_name": "NPMHU CIM v6",
                "article_or_section": "Article 31",
                "page": 468,
                "quote": "Employees who have annual leave approved are entitled to such annual leave except in emergency situations.",
            },
        ],
        {
            "saved_quotes": [
                "All advance commitments for granting annual leave must be honored except in serious emergency situations.",
                "Employees who have annual leave approved are entitled to such annual leave except in emergency situations.",
            ]
        },
    )

    types = {item.document_type for item in citations}
    assert types == {"CONTRACT", "CIM"}


def test_new_facts_suggests_regen_not_auto_regen():
    case = _sample_case()
    grounding = FollowUpChatService.build_grounding_package(case, case.report_versions[0])

    def fake_llm(_question, _grounding):
        return _mock_llm_response(answer="Acknowledged new fact.")

    answer = FollowUpChatService.generate_answer(
        "Actually management also suspended the grievant yesterday.",
        grounding,
        llm_callable=fake_llm,
    )

    assert answer.requires_report_regen is True
    assert "regenerate_report" in answer.suggested_actions


def test_prior_followups_included_in_context():
    prior_user = _message(
        "user",
        "What evidence am I missing?",
        metadata={"intent": FOLLOW_UP_INTENT},
        message_id=10,
    )
    prior_assistant = _message(
        "assistant",
        "Gather written approval.",
        metadata={"intent": FOLLOW_UP_INTENT, "answer_type": "missing_evidence"},
        message_id=11,
    )
    case = _sample_case(messages=[prior_user, prior_assistant])
    grounding = FollowUpChatService.build_grounding_package(case, case.report_versions[0])

    assert len(grounding["prior_followups"]) == 2
    assert grounding["prior_followups"][0]["content"] == "What evidence am I missing?"


def test_answer_follow_up_persists_without_report_regeneration():
    case = _sample_case()
    db = MagicMock()
    user_msg = _message("user", "Follow-up?", metadata={"intent": FOLLOW_UP_INTENT}, message_id=20)
    assistant_msg = _message(
        "assistant",
        "Answer text",
        metadata={"intent": FOLLOW_UP_INTENT, "answer_type": "fact"},
        message_id=21,
    )

    with patch.object(CaseService, "get_case_for_chat", return_value=case), patch.object(
        CaseService,
        "get_grounding_report_version",
        return_value=case.report_versions[0],
    ), patch.object(
        CaseService,
        "build_restored_interaction_context",
        return_value={"known_facts": case.known_facts},
    ), patch.object(
        FollowUpChatService,
        "retrieve_indexed_source_passages",
        return_value={
            "retrieved_source_passages": [],
            "indexed_source_types": ["CONTRACT", "CIM"],
            "retrieval_query": "What evidence am I missing?",
            "retrieval_performed": True,
            "retrieval_status": "empty",
            "retrieval_error": False,
            "retrieval_error_class": None,
        },
    ), patch.object(
        CaseService,
        "add_follow_up_exchange",
        return_value=(user_msg, assistant_msg),
    ) as mock_add, patch.object(
        CaseService,
        "generate_report_version",
    ) as mock_regen:
        result = FollowUpChatService.answer_follow_up(
            db,
            CASE_UUID,
            "What evidence am I missing?",
            llm_callable=lambda _q, _g: _mock_llm_response(),
        )

    mock_add.assert_called_once()
    mock_regen.assert_not_called()
    assert result["answer"]
    assert result["linked_report_version"]["version_number"] == 1


def test_get_grounding_report_version_missing_report_raises():
    case = _sample_case(report_versions=[])
    with pytest.raises(CaseReportRequiredError):
        CaseService.get_grounding_report_version(case)


def test_get_grounding_report_version_missing_version_raises():
    case = _sample_case()
    with pytest.raises(ReportVersionNotFoundError):
        CaseService.get_grounding_report_version(case, version_number=99)


def test_list_follow_up_messages_filters_thread():
    case = _sample_case(
        messages=[
            _message("user", "Initial", metadata=None, message_id=1),
            _message(
                "user",
                "Follow-up?",
                metadata={"intent": FOLLOW_UP_INTENT},
                message_id=2,
            ),
            _message(
                "assistant",
                "Answer",
                metadata={"intent": FOLLOW_UP_INTENT, "answer_type": "fact"},
                message_id=3,
            ),
        ]
    )
    messages = CaseService.list_follow_up_messages(case)
    assert len(messages) == 2
    assert messages[0].content == "Follow-up?"
