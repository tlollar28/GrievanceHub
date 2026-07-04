"""Follow-up Q&A grounded in saved GrievanceHub case reports."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Callable

from dotenv import load_dotenv
from openai import OpenAI
from sqlalchemy.orm import Session

from app.database.models import CaseMessage, CaseReportVersion, GrievanceCase
from app.schemas.follow_up_schema import FollowUpAnswerPayload, FollowUpCitation
from app.services.case_service import (
    CaseReportRequiredError,
    CaseService,
    ReportVersionNotFoundError,
)
from app.services.relevance_utils import verify_quote_in_chunk

load_dotenv()

FOLLOW_UP_INTENT = "follow_up"

AUTHORITY_SECTION_KEYS = (
    "key_contract_violations",
    "union_supporting_authority",
    "procedural_requirements",
    "information_rights",
    "timeline_requirements",
    "remedy_authority",
    "management_limiting_authority",
    "background_authority",
)

INDEXED_SOURCE_TYPES = ["CONTRACT", "CIM", "ELM"]
UNINDEXED_SOURCE_DISCLOSURES = ["LMOU"]

ALLOWED_ANSWER_TYPES = {
    "fact",
    "argument",
    "citation",
    "remedy",
    "procedural",
    "uncertainty",
    "action",
    "missing_evidence",
}

NEW_FACT_SIGNALS = (
    "actually ",
    "just learned",
    "new fact",
    "new information",
    "also happened",
    "also suspended",
    "yesterday management",
    "recently management",
)


class FollowUpChatService:
    @staticmethod
    def _client() -> OpenAI:
        return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    @staticmethod
    def _report_root(report_version: CaseReportVersion) -> dict:
        report_data = report_version.report_data or {}
        if isinstance(report_data.get("report"), dict):
            return report_data["report"]
        return report_data if isinstance(report_data, dict) else {}

    @staticmethod
    def _wrapper_data(report_version: CaseReportVersion) -> dict:
        report_data = report_version.report_data or {}
        return report_data if isinstance(report_data, dict) else {}

    @staticmethod
    def _authority_items(report: dict, key: str) -> list[dict]:
        section = report.get(key)
        if isinstance(section, list):
            return [item for item in section if isinstance(item, dict)]
        return []

    @staticmethod
    def _collect_saved_quotes(report_version: CaseReportVersion) -> list[str]:
        quotes: list[str] = []
        report = FollowUpChatService._report_root(report_version)
        wrapper = FollowUpChatService._wrapper_data(report_version)

        for key in AUTHORITY_SECTION_KEYS:
            for item in FollowUpChatService._authority_items(report, key):
                quote = str(item.get("direct_quote") or "").strip()
                if quote:
                    quotes.append(quote)

        for item in report.get("supporting_evidence") or []:
            if isinstance(item, dict):
                quote = str(item.get("direct_quote") or "").strip()
                if quote:
                    quotes.append(quote)

        for item in wrapper.get("ranked_authorities") or report_version.ranked_authorities or []:
            if isinstance(item, dict):
                quote = str(item.get("direct_quote") or "").strip()
                if quote:
                    quotes.append(quote)

        return quotes

    @staticmethod
    def _serialize_authority(item: dict) -> dict:
        citation = item.get("citation") if isinstance(item.get("citation"), dict) else {}
        return {
            "article_or_section": item.get("article_or_section"),
            "issue": item.get("issue") or item.get("legal_issue"),
            "role": item.get("role"),
            "direct_quote": item.get("direct_quote"),
            "document_type": citation.get("document_type") or item.get("document_type"),
            "document_name": citation.get("document_name") or item.get("document_name"),
            "page": citation.get("page") if citation.get("page") is not None else item.get("page"),
        }

    @staticmethod
    def _prior_followups(case: GrievanceCase) -> list[dict]:
        thread: list[dict] = []
        for message in sorted(case.messages or [], key=lambda m: m.created_at):
            meta = message.message_metadata or {}
            if meta.get("intent") != FOLLOW_UP_INTENT:
                continue
            thread.append(
                {
                    "role": message.role,
                    "content": message.content,
                    "metadata": meta,
                }
            )
        return thread

    @staticmethod
    def build_grounding_package(
        case: GrievanceCase,
        report_version: CaseReportVersion,
    ) -> dict[str, Any]:
        report = FollowUpChatService._report_root(report_version)
        wrapper = FollowUpChatService._wrapper_data(report_version)
        retrieval_gaps = report_version.retrieval_gaps
        if not isinstance(retrieval_gaps, dict):
            retrieval_gaps = wrapper.get("retrieval_gaps") or {}
            if not isinstance(retrieval_gaps, dict):
                retrieval_gaps = {}
            limitations = report.get("limitations")
            if isinstance(limitations, dict) and isinstance(limitations.get("retrieval_gaps"), dict):
                retrieval_gaps = {**retrieval_gaps, **limitations["retrieval_gaps"]}

        source_coverage_audit = report_version.source_coverage_audit
        if source_coverage_audit is None:
            source_coverage_audit = retrieval_gaps.get("source_coverage_audit") or []

        report_summary = report_version.report_summary or {}
        if not report_summary:
            report_summary = CaseService.build_report_summary(case, wrapper)

        authority_sections = {
            key: [
                FollowUpChatService._serialize_authority(item)
                for item in FollowUpChatService._authority_items(report, key)
            ]
            for key in AUTHORITY_SECTION_KEYS
        }

        detailed = report.get("detailed_analysis") if isinstance(report.get("detailed_analysis"), dict) else {}
        limitations = report.get("limitations") if isinstance(report.get("limitations"), dict) else {}

        return {
            "case_uuid": case.case_uuid,
            "report_version_number": report_version.version_number,
            "report_version_id": report_version.id,
            "initial_question": case.initial_question,
            "known_facts": case.known_facts or {},
            "uploaded_files": CaseService.build_case_context(case).get("uploaded_files") or [],
            "report_summary": report_summary,
            "retrieval_gaps": retrieval_gaps,
            "source_coverage_audit": source_coverage_audit,
            "quick_assessment": report.get("quick_assessment") or {},
            "key_violations": authority_sections.get("key_contract_violations") or [],
            "authority_sections": authority_sections,
            "recommended_remedy": report.get("recommended_remedy") or {},
            "evidence_to_gather": detailed.get("evidence_to_gather") or [],
            "limitations_caveats": limitations.get("caveats") or [],
            "facts_still_needed": retrieval_gaps.get("facts_still_needed")
            or limitations.get("missing_facts")
            or [],
            "issue_analysis": report_version.issue_analysis or wrapper.get("issue_analysis") or {},
            "evidence_items": report_version.evidence_items
            or report.get("supporting_evidence")
            or [],
            "prior_followups": FollowUpChatService._prior_followups(case),
            "saved_quotes": FollowUpChatService._collect_saved_quotes(report_version),
            "indexed_source_types_available": INDEXED_SOURCE_TYPES,
            "unindexed_sources_disclosed": list(
                retrieval_gaps.get("unindexed_sources_requested") or UNINDEXED_SOURCE_DISCLOSURES
            ),
        }

    @staticmethod
    def validate_citations(
        citations: list[dict],
        grounding: dict[str, Any],
    ) -> list[FollowUpCitation]:
        saved_quotes = grounding.get("saved_quotes") or []
        validated: list[FollowUpCitation] = []

        for raw in citations or []:
            if not isinstance(raw, dict):
                continue
            quote = str(raw.get("quote") or "").strip()
            grounded = False
            if quote:
                for saved in saved_quotes:
                    if verify_quote_in_chunk(quote, saved) or verify_quote_in_chunk(saved, quote):
                        grounded = True
                        break
            citation = FollowUpCitation(
                document_type=str(raw.get("document_type") or "").upper(),
                document_name=str(raw.get("document_name") or ""),
                article_or_section=str(raw.get("article_or_section") or ""),
                page=raw.get("page"),
                quote=quote,
                grounded=grounded if quote else False,
            )
            validated.append(citation)

        return validated

    @staticmethod
    def detect_requires_report_regen(question: str, grounding: dict[str, Any]) -> bool:
        lowered = question.lower()
        for signal in NEW_FACT_SIGNALS:
            if signal in lowered:
                return True

        known_blob = json.dumps(
            {
                "known_facts": grounding.get("known_facts") or {},
                "initial_question": grounding.get("initial_question") or "",
                "prior_followups": grounding.get("prior_followups") or [],
            },
            sort_keys=True,
        ).lower()

        date_patterns = re.findall(r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]* \d{1,2}\b", lowered)
        for token in date_patterns:
            if token not in known_blob:
                return True

        return False

    @staticmethod
    def build_system_prompt() -> str:
        return (
            "You are GrievanceHub follow-up assistant for NPMHU stewards. "
            "Ground every answer in the provided CASE_CONTEXT JSON only. "
            "Never invent grievant names, dates, management actions, or source passages. "
            "When contractual or manual claims rely on saved authorities, include citations with "
            "verbatim quotes copied from CASE_CONTEXT saved authorities. "
            "Separate National Agreement (CONTRACT), CIM, ELM, and LMOU citations — never merge them. "
            "If LMOU or other sources are not indexed, disclose that honestly. "
            "If remedy authority is absent in the saved report, say so and label practical relief as proposed. "
            "Ask for missing facts instead of inventing them. Brand as GrievanceHub only — never CREA. "
            "Use 'the steward' in product-facing wording. Return JSON only."
        )

    @staticmethod
    def build_user_prompt(question: str, grounding: dict[str, Any]) -> str:
        context_json = json.dumps(grounding, indent=2, default=str)
        return (
            f"CASE_CONTEXT:\n{context_json}\n\n"
            f"STEWARD FOLLOW-UP QUESTION:\n{question}\n\n"
            "Return JSON exactly like:\n"
            "{\n"
            '  "answer": "plain-language answer for the steward",\n'
            '  "answer_type": "fact|argument|citation|remedy|procedural|uncertainty|action|missing_evidence",\n'
            '  "citations": [\n'
            "    {\n"
            '      "document_type": "CONTRACT",\n'
            '      "document_name": "2022-2025 NPMHU National Agreement",\n'
            '      "article_or_section": "Article 10.5",\n'
            '      "page": 44,\n'
            '      "quote": "verbatim quote from CASE_CONTEXT only"\n'
            "    }\n"
            "  ],\n"
            '  "disclosures": ["honest source or evidence gaps"],\n'
            '  "facts_needed": ["missing facts the steward should obtain"],\n'
            '  "requires_report_regen": false,\n'
            '  "suggested_actions": ["regenerate_report"]\n'
            "}"
        )

    @staticmethod
    def _parse_llm_payload(content: str) -> dict[str, Any]:
        data = json.loads(content)
        if not isinstance(data, dict):
            raise ValueError("Follow-up LLM response must be a JSON object")
        return data

    @staticmethod
    def call_llm(question: str, grounding: dict[str, Any]) -> dict[str, Any]:
        client = FollowUpChatService._client()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": FollowUpChatService.build_system_prompt()},
                {
                    "role": "user",
                    "content": FollowUpChatService.build_user_prompt(question, grounding),
                },
            ],
        )
        return FollowUpChatService._parse_llm_payload(response.choices[0].message.content)

    @staticmethod
    def generate_answer(
        question: str,
        grounding: dict[str, Any],
        *,
        llm_callable: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None,
    ) -> FollowUpAnswerPayload:
        caller = llm_callable or FollowUpChatService.call_llm
        raw = caller(question, grounding)

        citations = FollowUpChatService.validate_citations(
            raw.get("citations") or [],
            grounding,
        )

        disclosures = [
            str(item).strip()
            for item in (raw.get("disclosures") or [])
            if str(item).strip()
        ]
        facts_needed = [
            str(item).strip()
            for item in (raw.get("facts_needed") or [])
            if str(item).strip()
        ]

        requires_regen = bool(raw.get("requires_report_regen"))
        if FollowUpChatService.detect_requires_report_regen(question, grounding):
            requires_regen = True

        suggested_actions = [
            str(item).strip()
            for item in (raw.get("suggested_actions") or [])
            if str(item).strip()
        ]
        if requires_regen and "regenerate_report" not in suggested_actions:
            suggested_actions.append("regenerate_report")

        ungrounded = [c for c in citations if c.quote and not c.grounded]
        if ungrounded:
            disclosures.append(
                "One or more cited quotes could not be verified against the saved report excerpts."
            )

        if grounding.get("report_summary", {}).get("has_remedy_authority") is False:
            if any(token in question.lower() for token in ("remedy", "relief", "request")):
                disclosures.append(
                    "The saved report does not contain explicit remedy authority above relevance gates."
                )

        unindexed = grounding.get("unindexed_sources_disclosed") or []
        if unindexed and any(src.lower() in question.lower() for src in unindexed):
            disclosures.append(
                f"{', '.join(unindexed)} is referenced but not currently indexed in GrievanceHub."
            )

        answer_type = str(raw.get("answer_type") or "fact")
        if answer_type not in ALLOWED_ANSWER_TYPES:
            answer_type = "fact"

        return FollowUpAnswerPayload(
            answer=str(raw.get("answer") or "").strip(),
            answer_type=answer_type,
            citations=citations,
            disclosures=sorted(set(disclosures)),
            facts_needed=facts_needed,
            requires_report_regen=requires_regen,
            suggested_actions=suggested_actions,
        )

    @staticmethod
    def answer_follow_up(
        db: Session,
        case_uuid: str,
        content: str,
        report_version_number: int | None = None,
        *,
        llm_callable: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        case = CaseService.get_case(db, case_uuid)
        try:
            report_version = CaseService.get_grounding_report_version(case, report_version_number)
        except ReportVersionNotFoundError as exc:
            raise exc

        if not report_version.report_data:
            raise CaseReportRequiredError("Saved report version has no report_data")

        grounding = FollowUpChatService.build_grounding_package(case, report_version)
        answer = FollowUpChatService.generate_answer(
            content,
            grounding,
            llm_callable=llm_callable,
        )

        user_message, assistant_message = CaseService.add_follow_up_exchange(
            db=db,
            case_uuid=case_uuid,
            question=content,
            answer=answer,
            report_version=report_version,
        )

        return {
            "user_message": user_message,
            "assistant_message": assistant_message,
            "answer": answer.answer,
            "answer_type": answer.answer_type,
            "citations": [c.model_dump() for c in answer.citations],
            "disclosures": answer.disclosures,
            "facts_needed": answer.facts_needed,
            "linked_report_version": {
                "id": report_version.id,
                "version_number": report_version.version_number,
            },
            "requires_report_regen": answer.requires_report_regen,
            "suggested_actions": answer.suggested_actions,
        }

    @staticmethod
    def list_follow_up_thread(db: Session, case_uuid: str) -> dict[str, Any]:
        case = CaseService.get_case(db, case_uuid)
        messages = CaseService.list_follow_up_messages(case)
        linked = None
        for message in reversed(messages):
            meta = message.message_metadata or {}
            version_number = meta.get("linked_report_version_number")
            version_id = meta.get("linked_report_version_id")
            if version_number is not None and version_id is not None:
                linked = {"id": version_id, "version_number": version_number}
                break

        if linked is None and case.report_versions:
            latest = max(case.report_versions, key=lambda v: v.version_number)
            linked = {"id": latest.id, "version_number": latest.version_number}

        return {
            "case_uuid": case.case_uuid,
            "linked_report_version": linked,
            "messages": [
                CaseService.serialize_message(message)
                for message in messages
            ],
        }
