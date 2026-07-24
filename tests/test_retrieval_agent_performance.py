"""Bounded-query and computational regression tests for retrieval agents.

Documented SQL budgets:
- one agent, any bounded result count: 1 statement;
- combined orchestration: 2 statements (one per selected agent);
- provenance hydration: included in those statements, 0 additional;
- legacy JSON adapter conversion: 0 additional.
"""

from __future__ import annotations

from unittest.mock import patch

from app.retrieval_config import (
    RETRIEVAL_MAX_CANDIDATE_LIMIT,
    RETRIEVAL_MAX_CHUNK_TEXT_CHARS,
    RETRIEVAL_MAX_PER_AGENT_RESULT_LIMIT,
    RETRIEVAL_MAX_RESPONSE_TEXT_CHARS,
    RETRIEVAL_MAX_TOTAL_RESULT_LIMIT,
)
from app.services.embedding_service import EmbeddingService
from app.services.knowledge_retrieval_service import KnowledgeRetrievalService
from app.services.retrieval.contract_agent import ContractAgent
from app.services.retrieval.models import (
    AgentIdentity,
    AgentRetrievalResult,
    RetrievalRequest,
)
from app.services.retrieval.orchestrator import RetrievalOrchestrator
from app.services.retrieval.supervisor_manual_agent import SupervisorManualAgent
from tests.test_retrieval_agents import (
    AUTH,
    EMBEDDING,
    FakeAgent,
    StubSession,
    _evidence,
    _row,
    _validated,
)


def _distinct_rows(count, *, source_type="CONTRACT", prefix="source"):
    return [
        _row(
            source_document_id=index + 1,
            canonical_source_id=f"{prefix}-{index}",
            source_type=source_type,
            chunk_id=1000 + index,
            chunk_index=index,
            page_number=index + 1,
            chunk_text=(
                f"Contract grievance rights remedy provision unique-{index} "
                + ("substantive language " * 5)
            ),
            raw_vector_distance=0.05 + (index / 10000),
        )
        for index in range(count)
    ]


def test_contract_query_count_is_one_for_one_or_many_results():
    request = _validated(
        RetrievalRequest(
            query="contract grievance rights remedy",
            domain="contract",
            candidate_limit=48,
            per_agent_result_limit=16,
            per_source_result_limit=1,
        )
    )
    one = StubSession(_distinct_rows(1))
    many = StubSession(_distinct_rows(16))
    one_result = ContractAgent().retrieve(one, request, AUTH, EMBEDDING)
    many_result = ContractAgent().retrieve(many, request, AUTH, EMBEDDING)
    assert one_result.sql_query_count == many_result.sql_query_count == 1
    assert len(one.statements) == len(many.statements) == 1
    assert len(many_result.results) > len(one_result.results)


def test_supervisor_query_count_is_one_across_all_three_manuals():
    rows = [
        _row(
            source_document_id=index,
            canonical_source_id=source_id,
            source_type="SUPERVISOR_MANUAL",
            chunk_id=200 + index,
            chunk_index=index,
            chunk_text=(
                "Supervisor attendance safety grievance documentation procedure "
                f"manual-{index} distinct text"
            ),
            raw_vector_distance=0.05 + index / 100,
        )
        for index, source_id in enumerate(
            (
                "supervisor_manual_el921_grievance_2015",
                "supervisor_manual_el801_safety_2020",
                "supervisor_manual_f21_time_attendance_2016",
            ),
            start=1,
        )
    ]
    session = StubSession(rows)
    result = SupervisorManualAgent().retrieve(
        session,
        _validated(
            RetrievalRequest(
                query="supervisor attendance safety grievance documentation",
                domain="supervisor_manual",
            )
        ),
        AUTH,
        EMBEDDING,
    )
    assert result.sql_query_count == 1
    assert len(session.statements) == 1
    assert len(result.results) == 3


def test_combined_orchestration_query_budget_is_two_with_batched_provenance():
    contract_rows = _distinct_rows(8)
    supervisor_rows = _distinct_rows(
        8,
        source_type="SUPERVISOR_MANUAL",
        prefix="manual",
    )
    session = StubSession(contract_rows, supervisor_rows)
    result = RetrievalOrchestrator(
        embedding_provider=lambda _query: EMBEDDING
    ).retrieve(
        session,
        RetrievalRequest(
            query="contract grievance and supervisor documentation procedure",
            domain="combined",
        ),
        AUTH,
    )
    assert len(session.statements) == 2
    assert sum(item.sql_query_count for item in result.agent_results) == 2
    assert result.to_dict(include_diagnostics=True)["diagnostics"]["sql_query_count"] == 2


def test_no_results_path_stays_within_one_query_per_selected_agent():
    session = StubSession([], [])
    result = RetrievalOrchestrator(
        embedding_provider=lambda _query: EMBEDDING
    ).retrieve(
        session,
        RetrievalRequest(query="contract supervisor", domain="combined"),
        AUTH,
    )
    assert result.status == "no_eligible_sources"
    assert len(session.statements) == 2


