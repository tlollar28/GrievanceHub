"""Narrow read-only interface and shared SQL vector-search implementation."""

from __future__ import annotations

import logging
import math
import re
import unicodedata
from abc import ABC, abstractmethod
from time import perf_counter
from typing import Any, Mapping, Protocol, Sequence

from sqlalchemy import false, or_, select
from sqlalchemy.orm import Session

from app.database.models import SourceChunk, SourceDocument
from app.retrieval_config import (
    RETRIEVAL_MAX_CHUNK_TEXT_CHARS,
    RETRIEVAL_MIN_CANDIDATE_SIMILARITY,
)
from app.services.relevance_utils import (
    STOPWORDS,
    combine_retrieval_score,
    compute_distinctive_overlap_score,
    compute_procedural_bonus,
    is_boilerplate_chunk,
)
from app.services.retrieval.models import (
    AgentFailure,
    AgentIdentity,
    AgentRetrievalResult,
    RetrievalAuthorizationContext,
    RetrievalEvidence,
    ValidatedRetrievalRequest,
)


logger = logging.getLogger(__name__)

SAFE_METADATA_KEYS = frozenset(
    {
        "article",
        "chapter",
        "chunking_strategy",
        "heading",
        "page",
        "section",
        "source_type",
    }
)
MAX_METADATA_VALUE_CHARS = 240
MAX_METADATA_LIST_ITEMS = 8
MAX_TITLE_CHARS = 255
MAX_SOURCE_ID_CHARS = 150


class RetrievalAgent(Protocol):
    identity: AgentIdentity

    def is_eligible(self, request: ValidatedRetrievalRequest) -> bool:
        ...

    def retrieve(
        self,
        db: Session,
        request: ValidatedRetrievalRequest,
        authorization: RetrievalAuthorizationContext,
        query_embedding: Sequence[float],
    ) -> AgentRetrievalResult:
        ...


def _strip_unsafe_controls(value: str, *, preserve_newlines: bool) -> str:
    normalized = unicodedata.normalize("NFKC", value).replace("\x00", "")
    allowed_controls = {"\n", "\r", "\t"} if preserve_newlines else set()
    return "".join(
        char
        for char in normalized
        if char in allowed_controls or unicodedata.category(char) != "Cc"
    )


def _safe_display_text(value: Any, *, max_chars: int) -> str:
    return _strip_unsafe_controls(
        str(value or ""),
        preserve_newlines=False,
    ).strip()[:max_chars]


def _safe_chunk_text(value: Any) -> str:
    return _strip_unsafe_controls(
        str(value or ""),
        preserve_newlines=True,
    ).strip()[:RETRIEVAL_MAX_CHUNK_TEXT_CHARS]


def _safe_metadata_value(value: Any) -> Any | None:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _safe_display_text(value, max_chars=MAX_METADATA_VALUE_CHARS)
    if isinstance(value, (list, tuple)):
        safe_items: list[Any] = []
        for item in value[:MAX_METADATA_LIST_ITEMS]:
            safe_item = _safe_metadata_value(item)
            if safe_item is not None and not isinstance(safe_item, list):
                safe_items.append(safe_item)
        return safe_items
    return None


def sanitize_chunk_metadata(value: Any) -> dict[str, Any]:
    """Return an allowlisted, shallow JSON projection with no path-like keys."""

    if not isinstance(value, Mapping):
        return {}
    safe: dict[str, Any] = {}
    for key in sorted(SAFE_METADATA_KEYS):
        if key not in value:
            continue
        safe_value = _safe_metadata_value(value[key])
        if safe_value is not None:
            safe[key] = safe_value
    return safe


