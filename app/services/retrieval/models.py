"""Safe shared contracts for retrieval agents.

The contracts deliberately contain projections rather than SQLAlchemy entities.
Embedding vectors, local paths, credentials, and exception traces have no field
through which they can be serialized.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


RETRIEVAL_STATUSES = frozenset(
    {
        "success",
        "no_eligible_sources",
        "no_relevant_results",
        "partial_failure",
        "complete_failure",
        "authorization_failure",
        "validation_failure",
    }
)

AGENT_STATUSES = frozenset(
    {
        "success",
        "no_eligible_sources",
        "no_relevant_results",
        "failure",
        "skipped",
    }
)


@dataclass(frozen=True)
class RetrievalAuthorizationContext:
    """Trusted caller scope consumed by SQL candidate selection.

    The application currently has no persisted user/role model. Callers must
    therefore construct this context explicitly; the retrieval layer never
    infers organization access from a query, case UUID, or client filter.
    """

    authenticated: bool
    principal_id: str | None = None
    allow_global_sources: bool = True
    allowed_organization_ids: frozenset[int] = frozenset()
    is_admin: bool = False
    allow_all_organizations: bool = False
    correlation_id: str | None = None

    @classmethod
    def unauthenticated(cls) -> "RetrievalAuthorizationContext":
        return cls(authenticated=False, allow_global_sources=False)

    @classmethod
    def global_corpus(
        cls,
        *,
        principal_id: str = "trusted-internal",
        correlation_id: str | None = None,
    ) -> "RetrievalAuthorizationContext":
        return cls(
            authenticated=True,
            principal_id=principal_id,
            allow_global_sources=True,
            correlation_id=correlation_id,
        )

    @classmethod
    def for_organizations(
        cls,
        organization_ids: set[int] | frozenset[int],
        *,
        principal_id: str,
        include_global: bool = True,
        correlation_id: str | None = None,
    ) -> "RetrievalAuthorizationContext":
        return cls(
            authenticated=True,
            principal_id=principal_id,
            allow_global_sources=include_global,
            allowed_organization_ids=frozenset(organization_ids),
            correlation_id=correlation_id,
        )


@dataclass(frozen=True)
class RetrievalRequest:
    """Caller request before server-side validation and capping."""

    query: str
    domain: str = "auto"
    agent_names: tuple[str, ...] = ()
    workflow_context: str | None = None
    candidate_limit: int | None = None
    result_limit: int | None = None
    per_agent_result_limit: int | None = None
    per_source_result_limit: int | None = None
    relevance_threshold: float | None = None
    source_types: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()
    include_diagnostics: bool = False


@dataclass(frozen=True)
class ValidatedRetrievalRequest:
    """Normalized request with only bounded, allowlisted values."""

    query: str
    domains: tuple[str, ...]
    agent_names: tuple[str, ...]
    workflow_context: str | None
    candidate_limit: int
    result_limit: int
    per_agent_result_limit: int
    per_source_result_limit: int
    relevance_threshold: float
    source_types: tuple[str, ...]
    source_ids: tuple[str, ...]
    include_diagnostics: bool


@dataclass(frozen=True)
class AgentIdentity:
    name: str
    domain: str
    supported_source_types: frozenset[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "domain": self.domain,
            "supported_source_types": sorted(self.supported_source_types),
        }


@dataclass(frozen=True)
class CitationProvenance:
    source_document_id: int
    canonical_source_id: str
    source_title: str
    source_type: str
    source_version: str | None
    source_sha256: str | None
    chunk_id: int
    chunk_index: int
    page_number: int | None
    retrieval_agent: str
    processing_strategy: str | None
    evidence_role: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_document_id": self.source_document_id,
            "canonical_source_id": self.canonical_source_id,
            "source_title": self.source_title,
            "source_type": self.source_type,
            "source_version": self.source_version,
            "source_sha256": self.source_sha256,
            "chunk_id": self.chunk_id,
            "chunk_index": self.chunk_index,
            "page_number": self.page_number,
            "retrieval_agent": self.retrieval_agent,
            "processing_strategy": self.processing_strategy,
            "evidence_role": self.evidence_role,
        }


@dataclass(frozen=True)
class RetrievalEvidence:
    """Citation-ready evidence with no ORM or vector leakage."""

    source_document_id: int
    canonical_source_id: str
    source_title: str
    source_type: str
    source_version: str | None
    source_sha256: str | None
    chunk_id: int
    chunk_index: int
    page_number: int | None
    chunk_text: str
    raw_vector_distance: float
    raw_vector_similarity: float
    normalized_score: float
    final_relevance_score: float
    retrieval_agent: str
    retrieval_domain: str
    evidence_role: str
    processing_strategy: str | None
    safe_chunk_metadata: Mapping[str, Any] = field(default_factory=dict)
    alternate_provenance: tuple[CitationProvenance, ...] = ()
    content_trust: str = "untrusted_evidence"

    @property
    def citation(self) -> CitationProvenance:
        return CitationProvenance(
            source_document_id=self.source_document_id,
            canonical_source_id=self.canonical_source_id,
            source_title=self.source_title,
            source_type=self.source_type,
            source_version=self.source_version,
            source_sha256=self.source_sha256,
            chunk_id=self.chunk_id,
            chunk_index=self.chunk_index,
            page_number=self.page_number,
            retrieval_agent=self.retrieval_agent,
            processing_strategy=self.processing_strategy,
            evidence_role=self.evidence_role,
        )

    @property
    def chunk_key(self) -> tuple[int, int]:
        return (self.source_document_id, self.chunk_id)

    def to_dict(self, *, include_text: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            **self.citation.to_dict(),
            "raw_vector_distance": round(self.raw_vector_distance, 8),
            "raw_vector_similarity": round(self.raw_vector_similarity, 8),
            "normalized_score": round(self.normalized_score, 8),
            "final_relevance_score": round(self.final_relevance_score, 8),
            "retrieval_domain": self.retrieval_domain,
            "safe_chunk_metadata": {
                key: self.safe_chunk_metadata[key]
                for key in sorted(self.safe_chunk_metadata)
            },
            "alternate_provenance": [
                item.to_dict() for item in self.alternate_provenance
            ],
            "content_trust": self.content_trust,
        }
        if include_text:
            payload["chunk_text"] = self.chunk_text
        return payload


@dataclass(frozen=True)
class AgentFailure:
    code: str
    message: str
    retriable: bool = False
    error_class: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "retriable": self.retriable,
            "error_class": self.error_class,
        }


@dataclass(frozen=True)
class AgentRetrievalResult:
    identity: AgentIdentity
    status: str
    results: tuple[RetrievalEvidence, ...] = ()
    failure: AgentFailure | None = None
    candidate_count: int = 0
    accepted_count: int = 0
    threshold_rejected_count: int = 0
    duplicate_count: int = 0
    duration_ms: float = 0.0
    sql_query_count: int = 0

    def to_dict(
        self,
        *,
        include_text: bool = True,
        include_diagnostics: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "agent": self.identity.to_dict(),
            "status": self.status,
            "results": [
                result.to_dict(include_text=include_text) for result in self.results
            ],
            "failure": self.failure.to_dict() if self.failure else None,
        }
        if include_diagnostics:
            payload["diagnostics"] = {
                "candidate_count": self.candidate_count,
                "accepted_count": self.accepted_count,
                "threshold_rejected_count": self.threshold_rejected_count,
                "duplicate_count": self.duplicate_count,
                "duration_ms": round(self.duration_ms, 3),
                "sql_query_count": self.sql_query_count,
            }
        return payload


@dataclass(frozen=True)
class OrchestrationResult:
    status: str
    results: tuple[RetrievalEvidence, ...] = ()
    agent_results: tuple[AgentRetrievalResult, ...] = ()
    failures: tuple[AgentFailure, ...] = ()
    selected_agents: tuple[str, ...] = ()
    query_hash: str = ""
    partial: bool = False
    duration_ms: float = 0.0
    embedding_duration_ms: float = 0.0
    database_duration_ms: float = 0.0
    merge_duration_ms: float = 0.0
    duplicate_count: int = 0
    capped: bool = False

    def to_dict(
        self,
        *,
        include_text: bool = True,
        include_diagnostics: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": self.status,
            "partial": self.partial,
            "selected_agents": list(self.selected_agents),
            "results": [
                result.to_dict(include_text=include_text) for result in self.results
            ],
            "agent_results": [
                result.to_dict(
                    include_text=include_text,
                    include_diagnostics=include_diagnostics,
                )
                for result in self.agent_results
            ],
            "failures": [failure.to_dict() for failure in self.failures],
        }
        if include_diagnostics:
            payload["diagnostics"] = {
                "query_hash": self.query_hash,
                "duration_ms": round(self.duration_ms, 3),
                "embedding_duration_ms": round(self.embedding_duration_ms, 3),
                "database_duration_ms": round(self.database_duration_ms, 3),
                "merge_duration_ms": round(self.merge_duration_ms, 3),
                "duplicate_count": self.duplicate_count,
                "capped": self.capped,
                "sql_query_count": sum(
                    item.sql_query_count for item in self.agent_results
                ),
                "candidate_count": sum(
                    item.candidate_count for item in self.agent_results
                ),
                "returned_count": len(self.results),
            }
        return payload
