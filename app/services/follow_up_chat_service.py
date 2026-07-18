"""Case chat grounded in Case Memory, conversation context, and indexed sources."""

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

# Conversational retrieval is lighter than full analysis-report construction.
CHAT_RETRIEVAL_LIMIT_PER_SOURCE = 4
CHAT_RETRIEVAL_MAX_PASSAGES = 12
CHAT_PASSAGE_EXCERPT_CHARS = 1200
CHAT_RETRIEVAL_FACT_LIMIT = 6
CHAT_RETRIEVAL_FACT_VALUE_CHARS = 80

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
    def _collect_saved_authorities(
        report_version: CaseReportVersion,
    ) -> list[dict[str, Any]]:
        """Return deduplicated saved-report authorities with source metadata."""
        report = FollowUpChatService._report_root(report_version)
        wrapper = FollowUpChatService._wrapper_data(report_version)
        candidates: list[dict[str, Any]] = []

        for key in AUTHORITY_SECTION_KEYS:
            for item in FollowUpChatService._authority_items(report, key):
                serialized = FollowUpChatService._serialize_authority(item)
                serialized["authority_section"] = key
                candidates.append(serialized)

        for item in report.get("supporting_evidence") or []:
            if isinstance(item, dict):
                serialized = FollowUpChatService._serialize_authority(item)
                serialized["authority_section"] = "supporting_evidence"
                candidates.append(serialized)

        ranked = wrapper.get("ranked_authorities") or report_version.ranked_authorities or []
        for item in ranked:
            if isinstance(item, dict):
                serialized = FollowUpChatService._serialize_authority(item)
                serialized["authority_section"] = "ranked_authorities"
                candidates.append(serialized)

        authorities: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str, int | None]] = set()
        for item in candidates:
            quote = str(item.get("direct_quote") or "").strip()
            if not quote:
                continue
            key = (
                quote.casefold(),
                str(item.get("document_type") or "").casefold(),
                str(item.get("document_name") or "").casefold(),
                item.get("page"),
            )
            if key in seen:
                continue
            seen.add(key)
            authorities.append(item)
        return authorities

    @staticmethod
    def _collect_saved_quotes(report_version: CaseReportVersion) -> list[str]:
        return [
            str(item.get("direct_quote") or "").strip()
            for item in FollowUpChatService._collect_saved_authorities(report_version)
            if str(item.get("direct_quote") or "").strip()
        ]

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
    def _prior_followups(
        case: GrievanceCase,
        *,
        db: Session | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        from app.services.case_service import AI_CONTEXT_PRIOR_FOLLOWUP_LIMIT

        if limit is None:
            limit = AI_CONTEXT_PRIOR_FOLLOWUP_LIMIT

        messages = (
            CaseService.fetch_recent_follow_up_messages(db, case.id, limit=limit)
            if db is not None and getattr(case, "id", None) is not None
            else sorted(case.messages or [], key=lambda m: m.created_at)
        )
        thread: list[dict] = []
        for message in messages:
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
        if limit is not None and limit >= 0:
            thread = thread[-limit:]
        return thread

    @staticmethod
    def _known_facts_as_list(known_facts: Any) -> list[str] | None:
        if not known_facts:
            return None
        if isinstance(known_facts, dict):
            return [f"{key}: {value}" for key, value in known_facts.items()]
        if isinstance(known_facts, list):
            return [str(item) for item in known_facts if str(item).strip()]
        return [str(known_facts)]

    @staticmethod
    def _live_indexed_source_types(db: Session | None) -> list[str]:
        """Source types present in the running index (empty when unavailable)."""
        if db is None:
            return []
        try:
            from app.services.knowledge_retrieval_service import KnowledgeRetrievalService

            return sorted(KnowledgeRetrievalService._get_indexed_source_types(db))
        except Exception:
            return []

    @staticmethod
    def _question_tokens(text: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[a-zA-Z0-9.']+", (text or "").lower())
            if len(token) >= 4
        }

    @staticmethod
    def build_chat_retrieval_query(
        question: str,
        *,
        known_facts: Any = None,
        max_facts: int = CHAT_RETRIEVAL_FACT_LIMIT,
    ) -> str:
        """Build a question-centered retrieval query with bounded overlapping facts.

        The current steward question is always primary and is never replaced by
        prior conversation or historical case narrative.
        """
        question = str(question or "").strip()
        if not question:
            return ""

        question_tokens = FollowUpChatService._question_tokens(question)
        fact_snippets: list[str] = []
        if isinstance(known_facts, dict) and question_tokens:
            for key, value in known_facts.items():
                if len(fact_snippets) >= max_facts:
                    break
                key_text = str(key or "").strip()
                value_text = str(value or "").strip()
                if not value_text:
                    continue
                if len(value_text) > CHAT_RETRIEVAL_FACT_VALUE_CHARS:
                    value_text = value_text[:CHAT_RETRIEVAL_FACT_VALUE_CHARS].rstrip()
                fact_tokens = FollowUpChatService._question_tokens(
                    f"{key_text} {value_text}"
                )
                if not fact_tokens.intersection(question_tokens):
                    continue
                fact_snippets.append(f"{key_text}: {value_text}" if key_text else value_text)

        if not fact_snippets:
            return question
        return question + "\nRelevant case facts: " + "; ".join(fact_snippets)

    @staticmethod
    def retrieve_indexed_source_passages(
        db: Session,
        query: str,
        *,
        known_facts: Any = None,
        limit_per_source: int = CHAT_RETRIEVAL_LIMIT_PER_SOURCE,
        max_passages: int = CHAT_RETRIEVAL_MAX_PASSAGES,
    ) -> dict[str, Any]:
        """Retrieve relevant passages from the configured indexed corpus for chat.

        Uses the shared KnowledgeRetrievalService relevance controls. Does not
        run AuthorityRanker, ReportBuilder, or report-level citation validation.

        ``retrieval_status`` is one of: ``ok``, ``empty``, ``failed``, ``skipped``.
        """
        from app.services.analysis_service import AnalysisService
        from app.services.knowledge_retrieval_service import KnowledgeRetrievalService

        empty: dict[str, Any] = {
            "retrieved_source_passages": [],
            "indexed_source_types": FollowUpChatService._live_indexed_source_types(db),
            "retrieval_query": query,
            "retrieval_performed": False,
            "retrieval_status": "skipped",
            "retrieval_error": False,
            "retrieval_error_class": None,
        }
        if db is None or not str(query or "").strip():
            return empty

        try:
            results = KnowledgeRetrievalService.search_all(
                db=db,
                query=query,
                limit_per_source=limit_per_source,
                known_facts=FollowUpChatService._known_facts_as_list(known_facts),
            )
        except Exception as exc:
            return {
                **empty,
                "indexed_source_types": FollowUpChatService._live_indexed_source_types(
                    db
                ),
                "retrieval_status": "failed",
                "retrieval_error": True,
                "retrieval_error_class": type(exc).__name__,
            }

        passages: list[dict[str, Any]] = []
        for chunk in (results.get("all_chunks") or [])[:max_passages]:
            source_dict = AnalysisService.chunk_to_source_dict(chunk)
            text = str(source_dict.get("text") or "").strip()
            if not text:
                continue
            excerpt = text[:CHAT_PASSAGE_EXCERPT_CHARS]
            metadata = source_dict.get("retrieval_metadata") or {}
            passages.append(
                {
                    "source_id": source_dict.get("source_id"),
                    "document_type": source_dict.get("document_type"),
                    "document_name": source_dict.get("document_name"),
                    "page": source_dict.get("page"),
                    "chunk": source_dict.get("chunk"),
                    "article_or_section": metadata.get("article_or_section")
                    or metadata.get("section")
                    or "",
                    "excerpt": excerpt,
                    "combined_score": metadata.get("combined_score"),
                    "provenance": "retrieved_passage",
                }
            )

        indexed = list(
            results.get("indexed_source_types")
            or FollowUpChatService._live_indexed_source_types(db)
        )
        return {
            "retrieved_source_passages": passages,
            "indexed_source_types": indexed,
            "retrieval_query": query,
            "retrieval_performed": True,
            "retrieval_status": "ok" if passages else "empty",
            "retrieval_error": False,
            "retrieval_error_class": None,
        }

    @staticmethod
    def attach_source_retrieval(
        package: dict[str, Any],
        db: Session | None,
        question: str,
        *,
        limit_per_source: int = CHAT_RETRIEVAL_LIMIT_PER_SOURCE,
    ) -> dict[str, Any]:
        """Attach live indexed-corpus retrieval to a chat grounding package."""
        retrieval_query = FollowUpChatService.build_chat_retrieval_query(
            question,
            known_facts=package.get("known_facts"),
        )
        retrieved = FollowUpChatService.retrieve_indexed_source_passages(
            db,
            retrieval_query,
            known_facts=package.get("known_facts"),
            limit_per_source=limit_per_source,
        )
        package["retrieved_source_passages"] = retrieved["retrieved_source_passages"]
        package["retrieval_query"] = retrieved.get("retrieval_query")
        package["retrieval_performed"] = bool(retrieved.get("retrieval_performed"))
        package["retrieval_status"] = retrieved.get("retrieval_status") or "skipped"
        package["retrieval_error"] = bool(retrieved.get("retrieval_error"))
        package["retrieval_error_class"] = retrieved.get("retrieval_error_class")
        package["indexed_source_types_available"] = list(
            retrieved.get("indexed_source_types") or []
        )

        # Keep report quotes separate from current-retrieval passages for provenance.
        package.setdefault(
            "saved_report_authority_quotes",
            list(package.get("saved_report_authority_quotes") or []),
        )
        # Compatibility field for older tests: report quotes only (not merged).
        package["saved_quotes"] = list(package["saved_report_authority_quotes"])

        if package.get("report_version_id") is not None:
            package["grounding_mode"] = "case_report_and_indexed_sources"
        else:
            package["grounding_mode"] = "case_memory_and_indexed_sources"

        caveats = [
            str(item)
            for item in (package.get("limitations_caveats") or [])
            if "Case Memory and conversation only" not in str(item)
        ]
        status = package["retrieval_status"]
        if status == "failed":
            caveats.append(
                "Indexed source retrieval was temporarily unavailable for this "
                "question. Answer from Case Memory and conversation context only."
            )
        elif status == "empty":
            caveats.append(
                "No relevant indexed passage was found for this question."
            )
        package["limitations_caveats"] = caveats
        return package

    @staticmethod
    def build_grounding_package(
        case: GrievanceCase,
        report_version: CaseReportVersion,
        *,
        db: Session | None = None,
        question: str | None = None,
        restored_case_context: dict[str, Any] | None = None,
        attach_retrieval: bool = False,
        limit_per_source: int = CHAT_RETRIEVAL_LIMIT_PER_SOURCE,
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
        saved_report_authorities = FollowUpChatService._collect_saved_authorities(
            report_version
        )
        saved_report_authority_quotes = [
            str(item.get("direct_quote") or "").strip()
            for item in saved_report_authorities
            if str(item.get("direct_quote") or "").strip()
        ]

        package: dict[str, Any] = {
            "case_uuid": case.case_uuid,
            "report_version_number": report_version.version_number,
            "report_version_id": report_version.id,
            "initial_question": case.initial_question,
            "known_facts": case.known_facts or {},
            "uploaded_files": CaseService._collect_asset_upload_metadata(case),
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
            "prior_followups": FollowUpChatService._prior_followups(case, db=db),
            "saved_report_authorities": saved_report_authorities,
            "saved_report_authority_quotes": saved_report_authority_quotes,
            "saved_quotes": saved_report_authority_quotes,
            "indexed_source_types_available": FollowUpChatService._live_indexed_source_types(
                db
            ),
            "unindexed_sources_disclosed": list(
                retrieval_gaps.get("unindexed_sources_requested") or []
            ),
            "retrieval_status": "skipped",
            "retrieval_error": False,
        }

        # Application owns case memory; AI consumes restored case state.
        continuity = restored_case_context
        if continuity is None and db is not None:
            continuity = CaseService.build_restored_interaction_context(
                db,
                case,
                question or "",
            )
        if continuity:
            package["ai_continuity_context"] = continuity
            package["case_state"] = continuity.get("case_state") or {}
            package["continuity_summary"] = continuity.get("continuity_summary") or {}
            package["important_historical_decisions"] = (
                continuity.get("important_historical_decisions") or []
            )
            package["durable_conversation_signals"] = (
                continuity.get("durable_conversation_signals") or []
            )
            package["official_artifacts"] = continuity.get("official_artifacts") or []
            package["official_artifact_index"] = (
                continuity.get("official_artifact_index") or []
            )
            package["official_artifact_count"] = continuity.get("official_artifact_count")
            package["latest_official_report"] = continuity.get("latest_official_report")
            package["latest_official_grievance"] = continuity.get(
                "latest_official_grievance"
            )
            package["retrieved_case_memory"] = continuity.get("retrieved_case_memory") or {}
            package["workflow_state"] = continuity.get("workflow_state") or {}
            package["draft_state"] = continuity.get("draft_state") or {}
            package["evidence_assets"] = continuity.get("evidence_assets") or []
            package["ai_context_restored"] = True
            package["restore_action_required"] = False
            package["case_is_system_of_record"] = True
            # Prefer cumulative known facts from restored case state.
            if continuity.get("known_facts"):
                package["known_facts"] = continuity["known_facts"]
        package["grounding_mode"] = "case_report"
        package.setdefault("retrieved_source_passages", [])
        if attach_retrieval and db is not None and question:
            FollowUpChatService.attach_source_retrieval(
                package,
                db,
                question,
                limit_per_source=limit_per_source,
            )
        return package

    @staticmethod
    def validate_citations(
        citations: list[dict],
        grounding: dict[str, Any],
    ) -> list[FollowUpCitation]:
        """Validate citations with explicit provenance (retrieval vs saved report)."""
        passages = grounding.get("retrieved_source_passages") or []
        report_authorities = list(grounding.get("saved_report_authorities") or [])
        if not report_authorities:
            report_authorities = [
                {"direct_quote": quote}
                for quote in (
                    grounding.get("saved_report_authority_quotes")
                    or grounding.get("saved_quotes")
                    or []
                )
            ]
        validated: list[FollowUpCitation] = []
        retrieval_failed = bool(grounding.get("retrieval_error")) or (
            grounding.get("retrieval_status") == "failed"
        )

        for raw in citations or []:
            if not isinstance(raw, dict):
                continue
            quote = str(raw.get("quote") or "").strip()
            provenance = "ungrounded"
            passage_index: int | None = None
            authority_index: int | None = None
            grounded = False

            if quote and not retrieval_failed:
                for index, passage in enumerate(passages):
                    if not isinstance(passage, dict):
                        continue
                    excerpt = str(passage.get("excerpt") or "")
                    if excerpt and (
                        verify_quote_in_chunk(quote, excerpt)
                        or verify_quote_in_chunk(excerpt, quote)
                    ):
                        grounded = True
                        provenance = "retrieved_passage"
                        passage_index = index
                        # Source metadata comes from the matched passage, not model output.
                        for key in (
                            "document_type",
                            "document_name",
                            "page",
                            "article_or_section",
                        ):
                            value = passage.get(key)
                            if value not in (None, ""):
                                raw = {**raw, key: value}
                        break

            if quote and not grounded:
                for index, authority in enumerate(report_authorities):
                    if not isinstance(authority, dict):
                        continue
                    saved = str(authority.get("direct_quote") or "").strip()
                    if not saved:
                        continue
                    if verify_quote_in_chunk(quote, saved) or verify_quote_in_chunk(
                        saved, quote
                    ):
                        grounded = True
                        provenance = "saved_report_authority"
                        authority_index = index
                        # Saved-report metadata is authoritative; ignore model substitutions.
                        for key in (
                            "document_type",
                            "document_name",
                            "page",
                            "article_or_section",
                        ):
                            value = authority.get(key)
                            if value not in (None, ""):
                                raw = {**raw, key: value}
                        break

            citation = FollowUpCitation(
                document_type=str(raw.get("document_type") or "").upper(),
                document_name=str(raw.get("document_name") or ""),
                article_or_section=str(raw.get("article_or_section") or ""),
                page=raw.get("page"),
                quote=quote,
                grounded=grounded if quote else False,
                grounding_provenance=provenance,  # type: ignore[arg-type]
                grounding_passage_index=passage_index,
                grounding_authority_index=authority_index,
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
            "You are the GrievanceHub case assistant for NPMHU stewards. "
            "Ground every answer in the provided CASE_CONTEXT JSON only. "
            "CASE_CONTEXT includes Case Memory, bounded conversation context, optional "
            "saved-report authorities, and retrieved_source_passages from the indexed "
            "labor-reference corpus. "
            "Prefer retrieved_source_passages for contract and grievance questions. "
            "Also use ai_continuity_context, official_artifact_index, "
            "important_historical_decisions, durable_conversation_signals, and "
            "retrieved_case_memory when present. "
            "Do not invent grievant names, dates, management actions, or source passages. "
            "When citing sources, copy verbatim quotes only from "
            "retrieved_source_passages excerpts for current retrieval, or from "
            "saved_report_authorities / authority_sections for saved-report "
            "authorities. Do not invent quotes. Keep document types distinct. "
            "If remedy authority is absent, say so and label practical relief as proposed. "
            "Ask for missing facts instead of inventing them. Brand as GrievanceHub only. "
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
            '      "quote": "verbatim quote from retrieved_source_passages or saved authorities"\n'
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

        retrieval_status = grounding.get("retrieval_status") or "skipped"
        retrieval_failed = bool(grounding.get("retrieval_error")) or (
            retrieval_status == "failed"
        )

        if retrieval_failed:
            disclosures.append(
                "Indexed source retrieval was temporarily unavailable for this question."
            )
            # Do not present ungrounded or retrieval-claimed citations after failure.
            citations = [
                c
                for c in citations
                if c.grounded and c.grounding_provenance == "saved_report_authority"
            ]
        elif retrieval_status == "empty":
            disclosures.append(
                "No relevant indexed passage was found for this question."
            )
            # Empty search cannot support current-retrieval citations.
            citations = [
                c
                for c in citations
                if c.grounded and c.grounding_provenance == "saved_report_authority"
            ]

        ungrounded = [c for c in citations if c.quote and not c.grounded]
        if ungrounded:
            disclosures.append(
                "One or more cited quotes could not be verified against retrieved "
                "source passages or saved report excerpts."
            )
            citations = [c for c in citations if c.grounded]

        if grounding.get("report_summary", {}).get("has_remedy_authority") is False:
            if any(token in question.lower() for token in ("remedy", "relief", "request")):
                disclosures.append(
                    "The saved report does not contain explicit remedy authority above relevance gates."
                )

        # Disclose gaps recorded on a saved report when the steward asks about them.
        report_gaps = grounding.get("unindexed_sources_disclosed") or []
        if report_gaps and any(
            str(src).lower() in question.lower() for src in report_gaps
        ):
            disclosures.append(
                f"{', '.join(str(src) for src in report_gaps)} is referenced in the "
                "saved report gaps but is not present in the current indexed corpus."
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
    def build_memory_only_grounding_package(
        case: GrievanceCase,
        *,
        db: Session | None = None,
        question: str | None = None,
        restored_case_context: dict[str, Any] | None = None,
        attach_retrieval: bool = False,
        limit_per_source: int = CHAT_RETRIEVAL_LIMIT_PER_SOURCE,
    ) -> dict[str, Any]:
        """Ground chat from Case Memory when no saved analysis report exists.

        Live indexed-corpus retrieval is attached separately via
        ``attach_source_retrieval`` so chat is not limited to Case Memory alone.
        """
        restored = restored_case_context
        if restored is None and db is not None:
            restored = CaseService.build_restored_interaction_context(
                db,
                case,
                question or "",
            )
        package: dict[str, Any] = {
            "case_uuid": case.case_uuid,
            "report_version_number": None,
            "report_version_id": None,
            "initial_question": case.initial_question,
            "known_facts": case.known_facts or {},
            "uploaded_files": CaseService._collect_asset_upload_metadata(case),
            "report_summary": {},
            "retrieval_gaps": {},
            "source_coverage_audit": [],
            "quick_assessment": {},
            "key_violations": [],
            "authority_sections": {key: [] for key in AUTHORITY_SECTION_KEYS},
            "recommended_remedy": {},
            "evidence_to_gather": [],
            "limitations_caveats": [
                "No analysis report has been saved yet. "
                "Answer using Case Memory, conversation context, and retrieved "
                "indexed source passages."
            ],
            "facts_still_needed": [],
            "issue_analysis": {},
            "evidence_items": [],
            "prior_followups": FollowUpChatService._prior_followups(case, db=db),
            "saved_report_authorities": [],
            "saved_report_authority_quotes": [],
            "saved_quotes": [],
            "retrieved_source_passages": [],
            "indexed_source_types_available": FollowUpChatService._live_indexed_source_types(
                db
            ),
            "unindexed_sources_disclosed": [],
            "grounding_mode": "case_memory_only",
            "retrieval_status": "skipped",
            "retrieval_error": False,
        }
        if restored:
            package["ai_continuity_context"] = restored
            package["case_state"] = restored.get("case_state") or {}
            package["continuity_summary"] = restored.get("continuity_summary") or {}
            package["important_historical_decisions"] = (
                restored.get("important_historical_decisions") or []
            )
            package["durable_conversation_signals"] = (
                restored.get("durable_conversation_signals") or []
            )
            package["official_artifacts"] = restored.get("official_artifacts") or []
            package["official_artifact_index"] = (
                restored.get("official_artifact_index") or []
            )
            package["retrieved_case_memory"] = restored.get("retrieved_case_memory") or {}
            package["workflow_state"] = restored.get("workflow_state") or {}
            package["draft_state"] = restored.get("draft_state") or {}
            package["evidence_assets"] = restored.get("evidence_assets") or []
            package["ai_context_restored"] = True
            package["restore_action_required"] = False
            package["case_is_system_of_record"] = True
            if restored.get("known_facts"):
                package["known_facts"] = restored["known_facts"]
        if attach_retrieval and db is not None and question:
            FollowUpChatService.attach_source_retrieval(
                package,
                db,
                question,
                limit_per_source=limit_per_source,
            )
        return package

    @staticmethod
    def answer_follow_up(
        db: Session,
        case_uuid: str,
        content: str,
        report_version_number: int | None = None,
        *,
        llm_callable: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None,
        limit_per_source: int = CHAT_RETRIEVAL_LIMIT_PER_SOURCE,
    ) -> dict[str, Any]:
        case = CaseService.get_case_for_chat(db, case_uuid)
        report_version = None
        if report_version_number is not None:
            report_version = CaseService.get_grounding_report_version(
                case, report_version_number
            )
            if not report_version.report_data:
                raise CaseReportRequiredError("Saved report version has no report_data")
        elif case.report_versions:
            try:
                report_version = CaseService.get_grounding_report_version(case, None)
                if report_version and not report_version.report_data:
                    report_version = None
            except CaseReportRequiredError:
                report_version = None

        restored = CaseService.build_restored_interaction_context(db, case, content)
        if report_version is not None:
            grounding = FollowUpChatService.build_grounding_package(
                case,
                report_version,
                db=db,
                question=content,
                restored_case_context=restored,
                attach_retrieval=True,
                limit_per_source=limit_per_source,
            )
        else:
            grounding = FollowUpChatService.build_memory_only_grounding_package(
                case,
                db=db,
                question=content,
                restored_case_context=restored,
                attach_retrieval=True,
                limit_per_source=limit_per_source,
            )
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

        memory_update_status = str(
            (assistant_message.message_metadata or {}).get(
                "case_memory_update_status", "unknown"
            )
        )

        linked = None
        if report_version is not None:
            linked = {
                "id": report_version.id,
                "version_number": report_version.version_number,
            }

        return {
            "user_message": user_message,
            "assistant_message": assistant_message,
            "answer": answer.answer,
            "answer_type": answer.answer_type,
            "citations": [c.model_dump() for c in answer.citations],
            "disclosures": answer.disclosures,
            "facts_needed": answer.facts_needed,
            "linked_report_version": linked,
            "requires_report_regen": answer.requires_report_regen,
            "suggested_actions": answer.suggested_actions,
            "retrieval_status": grounding.get("retrieval_status"),
            "retrieval_query": grounding.get("retrieval_query"),
            "retrieval_error": bool(grounding.get("retrieval_error")),
            "case_memory_update_status": memory_update_status,
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
