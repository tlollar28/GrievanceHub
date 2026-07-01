import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from openai import OpenAI

from app.database.models import SourceChunk
from app.services.authority_ranker import AuthorityRanker
from app.services.legal_issue_analyzer import LegalIssueAnalyzer
from app.services.legal_issue_identifier import LegalIssueIdentifier
from app.services.evidence_extractor import EvidenceExtractor
from app.services.report_builder import ReportBuilder
from app.services.citation_validator import CitationValidator
from app.services.narrative_generator import NarrativeGenerator
from app.services.relevance_utils import extract_issue_keywords
from app.retrieval_config import MAX_AUTHORITIES_TO_RANKER, REPORT_TITLE

load_dotenv()


class AnalysisService:
    @staticmethod
    def _client():
        return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    @staticmethod
    def chunk_to_source_dict(chunk: SourceChunk) -> dict:
        source = chunk.source_document
        metadata = getattr(chunk, "retrieval_metadata", {}) or {}

        return {
            "document_name": source.name,
            "document_type": source.source_type,
            "page": chunk.page_number,
            "chunk": chunk.chunk_index,
            "text": chunk.text,
            "retrieval_metadata": metadata,
        }

    @staticmethod
    def _resolve_dispute_frame(issue_analysis: dict, question: str) -> dict:
        enriched = dict(issue_analysis)
        frame = enriched.get("dispute_frame")
        if not isinstance(frame, dict) or not frame.get("action"):
            enriched["dispute_frame"] = {
                "actor": "management",
                "action": str(enriched.get("primary_issue") or question).strip(),
                "object": "",
                "direction": "",
                "installation": "",
                "employee_status": "",
                "management_actions": [],
                "employee_actions": [],
            }
        return enriched

    @staticmethod
    def _normalize_known_facts(
        known_facts: list[str] | None,
        issue_analysis: dict,
    ) -> list[str]:
        if known_facts is not None:
            return [str(f).strip() for f in known_facts if str(f).strip()]

        from_analysis = issue_analysis.get("known_facts")
        if isinstance(from_analysis, list):
            return [str(f).strip() for f in from_analysis if str(f).strip()]

        return []

    @staticmethod
    def _issue_supported_by_ranked(
        issue_label: str,
        ranked_authorities: list[dict],
    ) -> bool:
        label_lower = issue_label.lower()
        for authority in ranked_authorities:
            haystack = " ".join(
                [
                    str(authority.get("legal_issue") or ""),
                    str(authority.get("why_it_matters") or ""),
                    str(authority.get("direct_quote") or ""),
                    str(authority.get("article_or_section") or ""),
                ]
            ).lower()
            if any(
                word in haystack
                for word in label_lower.split()
                if len(word) >= 5
            ):
                return True
        return False

    @staticmethod
    def _source_types_relevant_to_analysis(issue_analysis: dict) -> set[str]:
        from app.services.relevance_utils import collect_decomposed_issues

        global_possible = {
            str(source).upper()
            for source in issue_analysis.get("possible_sources") or []
            if str(source).strip()
        }
        if not global_possible:
            return set()

        relevant: set[str] = set()
        decomposed = collect_decomposed_issues(issue_analysis)

        issue_type_hints = {
            "local_agreement": {"LMOU"},
            "information_rights": {"ELM"},
        }
        elm_signals = (
            "elm",
            "employee and labor relations",
            "discipline",
            "personnel action",
            "past practice",
        )
        lmou_signals = (
            "lmou",
            "local memorandum",
            "local agreement",
            "local mou",
        )

        for issue in decomposed:
            for src in issue.get("possible_sources") or []:
                cleaned = str(src).upper()
                if cleaned in global_possible:
                    relevant.add(cleaned)

            for hinted in issue_type_hints.get(issue.get("issue_type") or "", set()):
                if hinted in global_possible:
                    relevant.add(hinted)

            blob = " ".join(
                [
                    str(issue.get("issue") or ""),
                    " ".join(issue.get("search_queries") or []),
                    " ".join(issue.get("legal_synonyms") or []),
                ]
            ).lower()

            if any(signal in blob for signal in lmou_signals):
                if "LMOU" in global_possible:
                    relevant.add("LMOU")
            if any(signal in blob for signal in elm_signals):
                if "ELM" in global_possible:
                    relevant.add("ELM")

        if issue_analysis.get("local_agreement_issues") and "LMOU" in global_possible:
            relevant.add("LMOU")

        if issue_analysis.get("legal_issues") or issue_analysis.get("remedial_issues"):
            for source_type in ("CONTRACT", "CIM"):
                if source_type in global_possible:
                    relevant.add(source_type)

        if not relevant:
            for source_type in ("CONTRACT", "CIM"):
                if source_type in global_possible:
                    relevant.add(source_type)

        return relevant & global_possible

    @staticmethod
    def _build_retrieval_gaps(
        issue_analysis: dict,
        ranked_authorities: list[dict],
        issue_keywords: list[str] | None,
        all_chunks: list | None = None,
        retrieval_gaps_from_krs: list | None = None,
        indexed_source_types: set[str] | list[str] | None = None,
    ) -> dict:
        issue_keywords = issue_keywords or []
        pool_chunks = all_chunks or []

        found_types = {
            str(chunk.source_document.source_type).upper()
            for chunk in pool_chunks
            if getattr(chunk, "source_document", None)
            and chunk.source_document.source_type
        }

        indexed = {
            str(source_type).upper()
            for source_type in (indexed_source_types or [])
            if str(source_type).strip()
        }

        relevant_types = AnalysisService._source_types_relevant_to_analysis(
            issue_analysis
        )
        missing_source_types = sorted(
            (relevant_types & indexed) - found_types
        )

        governing_found = found_types & {"CONTRACT", "CIM"}
        if governing_found:
            missing_source_types = [
                source_type
                for source_type in missing_source_types
                if source_type not in {"ELM", "LMOU"}
            ]
        if "CIM" in found_types:
            missing_source_types = [
                source_type
                for source_type in missing_source_types
                if source_type != "CONTRACT"
            ]
        if "CONTRACT" in found_types:
            missing_source_types = [
                source_type
                for source_type in missing_source_types
                if source_type != "CIM"
            ]

        issues_without_support: list[str] = []
        seen_labels: set[str] = set()

        has_substantive_ranked = bool(ranked_authorities)

        for gap in retrieval_gaps_from_krs or []:
            label = str(gap.get("issue") or "").strip()
            if not label:
                continue
            if (
                str(gap.get("issue_type") or "").lower() == "remedy"
                and has_substantive_ranked
                and governing_found
            ):
                continue
            key = label.lower()
            if key in seen_labels:
                continue
            if AnalysisService._issue_supported_by_ranked(
                label,
                ranked_authorities,
            ):
                continue
            issues_without_support.append(label)
            seen_labels.add(key)

        return {
            "missing_source_types": missing_source_types,
            "issues_without_supporting_authority": issues_without_support,
            "facts_still_needed": list(issue_analysis.get("facts_needed") or []),
            "found_source_types": sorted(found_types),
        }

    @staticmethod
    def answer_question(
        question: str,
        chunks: list[SourceChunk],
        issue_analysis: dict | None = None,
        issue_keywords: list[str] | None = None,
    ) -> dict:
        if issue_analysis is None:
            issue_analysis = LegalIssueAnalyzer.analyze(question)

        issue_analysis = AnalysisService._resolve_dispute_frame(
            issue_analysis,
            question,
        )

        if issue_keywords is None:
            issue_keywords = extract_issue_keywords(
                question=question,
                analysis=issue_analysis,
            )

        ranked_authorities = AuthorityRanker.rank_authorities(
            question=question,
            chunks=chunks,
            max_authorities=MAX_AUTHORITIES_TO_RANKER,
            issue_analysis=issue_analysis,
            issue_keywords=issue_keywords,
        )

        evidence_items = EvidenceExtractor.extract_evidence(
            question=question,
            ranked_authorities=ranked_authorities,
            issue_analysis=issue_analysis,
        )

        return {
            "question": question,
            "issue_analysis": issue_analysis,
            "ranked_authorities": [
                {
                    "document_name": item["document_name"],
                    "document_type": item["document_type"],
                    "page": item["page"],
                    "chunk": item["chunk_index"],
                    "relevance_score": item["relevance_score"],
                    "keyword_overlap": item.get("keyword_overlap"),
                    "role": item.get("role"),
                    "legal_issue": item["legal_issue"],
                    "article_or_section": item["article_or_section"],
                    "direct_quote": item["direct_quote"],
                    "why_it_matters": item["why_it_matters"],
                }
                for item in ranked_authorities
            ],
            "supporting_evidence": evidence_items,
        }

    @staticmethod
    def generate_report(
        question: str,
        chunks: list[SourceChunk],
        issue_analysis: dict | None = None,
        issue_keywords: list[str] | None = None,
        case_context: dict | None = None,
        known_facts: list[str] | None = None,
        all_chunks: list[SourceChunk] | None = None,
        retrieval_gaps_list: list | None = None,
        indexed_source_types: set[str] | list[str] | None = None,
    ) -> dict:
        if issue_analysis is None:
            issue_analysis = LegalIssueAnalyzer.analyze(question)

        issue_analysis = AnalysisService._resolve_dispute_frame(
            issue_analysis,
            question,
        )
        known_facts = AnalysisService._normalize_known_facts(
            known_facts,
            issue_analysis,
        )

        if issue_keywords is None:
            issue_keywords = extract_issue_keywords(
                question=question,
                analysis=issue_analysis,
            )

        ranked_authorities = AuthorityRanker.rank_authorities(
            question=question,
            chunks=chunks,
            max_authorities=MAX_AUTHORITIES_TO_RANKER,
            issue_analysis=issue_analysis,
            issue_keywords=issue_keywords,
        )

        pool_chunks = all_chunks if all_chunks is not None else chunks

        retrieval_gaps = AnalysisService._build_retrieval_gaps(
            issue_analysis=issue_analysis,
            ranked_authorities=ranked_authorities,
            issue_keywords=issue_keywords,
            all_chunks=pool_chunks,
            retrieval_gaps_from_krs=retrieval_gaps_list,
            indexed_source_types=indexed_source_types,
        )

        legal_issues = LegalIssueIdentifier.identify_issues(
            question=question,
            ranked_authorities=ranked_authorities,
            issue_analysis=issue_analysis,
            known_facts=known_facts,
        )

        evidence_items = EvidenceExtractor.extract_evidence(
            question=question,
            ranked_authorities=ranked_authorities,
            issue_analysis=issue_analysis,
        )

        report = ReportBuilder.build_report(
            question=question,
            legal_issues=legal_issues,
            evidence_items=evidence_items,
            ranked_authorities=ranked_authorities,
            case_context=case_context,
            issue_analysis=issue_analysis,
            known_facts=known_facts,
            retrieval_gaps=retrieval_gaps,
        )

        report["issue_analysis"] = issue_analysis

        validated_report = CitationValidator.validate_report(
            report=report,
            evidence_items=evidence_items,
            ranked_authorities=ranked_authorities,
        )

        citation_status = (
            validated_report.get("citation_validation") or {}
        ).get("status")
        validated_report["quick_assessment"]["confidence"] = (
            NarrativeGenerator.compute_confidence(
                ranked_authorities=ranked_authorities,
                retrieval_gaps=retrieval_gaps,
                citation_status=citation_status,
            )
        )

        selected_source_types = sorted(
            {
                item["document_type"].upper()
                for item in ranked_authorities
                if item.get("document_type")
            }
        )

        return {
            "title": REPORT_TITLE,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "research_draft_notice": (
                "This analysis is a research starting point, not legal advice. "
                "Review all citations and arguments before using it in a grievance."
            ),
            "question": question,
            "issue_analysis": issue_analysis,
            "retrieval_gaps": retrieval_gaps,
            "known_facts": known_facts,
            "report": validated_report,
            "ranked_authorities": [
                {
                    "document_name": item["document_name"],
                    "document_type": item["document_type"],
                    "page": item["page"],
                    "chunk": item["chunk_index"],
                    "relevance_score": item["relevance_score"],
                    "keyword_overlap": item.get("keyword_overlap"),
                    "role": item.get("role"),
                    "legal_issue": item["legal_issue"],
                    "article_or_section": item["article_or_section"],
                    "authority_type": item["authority_type"],
                    "direct_quote": item["direct_quote"],
                    "why_it_matters": item["why_it_matters"],
                }
                for item in ranked_authorities
            ],
            "selected_source_types": selected_source_types,
        }
