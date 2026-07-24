"""Phase 1.1 — source coverage and remedy grounding diagnostic (frozen question)."""

from __future__ import annotations

import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from app.database.session import SessionLocal
from app.retrieval_config import (
    DIRECTION_CONTRADICTION_PENALTY,
    MAX_AUTHORITIES_TO_RANKER,
    MIN_AUTHORITY_RELEVANCE_SCORE,
    MIN_COMBINED_RETRIEVAL_SCORE,
)
from app.services.analysis_service import AnalysisService
from app.services.authority_ranker import AuthorityRanker
from app.services.knowledge_retrieval_service import KnowledgeRetrievalService
from app.services.legal_issue_analyzer import LegalIssueAnalyzer
from app.services.relevance_utils import (
    build_queries_for_issue,
    collect_decomposed_issues,
    compute_direction_match_score,
    compute_direction_penalty,
    compute_distinctive_overlap_score,
    extract_issue_keywords,
    extract_issue_keywords_for_issue,
    passes_retrieval_gate,
    verify_quote_in_chunk,
)
from scripts.diagnose_regression import filter_drop_reason, rank_authorities_with_diagnostics

FROZEN_QUESTION = (
    "Management canceled previously approved annual leave without explanation and "
    "ignored the union's information request. What rules apply and what remedy is "
    "appropriate?"
)

OUTPUT_MD = ROOT / "data" / "reports" / "phase1_1_source_coverage_diagnostic_2026-07-02.md"
OUTPUT_JSON = ROOT / "data" / "reports" / "phase1_1_source_coverage_diagnostic_2026-07-02.json"

SOURCE_TYPES = ("CONTRACT", "CIM", "ELM")

ISSUE_CATEGORIES = {
    "leave_cancellation": [
        "leave",
        "annual leave",
        "cancel",
        "approved",
        "revoke",
    ],
    "information_rights": [
        "information",
        "request",
        "union",
        "disclosure",
    ],
    "grievance_deadlines": [
        "deadline",
        "timeliness",
        "filing",
        "days",
        "grievance procedure",
    ],
    "remedy": [
        "remedy",
        "make whole",
        "rescind",
        "reinstate",
        "compensat",
        "relief",
    ],
    "management_authority": [
        "management",
        "employer",
        "operational",
        "postal",
        "may",
        "authority",
    ],
}


def _json_safe(obj):
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    return str(obj)


def _classify_issue_category(text: str) -> list[str]:
    lowered = (text or "").lower()
    return [
        cat
        for cat, signals in ISSUE_CATEGORIES.items()
        if any(sig in lowered for sig in signals)
    ]


def _candidate_record(
    retrieved,
    issue_id: str,
    issue_keywords: list[str],
    dispute_frame: dict,
    rank_before: int | None = None,
) -> dict:
    chunk = retrieved.chunk
    source = chunk.source_document
    text = chunk.text or ""
    meta = retrieved.retrieval_metadata or {}
    combined = float(getattr(retrieved, "combined_score", 0.0))
    gate_pass = passes_retrieval_gate(retrieved, combined)
    direction_penalty = compute_direction_penalty(text, dispute_frame)
    direction_match = compute_direction_match_score(text, dispute_frame)
    overlap = compute_distinctive_overlap_score(text, issue_keywords)

    return {
        "issue_id": issue_id,
        "source_type": source.source_type,
        "document_name": source.name,
        "page": chunk.page_number,
        "chunk_index": chunk.chunk_index,
        "article_or_section": _extract_article(text),
        "combined_score": round(combined, 4),
        "embedding_similarity": round(max(0.0, 1.0 - retrieved.best_embedding_distance), 4),
        "keyword_overlap": round(overlap, 4),
        "direction_penalty": round(direction_penalty, 4),
        "direction_match_score": round(direction_match, 4),
        "passes_retrieval_gate": gate_pass,
        "gate_rejection_reason": None
        if gate_pass
        else f"combined_score={combined:.4f} below MIN_COMBINED={MIN_COMBINED_RETRIEVAL_SCORE}",
        "text_preview": text[:280].replace("\n", " "),
        "issue_categories": _classify_issue_category(text),
        "rank_before_reranking": rank_before,
        "entered_all_chunks": None,
        "entered_ranked_authorities": False,
        "entered_report": False,
        "entered_wrapper": False,
        "final_role": None,
        "post_filter_result": None,
        "rejection_reason": None,
    }


def _extract_article(text: str) -> str:
    import re

    for pattern in (
        r"Article\s+\d+(?:\.\d+)?",
        r"Section\s+\d+(?:\.\d+)?",
        r"ELM\s+\d+(?:\.\d+)?",
    ):
        match = re.search(pattern, text or "", re.IGNORECASE)
        if match:
            return match.group(0)
    return "Unknown"


