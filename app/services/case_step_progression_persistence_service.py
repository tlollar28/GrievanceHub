"""Database persistence for grievance case step progression (Phase 1.4D).

Persists the Phase 1.4C same-case lifecycle concepts to SQLAlchemy tables.
The in-memory CaseStepProgressionService remains available for unit tests and
future API wiring.

No OpenAI, no PDF/DOCX export, no filled-form disk output in this phase.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.orm import Session, joinedload

from app.database.models import (
    CaseFormDraftRecord,
    CaseStep,
    CaseStepOutcome,
    CaseTimelineEventRecord,
    GrievanceCase,
)
from app.schemas.case_step_progression_schema import (
    CaseFormDraftHistoryInput,
    CaseFormDraftHistoryRecord,
    CaseStepOutcomeInput,
    CaseStepOutcomeRecord,
    CaseStepProgressionState,
    CaseStepStage,
    CaseTimelineEvent,
    CaseTimelineEventReferences,
    StepType,
    TimelineEventType,
)
from app.services.case_step_progression_service import (
    CaseStepNotFoundError,
    CaseStepProgressionError,
    CaseStepProgressionNotFoundError,
    CaseStepProgressionService,
    _NEXT_STEP,
    _RESOLVED_OUTCOME_TYPES,
)

_NEXT_STEP_TYPE = _NEXT_STEP


def _now() -> datetime:
    return datetime.now(UTC)


def _to_naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _to_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class CaseStepProgressionPersistenceService:
    """SQLAlchemy-backed case step progression persistence (Phase 1.4D)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def get_step_template_availability(step_type: StepType):
        return CaseStepProgressionService.get_step_template_availability(step_type)

    @staticmethod
    def list_buildable_template_ids_for_step(step_type: StepType) -> list[str]:
        return CaseStepProgressionService.list_buildable_template_ids_for_step(step_type)

    def _get_case_row(self, case_uuid: str) -> GrievanceCase:
        row = (
            self.db.query(GrievanceCase)
            .filter(GrievanceCase.case_uuid == case_uuid)
            .first()
        )
        if row is None:
            raise CaseStepProgressionNotFoundError(case_uuid)
        return row

    def _get_step_row(self, case_uuid: str, step_type: StepType) -> CaseStep:
        case = self._get_case_row(case_uuid)
        step = (
            self.db.query(CaseStep)
            .filter(CaseStep.case_id == case.id, CaseStep.step_type == step_type)
            .first()
        )
        if step is None:
            raise CaseStepNotFoundError(step_type)
        return step

    def _has_progression(self, case_uuid: str) -> bool:
        return (
            self.db.query(CaseStep.id)
            .filter(CaseStep.case_uuid == case_uuid)
            .first()
            is not None
        )

    def _append_timeline_event(
        self,
        case: GrievanceCase,
        *,
        event_type: TimelineEventType,
        title: str,
        step_type: StepType | None = None,
        case_step_id: int | None = None,
        details: str | None = None,
        event_timestamp: datetime | None = None,
        references: CaseTimelineEventReferences | None = None,
        draft_record_id: int | None = None,
    ) -> CaseTimelineEventRecord:
        refs = references or CaseTimelineEventReferences()
        ts = _to_naive_utc(event_timestamp or _now())
        row = CaseTimelineEventRecord(
            event_uuid=str(uuid4()),
            case_id=case.id,
            case_uuid=case.case_uuid,
            case_step_id=case_step_id,
            step_type=step_type,
            event_type=event_type,
            event_timestamp=ts,
            title=title,
            details=details,
            report_version_id=refs.report_version_id,
            report_version_number=refs.report_version_number,
            follow_up_message_ids=list(refs.follow_up_message_ids),
            draft_record_id=draft_record_id,
            draft_record_uuid=refs.form_draft_id,
            upload_refs=list(refs.upload_refs),
            outcome_uuid=refs.outcome_id,
            prior_step_type=refs.prior_step_type,
            next_step_type=refs.next_step_type,
            export_ref=refs.export_ref,
            created_at=ts,
        )
        self.db.add(row)
        self.db.flush()
        return row

    @staticmethod
    def _outcome_row_to_schema(row: CaseStepOutcome) -> CaseStepOutcomeRecord:
        return CaseStepOutcomeRecord(
            outcome_id=row.outcome_uuid,
            step_type=row.step_type,  # type: ignore[arg-type]
            outcome_type=row.outcome_type,  # type: ignore[arg-type]
            decision_summary=row.decision_summary,
            decision_date=row.decision_date,
            decision_maker_name=row.decision_maker_name,
            decision_maker_title=row.decision_maker_title,
            decision_document_refs=list(row.decision_document_refs or []),
            steward_notes=row.steward_notes,
            step_closed=row.close_step,
            case_closed=row.close_case,
            appeal_requested=row.appeal_to_next_step,
            next_step_target=row.next_step_type,  # type: ignore[arg-type]
            recorded_at=_to_aware_utc(row.recorded_at),
        )

    @staticmethod
    def _timeline_row_to_schema(row: CaseTimelineEventRecord) -> CaseTimelineEvent:
        return CaseTimelineEvent(
            event_id=row.event_uuid,
            case_uuid=row.case_uuid,
            step_type=row.step_type,  # type: ignore[arg-type]
            event_type=row.event_type,  # type: ignore[arg-type]
            event_timestamp=_to_aware_utc(row.event_timestamp),
            title=row.title,
            details=row.details,
            references=CaseTimelineEventReferences(
                report_version_id=row.report_version_id,
                report_version_number=row.report_version_number,
                follow_up_message_ids=list(row.follow_up_message_ids or []),
                form_draft_id=row.draft_record_uuid,
                upload_refs=list(row.upload_refs or []),
                outcome_id=row.outcome_uuid,
                prior_step_type=row.prior_step_type,  # type: ignore[arg-type]
                next_step_type=row.next_step_type,  # type: ignore[arg-type]
                export_ref=row.export_ref,
            ),
        )

    @staticmethod
    def _draft_row_to_schema(row: CaseFormDraftRecord) -> CaseFormDraftHistoryRecord:
        return CaseFormDraftHistoryRecord(
            draft_id=row.draft_uuid,
            case_uuid=row.case_uuid,
            step_type=row.case_step.step_type,  # type: ignore[arg-type]
            template_id=row.template_id,
            draft_version=row.draft_version,
            report_version_id=row.report_version_id,
            report_version_number=row.report_version_number,
            follow_up_message_ids=list(row.follow_up_message_ids or []),
            validation_status=row.validation_status or row.draft_status,  # type: ignore[arg-type]
            missing_required_field_ids=list(row.missing_required_field_ids or []),
            steward_override_field_ids=list(row.steward_override_field_ids or []),
            approval_status=row.approval_status,
            export_status=row.export_status,
            created_at=_to_aware_utc(row.created_at),
        )

    def _step_row_to_schema(
        self,
        step: CaseStep,
        *,
        outcomes: list[CaseStepOutcome] | None = None,
        draft_uuids: list[str] | None = None,
    ) -> CaseStepStage:
        outcome_rows = outcomes
        if outcome_rows is None:
            outcome_rows = (
                self.db.query(CaseStepOutcome)
                .filter(CaseStepOutcome.case_step_id == step.id)
                .order_by(CaseStepOutcome.recorded_at.asc())
                .all()
            )
        draft_ids = draft_uuids
        if draft_ids is None:
            draft_ids = [
                item.draft_uuid
                for item in (
                    self.db.query(CaseFormDraftRecord)
                    .filter(CaseFormDraftRecord.case_step_id == step.id)
                    .order_by(CaseFormDraftRecord.created_at.asc())
                    .all()
                )
            ]
        return CaseStepStage(
            step_type=step.step_type,  # type: ignore[arg-type]
            step_number=step.step_number,
            status=step.status,  # type: ignore[arg-type]
            is_closed=step.is_closed,
            was_reopened=step.was_reopened,
            appealed_from_prior_step=step.appealed_from_prior_step,  # type: ignore[arg-type]
            prior_step_outcome_id=step.prior_step_outcome_uuid,
            report_version_id=step.report_version_id,
            report_version_number=step.report_version_number,
            follow_up_message_ids=list(step.follow_up_message_ids or []),
            form_draft_ids=draft_ids,
            template_id=step.template_id,
            template_availability=step.template_availability,  # type: ignore[arg-type]
            outcomes=[self._outcome_row_to_schema(item) for item in outcome_rows],
            opened_at=_to_aware_utc(step.opened_at),
            closed_at=_to_aware_utc(step.closed_at) if step.closed_at else None,
            reopened_at=_to_aware_utc(step.reopened_at) if step.reopened_at else None,
        )

    def _derive_workspace_status(
        self,
        timeline_rows: list[CaseTimelineEventRecord],
    ) -> tuple[str, datetime | None, datetime | None]:
        closed_at: datetime | None = None
        reopened_at: datetime | None = None
        status = "open"
        for row in sorted(timeline_rows, key=lambda item: item.event_timestamp):
            if row.event_type == "case_closed":
                closed_at = _to_aware_utc(row.event_timestamp)
                status = "closed"
            elif row.event_type == "case_settled":
                closed_at = _to_aware_utc(row.event_timestamp)
                status = "settled"
            elif row.event_type == "case_archived":
                closed_at = _to_aware_utc(row.event_timestamp)
                status = "archived"
            elif row.event_type == "case_reopened":
                reopened_at = _to_aware_utc(row.event_timestamp)
                status = "open"
        return status, closed_at, reopened_at

    def _build_progression_state(self, case_uuid: str) -> CaseStepProgressionState:
        case = self._get_case_row(case_uuid)
        steps = (
            self.db.query(CaseStep)
            .filter(CaseStep.case_id == case.id)
            .order_by(CaseStep.step_number.asc())
            .all()
        )
        if not steps:
            raise CaseStepProgressionNotFoundError(case_uuid)

        step_ids = [step.id for step in steps]
        outcome_rows = (
            self.db.query(CaseStepOutcome)
            .filter(CaseStepOutcome.case_step_id.in_(step_ids))
            .order_by(CaseStepOutcome.recorded_at.asc())
            .all()
            if step_ids
            else []
        )
        outcomes_by_step: dict[int, list[CaseStepOutcome]] = {}
        for outcome in outcome_rows:
            outcomes_by_step.setdefault(outcome.case_step_id, []).append(outcome)

        timeline_rows = (
            self.db.query(CaseTimelineEventRecord)
            .filter(CaseTimelineEventRecord.case_id == case.id)
            .order_by(CaseTimelineEventRecord.event_timestamp.asc())
            .all()
        )
        draft_rows = (
            self.db.query(CaseFormDraftRecord)
            .options(joinedload(CaseFormDraftRecord.case_step))
            .filter(CaseFormDraftRecord.case_id == case.id)
            .order_by(CaseFormDraftRecord.created_at.asc())
            .all()
        )
        drafts_by_step: dict[int, list[str]] = {}
        for draft in draft_rows:
            drafts_by_step.setdefault(draft.case_step_id, []).append(draft.draft_uuid)

        workspace_status, closed_at, reopened_at = self._derive_workspace_status(
            timeline_rows
        )
        current_step_type = steps[-1].step_type  # type: ignore[arg-type]
        created_at = _to_aware_utc(steps[0].opened_at)
        updated_at = _to_aware_utc(
            timeline_rows[-1].event_timestamp if timeline_rows else steps[-1].updated_at
        )

        return CaseStepProgressionState(
            case_uuid=case_uuid,
            workspace_status=workspace_status,  # type: ignore[arg-type]
            current_step_type=current_step_type,
            steps=[
                self._step_row_to_schema(
                    step,
                    outcomes=outcomes_by_step.get(step.id, []),
                    draft_uuids=drafts_by_step.get(step.id, []),
                )
                for step in steps
            ],
            timeline=[self._timeline_row_to_schema(row) for row in timeline_rows],
            form_draft_history=[self._draft_row_to_schema(row) for row in draft_rows],
            created_at=created_at,
            updated_at=updated_at,
            closed_at=closed_at,
            reopened_at=reopened_at,
        )

    def ensure_case_progression(
        self,
        case_uuid: str,
        *,
        event_timestamp: datetime | None = None,
        commit: bool = True,
    ) -> CaseStepProgressionState:
        """Return existing progression or create Step 1 once (idempotent)."""
        if self._has_progression(case_uuid):
            return self._build_progression_state(case_uuid)
        return self.create_case_progression(
            case_uuid,
            event_timestamp=event_timestamp,
            commit=commit,
        )

    def create_case_progression(
        self,
        case_uuid: str,
        *,
        event_timestamp: datetime | None = None,
        commit: bool = True,
    ) -> CaseStepProgressionState:
        """Initialize persisted progression starting at Step 1 for an existing case."""
        if self._has_progression(case_uuid):
            raise CaseStepProgressionError(
                f"Case progression already exists for case_uuid={case_uuid}"
            )

        case = self._get_case_row(case_uuid)
        now = _to_naive_utc(event_timestamp or _now())
        availability = self.get_step_template_availability("step_1_initial")

        step = CaseStep(
            case_id=case.id,
            case_uuid=case_uuid,
            step_type="step_1_initial",
            step_number=1,
            status="open",
            template_id=availability.template_id,
            template_available=availability.template_available,
            template_availability=availability.availability_status,
            opened_at=now,
            created_at=now,
            updated_at=now,
        )
        self.db.add(step)
        self.db.flush()

        self._append_timeline_event(
            case,
            event_type="case_created",
            title="Case created",
            step_type="step_1_initial",
            case_step_id=step.id,
            event_timestamp=event_timestamp,
        )
        self._append_timeline_event(
            case,
            event_type="case_opened",
            title="Step 1 opened",
            step_type="step_1_initial",
            case_step_id=step.id,
            event_timestamp=event_timestamp,
        )
        if commit:
            self.db.commit()
        else:
            self.db.flush()
        return self._build_progression_state(case_uuid)

    def get_progression(self, case_uuid: str) -> CaseStepProgressionState:
        if not self._has_progression(case_uuid):
            raise CaseStepProgressionNotFoundError(case_uuid)
        return self._build_progression_state(case_uuid)

    def get_case_step(self, case_uuid: str, step_type: StepType) -> CaseStepStage:
        step = self._get_step_row(case_uuid, step_type)
        return self._step_row_to_schema(step)

    def add_step_outcome(
        self,
        case_uuid: str,
        step_type: StepType,
        outcome_input: CaseStepOutcomeInput,
        *,
        event_timestamp: datetime | None = None,
    ) -> tuple[CaseStepOutcomeRecord, CaseStepStage]:
        case = self._get_case_row(case_uuid)
        step = self._get_step_row(case_uuid, step_type)
        now = _to_naive_utc(event_timestamp or _now())

        outcome_row = CaseStepOutcome(
            outcome_uuid=str(uuid4()),
            case_id=case.id,
            case_uuid=case_uuid,
            case_step_id=step.id,
            step_type=step_type,
            outcome_type=outcome_input.outcome_type,
            decision_summary=outcome_input.decision_summary,
            decision_date=outcome_input.decision_date,
            decision_maker_name=outcome_input.decision_maker_name,
            decision_maker_title=outcome_input.decision_maker_title,
            decision_document_refs=list(outcome_input.decision_document_refs),
            steward_notes=outcome_input.steward_notes,
            close_step=outcome_input.close_step,
            close_case=outcome_input.close_case,
            appeal_to_next_step=outcome_input.appeal_to_next_step,
            next_step_type=_NEXT_STEP_TYPE[step_type]
            if outcome_input.appeal_to_next_step
            else None,
            recorded_at=now,
            created_at=now,
        )
        self.db.add(outcome_row)
        step.status = "decision_added"
        step.updated_at = now
        self.db.flush()

        outcome_schema = self._outcome_row_to_schema(outcome_row)
        self._append_timeline_event(
            case,
            event_type="step_decision_added",
            title=f"{step_type.replace('_', ' ').title()} decision recorded",
            step_type=step_type,
            case_step_id=step.id,
            details=outcome_input.decision_summary,
            event_timestamp=event_timestamp,
            references=CaseTimelineEventReferences(outcome_id=outcome_row.outcome_uuid),
        )

        if outcome_input.close_step:
            self.close_step(
                case_uuid,
                step_type,
                reason=outcome_input.outcome_type,
                event_timestamp=event_timestamp,
                commit=False,
            )
            step = self._get_step_row(case_uuid, step_type)

        if outcome_input.close_case:
            self.close_case(
                case_uuid,
                reason=outcome_input.outcome_type,
                event_timestamp=event_timestamp,
                commit=False,
            )

        if outcome_input.appeal_to_next_step:
            self.appeal_to_next_step(
                case_uuid,
                from_step=step_type,
                prior_outcome_id=outcome_row.outcome_uuid,
                event_timestamp=event_timestamp,
                commit=False,
            )
            step = self._get_step_row(case_uuid, step_type)

        self.db.commit()
        return outcome_schema, self._step_row_to_schema(step)

    def close_step(
        self,
        case_uuid: str,
        step_type: StepType,
        *,
        reason: str | None = None,
        event_timestamp: datetime | None = None,
        commit: bool = True,
    ) -> CaseStepStage:
        case = self._get_case_row(case_uuid)
        step = self._get_step_row(case_uuid, step_type)
        if step.is_closed and not step.was_reopened:
            return self._step_row_to_schema(step)

        now = _to_naive_utc(event_timestamp or _now())
        step.is_closed = True
        step.closed_at = now
        step.updated_at = now
        if reason in {"withdrawn"}:
            step.status = "closed_withdrawn"
        elif reason in _RESOLVED_OUTCOME_TYPES:
            step.status = "closed_resolved"
        else:
            step.status = "closed_resolved"

        self._append_timeline_event(
            case,
            event_type="step_closed",
            title=f"{step_type.replace('_', ' ').title()} closed",
            step_type=step_type,
            case_step_id=step.id,
            details=reason,
            event_timestamp=event_timestamp,
        )
        if commit:
            self.db.commit()
        else:
            self.db.flush()
        return self._step_row_to_schema(step)

    def close_case(
        self,
        case_uuid: str,
        *,
        reason: str | None = None,
        event_timestamp: datetime | None = None,
        commit: bool = True,
    ) -> CaseStepProgressionState:
        case = self._get_case_row(case_uuid)
        state = self.get_progression(case_uuid)
        now = _to_naive_utc(event_timestamp or _now())

        self._append_timeline_event(
            case,
            event_type="case_closed",
            title="Case closed",
            step_type=state.current_step_type,
            details=reason,
            event_timestamp=event_timestamp or _to_aware_utc(now),
        )
        if commit:
            self.db.commit()
        else:
            self.db.flush()
        return self.get_progression(case_uuid)

    def settle_case(
        self,
        case_uuid: str,
        *,
        reason: str | None = None,
        event_timestamp: datetime | None = None,
        commit: bool = True,
    ) -> CaseStepProgressionState:
        """Mark case settled. Never deletes case history or artifacts."""
        case = self._get_case_row(case_uuid)
        state = self.get_progression(case_uuid)
        now = _to_naive_utc(event_timestamp or _now())
        self._append_timeline_event(
            case,
            event_type="case_settled",
            title="Case settled",
            step_type=state.current_step_type,
            details=reason or "Case settled; permanent record retained.",
            event_timestamp=event_timestamp or _to_aware_utc(now),
        )
        if commit:
            self.db.commit()
        else:
            self.db.flush()
        return self.get_progression(case_uuid)

    def archive_case(
        self,
        case_uuid: str,
        *,
        reason: str | None = None,
        event_timestamp: datetime | None = None,
        commit: bool = True,
    ) -> CaseStepProgressionState:
        """Future-ready archive. Never deletes case history or artifacts."""
        case = self._get_case_row(case_uuid)
        state = self.get_progression(case_uuid)
        now = _to_naive_utc(event_timestamp or _now())
        self._append_timeline_event(
            case,
            event_type="case_archived",
            title="Case archived",
            step_type=state.current_step_type,
            details=reason or "Case archived; permanent record retained.",
            event_timestamp=event_timestamp or _to_aware_utc(now),
        )
        if commit:
            self.db.commit()
        else:
            self.db.flush()
        return self.get_progression(case_uuid)

    def reopen_step(
        self,
        case_uuid: str,
        step_type: StepType,
        *,
        event_timestamp: datetime | None = None,
    ) -> CaseStepStage:
        case = self._get_case_row(case_uuid)
        step = self._get_step_row(case_uuid, step_type)
        if not step.is_closed:
            raise CaseStepProgressionError(
                f"Step {step_type} is not closed and cannot be reopened."
            )

        now = _to_naive_utc(event_timestamp or _now())
        step.is_closed = False
        step.was_reopened = True
        step.reopened_at = now
        step.status = "reopened"
        step.updated_at = now

        self._append_timeline_event(
            case,
            event_type="step_reopened",
            title=f"{step_type.replace('_', ' ').title()} reopened",
            step_type=step_type,
            case_step_id=step.id,
            event_timestamp=event_timestamp,
        )
        self.db.commit()
        return self._step_row_to_schema(step)

    def reopen_case(
        self,
        case_uuid: str,
        *,
        reason: str | None = None,
        source: str | None = None,
        event_timestamp: datetime | None = None,
    ) -> CaseStepProgressionState:
        state = self.get_progression(case_uuid)
        if state.workspace_status not in {"closed", "settled", "archived"}:
            return state

        case = self._get_case_row(case_uuid)
        details_parts = []
        if source:
            details_parts.append(f"source={source}")
        if reason:
            details_parts.append(f"reason={reason}")
        details = "; ".join(details_parts) if details_parts else None

        self._append_timeline_event(
            case,
            event_type="case_reopened",
            title="Case reopened",
            step_type=state.current_step_type,
            details=details,
            event_timestamp=event_timestamp,
        )
        self.db.commit()
        return self.get_progression(case_uuid)

    def appeal_to_next_step(
        self,
        case_uuid: str,
        from_step: StepType,
        *,
        prior_outcome_id: str | None = None,
        event_timestamp: datetime | None = None,
        commit: bool = True,
    ) -> CaseStepStage:
        case = self._get_case_row(case_uuid)
        prior_step = self._get_step_row(case_uuid, from_step)
        next_step = _NEXT_STEP_TYPE[from_step]
        if next_step is None:
            raise CaseStepProgressionError(f"No next step available after {from_step}.")

        existing = (
            self.db.query(CaseStep.id)
            .filter(CaseStep.case_id == case.id, CaseStep.step_type == next_step)
            .first()
        )
        if existing is not None:
            raise CaseStepProgressionError(
                f"Step {next_step} already exists on case {case_uuid}."
            )

        now = _to_naive_utc(event_timestamp or _now())
        if not prior_step.is_closed:
            self.close_step(
                case_uuid,
                from_step,
                reason="appealed",
                event_timestamp=event_timestamp,
                commit=False,
            )
            prior_step = self._get_step_row(case_uuid, from_step)

        prior_step.status = "appealed_to_next_step"
        prior_step.updated_at = now

        if prior_outcome_id is None:
            latest_outcome = (
                self.db.query(CaseStepOutcome)
                .filter(CaseStepOutcome.case_step_id == prior_step.id)
                .order_by(CaseStepOutcome.recorded_at.desc())
                .first()
            )
            prior_outcome_id = latest_outcome.outcome_uuid if latest_outcome else None

        availability = self.get_step_template_availability(next_step)
        new_step = CaseStep(
            case_id=case.id,
            case_uuid=case_uuid,
            step_type=next_step,
            step_number=CaseStepProgressionService._step_number(next_step),
            status="open",
            appealed_from_prior_step=from_step,
            prior_step_id=prior_step.id,
            prior_step_outcome_uuid=prior_outcome_id,
            template_id=availability.template_id,
            template_available=availability.template_available,
            template_availability=availability.availability_status,
            opened_at=now,
            created_at=now,
            updated_at=now,
        )
        self.db.add(new_step)
        self.db.flush()

        self._append_timeline_event(
            case,
            event_type="appealed_to_next_step",
            title=f"Appealed to {next_step.replace('_', ' ')}",
            step_type=next_step,
            case_step_id=new_step.id,
            details=f"Prior step: {from_step}",
            event_timestamp=event_timestamp,
            references=CaseTimelineEventReferences(
                prior_step_type=from_step,
                next_step_type=next_step,
                outcome_id=prior_outcome_id,
            ),
        )
        self._append_timeline_event(
            case,
            event_type="case_opened",
            title=f"{next_step.replace('_', ' ').title()} opened",
            step_type=next_step,
            case_step_id=new_step.id,
            event_timestamp=event_timestamp,
        )
        if commit:
            self.db.commit()
        else:
            self.db.flush()
        return self._step_row_to_schema(new_step)

    def add_timeline_event(
        self,
        case_uuid: str,
        *,
        event_type: TimelineEventType,
        title: str,
        step_type: StepType | None = None,
        details: str | None = None,
        event_timestamp: datetime | None = None,
        references: CaseTimelineEventReferences | None = None,
    ) -> CaseTimelineEvent:
        case = self._get_case_row(case_uuid)
        case_step_id = None
        if step_type is not None:
            step = self._get_step_row(case_uuid, step_type)
            case_step_id = step.id
        row = self._append_timeline_event(
            case,
            event_type=event_type,
            title=title,
            step_type=step_type,
            case_step_id=case_step_id,
            details=details,
            event_timestamp=event_timestamp,
            references=references,
        )
        self.db.commit()
        return self._timeline_row_to_schema(row)

    def list_timeline_events(
        self,
        case_uuid: str,
        *,
        newest_first: bool = False,
    ) -> list[CaseTimelineEvent]:
        case = self._get_case_row(case_uuid)
        query = (
            self.db.query(CaseTimelineEventRecord)
            .filter(CaseTimelineEventRecord.case_id == case.id)
            .order_by(CaseTimelineEventRecord.event_timestamp.asc())
        )
        rows = query.all()
        events = [self._timeline_row_to_schema(row) for row in rows]
        if newest_first:
            return sorted(events, key=lambda item: item.event_timestamp, reverse=True)
        return events

    def create_form_draft_record(
        self,
        case_uuid: str,
        draft_input: CaseFormDraftHistoryInput,
        *,
        event_timestamp: datetime | None = None,
    ) -> CaseFormDraftHistoryRecord:
        """Persist a form draft history record linked to case/step/report/follow-ups."""
        case = self._get_case_row(case_uuid)
        step = self._get_step_row(case_uuid, draft_input.step_type)
        now = _to_naive_utc(event_timestamp or _now())

        row = CaseFormDraftRecord(
            draft_uuid=str(uuid4()),
            case_id=case.id,
            case_uuid=case_uuid,
            case_step_id=step.id,
            template_id=draft_input.template_id,
            report_version_id=draft_input.report_version_id,
            report_version_number=draft_input.report_version_number,
            follow_up_message_ids=list(draft_input.follow_up_message_ids),
            draft_version=draft_input.draft_version,
            draft_status=draft_input.validation.status,
            validation_status=draft_input.validation.status,
            missing_required_field_ids=[
                item.field_id for item in draft_input.validation.missing_required_fields
            ],
            steward_override_field_ids=list(draft_input.steward_override_field_ids),
            approval_status=draft_input.approval_status,
            export_status=draft_input.export_status,
            export_attempted=False,
            created_at=now,
        )
        self.db.add(row)
        step.status = "draft_form_created"
        step.template_id = draft_input.template_id
        if draft_input.report_version_id is not None:
            step.report_version_id = draft_input.report_version_id
        if draft_input.report_version_number is not None:
            step.report_version_number = draft_input.report_version_number
        if draft_input.follow_up_message_ids:
            merged = sorted(
                set(step.follow_up_message_ids or [])
                | set(draft_input.follow_up_message_ids)
            )
            step.follow_up_message_ids = merged
        step.updated_at = now
        self.db.flush()

        self._append_timeline_event(
            case,
            event_type="form_draft_created",
            title="Official grievance form draft created",
            step_type=draft_input.step_type,
            case_step_id=step.id,
            details=(
                f"template={draft_input.template_id}; "
                f"draft_version={draft_input.draft_version}"
            ),
            event_timestamp=event_timestamp,
            references=CaseTimelineEventReferences(
                report_version_id=draft_input.report_version_id,
                report_version_number=draft_input.report_version_number,
                follow_up_message_ids=draft_input.follow_up_message_ids,
                form_draft_id=row.draft_uuid,
            ),
            draft_record_id=row.id,
        )
        self.db.commit()
        return self._draft_row_to_schema(row)

    def build_step_form_draft(
        self,
        case_uuid: str,
        step_type: StepType,
        draft_input,
        *,
        template_id: str | None = None,
        record_history: bool = True,
        event_timestamp: datetime | None = None,
    ):
        """Build a draft via Phase 1.4B and optionally persist draft history."""
        memory_service = CaseStepProgressionService()
        draft, _ = memory_service.build_step_form_draft(
            case_uuid,
            step_type,
            draft_input,
            template_id=template_id,
            record_history=False,
            event_timestamp=event_timestamp,
        )
        history_record = None
        if record_history:
            follow_up_ids = (
                draft_input.follow_up_context.follow_up_message_ids
                if draft_input.follow_up_context
                else []
            )
            case_context = draft_input.case_context
            history_record = self.create_form_draft_record(
                case_uuid,
                CaseFormDraftHistoryInput(
                    step_type=step_type,
                    template_id=template_id or draft.template_id,
                    draft_version=case_context.draft_version if case_context else 1,
                    report_version_id=case_context.report_version_id if case_context else None,
                    report_version_number=(
                        case_context.report_version_number if case_context else None
                    ),
                    follow_up_message_ids=follow_up_ids,
                    validation=draft.validation,
                    steward_override_field_ids=sorted(draft_input.steward_overrides),
                ),
                event_timestamp=event_timestamp,
            )
        return draft, history_record

    @staticmethod
    def sort_timeline_oldest_first(
        state: CaseStepProgressionState,
    ) -> list[CaseTimelineEvent]:
        return CaseStepProgressionService.sort_timeline_oldest_first(state)

    @staticmethod
    def sort_timeline_newest_first(
        state: CaseStepProgressionState,
    ) -> list[CaseTimelineEvent]:
        return CaseStepProgressionService.sort_timeline_newest_first(state)
