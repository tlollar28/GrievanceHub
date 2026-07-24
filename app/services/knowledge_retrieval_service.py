import re
from collections import Counter

from sqlalchemy.orm import Session

from app.retrieval_config import (
    LEGACY_MAX_BACKFILL_QUERIES,
    LEGACY_MAX_DECOMPOSED_ISSUES,
    LEGACY_MAX_GLOBAL_EXPANDED_QUERIES,
    LEGACY_MAX_LIMIT_PER_SOURCE,
    LEGACY_MAX_PROVIDER_CALLS,
    LEGACY_MAX_QUERIES_PER_ISSUE,
    LEGACY_MAX_TOTAL_CANDIDATE_CHUNKS,
    LEGACY_MAX_TOTAL_EMBEDDING_CALLS,
    MAX_CHUNKS_TO_RANKER,
    MIN_EMBEDDING_SIMILARITY,
)
from app.services.embedding_service import EmbeddingService
from app.services.analysis_service import AnalysisService
from app.services.providers.contract_provider import ContractProvider
from app.services.providers.elm_provider import ELMProvider
from app.services.providers.cim_provider import CIMProvider
from app.services.providers.lmou_provider import LMOUProvider
from app.services.relevance_utils import (
    RetrievedChunk,
    build_issue_type_backfill_queries,
    build_queries_for_issue,
    build_source_type_backfill_queries,
    collect_decomposed_issues,
    extract_issue_keywords,
    extract_issue_keywords_for_issue,
    is_boilerplate_chunk,
    merge_issue_retrieval_pools,
    passes_retrieval_gate,
    dispute_concerns_management_revoking_approved_leave,
    passage_describes_management_leave_commitment,
    passage_states_employee_entitlement_rule,
    score_chunk_for_issue,
)


