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
        query = db.query(GrievanceCase).order_by(GrievanceCase.updated_at.desc())
        if status is not None:
            query = query.filter(GrievanceCase.status == status)
        return query.all()

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
        )

        next_version = 1
        if case.report_versions:
            next_version = max(v.version_number for v in case.report_versions) + 1

        report_data = report_result.get("report") or report_result
        evidence_items = None
        if isinstance(report_data, dict):
            evidence_items = report_data.get("supporting_evidence")

        version = CaseReportVersion(
            case_id=case.id,
            version_number=next_version,
            trigger_message_id=trigger_message_id,
            report_data=report_result,
            ranked_authorities=report_result.get("ranked_authorities"),
            issue_analysis=report_result.get("issue_analysis"),
            evidence_items=evidence_items,
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
