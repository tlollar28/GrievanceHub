"""Saved case listing, open/reopen, and timeline retrieval (Phase 1.4E).

Provides a unified backend workflow for manual UI and future AI-command reopen.
Manual and AI paths call the same service methods.

No OpenAI, no PDF/DOCX export, no filled-form disk output.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.database.models import (
    CaseStep,
    CaseStepOutcome,
    CaseTimelineEventRecord,
    GrievanceCase,
)
from app.schemas.saved_case_schema import (
    OpenCaseResponse,
    ReopenCaseResponse,
    ReopenSource,
    SavedCaseAction,
    SavedCaseListResponse,
    SavedCaseStatusFilter,
    SavedCaseSummary,
    SavedCaseTemplateAvailability,
    SavedCaseTimelineResponse,
    SavedCaseWorkspaceStatus,
)
from app.schemas.case_step_progression_schema import StepType
from app.services.case_service import CaseNotFoundError, CaseService
from app.services.case_step_progression_persistence_service import (
    CaseStepProgressionNotFoundError,
    CaseStepProgressionPersistenceService,
)
from app.services.case_step_progression_service import CaseStepProgressionService

_GRIEVANT_FACT_KEYS = (
    "grievant",
    "grievant_name",
    "grievant_name_or_class",
    "grievant_or_class",
    "employee_name",
)


def _aware_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class SavedCaseService:
    @staticmethod
    def _get_case_row(db: Session, case_uuid: str) -> GrievanceCase:
        case = CaseService._get_case_row(db, case_uuid)
        if case is None:
            raise CaseNotFoundError(case_uuid)
        return case

    @staticmethod
    def _last_activity_at(db: Session, case_id: int, fallback: datetime | None) -> datetime | None:
        latest = (
            db.query(func.max(CaseTimelineEventRecord.event_timestamp))
            .filter(CaseTimelineEventRecord.case_id == case_id)
            .scalar()
        )
        if latest is not None:
            return _aware_utc(latest)
        return _aware_utc(fallback)

    @staticmethod
    def _extract_grievant(known_facts: dict | None) -> str | None:
        if not known_facts:
            return None
        for key in _GRIEVANT_FACT_KEYS:
            value = known_facts.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @staticmethod
    def _extract_issue_summary(case: GrievanceCase) -> str | None:
        if case.report_versions:
            latest = max(case.report_versions, key=lambda item: item.version_number)
            summary = latest.report_summary if latest else None
            if isinstance(summary, dict):
                primary = summary.get("primary_issue")
                if isinstance(primary, str) and primary.strip():
                    return primary.strip()
        return None

    @staticmethod
    def _latest_outcome(
        db: Session,
        case_id: int,
    ) -> CaseStepOutcome | None:
        return (
            db.query(CaseStepOutcome)
            .filter(CaseStepOutcome.case_id == case_id)
            .order_by(CaseStepOutcome.recorded_at.desc())
            .first()
        )

    @staticmethod
    def _current_step_row(db: Session, case_id: int) -> CaseStep | None:
        return (
            db.query(CaseStep)
            .filter(CaseStep.case_id == case_id)
            .order_by(CaseStep.step_number.desc())
            .first()
        )

    @staticmethod
    def _has_reopen_event(db: Session, case_id: int) -> bool:
        return (
            db.query(CaseTimelineEventRecord.id)
            .filter(
                CaseTimelineEventRecord.case_id == case_id,
                CaseTimelineEventRecord.event_type == "case_reopened",
            )
            .first()
            is not None
        )

    @staticmethod
    def _derive_workspace_status(
        db: Session,
        case: GrievanceCase,
        progression,
    ) -> SavedCaseWorkspaceStatus:
        if progression is not None:
            if progression.workspace_status == "closed":
                return "closed"
            current_step = progression.steps[-1] if progression.steps else None
            if current_step and current_step.status == "appealed_to_next_step":
                return "appealed"
            if progression.reopened_at is not None or SavedCaseService._has_reopen_event(
                db, case.id
            ):
                return "reopened"
            return "open"

        if case.status == "closed":
            return "closed"
        return "open"

    @staticmethod
    def _build_available_actions(
        *,
        workspace_status: SavedCaseWorkspaceStatus,
        current_step,
        template_available: bool,
        latest_outcome: CaseStepOutcome | None,
    ) -> list[SavedCaseAction]:
        actions: list[SavedCaseAction] = ["open_case", "view_timeline"]
        if workspace_status == "closed":
            actions.append("reopen_case")
        if latest_outcome and latest_outcome.appeal_to_next_step:
            actions.append("continue_to_next_step")
        elif (
            current_step
            and latest_outcome
            and latest_outcome.outcome_type in {"denied", "partially_granted", "appealed"}
            and not latest_outcome.appeal_to_next_step
            and current_step.step_type in {"step_1_initial", "step_2_appeal"}
        ):
            actions.append("continue_to_next_step")
        if template_available:
            actions.append("create_form_draft")
        return sorted(set(actions))

    @classmethod
    def build_summary(cls, db: Session, case: GrievanceCase) -> SavedCaseSummary:
        progression_service = CaseStepProgressionPersistenceService(db)
        progression = None
        has_progression = False
        try:
            progression = progression_service.get_progression(case.case_uuid)
            has_progression = True
        except CaseStepProgressionNotFoundError:
            progression = None

        current_step_row = cls._current_step_row(db, case.id)
        latest_outcome = cls._latest_outcome(db, case.id)
        workspace_status = cls._derive_workspace_status(db, case, progression)

        current_step_type = None
        current_step_status = None
        closed_at = None
        reopened_at = None
        template_info = SavedCaseTemplateAvailability()

        if progression is not None:
            current_step_type = progression.current_step_type
            if progression.steps:
                stage = progression.steps[-1]
                current_step_status = stage.status
                closed_at = stage.closed_at or progression.closed_at
                reopened_at = stage.reopened_at or progression.reopened_at
            else:
                closed_at = progression.closed_at
                reopened_at = progression.reopened_at
        elif current_step_row is not None:
            current_step_type = current_step_row.step_type  # type: ignore[assignment]
            current_step_status = current_step_row.status
            closed_at = _aware_utc(current_step_row.closed_at)
            reopened_at = _aware_utc(current_step_row.reopened_at)

        if current_step_type is not None:
            availability = CaseStepProgressionService.get_step_template_availability(
                current_step_type
            )
            template_info = SavedCaseTemplateAvailability(
                step_type=current_step_type,
                template_available=availability.template_available,
                template_id=availability.template_id,
                availability_status=availability.availability_status,
            )

        last_activity = cls._last_activity_at(db, case.id, case.updated_at)

        return SavedCaseSummary(
            case_id=case.id,
            case_uuid=case.case_uuid,
            case_number=str(case.id),
            title=case.title,
            issue_summary=cls._extract_issue_summary(case),
            grievant_or_class=cls._extract_grievant(case.known_facts),
            current_step_type=current_step_type,
            current_step_status=current_step_status,
            workspace_status=workspace_status,
            legacy_case_status=case.status,
            created_at=_aware_utc(case.created_at),
            last_activity_at=last_activity,
            closed_at=closed_at,
            reopened_at=reopened_at,
            latest_outcome_summary=(
                latest_outcome.decision_summary if latest_outcome else None
            ),
            latest_outcome_type=latest_outcome.outcome_type if latest_outcome else None,
            template_availability=template_info if current_step_type else None,
            available_actions=cls._build_available_actions(
                workspace_status=workspace_status,
                current_step=current_step_row,
                template_available=template_info.template_available,
                latest_outcome=latest_outcome,
            ),
            has_step_progression=has_progression,
        )

    @classmethod
    def _matches_status_filter(
        cls,
        summary: SavedCaseSummary,
        status_filter: SavedCaseStatusFilter,
    ) -> bool:
        if status_filter == "all":
            return True
        return summary.workspace_status == status_filter

    @classmethod
    def list_saved_cases(
        cls,
        db: Session,
        *,
        status_filter: SavedCaseStatusFilter = "all",
        step_filter: StepType | None = None,
        search: str | None = None,
        newest_first: bool = True,
    ) -> SavedCaseListResponse:
        query = db.query(GrievanceCase).options(joinedload(GrievanceCase.report_versions))
        if search:
            term = f"%{search.strip()}%"
            filters = [
                GrievanceCase.case_uuid.ilike(term),
                GrievanceCase.title.ilike(term),
                GrievanceCase.initial_question.ilike(term),
            ]
            if search.strip().isdigit():
                filters.append(GrievanceCase.id == int(search.strip()))
            query = query.filter(or_(*filters))

        cases = query.all()
        summaries = [cls.build_summary(db, case) for case in cases]

        if status_filter != "all":
            summaries = [
                item
                for item in summaries
                if cls._matches_status_filter(item, status_filter)
            ]

        if step_filter is not None:
            summaries = [
                item for item in summaries if item.current_step_type == step_filter
            ]

        summaries.sort(
            key=lambda item: item.last_activity_at or datetime.min.replace(tzinfo=UTC),
            reverse=newest_first,
        )

        return SavedCaseListResponse(
            count=len(summaries),
            order="newest_first" if newest_first else "oldest_first",
            status_filter=status_filter,
            step_filter=step_filter,
            search=search,
            cases=summaries,
        )

    @classmethod
    def get_saved_case(cls, db: Session, case_uuid: str) -> SavedCaseSummary:
        case = cls._get_case_row(db, case_uuid)
        return cls.build_summary(db, case)

    @classmethod
    def open_case(
        cls,
        db: Session,
        case_uuid: str,
        *,
        source: ReopenSource = "manual_ui",
    ) -> OpenCaseResponse:
        summary = cls.get_saved_case(db, case_uuid)
        if summary.workspace_status == "closed":
            return OpenCaseResponse(
                case=summary,
                action_taken="closed_requires_reopen",
                message=(
                    "Case is closed. Use reopen_case to resume work on the same case workspace."
                ),
            )

        case = cls._get_case_row(db, case_uuid)
        if case.status == "closed":
            CaseService.reopen_case(db, case_uuid)

        return OpenCaseResponse(
            case=cls.get_saved_case(db, case_uuid),
            action_taken="already_open",
            message=f"Case is open and ready (source={source}).",
        )

    @classmethod
    def reopen_case(
        cls,
        db: Session,
        case_uuid: str,
        *,
        reason: str | None = None,
        source: ReopenSource = "manual_ui",
    ) -> ReopenCaseResponse:
        summary = cls.get_saved_case(db, case_uuid)
        if summary.workspace_status != "closed" and summary.legacy_case_status != "closed":
            return ReopenCaseResponse(
                case=summary,
                action_taken="already_open",
                message="Case is already open; no reopen timeline event added.",
                source=source,
            )

        CaseService.reopen_case(db, case_uuid)

        progression_service = CaseStepProgressionPersistenceService(db)
        try:
            progression_service.reopen_case(
                case_uuid,
                reason=reason,
                source=source,
            )
        except CaseStepProgressionNotFoundError:
            pass

        updated = cls.get_saved_case(db, case_uuid)
        return ReopenCaseResponse(
            case=updated,
            action_taken="reopened",
            message="Case reopened on the same case workspace.",
            source=source,
        )

    @classmethod
    def get_case_timeline(
        cls,
        db: Session,
        case_uuid: str,
        *,
        newest_first: bool = False,
    ) -> SavedCaseTimelineResponse:
        cls._get_case_row(db, case_uuid)
        progression_service = CaseStepProgressionPersistenceService(db)
        try:
            events = progression_service.list_timeline_events(
                case_uuid,
                newest_first=newest_first,
            )
        except CaseStepProgressionNotFoundError:
            events = []

        return SavedCaseTimelineResponse(
            case_uuid=case_uuid,
            order="newest_first" if newest_first else "oldest_first",
            count=len(events),
            events=events,
        )