class KnowledgeRetrievalService:
    @staticmethod
    def _get_indexed_source_types(db: Session, authorization=None) -> set[str]:
        from app.database.models import SourceChunk, SourceDocument
        from app.services.providers.base_provider import BaseProvider

        query = (
            db.query(SourceDocument.source_type)
            .join(SourceChunk, SourceChunk.source_document_id == SourceDocument.id)
            .filter(SourceChunk.embedding.isnot(None))
        )
        # Reuse provider authorization predicates without inventing a provider.
        helper = BaseProvider.__new__(BaseProvider)
        predicates = helper._authorization_predicates(authorization)
        if len(predicates) == 1:
            query = query.filter(predicates[0])
        elif predicates:
            from sqlalchemy import or_

            query = query.filter(or_(*predicates))
        rows = query.distinct().all()
        return {
            str(row[0]).upper()
            for row in rows
            if row and row[0]
        }

    providers = [
        ContractProvider(),
        ELMProvider(),
        CIMProvider(),
        LMOUProvider(),
    ]

    STOPWORDS = {
        "a", "an", "and", "are", "as", "at", "be", "been", "by", "can",
        "did", "do", "does", "for", "from", "has", "have", "he", "her",
        "his", "how", "i", "if", "in", "is", "it", "its", "me", "my",
        "not", "of", "on", "or", "our", "she", "should", "that", "the",
        "their", "them", "then", "there", "they", "this", "to", "under",
        "was", "we", "were", "what", "when", "where", "which", "who",
        "why", "will", "with", "without", "you", "your",
    }

    @staticmethod
    def extract_keywords(query: str) -> list[str]:
        words = re.findall(r"[a-zA-Z0-9.']+", query.lower())

        keywords = [
            word
            for word in words
            if len(word) >= 4 and word not in KnowledgeRetrievalService.STOPWORDS
        ]

        counts = Counter(keywords)

        return [
            word
            for word, _ in counts.most_common(12)
        ]

    @staticmethod
    def extract_article_mentions(query: str) -> list[str]:
        q = query.lower()

        patterns = [
            r"article\s+\d+(?:\.\d+)?",
            r"section\s+\d+(?:\.\d+)?",
            r"elm\s+\d+(?:\.\d+)?",
        ]

        mentions = []

        for pattern in patterns:
            mentions.extend(re.findall(pattern, q))

        return list(dict.fromkeys(mentions))

    @staticmethod
    def _chunk_key(chunk):
        return (
            chunk.source_document_id,
            chunk.page_number,
            chunk.chunk_index,
        )

    @staticmethod
    def _score_chunk_match(
        retrieved: RetrievedChunk,
        issue_keywords: list[str],
        dispute_frame: dict | None = None,
        issue: dict | None = None,
        global_keywords: list[str] | None = None,
        question: str = "",
    ) -> float:
        mention_source = " ".join(issue_keywords)
        if global_keywords:
            mention_source = f"{mention_source} {' '.join(global_keywords)}"
        article_mentions = KnowledgeRetrievalService.extract_article_mentions(
            mention_source
        )

        return score_chunk_for_issue(
            retrieved=retrieved,
            issue_keywords=issue_keywords,
            dispute_frame=dispute_frame,
            issue=issue,
            article_mentions=article_mentions,
            global_keywords=global_keywords,
            question=question,
        )

    @staticmethod
    def _retrieve_queries_into_pool(
        db: Session,
        queries: list[str],
        limit_per_source: int,
        issue: dict | None = None,
        allowed_source_types: set[str] | None = None,
        *,
        authorization=None,
        embedding_cache: dict[str, list[float]] | None = None,
        budget: dict[str, int] | None = None,
    ) -> dict[tuple, RetrievedChunk]:
        chunk_map: dict[tuple, RetrievedChunk] = {}
        cache = embedding_cache if embedding_cache is not None else {}
        counters = budget if budget is not None else {
            "embedding_calls": 0,
            "provider_calls": 0,
            "candidate_chunks": 0,
        }

        deduped_queries = list(
            dict.fromkeys(
                str(item).strip()
                for item in queries
                if item is not None and str(item).strip()
            )
        )[:LEGACY_MAX_QUERIES_PER_ISSUE]

        for expanded_query in deduped_queries:
            if counters["embedding_calls"] >= LEGACY_MAX_TOTAL_EMBEDDING_CALLS:
                break
            if counters["candidate_chunks"] >= LEGACY_MAX_TOTAL_CANDIDATE_CHUNKS:
                break

            if expanded_query in cache:
                query_embedding = cache[expanded_query]
            else:
                query_embedding = EmbeddingService.create_embedding(expanded_query)
                cache[expanded_query] = query_embedding
                counters["embedding_calls"] += 1

            for provider in KnowledgeRetrievalService.providers:
                if counters["provider_calls"] >= LEGACY_MAX_PROVIDER_CALLS:
                    break
                if (
                    allowed_source_types is not None
                    and provider.source_type not in allowed_source_types
                ):
                    continue

                results = provider.search(
                    db=db,
                    query_embedding=query_embedding,
                    limit=limit_per_source,
                    authorization=authorization,
                )
                counters["provider_calls"] += 1

                for chunk, distance in results:
                    if counters["candidate_chunks"] >= LEGACY_MAX_TOTAL_CANDIDATE_CHUNKS:
                        break
                    counters["candidate_chunks"] += 1
                    embedding_similarity = max(0.0, 1.0 - float(distance))

                    if embedding_similarity < MIN_EMBEDDING_SIMILARITY:
                        continue

                    if is_boilerplate_chunk(chunk.text or ""):
                        continue

                    key = KnowledgeRetrievalService._chunk_key(chunk)

                    if key not in chunk_map:
                        metadata = {}
                        if issue and issue.get("issue_id"):
                            metadata["matched_issue_ids"] = [issue["issue_id"]]

                        chunk_map[key] = RetrievedChunk(
                            chunk=chunk,
                            best_embedding_distance=float(distance),
                            matched_query_count=1,
                            retrieval_metadata=metadata,
                        )
                    else:
                        existing = chunk_map[key]
                        existing.matched_query_count += 1
                        if float(distance) < existing.best_embedding_distance:
                            existing.best_embedding_distance = float(distance)

                        if issue and issue.get("issue_id"):
                            ids = set(
                                existing.retrieval_metadata.get(
                                    "matched_issue_ids",
                                    [],
                                )
                            )
                            ids.add(issue["issue_id"])
                            existing.retrieval_metadata["matched_issue_ids"] = sorted(
                                ids
                            )

        return chunk_map

    @staticmethod
    def _append_passing_chunks_to_pool(
        chunk_map: dict[tuple, RetrievedChunk],
        pool: list[RetrievedChunk],
        issue_keywords_for_issue: list[str],
        dispute_frame: dict | None,
        issue: dict,
        global_keywords: list[str],
        question: str = "",
    ) -> None:
        existing_keys = {
            KnowledgeRetrievalService._chunk_key(item.chunk) for item in pool
        }
        scored_candidates: list[tuple[float, RetrievedChunk]] = []

        for retrieved in chunk_map.values():
            score = KnowledgeRetrievalService._score_chunk_match(
                retrieved,
                issue_keywords_for_issue,
                dispute_frame=dispute_frame,
                issue=issue,
                global_keywords=global_keywords,
                question=question,
            )
            if passes_retrieval_gate(
                retrieved,
                score,
                dispute_frame=dispute_frame,
                question=question,
            ):
                retrieved.combined_score = score
                scored_candidates.append((score, retrieved))

        scored_candidates.sort(key=lambda item: item[0], reverse=True)

        for _score, retrieved in scored_candidates:
            key = KnowledgeRetrievalService._chunk_key(retrieved.chunk)
            if key in existing_keys:
                continue
            existing_keys.add(key)
            pool.append(retrieved)

    @staticmethod
    def _backfill_empty_issue_pools(
        db: Session,
        issue_pools: dict[str, list[RetrievedChunk]],
        decomposed_issues: list[dict],
        dispute_frame: dict | None,
        issue_keywords: list[str],
        limit_per_source: int,
        indexed_source_types: set[str],
        *,
        authorization=None,
        embedding_cache: dict[str, list[float]] | None = None,
        budget: dict[str, int] | None = None,
    ) -> None:
        """Second-pass retrieval for issue pools still empty after global fallback."""
        for issue in decomposed_issues:
            issue_id = issue.get("issue_id")
            if not issue_id or issue_pools.get(issue_id):
                continue

            issue_type = str(issue.get("issue_type") or "").lower()
            if issue_type == "local_agreement" and "LMOU" not in indexed_source_types:
                continue

            backfill_queries = build_issue_type_backfill_queries(
                issue,
                dispute_frame,
            )
            if not backfill_queries:
                continue

            chunk_map = KnowledgeRetrievalService._retrieve_queries_into_pool(
                db=db,
                queries=backfill_queries[:LEGACY_MAX_BACKFILL_QUERIES],
                limit_per_source=limit_per_source,
                issue=issue,
                allowed_source_types=indexed_source_types,
                authorization=authorization,
                embedding_cache=embedding_cache,
                budget=budget,
            )

            issue_keywords_for_issue = extract_issue_keywords_for_issue(
                issue,
                dispute_frame=dispute_frame,
            )
            pool = issue_pools.setdefault(issue_id, [])
            KnowledgeRetrievalService._append_passing_chunks_to_pool(
                chunk_map,
                pool,
                issue_keywords_for_issue,
                dispute_frame,
                issue,
                issue_keywords,
            )
            pool.sort(key=lambda item: item.combined_score, reverse=True)
            issue_pools[issue_id] = pool

    @staticmethod
    def _backfill_missing_source_types(
        db: Session,
        issue_pools: dict[str, list[RetrievedChunk]],
        decomposed_issues: list[dict],
        dispute_frame: dict | None,
        issue_keywords: list[str],
        limit_per_source: int,
        indexed_source_types: set[str],
        question: str = "",
        *,
        authorization=None,
        embedding_cache: dict[str, list[float]] | None = None,
        budget: dict[str, int] | None = None,
    ) -> list[dict]:
        """One retrieval pass per indexed source type absent from all issue pools."""
        applicable_issue_types = {
            "legal",
            "remedy",
            "timeline",
            "information_rights",
        }
        applicable_issues = [
            issue
            for issue in decomposed_issues
            if str(issue.get("issue_type") or "").lower() in applicable_issue_types
        ]
        if not applicable_issues:
            return []

        pool_source_types: set[str] = set()
        for pool in issue_pools.values():
            for item in pool:
                doc = getattr(item.chunk, "source_document", None)
                if doc and doc.source_type:
                    pool_source_types.add(str(doc.source_type).upper())

        audit: list[dict] = []

        for source_type in sorted(indexed_source_types):
            if source_type == "LMOU" and source_type not in indexed_source_types:
                continue

            if source_type in pool_source_types:
                retained = sum(
                    1
                    for pool in issue_pools.values()
                    for item in pool
                    if str(item.chunk.source_document.source_type or "").upper()
                    == source_type
                )
                audit.append(
                    {
                        "source_type": source_type,
                        "searched": True,
                        "queries_issued": [],
                        "passages_found": retained,
                        "passages_retained": retained,
                        "disposition": "retained_in_pool",
                    }
                )
                continue

            combined_queries: list[str] = []
            for issue in applicable_issues:
                combined_queries.extend(
                    build_queries_for_issue(issue, dispute_frame)[:3]
                )
                combined_queries.extend(
                    build_source_type_backfill_queries(
                        issue,
                        dispute_frame,
                        source_type,
                        question=question,
                    )[
                        :2
                    ]
                )
            combined_queries = list(dict.fromkeys(combined_queries))[
                :LEGACY_MAX_BACKFILL_QUERIES
            ]
            if (
                source_type == "CONTRACT"
                and dispute_concerns_management_revoking_approved_leave(
                    dispute_frame,
                    question,
                )
                and question.strip()
            ):
                combined_queries = list(
                    dict.fromkeys([question.strip()[:160], *combined_queries])
                )[:LEGACY_MAX_BACKFILL_QUERIES]

            chunk_map = KnowledgeRetrievalService._retrieve_queries_into_pool(
                db=db,
                queries=combined_queries,
                limit_per_source=limit_per_source,
                issue=None,
                allowed_source_types={source_type},
                authorization=authorization,
                embedding_cache=embedding_cache,
                budget=budget,
            )

            retained_total = 0
            for issue in applicable_issues:
                issue_id = issue.get("issue_id")
                if not issue_id:
                    continue
                issue_keywords_for_issue = extract_issue_keywords_for_issue(
                    issue,
                    dispute_frame=dispute_frame,
                )
                pool = issue_pools.setdefault(issue_id, [])
                before = len(pool)
                for retrieved in chunk_map.values():
                    metadata = retrieved.retrieval_metadata or {}
                    ids = set(metadata.get("matched_issue_ids") or [])
                    ids.add(issue_id)
                    retrieved.retrieval_metadata = {
                        **metadata,
                        "matched_issue_ids": sorted(ids),
                    }
                KnowledgeRetrievalService._append_passing_chunks_to_pool(
                    chunk_map,
                    pool,
                    issue_keywords_for_issue,
                    dispute_frame,
                    issue,
                    issue_keywords,
                    question=question,
                )
                pool.sort(key=lambda item: item.combined_score, reverse=True)
                issue_pools[issue_id] = pool
                retained_total += max(0, len(pool) - before)

            found = len(chunk_map)
            if retained_total:
                disposition = "retained_in_pool"
            elif found:
                disposition = "none_passed_gates"
            else:
                disposition = "no_embedding_matches"

            audit.append(
                {
                    "source_type": source_type,
                    "searched": True,
                    "queries_issued": combined_queries,
                    "passages_found": found,
                    "passages_retained": retained_total,
                    "disposition": disposition,
                }
            )

            if retained_total:
                pool_source_types.add(source_type)

        return audit

    @staticmethod
    def _pool_has_contract_leave_commitment(
        issue_pools: dict[str, list[RetrievedChunk]],
    ) -> bool:
        for pool in issue_pools.values():
            for item in pool:
                doc = getattr(item.chunk, "source_document", None)
                if not doc or str(doc.source_type or "").upper() != "CONTRACT":
                    continue
                text = item.chunk.text or ""
                if passage_describes_management_leave_commitment(
                    text
                ) or passage_states_employee_entitlement_rule(text):
                    return True
        return False

    @staticmethod
    def _supplement_contract_leave_commitment_pool(
        db: Session,
        issue_pools: dict[str, list[RetrievedChunk]],
        decomposed_issues: list[dict],
        dispute_frame: dict | None,
        issue_keywords: list[str],
        limit_per_source: int,
        question: str,
        *,
        authorization=None,
        embedding_cache: dict[str, list[float]] | None = None,
        budget: dict[str, int] | None = None,
    ) -> None:
        """Extra CONTRACT retrieval when leave-revocation disputes lack commitment language."""
        if not dispute_concerns_management_revoking_approved_leave(
            dispute_frame,
            question,
        ):
            return
        if KnowledgeRetrievalService._pool_has_contract_leave_commitment(issue_pools):
            return

        legal_issues = [
            issue
            for issue in decomposed_issues
            if str(issue.get("issue_type") or "").lower() == "legal"
        ]
        target_issue = legal_issues[0] if legal_issues else None
        if target_issue is None:
            for issue in decomposed_issues:
                if str(issue.get("issue_type") or "").lower() in {
                    "legal",
                    "remedy",
                }:
                    target_issue = issue
                    break

        supplement_queries = [
            question.strip()[:160],
            "national agreement advance annual leave commitment honored emergency",
            "contract approved annual leave must be honored except emergency",
            "previously approved annual leave commitment national agreement",
        ]
        supplement_queries = [
            q for q in dict.fromkeys(supplement_queries) if q and q.strip()
        ]

        chunk_map = KnowledgeRetrievalService._retrieve_queries_into_pool(
            db=db,
            queries=supplement_queries,
            limit_per_source=limit_per_source,
            issue=target_issue,
            allowed_source_types={"CONTRACT"},
            authorization=authorization,
            embedding_cache=embedding_cache,
            budget=budget,
        )

        if not chunk_map:
            return

        issue_id = (
            str(target_issue.get("issue_id") or "global")
            if target_issue
            else "global"
        )
        issue_keywords_for_issue = (
            extract_issue_keywords_for_issue(target_issue, dispute_frame=dispute_frame)
            if target_issue
            else issue_keywords
        )
        pool = issue_pools.setdefault(issue_id, [])

        KnowledgeRetrievalService._append_passing_chunks_to_pool(
            chunk_map,
            pool,
            issue_keywords_for_issue,
            dispute_frame,
            target_issue or {"issue_id": issue_id, "issue_type": "legal", "issue": ""},
            issue_keywords,
            question=question,
        )
        pool.sort(key=lambda item: item.combined_score, reverse=True)
        issue_pools[issue_id] = pool

    @staticmethod
    def retrieve_with_agents(
        db: Session,
        query: str,
        authorization,
        *,
        domain: str = "auto",
        limit_per_source: int = 8,
        result_limit: int | None = None,
        source_types: tuple[str, ...] = (),
        source_ids: tuple[str, ...] = (),
        include_diagnostics: bool = False,
    ):
        """Run the bounded retrieval-agent path.

        ``authorization`` is required. Omitting it is a TypeError at the call
        site; passing ``None`` fails closed inside the orchestrator. Trusted
        global-corpus access must use
        ``retrieve_global_corpus_internal`` or an explicit
        ``RetrievalAuthorizationContext``.
        """
        from app.services.retrieval.models import (
            RetrievalAuthorizationContext,
            RetrievalRequest,
        )
        from app.services.retrieval.orchestrator import RetrievalOrchestrator

        if not isinstance(authorization, RetrievalAuthorizationContext):
            authorization = RetrievalAuthorizationContext.unauthenticated()

        return RetrievalOrchestrator().retrieve(
            db,
            RetrievalRequest(
                query=query,
                domain=domain,
                per_agent_result_limit=limit_per_source,
                per_source_result_limit=limit_per_source,
                result_limit=result_limit or limit_per_source * 2,
                source_types=source_types,
                source_ids=source_ids,
                include_diagnostics=include_diagnostics,
            ),
            authorization,
        )

    @staticmethod
    def retrieve_global_corpus_internal(
        db: Session,
        query: str,
        *,
        principal_id: str,
        domain: str = "auto",
        limit_per_source: int = 8,
        result_limit: int | None = None,
        source_types: tuple[str, ...] = (),
        source_ids: tuple[str, ...] = (),
        include_diagnostics: bool = False,
    ):
        """Explicit trusted-internal global-corpus retrieval.

        API routes must never call this helper. Use only from audited internal
        service code that cannot accept client-supplied scope.
        """
        from app.services.retrieval.models import RetrievalAuthorizationContext

        if not str(principal_id or "").strip():
            raise ValueError("principal_id is required for trusted internal retrieval")

        return KnowledgeRetrievalService.retrieve_with_agents(
            db,
            query,
            RetrievalAuthorizationContext.global_corpus(
                principal_id=str(principal_id).strip(),
            ),
            domain=domain,
            limit_per_source=limit_per_source,
            result_limit=result_limit,
            source_types=source_types,
            source_ids=source_ids,
            include_diagnostics=include_diagnostics,
        )

    @staticmethod
    def search_with_agents(
        db: Session,
        query: str,
        authorization,
        *,
        domain: str = "auto",
        limit_per_source: int = 8,
        include_diagnostics: bool = False,
    ) -> dict:
        """Compatibility JSON adapter for the structured agent result."""
        effective_limit = (
            min(limit_per_source, 5)
            if isinstance(limit_per_source, int)
            and not isinstance(limit_per_source, bool)
            and limit_per_source > 0
            else 1
        )
        result = KnowledgeRetrievalService.retrieve_with_agents(
            db,
            query,
            authorization,
            domain=domain,
            limit_per_source=effective_limit,
            include_diagnostics=include_diagnostics,
        )
        grouped_results = {
            source_type: []
            for source_type in (
                "CONTRACT",
                "ELM",
                "CIM",
                "LMOU",
                "ARBITRATION",
                "SUPERVISOR_MANUAL",
            )
        }
        for evidence in result.results:
            grouped_results.setdefault(evidence.source_type, [])
            if len(grouped_results[evidence.source_type]) >= effective_limit:
                continue
            grouped_results[evidence.source_type].append(
                {
                    "source_id": evidence.canonical_source_id,
                    "document_name": evidence.source_title,
                    "document_type": evidence.source_type,
                    "page": evidence.page_number,
                    "chunk": evidence.chunk_index,
                    "text": evidence.chunk_text,
                    "retrieval_metadata": {
                        "best_embedding_distance": evidence.raw_vector_distance,
                        "embedding_similarity": evidence.raw_vector_similarity,
                        "normalized_score": evidence.normalized_score,
                        "combined_score": evidence.final_relevance_score,
                        "retrieval_agent": evidence.retrieval_agent,
                        "retrieval_domain": evidence.retrieval_domain,
                        "evidence_role": evidence.evidence_role,
                        "content_trust": evidence.content_trust,
                    },
                    "retrieval_relationship": "embedding_retrieval",
                }
            )
        payload = {
            "query": query,
            "limit_per_source": effective_limit,
            "results_by_source": grouped_results,
            "retrieval_status": result.status,
            "partial": result.partial,
            "failures": [failure.to_dict() for failure in result.failures],
        }
        if include_diagnostics:
            payload["diagnostics"] = result.to_dict(
                include_text=False,
                include_diagnostics=True,
            ).get("diagnostics", {})
        return payload

    @staticmethod
    def search_all(
        db: Session,
        query: str,
        authorization,
        limit_per_source: int = 8,
        known_facts: list[str] | None = None,
    ):
        """Issue-decomposition retrieval facade.

        ``authorization`` is required. Trusted global-corpus callers must use
        ``search_global_corpus_internal`` or pass an explicit
        ``RetrievalAuthorizationContext``.
        """
        from app.services.legal_issue_analyzer import LegalIssueAnalyzer
        from app.services.retrieval.models import RetrievalAuthorizationContext

        if not isinstance(authorization, RetrievalAuthorizationContext):
            raise TypeError(
                "search_all requires an explicit RetrievalAuthorizationContext"
            )
        if not authorization.authenticated:
            raise PermissionError("Authentication is required for search_all")

        effective_limit = (
            min(int(limit_per_source), LEGACY_MAX_LIMIT_PER_SOURCE)
            if isinstance(limit_per_source, int)
            and not isinstance(limit_per_source, bool)
            and limit_per_source > 0
            else 1
        )

        analysis = LegalIssueAnalyzer.analyze(
            query,
            known_facts=known_facts,
        )

        expanded_queries = LegalIssueAnalyzer.build_search_queries(
            question=query,
            analysis=analysis,
        )

        issue_keywords = extract_issue_keywords(
            question=query,
            analysis=analysis,
            expanded_queries=expanded_queries,
        )

        dispute_frame = analysis.get("dispute_frame") or {}
        decomposed_issues = collect_decomposed_issues(analysis)[
            :LEGACY_MAX_DECOMPOSED_ISSUES
        ]
        issue_pools: dict[str, list[RetrievedChunk]] = {}
        retrieval_gaps: list[dict] = []
        embedding_cache: dict[str, list[float]] = {}
        budget = {
            "embedding_calls": 0,
            "provider_calls": 0,
            "candidate_chunks": 0,
        }

        for issue in decomposed_issues:
            issue_id = issue["issue_id"]
            per_issue_queries = build_queries_for_issue(issue, dispute_frame)

            if not per_issue_queries:
                per_issue_queries = [str(issue.get("issue") or query).strip()]

            chunk_map = KnowledgeRetrievalService._retrieve_queries_into_pool(
                db=db,
                queries=per_issue_queries,
                limit_per_source=effective_limit,
                issue=issue,
                authorization=authorization,
                embedding_cache=embedding_cache,
                budget=budget,
            )

            issue_keywords_for_issue = extract_issue_keywords_for_issue(
                issue,
                dispute_frame=dispute_frame,
            )

            scored_pool: list[RetrievedChunk] = []

            for retrieved in chunk_map.values():
                score = KnowledgeRetrievalService._score_chunk_match(
                    retrieved,
                    issue_keywords_for_issue,
                    dispute_frame=dispute_frame,
                    issue=issue,
                    global_keywords=issue_keywords,
                    question=query,
                )

                if passes_retrieval_gate(
                    retrieved,
                    score,
                    dispute_frame=dispute_frame,
                    question=query,
                ):
                    scored_pool.append(retrieved)

            scored_pool.sort(
                key=lambda item: item.combined_score,
                reverse=True,
            )

            issue_pools[issue_id] = scored_pool

            if not scored_pool:
                retrieval_gaps.append(
                    {
                        "issue_id": issue_id,
                        "issue_type": issue.get("issue_type"),
                        "issue": issue.get("issue"),
                        "reason": "no_chunks_above_retrieval_threshold",
                    }
                )

        # Global fallback retrieval
        global_queries = [query] + expanded_queries[
            :LEGACY_MAX_GLOBAL_EXPANDED_QUERIES
        ]
        global_map = KnowledgeRetrievalService._retrieve_queries_into_pool(
            db=db,
            queries=global_queries,
            limit_per_source=effective_limit,
            issue=None,
            authorization=authorization,
            embedding_cache=embedding_cache,
            budget=budget,
        )

        for retrieved in global_map.values():
            best_score = 0.0
            best_issue_id = "global"
            best_issue = None
            best_keywords = issue_keywords

            global_score = KnowledgeRetrievalService._score_chunk_match(
                retrieved,
                issue_keywords,
                dispute_frame=dispute_frame,
                issue=None,
                global_keywords=issue_keywords,
                question=query,
            )
            best_score = global_score

            for issue in decomposed_issues:
                ikw = extract_issue_keywords_for_issue(issue, dispute_frame)
                scored = KnowledgeRetrievalService._score_chunk_match(
                    retrieved,
                    ikw,
                    dispute_frame=dispute_frame,
                    issue=issue,
                    global_keywords=issue_keywords,
                    question=query,
                )
                if scored > best_score:
                    best_score = scored
                    best_issue_id = issue["issue_id"]
                    best_issue = issue
                    best_keywords = ikw

            if not passes_retrieval_gate(
                retrieved,
                best_score,
                dispute_frame=dispute_frame,
                question=query,
            ):
                continue

            KnowledgeRetrievalService._score_chunk_match(
                retrieved,
                best_keywords,
                dispute_frame=dispute_frame,
                issue=best_issue,
                global_keywords=issue_keywords,
                question=query,
            )
            retrieved.combined_score = best_score

            pool = issue_pools.setdefault(best_issue_id, [])
            key = KnowledgeRetrievalService._chunk_key(retrieved.chunk)
            existing_keys = {
                KnowledgeRetrievalService._chunk_key(item.chunk) for item in pool
            }
            if key in existing_keys:
                continue

            pool.append(retrieved)

        indexed_source_types = KnowledgeRetrievalService._get_indexed_source_types(
            db,
            authorization=authorization,
        )

        KnowledgeRetrievalService._backfill_empty_issue_pools(
            db=db,
            issue_pools=issue_pools,
            decomposed_issues=decomposed_issues,
            dispute_frame=dispute_frame,
            issue_keywords=issue_keywords,
            limit_per_source=effective_limit,
            indexed_source_types=indexed_source_types,
            authorization=authorization,
            embedding_cache=embedding_cache,
            budget=budget,
        )

        source_coverage_audit = KnowledgeRetrievalService._backfill_missing_source_types(
            db=db,
            issue_pools=issue_pools,
            decomposed_issues=decomposed_issues,
            dispute_frame=dispute_frame,
            issue_keywords=issue_keywords,
            limit_per_source=effective_limit,
            indexed_source_types=indexed_source_types,
            question=query,
            authorization=authorization,
            embedding_cache=embedding_cache,
            budget=budget,
        )

        KnowledgeRetrievalService._supplement_contract_leave_commitment_pool(
            db=db,
            issue_pools=issue_pools,
            decomposed_issues=decomposed_issues,
            dispute_frame=dispute_frame,
            issue_keywords=issue_keywords,
            limit_per_source=effective_limit,
            question=query,
            authorization=authorization,
            embedding_cache=embedding_cache,
            budget=budget,
        )

        retrieval_gaps = [
            gap
            for gap in retrieval_gaps
            if len(issue_pools.get(gap["issue_id"], [])) == 0
        ]

        retrieved_chunks, merge_metadata = merge_issue_retrieval_pools(
            issue_pools,
            MAX_CHUNKS_TO_RANKER,
        )

        all_chunks = [item.chunk for item in retrieved_chunks]

        for chunk, retrieved in zip(all_chunks, retrieved_chunks):
            chunk.retrieval_metadata = retrieved.retrieval_metadata

        grouped_results = {
            provider.source_type: []
            for provider in KnowledgeRetrievalService.providers
        }

        for retrieved in retrieved_chunks:
            chunk = retrieved.chunk
            source_type = chunk.source_document.source_type

            if source_type not in grouped_results:
                continue

            if len(grouped_results[source_type]) >= effective_limit:
                continue

            grouped_results[source_type].append(
                AnalysisService.chunk_to_source_dict(chunk)
            )

        indexed_source_types = sorted(indexed_source_types)

        return {
            "query": query,
            "known_facts": known_facts or [],
            "issue_analysis": analysis,
            "decomposed_issues": decomposed_issues,
            "expanded_queries": expanded_queries,
            "issue_keywords": issue_keywords,
            "keywords": KnowledgeRetrievalService.extract_keywords(query),
            "article_mentions": KnowledgeRetrievalService.extract_article_mentions(
                query
            ),
            "limit_per_source": effective_limit,
            "results_by_source": grouped_results,
            "all_chunks": all_chunks,
            "retrieved_chunks": retrieved_chunks,
            "issue_pools": issue_pools,
            "merge_metadata": merge_metadata,
            "retrieval_gaps": retrieval_gaps,
            "indexed_source_types": indexed_source_types,
            "source_coverage_audit": source_coverage_audit,
            "retrieval_budget": {
                "embedding_calls": budget["embedding_calls"],
                "provider_calls": budget["provider_calls"],
                "candidate_chunks": budget["candidate_chunks"],
                "max_embedding_calls": LEGACY_MAX_TOTAL_EMBEDDING_CALLS,
                "max_provider_calls": LEGACY_MAX_PROVIDER_CALLS,
                "max_candidate_chunks": LEGACY_MAX_TOTAL_CANDIDATE_CHUNKS,
            },
        }

    @staticmethod
    def search_global_corpus_internal(
        db: Session,
        query: str,
        *,
        principal_id: str,
        limit_per_source: int = 8,
        known_facts: list[str] | None = None,
    ):
        """Explicit trusted-internal legacy search over the global corpus.

        API routes must never call this helper.
        """
        from app.services.retrieval.models import RetrievalAuthorizationContext

        if not str(principal_id or "").strip():
            raise ValueError("principal_id is required for trusted internal search")

        return KnowledgeRetrievalService.search_all(
            db,
            query,
            RetrievalAuthorizationContext.global_corpus(
                principal_id=str(principal_id).strip(),
            ),
            limit_per_source=limit_per_source,
            known_facts=known_facts,
        )
