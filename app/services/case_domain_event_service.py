"""Internal domain-event publish/dispatch for Case Memory projections.

Synchronous in-process delivery: persist event → apply memory handlers →
optionally append steward timeline. No external broker.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.database.models import CaseDomainEvent, CaseTimelineEventRecord, GrievanceCase
from app.schemas.case_domain_event_schema import (
    DOMAIN_EVENT_SCHEMA,
    CaseDomainEventPayload,
    CaseDomainEventRecord,
)
from app.services.case_service import CaseNotFoundError, CaseService

# Steward-facing titles for selected domain events (Official Case Record).
_STEWARD_TITLES: dict[str, str] = {
    "case_created": "Case created",
    "evidence_uploaded": "Evidence uploaded",
    "management_response_uploaded": "Management response uploaded",
    "analysis_generated": "Analysis generated",
    "analysis_saved": "Analysis Report saved",
    "analysis_saved_and_printed": "Analysis Report saved and printed",
    "grievance_generated": "Grievance generated",
    "grievance_saved": "Grievance saved",
    "grievance_saved_and_printed": "Grievance saved and printed",
    "grievance_revised": "Grievance revised",
    "outcome_recorded": "Outcome recorded",
    "case_closed": "Case closed",
    "case_settled": "Case settled",
    "case_reopened": "Case reopened",
}

# Map domain event types → steward timeline event_type when appending.
_STEWARD_TIMELINE_TYPE: dict[str, str] = {
    "case_created": "case_created",
    "evidence_uploaded": "files_uploaded",
    "management_response_uploaded": "management_response_uploaded",
    "analysis_generated": "analysis_report_generated",
    "analysis_saved": "analysis_report_saved",
    "analysis_saved_and_printed": "analysis_report_saved_and_printed",
    "grievance_generated": "form_draft_created",
    "grievance_saved": "grievance_form_saved",
    "grievance_saved_and_printed": "grievance_form_saved_and_printed",
    "grievance_revised": "grievance_revision_created",
    "outcome_recorded": "step_decision_added",
    "case_closed": "case_closed",
    "case_settled": "case_settled",
    "case_reopened": "case_reopened",
}


class CaseDomainEventService:
    """Publish and synchronously apply case-domain events."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def publish(
        self,
        case_uuid: str,
        *,
        event_type: str,
        actor_id: str | None = None,
        grievance_step: str | None = None,
        source_type: str | None = None,
        source_uuid: str | None = None,
        metadata: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
        occurred_at: datetime | None = None,
        append_steward_timeline: bool = False,
        steward_timeline_title: str | None = None,
        steward_timeline_details: str | None = None,
        apply_to_memory: bool = True,
        commit: bool = True,
    ) -> CaseDomainEventRecord:
        payload = CaseDomainEventPayload(
            case_uuid=case_uuid,
            event_type=event_type,
            occurred_at=occurred_at,
            actor_id=actor_id,
            grievance_step=grievance_step,
            source_type=source_type,
            source_uuid=source_uuid,
            metadata=metadata or {},
            idempotency_key=idempotency_key,
            append_steward_timeline=append_steward_timeline,
            steward_timeline_title=steward_timeline_title,
            steward_timeline_details=steward_timeline_details,
        )
        return self.publish_payload(
            payload,
            apply_to_memory=apply_to_memory,
            commit=commit,
        )

    def publish_payload(
        self,
        payload: CaseDomainEventPayload,
        *,
        apply_to_memory: bool = True,
        commit: bool = True,
    ) -> CaseDomainEventRecord:
        case = CaseService._get_case_row(self.db, payload.case_uuid)
        if case is None:
            raise CaseNotFoundError(payload.case_uuid)

        if payload.idempotency_key:
            existing = (
                self.db.query(CaseDomainEvent)
                .filter(
                    CaseDomainEvent.case_uuid == payload.case_uuid,
                    CaseDomainEvent.idempotency_key == payload.idempotency_key,
                )
                .first()
            )
            # Ignore non-model stubs from unit-test MagicMock sessions.
            if isinstance(existing, CaseDomainEvent):
                return self._to_record(existing, already_processed=True)

        now = payload.occurred_at or datetime.utcnow()
        row = CaseDomainEvent(
            event_id=payload.event_id or str(uuid4()),
            case_id=case.id,
            case_uuid=payload.case_uuid,
            event_type=str(payload.event_type),
            occurred_at=now,
            actor_id=payload.actor_id,
            grievance_step=payload.grievance_step,
            source_type=payload.source_type,
            source_uuid=payload.source_uuid,
            metadata_json=dict(payload.metadata or {}),
            idempotency_key=payload.idempotency_key,
            schema_version=payload.schema_version or DOMAIN_EVENT_SCHEMA,
            processing_status="pending",
            created_at=datetime.utcnow(),
        )
        self.db.add(row)
        self.db.flush()

        timeline_uuid = None
        if payload.append_steward_timeline:
            timeline_uuid = self._append_steward_timeline(
                case,
                event_type=str(payload.event_type),
                title=payload.steward_timeline_title
                or _STEWARD_TITLES.get(str(payload.event_type))
                or str(payload.event_type),
                details=payload.steward_timeline_details,
                grievance_step=payload.grievance_step,
                source_uuid=payload.source_uuid,
                metadata=payload.metadata or {},
                occurred_at=now,
            )
            row.steward_timeline_event_uuid = timeline_uuid

        if apply_to_memory:
            from app.services.case_memory_service import CaseMemoryService

            try:
                CaseMemoryService(self.db).apply_event(
                    self._to_record(row),
                    commit=False,
                )
            except Exception:
                # Memory projection failure must not discard the persisted event row
                # in the same unit of work; caller transaction decides commit/rollback.
                row.processing_status = "memory_apply_failed"
            else:
                row.processing_status = "processed"
                row.processed_at = datetime.utcnow()
        else:
            row.processing_status = "processed"
            row.processed_at = datetime.utcnow()

        if row.processing_status == "pending":
            row.processing_status = "processed"
            row.processed_at = datetime.utcnow()
        if commit:
            self.db.commit()
            self.db.refresh(row)
        else:
            self.db.flush()
        return self._to_record(row, already_processed=False)

    def get_event(self, case_uuid: str, event_id: str) -> CaseDomainEventRecord:
        row = (
            self.db.query(CaseDomainEvent)
            .filter(
                CaseDomainEvent.case_uuid == case_uuid,
                CaseDomainEvent.event_id == event_id,
            )
            .first()
        )
        if not isinstance(row, CaseDomainEvent):
            raise CaseNotFoundError(f"{case_uuid}:{event_id}")
        return self._to_record(row)

    def list_events(
        self,
        case_uuid: str,
        *,
        limit: int = 100,
        event_type: str | None = None,
    ) -> list[CaseDomainEventRecord]:
        case = CaseService._get_case_row(self.db, case_uuid)
        if case is None:
            raise CaseNotFoundError(case_uuid)
        q = self.db.query(CaseDomainEvent).filter(
            CaseDomainEvent.case_uuid == case_uuid
        )
        if event_type:
            q = q.filter(CaseDomainEvent.event_type == event_type)
        rows = (
            q.order_by(CaseDomainEvent.occurred_at.asc(), CaseDomainEvent.id.asc())
            .limit(max(1, min(limit, 200)))
            .all()
        )
        return [
            self._to_record(r) for r in rows if isinstance(r, CaseDomainEvent)
        ]

    def _append_steward_timeline(
        self,
        case: GrievanceCase,
        *,
        event_type: str,
        title: str,
        details: str | None,
        grievance_step: str | None,
        source_uuid: str | None,
        metadata: dict[str, Any],
        occurred_at: datetime,
    ) -> str:
        timeline_type = _STEWARD_TIMELINE_TYPE.get(event_type, event_type)
        event_uuid = str(uuid4())
        self.db.add(
            CaseTimelineEventRecord(
                event_uuid=event_uuid,
                case_id=case.id,
                case_uuid=case.case_uuid,
                step_type=grievance_step,
                event_type=timeline_type,
                event_timestamp=occurred_at,
                title=title,
                details=details,
                report_version_number=metadata.get("report_version_number"),
                follow_up_message_ids=metadata.get("message_ids"),
                upload_refs=metadata.get("upload_refs")
                or ([source_uuid] if source_uuid and event_type.endswith("uploaded") else None),
                export_ref=metadata.get("artifact_uuid") or source_uuid,
                outcome_uuid=metadata.get("outcome_uuid"),
                created_at=datetime.utcnow(),
            )
        )
        self.db.flush()
        return event_uuid

    @staticmethod
    def _to_record(
        row: CaseDomainEvent, *, already_processed: bool = False
    ) -> CaseDomainEventRecord:
        return CaseDomainEventRecord(
            event_id=row.event_id,
            case_uuid=row.case_uuid,
            event_type=row.event_type,
            occurred_at=row.occurred_at,
            actor_id=row.actor_id,
            grievance_step=row.grievance_step,
            source_type=row.source_type,
            source_uuid=row.source_uuid,
            metadata=dict(row.metadata_json or {}),
            idempotency_key=row.idempotency_key,
            schema_version=row.schema_version or DOMAIN_EVENT_SCHEMA,
            processing_status=row.processing_status,
            processed_at=row.processed_at,
            steward_timeline_event_uuid=row.steward_timeline_event_uuid,
            already_processed=already_processed
            or row.processing_status == "processed",
        )
