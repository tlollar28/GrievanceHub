"""First-class Case Memory — durable structured understanding of a case.

Physically stored as versioned JSON (case_memory_v1). Logically modular:
each domain event updates only the affected sections via apply_event.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.database.models import CaseMemoryRecord, GrievanceCase
from app.schemas.case_domain_event_schema import CaseDomainEventRecord
from app.schemas.case_memory_schema import CaseOverview
from app.schemas.case_recommendation_schema import AiRecommendation
from app.services.case_service import CaseNotFoundError, CaseService

CASE_MEMORY_SCHEMA = "case_memory_v1"
CASE_MEMORY_SCHEMA_NEXT = "case_memory_v2"

REQUIRED_SECTIONS = (
    "identity_and_facts",
    "status_and_lifecycle",
    "workflow",
    "decisions",
    "conclusions",
    "union_arguments",
    "management_arguments",
    "evidence",
    "reports",
    "grievances",
    "conversations",
    "open_questions",
    "resolved_questions",
    "outstanding_issues",
    "recommendations",
    "relationships",
    "official_artifacts",
    "settlement",
    "closure",
    "reopen_history",
)

_MAX_LIST = 40
_MAX_MEANINGS = 30
_MAX_RELATIONSHIPS = 50
_MAX_DECISIONS = 40
_MAX_OPEN_QUESTIONS = 40
_MAX_EVIDENCE = 40
_MAX_ARTIFACT_INDEX = 40
_MAX_RECOMMENDATION_HISTORY = 20


def _now() -> datetime:
    return datetime.utcnow()


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


class CaseMemoryService:
    """Owns load/update of durable Case Memory and Case Overview."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Core load / ensure
    # ------------------------------------------------------------------

    def ensure(self, case_uuid: str, *, commit: bool = True) -> CaseMemoryRecord:
        case = self._require_case(case_uuid)
        return self.ensure_for_case(case, commit=commit)

    def ensure_for_case(
        self, case: GrievanceCase, *, commit: bool = True
    ) -> CaseMemoryRecord:
        row = (
            self.db.query(CaseMemoryRecord)
            .filter(CaseMemoryRecord.case_uuid == case.case_uuid)
            .first()
        )
        if isinstance(row, CaseMemoryRecord):
            raw = (
                deepcopy(row.memory_json) if isinstance(row.memory_json, dict) else {}
            )
            memory = self.normalize_memory(raw)
            # Only write when normalization added required structure.
            if memory != raw or not row.workflow_state:
                row.memory_json = memory
                if not row.workflow_state:
                    wf = memory.get("workflow") or {}
                    row.workflow_state = (
                        wf.get("explicit_state") if isinstance(wf, dict) else None
                    ) or "case_open"
                if commit:
                    self.db.commit()
                    self.db.refresh(row)
                else:
                    self.db.flush()
            return row
        now = _now()
        memory = self._initial_memory(case)
        row = CaseMemoryRecord(
            case_id=case.id,
            case_uuid=case.case_uuid,
            schema_version=CASE_MEMORY_SCHEMA,
            memory_json=memory,
            workflow_state="case_open",
            reopen_count=0,
            created_at=now,
            updated_at=now,
        )
        self.db.add(row)
        if commit:
            self.db.commit()
            self.db.refresh(row)
        else:
            self.db.flush()
        return row

    def load(self, case_uuid: str, *, commit: bool = True) -> dict[str, Any]:
        row = self.ensure(case_uuid, commit=commit)
        memory = deepcopy(row.memory_json) if isinstance(row.memory_json, dict) else {}
        memory = self.normalize_memory(memory)
        memory["reopen_count"] = int(row.reopen_count or memory.get("reopen_count") or 0)
        memory["schema_version"] = row.schema_version or CASE_MEMORY_SCHEMA
        return memory

    def get_row(self, case_uuid: str) -> CaseMemoryRecord:
        return self.ensure(case_uuid, commit=True)

    def get_overview(self, case_uuid: str) -> CaseOverview:
        memory = self.load(case_uuid)
        return self._overview_from_memory(case_uuid, memory)

    def to_ai_foundation(self, case_uuid: str) -> dict[str, Any]:
        """Bounded Case Memory foundation for AI (not transcript replay)."""
        memory = self.load(case_uuid)
        recommendation = self._current_recommendation(memory)
        return {
            "schema_version": memory.get("schema_version") or CASE_MEMORY_SCHEMA,
            "case_is_system_of_record": True,
            "restored_from": "case_memory",
            "identity_and_facts": memory.get("identity_and_facts") or {},
            "facts": memory.get("facts") or {},
            "status": memory.get("status"),
            "status_and_lifecycle": memory.get("status_and_lifecycle") or {},
            "current_grievance_step": memory.get("current_grievance_step"),
            "workflow": memory.get("workflow") or {},
            "workflow_state": memory.get("workflow_state") or memory.get("workflow") or {},
            "important_decisions": (memory.get("decisions") or memory.get("important_decisions") or [])[-12:],
            "important_conclusions": (memory.get("conclusions") or memory.get("important_conclusions") or [])[-12:],
            "union_arguments": (memory.get("union_arguments") or [])[-10:],
            "management_arguments": (memory.get("management_arguments") or [])[-10:],
            "evidence_summaries": (
                (memory.get("evidence") or {}).get("summaries")
                or memory.get("evidence_summaries")
                or []
            )[-15:],
            "open_questions": (memory.get("open_questions") or [])[:20],
            "resolved_questions": (memory.get("resolved_questions") or [])[-15:],
            "outstanding_issues": (memory.get("outstanding_issues") or [])[:20],
            "conversation_meanings": (
                (memory.get("conversations") or {}).get("meanings")
                or memory.get("conversation_meanings")
                or []
            )[-12:],
            "conversation_summaries": (
                (memory.get("conversations") or {}).get("summaries")
                or memory.get("conversation_summaries")
                or []
            )[-8:],
            "grievance_history": (
                (memory.get("grievances") or {}).get("history")
                or memory.get("grievance_history")
                or []
            )[-12:],
            "analysis_reports": (
                (memory.get("reports") or {}).get("items")
                or memory.get("analysis_reports")
                or []
            )[-8:],
            "official_artifacts": memory.get("official_artifacts") or {
                "latest": {},
                "all": [],
            },
            "relationships": (memory.get("relationships") or [])[-20:],
            "settlement": memory.get("settlement") or {},
            "closure": memory.get("closure") or {},
            "reopen_history": (memory.get("reopen_history") or [])[-10:],
            "reopen_count": int(memory.get("reopen_count") or 0),
            "recommendations": memory.get("recommendations") or {},
            "current_recommendation": recommendation.get("recommendation")
            if recommendation
            else memory.get("current_recommendation"),
            "ai_recommendation": recommendation,
            "overview": memory.get("overview") or {},
            "full_transcript_embedded": False,
            "full_artifact_bodies_embedded": False,
            "sections": list(REQUIRED_SECTIONS),
        }

    # ------------------------------------------------------------------
    # Event-driven modular updates
    # ------------------------------------------------------------------

    def apply_event(
        self,
        event: CaseDomainEventRecord,
        *,
        commit: bool = True,
    ) -> dict[str, Any]:
        """Route a domain event to section handlers; update only affected sections."""
        memory = self.load(event.case_uuid, commit=False)
        before_keys = {k: deepcopy(memory.get(k)) for k in REQUIRED_SECTIONS}
        meta = dict(event.metadata or {})
        event_type = event.event_type

        if event_type == "case_created":
            self._section_identity(memory, meta)
            self._section_status(memory, status="open")
            self._section_workflow_set(memory, "case_open", event.grievance_step)
        elif event_type == "conversation_meaning_recorded":
            self._section_conversation(memory, meta, event)
            self._maybe_update_recommendation(memory, meta, event, trigger="conversation")
        elif event_type == "evidence_uploaded":
            self._section_evidence(memory, meta, management=False)
            self._maybe_update_recommendation(memory, meta, event, trigger="evidence")
        elif event_type == "management_response_uploaded":
            self._section_evidence(memory, meta, management=True)
            self._maybe_update_recommendation(
                memory, meta, event, trigger="management_response"
            )
        elif event_type == "analysis_generated":
            self._section_report(memory, meta, official=False)
            self._maybe_update_recommendation(memory, meta, event, trigger="analysis")
        elif event_type in {"analysis_saved", "analysis_saved_and_printed"}:
            self._section_report(memory, meta, official=True)
            self._maybe_update_recommendation(memory, meta, event, trigger="analysis")
        elif event_type in {"grievance_generated", "grievance_revised"}:
            self._section_grievance(
                memory,
                meta,
                event,
                generated=True,
                saved_and_printed=False,
            )
        elif event_type in {"grievance_saved", "grievance_saved_and_printed"}:
            self._section_grievance(
                memory,
                meta,
                event,
                generated=False,
                saved_and_printed=bool(
                    event_type == "grievance_saved_and_printed"
                    or meta.get("saved_and_printed")
                    or meta.get("printed")
                ),
            )
        elif event_type == "workflow_state_changed":
            to_state = meta.get("to_state")
            if to_state:
                self._section_workflow_set(
                    memory, str(to_state), event.grievance_step
                )
            self._maybe_update_recommendation(
                memory, meta, event, trigger="workflow"
            )
        elif event_type == "outcome_recorded":
            self._section_decision(memory, meta, event)
            self._maybe_update_recommendation(memory, meta, event, trigger="outcome")
        elif event_type == "case_closed":
            self._section_closure(memory, meta)
            self._section_workflow_set(memory, "closed", event.grievance_step)
        elif event_type == "case_settled":
            self._section_settlement(memory, meta)
            self._section_workflow_set(memory, "settled", event.grievance_step)
        elif event_type == "case_reopened":
            self._section_reopen(memory, meta, event)
            self._section_workflow_set(memory, "reopened", event.grievance_step)
        elif event_type == "recommendation_updated":
            self._section_recommendation(memory, meta, event, force=True)

        # Boundedness: never embed full bodies from event metadata.
        self._strip_bodies_from_memory(memory)
        self._sync_section_aliases(memory)
        memory["last_activity_at"] = _iso(event.occurred_at or _now())

        # Ensure unrelated sections were not wiped.
        for key in REQUIRED_SECTIONS:
            if memory.get(key) is None and before_keys.get(key) is not None:
                memory[key] = before_keys[key]

        return self._persist(event.case_uuid, memory, commit=commit)

    def normalize_memory(self, memory: dict[str, Any]) -> dict[str, Any]:
        """Validate required sections and apply compatible defaults for older docs."""
        memory = dict(memory or {})
        schema = memory.get("schema_version") or CASE_MEMORY_SCHEMA
        if schema not in {CASE_MEMORY_SCHEMA, CASE_MEMORY_SCHEMA_NEXT}:
            memory["schema_version"] = CASE_MEMORY_SCHEMA
        else:
            memory["schema_version"] = schema

        # Lift legacy flat keys into modular sections when missing.
        memory.setdefault(
            "identity_and_facts",
            {
                "facts": dict(memory.get("facts") or {}),
                "issue": memory.get("issue"),
                "employee": memory.get("employee"),
                "case_number": memory.get("case_number"),
                "assigned_steward": memory.get("assigned_steward"),
            },
        )
        memory.setdefault(
            "status_and_lifecycle",
            {
                "status": memory.get("status") or "open",
                "last_activity_at": memory.get("last_activity_at"),
            },
        )
        workflow = memory.get("workflow")
        if not isinstance(workflow, dict):
            legacy_wf = memory.get("workflow_state")
            workflow = dict(legacy_wf) if isinstance(legacy_wf, dict) else {}
        workflow.setdefault(
            "explicit_state",
            workflow.get("phase") or "case_open",
        )
        workflow.setdefault("inference_confidence", "confirmed")
        memory["workflow"] = workflow
        memory.setdefault("workflow_state", workflow)

        memory.setdefault(
            "decisions", list(memory.get("important_decisions") or [])
        )
        memory.setdefault(
            "conclusions", list(memory.get("important_conclusions") or [])
        )
        memory.setdefault("union_arguments", list(memory.get("union_arguments") or []))
        memory.setdefault(
            "management_arguments", list(memory.get("management_arguments") or [])
        )
        memory.setdefault(
            "evidence",
            {
                "references": list(memory.get("evidence_references") or []),
                "summaries": list(memory.get("evidence_summaries") or []),
                "uploaded_documents": list(memory.get("uploaded_documents") or []),
            },
        )
        memory.setdefault(
            "reports",
            {"items": list(memory.get("analysis_reports") or [])},
        )
        memory.setdefault(
            "grievances",
            {"history": list(memory.get("grievance_history") or [])},
        )
        memory.setdefault(
            "conversations",
            {
                "summaries": list(memory.get("conversation_summaries") or []),
                "meanings": list(memory.get("conversation_meanings") or []),
            },
        )
        memory.setdefault("open_questions", list(memory.get("open_questions") or []))
        memory.setdefault(
            "resolved_questions", list(memory.get("resolved_questions") or [])
        )
        memory.setdefault(
            "outstanding_issues", list(memory.get("outstanding_issues") or [])
        )
        recs = memory.get("recommendations")
        if not isinstance(recs, dict):
            legacy = memory.get("current_recommendation")
            recs = {
                "current": (
                    {
                        "recommendation": legacy,
                        "status": "current" if legacy else "no_recommendation",
                        "kind": "ai_recommendation",
                    }
                    if legacy
                    else {"status": "no_recommendation", "kind": "ai_recommendation"}
                ),
                "history": [],
            }
        recs.setdefault(
            "current",
            {"status": "no_recommendation", "kind": "ai_recommendation"},
        )
        recs.setdefault("history", [])
        memory["recommendations"] = recs
        memory.setdefault("relationships", list(memory.get("relationships") or []))
        memory.setdefault(
            "official_artifacts",
            memory.get("official_artifacts") or {"latest": {}, "all": []},
        )
        memory.setdefault("settlement", memory.get("settlement") or {})
        memory.setdefault("closure", memory.get("closure") or {})
        memory.setdefault("reopen_history", list(memory.get("reopen_history") or []))

        for section in REQUIRED_SECTIONS:
            memory.setdefault(section, {} if section not in {
                "decisions",
                "conclusions",
                "union_arguments",
                "management_arguments",
                "open_questions",
                "resolved_questions",
                "outstanding_issues",
                "relationships",
                "reopen_history",
            } else [])

        self._sync_section_aliases(memory)
        self._bound_lists(memory)
        return memory

    # ------------------------------------------------------------------
    # Compatibility record_* APIs (delegate to section writers)
    # ------------------------------------------------------------------

    def publish_conversation_event(
        self,
        case_uuid: str,
        *,
        meaning: dict[str, Any],
        message_ids: list[int] | None = None,
        report_version_number: int | None = None,
        commit: bool = True,
    ) -> CaseDomainEventRecord:
        """Persist one conversation-meaning event and return projection status."""
        from app.services.case_domain_event_service import CaseDomainEventService

        return CaseDomainEventService(self.db).publish(
            case_uuid,
            event_type="conversation_meaning_recorded",
            source_type="conversation",
            metadata={
                "meaning": meaning,
                "message_ids": list(message_ids or []),
                "report_version_number": report_version_number,
                "recommendation": meaning.get("conclusion_reached"),
                "rationale": meaning.get("problem_discussed"),
                "unresolved_questions": meaning.get("unresolved_questions") or [],
            },
            idempotency_key=(
                f"conversation:{case_uuid}:{','.join(str(i) for i in (message_ids or []))}"
                if message_ids
                else None
            ),
            append_steward_timeline=False,
            commit=commit,
        )

    def record_conversation(
        self,
        case_uuid: str,
        *,
        meaning: dict[str, Any],
        message_ids: list[int] | None = None,
        report_version_number: int | None = None,
        commit: bool = True,
    ) -> dict[str, Any]:
        self.publish_conversation_event(
            case_uuid,
            meaning=meaning,
            message_ids=message_ids,
            report_version_number=report_version_number,
            commit=commit,
        )
        return self.load(case_uuid)

    def record_report(
        self,
        case_uuid: str,
        *,
        report_version_number: int,
        report_summary: dict | None = None,
        primary_issue: str | None = None,
        recommendation: str | None = None,
        open_questions: list[str] | None = None,
        official: bool = False,
        artifact_uuid: str | None = None,
        commit: bool = True,
        via_event: bool = True,
    ) -> dict[str, Any]:
        if via_event:
            from app.services.case_domain_event_service import CaseDomainEventService

            event_type = (
                "analysis_saved_and_printed" if official else "analysis_generated"
            )
            CaseDomainEventService(self.db).publish(
                case_uuid,
                event_type=event_type,
                source_type="analysis_report",
                source_uuid=artifact_uuid,
                metadata={
                    "report_version_number": report_version_number,
                    "report_summary": report_summary or {},
                    "primary_issue": primary_issue,
                    "recommendation": recommendation,
                    "rationale": (report_summary or {}).get("rationale")
                    or recommendation,
                    "open_questions": open_questions or [],
                    "artifact_uuid": artifact_uuid,
                    "official": official,
                },
                idempotency_key=(
                    f"{event_type}:{case_uuid}:{artifact_uuid or report_version_number}"
                ),
                append_steward_timeline=False,
                commit=commit,
            )
            return self.load(case_uuid)

        memory = self.load(case_uuid)
        self._section_report(
            memory,
            {
                "report_version_number": report_version_number,
                "report_summary": report_summary or {},
                "primary_issue": primary_issue,
                "recommendation": recommendation,
                "open_questions": open_questions or [],
                "artifact_uuid": artifact_uuid,
            },
            official=official,
        )
        self._sync_section_aliases(memory)
        return self._persist(case_uuid, memory, commit=commit)

    def record_grievance(
        self,
        case_uuid: str,
        *,
        grievance_step: str | None,
        version_number: int,
        artifact_uuid: str,
        title: str,
        template_id: str | None = None,
        key_field_values: dict | None = None,
        generated: bool = False,
        saved_and_printed: bool = False,
        commit: bool = True,
        via_event: bool = True,
    ) -> dict[str, Any]:
        if via_event:
            from app.services.case_domain_event_service import CaseDomainEventService

            if saved_and_printed:
                event_type = "grievance_saved_and_printed"
            elif version_number > 1:
                event_type = "grievance_revised"
            else:
                event_type = "grievance_generated"
            CaseDomainEventService(self.db).publish(
                case_uuid,
                event_type=event_type,
                grievance_step=grievance_step,
                source_type="grievance_form",
                source_uuid=artifact_uuid,
                metadata={
                    "version_number": version_number,
                    "artifact_uuid": artifact_uuid,
                    "title": title,
                    "template_id": template_id,
                    "key_field_values": key_field_values or {},
                    "generated": generated,
                    "saved_and_printed": saved_and_printed,
                },
                idempotency_key=f"{event_type}:{case_uuid}:{artifact_uuid}",
                append_steward_timeline=False,
                commit=commit,
            )
            return self.load(case_uuid)

        memory = self.load(case_uuid)
        fake = CaseDomainEventRecord(
            event_id="local",
            case_uuid=case_uuid,
            event_type="grievance_saved_and_printed",
            occurred_at=_now(),
            grievance_step=grievance_step,
            metadata={
                "version_number": version_number,
                "artifact_uuid": artifact_uuid,
                "title": title,
                "template_id": template_id,
                "key_field_values": key_field_values or {},
            },
        )
        self._section_grievance(
            memory,
            fake.metadata,
            fake,
            generated=generated,
            saved_and_printed=saved_and_printed,
        )
        self._sync_section_aliases(memory)
        return self._persist(case_uuid, memory, commit=commit)

    def record_evidence(
        self,
        case_uuid: str,
        *,
        asset_uuid: str,
        filename: str | None,
        management_response: bool = False,
        summary: str | None = None,
        commit: bool = True,
    ) -> dict[str, Any]:
        from app.services.case_domain_event_service import CaseDomainEventService

        CaseDomainEventService(self.db).publish(
            case_uuid,
            event_type=(
                "management_response_uploaded"
                if management_response
                else "evidence_uploaded"
            ),
            source_type="case_asset",
            source_uuid=asset_uuid,
            metadata={
                "asset_uuid": asset_uuid,
                "filename": filename,
                "summary": summary or filename,
                "upload_refs": [asset_uuid],
            },
            idempotency_key=f"evidence:{case_uuid}:{asset_uuid}",
            append_steward_timeline=False,
            commit=commit,
        )
        return self.load(case_uuid)

    def record_outcome(
        self,
        case_uuid: str,
        *,
        step_type: str | None,
        outcome_type: str,
        decision_summary: str | None,
        appeal_to_next_step: bool = False,
        close_case: bool = False,
        commit: bool = True,
    ) -> dict[str, Any]:
        from app.services.case_domain_event_service import CaseDomainEventService

        CaseDomainEventService(self.db).publish(
            case_uuid,
            event_type="outcome_recorded",
            grievance_step=step_type,
            source_type="step_outcome",
            metadata={
                "step_type": step_type,
                "outcome_type": outcome_type,
                "decision_summary": decision_summary,
                "appeal_to_next_step": appeal_to_next_step,
                "close_case": close_case,
                "recommendation": decision_summary,
                "rationale": f"Steward outcome: {outcome_type}",
            },
            idempotency_key=None,
            append_steward_timeline=False,
            commit=commit,
        )
        return self.load(case_uuid)

    def record_close(
        self,
        case_uuid: str,
        *,
        outcome: str,
        outcome_notes: str | None,
        resolution_type: str,
        close_date: datetime | None,
        closed_by: str | None,
        final_grievance_step: str | None,
        supporting_document_refs: list[str] | None = None,
        commit: bool = True,
    ) -> dict[str, Any]:
        from app.services.case_domain_event_service import CaseDomainEventService

        CaseDomainEventService(self.db).publish(
            case_uuid,
            event_type="case_closed",
            actor_id=closed_by,
            grievance_step=final_grievance_step,
            metadata={
                "outcome": outcome,
                "outcome_notes": outcome_notes,
                "resolution_type": resolution_type,
                "close_date": _iso(close_date or _now()),
                "closed_by": closed_by,
                "final_grievance_step": final_grievance_step,
                "supporting_document_refs": list(supporting_document_refs or []),
            },
            idempotency_key=f"case_closed:{case_uuid}:{_iso(close_date or _now())}",
            append_steward_timeline=False,
            commit=commit,
        )
        return self.load(case_uuid)

    def record_settle(
        self,
        case_uuid: str,
        *,
        settlement_notes: str | None,
        settlement_date: datetime | None,
        settlement_document_refs: list[str] | None = None,
        settlement_amount: float | None = None,
        settled_by: str | None = None,
        commit: bool = True,
    ) -> dict[str, Any]:
        from app.services.case_domain_event_service import CaseDomainEventService

        CaseDomainEventService(self.db).publish(
            case_uuid,
            event_type="case_settled",
            actor_id=settled_by,
            metadata={
                "settlement_notes": settlement_notes,
                "settlement_date": _iso(settlement_date or _now()),
                "settlement_document_refs": list(settlement_document_refs or []),
                "settlement_amount": settlement_amount,
                "settled_by": settled_by,
                "settlement_status": "settled",
            },
            idempotency_key=f"case_settled:{case_uuid}:{_iso(settlement_date or _now())}",
            append_steward_timeline=False,
            commit=commit,
        )
        return self.load(case_uuid)

    def record_reopen(
        self,
        case_uuid: str,
        *,
        reason: str | None,
        reopened_by: str | None,
        source: str | None = None,
        commit: bool = True,
    ) -> dict[str, Any]:
        from app.services.case_domain_event_service import CaseDomainEventService

        row = self.ensure(case_uuid, commit=False)
        next_count = int(row.reopen_count or 0) + 1
        CaseDomainEventService(self.db).publish(
            case_uuid,
            event_type="case_reopened",
            actor_id=reopened_by,
            source_type=source,
            metadata={
                "reason_reopened": reason,
                "reopened_by": reopened_by,
                "source": source,
                "reopen_number": next_count,
            },
            idempotency_key=f"case_reopened:{case_uuid}:{next_count}",
            append_steward_timeline=False,
            commit=False,
        )
        # apply_event increments via section; sync row counter
        memory = self.load(case_uuid)
        row.reopen_count = int(memory.get("reopen_count") or next_count)
        if commit:
            self.db.commit()
            self.db.refresh(row)
        else:
            self.db.flush()
        return deepcopy(memory)

    def sync_facts_and_status(
        self,
        case_uuid: str,
        *,
        facts: dict | None = None,
        status: str | None = None,
        current_step: str | None = None,
        commit: bool = True,
    ) -> dict[str, Any]:
        memory = self.load(case_uuid)
        if facts is not None:
            identity = dict(memory.get("identity_and_facts") or {})
            merged = dict(identity.get("facts") or memory.get("facts") or {})
            merged.update(facts)
            identity["facts"] = merged
            memory["identity_and_facts"] = identity
            memory["facts"] = merged
        if status is not None:
            memory["status"] = status
            lifecycle = dict(memory.get("status_and_lifecycle") or {})
            lifecycle["status"] = status
            memory["status_and_lifecycle"] = lifecycle
        if current_step is not None:
            memory["current_grievance_step"] = current_step
        memory["last_activity_at"] = _iso(_now())
        self._sync_section_aliases(memory)
        return self._persist(case_uuid, memory, commit=commit)

    # ------------------------------------------------------------------
    # Section handlers
    # ------------------------------------------------------------------

    def _section_identity(self, memory: dict[str, Any], meta: dict[str, Any]) -> None:
        identity = dict(memory.get("identity_and_facts") or {})
        if meta.get("facts"):
            facts = dict(identity.get("facts") or {})
            facts.update(meta["facts"])
            identity["facts"] = facts
        for key in ("issue", "employee", "case_number", "assigned_steward"):
            if meta.get(key) is not None:
                identity[key] = meta[key]
        memory["identity_and_facts"] = identity

    def _section_status(self, memory: dict[str, Any], *, status: str) -> None:
        memory["status"] = status
        lifecycle = dict(memory.get("status_and_lifecycle") or {})
        lifecycle["status"] = status
        lifecycle["last_activity_at"] = _iso(_now())
        memory["status_and_lifecycle"] = lifecycle

    def _section_workflow_set(
        self,
        memory: dict[str, Any],
        explicit_state: str,
        grievance_step: str | None,
    ) -> None:
        workflow = dict(memory.get("workflow") or {})
        workflow["explicit_state"] = explicit_state
        workflow["phase"] = explicit_state
        workflow["inference_confidence"] = "confirmed"
        memory["workflow"] = workflow
        memory["workflow_state"] = workflow
        if grievance_step:
            memory["current_grievance_step"] = grievance_step

    def _section_conversation(
        self,
        memory: dict[str, Any],
        meta: dict[str, Any],
        event: CaseDomainEventRecord,
    ) -> None:
        meaning = meta.get("meaning") or {}
        entry = {
            "at": _iso(event.occurred_at or _now()),
            "message_ids": list(meta.get("message_ids") or []),
            "meaning": meaning,
            "report_version_number": meta.get("report_version_number"),
            "event_id": event.event_id,
        }
        conversations = dict(memory.get("conversations") or {})
        meanings = list(conversations.get("meanings") or [])
        # Deduplicate by message_ids
        msg_key = tuple(entry["message_ids"])
        if msg_key and any(tuple(m.get("message_ids") or []) == msg_key for m in meanings):
            return
        meanings.append(entry)
        conversations["meanings"] = meanings[-_MAX_MEANINGS:]
        summaries = list(conversations.get("summaries") or [])
        summaries.append(
            {
                "at": entry["at"],
                "problem_discussed": meaning.get("problem_discussed"),
                "conclusion_reached": meaning.get("conclusion_reached"),
                "decision_made": meaning.get("decision_made"),
            }
        )
        conversations["summaries"] = summaries[-_MAX_LIST:]
        memory["conversations"] = conversations
        for question in meaning.get("unresolved_questions") or []:
            self._add_unique(memory, "open_questions", str(question))
        if meaning.get("conclusion_reached"):
            conclusions = list(memory.get("conclusions") or [])
            conclusions.append(
                {
                    "at": entry["at"],
                    "conclusion": meaning.get("conclusion_reached"),
                    "accepted": meaning.get("accepted"),
                    "rejected": meaning.get("rejected"),
                }
            )
            memory["conclusions"] = conclusions[-_MAX_LIST:]
        decision = meaning.get("decision_made") or {}
        if decision:
            decisions = list(memory.get("decisions") or [])
            decisions.append(
                {
                    "at": entry["at"],
                    "source": "conversation",
                    "decision": decision,
                    "problem": meaning.get("problem_discussed"),
                    "kind": "steward_or_conversation_signal",
                }
            )
            memory["decisions"] = decisions[-_MAX_DECISIONS:]
        if meta.get("report_version_number") is not None:
            self._add_relationship(
                memory,
                kind="conversation_to_report",
                message_ids=list(meta.get("message_ids") or []),
                report_version_number=meta.get("report_version_number"),
                event_id=event.event_id,
            )

    def _section_evidence(
        self,
        memory: dict[str, Any],
        meta: dict[str, Any],
        *,
        management: bool,
    ) -> None:
        now = _iso(_now())
        asset_uuid = meta.get("asset_uuid")
        evidence = dict(memory.get("evidence") or {})
        docs = list(evidence.get("uploaded_documents") or [])
        if asset_uuid and any(d.get("asset_uuid") == asset_uuid for d in docs):
            return
        docs.append(
            {
                "asset_uuid": asset_uuid,
                "filename": meta.get("filename"),
                "management_response": management,
                "at": now,
            }
        )
        evidence["uploaded_documents"] = docs[-_MAX_EVIDENCE:]
        refs = list(evidence.get("references") or [])
        refs.append(
            {"asset_uuid": asset_uuid, "filename": meta.get("filename"), "at": now}
        )
        evidence["references"] = refs[-_MAX_EVIDENCE:]
        summaries = list(evidence.get("summaries") or [])
        summaries.append(
            {
                "asset_uuid": asset_uuid,
                "summary": meta.get("summary") or meta.get("filename") or asset_uuid,
                "management_response": management,
                "at": now,
            }
        )
        evidence["summaries"] = summaries[-_MAX_EVIDENCE:]
        memory["evidence"] = evidence
        if management:
            args = list(memory.get("management_arguments") or [])
            args.append(
                {
                    "at": now,
                    "source": "management_response_upload",
                    "asset_uuid": asset_uuid,
                    "summary": meta.get("summary") or meta.get("filename"),
                }
            )
            memory["management_arguments"] = args[-_MAX_LIST:]

    def _section_report(
        self,
        memory: dict[str, Any],
        meta: dict[str, Any],
        *,
        official: bool,
    ) -> None:
        reports = dict(memory.get("reports") or {})
        items = list(reports.get("items") or [])
        artifact_uuid = meta.get("artifact_uuid")
        version = meta.get("report_version_number")
        if artifact_uuid and any(
            i.get("artifact_uuid") == artifact_uuid for i in items
        ):
            return
        entry = {
            "report_version_number": version,
            "report_summary": meta.get("report_summary") or {},
            "primary_issue": meta.get("primary_issue"),
            "recommendation": meta.get("recommendation"),
            "official": official,
            "artifact_uuid": artifact_uuid,
            "record_class": "official_record" if official else "working_draft",
            "at": _iso(_now()),
        }
        # Never store full report body
        if isinstance(entry["report_summary"], dict):
            entry["report_summary"] = {
                k: v
                for k, v in entry["report_summary"].items()
                if k
                not in {
                    "report_data",
                    "full_text",
                    "ranked_authorities",
                    "evidence_items",
                }
            }
        items.append(entry)
        reports["items"] = items[-_MAX_LIST:]
        memory["reports"] = reports
        if meta.get("primary_issue"):
            identity = dict(memory.get("identity_and_facts") or {})
            identity["issue"] = meta["primary_issue"]
            memory["identity_and_facts"] = identity
            memory["issue"] = meta["primary_issue"]
        for question in meta.get("open_questions") or []:
            self._add_unique(memory, "open_questions", str(question))
        if official and artifact_uuid:
            self._upsert_official_artifact(
                memory,
                artifact_type="analysis_report",
                artifact_uuid=artifact_uuid,
                version=int(version or 1),
                title=f"Analysis Report v{version}",
            )
            self._add_relationship(
                memory,
                kind="report_to_official_artifact",
                report_version_number=version,
                artifact_uuid=artifact_uuid,
            )

    def _section_grievance(
        self,
        memory: dict[str, Any],
        meta: dict[str, Any],
        event: CaseDomainEventRecord,
        *,
        generated: bool,
        saved_and_printed: bool,
    ) -> None:
        grievances = dict(memory.get("grievances") or {})
        history = list(grievances.get("history") or [])
        artifact_uuid = meta.get("artifact_uuid")
        if artifact_uuid and any(
            h.get("artifact_uuid") == artifact_uuid for h in history
        ):
            return
        entry = {
            "grievance_step": event.grievance_step or meta.get("grievance_step"),
            "version_number": meta.get("version_number"),
            "artifact_uuid": artifact_uuid,
            "title": meta.get("title"),
            "template_id": meta.get("template_id"),
            "key_field_values": meta.get("key_field_values") or {},
            "generated": generated,
            "saved_and_printed": saved_and_printed,
            "record_class": "official_record" if saved_and_printed else "working_draft",
            "at": _iso(event.occurred_at or _now()),
            "event_id": event.event_id,
        }
        history.append(entry)
        grievances["history"] = history[-_MAX_LIST:]
        memory["grievances"] = grievances
        if entry["grievance_step"]:
            memory["current_grievance_step"] = entry["grievance_step"]
        if artifact_uuid:
            self._upsert_official_artifact(
                memory,
                artifact_type="grievance_form",
                artifact_uuid=artifact_uuid,
                version=int(meta.get("version_number") or 1),
                title=str(meta.get("title") or "Grievance"),
                grievance_step=entry["grievance_step"],
            )
            self._add_relationship(
                memory,
                kind="conversation_to_grievance" if generated else "grievance_official",
                artifact_uuid=artifact_uuid,
                grievance_step=entry["grievance_step"],
                version_number=meta.get("version_number"),
                event_id=event.event_id,
            )

    def _section_decision(
        self,
        memory: dict[str, Any],
        meta: dict[str, Any],
        event: CaseDomainEventRecord,
    ) -> None:
        decisions = list(memory.get("decisions") or [])
        entry = {
            "at": _iso(event.occurred_at or _now()),
            "source": "step_outcome",
            "step_type": meta.get("step_type") or event.grievance_step,
            "outcome_type": meta.get("outcome_type"),
            "decision_summary": meta.get("decision_summary"),
            "appeal_to_next_step": bool(meta.get("appeal_to_next_step")),
            "close_case": bool(meta.get("close_case")),
            "kind": "steward_decision",
            "event_id": event.event_id,
        }
        # Dedup by event_id
        if any(d.get("event_id") == event.event_id for d in decisions):
            return
        decisions.append(entry)
        memory["decisions"] = decisions[-_MAX_DECISIONS:]
        workflow = dict(memory.get("workflow") or {})
        workflow["latest_outcome_type"] = meta.get("outcome_type")
        workflow["latest_decision_summary"] = meta.get("decision_summary")
        workflow["awaiting_appeal"] = bool(meta.get("appeal_to_next_step"))
        memory["workflow"] = workflow
        memory["workflow_state"] = workflow
        if meta.get("step_type"):
            memory["current_grievance_step"] = meta["step_type"]

    def _section_closure(self, memory: dict[str, Any], meta: dict[str, Any]) -> None:
        memory["status"] = "closed"
        memory["closure"] = {
            "outcome": meta.get("outcome"),
            "outcome_notes": meta.get("outcome_notes"),
            "resolution_type": meta.get("resolution_type"),
            "close_date": meta.get("close_date") or _iso(_now()),
            "closed_by": meta.get("closed_by"),
            "final_grievance_step": meta.get("final_grievance_step")
            or memory.get("current_grievance_step"),
            "supporting_document_refs": list(meta.get("supporting_document_refs") or []),
        }
        lifecycle = dict(memory.get("status_and_lifecycle") or {})
        lifecycle["status"] = "closed"
        memory["status_and_lifecycle"] = lifecycle

    def _section_settlement(self, memory: dict[str, Any], meta: dict[str, Any]) -> None:
        memory["status"] = "settled"
        memory["settlement"] = {
            "settlement_notes": meta.get("settlement_notes"),
            "settlement_date": meta.get("settlement_date") or _iso(_now()),
            "settlement_document_refs": list(meta.get("settlement_document_refs") or []),
            "settlement_amount": meta.get("settlement_amount"),
            "settled_by": meta.get("settled_by"),
            "settlement_status": "settled",
        }
        lifecycle = dict(memory.get("status_and_lifecycle") or {})
        lifecycle["status"] = "settled"
        memory["status_and_lifecycle"] = lifecycle

    def _section_reopen(
        self,
        memory: dict[str, Any],
        meta: dict[str, Any],
        event: CaseDomainEventRecord,
    ) -> None:
        history = list(memory.get("reopen_history") or [])
        reopen_number = int(meta.get("reopen_number") or (len(history) + 1))
        if any(h.get("reopen_number") == reopen_number for h in history):
            return
        history.append(
            {
                "reason_reopened": meta.get("reason_reopened"),
                "reopened_by": meta.get("reopened_by"),
                "reopened_date": _iso(event.occurred_at or _now()),
                "source": meta.get("source"),
                "reopen_number": reopen_number,
                "event_id": event.event_id,
            }
        )
        memory["reopen_history"] = history[-_MAX_LIST:]
        memory["reopen_count"] = reopen_number
        memory["status"] = "open"
        lifecycle = dict(memory.get("status_and_lifecycle") or {})
        lifecycle["status"] = "open"
        memory["status_and_lifecycle"] = lifecycle

    def _section_recommendation(
        self,
        memory: dict[str, Any],
        meta: dict[str, Any],
        event: CaseDomainEventRecord,
        *,
        force: bool = False,
    ) -> None:
        recommendation_text = meta.get("recommendation")
        if not recommendation_text and not force:
            return
        recs = dict(memory.get("recommendations") or {})
        current = dict(recs.get("current") or {})
        history = list(recs.get("history") or [])
        if current.get("status") == "current" and current.get("recommendation"):
            superseded = dict(current)
            superseded["status"] = "superseded"
            history.append(superseded)
        updated = AiRecommendation(
            recommendation=recommendation_text,
            rationale=meta.get("rationale"),
            supporting_evidence_ids=list(meta.get("supporting_evidence_ids") or []),
            supporting_artifact_ids=list(meta.get("supporting_artifact_ids") or []),
            confidence=meta.get("confidence"),
            recommended_step=meta.get("recommended_step")
            or memory.get("current_grievance_step"),
            blockers=list(meta.get("blockers") or []),
            unresolved_questions=list(
                meta.get("unresolved_questions") or memory.get("open_questions") or []
            )[:20],
            generated_at=event.occurred_at or _now(),
            updated_at=_now(),
            source_interaction_id=meta.get("source_interaction_id") or event.event_id,
            source_report_version_number=meta.get("report_version_number"),
            status=meta.get("status") or ("current" if recommendation_text else "no_recommendation"),
        ).model_dump(mode="json")
        recs["current"] = updated
        recs["history"] = history[-_MAX_RECOMMENDATION_HISTORY:]
        memory["recommendations"] = recs
        memory["current_recommendation"] = recommendation_text

    def _maybe_update_recommendation(
        self,
        memory: dict[str, Any],
        meta: dict[str, Any],
        event: CaseDomainEventRecord,
        *,
        trigger: str,
    ) -> None:
        if meta.get("recommendation") or meta.get("unresolved_questions"):
            meta = dict(meta)
            meta.setdefault("rationale", f"Updated after {trigger}")
            self._section_recommendation(memory, meta, event)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _require_case(self, case_uuid: str) -> GrievanceCase:
        case = CaseService._get_case_row(self.db, case_uuid)
        if case is None:
            raise CaseNotFoundError(case_uuid)
        return case

    @staticmethod
    def _safe_str(value: Any) -> str | None:
        return value if isinstance(value, str) else None

    def _initial_memory(self, case: GrievanceCase) -> dict[str, Any]:
        now = _iso(_now())
        facts = case.known_facts if isinstance(case.known_facts, dict) else {}
        status = self._safe_str(case.status) or "open"
        case_uuid = self._safe_str(case.case_uuid) or ""
        memory: dict[str, Any] = {
            "schema_version": CASE_MEMORY_SCHEMA,
            "case_uuid": case_uuid,
            "identity_and_facts": {
                "facts": dict(facts),
                "issue": self._safe_str(case.initial_question),
                "employee": None,
                "case_number": self._safe_str(case.local_number),
                "assigned_steward": self._safe_str(case.user_name),
            },
            "status_and_lifecycle": {"status": status, "last_activity_at": now},
            "workflow": {
                "explicit_state": "case_open",
                "phase": "case_open",
                "inference_confidence": "confirmed",
                "transition_history": [],
            },
            "decisions": [],
            "conclusions": [],
            "union_arguments": [],
            "management_arguments": [],
            "evidence": {
                "references": [],
                "summaries": [],
                "uploaded_documents": [],
            },
            "reports": {"items": []},
            "grievances": {"history": []},
            "conversations": {"summaries": [], "meanings": []},
            "open_questions": [],
            "resolved_questions": [],
            "outstanding_issues": [],
            "recommendations": {
                "current": {
                    "status": "no_recommendation",
                    "kind": "ai_recommendation",
                },
                "history": [],
            },
            "relationships": [],
            "official_artifacts": {"latest": {}, "all": []},
            "settlement": {},
            "closure": {},
            "reopen_history": [],
            "reopen_count": 0,
            "current_grievance_step": "step_1_initial",
            "status": status,
            "last_activity_at": now,
        }
        memory = self.normalize_memory(memory)
        return self._refresh_overview(case_uuid or "unknown", memory)

    def _persist(
        self,
        case_uuid: str,
        memory: dict[str, Any],
        *,
        commit: bool,
    ) -> dict[str, Any]:
        row = self.ensure(case_uuid, commit=False)
        memory = self.normalize_memory(memory)
        memory["reopen_count"] = int(row.reopen_count or memory.get("reopen_count") or 0)
        # Keep row reopen_count in sync when memory advanced it
        if int(memory.get("reopen_count") or 0) > int(row.reopen_count or 0):
            row.reopen_count = int(memory["reopen_count"])
        memory = self._refresh_overview(case_uuid, memory)
        row.memory_json = memory
        row.schema_version = CASE_MEMORY_SCHEMA
        wf = memory.get("workflow") or {}
        if isinstance(wf, dict) and wf.get("explicit_state"):
            row.workflow_state = str(wf["explicit_state"])
        row.updated_at = _now()
        if commit:
            self.db.commit()
            self.db.refresh(row)
        else:
            self.db.flush()
        return deepcopy(memory)

    def _refresh_overview(self, case_uuid: str, memory: dict[str, Any]) -> dict[str, Any]:
        overview = self._overview_from_memory(case_uuid, memory)
        memory["overview"] = overview.model_dump(mode="json")
        return memory

    def _overview_from_memory(self, case_uuid: str, memory: dict[str, Any]) -> CaseOverview:
        memory = self.normalize_memory(memory)
        official = memory.get("official_artifacts") or {}
        latest = official.get("latest") or {}
        closure = memory.get("closure") or {}
        settlement = memory.get("settlement") or {}
        identity = memory.get("identity_and_facts") or {}
        recommendation = self._current_recommendation(memory)
        decisions = list(memory.get("decisions") or [])
        steward_decision = None
        for item in reversed(decisions):
            if item.get("kind") == "steward_decision" or item.get("source") == "step_outcome":
                steward_decision = {
                    "kind": "steward_decision",
                    "decision_summary": item.get("decision_summary")
                    or item.get("decision"),
                    "outcome_type": item.get("outcome_type"),
                    "step_type": item.get("step_type"),
                    "recorded_at": item.get("at"),
                    "source": item.get("source"),
                }
                break
        close_date = self._parse_dt(closure.get("close_date"))
        last_activity = self._parse_dt(memory.get("last_activity_at"))
        evidence = memory.get("evidence") or {}
        docs = list(evidence.get("uploaded_documents") or memory.get("uploaded_documents") or [])
        mgmt = sum(1 for item in docs if item.get("management_response"))
        workflow = memory.get("workflow") or {}
        explicit_state = (
            workflow.get("explicit_state") if isinstance(workflow, dict) else None
        )
        reports = (memory.get("reports") or {}).get("items") or memory.get(
            "analysis_reports"
        ) or []
        grievances = (memory.get("grievances") or {}).get("history") or memory.get(
            "grievance_history"
        ) or []
        supporting_refs = list(
            (recommendation or {}).get("supporting_evidence_ids") or []
        )
        def _s(value: Any) -> str | None:
            return value if isinstance(value, str) else None

        def _i(value: Any) -> int | None:
            return value if isinstance(value, int) else None

        return CaseOverview(
            case_uuid=case_uuid if isinstance(case_uuid, str) else str(case_uuid),
            employee=_s(identity.get("employee") or memory.get("employee")),
            case_number=_s(identity.get("case_number") or memory.get("case_number")),
            issue=_s(identity.get("issue") or memory.get("issue")),
            current_status=_s(memory.get("status")) or "open",
            current_step=_s(memory.get("current_grievance_step")),
            explicit_workflow_state=_s(explicit_state),
            current_recommendation=_s(
                (recommendation or {}).get("recommendation")
                or memory.get("current_recommendation")
            ),
            recommendation_rationale=_s((recommendation or {}).get("rationale")),
            recommendation_status=_s((recommendation or {}).get("status")),
            ai_recommendation=recommendation if isinstance(recommendation, dict) else None,
            steward_decision=steward_decision if isinstance(steward_decision, dict) else None,
            supporting_evidence_count=len(supporting_refs) or len(
                (evidence.get("summaries") or [])[:5]
            ),
            supporting_evidence_refs=[r for r in supporting_refs[:10] if isinstance(r, str)],
            open_questions=[
                q for q in list(memory.get("open_questions") or [])[:20] if isinstance(q, str)
            ],
            outstanding_issues=[
                q
                for q in list(memory.get("outstanding_issues") or [])[:20]
                if isinstance(q, str)
            ],
            evidence_count=len(docs),
            analysis_report_count=len(reports),
            official_grievance_count=len(
                [g for g in grievances if g.get("saved_and_printed")]
            ),
            management_response_count=mgmt,
            management_response_status=(
                "received" if mgmt else "none_recorded"
            ),
            last_activity_at=last_activity,
            assigned_steward=_s(
                identity.get("assigned_steward") or memory.get("assigned_steward")
            ),
            settlement_status=_s(settlement.get("settlement_status")),
            outcome_status=_s(
                (workflow.get("latest_outcome_type") if isinstance(workflow, dict) else None)
                or closure.get("resolution_type")
            ),
            close_date=close_date,
            reopen_count=(
                int(memory.get("reopen_count") or 0)
                if isinstance(memory.get("reopen_count"), (int, float))
                or memory.get("reopen_count") is None
                else 0
            ),
            latest_official_report_version=_i(
                (latest.get("analysis_report") or {}).get("version")
            ),
            latest_official_grievance_version=_i(
                (latest.get("grievance_form") or {}).get("version")
            ),
            latest_official_report_title=_s(
                (latest.get("analysis_report") or {}).get("title")
            ),
            latest_official_grievance_title=_s(
                (latest.get("grievance_form") or {}).get("title")
            ),
        )

    @staticmethod
    def _current_recommendation(memory: dict[str, Any]) -> dict[str, Any] | None:
        recs = memory.get("recommendations") or {}
        current = recs.get("current") if isinstance(recs, dict) else None
        if isinstance(current, dict) and current.get("status") != "no_recommendation":
            return current
        legacy = memory.get("current_recommendation")
        if legacy:
            return {
                "recommendation": legacy,
                "status": "current",
                "kind": "ai_recommendation",
            }
        return current if isinstance(current, dict) else None

    def _sync_section_aliases(self, memory: dict[str, Any]) -> None:
        """Keep legacy flat keys in sync for existing consumers/tests."""
        identity = memory.get("identity_and_facts") or {}
        memory["facts"] = dict(identity.get("facts") or memory.get("facts") or {})
        memory["issue"] = identity.get("issue") or memory.get("issue")
        memory["employee"] = identity.get("employee")
        memory["case_number"] = identity.get("case_number")
        memory["assigned_steward"] = identity.get("assigned_steward")
        lifecycle = memory.get("status_and_lifecycle") or {}
        memory["status"] = lifecycle.get("status") or memory.get("status") or "open"
        memory["important_decisions"] = list(memory.get("decisions") or [])
        memory["important_conclusions"] = list(memory.get("conclusions") or [])
        evidence = memory.get("evidence") or {}
        memory["evidence_references"] = list(evidence.get("references") or [])
        memory["evidence_summaries"] = list(evidence.get("summaries") or [])
        memory["uploaded_documents"] = list(evidence.get("uploaded_documents") or [])
        memory["analysis_reports"] = list(
            (memory.get("reports") or {}).get("items") or []
        )
        memory["grievance_history"] = list(
            (memory.get("grievances") or {}).get("history") or []
        )
        conversations = memory.get("conversations") or {}
        memory["conversation_meanings"] = list(conversations.get("meanings") or [])
        memory["conversation_summaries"] = list(conversations.get("summaries") or [])
        memory["workflow_state"] = memory.get("workflow") or memory.get("workflow_state")
        rec = self._current_recommendation(memory)
        if rec:
            memory["current_recommendation"] = rec.get("recommendation")

    def _bound_lists(self, memory: dict[str, Any]) -> None:
        memory["open_questions"] = list(memory.get("open_questions") or [])[
            -_MAX_OPEN_QUESTIONS:
        ]
        memory["resolved_questions"] = list(memory.get("resolved_questions") or [])[
            -_MAX_LIST:
        ]
        memory["outstanding_issues"] = list(memory.get("outstanding_issues") or [])[
            -_MAX_LIST:
        ]
        memory["decisions"] = list(memory.get("decisions") or [])[-_MAX_DECISIONS:]
        memory["relationships"] = list(memory.get("relationships") or [])[
            -_MAX_RELATIONSHIPS:
        ]
        official = dict(memory.get("official_artifacts") or {})
        official["all"] = list(official.get("all") or [])[-_MAX_ARTIFACT_INDEX:]
        memory["official_artifacts"] = official

    @staticmethod
    def _strip_bodies_from_memory(memory: dict[str, Any]) -> None:
        for key in ("full_transcript", "report_body", "pdf_bytes", "content_json"):
            memory.pop(key, None)

    @staticmethod
    def _add_unique(memory: dict[str, Any], key: str, value: str) -> None:
        items = list(memory.get(key) or [])
        if value and value not in items:
            items.append(value)
        memory[key] = items[-_MAX_LIST:]

    @staticmethod
    def _add_relationship(memory: dict[str, Any], *, kind: str, **payload: Any) -> None:
        rels = list(memory.get("relationships") or [])
        rels.append({"kind": kind, "at": _iso(_now()), **payload})
        memory["relationships"] = rels[-_MAX_RELATIONSHIPS:]

    @staticmethod
    def _upsert_official_artifact(
        memory: dict[str, Any],
        *,
        artifact_type: str,
        artifact_uuid: str,
        version: int,
        title: str,
        grievance_step: str | None = None,
    ) -> None:
        official = dict(memory.get("official_artifacts") or {})
        all_items = list(official.get("all") or [])
        if any(i.get("artifact_uuid") == artifact_uuid for i in all_items):
            official["latest"] = dict(official.get("latest") or {})
            official["latest"][artifact_type] = {
                "artifact_uuid": artifact_uuid,
                "version": version,
                "title": title,
                "grievance_step": grievance_step,
            }
            memory["official_artifacts"] = official
            return
        all_items.append(
            {
                "artifact_type": artifact_type,
                "artifact_uuid": artifact_uuid,
                "version": version,
                "title": title,
                "grievance_step": grievance_step,
                "at": _iso(_now()),
            }
        )
        official["all"] = all_items[-_MAX_ARTIFACT_INDEX:]
        latest = dict(official.get("latest") or {})
        latest[artifact_type] = {
            "artifact_uuid": artifact_uuid,
            "version": version,
            "title": title,
            "grievance_step": grievance_step,
        }
        official["latest"] = latest
        memory["official_artifacts"] = official

    @staticmethod
    def _parse_dt(value: Any) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value))
        except ValueError:
            return None
