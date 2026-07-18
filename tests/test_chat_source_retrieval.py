"""Normal case chat indexed retrieval, provenance, isolation, and side effects."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.schemas.case_workspace_action_schema import CaseInteractionRequest
from app.services.case_asset_service import CaseAssetService
from app.services.case_service import CaseService
from app.services.case_workspace_action_service import CaseWorkspaceActionService
from app.services.follow_up_chat_service import (
    CHAT_RETRIEVAL_LIMIT_PER_SOURCE,
    FollowUpChatService,
)
from app.services.knowledge_retrieval_service import KnowledgeRetrievalService
from app.services.case_memory_service import CaseMemoryService

CASE_A = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
CASE_B = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"


def _chunk(*, text: str, source_type: str = "CONTRACT", name: str = "National Agreement"):
    source = SimpleNamespace(
        source_id="contract-1",
        name=name,
        source_type=source_type,
    )
    return SimpleNamespace(
        source_document=source,
        page_number=44,
        chunk_index=3,
        text=text,
        retrieval_metadata={
            "combined_score": 0.82,
            "article_or_section": "Article 10.5",
        },
    )


def _case(
    *,
    case_uuid: str = CASE_A,
    with_report: bool = False,
    known_facts: dict | None = None,
    workflow: str = "case_open",
):
    report_versions = []
    if with_report:
        report_versions = [
            SimpleNamespace(
                id=1,
                version_number=1,
                report_data={
                    "report": {
                        "quick_assessment": {"summary": "prior"},
                        "key_contract_violations": [
                            {
                                "direct_quote": "Older saved report quote about overtime.",
                                "citation": {
                                    "document_type": "CONTRACT",
                                    "document_name": "National Agreement",
                                    "page": 10,
                                },
                            }
                        ],
                    }
                },
                ranked_authorities=[],
                issue_analysis={},
                evidence_items=[],
                retrieval_gaps={},
                source_coverage_audit=[],
                report_summary={"primary_issue": "leave"},
            )
        ]
    return SimpleNamespace(
        id=10 if case_uuid == CASE_A else 11,
        case_uuid=case_uuid,
        title="Case",
        user_name="Steward",
        local_number="300",
        initial_question="Initial concern",
        known_facts=known_facts
        or {"approved_in_writing": True, "grievant_name": "Pat Lee"},
        status="open",
        created_at=datetime(2026, 7, 1, tzinfo=UTC),
        updated_at=datetime(2026, 7, 1, tzinfo=UTC),
        messages=[],
        report_versions=report_versions,
        workflow_state=workflow,
    )


def _message(role: str, content: str, message_id: int, case_id: int = 10):
    return SimpleNamespace(
        id=message_id,
        role=role,
        content=content,
        message_metadata={"intent": "follow_up"},
        created_at=datetime(2026, 7, 18, tzinfo=UTC),
        case_id=case_id,
    )


def _inspection(case):
    return SimpleNamespace(
        case=case,
        has_analysis_report=bool(case.report_versions),
        latest_report_version_id=(
            case.report_versions[0].id if case.report_versions else None
        ),
        latest_report_version_number=(
            case.report_versions[0].version_number if case.report_versions else None
        ),
        has_step_progression=True,
        current_step_type="step_1_initial",
        template_id=None,
        template_availability_status="unconfirmed_pending_steward_confirmation",
        template_available=False,
        case_status="open",
    )


LEAVE_QUOTE = (
    "Annual leave which has been approved shall not be cancelled "
    "except in emergency situations."
)


def test_build_chat_retrieval_query_keeps_question_primary():
    query = FollowUpChatService.build_chat_retrieval_query(
        "Can management cancel approved leave?",
        known_facts={
            "approved_in_writing": True,
            "unrelated_note": "birthday party next week",
            "leave_date": "2026-06-01",
        },
    )
    assert query.startswith("Can management cancel approved leave?")
    assert "approved_in_writing" in query or "leave_date" in query
    assert "birthday party" not in query
    assert "Initial concern" not in query


def test_build_chat_retrieval_query_does_not_dump_transcript():
    query = FollowUpChatService.build_chat_retrieval_query(
        "What is the remedy?",
        known_facts={"remedy_requested": "make whole"},
    )
    assert "What is the remedy?" in query
    assert "user:" not in query.lower()


def test_attach_source_retrieval_threads_limit_and_query():
    package = {
        "known_facts": {"approved_in_writing": True},
        "saved_report_authority_quotes": [],
        "saved_quotes": [],
        "report_version_id": None,
        "limitations_caveats": [],
    }
    with patch.object(
        KnowledgeRetrievalService,
        "search_all",
        return_value={
            "all_chunks": [_chunk(text=LEAVE_QUOTE)],
            "indexed_source_types": ["CONTRACT", "CIM"],
        },
    ) as mock_search:
        FollowUpChatService.attach_source_retrieval(
            package,
            MagicMock(),
            "Can management cancel approved leave?",
            limit_per_source=3,
        )

    assert mock_search.call_args.kwargs["limit_per_source"] == 3
    assert "Can management cancel approved leave?" in mock_search.call_args.kwargs[
        "query"
    ]
    assert package["retrieval_status"] == "ok"
    assert package["retrieved_source_passages"][0]["provenance"] == "retrieved_passage"


def test_citation_provenance_prefers_current_retrieval_over_saved_report():
    shared = "shall not be cancelled except in emergency situations."
    grounding = {
        "retrieved_source_passages": [
            {
                "document_type": "CONTRACT",
                "document_name": "National Agreement",
                "page": 44,
                "article_or_section": "Article 10.5",
                "excerpt": LEAVE_QUOTE,
            }
        ],
        "saved_report_authority_quotes": [shared],
        "saved_quotes": [shared],
        "retrieval_status": "ok",
        "retrieval_error": False,
    }
    citations = FollowUpChatService.validate_citations(
        [
            {
                "document_type": "CONTRACT",
                "document_name": "National Agreement",
                "article_or_section": "Article 10.5",
                "page": 44,
                "quote": shared,
            }
        ],
        grounding,
    )
    assert citations[0].grounded is True
    assert citations[0].grounding_provenance == "retrieved_passage"
    assert citations[0].grounding_passage_index == 0


def test_citation_metadata_is_replaced_by_matched_source_metadata():
    grounding = {
        "retrieved_source_passages": [
            {
                "document_type": "CONTRACT",
                "document_name": "National Agreement",
                "page": 44,
                "article_or_section": "Article 10.5",
                "excerpt": LEAVE_QUOTE,
            }
        ],
        "saved_report_authorities": [],
        "retrieval_status": "ok",
        "retrieval_error": False,
    }
    citations = FollowUpChatService.validate_citations(
        [
            {
                "document_type": "CIM",
                "document_name": "Wrong document",
                "article_or_section": "Article 99",
                "page": 999,
                "quote": "shall not be cancelled except in emergency situations.",
            }
        ],
        grounding,
    )
    citation = citations[0]
    assert citation.grounded is True
    assert citation.document_type == "CONTRACT"
    assert citation.document_name == "National Agreement"
    assert citation.article_or_section == "Article 10.5"
    assert citation.page == 44


def test_saved_report_citation_uses_saved_authority_metadata():
    grounding = {
        "retrieved_source_passages": [],
        "saved_report_authorities": [
            {
                "document_type": "CONTRACT",
                "document_name": "National Agreement",
                "article_or_section": "Article 8",
                "page": 31,
                "direct_quote": "Older saved report quote about overtime.",
            }
        ],
        "retrieval_status": "empty",
        "retrieval_error": False,
    }
    citations = FollowUpChatService.validate_citations(
        [
            {
                "document_type": "ELM",
                "document_name": "Wrong document",
                "page": 777,
                "quote": "Older saved report quote about overtime.",
            }
        ],
        grounding,
    )
    citation = citations[0]
    assert citation.grounding_provenance == "saved_report_authority"
    assert citation.grounding_authority_index == 0
    assert citation.document_type == "CONTRACT"
    assert citation.document_name == "National Agreement"
    assert citation.article_or_section == "Article 8"
    assert citation.page == 31


def test_citation_cannot_claim_retrieval_from_saved_report_only():
    grounding = {
        "retrieved_source_passages": [],
        "saved_report_authority_quotes": [
            "Older saved report quote about overtime."
        ],
        "saved_quotes": ["Older saved report quote about overtime."],
        "retrieval_status": "empty",
        "retrieval_error": False,
    }
    citations = FollowUpChatService.validate_citations(
        [
            {
                "document_type": "CONTRACT",
                "quote": "Older saved report quote about overtime.",
            }
        ],
        grounding,
    )
    assert citations[0].grounded is True
    assert citations[0].grounding_provenance == "saved_report_authority"


def test_zero_results_strip_fabricated_retrieval_citations():
    grounding = {
        "retrieved_source_passages": [],
        "saved_report_authority_quotes": [],
        "saved_quotes": [],
        "retrieval_status": "empty",
        "retrieval_error": False,
        "report_summary": {},
    }

    def fake_llm(_q, _g):
        return {
            "answer": "I am not seeing a matching indexed passage.",
            "answer_type": "uncertainty",
            "citations": [
                {
                    "document_type": "CONTRACT",
                    "document_name": "National Agreement",
                    "quote": "fabricated quote not in corpus",
                }
            ],
            "disclosures": [],
            "facts_needed": [],
            "requires_report_regen": False,
            "suggested_actions": [],
        }

    answer = FollowUpChatService.generate_answer(
        "Can management cancel leave?",
        grounding,
        llm_callable=fake_llm,
    )
    assert answer.citations == []
    assert any("No relevant indexed passage" in d for d in answer.disclosures)


def test_retrieval_failure_distinct_from_empty_and_strips_citations():
    grounding = {
        "retrieved_source_passages": [],
        "saved_report_authority_quotes": [],
        "saved_quotes": [],
        "retrieval_status": "failed",
        "retrieval_error": True,
        "retrieval_error_class": "OperationalError",
        "report_summary": {},
    }

    def fake_llm(_q, _g):
        return {
            "answer": "I can still discuss the case facts.",
            "answer_type": "fact",
            "citations": [
                {
                    "document_type": "CONTRACT",
                    "quote": "any quote",
                }
            ],
            "disclosures": [],
            "facts_needed": [],
            "requires_report_regen": False,
            "suggested_actions": [],
        }

    answer = FollowUpChatService.generate_answer(
        "What does the contract say?",
        grounding,
        llm_callable=fake_llm,
    )
    assert answer.citations == []
    assert any("temporarily unavailable" in d for d in answer.disclosures)


def test_retrieve_indexed_source_passages_marks_failure():
    with patch.object(
        KnowledgeRetrievalService,
        "search_all",
        side_effect=RuntimeError("db down"),
    ):
        result = FollowUpChatService.retrieve_indexed_source_passages(
            MagicMock(),
            "Can management cancel approved leave?",
        )
    assert result["retrieval_status"] == "failed"
    assert result["retrieval_error"] is True
    assert result["retrieval_error_class"] == "RuntimeError"
    assert result["retrieval_performed"] is False
    assert result["retrieved_source_passages"] == []


def test_answer_follow_up_without_report_reaches_retrieval_with_question():
    case = _case(with_report=False)
    captured = {}

    def fake_llm(question, grounding):
        captured["grounding"] = grounding
        return {
            "answer": "Approved leave generally may not be cancelled except in emergencies.",
            "answer_type": "citation",
            "citations": [
                {
                    "document_type": "CONTRACT",
                    "document_name": "National Agreement",
                    "article_or_section": "Article 10.5",
                    "page": 44,
                    "quote": LEAVE_QUOTE,
                }
            ],
            "disclosures": [],
            "facts_needed": [],
            "requires_report_regen": False,
            "suggested_actions": [],
        }

    user_msg = _message("user", "Can management cancel approved leave?", 20)
    assistant_msg = _message("assistant", "Generally no.", 21)

    with (
        patch.object(CaseService, "get_case_for_chat", return_value=case),
        patch.object(
            CaseService,
            "build_restored_interaction_context",
            return_value={"known_facts": case.known_facts, "case_state": {}},
        ),
        patch.object(
            KnowledgeRetrievalService,
            "search_all",
            return_value={
                "all_chunks": [_chunk(text=LEAVE_QUOTE)],
                "indexed_source_types": ["CONTRACT", "CIM"],
            },
        ) as mock_search,
        patch.object(
            CaseService,
            "add_follow_up_exchange",
            return_value=(user_msg, assistant_msg),
        ) as mock_add,
        patch.object(CaseService, "generate_report_version") as mock_regen,
    ):
        result = FollowUpChatService.answer_follow_up(
            MagicMock(),
            CASE_A,
            "Can management cancel approved leave?",
            llm_callable=fake_llm,
            limit_per_source=CHAT_RETRIEVAL_LIMIT_PER_SOURCE,
        )

    mock_search.assert_called_once()
    assert "Can management cancel approved leave?" in mock_search.call_args.kwargs[
        "query"
    ]
    mock_regen.assert_not_called()
    mock_add.assert_called_once()
    assert captured["grounding"]["retrieved_source_passages"]
    assert result["citations"][0]["grounded"] is True
    assert result["citations"][0]["grounding_provenance"] == "retrieved_passage"
    assert result["retrieval_status"] == "ok"
    assert result["linked_report_version"] is None


def test_answer_follow_up_with_saved_report_still_runs_fresh_retrieval():
    case = _case(with_report=True)
    captured = {}

    def fake_llm(_q, grounding):
        captured["grounding"] = grounding
        return {
            "answer": "Current retrieval supports the leave rule.",
            "answer_type": "citation",
            "citations": [
                {
                    "document_type": "CONTRACT",
                    "document_name": "National Agreement",
                    "page": 44,
                    "quote": LEAVE_QUOTE,
                }
            ],
            "disclosures": [],
            "facts_needed": [],
            "requires_report_regen": False,
            "suggested_actions": [],
        }

    with (
        patch.object(CaseService, "get_case_for_chat", return_value=case),
        patch.object(
            CaseService,
            "get_grounding_report_version",
            return_value=case.report_versions[0],
        ),
        patch.object(
            CaseService,
            "build_restored_interaction_context",
            return_value={"known_facts": case.known_facts},
        ),
        patch.object(
            KnowledgeRetrievalService,
            "search_all",
            return_value={
                "all_chunks": [_chunk(text=LEAVE_QUOTE)],
                "indexed_source_types": ["CONTRACT", "CIM"],
            },
        ) as mock_search,
        patch.object(
            CaseService,
            "add_follow_up_exchange",
            return_value=(
                _message("user", "q", 1),
                _message("assistant", "a", 2),
            ),
        ),
    ):
        result = FollowUpChatService.answer_follow_up(
            MagicMock(),
            CASE_A,
            "Can management cancel approved leave now?",
            llm_callable=fake_llm,
        )

    mock_search.assert_called_once()
    assert (
        captured["grounding"]["grounding_mode"] == "case_report_and_indexed_sources"
    )
    assert result["citations"][0]["grounding_provenance"] == "retrieved_passage"


def test_submit_interaction_threads_limit_reaches_retrieval_and_serializes_provenance():
    service = CaseWorkspaceActionService(MagicMock())
    case = _case(with_report=False)
    inspection = _inspection(case)
    captured = {}

    def fake_answer(db, case_uuid, content, report_version_number=None, **kwargs):
        captured["limit_per_source"] = kwargs.get("limit_per_source")
        captured["content"] = content
        return {
            "user_message": _message("user", content, 40),
            "assistant_message": _message("assistant", "Grounded reply", 41),
            "answer": "Grounded reply",
            "answer_type": "citation",
            "citations": [
                {
                    "document_type": "CONTRACT",
                    "document_name": "National Agreement",
                    "article_or_section": "Article 10.5",
                    "page": 44,
                    "quote": LEAVE_QUOTE,
                    "grounded": True,
                    "grounding_provenance": "retrieved_passage",
                    "grounding_passage_index": 0,
                }
            ],
            "disclosures": [],
            "facts_needed": [],
            "linked_report_version": None,
            "requires_report_regen": False,
            "suggested_actions": [],
            "retrieval_status": "ok",
            "retrieval_error": False,
            "case_memory_update_status": "updated",
        }

    with (
        patch.object(
            service, "_inspect_workspace", side_effect=[inspection, inspection]
        ),
        patch.object(
            FollowUpChatService, "answer_follow_up", side_effect=fake_answer
        ),
        patch.object(
            service,
            "_enrich_interaction_message_metadata",
            return_value={"analysis_auto_refreshed": False},
        ),
        patch.object(CaseService, "generate_report_version") as mock_regen,
        patch("app.services.case_workflow_service.CaseWorkflowService.transition") as mock_wf,
        patch(
            "app.services.case_saved_artifact_service.CaseSavedArtifactService"
        ) as mock_art,
    ):
        result = service.submit_interaction(
            CASE_A,
            CaseInteractionRequest(message="Can management cancel approved leave?"),
            limit_per_source=5,
        )
        payload = result.model_dump(mode="json")

    assert captured["limit_per_source"] == 5
    assert "Can management cancel approved leave?" in captured["content"]
    assert payload["citations"][0]["grounding_provenance"] == "retrieved_passage"
    assert payload["citations"][0]["grounding_passage_index"] == 0
    assert payload["analysis_versions_created"] == 0
    assert payload["timeline_events"] == []
    assert payload["retrieval_status"] == "ok"
    assert payload["retrieval_error"] is False
    assert payload["case_memory_update_status"] == "updated"
    assert payload["analysis_update"]["case_memory_update_status"] == "updated"
    mock_regen.assert_not_called()
    mock_wf.assert_not_called()
    mock_art.assert_not_called()


def test_normal_chat_creates_no_report_artifact_or_ocr_via_add_exchange_path():
    case = _case(with_report=False)
    db = MagicMock()
    user = _message("user", "q", 1)
    assistant = _message("assistant", "a", 2)

    with (
        patch.object(CaseService, "get_case_for_chat", return_value=case),
        patch.object(
            CaseService,
            "build_restored_interaction_context",
            return_value={"known_facts": {}},
        ),
        patch.object(
            KnowledgeRetrievalService,
            "search_all",
            return_value={"all_chunks": [], "indexed_source_types": ["CONTRACT"]},
        ),
        patch.object(
            CaseService,
            "add_follow_up_exchange",
            return_value=(user, assistant),
        ) as mock_add,
        patch.object(CaseService, "generate_report_version") as mock_regen,
        patch.object(CaseService, "persist_report_version_from_preview") as mock_persist,
    ):
        FollowUpChatService.answer_follow_up(
            db,
            CASE_A,
            "Is overtime assignment governed by seniority?",
            llm_callable=lambda _q, _g: {
                "answer": "No matching indexed passage found in this test.",
                "answer_type": "uncertainty",
                "citations": [],
                "disclosures": [],
                "facts_needed": [],
                "requires_report_regen": False,
                "suggested_actions": [],
            },
        )

    mock_add.assert_called_once()
    mock_regen.assert_not_called()
    mock_persist.assert_not_called()


def test_follow_up_exchange_persists_chat_when_memory_projection_fails():
    case = _case(with_report=False)
    db = MagicMock()
    answer = SimpleNamespace(
        answer="Grounded answer",
        answer_type="fact",
        citations=[],
        disclosures=[],
        facts_needed=[],
        requires_report_regen=False,
        suggested_actions=[],
    )

    with (
        patch.object(CaseService, "_get_case_row", return_value=case),
        patch.object(
            CaseMemoryService,
            "publish_conversation_event",
            side_effect=RuntimeError("projection unavailable"),
        ),
    ):
        user_message, assistant_message = CaseService.add_follow_up_exchange(
            db, CASE_A, "Question", answer
        )

    assert user_message.role == "user"
    assert assistant_message.role == "assistant"
    assert (
        assistant_message.message_metadata["case_memory_update_status"] == "failed"
    )
    db.commit.assert_called_once()


def test_answer_follow_up_returns_memory_projection_status():
    case = _case(with_report=False)
    assistant = _message("assistant", "Answer", 2)
    assistant.message_metadata = {"case_memory_update_status": "projection_failed"}

    with (
        patch.object(CaseService, "get_case_for_chat", return_value=case),
        patch.object(
            CaseService,
            "build_restored_interaction_context",
            return_value={"known_facts": {}},
        ),
        patch.object(
            KnowledgeRetrievalService,
            "search_all",
            return_value={"all_chunks": [], "indexed_source_types": ["CONTRACT"]},
        ),
        patch.object(
            CaseService,
            "add_follow_up_exchange",
            return_value=(_message("user", "Question", 1), assistant),
        ),
    ):
        result = FollowUpChatService.answer_follow_up(
            MagicMock(),
            CASE_A,
            "Question",
            llm_callable=lambda _q, _g: {
                "answer": "Answer",
                "answer_type": "fact",
                "citations": [],
                "disclosures": [],
                "facts_needed": [],
                "requires_report_regen": False,
                "suggested_actions": [],
            },
        )

    assert result["case_memory_update_status"] == "projection_failed"


def test_case_isolation_memory_and_assets():
    case_a = _case(
        case_uuid=CASE_A,
        known_facts={"grievant_name": "Pat Lee", "issue": "leave"},
    )
    case_b = _case(
        case_uuid=CASE_B,
        known_facts={"grievant_name": "Sam Rivera", "issue": "overtime"},
    )
    foreign_asset_uuid = "bbbbbbbb-cccc-4ddd-8eee-ffffffffffff"
    asset_b = SimpleNamespace(
        asset_uuid=foreign_asset_uuid,
        case_uuid=CASE_B,
        original_filename="b.pdf",
        stored_filename="b.pdf",
        mime_type="application/pdf",
        size_bytes=10,
        asset_category="uploaded_document",
        status="active",
        asset_metadata={},
    )

    # Retrieval query for A must not include B facts.
    query_a = FollowUpChatService.build_chat_retrieval_query(
        "Was leave cancelled?",
        known_facts=case_a.known_facts,
    )
    assert "Sam Rivera" not in query_a
    assert "overtime" not in query_a

    db = MagicMock()
    # First query (case-scoped) returns None; second finds foreign asset.
    db.query.return_value.filter.return_value.first.side_effect = [None, asset_b]
    service = CaseAssetService(db)
    resolved = service.resolve_upload_refs_for_context(CASE_A, [foreign_asset_uuid])
    assert resolved[0]["rejected"] is True
    assert resolved[0]["reason"] == "asset_not_on_case"
    assert resolved[0]["asset_uuid"] is None

    # Grounding packages remain case-scoped by construction.
    with patch.object(
        CaseService,
        "build_restored_interaction_context",
        return_value={"known_facts": case_a.known_facts, "case_state": {"uuid": CASE_A}},
    ):
        package = FollowUpChatService.build_memory_only_grounding_package(
            case_a,
            db=MagicMock(),
            question="Was leave cancelled?",
            attach_retrieval=False,
        )
    assert package["case_uuid"] == CASE_A
    assert package["known_facts"]["grievant_name"] == "Pat Lee"
    assert case_b.known_facts["grievant_name"] not in str(package["known_facts"])


def test_generate_analysis_still_preview_only():
    service = CaseWorkspaceActionService(MagicMock())
    inspection = _inspection(_case())
    preview = {
        "temporary": True,
        "persisted": False,
        "review_mode": "read_only",
        "editable": False,
        "suggested_version_number_if_saved": 1,
        "report_data": {"report": {"quick_assessment": {"summary": "ok"}}},
        "ranked_authorities": [],
        "issue_analysis": {},
        "evidence_items": [],
        "retrieval_gaps": {},
        "source_coverage_audit": [],
        "report_summary": {"primary_issue": "leave"},
    }
    with (
        patch.object(service, "_inspect_workspace", return_value=inspection),
        patch.object(
            CaseService, "build_analysis_report_preview", return_value=preview
        ),
        patch.object(CaseService, "generate_report_version") as mock_persist,
        patch.object(CaseService, "persist_report_version_from_preview") as mock_save,
    ):
        result = service.generate_analysis_report(CASE_A)

    assert result.analysis_preview_ready is True
    assert result.official_artifact_created is False
    assert result.current_report_version_number is None
    mock_persist.assert_not_called()
    mock_save.assert_not_called()
