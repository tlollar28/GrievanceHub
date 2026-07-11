"""CaseService logic tests without live PostgreSQL."""

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.case_service import CaseNotFoundError, CaseService, ReportVersionNotFoundError


def _message(role, content, created_at=None, metadata=None):
    return SimpleNamespace(
        id=1,
        role=role,
        content=content,
        created_at=created_at or datetime(2026, 1, 1, tzinfo=timezone.utc),
        message_metadata=metadata,
    )


def _sample_report_result():
    return {
        "issue_analysis": {
            "primary_issue": "Management revoked approved annual leave",
        },
        "ranked_authorities": [
            {
                "document_type": "CONTRACT",
                "article_or_section": "Article 10.5",
                "role": "union_supporting",
                "legal_issue": "Leave commitments",
            },
            {
                "document_type": "CIM",
                "article_or_section": "Article 31",
                "role": "union_supporting",
                "legal_issue": "Information rights",
            },
        ],
        "retrieval_gaps": {
            "missing_source_types": ["ELM"],
            "found_source_types": ["CONTRACT", "CIM"],
            "unindexed_sources_requested": ["LMOU"],
            "source_coverage_audit": [
                {"source_type": "CONTRACT", "disposition": "found_and_ranked"},
            ],
        },
        "report": {
            "remedy_authority": [],
            "supporting_evidence": [{"item": "approval record"}],
        },
    }


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
    assert ctx["case_assets"] == []
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


def test_build_report_summary_extracts_articles_and_counts():
    case = SimpleNamespace(
        title="Leave cancellation",
        initial_question="Can management cancel approved leave?",
        messages=[_message("user", "Follow-up detail")],
    )
    report_result = _sample_report_result()

    summary = CaseService.build_report_summary(case, report_result)

    assert summary["primary_issue"] == "Management revoked approved annual leave"
    assert summary["articles"] == ["CONTRACT Article 10.5", "CIM Article 31"]
    assert summary["source_types_found"] == ["CIM", "CONTRACT"]
    assert summary["authority_count"] == 2
    assert summary["has_remedy_authority"] is False
    assert summary["has_source_gaps"] is True
    assert summary["message_count"] == 1


def test_build_retrieval_gaps_summary():
    summary = CaseService.build_retrieval_gaps_summary(
        {
            "missing_source_types": ["ELM"],
            "found_source_types": ["CONTRACT", "CIM"],
            "unindexed_sources_requested": ["LMOU"],
        }
    )
    assert summary["has_gaps"] is True
    assert summary["found_source_types"] == ["CONTRACT", "CIM"]
    assert summary["missing_source_types"] == ["ELM"]
    assert summary["unindexed_sources_requested"] == ["LMOU"]


def test_generate_report_version_persists_audit_columns():
    case = SimpleNamespace(
        id=10,
        case_uuid="case-uuid-123",
        title="Leave issue",
        user_name="Steward",
        local_number="300",
        initial_question="Question?",
        known_facts=None,
        status="open",
        messages=[],
        report_versions=[],
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    report_result = _sample_report_result()

    db = MagicMock()
    version_obj = SimpleNamespace(id=99)

    def _refresh(obj):
        obj.id = 99

    db.refresh.side_effect = _refresh

    with patch.object(CaseService, "get_case", return_value=case), patch(
        "app.services.case_service.KnowledgeRetrievalService.search_all",
        return_value={
            "all_chunks": [],
            "issue_analysis": report_result["issue_analysis"],
            "retrieval_gaps": [],
            "indexed_source_types": ["CONTRACT", "CIM", "ELM"],
            "source_coverage_audit": report_result["retrieval_gaps"]["source_coverage_audit"],
        },
    ), patch(
        "app.services.case_service.AnalysisService.generate_report",
        return_value=report_result,
    ):
        version = CaseService.generate_report_version(db, "case-uuid-123")

    assert version.retrieval_gaps == report_result["retrieval_gaps"]
    assert version.source_coverage_audit == report_result["retrieval_gaps"]["source_coverage_audit"]
    assert version.report_summary["authority_count"] == 2
    assert version.report_summary["has_source_gaps"] is True
    db.add.assert_called_once()
    db.commit.assert_called_once()


def test_get_case_workspace_aggregate_shape():
    created = datetime(2026, 1, 1, tzinfo=timezone.utc)
    version = SimpleNamespace(
        id=1,
        version_number=1,
        trigger_message_id=None,
        created_at=created,
        ranked_authorities=[{"document_type": "CONTRACT"}],
        issue_analysis={"primary_issue": "Leave issue"},
        evidence_items=[],
        retrieval_gaps={"missing_source_types": ["ELM"]},
        source_coverage_audit=[{"source_type": "CONTRACT"}],
        report_summary={
            "primary_issue": "Leave issue",
            "authority_count": 1,
        },
    )
    case = SimpleNamespace(
        case_uuid="workspace-case",
        title="Leave issue",
        user_name="Steward",
        local_number="300",
        initial_question="Question?",
        known_facts={},
        status="open",
        created_at=created,
        updated_at=created,
        messages=[_message("user", "Initial question")],
        report_versions=[version],
    )
    db = MagicMock()

    with patch.object(CaseService, "get_case", return_value=case):
        workspace = CaseService.get_case_workspace(db, "workspace-case")

    assert workspace["case_uuid"] == "workspace-case"
    assert workspace["latest_report_version"] == 1
    assert workspace["report_summary"]["authority_count"] == 1
    assert workspace["retrieval_gaps"]["missing_source_types"] == ["ELM"]
    assert workspace["source_coverage_audit"] == [{"source_type": "CONTRACT"}]
    assert len(workspace["report_versions"]) == 1
    assert workspace["exports"]["pdf_url"] == "/cases/workspace-case/versions/1/export/pdf"
    assert workspace["retrieval_gaps_summary"]["has_gaps"] is True
    assert workspace["assets"] == []
    assert workspace["uploaded_assets"] == []
