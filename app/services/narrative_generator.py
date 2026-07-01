"""Grounded narrative sections for GrievanceHub Analysis Reports."""

from __future__ import annotations

from app.retrieval_config import MIN_KEY_AUTHORITY_RELEVANCE_SCORE


class NarrativeGenerator:
    PROVENANCE_NAME = "narrative_generator"

    @staticmethod
    def _provenance(inputs: list[str], authority_keys: list[str] | None = None) -> dict:
        return {
            "generator": NarrativeGenerator.PROVENANCE_NAME,
            "inputs": inputs,
            "authority_keys": authority_keys or [],
        }

    @staticmethod
    def _authority_key(item: dict) -> str:
        citation = item.get("citation") or {}
        return "|".join(
            [
                str(item.get("article_or_section", "")),
                str(citation.get("document_name", item.get("document_name", ""))),
                str(citation.get("page", item.get("page", ""))),
                str(citation.get("chunk", item.get("chunk", ""))),
            ]
        )

    @staticmethod
    def _format_cited_authority(item: dict) -> str:
        citation = item.get("citation") or {}
        doc = citation.get("document_name") or item.get("document_name") or "Source"
        section = item.get("article_or_section") or "Section unknown"
        page = citation.get("page") if citation.get("page") is not None else item.get("page")
        page_part = f", p. {page}" if page is not None else ""
        return f"{section} ({doc}{page_part})"

    @staticmethod
    def compute_confidence(
        ranked_authorities: list[dict],
        retrieval_gaps: dict | None,
        citation_status: str | None,
    ) -> str:
        retrieval_gaps = retrieval_gaps or {}
        strong = [
            a
            for a in ranked_authorities
            if (a.get("relevance_score") or 0) >= MIN_KEY_AUTHORITY_RELEVANCE_SCORE
        ]
        missing_sources = retrieval_gaps.get("missing_source_types") or []
        unresolved = retrieval_gaps.get("issues_without_supporting_authority") or []

        if citation_status == "Needs Review":
            return "Low"

        if strong and not missing_sources and not unresolved:
            return "High"

        if strong or ranked_authorities:
            return "Medium"

        return "Low"

    @staticmethod
    def build_quick_assessment(
        question: str,
        legal_issues: dict,
        authority_groups: dict[str, list[dict]],
        evidence_items: list[dict],
        known_facts: list[str] | None,
        retrieval_gaps: dict | None,
    ) -> dict:
        key_roles = (
            "union_supporting",
            "procedural_requirement",
            "information_right",
            "timeline_requirement",
            "remedy_support",
        )
        cited_items: list[dict] = []
        for role in key_roles:
            cited_items.extend(authority_groups.get(role, [])[:3])

        cited_labels = [
            NarrativeGenerator._format_cited_authority(item) for item in cited_items[:6]
        ]

        primary = (legal_issues.get("primary_issue") or "").strip()
        summary_parts = []
        if primary:
            summary_parts.append(primary)
        elif question.strip():
            summary_parts.append(question.strip())

        if cited_labels:
            summary_parts.append(
                "Retrieved authorities include: " + "; ".join(cited_labels[:4]) + "."
            )
        elif not sum(len(authority_groups.get(r, [])) for r in key_roles):
            summary_parts.append(
                "No union-supporting or procedural authorities met the relevance gates."
            )

        grievability = legal_issues.get("grievability", "Not Enough Information")

        why_bits = [
            "This assessment uses only the steward question, stated facts, ranked authorities, "
            "and extracted evidence — not assumed violations."
        ]
        if known_facts:
            why_bits.append(
                "Stated facts considered: " + "; ".join(known_facts[:5]) + "."
            )
        if retrieval_gaps and retrieval_gaps.get("missing_source_types"):
            why_bits.append(
                "No authorities were retrieved for: "
                + ", ".join(retrieval_gaps["missing_source_types"])
                + "."
            )
        if evidence_items:
            why_bits.append(
                f"{len(evidence_items)} grounded evidence item(s) support the analysis."
            )

        citation_status = None
        confidence = NarrativeGenerator.compute_confidence(
            ranked_authorities=[
                item
                for role_items in authority_groups.values()
                for item in role_items
            ],
            retrieval_gaps=retrieval_gaps,
            citation_status=citation_status,
        )
        legal_confidence = legal_issues.get("confidence")
        if legal_confidence in ("High", "Medium", "Low"):
            confidence = legal_confidence

        return {
            "summary": " ".join(summary_parts).strip(),
            "grievability": grievability,
            "confidence": confidence,
            "why": " ".join(why_bits),
            "cited_authorities": cited_labels,
            "provenance": NarrativeGenerator._provenance(
                ["question", "legal_issues", "authority_groups", "evidence_items"],
                [NarrativeGenerator._authority_key(i) for i in cited_items],
            ),
        }

    @staticmethod
    def build_grievance_framework(
        dispute_frame: str,
        legal_issues: dict,
        likely_violations: list[dict] | None,
    ) -> str:
        frame = (dispute_frame or legal_issues.get("primary_issue") or "").strip()
        if not frame:
            return ""

        violation_bits = []
        for violation in likely_violations or legal_issues.get("likely_violations") or []:
            if not isinstance(violation, dict):
                continue
            section = str(violation.get("article_or_section") or "").strip()
            issue = str(violation.get("issue") or violation.get("why_relevant") or "").strip()
            if section and issue:
                violation_bits.append(f"{section}: {issue}")
            elif section:
                violation_bits.append(section)
            elif issue:
                violation_bits.append(issue)

        lines = [f"Dispute frame: {frame}"]
        primary = (legal_issues.get("primary_issue") or "").strip()
        if primary and primary.lower() != frame.lower():
            lines.append(f"Primary legal issue identified from authorities: {primary}")

        if violation_bits:
            lines.append(
                "Contract provisions flagged for review (from retrieved authority only): "
                + "; ".join(violation_bits[:6])
                + "."
            )
        else:
            lines.append(
                "No specific contract section was flagged as a likely violation "
                "from the retrieved authorities alone."
            )

        return " ".join(lines)

    @staticmethod
    def build_recommended_remedy(
        legal_issues: dict,
        authority_groups: dict[str, list[dict]],
        evidence_items: list[dict],
    ) -> dict:
        remedy_items = authority_groups.get("remedy_support") or []
        statements: list[str] = []
        grounding: list[str] = []

        for item in remedy_items:
            label = NarrativeGenerator._format_cited_authority(item)
            quote = (item.get("direct_quote") or "").strip()
            why = (item.get("why_relevant") or item.get("why_it_matters") or "").strip()
            if quote:
                statements.append(
                    f"Request remedy supported by {label}: \"{quote[:240]}\""
                    + (f" — {why}" if why else "")
                )
            elif why:
                statements.append(f"Request remedy supported by {label}: {why}")
            else:
                statements.append(
                    f"Request any remedy expressly supported by {label} if facts confirm a violation."
                )
            grounding.append(label)

        insufficient_notice = None
        if not statements:
            insufficient_notice = (
                "No remedy_support authority was retrieved above the relevance gates. "
                "Do not assume make-whole or other remedies until governing language is located."
            )
            missing = legal_issues.get("missing_facts") or []
            if missing:
                insufficient_notice += " Confirm: " + "; ".join(missing[:4]) + "."

        return {
            "statements": statements,
            "grounding_authorities": grounding,
            "insufficient_notice": insufficient_notice,
            "provenance": NarrativeGenerator._provenance(
                ["remedy_support authorities", "legal_issues.missing_facts"],
                [NarrativeGenerator._authority_key(i) for i in remedy_items],
            ),
        }

    @staticmethod
    def build_strategic_tips(
        legal_issues: dict,
        authority_groups: dict[str, list[dict]],
        issue_analysis: dict | None,
        retrieval_gaps: dict | None,
    ) -> list[dict]:
        tips: list[dict] = []
        seen_titles: set[str] = set()

        def add_tip(title: str, text: str, keys: list[str]) -> None:
            key = title.strip().lower()
            if not text.strip() or key in seen_titles:
                return
            seen_titles.add(key)
            tips.append(
                {
                    "title": title,
                    "text": text,
                    "provenance": NarrativeGenerator._provenance(
                        ["authority_groups", "issue_analysis"],
                        keys,
                    ),
                }
            )

        for item in authority_groups.get("information_right", [])[:2]:
            label = NarrativeGenerator._format_cited_authority(item)
            quote = (item.get("direct_quote") or "").strip()
            add_tip(
                f"Information request — {item.get('article_or_section', 'Provision')}",
                (
                    f"Use {label} to request documents management relied on. "
                    + (f"Key language: \"{quote[:200]}\"." if quote else "")
                ).strip(),
                [NarrativeGenerator._authority_key(item)],
            )

        for item in authority_groups.get("timeline_requirement", [])[:2]:
            label = NarrativeGenerator._format_cited_authority(item)
            quote = (item.get("direct_quote") or "").strip()
            add_tip(
                f"Timeline — {item.get('article_or_section', 'Deadline')}",
                (
                    f"Verify filing and response deadlines using {label}. "
                    + (f"\"{quote[:200]}\"." if quote else "")
                ).strip(),
                [NarrativeGenerator._authority_key(item)],
            )

        for item in authority_groups.get("procedural_requirement", [])[:2]:
            label = NarrativeGenerator._format_cited_authority(item)
            why = (item.get("why_relevant") or "").strip()
            add_tip(
                f"Procedure — {item.get('article_or_section', 'Step')}",
                f"Follow grievance steps supported by {label}. {why}".strip(),
                [NarrativeGenerator._authority_key(item)],
            )

        for item in authority_groups.get("management_limiting", [])[:1]:
            label = NarrativeGenerator._format_cited_authority(item)
            quote = (item.get("direct_quote") or "").strip()
            add_tip(
                "Management-limiting language",
                (
                    f"Address {label} separately; do not treat it as a union violation. "
                    + (f"\"{quote[:200]}\"." if quote else "")
                ).strip(),
                [NarrativeGenerator._authority_key(item)],
            )

        retrieval_gaps = retrieval_gaps or {}
        for source_type in retrieval_gaps.get("missing_source_types") or []:
            add_tip(
                f"Retrieve {source_type} language",
                (
                    f"Issue analysis suggested reviewing {source_type}, but no ranked authority "
                    "was retrieved from that source type. Search or upload the relevant "
                    f"{source_type} section before finalizing arguments."
                ),
                [],
            )

        for issue in (retrieval_gaps.get("issues_without_supporting_authority") or [])[:2]:
            add_tip(
                "Unresolved research issue",
                f"No retrieved authority directly supported: {issue}. Narrow retrieval or add local sources.",
                [],
            )

        if issue_analysis:
            for fact in issue_analysis.get("facts_needed") or []:
                add_tip(
                    "Confirm missing fact",
                    f"Obtain and document: {fact}",
                    [],
                )
                if len(tips) >= 8:
                    break

        for secondary in legal_issues.get("secondary_issues") or []:
            add_tip(
                "Secondary issue",
                f"Track related issue in the grievance record: {secondary}",
                [],
            )
            if len(tips) >= 8:
                break

        return tips[:8]

    @staticmethod
    def build_source_references(
        ranked_authorities: list[dict],
        issue_analysis: dict | None,
        retrieval_gaps: dict | None,
    ) -> dict:
        issue_analysis = issue_analysis or {}
        retrieval_gaps = retrieval_gaps or {}

        by_type: dict[str, set[str]] = {}
        for authority in ranked_authorities:
            source_type = str(authority.get("document_type") or "").upper()
            if not source_type:
                continue
            by_type.setdefault(source_type, set()).add(
                str(authority.get("document_name") or "").strip()
            )

        found = [
            {
                "source_type": source_type,
                "document_names": sorted(names - {""}),
                "authority_count": sum(
                    1
                    for a in ranked_authorities
                    if str(a.get("document_type") or "").upper() == source_type
                ),
            }
            for source_type, names in sorted(by_type.items())
        ]

        not_found: list[dict] = []
        for source_type in retrieval_gaps.get("missing_source_types") or []:
            not_found.append(
                {
                    "source_type": source_type,
                    "issue": issue_analysis.get("primary_issue") or "",
                    "reason": "Issue analysis flagged this source type but no authority was ranked.",
                }
            )

        for issue in retrieval_gaps.get("issues_without_supporting_authority") or []:
            not_found.append(
                {
                    "source_type": None,
                    "issue": issue,
                    "reason": "No ranked authority matched this research issue.",
                }
            )

        return {
            "found": found,
            "not_found": not_found,
            "provenance": NarrativeGenerator._provenance(
                ["ranked_authorities", "issue_analysis", "retrieval_gaps"],
                [],
            ),
        }

    @staticmethod
    def build_limitations(
        legal_issues: dict,
        issue_analysis: dict | None,
        retrieval_gaps: dict | None,
        known_facts: list[str] | None,
    ) -> dict:
        issue_analysis = issue_analysis or {}
        retrieval_gaps = retrieval_gaps or {}
        known_facts = known_facts or []

        missing_facts = list(legal_issues.get("missing_facts") or [])
        for fact in issue_analysis.get("facts_needed") or []:
            cleaned = str(fact or "").strip()
            if cleaned and cleaned not in missing_facts:
                missing_facts.append(cleaned)

        caveats = [
            "This report is a research draft, not legal advice or a final grievance decision.",
            "Arguments must tie to grounded quotes and verified case facts.",
        ]
        if retrieval_gaps.get("missing_source_types"):
            caveats.append(
                "Some suggested source types had no ranked authorities: "
                + ", ".join(retrieval_gaps["missing_source_types"])
                + "."
            )

        return {
            "missing_facts": missing_facts,
            "retrieval_gaps": retrieval_gaps,
            "known_facts": known_facts,
            "caveats": caveats,
            "provenance": NarrativeGenerator._provenance(
                ["legal_issues", "issue_analysis", "retrieval_gaps", "known_facts"],
                [],
            ),
        }
