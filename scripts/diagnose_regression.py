"""Comprehensive regression pipeline diagnostic (live DB + OpenAI)."""

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

from sqlalchemy import func, select

from app.database.models import SourceChunk, SourceDocument
from app.database.session import SessionLocal
from app.retrieval_config import (
    DIRECTION_CONTRADICTION_PENALTY,
    MAX_AUTHORITIES_TO_RANKER,
    MIN_AUTHORITY_RELEVANCE_SCORE,
    MIN_KEYWORD_OVERLAP_FOR_MANAGEMENT,
    MIN_KEYWORD_OVERLAP_FOR_SUPPORTING,
    MIN_KEYWORD_OVERLAP_RECLASSIFY_BACKGROUND,
    MIN_MANAGEMENT_LIMITING_RELEVANCE_SCORE,
)
from app.services.analysis_service import AnalysisService
from app.services.authority_ranker import AuthorityRanker
from app.services.knowledge_retrieval_service import KnowledgeRetrievalService
from app.services.legal_issue_analyzer import LegalIssueAnalyzer
from app.services.relevance_utils import (
    collect_decomposed_issues,
    compute_direction_penalty,
    compute_distinctive_overlap_score,
    extract_issue_keywords,
    verify_quote_in_chunk,
)
from tests.test_regression_harness import score_report_completeness

FIXTURE_PATH = ROOT / "tests" / "fixtures" / "regression_questions.json"
OUTPUT_PATH = ROOT / "data" / "reports" / "regression_diagnosis.json"

DB_KEYWORD_PROBES: dict[int, list[tuple[str, str]]] = {
    1: [
        ("annual leave cancel", "%annual%leave%cancell%"),
        ("approved leave cancel", "%approved%leave%"),
        ("information request union", "%information%request%"),
        ("union information request", "%union%information%"),
    ],
    5: [
        ("schedule change notice", "%schedule%change%"),
        ("regular schedule notice", "%regular%schedule%"),
        ("one day notice schedule", "%notice%schedule%"),
    ],
    6: [
        ("unsafe equipment", "%unsafe%equipment%"),
        ("safety inspection equipment", "%safety%inspection%"),
        ("operate unsafe", "%operate%unsafe%"),
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


def filter_drop_reason(item: dict, issue_keywords: list[str], dispute_frame: dict | None) -> str | None:
    role = item.get("role", "background_only")
    if role == "irrelevant":
        return "role_irrelevant"

    relevance_score = item.get("relevance_score", 0)
    chunk = item["chunk"]
    quote = item.get("direct_quote", "")
    overlap = compute_distinctive_overlap_score(chunk.text or "", issue_keywords)
    direction_penalty = compute_direction_penalty(chunk.text or "", dispute_frame)

    if not verify_quote_in_chunk(quote, chunk.text or ""):
        return "quote_not_in_chunk"

    if direction_penalty >= DIRECTION_CONTRADICTION_PENALTY:
        return "direction_contradiction_penalty"

    if role == "management_limiting":
        if relevance_score < MIN_MANAGEMENT_LIMITING_RELEVANCE_SCORE:
            return f"management_limiting_low_relevance({relevance_score})"
        if overlap < MIN_KEYWORD_OVERLAP_FOR_MANAGEMENT:
            return f"management_limiting_low_overlap({overlap:.4f})"
        return None

    if relevance_score < MIN_AUTHORITY_RELEVANCE_SCORE:
        return f"low_relevance_score({relevance_score})"

    if overlap < MIN_KEYWORD_OVERLAP_FOR_SUPPORTING:
        if overlap >= MIN_KEYWORD_OVERLAP_RECLASSIFY_BACKGROUND:
            return None
        return f"low_keyword_overlap({overlap:.4f})"

    return None


def rank_authorities_with_diagnostics(
    question: str,
    chunks: list,
    issue_analysis: dict,
    issue_keywords: list[str],
    retrieval_gaps: list | None = None,
) -> dict:
    import json as json_mod

    from openai import OpenAI

    if not chunks:
        return {
            "candidates_in": 0,
            "llm_raw_count": 0,
            "after_irrelevant_skip": 0,
            "authorities_out": 0,
            "kept": [],
            "filtered": [],
            "ranked_authorities": [],
            "coverage_gaps": [],
        }

    dispute_frame = (issue_analysis or {}).get("dispute_frame")
    decomposed_issues = collect_decomposed_issues(issue_analysis)

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
                "text": (chunk.text or "")[:3000],
                "retrieval_hints": metadata,
            }
        )

    from app.services.relevance_utils import (
        build_dispute_frame_summary,
        build_issue_context_summary,
    )

    issue_context = build_issue_context_summary(issue_analysis)
    dispute_context = build_dispute_frame_summary(dispute_frame)

    client = OpenAI(api_key=__import__("os").getenv("OPENAI_API_KEY"))
    max_authorities = MAX_AUTHORITIES_TO_RANKER

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an expert NPMHU and USPS grievance authority ranking engine. "
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
{json_mod.dumps(candidates, indent=2)}

