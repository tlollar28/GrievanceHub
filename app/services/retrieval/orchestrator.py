"""Deterministic high-level coordination for bounded retrieval agents."""

from __future__ import annotations

import hashlib
import logging
import math
import re
import unicodedata
from dataclasses import replace
from time import perf_counter
from typing import Callable, Iterable, Sequence

from sqlalchemy.orm import Session

from app.retrieval_config import (
    MIN_COMBINED_RETRIEVAL_SCORE,
    RETRIEVAL_DEFAULT_CANDIDATE_LIMIT,
    RETRIEVAL_DEFAULT_PER_AGENT_RESULT_LIMIT,
    RETRIEVAL_DEFAULT_PER_SOURCE_RESULT_LIMIT,
    RETRIEVAL_DEFAULT_TOTAL_RESULT_LIMIT,
    RETRIEVAL_EMBEDDING_TIMEOUT_SECONDS,
    RETRIEVAL_ENABLED_AGENTS,
    RETRIEVAL_MAX_CANDIDATE_LIMIT,
    RETRIEVAL_MAX_PER_AGENT_RESULT_LIMIT,
    RETRIEVAL_MAX_PER_SOURCE_RESULT_LIMIT,
    RETRIEVAL_MAX_QUERY_CHARS,
    RETRIEVAL_MAX_RESPONSE_TEXT_CHARS,
    RETRIEVAL_MAX_SOURCE_DOMAINS,
    RETRIEVAL_MAX_SOURCE_FILTERS,
    RETRIEVAL_MAX_TOTAL_RESULT_LIMIT,
)
from app.services.embedding_service import EmbeddingService
from app.services.retrieval.base_agent import RetrievalAgent, materially_overlaps
from app.services.retrieval.contract_agent import (
    CONTRACT_SOURCE_TYPES,
    ContractAgent,
)
from app.services.retrieval.models import (
    AgentFailure,
    AgentRetrievalResult,
    OrchestrationResult,
    RetrievalAuthorizationContext,
    RetrievalEvidence,
    RetrievalRequest,
    ValidatedRetrievalRequest,
)
from app.services.retrieval.supervisor_manual_agent import SupervisorManualAgent


logger = logging.getLogger(__name__)

ALLOWED_DOMAINS = frozenset(
    {
        "auto",
        "combined",
        "contract",
        "supervisor_manual",
    }
)
ALLOWED_WORKFLOW_CONTEXTS = frozenset(
    {
        "case_chat",
        "contract_analysis",
        "generic",
        "grievance_analysis",
        "report_evidence",
        "supervisor_guidance",
    }
)
ALLOWED_SOURCE_TYPES = CONTRACT_SOURCE_TYPES | frozenset({"SUPERVISOR_MANUAL"})
SOURCE_TYPE_DOMAINS = {
    **{source_type: "contract" for source_type in CONTRACT_SOURCE_TYPES},
    "SUPERVISOR_MANUAL": "supervisor_manual",
}

CONTRACT_ROUTING_SIGNALS = (
    "agreement",
    "arbitration",
    "article ",
    "bargaining",
    "cba",
    "cim",
    "contract",
    "elm",
    "lmou",
    "memorandum of understanding",
    "remedy",
    "right",
    "violation",
)
SUPERVISOR_ROUTING_SIGNALS = (
    "attendance control",
    "documentation",
    "el-801",
    "el-921",
    "f-21",
    "grievance handling",
    "management procedure",
    "safety responsib",
    "step 1 meeting",
    "supervisor",
    "time and attendance",
)
SOURCE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,149}$")


class RequestValidationError(ValueError):
    pass


