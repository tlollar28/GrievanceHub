"""Central explicit grievance workflow transition service."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.schemas.case_workflow_schema import WorkflowStateView
from app.services.case_service import CaseNotFoundError, CaseService

DEFAULT_WORKFLOW_STATE = "case_open"

# Permitted transitions for the explicit FSM. Closed/settled require reopen.
_TRANSITIONS: dict[str, frozenset[str]] = {
    "case_open": frozenset({"step_1_analysis", "closed", "settled"}),
    "step_1_analysis": frozenset(
        {"step_1_draft", "step_1_decision_required", "closed", "settled"}
    ),
    "step_1_draft": frozenset({"step_1_awaiting_steward_review", "step_1_analysis"}),
    "step_1_awaiting_steward_review": frozenset(
        {"step_1_official", "step_1_draft", "step_1_analysis"}
    ),
    "step_1_official": frozenset(
        {
            "step_1_awaiting_management_response",
            "step_1_decision_required",
            "step_1_resolved",
        }
    ),
    "step_1_awaiting_management_response": frozenset(
        {"step_1_response_received", "step_1_decision_required"}
    ),
    "step_1_response_received": frozenset({"step_1_decision_required"}),
    "step_1_decision_required": frozenset(
        {"step_1_resolved", "step_1_appealed", "settled", "closed"}
    ),
    "step_1_resolved": frozenset({"closed", "settled", "reopened"}),
    "step_1_appealed": frozenset({"step_2_analysis"}),
    "step_2_analysis": frozenset(
        {"step_2_draft", "step_2_decision_required", "closed", "settled"}
    ),
    "step_2_draft": frozenset({"step_2_awaiting_steward_review", "step_2_analysis"}),
    "step_2_awaiting_steward_review": frozenset(
        {"step_2_official", "step_2_draft", "step_2_analysis"}
    ),
    "step_2_official": frozenset(
        {
            "step_2_awaiting_management_response",
            "step_2_decision_required",
            "step_2_resolved",
        }
    ),
    "step_2_awaiting_management_response": frozenset(
        {"step_2_response_received", "step_2_decision_required"}
    ),
    "step_2_response_received": frozenset({"step_2_decision_required"}),
    "step_2_decision_required": frozenset(
        {"step_2_resolved", "step_2_appealed", "settled", "closed"}
    ),
    "step_2_resolved": frozenset({"closed", "settled", "reopened"}),
    "step_2_appealed": frozenset({"step_3_analysis"}),
    "step_3_analysis": frozenset(
        {"step_3_draft", "step_3_decision_required", "closed", "settled"}
    ),
    "step_3_draft": frozenset({"step_3_awaiting_steward_review", "step_3_analysis"}),
    "step_3_awaiting_steward_review": frozenset(
        {"step_3_official", "step_3_draft", "step_3_analysis"}
    ),
    "step_3_official": frozenset(
        {
            "step_3_awaiting_management_response",
            "step_3_decision_required",
            "step_3_resolved",
        }
    ),
    "step_3_awaiting_management_response": frozenset(
        {"step_3_response_received", "step_3_decision_required"}
    ),
    "step_3_response_received": frozenset({"step_3_decision_required"}),
    "step_3_decision_required": frozenset(
        {"step_3_resolved", "settled", "closed"}
    ),
    "step_3_resolved": frozenset({"closed", "settled", "reopened"}),
    "settled": frozenset({"reopened"}),
    "closed": frozenset({"reopened"}),
    "reopened": frozenset(
        {
            "step_1_analysis",
            "step_2_analysis",
            "step_3_analysis",
            "case_open",
            "closed",
            "settled",
        }
    ),
}

_STEP_PREFIX = {
    "step_1_initial": "step_1",
    "step_2_appeal": "step_2",
    "step_3_appeal": "step_3",
}


class CaseWorkflowError(Exception):
    """Invalid or unauthorized workflow transition."""


class CaseWorkflowService:
    """Owns explicit workflow state transitions (not artifact inference alone)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_state(self, case_uuid: str, *, commit: bool = True) -> WorkflowStateView:
        from app.services.case_memory_service import CaseMemoryService

        memory = CaseMemoryService(self.db).load(case_uuid, commit=commit)
        explicit, inferred, confidence = self._resolve_explicit(memory)
        step = memory.get("current_grievance_step")
        status = memory.get("status") or "open"
        if not isinstance(status, str):
            status = "open"
        step_val = step if isinstance(step, str) else None
        return WorkflowStateView(
            case_uuid=case_uuid,
            explicit_state=explicit,
            current_grievance_step=step_val,
            case_status=status,
            inferred=inferred,
            inference_confidence=confidence,  # type: ignore[arg-type]
            permitted_next_states=sorted(_TRANSITIONS.get(explicit, frozenset())),
            updated_at=self._parse_dt(memory.get("last_activity_at")),
        )

    def transition(
        self,
        case_uuid: str,
        to_state: str,
        *,
        reason: str | None = None,
        actor_id: str | None = None,
        grievance_step: str | None = None,
        allow_authorized_override: bool = False,
        source_type: str | None = None,
        source_uuid: str | None = None,
        metadata: dict[str, Any] | None = None,
        commit: bool = True,
        publish_event: bool = True,
    ) -> WorkflowStateView:
        from app.services.case_memory_service import CaseMemoryService

        case = CaseService._get_case_row(self.db, case_uuid)
        if case is None:
            raise CaseNotFoundError(case_uuid)

        memory_service = CaseMemoryService(self.db)
        memory = memory_service.load(case_uuid, commit=False)
        current, _, _ = self._resolve_explicit(memory)
        if current == to_state:
            return self.get_state(case_uuid, commit=commit)

        allowed = _TRANSITIONS.get(current, frozenset())
        if to_state not in allowed and not allow_authorized_override:
            raise CaseWorkflowError(
                f"Invalid workflow transition: {current} → {to_state}"
            )

        if current in {"closed", "settled"} and to_state != "reopened":
            if not allow_authorized_override:
                raise CaseWorkflowError(
                    "Closed or settled cases must reopen before new work."
                )

        if self._is_step_skip(current, to_state) and not allow_authorized_override:
            raise CaseWorkflowError(
                "Step skipping is not permitted without authorized override."
            )

        if to_state.endswith("_official") and current in {"closed", "settled"}:
            raise CaseWorkflowError(
                "Cannot produce official artifacts while settled or closed."
            )

        now = datetime.utcnow()
        workflow = dict(memory.get("workflow") or memory.get("workflow_state") or {})
        if not isinstance(workflow, dict):
            workflow = {}
        history = list(workflow.get("transition_history") or [])
        history.append(
            {
                "from": current,
                "to": to_state,
                "at": now.isoformat(),
                "reason": reason,
                "actor_id": actor_id,
                "source_type": source_type,
                "source_uuid": source_uuid,
            }
        )
        workflow["explicit_state"] = to_state
        workflow["phase"] = to_state
        workflow["transition_history"] = history[-40:]
        workflow["inference_confidence"] = "confirmed"
        memory["workflow"] = workflow
        memory["workflow_state"] = workflow
        if grievance_step:
            memory["current_grievance_step"] = grievance_step
        else:
            inferred_step = self._step_from_state(to_state)
            if inferred_step:
                memory["current_grievance_step"] = inferred_step
        if to_state == "closed":
            memory["status"] = "closed"
        elif to_state == "settled":
            memory["status"] = "settled"
        elif to_state == "reopened":
            memory["status"] = "open"
        memory["last_activity_at"] = now.isoformat()
        memory_service._persist(case_uuid, memory, commit=False)
        row = memory_service.ensure(case_uuid, commit=False)
        row.workflow_state = to_state

        if publish_event:
            from app.services.case_domain_event_service import CaseDomainEventService

            CaseDomainEventService(self.db).publish(
                case_uuid,
                event_type="workflow_state_changed",
                actor_id=actor_id,
                grievance_step=memory.get("current_grievance_step"),
                source_type=source_type,
                source_uuid=source_uuid,
                metadata={
                    "from_state": current,
                    "to_state": to_state,
                    "reason": reason,
                    **(metadata or {}),
                },
                idempotency_key=f"workflow:{case_uuid}:{current}:{to_state}:{now.isoformat()}",
                append_steward_timeline=False,
                apply_to_memory=False,
                commit=False,
            )

        if commit:
            self.db.commit()
        else:
            self.db.flush()
        return self.get_state(case_uuid, commit=False)

    def suggest_state_for_event(
        self,
        current: str,
        event_type: str,
        *,
        grievance_step: str | None = None,
    ) -> str | None:
        """Map meaningful domain events to target workflow states."""
        prefix = self._prefix_for_step(grievance_step) or self._prefix_from_state(
            current
        )
        if event_type == "case_created":
            return "case_open"
        if event_type == "case_reopened":
            return "reopened"
        if event_type == "case_closed":
            return "closed"
        if event_type == "case_settled":
            return "settled"
        if event_type == "analysis_generated":
            return f"{prefix}_analysis" if prefix else "step_1_analysis"
        if event_type == "grievance_generated":
            return f"{prefix}_draft" if prefix else "step_1_draft"
        if event_type in {
            "analysis_saved",
            "analysis_saved_and_printed",
            "grievance_saved",
            "grievance_saved_and_printed",
        }:
            return f"{prefix}_official" if prefix else "step_1_official"
        if event_type == "management_response_uploaded":
            return (
                f"{prefix}_response_received"
                if prefix
                else "step_1_response_received"
            )
        if event_type == "outcome_recorded":
            return f"{prefix}_decision_required" if prefix else "step_1_decision_required"
        return None

    def ensure_default(self, case_uuid: str, *, commit: bool = True) -> WorkflowStateView:
        from app.services.case_memory_service import CaseMemoryService

        memory = CaseMemoryService(self.db).load(case_uuid)
        explicit, inferred, _ = self._resolve_explicit(memory)
        if inferred or not explicit:
            memory.setdefault("workflow", {})
            if not isinstance(memory["workflow"], dict):
                memory["workflow"] = {}
            memory["workflow"]["explicit_state"] = explicit or DEFAULT_WORKFLOW_STATE
            memory["workflow"]["inference_confidence"] = (
                "inferred" if inferred else "confirmed"
            )
            memory["workflow_state"] = memory["workflow"]
            CaseMemoryService(self.db)._persist(case_uuid, memory, commit=commit)
            row = CaseMemoryService(self.db).get_row(case_uuid)
            row.workflow_state = memory["workflow"]["explicit_state"]
            if commit:
                self.db.commit()
            else:
                self.db.flush()
        return self.get_state(case_uuid)

    @staticmethod
    def _resolve_explicit(
        memory: dict[str, Any],
    ) -> tuple[str, bool, str]:
        workflow = memory.get("workflow") or memory.get("workflow_state") or {}
        if isinstance(workflow, dict) and workflow.get("explicit_state"):
            return str(workflow["explicit_state"]), False, "confirmed"
        status = str(memory.get("status") or "open")
        if status == "closed":
            return "closed", True, "inferred"
        if status == "settled":
            return "settled", True, "inferred"
        step = str(memory.get("current_grievance_step") or "step_1_initial")
        if "step_3" in step:
            return "step_3_analysis", True, "inferred"
        if "step_2" in step:
            return "step_2_analysis", True, "inferred"
        return "case_open", True, "inferred"

    @staticmethod
    def _is_step_skip(current: str, to_state: str) -> bool:
        order = {"step_1": 1, "step_2": 2, "step_3": 3}
        cur_n = next((n for p, n in order.items() if current.startswith(p)), 0)
        to_n = next((n for p, n in order.items() if to_state.startswith(p)), 0)
        if cur_n == 0 or to_n == 0:
            return False
        return to_n > cur_n + 1 or (
            current.startswith("step_1")
            and to_state.startswith("step_2")
            and current not in {"step_1_appealed", "reopened"}
            and not to_state.endswith("_analysis")
            and current != "step_1_appealed"
        )

    @staticmethod
    def _step_from_state(state: str) -> str | None:
        if state.startswith("step_1"):
            return "step_1_initial"
        if state.startswith("step_2"):
            return "step_2_appeal"
        if state.startswith("step_3"):
            return "step_3_appeal"
        return None

    @staticmethod
    def _prefix_for_step(step: str | None) -> str | None:
        if not step:
            return None
        return _STEP_PREFIX.get(step) or (
            "step_1"
            if "step_1" in step
            else "step_2"
            if "step_2" in step
            else "step_3"
            if "step_3" in step
            else None
        )

    @staticmethod
    def _prefix_from_state(state: str) -> str | None:
        for prefix in ("step_1", "step_2", "step_3"):
            if state.startswith(prefix):
                return prefix
        return "step_1"

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

    def snapshot_for_memory(self, case_uuid: str) -> dict[str, Any]:
        view = self.get_state(case_uuid)
        return deepcopy(view.model_dump(mode="json"))
