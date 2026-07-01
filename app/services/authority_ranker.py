import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from app.retrieval_config import (
    DIRECTION_CONTRADICTION_PENALTY,
    MAX_AUTHORITIES_TO_RANKER,
    MIN_AUTHORITY_RELEVANCE_SCORE,
    MIN_KEYWORD_OVERLAP_FOR_MANAGEMENT,
    MIN_KEYWORD_OVERLAP_FOR_SUPPORTING,
    MIN_KEYWORD_OVERLAP_RECLASSIFY_BACKGROUND,
    MIN_MANAGEMENT_LIMITING_RELEVANCE_SCORE,
)
from app.database.models import SourceChunk
from app.services.relevance_utils import (
    build_dispute_frame_summary,
    build_issue_context_summary,
    collect_decomposed_issues,
    compute_direction_penalty,
    compute_distinctive_overlap_score,
    extract_grounded_quote_snippet,
    extract_issue_keywords,
    extract_issue_keywords_for_issue,
    is_boilerplate_chunk,
    verify_quote_in_chunk,
)

load_dotenv()

ISSUE_TYPE_DEFAULT_ROLES = {
    "legal": "union_supporting",
    "remedy": "remedy_support",
    "timeline": "timeline_requirement",
    "information_rights": "information_right",
    "local_agreement": "background_only",
    "primary": "union_supporting",
}


