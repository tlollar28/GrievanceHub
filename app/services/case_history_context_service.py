"""Jump-to-context retrieval for Official Case Record events.

Historical viewing never mutates current Case Memory.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.database.models import (
    CaseMessage,
    CaseSavedArtifact,
    CaseTimelineEventRecord,
)
from app.schemas.case_history_context_schema import (
    CaseHistoryContextResponse,
    HistoricalConversationWindow,
)
from app.services.case_service import CaseNotFoundError, CaseService

_CONVERSATION_WINDOW = 8
_EVIDENCE_LIMIT = 10
_DECISION_LIMIT = 8

_OFFICIAL_TYPES = frozenset(
    {
        "analysis_report_saved",
        "analysis_report_saved_and_printed",
        "grievance_form_saved",
        "grievance_form_saved_and_printed",
    }
)
_DRAFT_TYPES = frozenset(
    {
        "analysis_report_generated",
        "form_draft_created",
        "grievance_revision_created",
    }
)
_LIFECYCLE_TYPES = frozenset(
    {
        "case_created",
        "case_opened",
        "case_reopened",
        "case_closed",
        "case_settled",
        "case_archived",
        "step_decision_added",
        "appealed_to_next_step",
        "important_case_decision_recorded",
    }
)


class CaseHistoryContextService:
    """Bounded historical context around a steward-facing case-record event."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def jump_to_context(
        self,
        case_uuid: str,
        event_id: str,
        *,
        conversation_window: int = _CONVERSATION_WINDOW,
    ) -> CaseHistoryContextResponse:
        case = CaseService._get_case_row(self.db, case_uuid)
        if case is None:
            raise CaseNotFoundError(case_uuid)

        event = (
            self.db.query(CaseTimelineEventRecord)
            .filter(
                CaseTimelineEventRecord.case_uuid == case_uuid,
                CaseTimelineEventRecord.event_uuid == event_id,
            )
            .first()
        )
        # Official Case Record may surface artifact-only rows whose event_id is
        # the artifact_uuid (pre-timeline or fallback index items).
        if event is None:
            return self._jump_to_artifact_context(
                case_uuid,
                event_id,
                conversation_window=conversation_window,
            )

        siblings = (
            self.db.query(CaseTimelineEventRecord)
            .filter(CaseTimelineEventRecord.case_uuid == case_uuid)
            .order_by(
                CaseTimelineEventRecord.event_timestamp.asc(),
                CaseTimelineEventRecord.id.asc(),
            )
            .all()
        )
        idx = next(
            (i for i, row in enumerate(siblings) if row.event_uuid == event_id),
            None,
        )
        previous_event = (
            self._event_brief(siblings[idx - 1]) if idx and idx > 0 else None
        )
        next_event = (
            self._event_brief(siblings[idx + 1])
            if idx is not None and idx + 1 < len(siblings)
            else None
        )

        artifact = self._related_artifact(case_uuid, event)
        conversation = self._related_conversation(
            case.id, event, window=max(2, min(conversation_window, 20))
        )
        evidence = self._related_evidence(event, limit=_EVIDENCE_LIMIT)
        decisions = self._related_decisions(case_uuid, event)
        recommendation = self._related_recommendation(case_uuid, event)
        workflow_state = {
            "step_type": event.step_type,
            "event_type": event.event_type,
            "snapshot_confidence": "inferred"
            if event.step_type
            else "unknown",
            "note": "Historical workflow snapshot from event linkage; not a rollback.",
        }

        record_class = self._record_class(event.event_type)
        unavailable: list[str] = []
        if artifact is None and event.export_ref:
            unavailable.append("related_artifact")
        if not conversation.message_ids and not event.follow_up_message_ids:
            unavailable.append("related_conversation")

        retrieval = {
            "workspace": f"/cases/{case_uuid}/workspace",
            "history_context": (
                f"/cases/{case_uuid}/history/{event_id}/context"
            ),
        }
        if artifact:
            retrieval["artifact"] = (
                f"/cases/{case_uuid}/artifacts/{artifact['artifact_uuid']}"
            )
            if artifact.get("pdf_asset_uuid"):
                retrieval["pdf"] = (
                    f"/cases/{case_uuid}/artifacts/{artifact['artifact_uuid']}/pdf"
                )
        if event.report_version_number is not None:
            retrieval["report_version"] = (
                f"/cases/{case_uuid}/reports/{event.report_version_number}"
            )

        return CaseHistoryContextResponse(
            case_uuid=case_uuid,
            event_id=event_id,
            event_details={
                "event_uuid": event.event_uuid,
                "event_type": event.event_type,
                "title": event.title,
                "details": event.details,
                "event_timestamp": event.event_timestamp.isoformat()
                if event.event_timestamp
                else None,
                "step_type": event.step_type,
                "report_version_number": event.report_version_number,
                "export_ref": event.export_ref,
                "upload_refs": list(event.upload_refs or []),
                "follow_up_message_ids": list(event.follow_up_message_ids or []),
                "outcome_uuid": event.outcome_uuid,
            },
            related_artifact=artifact,
            related_conversation=conversation,
            related_evidence=evidence,
            related_workflow_state=workflow_state,
            related_decisions=decisions,
            related_recommendation=recommendation,
            previous_event=previous_event,
            next_event=next_event,
            retrieval_references=retrieval,
            record_class=record_class,  # type: ignore[arg-type]
            mutates_current_memory=False,
            historical_focus_ref={
                "case_uuid": case_uuid,
                "event_id": event_id,
                "event_type": event.event_type,
                "record_class": record_class,
                "use_with": [
                    "current_case_memory",
                    "selected_historical_event_context",
                    "retrieved_supporting_records",
                ],
                "erases_current_state": False,
            },
            unavailable_fields=unavailable,
        )

    def _jump_to_artifact_context(
        self,
        case_uuid: str,
        artifact_uuid: str,
        *,
        conversation_window: int,
    ) -> CaseHistoryContextResponse:
        row = (
            self.db.query(CaseSavedArtifact)
            .filter(
                CaseSavedArtifact.case_uuid == case_uuid,
                CaseSavedArtifact.artifact_uuid == artifact_uuid,
            )
            .first()
        )
        if row is None:
            raise CaseNotFoundError(f"event:{artifact_uuid}")

        event_type = (
            "analysis_report_saved_and_printed"
            if row.artifact_type == "analysis_report"
            else "grievance_form_saved_and_printed"
        )
        artifact = {
            "artifact_uuid": row.artifact_uuid,
            "artifact_type": row.artifact_type,
            "title": row.title,
            "version_number": row.version_number,
            "version_label": row.version_label,
            "grievance_step": row.grievance_step,
            "printed": bool(row.printed),
            "pdf_asset_uuid": row.pdf_asset_uuid,
            "is_latest_official": bool(row.is_latest_official),
            "key_summary": row.key_summary_json,
            "content_embedded": False,
            "record_class": "official_record",
        }
        case = CaseService._get_case_row(self.db, case_uuid)
        conversation = HistoricalConversationWindow(
            bounded=True,
            full_transcript_replayed=False,
            window_size=0,
        )
        if case is not None:
            nearby = (
                self.db.query(CaseMessage)
                .filter(CaseMessage.case_id == case.id)
                .order_by(CaseMessage.created_at.desc())
                .limit(max(2, min(conversation_window, 20)))
                .all()
            )
            nearby = list(reversed(nearby))
            conversation = HistoricalConversationWindow(
                message_ids=[m.id for m in nearby],
                messages=[self._message_brief(m) for m in nearby],
                bounded=True,
                full_transcript_replayed=False,
                window_size=len(nearby),
            )

        return CaseHistoryContextResponse(
            case_uuid=case_uuid,
            event_id=artifact_uuid,
            event_details={
                "event_uuid": artifact_uuid,
                "event_type": event_type,
                "title": row.version_label,
                "details": "Official saved artifact",
                "event_timestamp": row.saved_at.isoformat() if row.saved_at else None,
                "step_type": row.grievance_step,
                "export_ref": row.artifact_uuid,
                "source": "artifact_index_fallback",
            },
            related_artifact=artifact,
            related_conversation=conversation,
            related_evidence=[],
            related_workflow_state={
                "step_type": row.grievance_step,
                "event_type": event_type,
                "snapshot_confidence": "inferred",
                "note": "Historical workflow snapshot from artifact linkage; not a rollback.",
            },
            related_decisions=[],
            related_recommendation=None,
            previous_event=None,
            next_event=None,
            retrieval_references={
                "workspace": f"/cases/{case_uuid}/workspace",
                "history_context": (
                    f"/cases/{case_uuid}/history/{artifact_uuid}/context"
                ),
                "artifact": f"/cases/{case_uuid}/artifacts/{artifact_uuid}",
                **(
                    {
                        "pdf": (
                            f"/cases/{case_uuid}/artifacts/{artifact_uuid}/pdf"
                        )
                    }
                    if row.pdf_asset_uuid
                    else {}
                ),
            },
            record_class="official_record",
            mutates_current_memory=False,
            historical_focus_ref={
                "case_uuid": case_uuid,
                "event_id": artifact_uuid,
                "event_type": event_type,
                "record_class": "official_record",
                "use_with": [
                    "current_case_memory",
                    "selected_historical_event_context",
                    "retrieved_supporting_records",
                ],
                "erases_current_state": False,
            },
            unavailable_fields=[
                "previous_event",
                "next_event",
                "related_recommendation",
            ],
        )

    def _related_artifact(
        self, case_uuid: str, event: CaseTimelineEventRecord
    ) -> dict[str, Any] | None:
        artifact_uuid = event.export_ref
        if not artifact_uuid:
            return None
        row = (
            self.db.query(CaseSavedArtifact)
            .filter(
                CaseSavedArtifact.case_uuid == case_uuid,
                CaseSavedArtifact.artifact_uuid == artifact_uuid,
            )
            .first()
        )
        if row is None:
            return None
        return {
            "artifact_uuid": row.artifact_uuid,
            "artifact_type": row.artifact_type,
            "title": row.title,
            "version_number": row.version_number,
            "version_label": row.version_label,
            "grievance_step": row.grievance_step,
            "printed": bool(row.printed),
            "pdf_asset_uuid": row.pdf_asset_uuid,
            "is_latest_official": bool(row.is_latest_official),
            "key_summary": row.key_summary_json,
            "content_embedded": False,
            "record_class": "official_record",
        }

    def _related_conversation(
        self,
        case_id: int,
        event: CaseTimelineEventRecord,
        *,
        window: int,
    ) -> HistoricalConversationWindow:
        message_ids = list(event.follow_up_message_ids or [])
        if not message_ids:
            # Bounded nearby messages by timestamp — never full transcript.
            nearby = (
                self.db.query(CaseMessage)
                .filter(CaseMessage.case_id == case_id)
                .order_by(CaseMessage.created_at.desc())
                .limit(window)
                .all()
            )
            nearby = list(reversed(nearby))
            return HistoricalConversationWindow(
                message_ids=[m.id for m in nearby],
                messages=[self._message_brief(m) for m in nearby],
                bounded=True,
                full_transcript_replayed=False,
                window_size=len(nearby),
            )

        rows = (
            self.db.query(CaseMessage)
            .filter(
                CaseMessage.case_id == case_id,
                CaseMessage.id.in_(message_ids[:window]),
            )
            .order_by(CaseMessage.created_at.asc())
            .all()
        )
        return HistoricalConversationWindow(
            message_ids=[m.id for m in rows],
            messages=[self._message_brief(m) for m in rows],
            bounded=True,
            full_transcript_replayed=False,
            window_size=len(rows),
        )

    def _related_evidence(
        self, event: CaseTimelineEventRecord, *, limit: int
    ) -> list[dict[str, Any]]:
        refs = list(event.upload_refs or [])[:limit]
        return [
            {
                "asset_uuid": ref,
                "retrieval_path": None,
                "source": "timeline_upload_ref",
            }
            for ref in refs
        ]

    def _related_decisions(
        self, case_uuid: str, event: CaseTimelineEventRecord
    ) -> list[dict[str, Any]]:
        from app.services.case_memory_service import CaseMemoryService

        try:
            memory = CaseMemoryService(self.db).load(case_uuid, commit=False)
        except CaseNotFoundError:
            return []
        decisions = list(memory.get("decisions") or memory.get("important_decisions") or [])
        # Prefer decisions near this event; do not invent history.
        matched = [
            d
            for d in decisions
            if d.get("event_id") == event.event_uuid
            or (
                event.outcome_uuid
                and d.get("outcome_uuid") == event.outcome_uuid
            )
        ]
        if not matched and event.event_type in {
            "step_decision_added",
            "important_case_decision_recorded",
        }:
            matched = [
                {
                    "decision_summary": event.details or event.title,
                    "step_type": event.step_type,
                    "source": "timeline",
                    "confidence": "inferred",
                    "kind": "steward_decision",
                }
            ]
        return matched[:_DECISION_LIMIT]

    def _related_recommendation(
        self, case_uuid: str, event: CaseTimelineEventRecord
    ) -> dict[str, Any] | None:
        from app.services.case_memory_service import CaseMemoryService

        try:
            memory = CaseMemoryService(self.db).load(case_uuid, commit=False)
        except CaseNotFoundError:
            return None
        recs = memory.get("recommendations") or {}
        history = list(recs.get("history") or [])
        for item in reversed(history):
            if item.get("source_interaction_id") == event.event_uuid:
                return item
        current = recs.get("current")
        if isinstance(current, dict) and event.event_type in {
            "analysis_report_saved_and_printed",
            "analysis_report_generated",
            "management_response_uploaded",
        }:
            # Mark as current-case projection, not confirmed historical.
            return {
                **current,
                "historical_confidence": "unavailable",
                "note": "Exact historical recommendation at event time unavailable; "
                "current recommendation shown for orientation only.",
            }
        return None

    @staticmethod
    def _record_class(event_type: str) -> str:
        if event_type in _OFFICIAL_TYPES:
            return "official_record"
        if event_type in _DRAFT_TYPES:
            return "working_draft"
        if event_type in _LIFECYCLE_TYPES:
            return "lifecycle"
        return "other"

    @staticmethod
    def _event_brief(row: CaseTimelineEventRecord) -> dict[str, Any]:
        return {
            "event_id": row.event_uuid,
            "event_type": row.event_type,
            "title": row.title,
            "event_timestamp": row.event_timestamp.isoformat()
            if row.event_timestamp
            else None,
        }

    @staticmethod
    def _message_brief(message: CaseMessage) -> dict[str, Any]:
        content = message.content or ""
        # Bound message content in historical window.
        if len(content) > 500:
            content = content[:500] + "…"
        return {
            "message_id": message.id,
            "role": message.role,
            "content": content,
            "created_at": message.created_at.isoformat()
            if message.created_at
            else None,
            "full_content_embedded": False,
        }
