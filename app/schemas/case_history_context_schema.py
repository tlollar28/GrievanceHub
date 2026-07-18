"""Jump-to-context contracts for Official Case Record events."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class HistoricalConversationWindow(BaseModel):
    message_ids: list[int] = Field(default_factory=list)
    messages: list[dict[str, Any]] = Field(default_factory=list)
    bounded: bool = True
    full_transcript_replayed: bool = False
    window_size: int = 0


class CaseHistoryContextResponse(BaseModel):
    """Bounded historical context around one Official Case Record event."""

    case_uuid: str
    event_id: str
    event_details: dict[str, Any]
    related_artifact: dict[str, Any] | None = None
    related_conversation: HistoricalConversationWindow = Field(
        default_factory=HistoricalConversationWindow
    )
    related_evidence: list[dict[str, Any]] = Field(default_factory=list)
    related_workflow_state: dict[str, Any] | None = None
    related_decisions: list[dict[str, Any]] = Field(default_factory=list)
    related_recommendation: dict[str, Any] | None = None
    previous_event: dict[str, Any] | None = None
    next_event: dict[str, Any] | None = None
    retrieval_references: dict[str, str] = Field(default_factory=dict)
    record_class: Literal["working_draft", "official_record", "lifecycle", "other"] = (
        "other"
    )
    mutates_current_memory: bool = False
    historical_focus_ref: dict[str, Any] | None = None
    unavailable_fields: list[str] = Field(default_factory=list)