def _query_keywords(query: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z0-9.']+", query.lower())
    return list(
        dict.fromkeys(
            token
            for token in tokens
            if len(token) >= 4 and token not in STOPWORDS
        )
    )[:30]


def _overlap_tokens(text: str) -> frozenset[str]:
    return frozenset(re.findall(r"[a-z0-9]+", text.lower()))


def materially_overlaps(left: RetrievalEvidence, right: RetrievalEvidence) -> bool:
    """Bounded duplicate check used only after candidate caps are enforced."""

    left_text = " ".join(left.chunk_text.lower().split())
    right_text = " ".join(right.chunk_text.lower().split())
    if not left_text or not right_text:
        return False
    if left_text == right_text:
        return True
    if left.source_document_id != right.source_document_id:
        return False
    shorter, longer = sorted((left_text, right_text), key=len)
    if len(shorter) >= 120 and shorter in longer:
        return True
    left_tokens = _overlap_tokens(left_text)
    right_tokens = _overlap_tokens(right_text)
    if not left_tokens or not right_tokens:
        return False
    union = left_tokens | right_tokens
    return bool(union) and len(left_tokens & right_tokens) / len(union) >= 0.88


class BaseRetrievalAgent(ABC):
    """Read-only, deterministic retrieval agent.

    A SQLAlchemy Session is not thread-safe. The orchestrator invokes agents
    sequentially unless a future caller supplies isolated sessions.
    """

    identity: AgentIdentity

    def is_eligible(self, request: ValidatedRetrievalRequest) -> bool:
        return (
            self.identity.domain in request.domains
            and (
                not request.agent_names
                or self.identity.name in request.agent_names
            )
        )

    @abstractmethod
    def retrieve(
        self,
        db: Session,
        request: ValidatedRetrievalRequest,
        authorization: RetrievalAuthorizationContext,
        query_embedding: Sequence[float],
    ) -> AgentRetrievalResult:
        raise NotImplementedError


class SqlVectorRetrievalAgent(BaseRetrievalAgent):
    """One-query pgvector retriever with projection-based provenance hydration."""

    @property
    @abstractmethod
    def default_evidence_role(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def processing_predicate(self):
        raise NotImplementedError

    def evidence_role_for(self, source_type: str) -> str:
        return self.default_evidence_role

    @staticmethod
    def _authorization_predicate(
        authorization: RetrievalAuthorizationContext,
    ):
        if authorization.is_admin and authorization.allow_all_organizations:
            return None

        predicates = []
        if authorization.allow_global_sources:
            predicates.append(SourceDocument.organization_id.is_(None))
        if authorization.allowed_organization_ids:
            predicates.append(
                SourceDocument.organization_id.in_(
                    sorted(authorization.allowed_organization_ids)
                )
            )
        if not predicates:
            return false()
        return or_(*predicates)

    def _candidate_statement(
        self,
        request: ValidatedRetrievalRequest,
        authorization: RetrievalAuthorizationContext,
        query_embedding: Sequence[float],
    ):
        distance = SourceChunk.embedding.cosine_distance(query_embedding)
        eligible_source_types = self.identity.supported_source_types
        if request.source_types:
            eligible_source_types = eligible_source_types.intersection(
                request.source_types
            )
        statement = (
            select(
                SourceDocument.id.label("source_document_id"),
                SourceDocument.source_id.label("canonical_source_id"),
                SourceDocument.name.label("source_title"),
                SourceDocument.source_type.label("source_type"),
                SourceDocument.version.label("source_version"),
                SourceDocument.sha256.label("source_sha256"),
                SourceDocument.processed_sha256.label("processed_sha256"),
                SourceDocument.processing_strategy.label("processing_strategy"),
                SourceChunk.id.label("chunk_id"),
                SourceChunk.chunk_index.label("chunk_index"),
                SourceChunk.page_number.label("page_number"),
                SourceChunk.text.label("chunk_text"),
                SourceChunk.chunk_metadata.label("chunk_metadata"),
                distance.label("raw_vector_distance"),
            )
            .select_from(SourceChunk)
            .join(
                SourceDocument,
                SourceDocument.id == SourceChunk.source_document_id,
            )
            .where(
                SourceDocument.source_type.in_(
                    sorted(eligible_source_types)
                ),
                SourceDocument.is_current.is_(True),
                self.processing_predicate(),
                SourceChunk.embedding.isnot(None),
            )
            .order_by(
                distance.asc(),
                SourceDocument.source_id.asc(),
                SourceChunk.page_number.asc().nullslast(),
                SourceChunk.chunk_index.asc(),
                SourceChunk.id.asc(),
            )
            .limit(request.candidate_limit)
        )
        authorization_predicate = self._authorization_predicate(authorization)
        if authorization_predicate is not None:
            statement = statement.where(authorization_predicate)
        if request.source_ids:
            statement = statement.where(
                SourceDocument.source_id.in_(request.source_ids)
            )
        return statement

    def _row_to_evidence(
        self,
        row: Mapping[str, Any],
        request: ValidatedRetrievalRequest,
        keywords: list[str],
    ) -> RetrievalEvidence | None:
        distance = float(row["raw_vector_distance"])
        if not math.isfinite(distance):
            return None
        similarity = max(0.0, min(1.0, 1.0 - distance))
        text = _safe_chunk_text(row["chunk_text"])
        if not text or similarity < RETRIEVAL_MIN_CANDIDATE_SIMILARITY:
            return None

        boilerplate = is_boilerplate_chunk(text)
        if boilerplate:
            return None
        keyword_overlap = compute_distinctive_overlap_score(text, keywords)
        score = combine_retrieval_score(
            embedding_similarity=similarity,
            keyword_overlap=keyword_overlap,
            source_type=str(row["source_type"]),
            is_boilerplate=False,
            procedural_bonus=compute_procedural_bonus(text, keywords),
        )
        # Match the shared gate's primary branch: a strong combined score can
        # accept mid-similarity evidence. Weak combined scores are rejected.
        if score < request.relevance_threshold:
            return None

        score_ceiling = 1.05
        denominator = max(0.000001, score_ceiling - request.relevance_threshold)
        normalized_score = max(
            0.0,
            min(1.0, (score - request.relevance_threshold) / denominator),
        )
        final_score = 0.85 * normalized_score + 0.15 * similarity
        processed_sha = row["processed_sha256"]
        source_sha = processed_sha or row["source_sha256"]
        processing_strategy = row["processing_strategy"]
        if processed_sha is None:
            processing_strategy = processing_strategy or "legacy_pre_w5_index"

        source_type = _safe_display_text(row["source_type"], max_chars=100).upper()
        return RetrievalEvidence(
            source_document_id=int(row["source_document_id"]),
            canonical_source_id=_safe_display_text(
                row["canonical_source_id"],
                max_chars=MAX_SOURCE_ID_CHARS,
            ),
            source_title=_safe_display_text(
                row["source_title"],
                max_chars=MAX_TITLE_CHARS,
            ),
            source_type=source_type,
            source_version=(
                _safe_display_text(row["source_version"], max_chars=80)
                if row["source_version"] is not None
                else None
            ),
            source_sha256=(
                _safe_display_text(source_sha, max_chars=128)
                if source_sha is not None
                else None
            ),
            chunk_id=int(row["chunk_id"]),
            chunk_index=int(row["chunk_index"]),
            page_number=(
                int(row["page_number"])
                if row["page_number"] is not None
                else None
            ),
            chunk_text=text,
            raw_vector_distance=distance,
            raw_vector_similarity=similarity,
            normalized_score=normalized_score,
            final_relevance_score=final_score,
            retrieval_agent=self.identity.name,
            retrieval_domain=self.identity.domain,
            evidence_role=self.evidence_role_for(source_type),
            processing_strategy=(
                _safe_display_text(processing_strategy, max_chars=80)
                if processing_strategy is not None
                else None
            ),
            safe_chunk_metadata=sanitize_chunk_metadata(row["chunk_metadata"]),
        )

    def retrieve(
        self,
        db: Session,
        request: ValidatedRetrievalRequest,
        authorization: RetrievalAuthorizationContext,
        query_embedding: Sequence[float],
    ) -> AgentRetrievalResult:
        started = perf_counter()
        attempted_queries = 0
        try:
            statement = self._candidate_statement(
                request,
                authorization,
                query_embedding,
            )
            attempted_queries = 1
            rows = db.execute(statement).mappings().all()
            if not rows:
                return AgentRetrievalResult(
                    identity=self.identity,
                    status="no_eligible_sources",
                    duration_ms=(perf_counter() - started) * 1000,
                    sql_query_count=attempted_queries,
                )

            keywords = _query_keywords(request.query)
            scored: list[RetrievalEvidence] = []
            rejected = 0
            for row in rows:
                evidence = self._row_to_evidence(row, request, keywords)
                if evidence is None:
                    rejected += 1
                    continue
                scored.append(evidence)

            scored.sort(
                key=lambda item: (
                    -item.final_relevance_score,
                    item.raw_vector_distance,
                    item.canonical_source_id,
                    item.page_number if item.page_number is not None else 2**31,
                    item.chunk_index,
                    item.chunk_id,
                )
            )

            selected: list[RetrievalEvidence] = []
            per_source: dict[str, int] = {}
            duplicates = 0
            for candidate in scored:
                if any(materially_overlaps(candidate, kept) for kept in selected):
                    duplicates += 1
                    continue
                source_count = per_source.get(candidate.canonical_source_id, 0)
                if source_count >= request.per_source_result_limit:
                    continue
                selected.append(candidate)
                per_source[candidate.canonical_source_id] = source_count + 1
                if len(selected) >= request.per_agent_result_limit:
                    break

            status = "success" if selected else "no_relevant_results"
            return AgentRetrievalResult(
                identity=self.identity,
                status=status,
                results=tuple(selected),
                candidate_count=len(rows),
                accepted_count=len(selected),
                threshold_rejected_count=rejected,
                duplicate_count=duplicates,
                duration_ms=(perf_counter() - started) * 1000,
                sql_query_count=attempted_queries,
            )
        except Exception as exc:
            # This is an agent isolation boundary. The client gets a stable,
            # non-sensitive error while the orchestrator may continue.
            logger.warning(
                "retrieval_agent_failure agent=%s error_class=%s",
                self.identity.name,
                type(exc).__name__,
            )
            return AgentRetrievalResult(
                identity=self.identity,
                status="failure",
                failure=AgentFailure(
                    code="agent_retrieval_failed",
                    message="The retrieval source was temporarily unavailable.",
                    retriable=True,
                    error_class=type(exc).__name__,
                ),
                duration_ms=(perf_counter() - started) * 1000,
                sql_query_count=attempted_queries,
            )
