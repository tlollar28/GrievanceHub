"""Functional contracts for bounded retrieval agents.

All embeddings and database results are local fakes; no test calls OpenAI.
"""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services.knowledge_retrieval_service import KnowledgeRetrievalService
from app.services.retrieval.base_agent import materially_overlaps
from app.services.retrieval.contract_agent import ContractAgent
from app.services.retrieval.models import (
    AgentFailure,
    AgentIdentity,
    AgentRetrievalResult,
    OrchestrationResult,
    RetrievalAuthorizationContext,
    RetrievalEvidence,
    RetrievalRequest,
)
from app.services.retrieval.orchestrator import RetrievalOrchestrator
from app.services.retrieval.supervisor_manual_agent import SupervisorManualAgent


EMBEDDING = [0.0] * 1536
AUTH = RetrievalAuthorizationContext.global_corpus(principal_id="test")


class _MappingResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return list(self._rows)


class StubSession:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.statements = []
        self.rollback_count = 0

    def execute(self, statement):
        self.statements.append(statement)
        response = self.responses.pop(0) if self.responses else []
        if isinstance(response, Exception):
            raise response
        return _MappingResult(response)

    def rollback(self):
        self.rollback_count += 1


def _row(
    *,
    source_document_id=1,
    canonical_source_id="contract-main",
    source_title="National Agreement",
    source_type="CONTRACT",
    source_version="2022-2025",
    source_sha256="a" * 64,
    processed_sha256="a" * 64,
    processing_strategy="generic_pdf_v1",
    chunk_id=11,
    chunk_index=2,
    page_number=44,
    chunk_text="Article 15 gives the union grievance rights and a contractual remedy.",
    chunk_metadata=None,
    raw_vector_distance=0.1,
):
    return {
        "source_document_id": source_document_id,
        "canonical_source_id": canonical_source_id,
        "source_title": source_title,
        "source_type": source_type,
        "source_version": source_version,
        "source_sha256": source_sha256,
        "processed_sha256": processed_sha256,
        "processing_strategy": processing_strategy,
        "chunk_id": chunk_id,
        "chunk_index": chunk_index,
        "page_number": page_number,
        "chunk_text": chunk_text,
        "chunk_metadata": chunk_metadata or {"section": "15", "page": page_number},
        "raw_vector_distance": raw_vector_distance,
    }


def _evidence(
    *,
    source_document_id=1,
    canonical_source_id="contract-main",
    source_title="National Agreement",
    source_type="CONTRACT",
    chunk_id=11,
    chunk_index=2,
    page_number=44,
    chunk_text="Article 15 grievance language.",
    score=0.9,
    distance=0.1,
    agent="ContractAgent",
    domain="contract",
    role="contract_controlling",
):
    return RetrievalEvidence(
        source_document_id=source_document_id,
        canonical_source_id=canonical_source_id,
        source_title=source_title,
        source_type=source_type,
        source_version="2022-2025",
        source_sha256="a" * 64,
        chunk_id=chunk_id,
        chunk_index=chunk_index,
        page_number=page_number,
        chunk_text=chunk_text,
        raw_vector_distance=distance,
        raw_vector_similarity=1.0 - distance,
        normalized_score=score,
        final_relevance_score=score,
        retrieval_agent=agent,
        retrieval_domain=domain,
        evidence_role=role,
        processing_strategy="generic_pdf_v1",
        safe_chunk_metadata={"page": page_number},
    )


class FakeAgent:
    def __init__(self, name, domain, result):
        self.identity = AgentIdentity(
            name=name,
            domain=domain,
            supported_source_types=frozenset(),
        )
        self.result = result
        self.embedding_objects = []

    def is_eligible(self, request):
        return self.identity.domain in request.domains and (
            not request.agent_names or self.identity.name in request.agent_names
        )

    def retrieve(self, _db, _request, _authorization, query_embedding):
        self.embedding_objects.append(query_embedding)
        if callable(self.result):
            return self.result()
        return self.result


def _validated(request: RetrievalRequest):
    return RetrievalOrchestrator(
        embedding_provider=lambda _query: EMBEDDING
    )._validate_request(request)