class RetrievalOrchestrator:
    """Stable, read-only entry point for specialized retrieval.

    Agents run sequentially because SQLAlchemy Session is not thread-safe. One
    query embedding is created and passed to every selected agent.
    """

    def __init__(
        self,
        agents: Iterable[RetrievalAgent] | None = None,
        *,
        embedding_provider: Callable[[str], Sequence[float]] | None = None,
    ) -> None:
        configured_agents = list(
            agents
            if agents is not None
            else (ContractAgent(), SupervisorManualAgent())
        )
        self._agents = tuple(
            agent
            for agent in configured_agents
            if agent.identity.name in RETRIEVAL_ENABLED_AGENTS
        )
        self._embedding_provider = (
            embedding_provider or self._create_query_embedding
        )

    @staticmethod
    def _create_query_embedding(query: str) -> Sequence[float]:
        return EmbeddingService.create_embedding(
            query,
            timeout_seconds=RETRIEVAL_EMBEDDING_TIMEOUT_SECONDS,
        )

    @staticmethod
    def _query_hash(query: str) -> str:
        return hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _safe_failure_result(
        *,
        status: str,
        code: str,
        message: str,
        query_hash: str = "",
        error_class: str | None = None,
        retriable: bool = False,
        duration_ms: float = 0.0,
    ) -> OrchestrationResult:
        failure = AgentFailure(
            code=code,
            message=message,
            retriable=retriable,
            error_class=error_class,
        )
        return OrchestrationResult(
            status=status,
            failures=(failure,),
            query_hash=query_hash,
            duration_ms=duration_ms,
        )

    @staticmethod
    def _bounded_positive(
        value: int | None,
        *,
        default: int,
        maximum: int,
        field_name: str,
    ) -> int:
        if value is None:
            return default
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise RequestValidationError(
                f"{field_name} must be a positive integer."
            )
        return min(value, maximum)

    @staticmethod
    def _route_domains(
        domain: str,
        workflow_context: str | None,
        query: str,
    ) -> tuple[str, ...]:
        if domain == "contract":
            return ("contract",)
        if domain == "supervisor_manual":
            return ("supervisor_manual",)
        if domain == "combined":
            return ("contract", "supervisor_manual")

        if workflow_context == "contract_analysis":
            return ("contract",)
        if workflow_context == "supervisor_guidance":
            return ("supervisor_manual",)
        if workflow_context in {"grievance_analysis", "report_evidence"}:
            return ("contract", "supervisor_manual")

        lowered = query.casefold()
        contract_match = any(
            signal in lowered for signal in CONTRACT_ROUTING_SIGNALS
        )
        supervisor_match = any(
            signal in lowered for signal in SUPERVISOR_ROUTING_SIGNALS
        )
        if contract_match and supervisor_match:
            return ("contract", "supervisor_manual")
        if supervisor_match:
            return ("supervisor_manual",)
        return ("contract",)

    def _validate_request(
        self,
        request: RetrievalRequest,
    ) -> ValidatedRetrievalRequest:
        if not isinstance(request, RetrievalRequest):
            raise RequestValidationError("Invalid retrieval request.")
        if not isinstance(request.query, str):
            raise RequestValidationError("query must be a string.")
        normalized_query = unicodedata.normalize("NFKC", request.query).strip()
        if not normalized_query:
            raise RequestValidationError("query must not be empty.")
        if "\x00" in normalized_query or any(
            unicodedata.category(char) == "Cc"
            and char not in {"\n", "\r", "\t"}
            for char in normalized_query
        ):
            raise RequestValidationError(
                "query contains unsupported control characters."
            )
        if len(normalized_query) > RETRIEVAL_MAX_QUERY_CHARS:
            raise RequestValidationError(
                f"query exceeds {RETRIEVAL_MAX_QUERY_CHARS} characters."
            )

        domain = str(request.domain or "auto").strip().lower()
        if domain not in ALLOWED_DOMAINS:
            raise RequestValidationError("Unsupported retrieval domain.")

        workflow_context = (
            str(request.workflow_context).strip().lower()
            if request.workflow_context is not None
            else None
        )
        if (
            workflow_context is not None
            and workflow_context not in ALLOWED_WORKFLOW_CONTEXTS
        ):
            raise RequestValidationError("Unsupported workflow context.")

        if not isinstance(request.agent_names, (tuple, list, set, frozenset)):
            raise RequestValidationError("agent_names must be a list.")
        available_agent_names = {
            agent.identity.name for agent in self._agents
        }
        agent_names = tuple(
            dict.fromkeys(str(name) for name in request.agent_names)
        )
        if any(name not in available_agent_names for name in agent_names):
            raise RequestValidationError("Unsupported retrieval agent.")

        if not isinstance(request.source_types, (tuple, list, set, frozenset)):
            raise RequestValidationError("source_types must be a list.")
        source_types = tuple(
            dict.fromkeys(
                str(source_type).strip().upper()
                for source_type in request.source_types
                if str(source_type).strip()
            )
        )
        if len(source_types) > RETRIEVAL_MAX_SOURCE_FILTERS:
            raise RequestValidationError("Too many source-type filters.")
        if any(source_type not in ALLOWED_SOURCE_TYPES for source_type in source_types):
            raise RequestValidationError("Unsupported source type.")

        if not isinstance(request.source_ids, (tuple, list, set, frozenset)):
            raise RequestValidationError("source_ids must be a list.")
        source_ids = tuple(
            dict.fromkeys(
                str(source_id).strip()
                for source_id in request.source_ids
                if str(source_id).strip()
            )
        )
        if len(source_ids) > RETRIEVAL_MAX_SOURCE_FILTERS:
            raise RequestValidationError("Too many source filters.")
        if any(not SOURCE_ID_PATTERN.fullmatch(source_id) for source_id in source_ids):
            raise RequestValidationError("Invalid source identifier.")

        domains = self._route_domains(
            domain,
            workflow_context,
            normalized_query,
        )
        if agent_names:
            selected_name_domains = {
                agent.identity.domain
                for agent in self._agents
                if agent.identity.name in agent_names
            }
            domains = tuple(
                item for item in domains if item in selected_name_domains
            )
            if not domains:
                domains = tuple(sorted(selected_name_domains))
        if source_types:
            selected_type_domains = {
                SOURCE_TYPE_DOMAINS[source_type] for source_type in source_types
            }
            if not selected_type_domains.issubset(domains):
                raise RequestValidationError(
                    "Source types do not match the selected retrieval domain."
                )
        if not domains or len(domains) > RETRIEVAL_MAX_SOURCE_DOMAINS:
            raise RequestValidationError("Invalid retrieval-domain selection.")

        candidate_limit = self._bounded_positive(
            request.candidate_limit,
            default=RETRIEVAL_DEFAULT_CANDIDATE_LIMIT,
            maximum=RETRIEVAL_MAX_CANDIDATE_LIMIT,
            field_name="candidate_limit",
        )
        total_limit = self._bounded_positive(
            request.result_limit,
            default=RETRIEVAL_DEFAULT_TOTAL_RESULT_LIMIT,
            maximum=RETRIEVAL_MAX_TOTAL_RESULT_LIMIT,
            field_name="result_limit",
        )
        per_agent_limit = self._bounded_positive(
            request.per_agent_result_limit,
            default=RETRIEVAL_DEFAULT_PER_AGENT_RESULT_LIMIT,
            maximum=RETRIEVAL_MAX_PER_AGENT_RESULT_LIMIT,
            field_name="per_agent_result_limit",
        )
        per_source_limit = self._bounded_positive(
            request.per_source_result_limit,
            default=RETRIEVAL_DEFAULT_PER_SOURCE_RESULT_LIMIT,
            maximum=RETRIEVAL_MAX_PER_SOURCE_RESULT_LIMIT,
            field_name="per_source_result_limit",
        )
        candidate_limit = max(candidate_limit, per_agent_limit)

        threshold = (
            MIN_COMBINED_RETRIEVAL_SCORE
            if request.relevance_threshold is None
            else request.relevance_threshold
        )
        if (
            isinstance(threshold, bool)
            or not isinstance(threshold, (int, float))
            or not math.isfinite(float(threshold))
            or not 0.0 <= float(threshold) <= 1.0
        ):
            raise RequestValidationError(
                "relevance_threshold must be between 0 and 1."
            )

        return ValidatedRetrievalRequest(
            query=normalized_query,
            domains=domains,
            agent_names=agent_names,
            workflow_context=workflow_context,
            candidate_limit=candidate_limit,
            result_limit=total_limit,
            per_agent_result_limit=per_agent_limit,
            per_source_result_limit=per_source_limit,
            relevance_threshold=float(threshold),
            source_types=source_types,
            source_ids=source_ids,
            include_diagnostics=bool(request.include_diagnostics),
        )

    @staticmethod
    def _validate_authorization(
        authorization: RetrievalAuthorizationContext,
    ) -> AgentFailure | None:
        if not authorization.authenticated:
            return AgentFailure(
                code="authentication_required",
                message="Authentication is required for retrieval.",
            )
        if (
            authorization.allow_all_organizations
            and not authorization.is_admin
        ):
            return AgentFailure(
                code="authorization_denied",
                message="The caller is not authorized for this retrieval scope.",
            )
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value <= 0
            for value in authorization.allowed_organization_ids
        ):
            return AgentFailure(
                code="authorization_denied",
                message="The caller is not authorized for this retrieval scope.",
            )
        if (
            len(authorization.allowed_organization_ids)
            > RETRIEVAL_MAX_SOURCE_FILTERS
        ):
            return AgentFailure(
                code="authorization_denied",
                message="The caller is not authorized for this retrieval scope.",
            )
        if (
            not authorization.allow_global_sources
            and not authorization.allowed_organization_ids
            and not (
                authorization.is_admin
                and authorization.allow_all_organizations
            )
        ):
            return AgentFailure(
                code="authorization_denied",
                message="The caller is not authorized for this retrieval scope.",
            )
        return None

    @staticmethod
    def _validate_embedding(embedding: Sequence[float]) -> tuple[float, ...]:
        if len(embedding) != 1536:
            raise ValueError("Unexpected embedding dimension.")
        normalized = tuple(float(value) for value in embedding)
        if not all(math.isfinite(value) for value in normalized):
            raise ValueError("Embedding contains non-finite values.")
        return normalized

    @staticmethod
    def _merge_results(
        agent_results: Sequence[AgentRetrievalResult],
        request: ValidatedRetrievalRequest,
    ) -> tuple[tuple[RetrievalEvidence, ...], int, bool]:
        candidates = [
            evidence
            for agent_result in agent_results
            for evidence in agent_result.results
        ]
        # Scores are threshold-normalized inside each agent before this merge:
        # final = 0.85 * normalized_agent_score + 0.15 * cosine_similarity.
        candidates.sort(
            key=lambda item: (
                -item.final_relevance_score,
                item.raw_vector_distance,
                item.retrieval_agent,
                item.canonical_source_id,
                item.page_number if item.page_number is not None else 2**31,
                item.chunk_index,
                item.chunk_id,
            )
        )

        selected: list[RetrievalEvidence] = []
        per_source: dict[str, int] = {}
        duplicate_count = 0
        response_chars = 0
        capped = False
        for candidate in candidates:
            duplicate_index = next(
                (
                    index
                    for index, kept in enumerate(selected)
                    if candidate.chunk_key == kept.chunk_key
                    or materially_overlaps(candidate, kept)
                ),
                None,
            )
            if duplicate_index is not None:
                kept = selected[duplicate_index]
                alternate = candidate.citation
                if alternate != kept.citation and alternate not in kept.alternate_provenance:
                    selected[duplicate_index] = replace(
                        kept,
                        alternate_provenance=(
                            *kept.alternate_provenance,
                            alternate,
                        ),
                    )
                duplicate_count += 1
                continue

            source_count = per_source.get(candidate.canonical_source_id, 0)
            if source_count >= request.per_source_result_limit:
                capped = True
                continue
            if response_chars + len(candidate.chunk_text) > RETRIEVAL_MAX_RESPONSE_TEXT_CHARS:
                capped = True
                continue
            selected.append(candidate)
            per_source[candidate.canonical_source_id] = source_count + 1
            response_chars += len(candidate.chunk_text)
            if len(selected) >= request.result_limit:
                capped = len(candidates) > len(selected)
                break
        return tuple(selected), duplicate_count, capped

    def retrieve(
        self,
        db: Session,
        request: RetrievalRequest,
        authorization: RetrievalAuthorizationContext,
    ) -> OrchestrationResult:
        started = perf_counter()
        try:
            validated = self._validate_request(request)
        except RequestValidationError as exc:
            return self._safe_failure_result(
                status="validation_failure",
                code="invalid_retrieval_request",
                message=str(exc),
                duration_ms=(perf_counter() - started) * 1000,
            )

        query_hash = self._query_hash(validated.query)
        if not isinstance(authorization, RetrievalAuthorizationContext):
            return self._safe_failure_result(
                status="authorization_failure",
                code="authorization_denied",
                message="The caller is not authorized for this retrieval scope.",
                query_hash=query_hash,
                duration_ms=(perf_counter() - started) * 1000,
            )
        authorization_failure = self._validate_authorization(authorization)
        if authorization_failure:
            return OrchestrationResult(
                status="authorization_failure",
                failures=(authorization_failure,),
                query_hash=query_hash,
                duration_ms=(perf_counter() - started) * 1000,
            )

        selected_agents = tuple(
            agent
            for agent in self._agents
            if agent.is_eligible(validated)
        )
        if not selected_agents:
            return self._safe_failure_result(
                status="complete_failure",
                code="no_enabled_retrieval_agent",
                message="No retrieval agent is enabled for this request.",
                query_hash=query_hash,
                duration_ms=(perf_counter() - started) * 1000,
            )

        logger.info(
            "retrieval_started correlation_id=%s query_hash=%s query_chars=%d agents=%s",
            authorization.correlation_id or "",
            query_hash,
            len(validated.query),
            ",".join(agent.identity.name for agent in selected_agents),
        )

        embedding_started = perf_counter()
        try:
            query_embedding = self._validate_embedding(
                self._embedding_provider(validated.query)
            )
        except Exception as exc:
            logger.warning(
                "retrieval_embedding_failure correlation_id=%s query_hash=%s error_class=%s",
                authorization.correlation_id or "",
                query_hash,
                type(exc).__name__,
            )
            return self._safe_failure_result(
                status="complete_failure",
                code="embedding_service_unavailable",
                message="Retrieval is temporarily unavailable.",
                query_hash=query_hash,
                error_class=type(exc).__name__,
                retriable=True,
                duration_ms=(perf_counter() - started) * 1000,
            )
        embedding_duration_ms = (perf_counter() - embedding_started) * 1000

        agent_results: list[AgentRetrievalResult] = []
        database_started = perf_counter()
        for agent in selected_agents:
            agent_result = agent.retrieve(
                db,
                validated,
                authorization,
                query_embedding,
            )
            agent_results.append(agent_result)
            if agent_result.status == "failure":
                try:
                    db.rollback()
                except Exception as rollback_exc:
                    logger.warning(
                        "retrieval_session_rollback_failure correlation_id=%s "
                        "query_hash=%s error_class=%s",
                        authorization.correlation_id or "",
                        query_hash,
                        type(rollback_exc).__name__,
                    )
        database_duration_ms = (perf_counter() - database_started) * 1000

        merge_started = perf_counter()
        merged, duplicate_count, capped = self._merge_results(
            agent_results,
            validated,
        )
        merge_duration_ms = (perf_counter() - merge_started) * 1000

        failed_results = [
            item for item in agent_results if item.status == "failure"
        ]
        failures = tuple(
            item.failure for item in failed_results if item.failure is not None
        )
        if failed_results and len(failed_results) == len(agent_results):
            status = "complete_failure"
            partial = False
        elif failed_results:
            status = "partial_failure"
            partial = True
        elif merged:
            status = "success"
            partial = False
        elif all(
            item.status == "no_eligible_sources" for item in agent_results
        ):
            status = "no_eligible_sources"
            partial = False
        else:
            status = "no_relevant_results"
            partial = False

        duration_ms = (perf_counter() - started) * 1000
        logger.info(
            "retrieval_completed correlation_id=%s query_hash=%s status=%s "
            "candidates=%d accepted=%d duplicates=%d duration_ms=%.3f",
            authorization.correlation_id or "",
            query_hash,
            status,
            sum(item.candidate_count for item in agent_results),
            len(merged),
            duplicate_count,
            duration_ms,
        )
        return OrchestrationResult(
            status=status,
            results=merged,
            agent_results=tuple(agent_results),
            failures=failures,
            selected_agents=tuple(
                agent.identity.name for agent in selected_agents
            ),
            query_hash=query_hash,
            partial=partial,
            duration_ms=duration_ms,
            embedding_duration_ms=embedding_duration_ms,
            database_duration_ms=database_duration_ms,
            merge_duration_ms=merge_duration_ms,
            duplicate_count=duplicate_count,
            capped=capped,
        )