class AuthorityRanker:
    @staticmethod
    def _client():
        return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    @staticmethod
    def _safe_json_loads(content: str, fallback: dict):
        try:
            return json.loads(content)
        except Exception:
            return fallback

    @staticmethod
    def _apply_post_filters(
        ranked: list[dict],
        issue_keywords: list[str],
        dispute_frame: dict | None = None,
    ) -> list[dict]:
        filtered = []

        for item in ranked:
            role = item.get("role", "background_only")
            relevance_score = item.get("relevance_score", 0)
            chunk = item["chunk"]
            quote = item.get("direct_quote", "")
            overlap = compute_distinctive_overlap_score(
                chunk.text or "",
                issue_keywords,
            )
            item["keyword_overlap"] = round(overlap, 4)

            direction_penalty = compute_direction_penalty(
                chunk.text or "",
                dispute_frame,
            )
            item["direction_penalty"] = round(direction_penalty, 4)

            if not verify_quote_in_chunk(quote, chunk.text or ""):
                continue

            if direction_penalty >= DIRECTION_CONTRADICTION_PENALTY:
                continue

            if role == "management_limiting":
                if relevance_score < MIN_MANAGEMENT_LIMITING_RELEVANCE_SCORE:
                    continue
                if overlap < MIN_KEYWORD_OVERLAP_FOR_MANAGEMENT:
                    continue
                filtered.append(item)
                continue

            if relevance_score < MIN_AUTHORITY_RELEVANCE_SCORE:
                continue

            if overlap < MIN_KEYWORD_OVERLAP_FOR_SUPPORTING:
                if overlap >= MIN_KEYWORD_OVERLAP_RECLASSIFY_BACKGROUND:
                    item["role"] = "background_only"
                    item["authority_type"] = "Background"
                else:
                    continue

            filtered.append(item)

        return filtered

    @staticmethod
    def _ensure_multi_issue_coverage(
        ranked: list[dict],
        decomposed_issues: list[dict],
        chunks: list[SourceChunk],
    ) -> list[dict]:
        gaps = []
        covered_issue_ids = set()

        for item in ranked:
            chunk = item.get("chunk")
            metadata = getattr(chunk, "retrieval_metadata", {}) or {}
            for issue_id in metadata.get("matched_issue_ids", []) or []:
                covered_issue_ids.add(issue_id)

        for chunk in chunks:
            metadata = getattr(chunk, "retrieval_metadata", {}) or {}
            for issue_id in metadata.get("matched_issue_ids", []) or []:
                covered_issue_ids.add(issue_id)

        for issue in decomposed_issues:
            issue_id = issue.get("issue_id")
            if not issue_id:
                continue

            has_ranked = any(
                issue_id
                in (
                    getattr(item.get("chunk"), "retrieval_metadata", {}) or {}
                ).get("matched_issue_ids", [])
                for item in ranked
            )

            if issue_id not in covered_issue_ids or not has_ranked:
                gaps.append(
                    {
                        "issue_id": issue_id,
                        "issue_type": issue.get("issue_type"),
                        "issue": issue.get("issue"),
                        "reason": "no_ranked_authority_for_issue",
                    }
                )

        return gaps


    @staticmethod
    def _issue_ranked_for_id(ranked: list[dict], issue_id: str) -> bool:
        for item in ranked:
            chunk = item.get("chunk")
            metadata = getattr(chunk, "retrieval_metadata", {}) or {}
            if issue_id in (metadata.get("matched_issue_ids") or []):
                return True
        return False

    @staticmethod
    def _chunk_in_ranked(ranked: list[dict], chunk: SourceChunk) -> bool:
        key = (
            chunk.source_document_id,
            chunk.page_number,
            chunk.chunk_index,
        )
        for item in ranked:
            existing = item.get("chunk")
            if not existing:
                continue
            existing_key = (
                existing.source_document_id,
                existing.page_number,
                existing.chunk_index,
            )
            if existing_key == key:
                return True
        return False

    @staticmethod
    def _promote_per_issue_coverage_floor(
        ranked: list[dict],
        decomposed_issues: list[dict],
        chunks: list[SourceChunk],
        issue_keywords: list[str],
        dispute_frame: dict | None,
        max_authorities: int,
    ) -> list[dict]:
        """Promote one gated candidate per uncovered issue when post-filters pass."""
        promoted = list(ranked)

        for issue in decomposed_issues:
            issue_id = issue.get("issue_id")
            if not issue_id:
                continue
            if AuthorityRanker._issue_ranked_for_id(promoted, issue_id):
                continue

            issue_type = str(issue.get("issue_type") or "").lower()
            default_role = ISSUE_TYPE_DEFAULT_ROLES.get(
                issue_type,
                "union_supporting",
            )
            issue_kws = extract_issue_keywords_for_issue(issue, dispute_frame)
            combined_keywords = list(dict.fromkeys(issue_kws + issue_keywords))

            best_chunk = None
            best_score = -1.0

            for chunk in chunks:
                metadata = getattr(chunk, "retrieval_metadata", {}) or {}
                matched_ids = metadata.get("matched_issue_ids") or []
                if issue_id not in matched_ids:
                    continue
                if AuthorityRanker._chunk_in_ranked(promoted, chunk):
                    continue
                if is_boilerplate_chunk(chunk.text or ""):
                    continue

                score = float(metadata.get("combined_score") or 0.0)
                if score <= best_score:
                    continue
                best_score = score
                best_chunk = chunk

            if best_chunk is None:
                continue

            source = best_chunk.source_document
            quote = extract_grounded_quote_snippet(
                best_chunk.text or "",
                issue_keywords=combined_keywords,
            )
            if not verify_quote_in_chunk(quote, best_chunk.text or ""):
                continue

            relevance_score = int(
                min(
                    99,
                    max(
                        MIN_AUTHORITY_RELEVANCE_SCORE,
                        round((best_score or 0.0) * 100),
                    ),
                )
            )

            candidate = {
                "ref_id": f"PROMOTE_{issue_id}",
                "chunk": best_chunk,
                "document_name": source.name,
                "document_type": source.source_type,
                "page": best_chunk.page_number,
                "chunk_index": best_chunk.chunk_index,
                "relevance_score": relevance_score,
                "role": default_role,
                "legal_issue": str(issue.get("issue") or ""),
                "article_or_section": "Unknown",
                "authority_type": default_role.replace("_", " ").title(),
                "direct_quote": quote,
                "why_it_matters": (
                    "Retrieved governing language tied to a decomposed issue "
                    "that lacked ranked coverage after initial classification."
                ),
                "retrieval_metadata": getattr(
                    best_chunk,
                    "retrieval_metadata",
                    {},
                )
                or {},
            }

            filtered = AuthorityRanker._apply_post_filters(
                [candidate],
                combined_keywords,
                dispute_frame=dispute_frame,
            )
            if not filtered:
                continue

            promoted.append(filtered[0])

        role_priority = {
            "union_supporting": 7,
            "procedural_requirement": 6,
            "information_right": 6,
            "remedy_support": 5,
            "timeline_requirement": 4,
            "management_limiting": 3,
            "background_only": 1,
        }

        promoted.sort(
            key=lambda item: (
                role_priority.get(item.get("role", "background_only"), 0),
                item.get("relevance_score", 0),
            ),
            reverse=True,
        )

        return promoted[:max_authorities]

    @staticmethod
    def rank_authorities(
        question: str,
        chunks: list[SourceChunk],
        max_authorities: int | None = None,
        issue_analysis: dict | None = None,
        issue_keywords: list[str] | None = None,
        retrieval_gaps: list | None = None,
    ) -> list[dict]:
        if max_authorities is None:
            max_authorities = MAX_AUTHORITIES_TO_RANKER

        if not chunks:
            return []

        if issue_keywords is None:
            issue_keywords = extract_issue_keywords(
                question=question,
                analysis=issue_analysis,
            )

        dispute_frame = (issue_analysis or {}).get("dispute_frame")
        decomposed_issues = collect_decomposed_issues(issue_analysis)

        client = AuthorityRanker._client()

        chunk_map = {}
        candidates = []

        for index, chunk in enumerate(chunks):
            ref_id = f"S{index + 1}"
            source = chunk.source_document
            chunk_map[ref_id] = chunk

            metadata = getattr(chunk, "retrieval_metadata", {}) or {}

            candidates.append(
                {
                    "ref_id": ref_id,
                    "document_name": source.name,
                    "source_type": source.source_type,
                    "page": chunk.page_number,
                    "chunk": chunk.chunk_index,
                    "text": chunk.text[:3000],
                    "retrieval_hints": metadata,
                }
            )

        issue_context = build_issue_context_summary(issue_analysis)
        dispute_context = build_dispute_frame_summary(dispute_frame)

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert NPMHU and USPS grievance authority ranking engine. "
                        "Your job is NOT to answer the user's question. "
                        "Your job is to classify and rank legal authorities for a union steward.\n\n"
                        "Every authority must be classified into ONE of these roles:\n"
                        "- union_supporting\n"
                        "- management_limiting\n"
                        "- procedural_requirement\n"
                        "- information_right\n"
                        "- remedy_support\n"
                        "- timeline_requirement\n"
                        "- background_only\n"
                        "- irrelevant\n\n"
                        "Rank authorities by how useful they are for building a grievance, "
                        "NOT simply by keyword similarity or shared topic area.\n\n"
                        "Topical similarity alone is insufficient. The excerpt must address "
                        "the specific management action, employee right, procedure, timeline, "
                        "information right, or remedy at issue in the question.\n\n"
                        "If an excerpt discusses a related but different legal issue within "
                        "the same subject area, classify it as background_only or irrelevant.\n\n"
                        "Union-supporting authorities should almost always rank above "
                        "management-limiting authorities unless no supporting authority exists.\n\n"
                        "If a management article limits employee rights, include it only so "
                        "the final analysis can distinguish or overcome it.\n\n"
                        "Never let an adverse authority become the primary authority unless "
                        "it is the only relevant authority.\n\n"
                        "Use ONLY the supplied excerpts. "
                        "Never invent article numbers. "
                        "Never invent quotes. "
                        "Never paraphrase direct quotes. "
                        "Ignore table of contents pages, indexes, headers, footers, and "
                        "cross references unless they contain actual governing language.\n\n"
                        "Return valid JSON only."
                    ),
                },
                {
                    "role": "user",
                    "content": f"""
User question:
{question}

Dispute frame:
{dispute_context or "Not available"}

Issue research context:
{issue_context or "Not available"}

Issue keywords for relevance:
{", ".join(issue_keywords) if issue_keywords else "Not available"}

Candidate excerpts:
{json.dumps(candidates, indent=2)}

Return JSON exactly like this:

{{
  "ranked_authorities": [
    {{
      "ref_id": "S1",
      "relevance_score": 97,
      "role": "union_supporting",
      "legal_issue": "What issue this authority supports",
      "article_or_section": "Exact article/section if visible, otherwise Unknown",
      "authority_type": "Union-Supporting / Management-Limiting / Procedural / Information Right / Remedy / Timeline / Background / Irrelevant",
      "direct_quote": "Exact quote copied from the excerpt",
      "why_it_matters": "Explain how a union steward would use, rely on, or distinguish this authority"
    }}
  ]
}}

Rules:
- Return no more than {max_authorities} authorities.
- Prioritize authorities that help the union build, support, preserve, or investigate a grievance.
- Classify every authority by role.
- Do not treat management-limiting language as the final answer if other excerpts support a grievance.
- Direct quotes must be copied exactly from the excerpt.
- Do not invent article numbers.
- Do not invent quotes.
- Do not use table of contents/index excerpts as governing authority.
- If an excerpt limits grievance rights, label it management_limiting unless it directly helps the union argument.
- If an excerpt is only topically related but does not govern the specific dispute, use background_only or irrelevant.
""",
                },
            ],
        )

        parsed = AuthorityRanker._safe_json_loads(
            response.choices[0].message.content,
            {"ranked_authorities": []},
        )

        ranked = []

        for item in parsed.get("ranked_authorities", []):
            ref_id = item.get("ref_id")

            if ref_id not in chunk_map:
                continue

            chunk = chunk_map[ref_id]
            source = chunk.source_document

            role = item.get("role", "background_only")

            if role == "irrelevant":
                continue

            metadata = getattr(chunk, "retrieval_metadata", {}) or {}

            ranked.append(
                {
                    "ref_id": ref_id,
                    "chunk": chunk,
                    "document_name": source.name,
                    "document_type": source.source_type,
                    "page": chunk.page_number,
                    "chunk_index": chunk.chunk_index,
                    "relevance_score": item.get("relevance_score", 0),
                    "role": role,
                    "legal_issue": item.get("legal_issue", ""),
                    "article_or_section": item.get("article_or_section", "Unknown"),
                    "authority_type": item.get("authority_type", "Supporting"),
                    "direct_quote": item.get("direct_quote", ""),
                    "why_it_matters": item.get("why_it_matters", ""),
                    "retrieval_metadata": metadata,
                }
            )

        ranked = AuthorityRanker._apply_post_filters(
            ranked,
            issue_keywords,
            dispute_frame=dispute_frame,
        )

        role_priority = {
            "union_supporting": 7,
            "procedural_requirement": 6,
            "information_right": 6,
            "remedy_support": 5,
            "timeline_requirement": 4,
            "management_limiting": 3,
            "background_only": 1,
        }

        ranked.sort(
            key=lambda x: (
                role_priority.get(x.get("role", "background_only"), 0),
                x.get("relevance_score", 0),
            ),
            reverse=True,
        )

        ranked = AuthorityRanker._promote_per_issue_coverage_floor(
            ranked,
            decomposed_issues,
            chunks,
            issue_keywords,
            dispute_frame,
            max_authorities,
        )

        coverage_gaps = AuthorityRanker._ensure_multi_issue_coverage(
            ranked,
            decomposed_issues,
            chunks,
        )

        if retrieval_gaps is not None:
            retrieval_gaps.extend(coverage_gaps)

        return ranked

    @staticmethod
    def authorities_to_context(ranked_authorities: list[dict]) -> str:
        lines = []

        for index, authority in enumerate(ranked_authorities, start=1):
            chunk = authority["chunk"]

            lines.append(
                f"[Authority {index}]\n"
                f"Document: {authority['document_name']}\n"
                f"Type: {authority['document_type']}\n"
                f"Page: {authority['page']}\n"
                f"Chunk: {authority['chunk_index']}\n"
                f"Article/Section: {authority['article_or_section']}\n"
                f"Role: {authority.get('role', 'background_only')}\n"
                f"Authority Type: {authority['authority_type']}\n"
                f"Legal Issue: {authority['legal_issue']}\n"
                f"Direct Quote Selected: {authority['direct_quote']}\n"
                f"Why It Matters: {authority['why_it_matters']}\n"
                f"Full Excerpt:\n{chunk.text}"
            )

        return "\n\n".join(lines)