def _trace_per_source_queries(db, issue: dict, dispute_frame: dict, limit_per_source: int = 8) -> dict:
    """Run retrieval per source type for one issue."""
    per_issue_queries = build_queries_for_issue(issue, dispute_frame)
    result = {"queries": per_issue_queries, "sources": {}}

    for source_type in SOURCE_TYPES:
        chunk_map = KnowledgeRetrievalService._retrieve_queries_into_pool(
            db=db,
            queries=per_issue_queries,
            limit_per_source=limit_per_source,
            issue=issue,
            allowed_source_types={source_type},
        )
        issue_kws = extract_issue_keywords_for_issue(issue, dispute_frame)
        candidates = []
        for retrieved in chunk_map.values():
            score = KnowledgeRetrievalService._score_chunk_match(
                retrieved,
                issue_kws,
                dispute_frame=dispute_frame,
                issue=issue,
            )
            retrieved.combined_score = score
            rec = _candidate_record(retrieved, issue["issue_id"], issue_kws, dispute_frame)
            rec["combined_score"] = round(score, 4)
            rec["passes_retrieval_gate"] = passes_retrieval_gate(retrieved, score)
            candidates.append(rec)
        candidates.sort(key=lambda c: c["combined_score"], reverse=True)
        result["sources"][source_type] = {
            "searched": True,
            "raw_count": len(candidates),
            "passing_gate_count": sum(1 for c in candidates if c["passes_retrieval_gate"]),
            "candidates": candidates,
        }
    return result


