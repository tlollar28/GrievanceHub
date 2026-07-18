"""Database-paginated saved-case dashboard tests."""

from datetime import datetime, timedelta

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database.models import (
    CaseFormDraftRecord,
    CaseMessage,
    CaseReportVersion,
    CaseStep,
    CaseStepOutcome,
    CaseTimelineEventRecord,
    GrievanceCase,
)
from app.database.session import Base
from app.services.saved_case_service import SavedCaseService


def _session_with_saved_cases():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[
            GrievanceCase.__table__,
            CaseMessage.__table__,
            CaseReportVersion.__table__,
            CaseStep.__table__,
            CaseStepOutcome.__table__,
            CaseFormDraftRecord.__table__,
            CaseTimelineEventRecord.__table__,
        ],
    )
    session = sessionmaker(bind=engine)()
    base = datetime(2026, 1, 1)
    for index in range(5):
        case_uuid = f"00000000-0000-4000-8000-{index:012d}"
        case = GrievanceCase(
            case_uuid=case_uuid,
            title=f"Case {index}",
            initial_question="Synthetic dashboard question",
            known_facts={"grievant_name": f"Employee {index}"},
            status="open",
            created_at=base,
            updated_at=base + timedelta(days=index),
        )
        session.add(case)
        session.flush()
        step = CaseStep(
            case_id=case.id,
            case_uuid=case_uuid,
            step_type="step_1_initial",
            step_number=1,
            status="open",
            is_closed=False,
            was_reopened=False,
            template_available=False,
            opened_at=base,
            created_at=base,
            updated_at=base,
        )
        session.add(step)
        session.flush()
        event_type = "case_closed" if index == 0 else "case_opened"
        if index == 0:
            case.status = "closed"
            step.status = "closed_resolved"
            step.is_closed = True
            step.closed_at = base + timedelta(days=index)
        session.add(
            CaseTimelineEventRecord(
                event_uuid=f"10000000-0000-4000-8000-{index:012d}",
                case_id=case.id,
                case_uuid=case_uuid,
                case_step_id=step.id,
                step_type="step_1_initial",
                event_type=event_type,
                event_timestamp=base + timedelta(days=index),
                title=event_type,
                created_at=base,
            )
        )
        session.add(
            CaseReportVersion(
                case_id=case.id,
                version_number=1,
                report_data={},
                report_summary={"primary_issue": f"Issue {index}"},
                created_at=base,
            )
        )
        session.add(
            CaseStepOutcome(
                outcome_uuid=f"20000000-0000-4000-8000-{index:012d}",
                case_id=case.id,
                case_uuid=case_uuid,
                case_step_id=step.id,
                step_type="step_1_initial",
                outcome_type="pending",
                decision_summary=f"Outcome {index}",
                close_step=False,
                close_case=False,
                appeal_to_next_step=False,
                recorded_at=base,
                created_at=base,
            )
        )
    session.commit()
    return engine, session


def test_saved_case_dashboard_paginates_in_database_with_batched_queries():
    engine, session = _session_with_saved_cases()
    statements = []

    def count_statement(*_args):
        statements.append(1)

    event.listen(engine, "before_cursor_execute", count_statement)
    try:
        result = SavedCaseService.list_saved_cases(
            session, newest_first=True, limit=2, offset=1
        )
    finally:
        event.remove(engine, "before_cursor_execute", count_statement)
        session.close()

    assert result.total == 5
    assert [item.title for item in result.cases] == ["Case 3", "Case 2"]
    assert [item.issue_summary for item in result.cases] == ["Issue 3", "Issue 2"]
    assert len(statements) == 4


def test_saved_case_dashboard_applies_status_and_step_filters_before_paging():
    _engine, session = _session_with_saved_cases()
    try:
        result = SavedCaseService.list_saved_cases(
            session,
            status_filter="closed",
            step_filter="step_1_initial",
            limit=10,
        )
    finally:
        session.close()

    assert result.total == 1
    assert result.cases[0].workspace_status == "closed"
    assert result.cases[0].current_step_type == "step_1_initial"
