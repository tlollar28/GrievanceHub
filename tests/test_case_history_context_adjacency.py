"""W6 remediation C: bounded previous/next adjacency for jump_to_context.

The mock-based ``_QueryStub`` convention in test_case_architecture_hardening.py
returns one fixed value per SQLAlchemy model regardless of filter/order_by
arguments, so it cannot distinguish between the 3 distinct
CaseTimelineEventRecord queries jump_to_context now issues (target row,
previous, next) — it can prove call counts but not that the (event_timestamp,
id) comparison logic itself is correct. These tests exercise the real bounded
adjacency queries against PostgreSQL, following the same skip-if-unavailable
convention already established in test_saved_case_service.py.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, ProgrammingError

from app.database.models import CaseTimelineEventRecord, GrievanceCase
from app.database.session import SessionLocal
from app.services.case_history_context_service import CaseHistoryContextService
from app.services.case_service import CaseNotFoundError

SYNTHETIC_CASE_UUID = "00000000-0000-4000-8000-000000000601"
SYNTHETIC_OTHER_CASE_UUID = "00000000-0000-4000-8000-000000000602"


def _db_available() -> bool:
    session = SessionLocal()
    try:
        session.execute(text("SELECT 1"))
        return True
    except OperationalError:
        return False
    finally:
        session.close()


def _tables_ready(session) -> bool:
    try:
        session.query(CaseTimelineEventRecord.id).limit(1).all()
        return True
    except ProgrammingError:
        session.rollback()
        return False


pytestmark = pytest.mark.skipif(
    not _db_available(),
    reason="PostgreSQL database not available for jump_to_context adjacency tests",
)


def _delete_case(session, case_uuid: str) -> None:
    existing = (
        session.query(GrievanceCase)
        .filter(GrievanceCase.case_uuid == case_uuid)
        .first()
    )
    if existing is None:
        return
    session.query(CaseTimelineEventRecord).filter(
        CaseTimelineEventRecord.case_id == existing.id
    ).delete(synchronize_session=False)
    session.delete(existing)
    session.commit()


@pytest.fixture
def db_session():
    session = SessionLocal()
    if not _tables_ready(session):
        session.close()
        pytest.skip("case_timeline_events table not migrated")
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def synthetic_cases(db_session):
    """Two synthetic cases so tests can prove case isolation as well."""
    _delete_case(db_session, SYNTHETIC_CASE_UUID)
    _delete_case(db_session, SYNTHETIC_OTHER_CASE_UUID)

    now = datetime(2026, 7, 6, 9, 0, 0)
    case = GrievanceCase(
        case_uuid=SYNTHETIC_CASE_UUID,
        title="Synthetic adjacency case",
        user_name="Synthetic Steward",
        local_number="300",
        initial_question="Synthetic question for jump-to-context adjacency tests.",
        known_facts={},
        status="open",
        created_at=now,
        updated_at=now,
    )
    other_case = GrievanceCase(
        case_uuid=SYNTHETIC_OTHER_CASE_UUID,
        title="Synthetic other adjacency case",
        user_name="Synthetic Steward",
        local_number="300",
        initial_question="Synthetic other-case question for isolation tests.",
        known_facts={},
        status="open",
        created_at=now,
        updated_at=now,
    )
    db_session.add(case)
    db_session.add(other_case)
    db_session.flush()
    yield case, other_case
    db_session.rollback()


def _add_event(
    db_session,
    case: GrievanceCase,
    *,
    event_timestamp: datetime,
    title: str = "Synthetic event",
    event_type: str = "case_created",
) -> CaseTimelineEventRecord:
    row = CaseTimelineEventRecord(
        event_uuid=str(uuid4()),
        case_id=case.id,
        case_uuid=case.case_uuid,
        event_type=event_type,
        event_timestamp=event_timestamp,
        title=title,
        created_at=event_timestamp,
    )
    db_session.add(row)
    db_session.flush()
    return row


def test_first_event_has_no_previous_but_has_next(db_session, synthetic_cases):
    case, _other = synthetic_cases
    first = _add_event(
        db_session, case, event_timestamp=datetime(2026, 7, 6, 10, 0, 0), title="First"
    )
    second = _add_event(
        db_session, case, event_timestamp=datetime(2026, 7, 6, 11, 0, 0), title="Second"
    )
    _add_event(
        db_session, case, event_timestamp=datetime(2026, 7, 6, 12, 0, 0), title="Third"
    )

    ctx = CaseHistoryContextService(db_session).jump_to_context(
        SYNTHETIC_CASE_UUID, first.event_uuid
    )
    assert ctx.previous_event is None
    assert ctx.next_event is not None
    assert ctx.next_event["event_id"] == second.event_uuid


def test_last_event_has_no_next_but_has_previous(db_session, synthetic_cases):
    case, _other = synthetic_cases
    _add_event(
        db_session, case, event_timestamp=datetime(2026, 7, 6, 10, 0, 0), title="First"
    )
    second = _add_event(
        db_session, case, event_timestamp=datetime(2026, 7, 6, 11, 0, 0), title="Second"
    )
    third = _add_event(
        db_session, case, event_timestamp=datetime(2026, 7, 6, 12, 0, 0), title="Third"
    )

    ctx = CaseHistoryContextService(db_session).jump_to_context(
        SYNTHETIC_CASE_UUID, third.event_uuid
    )
    assert ctx.next_event is None
    assert ctx.previous_event is not None
    assert ctx.previous_event["event_id"] == second.event_uuid


def test_only_event_has_no_previous_or_next(db_session, synthetic_cases):
    case, _other = synthetic_cases
    only = _add_event(
        db_session, case, event_timestamp=datetime(2026, 7, 6, 10, 0, 0), title="Only"
    )

    ctx = CaseHistoryContextService(db_session).jump_to_context(
        SYNTHETIC_CASE_UUID, only.event_uuid
    )
    assert ctx.previous_event is None
    assert ctx.next_event is None


def test_equal_timestamps_break_ties_by_id(db_session, synthetic_cases):
    case, _other = synthetic_cases
    tied_timestamp = datetime(2026, 7, 6, 10, 0, 0)
    first = _add_event(db_session, case, event_timestamp=tied_timestamp, title="Tied A")
    middle = _add_event(db_session, case, event_timestamp=tied_timestamp, title="Tied B")
    last = _add_event(db_session, case, event_timestamp=tied_timestamp, title="Tied C")
    assert first.id < middle.id < last.id

    ctx = CaseHistoryContextService(db_session).jump_to_context(
        SYNTHETIC_CASE_UUID, middle.event_uuid
    )
    assert ctx.previous_event["event_id"] == first.event_uuid
    assert ctx.next_event["event_id"] == last.event_uuid


def test_event_not_found_raises_case_not_found(db_session, synthetic_cases):
    case, _other = synthetic_cases
    _add_event(db_session, case, event_timestamp=datetime(2026, 7, 6, 10, 0, 0))

    with pytest.raises(CaseNotFoundError):
        CaseHistoryContextService(db_session).jump_to_context(
            SYNTHETIC_CASE_UUID, "no-such-event-and-no-such-artifact"
        )


def test_previous_and_next_are_isolated_by_case(db_session, synthetic_cases):
    """An interleaved event on another case must never surface as this
    case's previous/next, even though its timestamp sits in between."""
    case, other_case = synthetic_cases
    target = _add_event(
        db_session, case, event_timestamp=datetime(2026, 7, 6, 10, 0, 0), title="Target"
    )
    later_same_case = _add_event(
        db_session,
        case,
        event_timestamp=datetime(2026, 7, 6, 12, 0, 0),
        title="Later same case",
    )
    _add_event(
        db_session,
        other_case,
        event_timestamp=datetime(2026, 7, 6, 11, 0, 0),
        title="Other case event chronologically between",
    )

    ctx = CaseHistoryContextService(db_session).jump_to_context(
        SYNTHETIC_CASE_UUID, target.event_uuid
    )
    assert ctx.previous_event is None
    assert ctx.next_event is not None
    assert ctx.next_event["event_id"] == later_same_case.event_uuid