def test_shared_result_contract_is_complete_and_safe_to_serialize():
    evidence = _evidence()
    payload = evidence.to_dict()
    required = {
        "source_document_id",
        "canonical_source_id",
        "source_title",
        "source_type",
        "source_version",
        "source_sha256",
        "chunk_id",
        "chunk_index",
        "page_number",
        "chunk_text",
        "raw_vector_distance",
        "raw_vector_similarity",
        "normalized_score",
        "final_relevance_score",
        "retrieval_agent",
        "processing_strategy",
        "safe_chunk_metadata",
        "content_trust",
    }
    assert required <= payload.keys()
    assert payload["content_trust"] == "untrusted_evidence"
    assert "embedding" not in payload
    assert "local_path" not in payload


def test_shared_result_contract_has_no_orm_entity_or_vector_field():
    evidence = _evidence()
    assert not hasattr(evidence, "chunk")
    assert not hasattr(evidence, "embedding")
    assert not hasattr(evidence, "local_path")


def test_shared_result_serialization_is_deterministic():
    evidence = replace(
        _evidence(),
        safe_chunk_metadata={"section": "15", "page": 44},
    )
    assert evidence.to_dict() == evidence.to_dict()
    assert list(evidence.to_dict()["safe_chunk_metadata"]) == ["page", "section"]


def test_contract_agent_owns_repository_contract_taxonomy_not_supervisor_manual():
    assert ContractAgent.identity.supported_source_types == {
        "ARBITRATION",
        "CIM",
        "CONTRACT",
        "ELM",
        "LMOU",
    }
    assert "SUPERVISOR_MANUAL" not in ContractAgent.identity.supported_source_types


def test_contract_agent_retrieves_provenance_with_one_projection_query():
    session = StubSession([_row()])
    result = ContractAgent().retrieve(
        session,
        _validated(RetrievalRequest(query="contract grievance rights", domain="contract")),
        AUTH,
        EMBEDDING,
    )
    assert result.status == "success"
    assert result.sql_query_count == 1
    assert len(session.statements) == 1
    evidence = result.results[0]
    assert evidence.canonical_source_id == "contract-main"
    assert evidence.source_version == "2022-2025"
    assert evidence.page_number == 44
    assert evidence.source_sha256 == "a" * 64
    assert evidence.retrieval_agent == "ContractAgent"
    assert evidence.evidence_role == "contract_controlling"


def test_contract_agent_legacy_pre_w5_provenance_is_explicit():
    row = _row(processed_sha256=None, processing_strategy=None)
    result = ContractAgent().retrieve(
        StubSession([row]),
        _validated(RetrievalRequest(query="contract grievance", domain="contract")),
        AUTH,
        EMBEDDING,
    )
    assert result.results[0].processing_strategy == "legacy_pre_w5_index"
    assert result.results[0].source_sha256 == "a" * 64


def test_contract_agent_statement_filters_source_state_and_limits_in_sql():
    agent = ContractAgent()
    request = _validated(
        RetrievalRequest(
            query="contract",
            domain="contract",
            candidate_limit=7,
            per_agent_result_limit=7,
        )
    )
    statement = agent._candidate_statement(request, AUTH, EMBEDDING)
    sql = str(statement)
    assert "source_documents.source_type IN" in sql
    assert "source_documents.processing_status" in sql
    assert "source_documents.is_current IS true" in sql
    assert "source_chunks.embedding IS NOT NULL" in sql
    assert statement._limit_clause.value == 7


def test_contract_agent_returns_no_eligible_sources_for_empty_projection():
    result = ContractAgent().retrieve(
        StubSession([]),
        _validated(RetrievalRequest(query="contract", domain="contract")),
        AUTH,
        EMBEDDING,
    )
    assert result.status == "no_eligible_sources"
    assert result.results == ()


def test_contract_agent_returns_no_relevant_results_below_threshold():
    result = ContractAgent().retrieve(
        StubSession([_row(raw_vector_distance=0.9)]),
        _validated(RetrievalRequest(query="contract", domain="contract")),
        AUTH,
        EMBEDDING,
    )
    assert result.status == "no_relevant_results"
    assert result.threshold_rejected_count == 1