def run_diagnostic(run_number: int = 1) -> dict:
    db = SessionLocal()
    try:
        LegalIssueAnalyzer.invalidate_cache()
        issue_analysis = LegalIssueAnalyzer.analyze(FROZEN_QUESTION)
        expanded_queries = LegalIssueAnalyzer.build_search_queries(FROZEN_QUESTION, issue_analysis)
        decomposed = collect_decomposed_issues(issue_analysis)
        dispute_frame = issue_analysis.get("dispute_frame") or {}

        issue_keywords = extract_issue_keywords(
            question=FROZEN_QUESTION,
            analysis=issue_analysis,
            expanded_queries=expanded_queries,
        )

        retrieval = KnowledgeRetrievalService.search_global_corpus_internal(
            db,
            FROZEN_QUESTION,
            principal_id="phase1-1-coverage-diagnostic-internal",
            limit_per_source=8,
        )
        issue_pools = retrieval.get("issue_pools") or {}
        all_chunks = retrieval.get("all_chunks") or []
        retrieved_chunks = retrieval.get("retrieved_chunks") or []

        rank_diag = rank_authorities_with_diagnostics(
            question=FROZEN_QUESTION,
            chunks=all_chunks,
            issue_analysis=issue_analysis,
            issue_keywords=issue_keywords,
            retrieval_gaps=list(retrieval.get("retrieval_gaps") or []),
        )
        ranked = rank_diag.get("ranked_authorities") or []

        report_payload = AnalysisService.generate_report(
            question=FROZEN_QUESTION,
            chunks=all_chunks,
            issue_analysis=issue_analysis,
            issue_keywords=issue_keywords,
            all_chunks=all_chunks,
            retrieval_gaps_list=retrieval.get("retrieval_gaps"),
            indexed_source_types=retrieval.get("indexed_source_types"),
        )

        inner = report_payload.get("report") or {}
        ranked_final = report_payload.get("ranked_authorities") or []

        chunk_key_to_ranked = {}
        for idx, item in enumerate(ranked):
            chunk = item.get("chunk")
            if chunk:
                key = (chunk.source_document_id, chunk.page_number, chunk.chunk_index)
                chunk_key_to_ranked[key] = {
                    "rank_after_reranking": idx + 1,
                    "role": item.get("role"),
                    "relevance_score": item.get("relevance_score"),
                    "article_or_section": item.get("article_or_section"),
                    "direct_quote": (item.get("direct_quote") or "")[:200],
                }

        per_issue_source_trace = {}
        for issue in decomposed:
            per_issue_source_trace[issue["issue_id"]] = {
                "issue_type": issue.get("issue_type"),
                "issue_text": issue.get("issue"),
                "issue_categories": _classify_issue_category(
                    " ".join(
                        [
                            str(issue.get("issue") or ""),
                            " ".join(issue.get("search_queries") or []),
                        ]
                    )
                ),
                "source_trace": _trace_per_source_queries(db, issue, dispute_frame),
                "pool_size": len(issue_pools.get(issue["issue_id"], [])),
                "pool_by_source": _pool_source_counts(issue_pools.get(issue["issue_id"], [])),
            }

        all_candidate_map: dict[tuple, dict] = {}
        for issue_id, pool in issue_pools.items():
            issue = next((i for i in decomposed if i["issue_id"] == issue_id), {})
            ikw = extract_issue_keywords_for_issue(issue, dispute_frame)
            for rank_idx, retrieved in enumerate(pool):
                key = (
                    retrieved.chunk.source_document_id,
                    retrieved.chunk.page_number,
                    retrieved.chunk.chunk_index,
                )
                if key not in all_candidate_map:
                    all_candidate_map[key] = _candidate_record(
                        retrieved, issue_id, ikw, dispute_frame, rank_before=rank_idx + 1
                    )
                all_candidate_map[key]["entered_all_chunks"] = any(
                    c.source_document_id == key[0]
                    and c.page_number == key[1]
                    and c.chunk_index == key[2]
                    for c in all_chunks
                )

        filtered_lookup = {
            (f.get("document_type"), f.get("page"), f.get("chunk_index")): f.get("filter_reason")
            for f in rank_diag.get("filtered") or []
        }
        kept_lookup = {
            (k.get("document_type"), k.get("page"), k.get("chunk_index")): k
            for k in rank_diag.get("kept") or []
        }

        for key, rec in all_candidate_map.items():
            chunk = None
            for c in all_chunks:
                ck = (c.source_document_id, c.page_number, c.chunk_index)
                if ck == key:
                    chunk = c
                    break
            if key in chunk_key_to_ranked:
                rec["entered_ranked_authorities"] = True
                rec["rank_after_reranking"] = chunk_key_to_ranked[key]["rank_after_reranking"]
                rec["final_role"] = chunk_key_to_ranked[key]["role"]
                rec["relevance_score"] = chunk_key_to_ranked[key]["relevance_score"]
            lookup_key = (rec["source_type"], rec["page"], rec["chunk_index"])
            if lookup_key in filtered_lookup:
                rec["post_filter_result"] = "rejected"
                rec["rejection_reason"] = filtered_lookup[lookup_key]
            elif lookup_key in kept_lookup:
                rec["post_filter_result"] = "retained"
            rec["entered_report"] = any(
                ra.get("page") == rec["page"]
                and ra.get("chunk_index") == rec["chunk_index"]
                and str(ra.get("document_type", "")).upper() == rec["source_type"]
                for ra in ranked_final
            )
            rec["entered_wrapper"] = rec["entered_report"]

        source_summary = {}
        for st in SOURCE_TYPES:
            pool_candidates = [c for c in all_candidate_map.values() if c["source_type"] == st]
            ranked_candidates = [c for c in pool_candidates if c["entered_ranked_authorities"]]
            report_candidates = [c for c in pool_candidates if c["entered_report"]]
            source_summary[st] = {
                "pool_candidates": len(pool_candidates),
                "ranked": len(ranked_candidates),
                "in_report": len(report_candidates),
                "articles": sorted({c["article_or_section"] for c in pool_candidates}),
            }

        article10_records = [
            c for c in all_candidate_map.values() if "10" in (c.get("article_or_section") or "")
        ]

        return {
            "run_number": run_number,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "frozen_question": FROZEN_QUESTION,
            "decomposition": {
                "dispute_frame": dispute_frame,
                "decomposed_issues": [
                    {
                        "issue_id": i.get("issue_id"),
                        "issue_type": i.get("issue_type"),
                        "issue": i.get("issue"),
                        "search_queries": i.get("search_queries"),
                        "possible_sources": i.get("possible_sources"),
                    }
                    for i in decomposed
                ],
                "expanded_queries": expanded_queries,
            },
            "retrieval": {
                "total_retrieved_chunks": len(retrieved_chunks),
                "all_chunks_count": len(all_chunks),
                "retrieval_gaps": retrieval.get("retrieval_gaps"),
                "indexed_source_types": sorted(retrieval.get("indexed_source_types") or []),
                "merge_metadata": retrieval.get("merge_metadata"),
                "source_types_in_pool": sorted(
                    {
                        (r.chunk.source_document.source_type if r.chunk.source_document else "")
                        for r in retrieved_chunks
                    }
                ),
            },
            "per_issue_source_trace": per_issue_source_trace,
            "all_candidates": list(all_candidate_map.values()),
            "source_summary": source_summary,
            "ranking": {
                "candidates_in": rank_diag.get("candidates_in"),
                "llm_raw_count": rank_diag.get("llm_raw_count"),
                "authorities_out": rank_diag.get("authorities_out"),
                "filtered": rank_diag.get("filtered"),
                "kept": rank_diag.get("kept"),
                "coverage_gaps": rank_diag.get("coverage_gaps"),
            },
            "report": {
                "ranked_count": len(ranked_final),
                "distinct_authorities": _count_distinct_authorities(ranked_final),
                "source_mix": sorted(
                    {str(r.get("document_type", "")).upper() for r in ranked_final}
                ),
                "authorities": [
                    {
                        "role": r.get("role"),
                        "document_type": r.get("document_type"),
                        "article_or_section": r.get("article_or_section"),
                        "page": r.get("page"),
                        "direct_quote_preview": (r.get("direct_quote") or "")[:180],
                    }
                    for r in ranked_final
                ],
                "remedy_authority": inner.get("remedy_authority") or [],
                "retrieval_gaps_report": report_payload.get("retrieval_gaps"),
            },
            "article10_analysis": article10_records,
        }
    finally:
        db.close()


