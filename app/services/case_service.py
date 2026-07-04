"""Grievance case session service."""

from __future__ import annotations

import json
from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session, joinedload

from app.database.models import CaseMessage, CaseReportVersion, GrievanceCase
from app.services.analysis_service import AnalysisService
from app.services.knowledge_retrieval_service import KnowledgeRetrievalService


class CaseNotFoundError(Exception):
    pass


class ReportVersionNotFoundError(Exception):
    pass


class CaseReportRequiredError(Exception):
    pass


class CaseService:
    @staticmethod
    def _title_from_question(question: str) -> str:
        normalized = " ".join(question.split())
        return normalized[:80]

    @staticmethod
    def _get_case_row(db: Session, case_uuid: str) -> GrievanceCase | None:
        return (
            db.query(GrievanceCase)
            .filter(GrievanceCase.case_uuid == case_uuid)
            .first()
        )

    @staticmethod
    def create_case(
        db: Session,
        question: str,
        user_name: str | None = None,
        local_number: str | None = None,
        known_facts: dict | None = None,
    ) -> GrievanceCase:
        case = GrievanceCase(
            case_uuid=str(uuid4()),
            title=CaseService._title_from_question(question),
            user_name=user_name,
            local_number=local_number,
            initial_question=question,
            known_facts=known_facts,
            status="open",
        )
        db.add(case)
        db.commit()
        db.refresh(case)
        return case

    @staticmethod
    def get_case(db: Session, case_uuid: str) -> GrievanceCase:
        case = (
            db.query(GrievanceCase)
            .options(
                joinedload(GrievanceCase.messages),
                joinedload(GrievanceCase.report_versions),
            )
            .filter(GrievanceCase.case_uuid == case_uuid)
            .first()
        )
        if case is None:
            raise CaseNotFoundError(case_uuid)
        case.messages.sort(key=lambda m: m.created_at)
        case.report_versions.sort(key=lambda v: v.version_number)
        return case

    @staticmethod
    def list_cases(db: Session, status: str | None = None) -> list[GrievanceCase]:
        query = (
            db.query(GrievanceCase)
            .options(joinedload(GrievanceCase.report_versions))
            .order_by(GrievanceCase.updated_at.desc())
        )
        if status is not None:
            query = query.filter(GrievanceCase.status == status)
        return query.all()

    @staticmethod
    def _normalize_ranked_authorities(ranked_authorities) -> list[dict]:
        if not ranked_authorities:
            return []
        if isinstance(ranked_authorities, list):
            return [item for item in ranked_authorities if isinstance(item, dict)]
        return []

    @staticmethod
    def _format_article_label(authority: dict) -> str:
        doc_type = str(authority.get("document_type") or "").strip().upper()
        article = str(authority.get("article_or_section") or "").strip()
        if not article:
            return doc_type or "Unknown"
        if doc_type:
            return f"{doc_type} {article}"
        return article

    @staticmethod
    def _has_remedy_authority(report_result: dict, ranked_authorities: list[dict]) -> bool:
        for authority in ranked_authorities:
            if authority.get("role") == "remedy_support":
                return True
        report = report_result.get("report") if isinstance(report_result.get("report"), dict) else {}
        remedy_section = report.get("remedy_authority") if isinstance(report, dict) else None
        return bool(remedy_section)

    @staticmethod
    def _has_source_gaps(retrieval_gaps: dict | None) -> bool:
        if not isinstance(retrieval_gaps, dict):
            return False
        return bool(
            retrieval_gaps.get("missing_source_types")
            or retrieval_gaps.get("unindexed_sources_requested")
            or retrieval_gaps.get("authority_topics_unavailable_in_index")
            or retrieval_gaps.get("issues_without_supporting_authority")
            or retrieval_gaps.get("facts_still_needed")
        )

    @staticmethod
    def build_retrieval_gaps_summary(retrieval_gaps: dict | None) -> dict:
        if not isinstance(retrieval_gaps, dict):
            return {
                "has_gaps": False,
                "found_source_types": [],
                "missing_source_types": [],
                "unindexed_sources_requested": [],
            }
        return {
            "has_gaps": CaseService._has_source_gaps(retrieval_gaps),
            "found_source_types": list(retrieval_gaps.get("found_source_types") or []),
            "missing_source_types": list(retrieval_gaps.get("missing_source_types") or []),
            "unindexed_sources_requested": list(
                retrieval_gaps.get("unindexed_sources_requested") or []
            ),
        }

    @staticmethod
    def build_report_summary(
        case: GrievanceCase,
        report_result: dict,
        *,
        message_count: int | None = None,
    ) -> dict:
        ranked_authorities = CaseService._normalize_ranked_authorities(
            report_result.get("ranked_authorities")
        )
        retrieval_gaps = report_result.get("retrieval_gaps")
        if not isinstance(retrieval_gaps, dict):
            retrieval_gaps = {}

        issue_analysis = report_result.get("issue_analysis")
        if not isinstance(issue_analysis, dict):
            issue_analysis = {}

        primary_issue = str(
            issue_analysis.get("primary_issue")
            or case.title
            or case.initial_question
        ).strip()

        source_types_found = sorted(
            {
                str(item.get("document_type")).upper()
                for item in ranked_authorities
                if item.get("document_type")
            }
        )

        articles: list[str] = []
        seen_articles: set[str] = set()
        for authority in ranked_authorities:
            label = CaseService._format_article_label(authority)
            if label not in seen_articles:
                seen_articles.add(label)
                articles.append(label)

        if message_count is None:
            message_count = len(case.messages or [])

        return {
            "primary_issue": primary_issue,
            "articles": articles,
            "source_types_found": source_types_found,
            "authority_count": len(ranked_authorities),
            "has_remedy_authority": CaseService._has_remedy_authority(
                report_result,
                ranked_authorities,
            ),
            "has_source_gaps": CaseService._has_source_gaps(retrieval_gaps),
            "message_count": message_count,
        }

    @staticmethod
    def build_export_metadata(case_uuid: str, version_number: int | None) -> dict:
        version_suffix = f"/versions/{version_number}" if version_number else ""
        base = f"/cases/{case_uuid}{version_suffix}/export"
        return {
            "preview_url": f"{base}/preview",
            "html_url": f"{base}/html",
            "pdf_url": f"{base}/pdf",
        }

    @staticmethod
    def get_case_workspace(db: Session, case_uuid: str) -> dict:
        case = CaseService.get_case(db, case_uuid)
        versions = sorted(case.report_versions, key=lambda v: v.version_number)
        latest = versions[-1] if versions else None

        version_summaries = [
            CaseService.serialize_report_version_summary(version) for version in versions
        ]

        workspace = {
            "case_uuid": case.case_uuid,
            "title": case.title,
            "user_name": case.user_name,
            "local_number": case.local_number,
            "initial_question": case.initial_question,
            "known_facts": case.known_facts,
            "status": case.status,
            "created_at": case.created_at.isoformat() if case.created_at else None,
            "updated_at": case.updated_at.isoformat() if case.updated_at else None,
            "messages": [
                {
                    "id": message.id,
                    "role": message.role,
                    "content": message.content,
                    "metadata": message.message_metadata,
                    "created_at": message.created_at.isoformat()
                    if message.created_at
                    else None,
                }
                for message in sorted(case.messages, key=lambda m: m.created_at)
            ],
            "report_versions": version_summaries,
            "latest_report_version": latest.version_number if latest else None,
            "latest_report": CaseService.serialize_report_version_summary(latest)
            if latest
            else None,
            "retrieval_gaps": latest.retrieval_gaps if latest else None,
            "source_coverage_audit": latest.source_coverage_audit if latest else None,
            "report_summary": latest.report_summary if latest else None,
            "retrieval_gaps_summary": CaseService.build_retrieval_gaps_summary(
                latest.retrieval_gaps if latest else None
            ),
            "exports": CaseService.build_export_metadata(
                case.case_uuid,
                latest.version_number if latest else None,
            ),
        }
        return workspace

    @staticmethod
    def serialize_report_version_summary(version: CaseReportVersion | None) -> dict | None:
        if version is None:
            return None
        return {
            "id": version.id,
            "version_number": version.version_number,
            "trigger_message_id": version.trigger_message_id,
            "created_at": version.created_at.isoformat() if version.created_at else None,
            "ranked_authorities": version.ranked_authorities,
            "issue_analysis": version.issue_analysis,
            "evidence_items": version.evidence_items,
            "retrieval_gaps": version.retrieval_gaps,
            "source_coverage_audit": version.source_coverage_audit,
            "report_summary": version.report_summary,
        }

    @staticmethod
    def serialize_case_list_summary(case: GrievanceCase) -> dict:
        latest_version = None
        if case.report_versions:
            latest_version = max(case.report_versions, key=lambda v: v.version_number)

        summary = {
            "case_uuid": case.case_uuid,
            "title": case.title,
            "user_name": case.user_name,
            "local_number": case.local_number,
            "initial_question": case.initial_question,
            "known_facts": case.known_facts,
            "status": case.status,
            "created_at": case.created_at.isoformat() if case.created_at else None,
            "updated_at": case.updated_at.isoformat() if case.updated_at else None,
            "latest_report_version": latest_version.version_number if latest_version else None,
            "report_summary": latest_version.report_summary if latest_version else None,
            "retrieval_gaps_summary": CaseService.build_retrieval_gaps_summary(
                latest_version.retrieval_gaps if latest_version else None
            ),
        }
        return summary

    @staticmethod
    def add_message(
        db: Session,
        case_uuid: str,
        role: str,
        content: str,
        metadata: dict | None = None,
    ) -> CaseMessage:
        case = CaseService._get_case_row(db, case_uuid)
        if case is None:
            raise CaseNotFoundError(case_uuid)

        message = CaseMessage(
            case_id=case.id,
            role=role,
            content=content,
            message_metadata=metadata,
        )
        db.add(message)
        case.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(message)
        return message

    @staticmethod
    def update_known_facts(db: Session, case_uuid: str, facts: dict) -> GrievanceCase:
        case = CaseService._get_case_row(db, case_uuid)
        if case is None:
            raise CaseNotFoundError(case_uuid)
        case.known_facts = facts
        case.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(case)
        return case

    @staticmethod
    def close_case(db: Session, case_uuid: str) -> GrievanceCase:
        case = CaseService._get_case_row(db, case_uuid)
        if case is None:
            raise CaseNotFoundError(case_uuid)
        case.status = "closed"
        case.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(case)
        return case

    @staticmethod
    def reopen_case(db: Session, case_uuid: str) -> GrievanceCase:
        case = CaseService._get_case_row(db, case_uuid)
        if case is None:
            raise CaseNotFoundError(case_uuid)
        case.status = "open"
        case.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(case)
        return case

    @staticmethod
    def _collect_upload_metadata(case: GrievanceCase) -> list[dict]:
        uploads: list[dict] = []
        for message in case.messages or []:
            meta = message.message_metadata or {}
            if isinstance(meta.get("uploaded_files"), list):
                uploads.extend(meta["uploaded_files"])
            elif meta.get("filename") or meta.get("file_id") or meta.get("file"):
                uploads.append(meta)
        return uploads

    @staticmethod
    def build_case_context(case: GrievanceCase) -> dict:
        messages = sorted(case.messages or [], key=lambda m: m.created_at)
        return {
            "case_id": case.case_uuid,
            "case_title": case.title,
            "user_name": case.user_name,
            "local_number": case.local_number,
            "initial_question": case.initial_question,
            "known_facts": case.known_facts or {},
            "status": case.status,
            "messages": [
                {
                    "role": message.role,
                    "content": message.content,
                    "metadata": message.message_metadata,
                    "created_at": message.created_at.isoformat()
                    if message.created_at
                    else None,
                }
                for message in messages
            ],
            "uploaded_files": CaseService._collect_upload_metadata(case),
        }

    @staticmethod
    def build_analysis_question(case: GrievanceCase) -> str:
        lines = [f"Initial question: {case.initial_question}"]
        for message in sorted(case.messages or [], key=lambda m: m.created_at):
            lines.append(f"{message.role}: {message.content}")
        if case.known_facts:
            lines.append(f"Known facts: {json.dumps(case.known_facts, sort_keys=True)}")
        return "\n".join(lines)

    @staticmethod
    def generate_report_version(
        db: Session,
        case_uuid: str,
        limit_per_source: int = 8,
        trigger_message_id: int | None = None,
    ) -> CaseReportVersion:
        case = CaseService.get_case(db, case_uuid)
        analysis_question = CaseService.build_analysis_question(case)
        case_context = CaseService.build_case_context(case)

        results = KnowledgeRetrievalService.search_all(
            db=db,
            query=analysis_question,
            limit_per_source=limit_per_source,
            known_facts=case.known_facts,
        )

        known_facts_list = None
        if case.known_facts:
            if isinstance(case.known_facts, dict):
                known_facts_list = [f"{k}: {v}" for k, v in case.known_facts.items()]
            elif isinstance(case.known_facts, list):
                known_facts_list = case.known_facts

        report_result = AnalysisService.generate_report(
            question=analysis_question,
            chunks=results["all_chunks"],
            issue_analysis=results.get("issue_analysis"),
            issue_keywords=results.get("issue_keywords"),
            case_context=case_context,
            known_facts=known_facts_list,
            all_chunks=results.get("all_chunks"),
            retrieval_gaps_list=results.get("retrieval_gaps"),
            indexed_source_types=results.get("indexed_source_types"),
            source_coverage_audit=results.get("source_coverage_audit"),
        )

        next_version = 1
        if case.report_versions:
            next_version = max(v.version_number for v in case.report_versions) + 1

        report_data = report_result.get("report") or report_result
        evidence_items = None
        if isinstance(report_data, dict):
            evidence_items = report_data.get("supporting_evidence")

        retrieval_gaps = report_result.get("retrieval_gaps")
        if not isinstance(retrieval_gaps, dict):
            retrieval_gaps = {}

        source_coverage_audit = retrieval_gaps.get("source_coverage_audit")
        if source_coverage_audit is None:
            source_coverage_audit = results.get("source_coverage_audit")

        report_summary = CaseService.build_report_summary(
            case,
            report_result,
            message_count=len(case.messages or []),
        )

        version = CaseReportVersion(
            case_id=case.id,
            version_number=next_version,
            trigger_message_id=trigger_message_id,
            report_data=report_result,
            ranked_authorities=report_result.get("ranked_authorities"),
            issue_analysis=report_result.get("issue_analysis"),
            evidence_items=evidence_items,
            retrieval_gaps=retrieval_gaps,
            source_coverage_audit=source_coverage_audit,
            report_summary=report_summary,
        )
        db.add(version)
        case.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(version)
        return version

    @staticmethod
    def list_report_versions(db: Session, case_uuid: str) -> list[CaseReportVersion]:
        case = CaseService.get_case(db, case_uuid)
        return list(case.report_versions)

    @staticmethod
    def get_report_version(
        db: Session,
        case_uuid: str,
        version_number: int,
    ) -> CaseReportVersion:
        case = CaseService.get_case(db, case_uuid)
        for version in case.report_versions:
            if version.version_number == version_number:
                return version
        raise ReportVersionNotFoundError(version_number)

    @staticmethod
    def get_grounding_report_version(
        case: GrievanceCase,
        version_number: int | None = None,
    ) -> CaseReportVersion:
        if not case.report_versions:
            raise CaseReportRequiredError("Case has no saved report version")
        if version_number is None:
            return max(case.report_versions, key=lambda v: v.version_number)
        for version in case.report_versions:
            if version.version_number == version_number:
                return version
        raise ReportVersionNotFoundError(version_number)

    @staticmethod
    def is_follow_up_message(message: CaseMessage) -> bool:
        meta = message.message_metadata or {}
        return meta.get("intent") == "follow_up"

    @staticmethod
    def serialize_message(message: CaseMessage) -> dict:
        return {
            "id": message.id,
            "role": message.role,
            "content": message.content,
            "metadata": message.message_metadata,
            "created_at": message.created_at.isoformat() if message.created_at else None,
        }

    @staticmethod
    def list_follow_up_messages(case: GrievanceCase) -> list[CaseMessage]:
        return [
            message
            for message in sorted(case.messages or [], key=lambda m: m.created_at)
            if CaseService.is_follow_up_message(message)
            or (
                message.role == "assistant"
                and isinstance(message.message_metadata, dict)
                and message.message_metadata.get("answer_type")
            )
        ]

    @staticmethod
    def add_follow_up_exchange(
        db: Session,
        case_uuid: str,
        question: str,
        answer,
        report_version: CaseReportVersion,
    ) -> tuple[CaseMessage, CaseMessage]:
        case = CaseService._get_case_row(db, case_uuid)
        if case is None:
            raise CaseNotFoundError(case_uuid)

        user_metadata = {
            "intent": "follow_up",
            "linked_report_version_id": report_version.id,
            "linked_report_version_number": report_version.version_number,
        }
        user_message = CaseMessage(
            case_id=case.id,
            role="user",
            content=question,
            message_metadata=user_metadata,
        )
        db.add(user_message)
        db.flush()

        assistant_metadata = {
            "intent": "follow_up",
            "linked_report_version_id": report_version.id,
            "linked_report_version_number": report_version.version_number,
            "answer_type": answer.answer_type,
            "citations": [c.model_dump() for c in answer.citations],
            "disclosures": answer.disclosures,
            "facts_needed": answer.facts_needed,
            "requires_report_regen": answer.requires_report_regen,
            "suggested_actions": answer.suggested_actions,
        }
        assistant_message = CaseMessage(
            case_id=case.id,
            role="assistant",
            content=answer.answer,
            message_metadata=assistant_metadata,
        )
        db.add(assistant_message)
        case.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user_message)
        db.refresh(assistant_message)
        return user_message, assistant_message