def test_contract_agent_accepts_mid_similarity_when_combined_score_passes():
    """Candidate admission uses a lower floor; final acceptance uses combined score."""
    result = ContractAgent().retrieve(
        StubSession(
            [
                _row(
                    raw_vector_distance=0.50,
                    chunk_text=(
                        "Article 15 grievance procedure grants contractual remedy "
                        "rights when management violates the agreement."
                    ),
                )
            ]
        ),
        _validated(
            RetrievalRequest(
                query="contract article grievance procedure remedy rights",
                domain="contract",
            )
        ),
        AUTH,
        EMBEDDING,
    )
    assert result.status == "success"
    assert len(result.results) == 1
    assert result.results[0].raw_vector_similarity == pytest.approx(0.50)


def test_contract_agent_failure_is_structured_and_redacted():
    result = ContractAgent().retrieve(
        StubSession(RuntimeError("postgresql://secret@host/private")),
        _validated(RetrievalRequest(query="contract", domain="contract")),
        AUTH,
        EMBEDDING,
    )
    assert result.status == "failure"
    payload = result.to_dict()
    assert payload["failure"]["code"] == "agent_retrieval_failed"
    assert "secret" not in str(payload)


def test_supervisor_manual_agent_owns_exact_source_type():
    assert SupervisorManualAgent.identity.supported_source_types == {
        "SUPERVISOR_MANUAL"
    }


def test_supervisor_manual_agent_preserves_manual_identity_and_noncontrolling_role():
    row = _row(
        canonical_source_id="supervisor_manual_el921_grievance_2015",
        source_title="EL-921 Supervisor Guide",
        source_type="SUPERVISOR_MANUAL",
        source_version="2015-04",
        chunk_text="Supervisors must investigate grievances and document the Step 1 meeting.",
    )
    result = SupervisorManualAgent().retrieve(
        StubSession([row]),
        _validated(
            RetrievalRequest(
                query="supervisor grievance handling documentation",
                domain="supervisor_manual",
            )
        ),
        AUTH,
        EMBEDDING,
    )
    evidence = result.results[0]
    assert evidence.canonical_source_id.startswith("supervisor_manual_el921")
    assert evidence.source_type == "SUPERVISOR_MANUAL"
    assert evidence.source_version == "2015-04"
    assert evidence.evidence_role == "supervisory_guidance_non_controlling"


def test_supervisor_agent_cross_manual_results_enforce_per_source_diversity():
    rows = []
    for index, source_id in enumerate(
        (
            "supervisor_manual_f21_time_attendance_2016",
            "supervisor_manual_f21_time_attendance_2016",
            "supervisor_manual_el801_safety_2020",
            "supervisor_manual_el921_grievance_2015",
        ),
        start=1,
    ):
        rows.append(
            _row(
                source_document_id=index if index > 2 else 1,
                canonical_source_id=source_id,
                source_type="SUPERVISOR_MANUAL",
                chunk_id=100 + index,
                chunk_index=index,
                chunk_text=(
                    f"Supervisor documentation attendance safety grievance procedure {index} "
                    + "distinct guidance words " * index
                ),
                raw_vector_distance=0.05 + index / 100,
            )
        )
    result = SupervisorManualAgent().retrieve(
        StubSession(rows),
        _validated(
            RetrievalRequest(
                query="supervisor attendance safety grievance documentation",
                domain="supervisor_manual",
                per_source_result_limit=1,
                per_agent_result_limit=6,
            )
        ),
        AUTH,
        EMBEDDING,
    )
    ids = [item.canonical_source_id for item in result.results]
    assert ids.count("supervisor_manual_f21_time_attendance_2016") == 1
    assert set(ids) == {
        "supervisor_manual_f21_time_attendance_2016",
        "supervisor_manual_el801_safety_2020",
        "supervisor_manual_el921_grievance_2015",
    }


def test_material_overlap_dedupes_exact_text_across_sources():
    left = _evidence(chunk_text="same grievance language " * 12)
    same_source = replace(left, chunk_id=12, chunk_index=3)
    other_source = replace(
        left,
        source_document_id=2,
        canonical_source_id="other",
        chunk_id=22,
    )
    assert materially_overlaps(left, same_source) is True
    assert materially_overlaps(left, other_source) is True


