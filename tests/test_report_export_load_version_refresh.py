"""Regression: export must see report versions flushed in the same transaction."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services import report_export_service
from app.services.case_service import CaseService, ReportVersionNotFoundError
from app.services.report_export_service import NoReportVersionError, _load_version


def test_load_version_expires_stale_relationship_before_lookup(monkeypatch):
    stale_v1 = SimpleNamespace(version_number=1, report_data={"a": 1})
    fresh_v2 = SimpleNamespace(version_number=2, report_data={"b": 2})
    case = SimpleNamespace(
        case_uuid="case-export-1",
        report_versions=[stale_v1],  # stale collection missing v2
    )
    db = MagicMock()
    expired = {}

    def _expire(obj, attrs):
        expired["obj"] = obj
        expired["attrs"] = attrs
        # Simulate SQLAlchemy reload after expire.
        obj.report_versions = [stale_v1, fresh_v2]

    db.expire.side_effect = _expire
    monkeypatch.setattr(CaseService, "get_case", lambda _db, _uuid: case)

    loaded = _load_version(db, "case-export-1", 2)
    assert loaded is fresh_v2
    assert expired["obj"] is case
    assert expired["attrs"] == ["report_versions"]


def test_load_version_still_raises_when_missing_after_refresh(monkeypatch):
    case = SimpleNamespace(case_uuid="case-export-2", report_versions=[])
    db = MagicMock()
    db.expire.side_effect = lambda obj, attrs: setattr(obj, "report_versions", [])
    monkeypatch.setattr(CaseService, "get_case", lambda _db, _uuid: case)

    with pytest.raises(NoReportVersionError):
        _load_version(db, "case-export-2", None)

    case.report_versions = [SimpleNamespace(version_number=1, report_data={})]
    db.expire.side_effect = lambda obj, attrs: None
    with pytest.raises(ReportVersionNotFoundError):
        _load_version(db, "case-export-2", 9)


def test_module_exports_load_helper():
    assert callable(report_export_service._load_version)