Return JSON exactly like this:

{{
  "ranked_authorities": [
    {{
      "ref_id": "S1",
      "relevance_score": 97,
      "role": "union_supporting",
      "legal_issue": "What issue this authority supports",
      "article_or_section": "Exact article/section if visible, otherwise Unknown",
      "authority_type": "Union-Supporting",
      "direct_quote": "Exact quote copied from the excerpt",
      "why_it_matters": "Explain steward use"
    }}
  ]
}}

Rules:
- Return no more than {max_authorities} authorities.
- Direct quotes must be copied exactly from the excerpt.
""",
            },
        ],
    )

    parsed = AuthorityRanker._safe_json_loads(
        response.choices[0].message.content,
        {"ranked_authorities": []},
    )

    pre_ranked: list[dict] = []
    skipped_irrelevant = 0
    invalid_ref = 0

    for item in parsed.get("ranked_authorities", []):
        ref_id = item.get("ref_id")
        if ref_id not in chunk_map:
            invalid_ref += 1
            continue
        chunk = chunk_map[ref_id]
        source = chunk.source_document
        role = item.get("role", "background_only")
        if role == "irrelevant":
            skipped_irrelevant += 1

        pre_ranked.append(
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
                "retrieval_metadata": getattr(chunk, "retrieval_metadata", {}) or {},
            }
        )

    filtered_records = []
    kept_records = []

    for item in pre_ranked:
        reason = filter_drop_reason(item, issue_keywords, dispute_frame)
        summary = {
            "ref_id": item.get("ref_id"),
            "document_type": item.get("document_type"),
            "page": item.get("page"),
            "chunk_index": item.get("chunk_index"),
            "role": item.get("role"),
            "relevance_score": item.get("relevance_score"),
            "article_or_section": item.get("article_or_section"),
            "direct_quote_preview": (item.get("direct_quote") or "")[:120],
        }
        if reason:
            summary["filter_reason"] = reason
            filtered_records.append(summary)
        else:
            kept_records.append(summary)

    ranked = AuthorityRanker._apply_post_filters(
        [i for i in pre_ranked if i.get("role") != "irrelevant"],
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
    ranked = ranked[:max_authorities]

    coverage_gaps = AuthorityRanker._ensure_multi_issue_coverage(
        ranked,
        decomposed_issues,
        chunks,
    )
    if retrieval_gaps is not None:
        retrieval_gaps.extend(coverage_gaps)

    return {
        "candidates_in": len(chunks),
        "llm_raw_count": len(parsed.get("ranked_authorities", [])),
        "invalid_ref_ids": invalid_ref,
        "skipped_irrelevant": skipped_irrelevant,
        "pre_filter_count": len(pre_ranked),
        "authorities_out": len(ranked),
        "kept": kept_records,
        "filtered": filtered_records,
        "ranked_authorities": ranked,
        "coverage_gaps": coverage_gaps,
    }


def chunk_summary(retrieved) -> dict:
    chunk = retrieved.chunk
    meta = retrieved.retrieval_metadata or {}
    source = chunk.source_document
    text = chunk.text or ""
    return {
        "document_type": source.source_type,
        "document_name": source.name,
        "page": chunk.page_number,
        "chunk_index": chunk.chunk_index,
        "combined_score": round(float(getattr(retrieved, "combined_score", 0.0)), 4),
        "embedding_similarity": meta.get("embedding_similarity"),
        "keyword_overlap": meta.get("keyword_overlap"),
        "direction_penalty": meta.get("direction_penalty"),
        "substantive_score": meta.get("substantive_score"),
        "text_preview": text[:180].replace("\n", " "),
    }


def probe_db_keywords(db, probes: list[tuple[str, str]], limit: int = 5) -> list[dict]:
    results = []
    for label, pattern in probes:
        stmt = (
            select(SourceChunk, SourceDocument)
            .join(SourceDocument, SourceChunk.source_document_id == SourceDocument.id)
            .where(func.lower(SourceChunk.text).like(pattern.lower()))
        )
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = db.scalar(count_stmt) or 0

        rows = db.execute(stmt.limit(limit)).all()
        samples = []
        for chunk, doc in rows:
            samples.append(
                {
                    "source_type": doc.source_type,
                    "document_name": doc.name,
                    "page": chunk.page_number,
                    "chunk_index": chunk.chunk_index,
                    "snippet": (chunk.text or "")[:220].replace("\n", " "),
                }
            )
        results.append({"label": label, "pattern": pattern, "count": total, "samples": samples})
    return results


def infer_failure_stage(record: dict) -> dict:
    stages = []
    decomp = record.get("decomposition") or {}
    retrieval = record.get("retrieval") or {}
    ranking = record.get("ranking") or {}
    report = record.get("report") or {}

    issue_count = decomp.get("decomposed_issues_count") or 0
    if issue_count == 0:
        stages.append("decomposition")

    total_chunks = retrieval.get("total_chunks") or 0
    retrieval_gaps = retrieval.get("retrieval_gaps") or []
    if total_chunks == 0 or retrieval_gaps:
        stages.append("retrieval")

    if (report.get("ranked_count") or 0) == 0 and total_chunks > 0:
        stages.append("ranking")

    citation_status = str(report.get("citation_status") or "").lower()
    if citation_status in {"failed", "fail", "needs review"}:
        stages.append("citation")

    completeness = record.get("completeness_score")
    if completeness == "FAIL" and not stages:
        stages.append("unknown")

    return {
        "failed_stages": stages or (["none"] if completeness == "PASS" else ["unknown"]),
        "primary_failure": stages[0] if stages else None,
    }


def run_question(db, item: dict, limit_per_source: int = 8) -> dict:
    index = item["index"]
    question = item["question"]
    log_lines: list[str] = []

    def log(msg: str) -> None:
        print(msg)
        log_lines.append(msg)

    log(f"\n{'=' * 72}\nQ{index}: {question}\n{'=' * 72}")

    LegalIssueAnalyzer.invalidate_cache()

    issue_analysis = LegalIssueAnalyzer.analyze(question)
    expanded_queries = LegalIssueAnalyzer.build_search_queries(question, issue_analysis)
    decomposed = collect_decomposed_issues(issue_analysis)
    dispute_frame = issue_analysis.get("dispute_frame") or {}

    log("--- LegalIssueAnalyzer.analyze ---")
    log(f"dispute_frame: {json.dumps(dispute_frame, ensure_ascii=False)[:1200]}")
    log(f"decomposed_issues_count: {len(decomposed)}")
    log(f"search_queries ({len(expanded_queries)}): {expanded_queries[:20]}")

    retrieval = KnowledgeRetrievalService.search_global_corpus_internal(
        db,
        question,
        principal_id="diagnose-regression-internal",
        limit_per_source=limit_per_source,
    )

    retrieved_chunks = retrieval.get("retrieved_chunks") or []
    issue_pools = retrieval.get("issue_pools") or {}
    retrieval_gaps = list(retrieval.get("retrieval_gaps") or [])

    log("--- KnowledgeRetrievalService.search_all ---")
    log(f"total_chunks: {len(retrieved_chunks)}")
    for issue_id, pool in issue_pools.items():
        log(f"  pool {issue_id}: {len(pool)} chunks")
    log(f"retrieval_gaps: {json.dumps(retrieval_gaps, ensure_ascii=False)}")
    top5 = sorted(
        retrieved_chunks,
        key=lambda r: getattr(r, "combined_score", 0.0),
        reverse=True,
    )[:5]
    log("top_5_chunks_by_combined_score:")
    for row in top5:
        log(f"  {json.dumps(chunk_summary(row), ensure_ascii=False)}")
    source_types = sorted(
        {
            (getattr(r.chunk.source_document, "source_type", None) or "")
            for r in retrieved_chunks
        }
    )
    log(f"source_types_found: {source_types}")

    issue_keywords = extract_issue_keywords(
        question=question,
        analysis=issue_analysis,
        expanded_queries=expanded_queries,
    )

    rank_diag = rank_authorities_with_diagnostics(
        question=question,
        chunks=retrieval.get("all_chunks") or [],
        issue_analysis=issue_analysis,
        issue_keywords=issue_keywords,
        retrieval_gaps=retrieval_gaps,
    )

    log("--- AuthorityRanker.rank_authorities (diagnostic) ---")
    log(f"candidates_in: {rank_diag['candidates_in']}")
    log(f"llm_raw_count: {rank_diag['llm_raw_count']}")
    log(f"authorities_out: {rank_diag['authorities_out']}")
    for filt in rank_diag.get("filtered") or []:
        log(f"  FILTERED {filt.get('ref_id')}: {filt.get('filter_reason')} ({filt.get('document_type')} p{filt.get('page')})")
    for kept in rank_diag.get("kept") or []:
        log(f"  KEPT {kept.get('ref_id')}: {kept.get('role')} score={kept.get('relevance_score')}")

    report_payload = AnalysisService.generate_report(
        question=question,
        chunks=retrieval.get("all_chunks") or [],
        issue_analysis=issue_analysis,
        issue_keywords=issue_keywords,
        all_chunks=retrieval.get("all_chunks") or [],
        retrieval_gaps_list=retrieval.get("retrieval_gaps"),
        indexed_source_types=retrieval.get("indexed_source_types"),
    )

    inner_report = report_payload.get("report") or {}
    citation = inner_report.get("citation_validation") or {}
    violations = inner_report.get("key_contract_violations") or []
    ranked_final = report_payload.get("ranked_authorities") or []

    completeness = score_report_completeness(report_payload)

    log("--- AnalysisService.generate_report ---")
    log(f"final_ranked_count: {len(ranked_final)}")
    log(f"key_violations_count: {len(violations)}")
    log(f"citation_status: {citation.get('status')}")
    log(f"score_report_completeness: {completeness}")

    db_probes = None
    if index in DB_KEYWORD_PROBES:
        log("--- Direct DB keyword probes ---")
        db_probes = probe_db_keywords(db, DB_KEYWORD_PROBES[index])
        for probe in db_probes:
            log(f"  [{probe['label']}] count={probe['count']} pattern={probe['pattern']}")
            for sample in probe.get("samples") or []:
                log(f"    sample: {sample['source_type']} {sample['snippet'][:100]}...")

    record = {
        "index": index,
        "question": question,
        "decomposition": {
            "dispute_frame": dispute_frame,
            "decomposed_issues_count": len(decomposed),
            "decomposed_issues": [
                {
                    "issue_id": i.get("issue_id"),
                    "issue_type": i.get("issue_type"),
                    "issue": i.get("issue"),
                }
                for i in decomposed
            ],
            "search_queries": expanded_queries,
        },
        "retrieval": {
            "total_chunks": len(retrieved_chunks),
            "per_issue_pool_sizes": {k: len(v) for k, v in issue_pools.items()},
            "retrieval_gaps": retrieval_gaps,
            "top_5_chunks": [chunk_summary(r) for r in top5],
            "source_types_found": source_types,
            "merge_metadata": retrieval.get("merge_metadata"),
        },
        "ranking": {
            "candidates_in": rank_diag["candidates_in"],
            "llm_raw_count": rank_diag["llm_raw_count"],
            "authorities_out": len(ranked_final),
            "diagnostic_authorities_out": rank_diag["authorities_out"],
            "filtered_authorities": rank_diag.get("filtered"),
            "kept_authorities": rank_diag.get("kept"),
            "coverage_gaps": rank_diag.get("coverage_gaps"),
        },
        "report": {
            "ranked_count": len(ranked_final),
            "key_violations_count": len(violations),
            "citation_status": citation.get("status"),
            "citation_details": citation,
            "retrieval_gaps_report": report_payload.get("retrieval_gaps"),
        },
        "completeness_score": completeness,
        "db_keyword_probes": db_probes,
        "log_excerpt": "\n".join(log_lines[-40:]),
    }
    record["failure_analysis"] = infer_failure_stage(record)
    return record


def main() -> int:
    questions = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    started = datetime.now(timezone.utc).isoformat()
    results: list[dict] = []
    errors: list[dict] = []

    db = SessionLocal()
    try:
        for item in questions:
            try:
                results.append(run_question(db, item))
            except Exception as exc:
                err = {
                    "index": item.get("index"),
                    "question": item.get("question"),
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                }
                errors.append(err)
                print(f"ERROR Q{item.get('index')}: {exc}")
                print(traceback.format_exc())
    finally:
        db.close()

    payload = {
        "generated_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "fixture": str(FIXTURE_PATH),
        "question_count": len(questions),
        "results": _json_safe(results),
        "errors": errors,
        "summaries": [
            {
                "index": r["index"],
                "completeness_score": r.get("completeness_score"),
                "failure_analysis": r.get("failure_analysis"),
                "total_chunks": (r.get("retrieval") or {}).get("total_chunks"),
                "authorities_out": (r.get("report") or {}).get("ranked_count"),
                "db_keyword_probes": r.get("db_keyword_probes"),
            }
            for r in results
        ],
    }

    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {OUTPUT_PATH}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