@pytest.mark.parametrize(
    ("domain", "expected"),
    [
        ("contract", ("ContractAgent",)),
        ("supervisor_manual", ("SupervisorManualAgent",)),
        ("combined", ("ContractAgent", "SupervisorManualAgent")),
    ],
)
def test_orchestrator_explicit_domain_routing(domain, expected):
    contract = FakeAgent(
        "ContractAgent",
        "contract",
        AgentRetrievalResult(AgentIdentity("ContractAgent", "contract", frozenset()), "no_eligible_sources"),
    )
    supervisor = FakeAgent(
        "SupervisorManualAgent",
        "supervisor_manual",
        AgentRetrievalResult(
            AgentIdentity("SupervisorManualAgent", "supervisor_manual", frozenset()),
            "no_eligible_sources",
        ),
    )
    result = RetrievalOrchestrator(
        [contract, supervisor],
        embedding_provider=lambda _query: EMBEDDING,
    ).retrieve(StubSession(), RetrievalRequest(query="neutral question", domain=domain), AUTH)
    assert result.selected_agents == expected


def test_orchestrator_auto_routing_is_deterministic_and_does_not_run_all_agents():
    contract_result = AgentRetrievalResult(
        AgentIdentity("ContractAgent", "contract", frozenset()),
        "no_eligible_sources",
    )
    supervisor_result = AgentRetrievalResult(
        AgentIdentity("SupervisorManualAgent", "supervisor_manual", frozenset()),
        "no_eligible_sources",
    )
    orchestrator = RetrievalOrchestrator(
        [
            FakeAgent("ContractAgent", "contract", contract_result),
            FakeAgent("SupervisorManualAgent", "supervisor_manual", supervisor_result),
        ],
        embedding_provider=lambda _query: EMBEDDING,
    )
    supervisor = orchestrator.retrieve(
        StubSession(),
        RetrievalRequest(query="What must a supervisor document for attendance control?"),
        AUTH,
    )
    contract = orchestrator.retrieve(
        StubSession(),
        RetrievalRequest(query="What does Article 15 of the agreement require?"),
        AUTH,
    )
    assert supervisor.selected_agents == ("SupervisorManualAgent",)
    assert contract.selected_agents == ("ContractAgent",)


def test_orchestrator_reuses_one_embedding_object_across_agents():
    calls = []
    contract_identity = AgentIdentity("ContractAgent", "contract", frozenset())
    supervisor_identity = AgentIdentity(
        "SupervisorManualAgent", "supervisor_manual", frozenset()
    )
    contract = FakeAgent(
        "ContractAgent",
        "contract",
        AgentRetrievalResult(contract_identity, "success", (_evidence(),)),
    )
    supervisor = FakeAgent(
        "SupervisorManualAgent",
        "supervisor_manual",
        AgentRetrievalResult(
            supervisor_identity,
            "success",
            (
                _evidence(
                    source_document_id=2,
                    canonical_source_id="el921",
                    source_type="SUPERVISOR_MANUAL",
                    chunk_id=20,
                    agent="SupervisorManualAgent",
                    domain="supervisor_manual",
                    role="supervisory_guidance_non_controlling",
                ),
            ),
        ),
    )

    def embed(_query):
        calls.append(1)
        return EMBEDDING

    RetrievalOrchestrator(
        [contract, supervisor],
        embedding_provider=embed,
    ).retrieve(
        StubSession(),
        RetrievalRequest(query="contract and supervisor procedure", domain="combined"),
        AUTH,
    )
    assert len(calls) == 1
    assert contract.embedding_objects[0] is supervisor.embedding_objects[0]


