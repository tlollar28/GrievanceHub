import re
from collections import Counter

from sqlalchemy.orm import Session

from app.retrieval_config import (
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
    collect_decomposed_issues,
    extract_issue_keywords,
    extract_issue_keywords_for_issue,
    is_boilerplate_chunk,
    merge_issue_retrieval_pools,
    passes_retrieval_gate,
    score_chunk_for_issue,
)


class KnowledgeRetrievalService:
    @staticmethod
    def _get_indexed_source_types(db: Session) -> set[str]:
        from app.database.models import SourceChunk, SourceDocument

        rows = (
            db.query(SourceDocument.source_type)
            .join(SourceChunk, SourceChunk.source_document_id == SourceDocument.id)
            .filter(SourceChunk.embedding.isnot(None))
            .distinct()
            .all()
        )
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
        )

    @staticmethod
    def _retrieve_queries_into_pool(
        db: Session,
        queries: list[str],
        limit_per_source: int,
        issue: dict | None = None,
        allowed_source_types: set[str] | None = None,
    ) -> dict[tuple, RetrievedChunk]:
        chunk_map: dict[tuple, RetrievedChunk] = {}

        for expanded_query in queries:
            query_embedding = EmbeddingService.create_embedding(expanded_query)

            for provider in KnowledgeRetrievalService.providers:
                if (
                    allowed_source_types is not None
                    and provider.source_type not in allowed_source_types
                ):
                    continue

                results = provider.search(
                    db=db,
                    query_embedding=query_embedding,
                    limit=limit_per_source,
                )

                for chunk, distance in results:
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
            )
            if passes_retrieval_gate(retrieved, score):
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
                queries=backfill_queries[:8],
                limit_per_source=limit_per_source,
                issue=issue,
                allowed_source_types=indexed_source_types,
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
    def search_all(
        db: Session,
        query: str,
        limit_per_source: int = 8,
        known_facts: list[str] | None = None,
    ):
        from app.services.legal_issue_analyzer import LegalIssueAnalyzer

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
        decomposed_issues = collect_decomposed_issues(analysis)
        issue_pools: dict[str, list[RetrievedChunk]] = {}
        retrieval_gaps: list[dict] = []

        for issue in decomposed_issues:
            issue_id = issue["issue_id"]
            per_issue_queries = build_queries_for_issue(issue, dispute_frame)

            if not per_issue_queries:
                per_issue_queries = [str(issue.get("issue") or query).strip()]

            chunk_map = KnowledgeRetrievalService._retrieve_queries_into_pool(
                db=db,
                queries=per_issue_queries,
                limit_per_source=limit_per_source,
                issue=issue,
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
                )

                if passes_retrieval_gate(retrieved, score):
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
        global_queries = [query] + expanded_queries[:8]
        global_map = KnowledgeRetrievalService._retrieve_queries_into_pool(
            db=db,
            queries=global_queries,
            limit_per_source=limit_per_source,
            issue=None,
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
                )
                if scored > best_score:
                    best_score = scored
                    best_issue_id = issue["issue_id"]
                    best_issue = issue
                    best_keywords = ikw

            if not passes_retrieval_gate(retrieved, best_score):
                continue

            KnowledgeRetrievalService._score_chunk_match(
                retrieved,
                best_keywords,
                dispute_frame=dispute_frame,
                issue=best_issue,
                global_keywords=issue_keywords,
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

        indexed_source_types = KnowledgeRetrievalService._get_indexed_source_types(db)

        KnowledgeRetrievalService._backfill_empty_issue_pools(
            db=db,
            issue_pools=issue_pools,
            decomposed_issues=decomposed_issues,
            dispute_frame=dispute_frame,
            issue_keywords=issue_keywords,
            limit_per_source=limit_per_source,
            indexed_source_types=indexed_source_types,
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

            if len(grouped_results[source_type]) >= limit_per_source:
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
            "limit_per_source": limit_per_source,
            "results_by_source": grouped_results,
            "all_chunks": all_chunks,
            "retrieved_chunks": retrieved_chunks,
            "issue_pools": issue_pools,
            "merge_metadata": merge_metadata,
            "retrieval_gaps": retrieval_gaps,
            "indexed_source_types": indexed_source_types,
        }
