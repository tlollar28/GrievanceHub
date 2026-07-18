"""Pydantic models for follow-up Q&A grounded in saved case reports."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class FollowUpRequest(BaseModel):
    content: str = Field(..., min_length=1, description="The steward's follow-up question")
    report_version: int | None = Field(
        default=None,
        description="Pinned report version number; null uses the latest saved version",
    )


class FollowUpCitation(BaseModel):
    document_type: str = ""
    document_name: str = ""
    article_or_section: str = ""
    page: int | None = None
    quote: str = ""
    grounded: bool = True
    grounding_provenance: Literal[
        "retrieved_passage",
        "saved_report_authority",
        "ungrounded",
    ] = "ungrounded"
    grounding_passage_index: int | None = None
    grounding_authority_index: int | None = None


class FollowUpMessageSummary(BaseModel):
    id: int
    role: str
    content: str
    metadata: dict[str, Any] | None = None
    created_at: str | None = None


class LinkedReportVersionSummary(BaseModel):
    id: int
    version_number: int


class FollowUpAnswerPayload(BaseModel):
    answer: str
    answer_type: Literal[
        "fact",
        "argument",
        "citation",
        "remedy",
        "procedural",
        "uncertainty",
        "action",
        "missing_evidence",
    ] = "fact"
    citations: list[FollowUpCitation] = Field(default_factory=list)
    disclosures: list[str] = Field(default_factory=list)
    facts_needed: list[str] = Field(default_factory=list)
    requires_report_regen: bool = False
    suggested_actions: list[str] = Field(default_factory=list)


class FollowUpResponse(BaseModel):
    user_message: FollowUpMessageSummary
    assistant_message: FollowUpMessageSummary
    answer: str
    answer_type: str
    citations: list[FollowUpCitation]
    disclosures: list[str]
    facts_needed: list[str]
    linked_report_version: LinkedReportVersionSummary
    requires_report_regen: bool = False
    suggested_actions: list[str] = Field(default_factory=list)


class FollowUpThreadResponse(BaseModel):
    case_uuid: str
    linked_report_version: LinkedReportVersionSummary | None = None
    messages: list[FollowUpMessageSummary] = Field(default_factory=list)