def test_orchestrator_partial_failure_retains_successful_results_and_rolls_back():
    good = _evidence()
    contract = FakeAgent(
        "ContractAgent",
        "contract",
        AgentRetrievalResult(
            AgentIdentity("ContractAgent", "contract", frozenset()),
            "success",
            (good,),
        ),
    )
    supervisor = FakeAgent(
        "SupervisorManualAgent",
        "supervisor_manual",
        AgentRetrievalResult(
            AgentIdentity("SupervisorManualAgent", "supervisor_manual", frozenset()),
            "failure",
            failure=AgentFailure("agent_retrieval_failed", "Unavailable", True, "TimeoutError"),
        ),
    )
    session = StubSession()
    result = RetrievalOrchestrator(
        [contract, supervisor],
        embedding_provider=lambda _query: EMBEDDING,
    ).retrieve(
        session,
        RetrievalRequest(query="contract and supervisor", domain="combined"),
        AUTH,
    )
    assert result.status == "partial_failure"
    assert result.partial is True
    assert result.results == (good,)
    assert session.rollback_count == 1
    assert "traceback" not in str(result.to_dict()).lower()


def test_orchestrator_all_agent_failure_is_structured():
    failure = AgentFailure(
        "agent_retrieval_failed",
        "The retrieval source was temporarily unavailable.",
        True,
        "RuntimeError",
    )
    agents = [
        FakeAgent(
            "ContractAgent",
            "contract",
            AgentRetrievalResult(
                AgentIdentity("ContractAgent", "contract", frozenset()),
                "failure",
                failure=failure,
            ),
        ),
        FakeAgent(
            "SupervisorManualAgent",
            "supervisor_manual",
            AgentRetrievalResult(
                AgentIdentity("SupervisorManualAgent", "supervisor_manual", frozenset()),
                "failure",
                failure=failure,
            ),
        ),
    ]
    result = RetrievalOrchestrator(
        agents,
        embedding_provider=lambda _query: EMBEDDING,
    ).retrieve(
        StubSession(),
        RetrievalRequest(query="contract and supervisor", domain="combined"),
        AUTH,
    )
    assert result.status == "complete_failure"
    assert len(result.failures) == 2


def test_orchestrator_stable_merge_removes_exact_duplicate_and_keeps_provenance():
    strongest = _evidence(score=0.95)
    duplicate = replace(
        strongest,
        retrieval_agent="SupervisorManualAgent",
        retrieval_domain="supervisor_manual",
        evidence_role="supervisory_guidance_non_controlling",
        final_relevance_score=0.8,
    )
    results = [
        AgentRetrievalResult(
            AgentIdentity("ContractAgent", "contract", frozenset()),
            "success",
            (strongest,),
        ),
        AgentRetrievalResult(
            AgentIdentity("SupervisorManualAgent", "supervisor_manual", frozenset()),
            "success",
            (duplicate,),
        ),
    ]
    merged, duplicate_count, _capped = RetrievalOrchestrator._merge_results(
        results,
        _validated(
            RetrievalRequest(query="contract supervisor", domain="combined")
        ),
    )
    assert duplicate_count == 1
    assert len(merged) == 1
    assert merged[0].retrieval_agent == "ContractAgent"
    assert len(merged[0].alternate_provenance) == 1


def test_orchestrator_embedding_failure_is_safe_complete_failure():
    def fail(_query):
        raise RuntimeError("api-key-secret")

    result = RetrievalOrchestrator(embedding_provider=fail).retrieve(
        StubSession(),
        RetrievalRequest(query="contract", domain="contract"),
        AUTH,
    )
    assert result.status == "complete_failure"
    assert result.failures[0].code == "embedding_service_unavailable"
    assert "api-key-secret" not in str(result.to_dict())


def test_legacy_search_adapter_preserves_expected_shape_and_fields():
    orchestration = OrchestrationResult(
        status="success",
        results=(_evidence(),),
        selected_agents=("ContractAgent",),
    )
    with patch.object(
        KnowledgeRetrievalService,
        "retrieve_with_agents",
        return_value=orchestration,
    ):
        payload = KnowledgeRetrievalService.search_with_agents(
            SimpleNamespace(),
            "contract question",
            AUTH,
            domain="contract",
            limit_per_source=3,
        )
    assert payload["query"] == "contract question"
    assert set(
        ("CONTRACT", "ELM", "CIM", "LMOU", "ARBITRATION", "SUPERVISOR_MANUAL")
    ) <= set(payload["results_by_source"])
    item = payload["results_by_source"]["CONTRACT"][0]
    assert item["source_id"] == "contract-main"
    assert item["page"] == 44
    assert item["retrieval_metadata"]["retrieval_agent"] == "ContractAgent"
