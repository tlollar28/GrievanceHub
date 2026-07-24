"""Grievance case step progression service (Phase 1.4C foundation).

In-memory same-case lifecycle across Step 1 → Step 2 → Step 3 with timestamped
timeline history, decision/outcome capture, close/reopen behavior, and form draft
history linkage. Integrates conceptually with Phase 1.4B draft builder without
duplicating export or persistence logic.

No OpenAI, no PDF/DOCX export, no database persistence in this phase.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.schemas.case_step_progression_schema import (
    CaseFormDraftHistoryInput,
    CaseFormDraftHistoryRecord,
    CaseStepOutcomeInput,
    CaseStepOutcomeRecord,
    CaseStepProgressionState,
    CaseStepStage,
    CaseTimelineEvent,
    CaseTimelineEventReferences,
    StepTemplateAvailabilityInfo,
    StepType,
    TimelineEventType,
)
from app.schemas.grievance_form_draft_schema import (
    GrievanceFormDraftCaseContext,
    GrievanceFormDraftFollowUpContext,
    GrievanceFormDraftInput,
)
from app.services.grievance_form_draft_builder import (
    build_grievance_form_draft,
)
from app.services.grievance_template_registry import (
    OFFICIAL_GRIEVANCE_WORKSHEET_STEP_1,
    OFFICIAL_STANDARD_GRIEVANCE_FORM_STEP_2,
    get_grievance_template_by_id,
    list_registered_grievance_templates,
)

_STEP_ORDER: dict[StepType, int] = {
    "step_1_initial": 1,
    "step_2_appeal": 2,
    "step_3_appeal": 3,
}

_NEXT_STEP: dict[StepType, StepType | None] = {
    "step_1_initial": "step_2_appeal",
    "step_2_appeal": "step_3_appeal",
    "step_3_appeal": None,
}

_APPEAL_OUTCOME_TYPES = frozenset({"denied", "appealed", "partially_granted"})
_RESOLVED_OUTCOME_TYPES = frozenset(
    {"resolved", "granted", "settled", "closed_no_appeal", "withdrawn"}
)


class CaseStepProgressionNotFoundError(Exception):
    """Raised when no progression state exists for a case uuid."""


class CaseStepNotFoundError(Exception):
    """Raised when a requested step is not present on the case."""


class CaseStepProgressionError(Exception):
    """Raised for invalid lifecycle transitions."""


class CaseStepProgressionService:
    """In-memory case step progression manager (Phase 1.4C foundation)."""

    def __init__(self) -> None:
        self._states: dict[str, CaseStepProgressionState] = {}

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _step_number(step_type: StepType) -> int:
        return _STEP_ORDER[step_type]

    @staticmethod
    def get_step_template_availability(step_type: StepType) -> StepTemplateAvailabilityInfo:
        """Return whether an official template is currently buildable for a step."""
        if step_type == "step_1_initial":
            template = OFFICIAL_GRIEVANCE_WORKSHEET_STEP_1
            return StepTemplateAvailabilityInfo(
                step_type=step_type,
                template_available=True,
                template_id=template.template_id,
                availability_status="available",
                notes=[
                    "The official Step 1 grievance worksheet is registered.",
                ],
            )

        if step_type == "step_3_appeal":
            return StepTemplateAvailabilityInfo(
                step_type=step_type,
                template_available=False,
                template_id=None,
                availability_status="deferred_separate_form_required",
                notes=[
                    "Step 3 appeal/out-of-building template is deferred — separate form required later.",
                ],
            )

        template = OFFICIAL_STANDARD_GRIEVANCE_FORM_STEP_2
        return StepTemplateAvailabilityInfo(
            step_type=step_type,
            template_available=True,
            template_id=template.template_id,
            availability_status="available",
            notes=[
                "The official standard Step 2 grievance form is registered.",
            ],
        )

    @staticmethod
    def list_buildable_template_ids_for_step(step_type: StepType) -> list[str]:
        """Return registered template ids buildable for a step (may be empty)."""
        availability = CaseStepProgressionService.get_step_template_availability(step_type)
        if not availability.template_available or availability.template_id is None:
            return []
        return [availability.template_id]

    def _append_timeline_event(
        self,
        state: CaseStepProgressionState,
        *,
        event_type: TimelineEventType,
        title: str,
        step_type: StepType | None = None,
        details: str | None = None,
        event_timestamp: datetime | None = None,
        references: CaseTimelineEventReferences | None = None,
    ) -> CaseTimelineEvent:
        event = CaseTimelineEvent(
            case_uuid=state.case_uuid,
            step_type=step_type,
            event_type=event_type,
            event_timestamp=event_timestamp or self._now(),
            title=title,
            details=details,
            references=references or CaseTimelineEventReferences(),
        )
        state.timeline.append(event)
        state.updated_at = self._now()
        return event

    def _get_stage(
        self,
        state: CaseStepProgressionState,
        step_type: StepType,
    ) -> CaseStepStage:
        for stage in state.steps:
            if stage.step_type == step_type:
                return stage
        raise CaseStepNotFoundError(step_type)

    def create_case_progression(
        self,
        case_uuid: str,
        *,
        event_timestamp: datetime | None = None,
    ) -> CaseStepProgressionState:
        """Initialize same-case progression starting at Step 1."""
        if case_uuid in self._states:
            raise CaseStepProgressionError(
                f"Case progression already exists for case_uuid={case_uuid}"
            )

        now = event_timestamp or self._now()
        step_1_availability = self.get_step_template_availability("step_1_initial")
        step_1 = CaseStepStage(
            step_type="step_1_initial",
            step_number=1,
            status="open",
            template_id=step_1_availability.template_id,
            template_availability=step_1_availability.availability_status,
            opened_at=now,
        )
        state = CaseStepProgressionState(
            case_uuid=case_uuid,
            workspace_status="open",
            current_step_type="step_1_initial",
            steps=[step_1],
            created_at=now,
            updated_at=now,
        )
        self._append_timeline_event(
            state,
            event_type="case_created",
            title="Case created",
            step_type="step_1_initial",
            event_timestamp=now,
        )
        self._append_timeline_event(
            state,
            event_type="case_opened",
            title="Step 1 opened",
            step_type="step_1_initial",
            event_timestamp=now,
        )
        self._states[case_uuid] = state
        return state

    def get_progression(self, case_uuid: str) -> CaseStepProgressionState:
        state = self._states.get(case_uuid)
        if state is None:
            raise CaseStepProgressionNotFoundError(case_uuid)
        return state

    def update_step_status(
        self,
        case_uuid: str,
        step_type: StepType,
        status: str,
        *,
        event_type: TimelineEventType | None = None,
        title: str | None = None,
        details: str | None = None,
        report_version_id: int | None = None,
        report_version_number: int | None = None,
        follow_up_message_ids: list[int] | None = None,
        event_timestamp: datetime | None = None,
    ) -> CaseStepStage:
        state = self.get_progression(case_uuid)
        stage = self._get_stage(state, step_type)
        stage.status = status  # type: ignore[assignment]

        if report_version_id is not None:
            stage.report_version_id = report_version_id
        if report_version_number is not None:
            stage.report_version_number = report_version_number
        if follow_up_message_ids:
            stage.follow_up_message_ids = sorted(
                set(stage.follow_up_message_ids) | set(follow_up_message_ids)
            )

        if event_type and title:
            refs = CaseTimelineEventReferences(
                report_version_id=report_version_id,
                report_version_number=report_version_number,
                follow_up_message_ids=follow_up_message_ids or [],
            )
            self._append_timeline_event(
                state,
                event_type=event_type,
                title=title,
                step_type=step_type,
                details=details,
                event_timestamp=event_timestamp,
                references=refs,
            )
        return stage

    def add_step_outcome(
        self,
        case_uuid: str,
        step_type: StepType,
        outcome_input: CaseStepOutcomeInput,
        *,
        event_timestamp: datetime | None = None,
    ) -> tuple[CaseStepOutcomeRecord, CaseStepStage]:
        """Record a management decision/outcome for the current step."""
        state = self.get_progression(case_uuid)
        stage = self._get_stage(state, step_type)
        now = event_timestamp or self._now()

        outcome = CaseStepOutcomeRecord(
            step_type=step_type,
            outcome_type=outcome_input.outcome_type,
            decision_summary=outcome_input.decision_summary,
            decision_date=outcome_input.decision_date,
            decision_maker_name=outcome_input.decision_maker_name,
            decision_maker_title=outcome_input.decision_maker_title,
            decision_document_refs=list(outcome_input.decision_document_refs),
            steward_notes=outcome_input.steward_notes,
            step_closed=outcome_input.close_step,
            case_closed=outcome_input.close_case,
            appeal_requested=outcome_input.appeal_to_next_step,
            next_step_target=_NEXT_STEP[step_type]
            if outcome_input.appeal_to_next_step
            else None,
            recorded_at=now,
        )
        stage.outcomes.append(outcome)
        stage.status = "decision_added"

        self._append_timeline_event(
            state,
            event_type="step_decision_added",
            title=f"{step_type.replace('_', ' ').title()} decision recorded",
            step_type=step_type,
            details=outcome_input.decision_summary,
            event_timestamp=now,
            references=CaseTimelineEventReferences(outcome_id=outcome.outcome_id),
        )

        if outcome_input.close_step:
            self.close_step(
                case_uuid,
                step_type,
                reason=outcome_input.outcome_type,
                event_timestamp=now,
            )
            stage = self._get_stage(state, step_type)

        if outcome_input.close_case:
            self.close_case(
                case_uuid,
                reason=outcome_input.outcome_type,
                event_timestamp=now,
            )

        if outcome_input.appeal_to_next_step:
            self.appeal_to_next_step(
                case_uuid,
                from_step=step_type,
                prior_outcome_id=outcome.outcome_id,
                event_timestamp=now,
            )
            stage = self._get_stage(state, step_type)

        return outcome, stage

    def close_step(
        self,
        case_uuid: str,
        step_type: StepType,
        *,
        reason: str | None = None,
        event_timestamp: datetime | None = None,
    ) -> CaseStepStage:
        state = self.get_progression(case_uuid)
        stage = self._get_stage(state, step_type)
        if stage.is_closed and not stage.was_reopened:
            return stage

        now = event_timestamp or self._now()
        stage.is_closed = True
        stage.closed_at = now
        if reason in {"withdrawn"}:
            stage.status = "closed_withdrawn"
        elif reason in _RESOLVED_OUTCOME_TYPES:
            stage.status = "closed_resolved"
        else:
            stage.status = "closed_resolved"

        self._append_timeline_event(
            state,
            event_type="step_closed",
            title=f"{step_type.replace('_', ' ').title()} closed",
            step_type=step_type,
            details=reason,
            event_timestamp=now,
        )
        return stage

    def close_case(
        self,
        case_uuid: str,
        *,
        reason: str | None = None,
        event_timestamp: datetime | None = None,
    ) -> CaseStepProgressionState:
        state = self.get_progression(case_uuid)
        now = event_timestamp or self._now()
        state.workspace_status = "closed"
        state.closed_at = now
        self._append_timeline_event(
            state,
            event_type="case_closed",
            title="Case closed",
            step_type=state.current_step_type,
            details=reason,
            event_timestamp=now,
        )
        return state

    def reopen_step(
        self,
        case_uuid: str,
        step_type: StepType,
        *,
        event_timestamp: datetime | None = None,
    ) -> CaseStepStage:
        state = self.get_progression(case_uuid)
        stage = self._get_stage(state, step_type)
        if not stage.is_closed:
            raise CaseStepProgressionError(
                f"Step {step_type} is not closed and cannot be reopened."
            )

        now = event_timestamp or self._now()
        stage.is_closed = False
        stage.was_reopened = True
        stage.reopened_at = now
        stage.status = "reopened"

        self._append_timeline_event(
            state,
            event_type="step_reopened",
            title=f"{step_type.replace('_', ' ').title()} reopened",
            step_type=step_type,
            event_timestamp=now,
        )
        return stage

    def reopen_case(
        self,
        case_uuid: str,
        *,
        event_timestamp: datetime | None = None,
    ) -> CaseStepProgressionState:
        """Reopen a closed case without deleting prior close/outcome history."""
        state = self.get_progression(case_uuid)
        if state.workspace_status != "closed":
            raise CaseStepProgressionError("Case is not closed and cannot be reopened.")

        now = event_timestamp or self._now()
        state.workspace_status = "open"
        state.reopened_at = now
        self._append_timeline_event(
            state,
            event_type="case_reopened",
            title="Case reopened",
            step_type=state.current_step_type,
            event_timestamp=now,
        )
        return state

    def appeal_to_next_step(
        self,
        case_uuid: str,
        from_step: StepType,
        *,
        prior_outcome_id: str | None = None,
        event_timestamp: datetime | None = None,
    ) -> CaseStepStage:
        """Continue the same case to the next grievance step after denial/appeal."""
        state = self.get_progression(case_uuid)
        prior_stage = self._get_stage(state, from_step)
        next_step = _NEXT_STEP[from_step]
        if next_step is None:
            raise CaseStepProgressionError(
                f"No next step available after {from_step}."
            )

        if any(stage.step_type == next_step for stage in state.steps):
            raise CaseStepProgressionError(
                f"Step {next_step} already exists on case {case_uuid}."
            )

        now = event_timestamp or self._now()
        prior_stage.status = "appealed_to_next_step"
        if not prior_stage.is_closed:
            self.close_step(
                case_uuid,
                from_step,
                reason="appealed",
                event_timestamp=now,
            )

        availability = self.get_step_template_availability(next_step)
        template_id = availability.template_id
        new_stage = CaseStepStage(
            step_type=next_step,
            step_number=self._step_number(next_step),
            status="open",
            appealed_from_prior_step=from_step,
            prior_step_outcome_id=prior_outcome_id
            or (prior_stage.outcomes[-1].outcome_id if prior_stage.outcomes else None),
            template_id=template_id,
            template_availability=availability.availability_status,
            opened_at=now,
        )
        state.steps.append(new_stage)
        state.current_step_type = next_step
        state.workspace_status = "open"

        self._append_timeline_event(
            state,
            event_type="appealed_to_next_step",
            title=f"Appealed to {next_step.replace('_', ' ')}",
            step_type=next_step,
            details=f"Prior step: {from_step}",
            event_timestamp=now,
            references=CaseTimelineEventReferences(
                prior_step_type=from_step,
                next_step_type=next_step,
                outcome_id=new_stage.prior_step_outcome_id,
            ),
        )
        self._append_timeline_event(
            state,
            event_type="case_opened",
            title=f"{next_step.replace('_', ' ').title()} opened",
            step_type=next_step,
            event_timestamp=now,
        )
        return new_stage

    def record_form_draft_created(
        self,
        case_uuid: str,
        draft_input: CaseFormDraftHistoryInput,
        *,
        event_timestamp: datetime | None = None,
    ) -> CaseFormDraftHistoryRecord:
        """Persist draft history metadata and add a timeline event."""
        state = self.get_progression(case_uuid)
        stage = self._get_stage(state, draft_input.step_type)
        now = event_timestamp or self._now()

        record = CaseFormDraftHistoryRecord(
            case_uuid=case_uuid,
            step_type=draft_input.step_type,
            template_id=draft_input.template_id,
            draft_version=draft_input.draft_version,
            report_version_id=draft_input.report_version_id,
            report_version_number=draft_input.report_version_number,
            follow_up_message_ids=list(draft_input.follow_up_message_ids),
            validation_status=draft_input.validation.status,
            missing_required_field_ids=[
                item.field_id for item in draft_input.validation.missing_required_fields
            ],
            steward_override_field_ids=list(draft_input.steward_override_field_ids),
            approval_status=draft_input.approval_status,
            export_status=draft_input.export_status,
            created_at=now,
        )
        state.form_draft_history.append(record)
        stage.form_draft_ids.append(record.draft_id)
        stage.template_id = draft_input.template_id
        stage.status = "draft_form_created"

        if draft_input.report_version_id is not None:
            stage.report_version_id = draft_input.report_version_id
        if draft_input.report_version_number is not None:
            stage.report_version_number = draft_input.report_version_number
        if draft_input.follow_up_message_ids:
            stage.follow_up_message_ids = sorted(
                set(stage.follow_up_message_ids) | set(draft_input.follow_up_message_ids)
            )

        self._append_timeline_event(
            state,
            event_type="form_draft_created",
            title="Official grievance form draft created",
            step_type=draft_input.step_type,
            details=f"template={draft_input.template_id}; draft_version={draft_input.draft_version}",
            event_timestamp=now,
            references=CaseTimelineEventReferences(
                report_version_id=draft_input.report_version_id,
                report_version_number=draft_input.report_version_number,
                follow_up_message_ids=draft_input.follow_up_message_ids,
                form_draft_id=record.draft_id,
            ),
        )
        return record

    def build_step_form_draft(
        self,
        case_uuid: str,
        step_type: StepType,
        draft_input: GrievanceFormDraftInput,
        *,
        template_id: str | None = None,
        record_history: bool = True,
        event_timestamp: datetime | None = None,
    ):
        """Build a Step 1 or Step 2 draft and optionally record history."""
        availability = self.get_step_template_availability(step_type)
        if not availability.template_available:
            raise CaseStepProgressionError(
                f"No buildable official template for {step_type}: "
                f"{availability.availability_status}"
            )

        resolved_template_id = template_id or availability.template_id
        if resolved_template_id is None:
            raise CaseStepProgressionError(f"No template id resolved for {step_type}.")

        buildable = self.list_buildable_template_ids_for_step(step_type)
        if resolved_template_id not in buildable:
            registered = get_grievance_template_by_id(resolved_template_id)
            if registered is None:
                raise CaseStepProgressionError(
                    f"Unknown template id for step draft: {resolved_template_id}"
                )
            raise CaseStepProgressionError(
                f"Template {resolved_template_id} is not buildable for {step_type}."
            )

        case_context = draft_input.case_context or GrievanceFormDraftCaseContext()
        case_context.case_uuid = case_uuid
        draft_input = draft_input.model_copy(update={"case_context": case_context})

        draft = build_grievance_form_draft(resolved_template_id, draft_input)

        history_record = None
        if record_history:
            follow_up_ids = (
                draft_input.follow_up_context.follow_up_message_ids
                if draft_input.follow_up_context
                else []
            )
            override_ids = sorted(draft_input.steward_overrides)
            history_record = self.record_form_draft_created(
                case_uuid,
                CaseFormDraftHistoryInput(
                    step_type=step_type,
                    template_id=resolved_template_id,
                    draft_version=case_context.draft_version,
                    report_version_id=case_context.report_version_id,
                    report_version_number=case_context.report_version_number,
                    follow_up_message_ids=follow_up_ids,
                    validation=draft.validation,
                    steward_override_field_ids=override_ids,
                ),
                event_timestamp=event_timestamp,
            )

        return draft, history_record

    @staticmethod
    def sort_timeline_oldest_first(
        state: CaseStepProgressionState,
    ) -> list[CaseTimelineEvent]:
        return sorted(state.timeline, key=lambda event: event.event_timestamp)

    @staticmethod
    def sort_timeline_newest_first(
        state: CaseStepProgressionState,
    ) -> list[CaseTimelineEvent]:
        return sorted(
            state.timeline,
            key=lambda event: event.event_timestamp,
            reverse=True,
        )

    @staticmethod
    def get_prior_step_outcome(
        state: CaseStepProgressionState,
        step_type: StepType,
    ) -> CaseStepOutcomeRecord | None:
        stage = next((item for item in state.steps if item.step_type == step_type), None)
        if stage is None or not stage.outcomes:
            return None
        return stage.outcomes[-1]

    @staticmethod
    def registered_templates_for_step(step_type: StepType) -> list[str]:
        """List registry template ids whose step_level matches the requested step."""
        return [
            template.template_id
            for template in list_registered_grievance_templates()
            if template.step_level == step_type
        ]

    def clear(self) -> None:
        """Reset in-memory store (testing helper)."""
        self._states.clear()
