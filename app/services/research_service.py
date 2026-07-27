"""Read-only Sources Research service for the W6 browser-safe boundary.

Reuses KnowledgeRetrievalService / ORM reads directly. Constructs a
global-corpus RetrievalAuthorizationContext in process — never trusts
browser-supplied API keys or case UUID as authentication.
"""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database.models import SourceChunk, SourceDocument
from app.retrieval_config import (
    RETRIEVAL_DEFAULT_PER_SOURCE_RESULT_LIMIT,
    RETRIEVAL_DEFAULT_TOTAL_RESULT_LIMIT,
    RETRIEVAL_MAX_CHUNK_TEXT_CHARS,
    RETRIEVAL_MAX_PER_SOURCE_RESULT_LIMIT,
    RETRIEVAL_MAX_QUERY_CHARS,
    RETRIEVAL_MAX_TOTAL_RESULT_LIMIT,
)
from app.schemas.research_schema import (
    ResearchFailure,
    ResearchMetaResponse,
    ResearchPassageDetail,
    ResearchPassageMetadata,
    ResearchSearchRequest,
    ResearchSearchResponse,
    ResearchSearchResultItem,
    ResearchSourceDetail,
    ResearchSourceListResponse,
    ResearchSourceSummary,
    ResearchSupportedFilter,
    ResearchUiStatus,
)
from app.services.knowledge_retrieval_service import KnowledgeRetrievalService
from app.services.retrieval.base_agent import sanitize_chunk_metadata
from app.services.retrieval.models import (
    AgentFailure,
    OrchestrationResult,
    RetrievalAuthorizationContext,
    RetrievalEvidence,
)
from app.services.retrieval.orchestrator import ALLOWED_SOURCE_TYPES, RequestValidationError

AUTHORITY_NOTICE = (
    "Sources Research searches the indexed authority corpus. Files uploaded "
    "under Evidence are case attachments and are not part of authority-corpus "
    "retrieval."
)

BOUNDARY_DESCRIPTION = (
    "Interim W6 browser-safe read-only research boundary. "
    "Does not replace production authentication (W9). "
    "Protected /sources administration remains API-key gated."
)

RESEARCH_PRINCIPAL_ID = "browser-research"
RESEARCH_MAX_OFFSET = 200
RESEARCH_LIST_DEFAULT_LIMIT = 50
RESEARCH_LIST_MAX_LIMIT = 100
EXCERPT_CHARS = 320

SOURCE_TYPE_LABELS: dict[str, str] = {
    "CONTRACT": "National Agreement",
    "CIM": "Contract Interpretation Manual",
    "SUPERVISOR_MANUAL": "Supervisor Manual",
    "ELM": "Employee and Labor Relations Manual",
    "LMOU": "Local Memorandum of Understanding",
    "ARBITRATION": "Arbitration",
}


class ResearchNotFoundError(LookupError):
    """Requested source document or passage was not found."""


class ResearchValidationError(ValueError):
    """Caller supplied an invalid research filter or parameter."""


def source_type_label(source_type: str) -> str:
    key = (source_type or "").strip().upper()
    if key in SOURCE_TYPE_LABELS:
        return SOURCE_TYPE_LABELS[key]
    if not key:
        return "Unknown source type"
    return key.replace("_", " ").title()


def map_retrieval_ui_status(
    status: str,
    *,
    result_count: int,
    partial: bool,
) -> ResearchUiStatus:
    if status in {"no_eligible_sources", "no_relevant_results"}:
        return "empty"
    if status in {
        "complete_failure",
        "authorization_failure",
        "validation_failure",
    }:
        return "failed"
    if status == "partial_failure" or (partial and result_count > 0):
        return "partial"
    if status == "success":
        return "ok" if result_count > 0 else "empty"
    if status == "skipped":
        return "skipped"
    return "failed" if result_count == 0 else "partial"


