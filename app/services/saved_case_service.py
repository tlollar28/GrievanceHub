"""Saved case listing, open/reopen, and timeline retrieval (Phase 1.4E).

Provides a unified backend workflow for manual UI and future AI-command reopen.
Manual and AI paths call the same service methods.

No OpenAI, no PDF/DOCX export, no filled-form disk output.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from sqlalchemy import case as sql_case, func, or_
from sqlalchemy.orm import Session

from app.database.models import (
    CaseReportVersion,
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
            if progression.workspace_status in {"closed", "settled", "archived"}:
                return progression.workspace_status  # type: ignore[return-value]
            current_step = progression.steps[-1] if progression.steps else None
            if current_step and current_step.status == "appealed_to_next_step":
                return "appealed"
            if progression.reopened_at is not None or SavedCaseService._has_reopen_event(
                db, case.id
            ):
                return "reopened"
            return "open"

        if case.status in {"closed", "settled", "archived"}:
            return case.status  # type: ignore[return-value]
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
        if workspace_status in {"closed", "settled", "archived"}:
            actions.append("reopen_case")
        if workspace_status == "open" or workspace_status == "reopened":
            actions.append("settle_case")
            actions.append("archive_case")
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

    @staticmethod
    def _latest_reports_by_case(
        db: Session,
        case_ids: list[int],
    ) -> dict[int, CaseReportVersion]:
        if not case_ids:
            return {}
        ranked = (
            db.query(
                CaseReportVersion.id.label("report_id"),
                func.row_number()
                .over(
                    partition_by=CaseReportVersion.case_id,
                    order_by=(
                        CaseReportVersion.version_number.desc(),
                        CaseReportVersion.id.desc(),
                    ),
                )
                .label("row_number"),
            )
            .filter(CaseReportVersion.case_id.in_(case_ids))
            .subquery()
        )
        rows = (
            db.query(CaseReportVersion)
            .join(ranked, ranked.c.report_id == CaseReportVersion.id)
            .filter(ranked.c.row_number == 1)
            .all()
        )
        return {row.case_id: row for row in rows}

    @staticmethod
    def _latest_outcomes_by_case(
        db: Session,
        case_ids: list[int],
    ) -> dict[int, CaseStepOutcome]:
        if not case_ids:
            return {}
        ranked = (
            db.query(
                CaseStepOutcome.id.label("outcome_id"),
                func.row_number()
                .over(
                    partition_by=CaseStepOutcome.case_id,
                    order_by=(
                        CaseStepOutcome.recorded_at.desc(),
                        CaseStepOutcome.id.desc(),
                    ),
                )
                .label("row_number"),
            )
            .filter(CaseStepOutcome.case_id.in_(case_ids))
            .subquery()
        )
        rows = (
            db.query(CaseStepOutcome)
            .join(ranked, ranked.c.outcome_id == CaseStepOutcome.id)
            .filter(ranked.c.row_number == 1)
            .all()
        )
        return {row.case_id: row for row in rows}

    @classmethod
    def _query_saved_case_page(
        cls,
        db: Session,
        *,
        status_filter: SavedCaseStatusFilter,
        step_filter: StepType | None,
        search: str | None,
        newest_first: bool,
        limit: int,
        offset: int,
    ) -> tuple[list[SavedCaseSummary], int]:
        """Fetch one dashboard page with bounded, batched database access."""
        terminal_event_types = ("case_closed", "case_settled", "case_archived")
        status_event_types = (*terminal_event_types, "case_reopened")

        timeline_aggregate = (
            db.query(
                CaseTimelineEventRecord.case_id.label("case_id"),
                func.max(CaseTimelineEventRecord.event_timestamp).label(
                    "last_activity_at"
                ),
                func.max(
                    sql_case(
                        (
                            CaseTimelineEventRecord.event_type.in_(
                                terminal_event_types
                            ),
                            CaseTimelineEventRecord.event_timestamp,
                        ),
                        else_=None,
                    )
                ).label("closed_at"),
                func.max(
                    sql_case(
                        (
                            CaseTimelineEventRecord.event_type == "case_reopened",
                            CaseTimelineEventRecord.event_timestamp,
                        ),
                        else_=None,
                    )
                ).label("reopened_at"),
            )
            .group_by(CaseTimelineEventRecord.case_id)
            .subquery()
        )

        ranked_status_events = (
            db.query(
                CaseTimelineEventRecord.case_id.label("case_id"),
                CaseTimelineEventRecord.event_type.label("event_type"),
                func.row_number()
                .over(
                    partition_by=CaseTimelineEventRecord.case_id,
                    order_by=(
                        CaseTimelineEventRecord.event_timestamp.desc(),
                        CaseTimelineEventRecord.id.desc(),
                    ),
                )
                .label("row_number"),
            )
            .filter(CaseTimelineEventRecord.event_type.in_(status_event_types))
            .subquery()
        )
        latest_status_event = (
            db.query(
                ranked_status_events.c.case_id,
                ranked_status_events.c.event_type,
            )
            .filter(ranked_status_events.c.row_number == 1)
            .subquery()
        )

        ranked_steps = (
            db.query(
                CaseStep.case_id.label("case_id"),
                CaseStep.id.label("step_id"),
                CaseStep.step_type.label("step_type"),
                CaseStep.status.label("step_status"),
                CaseStep.closed_at.label("step_closed_at"),
                CaseStep.reopened_at.label("step_reopened_at"),
                func.row_number()
                .over(
                    partition_by=CaseStep.case_id,
                    order_by=(CaseStep.step_number.desc(), CaseStep.id.desc()),
                )
                .label("row_number"),
            )
            .subquery()
        )
        current_step = (
            db.query(
                ranked_steps.c.case_id,
                ranked_steps.c.step_id,
                ranked_steps.c.step_type,
                ranked_steps.c.step_status,
                ranked_steps.c.step_closed_at,
                ranked_steps.c.step_reopened_at,
            )
            .filter(ranked_steps.c.row_number == 1)
            .subquery()
        )

        workspace_status = sql_case(
            (latest_status_event.c.event_type == "case_closed", "closed"),
            (latest_status_event.c.event_type == "case_settled", "settled"),
            (latest_status_event.c.event_type == "case_archived", "archived"),
            (current_step.c.step_status == "appealed_to_next_step", "appealed"),
            (latest_status_event.c.event_type == "case_reopened", "reopened"),
            (
                GrievanceCase.status.in_(("closed", "settled", "archived")),
                GrievanceCase.status,
            ),
            else_="open",
        )
        last_activity = func.coalesce(
            timeline_aggregate.c.last_activity_at, GrievanceCase.updated_at
        )

        query = (
            db.query(
                GrievanceCase,
                current_step.c.step_id.label("current_step_id"),
                current_step.c.step_type.label("current_step_type"),
                current_step.c.step_status.label("current_step_status"),
                func.coalesce(
                    current_step.c.step_closed_at, timeline_aggregate.c.closed_at
                ).label("closed_at"),
                func.coalesce(
                    current_step.c.step_reopened_at, timeline_aggregate.c.reopened_at
                ).label("reopened_at"),
                last_activity.label("last_activity_at"),
                workspace_status.label("workspace_status"),
            )
            .outerjoin(current_step, current_step.c.case_id == GrievanceCase.id)
            .outerjoin(
                timeline_aggregate,
                timeline_aggregate.c.case_id == GrievanceCase.id,
            )
            .outerjoin(
                latest_status_event,
                latest_status_event.c.case_id == GrievanceCase.id,
            )
        )

        if search:
            term = f"%{search.strip()}%"
            filters = [
                GrievanceCase.case_uuid.ilike(term),
                GrievanceCase.title.ilike(term),
                GrievanceCase.initial_question.ilike(term),
                GrievanceCase.user_name.ilike(term),
            ]
            if search.strip().isdigit():
                filters.append(GrievanceCase.id == int(search.strip()))
            query = query.filter(or_(*filters))
        if status_filter != "all":
            query = query.filter(workspace_status == status_filter)
        if step_filter is not None:
            query = query.filter(current_step.c.step_type == step_filter)

        total = query.order_by(None).count()
        order_columns = (last_activity.desc(), GrievanceCase.id.desc())
        if not newest_first:
            order_columns = (last_activity.asc(), GrievanceCase.id.asc())
        rows = query.order_by(*order_columns).offset(offset).limit(limit).all()

        case_ids = [row[0].id for row in rows]
        reports = cls._latest_reports_by_case(db, case_ids)
        outcomes = cls._latest_outcomes_by_case(db, case_ids)

        summaries: list[SavedCaseSummary] = []
        for row in rows:
            case = row[0]
            current_step_type = row.current_step_type
            current_step_status = row.current_step_status
            current_step_stub = (
                SimpleNamespace(
                    step_type=current_step_type,
                    status=current_step_status,
                )
                if row.current_step_id is not None
                else None
            )
            template_info = SavedCaseTemplateAvailability()
            if current_step_type is not None:
                availability = (
                    CaseStepProgressionService.get_step_template_availability(
                        current_step_type
                    )
                )
                template_info = SavedCaseTemplateAvailability(
                    step_type=current_step_type,
                    template_available=availability.template_available,
                    template_id=availability.template_id,
                    availability_status=availability.availability_status,
                )

            latest_report = reports.get(case.id)
            issue_summary = None
            if latest_report is not None and isinstance(
                latest_report.report_summary, dict
            ):
                primary = latest_report.report_summary.get("primary_issue")
                if isinstance(primary, str) and primary.strip():
                    issue_summary = primary.strip()

            latest_outcome = outcomes.get(case.id)
            summaries.append(
                SavedCaseSummary(
                    case_id=case.id,
                    case_uuid=case.case_uuid,
                    case_number=str(case.id),
                    title=case.title,
                    issue_summary=issue_summary,
                    grievant_or_class=cls._extract_grievant(case.known_facts),
                    current_step_type=current_step_type,
                    current_step_status=current_step_status,
                    workspace_status=row.workspace_status,
                    legacy_case_status=case.status,
                    created_at=_aware_utc(case.created_at),
                    last_activity_at=_aware_utc(row.last_activity_at),
                    closed_at=_aware_utc(row.closed_at),
                    reopened_at=_aware_utc(row.reopened_at),
                    latest_outcome_summary=(
                        latest_outcome.decision_summary if latest_outcome else None
                    ),
                    latest_outcome_type=(
                        latest_outcome.outcome_type if latest_outcome else None
                    ),
                    template_availability=(
                        template_info if current_step_type else None
                    ),
                    available_actions=cls._build_available_actions(
                        workspace_status=row.workspace_status,
                        current_step=current_step_stub,
                        template_available=template_info.template_available,
                        latest_outcome=latest_outcome,
                    ),
                    has_step_progression=row.current_step_id is not None,
                )
            )
        return summaries, total

    @classmethod
    def list_saved_cases(
        cls,
        db: Session,
        *,
        status_filter: SavedCaseStatusFilter = "all",
        step_filter: StepType | None = None,
        search: str | None = None,
        newest_first: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> SavedCaseListResponse:
        """Return a database-paginated saved-case dashboard page."""
        limit = max(1, min(int(limit), 100))
        offset = max(0, int(offset))
        summaries, total = cls._query_saved_case_page(
            db,
            status_filter=status_filter,
            step_filter=step_filter,
            search=search,
            newest_first=newest_first,
            limit=limit,
            offset=offset,
        )
        return SavedCaseListResponse(
            count=len(summaries),
            total=total,
            limit=limit,
            offset=offset,
            has_more=(offset + len(summaries)) < total,
            order="newest_first" if newest_first else "oldest_first",
            status_filter=status_filter,
            step_filter=step_filter,
            search=search,
            cases=summaries,
            payload_mode="summary_only",
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
        if summary.workspace_status in {"closed", "settled", "archived"}:
            return OpenCaseResponse(
                case=summary,
                action_taken="closed_requires_reopen",
                message=(
                    f"Case is {summary.workspace_status}. Use reopen_case to resume "
                    "work on the same case workspace."
                ),
                workspace=None,
            )

        case = cls._get_case_row(db, case_uuid)
        if case.status in {"closed", "settled", "archived"}:
            CaseService.reopen_case(db, case_uuid)

        # Idempotent backfill for pre-W4 cases; no-op when progression exists.
        CaseStepProgressionPersistenceService(db).ensure_case_progression(case_uuid)

        workspace = CaseService.get_case_workspace(db, case_uuid)
        return OpenCaseResponse(
            case=cls.get_saved_case(db, case_uuid),
            action_taken="already_open",
            message=f"Case is open and ready (source={source}).",
            workspace=workspace,
        )

    @classmethod
    def reopen_case(
        cls,
        db: Session,
        case_uuid: str,
        *,
        reason: str | None = None,
        reopened_by: str | None = None,
        source: ReopenSource = "manual_ui",
    ) -> ReopenCaseResponse:
        from app.services.case_memory_service import CaseMemoryService

        summary = cls.get_saved_case(db, case_uuid)
        terminal = {"closed", "settled", "archived"}
        if (
            summary.workspace_status not in terminal
            and summary.legacy_case_status not in terminal
        ):
            CaseStepProgressionPersistenceService(db).ensure_case_progression(case_uuid)
            return ReopenCaseResponse(
                case=cls.get_saved_case(db, case_uuid),
                action_taken="already_open",
                message="Case is already open; no reopen timeline event added.",
                source=source,
                workspace=CaseService.get_case_workspace(db, case_uuid),
            )

        CaseService.reopen_case(db, case_uuid)

        progression_service = CaseStepProgressionPersistenceService(db)
        had_progression = progression_service._has_progression(case_uuid)
        progression_service.ensure_case_progression(case_uuid)
        if had_progression:
            try:
                progression_service.reopen_case(
                    case_uuid,
                    reason=reason,
                    source=source,
                )
            except CaseStepProgressionNotFoundError:
                pass

        try:
            CaseMemoryService(db).record_reopen(
                case_uuid,
                reason=reason,
                reopened_by=reopened_by,
                source=source,
            )
        except Exception:
            # Reopen must succeed even if Case Memory projection is unavailable.
            pass

        updated = cls.get_saved_case(db, case_uuid)
        return ReopenCaseResponse(
            case=updated,
            action_taken="reopened",
            message="Case reopened on the same case workspace; Case Memory restored.",
            source=source,
            workspace=CaseService.get_case_workspace(db, case_uuid),
        )

    @classmethod
    def close_case_structured(
        cls,
        db: Session,
        case_uuid: str,
        *,
        outcome: str,
        outcome_notes: str | None = None,
        resolution_type: str,
        close_date=None,
        closed_by: str | None = None,
        final_grievance_step: str | None = None,
        supporting_document_refs: list[str] | None = None,
    ) -> dict:
        from app.services.case_memory_service import CaseMemoryService

        cls._get_case_row(db, case_uuid)
        CaseService.close_case(db, case_uuid)
        progression = CaseStepProgressionPersistenceService(db)
        progression.ensure_case_progression(case_uuid)
        progression.close_case(
            case_uuid,
            reason=f"{resolution_type}: {outcome}",
        )
        memory = CaseMemoryService(db).record_close(
            case_uuid,
            outcome=outcome,
            outcome_notes=outcome_notes,
            resolution_type=resolution_type,
            close_date=close_date,
            closed_by=closed_by,
            final_grievance_step=final_grievance_step,
            supporting_document_refs=supporting_document_refs,
        )
        workspace = CaseService.get_case_workspace(db, case_uuid)
        return {
            "case": cls.get_saved_case(db, case_uuid).model_dump(mode="json"),
            "action_taken": "closed",
            "message": "Case closed; permanent record retained.",
            "closure": memory.get("closure") or {},
            "workspace": workspace,
        }

    @classmethod
    def settle_case(
        cls,
        db: Session,
        case_uuid: str,
        *,
        reason: str | None = None,
        settlement_notes: str | None = None,
        settlement_date=None,
        settlement_document_refs: list[str] | None = None,
        settlement_amount: float | None = None,
        settled_by: str | None = None,
    ) -> dict:
        """Settle a case without deleting any attached record contents."""
        from app.services.case_memory_service import CaseMemoryService

        cls._get_case_row(db, case_uuid)
        CaseService.settle_case(db, case_uuid)
        progression = CaseStepProgressionPersistenceService(db)
        progression.ensure_case_progression(case_uuid)
        progression.settle_case(
            case_uuid,
            reason=settlement_notes or reason,
        )
        memory = CaseMemoryService(db).record_settle(
            case_uuid,
            settlement_notes=settlement_notes or reason,
            settlement_date=settlement_date,
            settlement_document_refs=settlement_document_refs,
            settlement_amount=settlement_amount,
            settled_by=settled_by,
        )
        workspace = CaseService.get_case_workspace(db, case_uuid)
        return {
            "case": cls.get_saved_case(db, case_uuid).model_dump(mode="json"),
            "action_taken": "settled",
            "message": "Case settled; permanent record retained.",
            "settlement": memory.get("settlement") or {},
            "workspace": workspace,
        }

    @classmethod
    def archive_case(
        cls,
        db: Session,
        case_uuid: str,
        *,
        reason: str | None = None,
    ) -> dict:
        """Archive a case (future-ready) without deleting attached contents."""
        cls._get_case_row(db, case_uuid)
        CaseService.archive_case(db, case_uuid)
        progression = CaseStepProgressionPersistenceService(db)
        progression.ensure_case_progression(case_uuid)
        progression.archive_case(case_uuid, reason=reason)
        workspace = CaseService.get_case_workspace(db, case_uuid)
        return {
            "case": cls.get_saved_case(db, case_uuid).model_dump(mode="json"),
            "action_taken": "archived",
            "message": "Case archived; permanent record retained.",
            "workspace": workspace,
        }

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
