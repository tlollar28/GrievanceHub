"""Structured AI recommendation contracts (distinct from steward decisions)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

RecommendationStatus = Literal[
    "current",
    "superseded",
    "pending_more_evidence",
    "no_recommendation",
]


class AiRecommendation(BaseModel):
    """AI recommendation projection — never presented as a steward decision."""

    recommendation: str | None = None
    rationale: str | None = None
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    supporting_artifact_ids: list[str] = Field(default_factory=list)
    confidence: str | None = None
    recommended_step: str | None = None
    blockers: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    generated_at: datetime | None = None
    updated_at: datetime | None = None
    source_interaction_id: str | None = None
    source_report_version_number: int | None = None
    status: RecommendationStatus | str = "no_recommendation"
    kind: Literal["ai_recommendation"] = "ai_recommendation"


class StewardDecisionView(BaseModel):
    """Steward decision projection — distinct from AI recommendation."""

    decision_summary: str | None = None
    outcome_type: str | None = None
    step_type: str | None = None
    recorded_at: datetime | None = None
    source: str | None = None
    kind: Literal["steward_decision"] = "steward_decision"