def test_legacy_adapter_adds_no_database_queries():
    session = StubSession(
        _distinct_rows(3),
        _distinct_rows(
            3,
            source_type="SUPERVISOR_MANUAL",
            prefix="manual",
        ),
    )
    with patch.object(EmbeddingService, "create_embedding", return_value=EMBEDDING):
        payload = KnowledgeRetrievalService.search_with_agents(
            session,
            "contract supervisor documentation",
            AUTH,
            domain="combined",
            limit_per_source=3,
            include_diagnostics=True,
        )
    assert len(session.statements) == 2
    assert payload["diagnostics"]["sql_query_count"] == 2


def test_caller_limits_are_capped_by_server_configuration():
    validated = _validated(
        RetrievalRequest(
            query="contract",
            domain="contract",
            candidate_limit=10_000,
            per_agent_result_limit=10_000,
            result_limit=10_000,
            per_source_result_limit=10_000,
        )
    )
    assert validated.candidate_limit == RETRIEVAL_MAX_CANDIDATE_LIMIT
    assert validated.per_agent_result_limit == RETRIEVAL_MAX_PER_AGENT_RESULT_LIMIT
    assert validated.result_limit == RETRIEVAL_MAX_TOTAL_RESULT_LIMIT
    assert validated.per_source_result_limit < validated.result_limit


def test_maximum_returned_results_and_response_text_are_bounded():
    contract_identity = AgentIdentity("ContractAgent", "contract", frozenset())
    supervisor_identity = AgentIdentity(
        "SupervisorManualAgent", "supervisor_manual", frozenset()
    )
    contract_evidence = tuple(
        _evidence(
            source_document_id=index + 1,
            canonical_source_id=f"contract-{index}",
            chunk_id=100 + index,
            chunk_text=(
                f"contract-{index}-"
                + "x" * (RETRIEVAL_MAX_CHUNK_TEXT_CHARS - len(f"contract-{index}-"))
            ),
            score=1.0 - index / 1000,
        )
        for index in range(RETRIEVAL_MAX_PER_AGENT_RESULT_LIMIT)
    )
    manual_evidence = tuple(
        _evidence(
            source_document_id=100 + index,
            canonical_source_id=f"manual-{index}",
            source_type="SUPERVISOR_MANUAL",
            chunk_id=500 + index,
            chunk_text=(
                f"manual-{index}-"
                + "x" * (RETRIEVAL_MAX_CHUNK_TEXT_CHARS - len(f"manual-{index}-"))
            ),
            score=0.9 - index / 1000,
            agent="SupervisorManualAgent",
            domain="supervisor_manual",
            role="supervisory_guidance_non_controlling",
        )
        for index in range(RETRIEVAL_MAX_PER_AGENT_RESULT_LIMIT)
    )
    result = RetrievalOrchestrator(
        [
            FakeAgent(
                "ContractAgent",
                "contract",
                AgentRetrievalResult(
                    contract_identity,
                    "success",
                    contract_evidence,
                ),
            ),
            FakeAgent(
                "SupervisorManualAgent",
                "supervisor_manual",
                AgentRetrievalResult(
                    supervisor_identity,
                    "success",
                    manual_evidence,
                ),
            ),
        ],
        embedding_provider=lambda _query: EMBEDDING,
    ).retrieve(
        StubSession(),
        RetrievalRequest(
            query="contract supervisor",
            domain="combined",
            result_limit=10_000,
        ),
        AUTH,
    )
    assert len(result.results) <= RETRIEVAL_MAX_TOTAL_RESULT_LIMIT
    assert sum(len(item.chunk_text) for item in result.results) <= RETRIEVAL_MAX_RESPONSE_TEXT_CHARS
    assert result.capped is True


def test_deduplication_maximum_input_is_bounded_and_deterministic():
    identity = AgentIdentity("ContractAgent", "contract", frozenset())
    evidence = tuple(
        _evidence(
            source_document_id=index + 1,
            canonical_source_id=f"source-{index}",
            chunk_id=index + 1,
            chunk_text=f"unique bounded candidate {index} " * 20,
            score=0.8,
        )
        for index in range(RETRIEVAL_MAX_PER_AGENT_RESULT_LIMIT)
    )
    request = _validated(
        RetrievalRequest(
            query="contract",
            domain="contract",
            per_agent_result_limit=10_000,
            result_limit=10_000,
        )
    )
    agent_results = (AgentRetrievalResult(identity, "success", evidence),)
    first = RetrievalOrchestrator._merge_results(agent_results, request)
    second = RetrievalOrchestrator._merge_results(agent_results, request)
    assert first == second
    assert len(first[0]) <= RETRIEVAL_MAX_PER_AGENT_RESULT_LIMIT


def test_one_embedding_call_for_maximum_combined_request():
    calls = []
    session = StubSession(
        _distinct_rows(RETRIEVAL_MAX_CANDIDATE_LIMIT),
        _distinct_rows(
            RETRIEVAL_MAX_CANDIDATE_LIMIT,
            source_type="SUPERVISOR_MANUAL",
            prefix="manual",
        ),
    )
    RetrievalOrchestrator(
        embedding_provider=lambda _query: calls.append(1) or EMBEDDING
    ).retrieve(
        session,
        RetrievalRequest(
            query="contract supervisor",
            domain="combined",
            candidate_limit=10_000,
        ),
        AUTH,
    )
    assert calls == [1]
    assert len(session.statements) == 2
