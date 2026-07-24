"""Read-only retrieval-agent benchmark with safe, text-free output.

This command performs one query embedding and never prints the query, chunk
text, credentials, paths, database URL, or provider response bodies.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from sqlalchemy import event


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database.session import SessionLocal, engine  # noqa: E402
from app.services.retrieval.models import (  # noqa: E402
    RetrievalAuthorizationContext,
    RetrievalRequest,
)
from app.services.retrieval.orchestrator import RetrievalOrchestrator  # noqa: E402


DEFAULT_SAFE_QUERY = (
    "Contract requirements and supervisor procedures for grievance handling, "
    "Step 1 meetings, time and attendance documentation, attendance control, "
    "and employee safety responsibilities."
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", default=DEFAULT_SAFE_QUERY)
    parser.add_argument(
        "--domain",
        choices=("auto", "contract", "supervisor_manual", "combined"),
        default="combined",
    )
    parser.add_argument("--candidate-limit", type=int, default=48)
    parser.add_argument("--result-limit", type=int, default=12)
    args = parser.parse_args()

    query_count = 0

    def count_query(*_args) -> None:
        nonlocal query_count
        query_count += 1

    event.listen(engine, "before_cursor_execute", count_query)
    db = SessionLocal()
    try:
        result = RetrievalOrchestrator().retrieve(
            db,
            RetrievalRequest(
                query=args.query,
                domain=args.domain,
                candidate_limit=args.candidate_limit,
                result_limit=args.result_limit,
                include_diagnostics=True,
            ),
            RetrievalAuthorizationContext.global_corpus(
                principal_id="retrieval-diagnostic",
                correlation_id="retrieval-diagnostic",
            ),
        )
    finally:
        db.close()
        event.remove(engine, "before_cursor_execute", count_query)

    diagnostics = result.to_dict(
        include_text=False,
        include_diagnostics=True,
    ).get("diagnostics", {})
    payload = {
        "status": result.status,
        "partial": result.partial,
        "selected_agents": list(result.selected_agents),
        "query_hash": result.query_hash,
        "sql_query_count_observed": query_count,
        "metrics": diagnostics,
        "results": [
            {
                "canonical_source_id": item.canonical_source_id,
                "source_type": item.source_type,
                "source_version": item.source_version,
                "page_number": item.page_number,
                "retrieval_agent": item.retrieval_agent,
                "evidence_role": item.evidence_role,
                "raw_vector_distance": round(item.raw_vector_distance, 6),
                "normalized_score": round(item.normalized_score, 6),
                "final_relevance_score": round(item.final_relevance_score, 6),
            }
            for item in result.results
        ],
        "failures": [failure.to_dict() for failure in result.failures],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if result.status not in {"complete_failure", "authorization_failure"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