def _pool_source_counts(pool: list) -> dict:
    counts: dict[str, int] = {}
    for item in pool:
        st = item.chunk.source_document.source_type if item.chunk.source_document else "?"
        counts[st] = counts.get(st, 0) + 1
    return counts


def _count_distinct_authorities(ranked: list) -> int:
    seen = set()
    for item in ranked:
        key = (
            str(item.get("article_or_section", "")).lower(),
            str(item.get("document_name", "")).lower(),
            item.get("page"),
        )
        seen.add(key)
    return len(seen)


def write_markdown(payload: dict) -> None:
    lines = [
        "# Phase 1.1 — Source Coverage Diagnostic",
        "",
        f"**Generated:** {payload.get('generated_at')}",
        f"**Frozen question:** {FROZEN_QUESTION}",
        "",
        "## Decomposition",
        "",
        f"- Issues: {len(payload['runs'][0]['decomposition']['decomposed_issues'])}",
        f"- Dispute frame: `{json.dumps(payload['runs'][0]['decomposition']['dispute_frame'], ensure_ascii=False)[:800]}`",
        "",
    ]

    for issue in payload["runs"][0]["decomposition"]["decomposed_issues"]:
        lines.append(f"### {issue['issue_id']} ({issue['issue_type']})")
        lines.append(f"- {issue['issue']}")
        trace = payload["runs"][0]["per_issue_source_trace"].get(issue["issue_id"], {})
        st = trace.get("source_trace", {})
        for src in SOURCE_TYPES:
            src_data = st.get("sources", {}).get(src, {})
            lines.append(
                f"- **{src}**: searched={src_data.get('searched')}, "
                f"raw={src_data.get('raw_count')}, passing={src_data.get('passing_gate_count')}"
            )
        lines.append("")

    lines.extend(["## Source summary (run 1)", ""])
    for src, summary in payload["runs"][0]["source_summary"].items():
        lines.append(
            f"- **{src}**: pool={summary['pool_candidates']}, "
            f"ranked={summary['ranked']}, report={summary['in_report']}"
        )

    lines.extend(["", "## Final report authorities", ""])
    for auth in payload["runs"][0]["report"]["authorities"]:
        lines.append(
            f"- `{auth['role']}` | {auth['document_type']} | {auth['article_or_section']} | p.{auth['page']}"
        )

    lines.extend(["", "## Article 10 candidates", ""])
    for rec in payload["runs"][0]["article10_analysis"]:
        lines.append(
            f"- {rec['source_type']} p.{rec['page']} role={rec.get('final_role')} "
            f"direction_penalty={rec.get('direction_penalty')} "
            f"preview={rec['text_preview'][:120]}..."
        )

    if len(payload["runs"]) > 1:
        lines.extend(["", "## Run stability (run 1 vs run 2)", ""])
        mix1 = payload["runs"][0]["report"]["source_mix"]
        mix2 = payload["runs"][1]["report"]["source_mix"]
        lines.append(f"- Run 1 source mix: {mix1}")
        lines.append(f"- Run 2 source mix: {mix2}")
        lines.append(f"- Materially different: {mix1 != mix2}")

    OUTPUT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat()
    runs = []
    errors = []

    for run_num in (1, 2):
        try:
            print(f"=== Diagnostic run {run_num} ===")
            runs.append(run_diagnostic(run_num))
        except Exception as exc:
            errors.append({"run": run_num, "error": str(exc), "traceback": traceback.format_exc()})
            print(traceback.format_exc())

    payload = {
        "generated_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "frozen_question": FROZEN_QUESTION,
        "run_count": len(runs),
        "runs": _json_safe(runs),
        "errors": errors,
        "root_cause_hypotheses": [],
    }

    if len(runs) >= 1:
        r0 = runs[0]
        only_cim = r0["report"]["source_mix"] == ["CIM"]
        payload["root_cause_hypotheses"] = [
            "CIM-only final mix" if only_cim else f"source mix: {r0['report']['source_mix']}",
            f"CONTRACT pool candidates: {r0['source_summary'].get('CONTRACT', {}).get('pool_candidates', 0)}",
            f"ELM pool candidates: {r0['source_summary'].get('ELM', {}).get('pool_candidates', 0)}",
        ]

    OUTPUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    write_markdown(payload)
    print(f"Wrote {OUTPUT_JSON}")
    print(f"Wrote {OUTPUT_MD}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
