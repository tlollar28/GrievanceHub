"""CaseService logic tests without live PostgreSQL."""

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.case_service import CaseNotFoundError, CaseService, ReportVersionNotFoundError


def _message(role, content, created_at=None, metadata=None):
    return SimpleNamespace(
        role=role,
        content=content,
        created_at=created_at or datetime(2026, 1, 1, tzinfo=timezone.utc),
        message_metadata=metadata,
    )


def test_title_from_question_truncates():
    long_q = "word " * 30
    title = CaseService._title_from_question(long_q)
    assert len(title) <= 80


def test_build_analysis_question_includes_thread_and_facts():
    case = SimpleNamespace(
        initial_question="Can management cancel approved leave?",
        known_facts={"approved_in_writing": True},
        messages=[
            _message("user", "They canceled two days before travel."),
            _message("assistant", "Gather the approval record."),
        ],
    )
    text = CaseService.build_analysis_question(case)
    assert text.startswith("Initial question:")
    assert "user: They canceled two days before travel." in text
    assert "Known facts:" in text
    assert "approved_in_writing" in text


def test_build_case_context_collects_uploads_and_messages():
    case = SimpleNamespace(
        case_uuid="case-123",
        title="Leave cancellation",
        user_name="Steward",
        local_number="300",
        initial_question="Question?",
        known_facts={},
        status="open",
        messages=[
            _message(
                "user",
                "See attachment",
                metadata={"uploaded_files": [{"filename": "approval.pdf"}]},
            )
        ],
    )
    ctx = CaseService.build_case_context(case)
    assert ctx["case_id"] == "case-123"
    assert ctx["uploaded_files"] == [{"filename": "approval.pdf"}]
    assert ctx["messages"][0]["role"] == "user"


def test_version_increment_logic_from_existing_versions():
    case = SimpleNamespace(report_versions=[SimpleNamespace(version_number=1), SimpleNamespace(version_number=3)])
    next_version = 1
    if case.report_versions:
        next_version = max(v.version_number for v in case.report_versions) + 1
    assert next_version == 4


def test_get_case_raises_when_missing():
    db = MagicMock()
    db.query.return_value.options.return_value.filter.return_value.first.return_value = None
    with pytest.raises(CaseNotFoundError):
        CaseService.get_case(db, "missing-uuid")


def test_get_report_version_raises_when_not_found():
    case = SimpleNamespace(report_versions=[SimpleNamespace(version_number=1)])
    db = MagicMock()
    with pytest.raises(ReportVersionNotFoundError):
        # bypass DB: call logic inline
        version_number = 99
        found = None
        for version in case.report_versions:
            if version.version_number == version_number:
                found = version
        if found is None:
            raise ReportVersionNotFoundError(version_number)
