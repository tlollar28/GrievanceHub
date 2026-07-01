from datetime import datetime, timezone

from app.retrieval_config import (
    MIN_KEY_AUTHORITY_RELEVANCE_SCORE,
    REPORT_BRAND,
    REPORT_TITLE,
)
from app.schemas.report_schema import GrievanceHubReport
from app.services.narrative_generator import NarrativeGenerator


class ReportBuilder:
    SUPPORTING_ROLES = {
        "union_supporting",
        "procedural_requirement",
        "information_right",
        "remedy_support",
        "timeline_requirement",
    }

    KEY_CONTRACT_ROLES = {
        "union_supporting",
        "procedural_requirement",
        "information_right",
        "timeline_requirement",
    }

    ROLE_TITLES = {
        "union_supporting": "Union-Supporting Authority",
        "procedural_requirement": "Procedural Requirement",
        "information_right": "Information Right",
        "remedy_support": "Remedy Support",
        "timeline_requirement": "Timeline Requirement",
        "management_limiting": "Management-Limiting Authority",
        "background_only": "Background Authority",
    }

    MATCHING_TEMPLATES_NOTICE = (
        "Grievance template matching is not yet available. "
        "Templates will be suggested in a future release once template storage is connected."
    )

    @staticmethod
    def _normalize_role(authority: dict) -> str:
        role = str(authority.get("role") or "").strip().lower()

        if role:
            return role

        authority_type = str(authority.get("authority_type") or "").strip().lower()

        legacy_map = {
            "union-supporting": "union_supporting",
            "union supporting": "union_supporting",
            "procedural": "procedural_requirement",
            "information right": "information_right",
            "remedy": "remedy_support",
            "timeline": "timeline_requirement",
            "management-limiting": "management_limiting",
            "management limiting": "management_limiting",
            "management-adverse": "management_limiting",
            "management adverse": "management_limiting",
            "background": "background_only",
            "weak": "background_only",
        }

        return legacy_map.get(authority_type, "background_only")

    @staticmethod
    def _authority_to_report_item(authority: dict) -> dict:
        role = ReportBuilder._normalize_role(authority)

        return {
            "article_or_section": authority.get("article_or_section", "Unknown"),
            "issue": authority.get("legal_issue", ""),
            "role": role,
            "role_title": ReportBuilder.ROLE_TITLES.get(
                role,
                "Background Authority",
            ),
            "why_relevant": authority.get("why_it_matters", ""),
            "direct_quote": authority.get("direct_quote", ""),
            "relevance_score": authority.get("relevance_score"),
            "keyword_overlap": authority.get("keyword_overlap"),
            "citation": {
                "document_name": authority.get("document_name", ""),
                "document_type": authority.get("document_type", ""),
                "page": authority.get("page"),
                "chunk": authority.get("chunk_index"),
            },
            "provenance": {
                "generator": "report_builder",
                "inputs": ["ranked_authorities"],
                "authority_keys": [
                    "|".join(
                        [
                            str(authority.get("article_or_section", "")),
                            str(authority.get("document_name", "")),
                            str(authority.get("page", "")),
                            str(authority.get("chunk_index", "")),
                        ]
                    )
                ],
            },
        }

    @staticmethod
    def _deduplicate(items: list[dict]) -> list[dict]:
        seen = set()
        unique = []

        for item in items:
            citation = item.get("citation", {})

            key = (
                str(item.get("article_or_section", "")).strip().lower(),
                str(item.get("direct_quote", "")).strip().lower(),
                str(citation.get("document_name", "")).strip().lower(),
                citation.get("page"),
                citation.get("chunk"),
            )

            if key in seen:
                continue

            seen.add(key)
            unique.append(item)

        return unique

    @staticmethod
    def _group_authorities(ranked_authorities: list[dict]) -> dict[str, list[dict]]:
        groups = {
            "union_supporting": [],
            "procedural_requirement": [],
            "information_right": [],
            "remedy_support": [],
            "timeline_requirement": [],
            "management_limiting": [],
            "background_only": [],
        }

        for authority in ranked_authorities:
            role = ReportBuilder._normalize_role(authority)

            if role == "irrelevant":
                continue

            if role not in groups:
                role = "background_only"

            groups[role].append(
                ReportBuilder._authority_to_report_item(authority)
            )

        for role, items in groups.items():
            groups[role] = ReportBuilder._deduplicate(items)

        return groups

    @staticmethod
    def _build_key_contract_issues(groups: dict[str, list[dict]]) -> list[dict]:
        key_items = []

        for role in ReportBuilder.KEY_CONTRACT_ROLES:
            for item in groups.get(role, []):
                score = item.get("relevance_score") or 0
                if score >= MIN_KEY_AUTHORITY_RELEVANCE_SCORE:
                    key_items.append(item)

        return ReportBuilder._deduplicate(key_items)

    @staticmethod
    def _dispute_frame(issue_analysis: dict | None, question: str) -> str:
        issue_analysis = issue_analysis or {}
        frame = str(issue_analysis.get("dispute_frame") or "").strip()
        if frame:
            return frame
        primary = str(issue_analysis.get("primary_issue") or "").strip()
        if primary:
            return primary
        return str(question or "").strip()

    @staticmethod
    def build_report(
        question: str,
        legal_issues: dict,
        evidence_items: list[dict],
        ranked_authorities: list[dict],
        case_context: dict | None = None,
        issue_analysis: dict | None = None,
        known_facts: list[str] | None = None,
        retrieval_gaps: dict | None = None,
    ) -> dict:
        authority_groups = ReportBuilder._group_authorities(ranked_authorities)
        case_context = case_context or {}
        known_facts = known_facts or []
        retrieval_gaps = retrieval_gaps or {}
        dispute_frame = ReportBuilder._dispute_frame(issue_analysis, question)

        selected_source_types = sorted(
            {
                str(item.get("document_type", "")).upper()
                for item in ranked_authorities
                if item.get("document_type")
            }
        )

        key_contract_issues = ReportBuilder._build_key_contract_issues(authority_groups)

        quick_assessment = NarrativeGenerator.build_quick_assessment(
            question=question,
            legal_issues=legal_issues,
            authority_groups=authority_groups,
            evidence_items=evidence_items,
            known_facts=known_facts,
            retrieval_gaps=retrieval_gaps,
        )

        recommended_remedy = NarrativeGenerator.build_recommended_remedy(
            legal_issues=legal_issues,
            authority_groups=authority_groups,
            evidence_items=evidence_items,
        )

        strategic_tips = NarrativeGenerator.build_strategic_tips(
            legal_issues=legal_issues,
            authority_groups=authority_groups,
            issue_analysis=issue_analysis,
            retrieval_gaps=retrieval_gaps,
        )

        limitations = NarrativeGenerator.build_limitations(
            legal_issues=legal_issues,
            issue_analysis=issue_analysis,
            retrieval_gaps=retrieval_gaps,
            known_facts=known_facts,
        )

        source_references = NarrativeGenerator.build_source_references(
            ranked_authorities=ranked_authorities,
            issue_analysis=issue_analysis,
            retrieval_gaps=retrieval_gaps,
        )

        grievance_framework = NarrativeGenerator.build_grievance_framework(
            dispute_frame=dispute_frame,
            legal_issues=legal_issues,
            likely_violations=legal_issues.get("likely_violations"),
        )

        report_payload = {
            "report_title": REPORT_TITLE,
            "brand": REPORT_BRAND,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "case_information": {
                "case_id": case_context.get("case_id"),
                "case_title": case_context.get("case_title"),
                "user_name": case_context.get("user_name"),
                "local_number": case_context.get("local_number"),
            },
            "research_draft_notice": (
                "This analysis is a research starting point, not legal advice. "
                "Review all citations and arguments before using it in a grievance."
            ),
            "your_question": question,
            "quick_assessment": quick_assessment,
            "secondary_issues": legal_issues.get("secondary_issues") or [],
            "key_contract_violations": key_contract_issues,
            "union_supporting_authority": authority_groups["union_supporting"],
            "procedural_requirements": authority_groups["procedural_requirement"],
            "information_rights": authority_groups["information_right"],
            "timeline_requirements": authority_groups["timeline_requirement"],
            "remedy_authority": authority_groups["remedy_support"],
            "management_limiting_authority": authority_groups["management_limiting"],
            "background_authority": authority_groups["background_only"],
            "supporting_evidence": evidence_items,
            "recommended_remedy": recommended_remedy,
            "detailed_analysis": {
                "grievance_framework": grievance_framework,
                "evidence_to_gather": limitations.get("missing_facts") or [],
                "strategic_tips": strategic_tips,
                "provenance": {
                    "generator": "narrative_generator",
                    "inputs": ["dispute_frame", "legal_issues", "authority_groups"],
                    "authority_keys": [],
                },
            },
            "matching_grievance_templates": [],
            "matching_grievance_templates_notice": ReportBuilder.MATCHING_TEMPLATES_NOTICE,
            "limitations": limitations,
            "source_references": source_references,
            "source_summary": {
                "selected_source_types": selected_source_types,
                "ranked_authorities_count": len(ranked_authorities),
                "evidence_items_count": len(evidence_items),
                "union_supporting_count": len(authority_groups["union_supporting"]),
                "procedural_requirement_count": len(
                    authority_groups["procedural_requirement"]
                ),
                "information_right_count": len(authority_groups["information_right"]),
                "remedy_support_count": len(authority_groups["remedy_support"]),
                "timeline_requirement_count": len(
                    authority_groups["timeline_requirement"]
                ),
                "management_limiting_count": len(
                    authority_groups["management_limiting"]
                ),
            },
        }

        validated = GrievanceHubReport.model_validate(report_payload)
        return validated.model_dump(mode="json")
