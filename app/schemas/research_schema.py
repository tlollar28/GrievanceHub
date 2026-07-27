"""Browser-safe Pydantic contracts for W6 Sources Research.

Interim read-only boundary: allowlisted fields only. Never serialize embeddings,
filesystem paths, provider secrets, SQL, or authorization predicates.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ResearchUiStatus = Literal["ok", "empty", "failed", "skipped", "partial"]


class ResearchFailure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    retriable: bool = False


class ResearchPassageMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    article: str | None = None
    chapter: str | None = None
    heading: str | None = None
    page: int | str | None = None
    section: str | None = None


class ResearchSearchResultItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rank: int
    source_document_id: int
    canonical_source_id: str
    source_title: str
    source_type: str
    source_type_label: str
    source_chunk_id: int
    chunk_index: int
    page_number: int | None = None
    section: str | None = None
    article: str | None = None
    heading: str | None = None
    passage_text: str
    excerpt: str
    final_relevance_score: float
    normalized_score: float
    evidence_role: str
    retrieval_agent: str
    content_trust: str
    provenance: str
    metadata: ResearchPassageMetadata = Field(default_factory=ResearchPassageMetadata)


class ResearchSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., min_length=1, max_length=2000)
    source_types: list[str] = Field(default_factory=list, max_length=16)
    source_ids: list[str] = Field(default_factory=list, max_length=16)
    limit: int = Field(default=12, ge=1, le=24)
    limit_per_source: int = Field(default=3, ge=1, le=5)
    offset: int = Field(default=0, ge=0, le=200)
    domain: str = Field(default="auto", max_length=64)

    @field_validator("query")
    @classmethod
    def strip_query(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("query must not be empty")
        return cleaned

    @field_validator("source_ids")
    @classmethod
    def normalize_source_ids(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in value:
            text = str(item or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            cleaned.append(text)
        return cleaned

    @field_validator("source_types")
    @classmethod
    def normalize_source_types(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in value:
            text = str(item or "").strip().upper()
            if not text or text in seen:
                continue
            seen.add(text)
            cleaned.append(text)
        return cleaned

    @field_validator("domain")
    @classmethod
    def normalize_domain(cls, value: str) -> str:
        return value.strip().lower() or "auto"


class ResearchSearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    retrieval_status: ResearchUiStatus
    retrieval_status_raw: str
    partial: bool
    result_count: int
    total_matched: int
    limit: int
    offset: int
    limit_per_source: int
    results: list[ResearchSearchResultItem]
    failures: list[ResearchFailure]
    authority_notice: str


class ResearchSourceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_document_id: int
    canonical_source_id: str
    title: str
    source_type: str
    source_type_label: str
    is_current: bool
    processing_status: str
    is_indexed: bool
    official_page: str | None = None
    version: str | None = None


class ResearchSourceListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    count: int
    total: int
    limit: int
    offset: int
    sources: list[ResearchSourceSummary]
    authority_notice: str


class ResearchSourceDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_document_id: int
    canonical_source_id: str
    title: str
    source_type: str
    source_type_label: str
    is_current: bool
    processing_status: str
    is_indexed: bool
    official_page: str | None = None
    version: str | None = None
    content_type: str | None = None
    chunk_count: int
    embedded_chunk_count: int
    authority_notice: str


class ResearchPassageDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_chunk_id: int
    chunk_index: int
    source_document_id: int
    canonical_source_id: str
    source_title: str
    source_type: str
    source_type_label: str
    page_number: int | None = None
    section_label: str | None = None
    passage_text: str
    metadata: ResearchPassageMetadata = Field(default_factory=ResearchPassageMetadata)
    processing_status: str
    is_indexed: bool
    authority_notice: str


class ResearchSupportedFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str
    label: str


class ResearchMetaResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_types: list[ResearchSupportedFilter]
    default_limit: int
    max_limit: int
    default_limit_per_source: int
    max_limit_per_source: int
    max_offset: int
    max_query_chars: int
    authority_notice: str
    boundary: str
