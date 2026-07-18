"""Internal case-domain event contracts (not steward timeline substitutes)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

DomainEventType = Literal[
    "case_created",
    "conversation_meaning_recorded",
    "evidence_uploaded",
    "management_response_uploaded",
    "analysis_generated",
    "analysis_saved",
    "analysis_saved_and_printed",
    "grievance_generated",
    "grievance_saved",
    "grievance_saved_and_printed",
    "grievance_revised",
    "workflow_state_changed",
    "outcome_recorded",
    "case_closed",
    "case_settled",
    "case_reopened",
    "recommendation_updated",
]

DOMAIN_EVENT_SCHEMA = "case_domain_event_v1"


class CaseDomainEventPayload(BaseModel):
    """Explicit domain-event contract for Case Memory / workflow projections."""

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    case_uuid: str
    event_type: DomainEventType | str
    occurred_at: datetime | None = None
    actor_id: str | None = None
    grievance_step: str | None = None
    source_type: str | None = None
    source_uuid: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None
    schema_version: str = DOMAIN_EVENT_SCHEMA
    append_steward_timeline: bool = False
    steward_timeline_title: str | None = None
    steward_timeline_details: str | None = None


class CaseDomainEventRecord(BaseModel):
    event_id: str
    case_uuid: str
    event_type: str
    occurred_at: datetime
    actor_id: str | None = None
    grievance_step: str | None = None
    source_type: str | None = None
    source_uuid: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None
    schema_version: str = DOMAIN_EVENT_SCHEMA
    processing_status: str = "pending"
    processed_at: datetime | None = None
    steward_timeline_event_uuid: str | None = None
    already_processed: bool = False
