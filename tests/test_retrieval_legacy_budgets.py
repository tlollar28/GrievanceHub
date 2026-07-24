"""Budget and N+1 regression tests for legacy/migrated retrieval paths."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.retrieval_config import (
    LEGACY_MAX_DECOMPOSED_ISSUES,
    LEGACY_MAX_PROVIDER_CALLS,
    LEGACY_MAX_QUERIES_PER_ISSUE,
    LEGACY_MAX_TOTAL_EMBEDDING_CALLS,
)
from app.services.embedding_service import EmbeddingService
from app.services.knowledge_retrieval_service import KnowledgeRetrievalService
from app.services.retrieval.models import RetrievalAuthorizationContext
from tests.test_chat_source_retrieval import _orchestration
from app.services.follow_up_chat_service import FollowUpChatService


AUTH = RetrievalAuthorizationContext.global_corpus(principal_id="budget-test")
EMBEDDING = [0.0] * 1536


class CountingProvider:
    def __init__(self, source_type: str):
        self.source_type = source_type
        self.calls = 0

    def search(self, db, query_embedding, limit=5, *, authorization=None):
        self.calls += 1
        return []


def test_identical_expanded_queries_reuse_one_embedding_per_request():
    provider = CountingProvider("CONTRACT")
    create_calls = {"n": 0}

    def fake_embed(text):
        create_calls["n"] += 1
        return EMBEDDING

    with (
        patch.object(
            KnowledgeRetrievalService,
            "providers",
            [provider],
        ),
        patch.object(EmbeddingService, "create_embedding", side_effect=fake_embed),
    ):
        KnowledgeRetrievalService._retrieve_queries_into_pool(
            MagicMock(),
            queries=["same query", "same query", "same query"],
            limit_per_source=2,
            authorization=AUTH,
        )

    assert create_calls["n"] == 1
    assert provider.calls == 1


def test_per_issue_query_and_provider_budgets_are_enforced():
    provider = CountingProvider("CONTRACT")
    create_calls = {"n": 0}

    def fake_embed(text):
        create_calls["n"] += 1
        return EMBEDDING

    oversized = [f"query-{index}" for index in range(LEGACY_MAX_QUERIES_PER_ISSUE + 10)]
    budget = {
        "embedding_calls": 0,
        "provider_calls": 0,
        "candidate_chunks": 0,
    }
    with (
        patch.object(KnowledgeRetrievalService, "providers", [provider]),
        patch.object(EmbeddingService, "create_embedding", side_effect=fake_embed),
    ):
        KnowledgeRetrievalService._retrieve_queries_into_pool(
            MagicMock(),
            queries=oversized,
            limit_per_source=2,
            authorization=AUTH,
            budget=budget,
        )

    assert create_calls["n"] == LEGACY_MAX_QUERIES_PER_ISSUE
    assert budget["embedding_calls"] == LEGACY_MAX_QUERIES_PER_ISSUE
    assert budget["provider_calls"] == LEGACY_MAX_QUERIES_PER_ISSUE
    assert budget["provider_calls"] <= LEGACY_MAX_PROVIDER_CALLS
    assert budget["embedding_calls"] <= LEGACY_MAX_TOTAL_EMBEDDING_CALLS


def test_search_all_caps_decomposed_issues_and_returns_budget():
    issues = [
        {
            "issue_id": f"issue-{index}",
            "issue_type": "legal",
            "issue": f"Issue {index}",
        }
        for index in range(LEGACY_MAX_DECOMPOSED_ISSUES + 5)
    ]
    analysis = {
        "dispute_frame": {},
        "decomposed_issues": issues,
    }

    with (
        patch(
            "app.services.legal_issue_analyzer.LegalIssueAnalyzer.analyze",
            return_value=analysis,
        ),
        patch(
            "app.services.legal_issue_analyzer.LegalIssueAnalyzer.build_search_queries",
            return_value=["expanded"],
        ),
        patch(
            "app.services.knowledge_retrieval_service.collect_decomposed_issues",
            return_value=issues,
        ),
        patch(
            "app.services.knowledge_retrieval_service.extract_issue_keywords",
            return_value=["leave"],
        ),
        patch(
            "app.services.knowledge_retrieval_service.build_queries_for_issue",
            return_value=["leave query"],
        ),
        patch.object(
            KnowledgeRetrievalService,
            "_retrieve_queries_into_pool",
            return_value={},
        ) as mock_pool,
        patch.object(
            KnowledgeRetrievalService,
            "_get_indexed_source_types",
            return_value={"CONTRACT"},
        ),
        patch.object(
            KnowledgeRetrievalService,
            "_backfill_empty_issue_pools",
        ),
        patch.object(
            KnowledgeRetrievalService,
            "_backfill_missing_source_types",
            return_value=[],
        ),
        patch.object(
            KnowledgeRetrievalService,
            "_supplement_contract_leave_commitment_pool",
        ),
        patch(
            "app.services.knowledge_retrieval_service.merge_issue_retrieval_pools",
            return_value=([], {}),
        ),
    ):
        payload = KnowledgeRetrievalService.search_all(
            MagicMock(),
            "annual leave cancellation",
            AUTH,
            limit_per_source=3,
        )

    assert len(payload["decomposed_issues"]) == LEGACY_MAX_DECOMPOSED_ISSUES
    assert mock_pool.call_count >= 1
    assert payload["retrieval_budget"]["max_embedding_calls"] == (
        LEGACY_MAX_TOTAL_EMBEDDING_CALLS
    )


def test_provider_defaults_to_global_organization_filter():
    sql_holder = {}

    class CaptureSession:
        def query(self, *args, **kwargs):
            return self

        def options(self, *args, **kwargs):
            return self

        def join(self, *args, **kwargs):
            return self

        def filter(self, *args, **kwargs):
            sql_holder.setdefault("filters", []).extend(args)
            return self

        def order_by(self, *args, **kwargs):
            return self

        def limit(self, *args, **kwargs):
            return self

        def all(self):
            return []

    from app.services.providers.contract_provider import ContractProvider

    ContractProvider().search(CaptureSession(), EMBEDDING, limit=2, authorization=None)
    rendered = " ".join(str(item) for item in sql_holder.get("filters", []))
    assert "organization_id" in rendered.lower() or "IS NULL" in rendered


def test_follow_up_chat_uses_internal_orchestrator_helper():
    with patch.object(
        KnowledgeRetrievalService,
        "retrieve_global_corpus_internal",
        return_value=_orchestration(text="supervisor guidance text"),
    ) as mock_retrieve:
        result = FollowUpChatService.retrieve_indexed_source_passages(
            MagicMock(),
            "How should a supervisor conduct a Step 1 meeting?",
        )
    assert mock_retrieve.call_args.kwargs["principal_id"] == "follow-up-chat-internal"
    assert result["retrieval_status"] == "ok"
    assert result["retrieved_source_passages"][0]["content_trust"] == (
        "untrusted_evidence"
    )


def test_case_preview_uses_explicit_internal_search_helper():
    from app.services.case_service import CaseService

    case = SimpleNamespace(
        known_facts={"fact": "value"},
        initial_question="leave",
        title="Case",
        user_name="A",
        local_number="300",
        messages=[],
        report_versions=[],
    )
    with (
        patch.object(CaseService, "get_case", return_value=case),
        patch.object(CaseService, "build_analysis_question", return_value="leave"),
        patch.object(CaseService, "build_case_context", return_value={}),
        patch.object(
            KnowledgeRetrievalService,
            "search_global_corpus_internal",
            return_value={
                "all_chunks": [],
                "issue_analysis": {},
                "issue_keywords": [],
                "retrieval_gaps": [],
                "indexed_source_types": [],
                "source_coverage_audit": [],
            },
        ) as mock_search,
        patch(
            "app.services.case_service.AnalysisService.generate_report",
            return_value={"report": {}},
        ),
    ):
        CaseService.build_analysis_report_preview(MagicMock(), "case-uuid")

    assert mock_search.call_args.kwargs["principal_id"] == (
        "case-report-preview-internal"
    )