def _safe_failure(failure: AgentFailure) -> ResearchFailure:
    message = str(failure.message or "The retrieval source was temporarily unavailable.")
    if len(message) > 240:
        message = message[:237] + "..."
    return ResearchFailure(
        code=str(failure.code or "retrieval_failure")[:80],
        message=message,
        retriable=bool(failure.retriable),
    )


def _metadata_from_mapping(raw: dict) -> ResearchPassageMetadata:
    safe = sanitize_chunk_metadata(raw)
    page = safe.get("page")
    return ResearchPassageMetadata(
        article=_as_optional_str(safe.get("article")),
        chapter=_as_optional_str(safe.get("chapter")),
        heading=_as_optional_str(safe.get("heading")),
        page=page if isinstance(page, (int, str)) else None,
        section=_as_optional_str(safe.get("section")),
    )


def _as_optional_str(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _excerpt(text: str) -> str:
    cleaned = (text or "").strip()
    if len(cleaned) <= EXCERPT_CHARS:
        return cleaned
    return cleaned[: EXCERPT_CHARS - 1].rstrip() + "…"


def _provenance(evidence: RetrievalEvidence) -> str:
    parts = [
        evidence.source_type,
        evidence.evidence_role,
    ]
    if evidence.page_number is not None:
        parts.append(f"page {evidence.page_number}")
    parts.append(f"chunk {evidence.chunk_index}")
    return " · ".join(str(part) for part in parts if part)


def _authorization() -> RetrievalAuthorizationContext:
    return RetrievalAuthorizationContext.global_corpus(
        principal_id=RESEARCH_PRINCIPAL_ID,
    )


def _validate_source_types(source_types: list[str]) -> tuple[str, ...]:
    normalized = tuple(
        item.strip().upper() for item in source_types if item and item.strip()
    )
    unknown = [item for item in normalized if item not in ALLOWED_SOURCE_TYPES]
    if unknown:
        raise ResearchValidationError(
            "Unsupported source_type filter: " + ", ".join(sorted(set(unknown)))
        )
    return normalized


class ResearchService:
    """Read-only authority-corpus research operations for the browser boundary."""

    @staticmethod
    def get_meta() -> ResearchMetaResponse:
        types = sorted(ALLOWED_SOURCE_TYPES)
        return ResearchMetaResponse(
            source_types=[
                ResearchSupportedFilter(value=item, label=source_type_label(item))
                for item in types
            ],
            default_limit=RETRIEVAL_DEFAULT_TOTAL_RESULT_LIMIT,
            max_limit=RETRIEVAL_MAX_TOTAL_RESULT_LIMIT,
            default_limit_per_source=RETRIEVAL_DEFAULT_PER_SOURCE_RESULT_LIMIT,
            max_limit_per_source=RETRIEVAL_MAX_PER_SOURCE_RESULT_LIMIT,
            max_offset=RESEARCH_MAX_OFFSET,
            max_query_chars=RETRIEVAL_MAX_QUERY_CHARS,
            authority_notice=AUTHORITY_NOTICE,
            boundary=BOUNDARY_DESCRIPTION,
        )

    @staticmethod
    def list_sources(
        db: Session,
        *,
        limit: int = RESEARCH_LIST_DEFAULT_LIMIT,
        offset: int = 0,
        source_type: str | None = None,
    ) -> ResearchSourceListResponse:
        limit = max(1, min(int(limit), RESEARCH_LIST_MAX_LIMIT))
        offset = max(0, min(int(offset), RESEARCH_MAX_OFFSET))

        query = db.query(SourceDocument).filter(SourceDocument.is_current.is_(True))
        if source_type:
            normalized = source_type.strip().upper()
            if normalized not in ALLOWED_SOURCE_TYPES:
                raise ResearchValidationError(
                    f"Unsupported source_type filter: {normalized}"
                )
            query = query.filter(SourceDocument.source_type == normalized)

        total = query.count()
        rows = (
            query.order_by(SourceDocument.name.asc(), SourceDocument.id.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        source_ids = [row.id for row in rows]
        count_map = ResearchService._chunk_counts(db, source_ids)

        sources = [
            ResearchService._source_summary(row, count_map.get(row.id, (0, 0)))
            for row in rows
        ]
        return ResearchSourceListResponse(
            count=len(sources),
            total=total,
            limit=limit,
            offset=offset,
            sources=sources,
            authority_notice=AUTHORITY_NOTICE,
        )

    @staticmethod
    def get_source(db: Session, source_document_id: int) -> ResearchSourceDetail:
        source = (
            db.query(SourceDocument)
            .filter(SourceDocument.id == source_document_id)
            .first()
        )
        if source is None:
            raise ResearchNotFoundError("Source document not found.")

        total_chunks, embedded_chunks = ResearchService._chunk_counts(
            db, [source.id]
        ).get(source.id, (0, 0))
        return ResearchSourceDetail(
            source_document_id=source.id,
            canonical_source_id=source.source_id,
            title=source.name,
            source_type=source.source_type,
            source_type_label=source_type_label(source.source_type),
            is_current=bool(source.is_current),
            processing_status=str(source.processing_status or "pending"),
            is_indexed=embedded_chunks > 0,
            official_page=source.official_page,
            version=source.version,
            content_type=source.content_type,
            chunk_count=total_chunks,
            embedded_chunk_count=embedded_chunks,
            authority_notice=AUTHORITY_NOTICE,
        )

    @staticmethod
    def get_passage(db: Session, source_chunk_id: int) -> ResearchPassageDetail:
        chunk = (
            db.query(SourceChunk)
            .filter(SourceChunk.id == source_chunk_id)
            .first()
        )
        if chunk is None:
            raise ResearchNotFoundError("Passage not found.")

        source = (
            db.query(SourceDocument)
            .filter(SourceDocument.id == chunk.source_document_id)
            .first()
        )
        if source is None:
            raise ResearchNotFoundError("Passage not found.")

        metadata = _metadata_from_mapping(
            chunk.chunk_metadata if isinstance(chunk.chunk_metadata, dict) else {}
        )
        text = (chunk.text or "")[:RETRIEVAL_MAX_CHUNK_TEXT_CHARS]
        # Check embedding presence without materializing the vector payload.
        embedded = (
            db.query(SourceChunk.id)
            .filter(
                SourceChunk.id == source_chunk_id,
                SourceChunk.embedding.isnot(None),
            )
            .first()
            is not None
        )
        return ResearchPassageDetail(
            source_chunk_id=chunk.id,
            chunk_index=int(chunk.chunk_index),
            source_document_id=source.id,
            canonical_source_id=source.source_id,
            source_title=source.name,
            source_type=source.source_type,
            source_type_label=source_type_label(source.source_type),
            page_number=chunk.page_number,
            section_label=chunk.section_label,
            passage_text=text,
            metadata=metadata,
            processing_status=str(source.processing_status or "pending"),
            is_indexed=bool(embedded),
            authority_notice=AUTHORITY_NOTICE,
        )

    @staticmethod
    def search(db: Session, request: ResearchSearchRequest) -> ResearchSearchResponse:
        source_types = _validate_source_types(request.source_types)
        source_ids = tuple(
            item.strip() for item in request.source_ids if item and item.strip()
        )
        limit = max(1, min(int(request.limit), RETRIEVAL_MAX_TOTAL_RESULT_LIMIT))
        limit_per_source = max(
            1,
            min(int(request.limit_per_source), RETRIEVAL_MAX_PER_SOURCE_RESULT_LIMIT),
        )
        offset = max(0, min(int(request.offset), RESEARCH_MAX_OFFSET))
        fetch_limit = min(offset + limit, RETRIEVAL_MAX_TOTAL_RESULT_LIMIT)

        try:
            result: OrchestrationResult = (
                KnowledgeRetrievalService.retrieve_with_agents(
                    db,
                    request.query[:RETRIEVAL_MAX_QUERY_CHARS],
                    _authorization(),
                    domain=request.domain,
                    limit_per_source=limit_per_source,
                    result_limit=fetch_limit,
                    source_types=source_types,
                    source_ids=source_ids,
                    include_diagnostics=False,
                )
            )
        except RequestValidationError as exc:
            raise ResearchValidationError(str(exc)) from exc

        all_items = [
            ResearchService._result_item(evidence, rank=index + 1)
            for index, evidence in enumerate(result.results)
        ]
        page = all_items[offset : offset + limit]
        ui_status = map_retrieval_ui_status(
            result.status,
            result_count=len(all_items),
            partial=bool(result.partial),
        )
        failures = [_safe_failure(item) for item in result.failures]

        return ResearchSearchResponse(
            query=request.query,
            retrieval_status=ui_status,
            retrieval_status_raw=str(result.status),
            partial=bool(result.partial),
            result_count=len(page),
            total_matched=len(all_items),
            limit=limit,
            offset=offset,
            limit_per_source=limit_per_source,
            results=page,
            failures=failures,
            authority_notice=AUTHORITY_NOTICE,
        )

    @staticmethod
    def _result_item(evidence: RetrievalEvidence, *, rank: int) -> ResearchSearchResultItem:
        metadata = _metadata_from_mapping(dict(evidence.safe_chunk_metadata or {}))
        text = (evidence.chunk_text or "")[:RETRIEVAL_MAX_CHUNK_TEXT_CHARS]
        return ResearchSearchResultItem(
            rank=rank,
            source_document_id=evidence.source_document_id,
            canonical_source_id=evidence.canonical_source_id,
            source_title=evidence.source_title,
            source_type=evidence.source_type,
            source_type_label=source_type_label(evidence.source_type),
            source_chunk_id=evidence.chunk_id,
            chunk_index=evidence.chunk_index,
            page_number=evidence.page_number,
            section=metadata.section or _as_optional_str(
                evidence.safe_chunk_metadata.get("section")
                if evidence.safe_chunk_metadata
                else None
            ),
            article=metadata.article,
            heading=metadata.heading,
            passage_text=text,
            excerpt=_excerpt(text),
            final_relevance_score=round(float(evidence.final_relevance_score), 6),
            normalized_score=round(float(evidence.normalized_score), 6),
            evidence_role=evidence.evidence_role,
            retrieval_agent=evidence.retrieval_agent,
            content_trust=evidence.content_trust,
            provenance=_provenance(evidence),
            metadata=metadata,
        )

    @staticmethod
    def _source_summary(
        source: SourceDocument,
        counts: tuple[int, int],
    ) -> ResearchSourceSummary:
        total_chunks, embedded_chunks = counts
        return ResearchSourceSummary(
            source_document_id=source.id,
            canonical_source_id=source.source_id,
            title=source.name,
            source_type=source.source_type,
            source_type_label=source_type_label(source.source_type),
            is_current=bool(source.is_current),
            processing_status=str(source.processing_status or "pending"),
            is_indexed=embedded_chunks > 0,
            official_page=source.official_page,
            version=source.version,
        )

    @staticmethod
    def _chunk_counts(
        db: Session,
        source_ids: list[int],
    ) -> dict[int, tuple[int, int]]:
        if not source_ids:
            return {}
        rows = (
            db.query(
                SourceChunk.source_document_id,
                func.count(SourceChunk.id).label("total_chunks"),
                func.count(SourceChunk.embedding).label("embedded_chunks"),
            )
            .filter(SourceChunk.source_document_id.in_(source_ids))
            .group_by(SourceChunk.source_document_id)
            .all()
        )
        return {
            int(row.source_document_id): (
                int(row.total_chunks or 0),
                int(row.embedded_chunks or 0),
            )
            for row in rows
        }
