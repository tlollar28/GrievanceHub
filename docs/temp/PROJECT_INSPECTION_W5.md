# GrievanceHub W5 Project Inspection — Retrieval Architecture

**Status:** Temporary working document for the W5 retrieval refactor  
**Workspace:** `C:\Users\tloll\Documents\GrievanceHub`  
**Branch context at inspection:** Treat the workspace codebase as authoritative (latest W5 changes already present). Do **not** restore older implementations or remove existing retrieval behavior without an explicit implementation prompt.  
**Inspection date:** 2026-07-23  
**Scope:** Read-only inspection of retrieval, source processing, providers, scoring/gates/backfill/merge/coverage, public return contracts, callers, tests, and compatibility constraints.

---

## Table of contents

1. [Architecture overview](#1-architecture-overview)
2. [Current retrieval flow](#2-current-retrieval-flow)
3. [Ingestion pipeline](#3-ingestion-pipeline)
4. [Providers](#4-providers)
5. [Source types](#5-source-types)
6. [Database interactions](#6-database-interactions)
7. [Retrieval scoring](#7-retrieval-scoring)
8. [Retrieval gates](#8-retrieval-gates)
9. [Backfill logic](#9-backfill-logic)
10. [Merge logic](#10-merge-logic)
11. [Source-coverage behavior](#11-source-coverage-behavior)
12. [Public API contracts](#12-public-api-contracts)
13. [Dependencies, callers, and tests](#13-dependencies-callers-and-tests)
14. [Import and compatibility constraints](#14-import-and-compatibility-constraints)
15. [Config knobs (`retrieval_config.py`)](#15-config-knobs-retrieval_configpy)
16. [Files inspected](#16-files-inspected)
17. [Refactor-critical notes](#17-refactor-critical-notes)
18. [Condensed flow diagram](#18-condensed-flow-diagram)

---

## 1. Architecture overview

Indexed retrieval depends on **embedded `SourceChunk` rows** in PostgreSQL (pgvector), not on filesystem access at query time.

| Layer | Role relative to retrieval |
|--------|----------------------------|
| **`source_manager.py`** | Offline registry/download (`load_registry`, `update_all_sources` via `scripts/download_sources.py`). **Not imported** by `KnowledgeRetrievalService`. |
| **`SourceSyncService`** | Sets `SourceDocument.local_path` / `sha256` from `uploads/{contract,elm,cim,lmou,...}` or `download_url`. API: `POST /sources/{id}/sync`. |
| **`SourceProcessingService`** | PDF → paragraph chunks → OpenAI `text-embedding-3-small` → `SourceChunk` rows. API: `POST /sources/{id}/process`. Replaces all chunks for a document on re-process. |
| **Providers** (`ContractProvider`, `ELMProvider`, `CIMProvider`, `LMOUProvider`) | Per–source-type cosine-distance search on chunks with non-null embeddings. |
| **`KnowledgeRetrievalService`** | Orchestrates analysis, multi-query retrieval, scoring, gates, backfill, merge. |
| **`relevance_utils.py`** | Shared primitives: `RetrievedChunk`, scoring, gates, backfill query builders, merge, leave-direction helpers. |
| **`LegalIssueAnalyzer`** | Pre-retrieval LLM issue decomposition and query expansion. |
| **`AnalysisService`** | Post-retrieval: `chunk_to_source_dict`, ask/report generation, enrichment of gaps/coverage audit. **Does not call `search_all` itself.** |

**Indexed source types at runtime:** `KnowledgeRetrievalService._get_indexed_source_types(db)` returns distinct uppercased `SourceDocument.source_type` values that have **at least one** `SourceChunk` with `embedding IS NOT NULL`.

There is a parallel offline path (`source_manager` → manifest → `source_parser` → JSON index) that is **not** used by `KnowledgeRetrievalService`. The DB + pgvector path is authoritative for runtime retrieval.

---

## 2. Current retrieval flow

### 2.1 Entry points into `search_all()`

```python
# app/services/knowledge_retrieval_service.py ~545–550
def search_all(
    db: Session,
    query: str,
    limit_per_source: int = 8,
    known_facts: list[str] | None = None,
):
```

| Caller | Path | Notes |
|--------|------|--------|
| `GET /sources/search/` | `app/api/routes/sources.py` ~161 | Returns subset of `search_all` result |
| `GET /sources/ask/` | `app/api/routes/sources.py` ~180 | `search_all` → `AnalysisService.answer_question(chunks=results["all_chunks"], ...)` |
| `GET /sources/report/` | `app/api/routes/sources.py` ~224 | `search_all` → `AnalysisService.generate_report(..., all_chunks, retrieval_gaps_list, indexed_source_types, source_coverage_audit)` |
| `CaseService.build_analysis_report_preview` | `app/services/case_service.py` ~2227 | Same pattern as report route |
| `FollowUpChatService.retrieve_indexed_source_passages` | `app/services/follow_up_chat_service.py` ~293 | Uses `all_chunks` + `AnalysisService.chunk_to_source_dict`; no ranker/report |
| `scripts/diagnose_regression.py` | diagnostic | Uses `retrieved_chunks`, `issue_pools`, `merge_metadata`, report path |
| `scripts/phase1_1_verification.py` | diagnostic | Same report pipeline fields as `/report/` |
| `scripts/phase1_1_source_coverage_diagnostic.py` | diagnostic | `issue_pools`, `all_chunks`, `retrieved_chunks`, `retrieval_gaps`, `indexed_source_types`, `merge_metadata` |

Downstream **report** path uses **`all_chunks`** (merged pool, cap 50), not `results_by_source` (per-type cap `limit_per_source`).

### 2.2 Phase A — Issue analysis and query expansion (inside `search_all`)

1. **`LegalIssueAnalyzer.analyze(query, known_facts=known_facts)`** (lazy-imported at the start of `search_all`).
   - GPT-4o-mini JSON; cached by `(question.lower(), known_facts)`.
   - Normalized shape from `_empty_analysis` / `_normalize_analysis`.

2. **`LegalIssueAnalyzer.build_search_queries(question, analysis)`**.
   - Deduped list: raw question, `primary_issue`, categories, all issue names / `search_queries` / `legal_synonyms` from issue list fields.

3. **`extract_issue_keywords(question, analysis, expanded_queries)`** (`relevance_utils.py`).
   - Up to 30 tokens from question, analysis text, dispute frame summary, expanded queries.

4. **`dispute_frame = analysis.get("dispute_frame") or {}`**

5. **`collect_decomposed_issues(analysis)`**.
   - Flattens `legal_issues`, `remedial_issues`, `timeline_issues`, `information_rights_issues`, `local_agreement_issues` into `{issue_id, issue_type, issue, search_queries, legal_synonyms}`.
   - Fallback single issue `{issue_id: "primary_1", issue_type: "primary", ...}` if lists empty but `primary_issue` set.

### 2.3 Phase B — Per-issue primary retrieval

For each `issue` in `decomposed_issues`:

1. **`build_queries_for_issue(issue, dispute_frame)`** — issue text, search_queries, legal_synonyms, optional dispute frame snippet, safety-token expansion.

2. **`_retrieve_queries_into_pool(db, queries, limit_per_source, issue=issue)`**:
   - For each query: **`EmbeddingService.create_embedding(expanded_query)`** (`text-embedding-3-small`).
   - For each provider in `KnowledgeRetrievalService.providers` (CONTRACT, ELM, CIM, LMOU):
     - Optional filter via `allowed_source_types`.
     - `provider.search(db, query_embedding, limit=limit_per_source)` → `(SourceChunk, cosine_distance)`.
     - Skip if `embedding_similarity = 1 - distance < MIN_EMBEDDING_SIMILARITY` (0.62).
     - Skip **`is_boilerplate_chunk`**.
     - Dedupe by **`_chunk_key`** `(source_document_id, page_number, chunk_index)`; track `best_embedding_distance`, `matched_query_count`, `retrieval_metadata.matched_issue_ids`.

3. Score each candidate: **`_score_chunk_match`** → **`score_chunk_for_issue`** (sets `combined_score`, `keyword_overlap`, rich `retrieval_metadata`).

4. **`passes_retrieval_gate(retrieved, score, dispute_frame, question)`** — only passing chunks go into `issue_pools[issue_id]`.

5. Sort pool by **`combined_score`** descending.

6. If pool empty → append to **`retrieval_gaps`**:
   ```python
   {
     "issue_id": ...,
     "issue_type": ...,
     "issue": ...,
     "reason": "no_chunks_above_retrieval_threshold",
   }
   ```

### 2.4 Phase C — Global fallback retrieval

1. **`global_queries = [query] + expanded_queries[:8]`**

2. **`_retrieve_queries_into_pool(..., issue=None)`** — all providers, no issue id on first insert.

3. For each chunk in `global_map`:
   - Score with global keywords; re-score against each decomposed issue; pick **best** `(best_score, best_issue_id, best_keywords, best_issue)`.
   - **`passes_retrieval_gate`** with `best_score`.
   - Set `retrieved.combined_score = best_score`; append to `issue_pools[best_issue_id]` if chunk key not already in that pool.

### 2.5 Phase D — Backfills and coverage

1. **`indexed_source_types = _get_indexed_source_types(db)`**

2. **`_backfill_empty_issue_pools`**:
   - For issues still with **empty** pool:
   - Skip `local_agreement` if `"LMOU" not in indexed_source_types`.
   - **`build_issue_type_backfill_queries(issue, dispute_frame)`** (max 8 queries).
   - Retrieve with **`allowed_source_types=indexed_source_types`**.
   - **`_append_passing_chunks_to_pool`** (gate + dedupe + sort).

3. **`_backfill_missing_source_types`** → **`source_coverage_audit`**:
   - Applies to issue types: `legal`, `remedy`, `timeline`, `information_rights`.
   - Collects source types already present in any pool (via `chunk.source_document.source_type`).
   - For each **indexed** type **missing** from pools:
     - Build up to 8 combined queries: `build_queries_for_issue`[:3] + `build_source_type_backfill_queries`[:2] per applicable issue.
     - Special CONTRACT + leave-revocation: prepend `question[:160]`, up to 10 queries.
     - Retrieve **only** that `source_type`; tag `matched_issue_ids` for each applicable issue; **`_append_passing_chunks_to_pool`** per issue.
   - Audit entry per source type (see §11).

4. **`_supplement_contract_leave_commitment_pool`**:
   - If **`dispute_concerns_management_revoking_approved_leave(dispute_frame, question)`** and no CONTRACT chunk with management leave commitment / entitlement language in pools → extra CONTRACT queries (question + fixed templates) into first `legal` (or legal/remedy) issue pool.

5. **Re-filter `retrieval_gaps`**: drop gaps whose `issue_id` now has a non-empty pool.

### 2.6 Phase E — Merge and API-shaped outputs

1. **`merge_issue_retrieval_pools(issue_pools, MAX_CHUNKS_TO_RANKER)`** (50):
   - Per issue: take top **`MAX_CHUNKS_PER_ISSUE`** (12) by `combined_score`.
   - Global dedupe by chunk key; merge `matched_issue_ids`; keep higher `combined_score`.
   - Global sort; truncate to **`max_total`** (50).
   - **`merge_metadata`**: `{ "per_issue_counts": dict[str,int], "total_merged": int }`.

2. **`all_chunks`**: `[item.chunk for item in retrieved_chunks]`; copy **`retrieval_metadata`** onto each ORM chunk object.

3. **`results_by_source`**: For each provider `source_type`, up to **`limit_per_source`** dicts via **`AnalysisService.chunk_to_source_dict(chunk)`**.

4. Return top-level dict (see §12).

### 2.7 Helper methods on `KnowledgeRetrievalService` (tests/scripts depend on these)

- `_retrieve_queries_into_pool`
- `_append_passing_chunks_to_pool`
- `_backfill_empty_issue_pools`
- `_backfill_missing_source_types`
- `_supplement_contract_leave_commitment_pool`
- `_pool_has_contract_leave_commitment`
- `_score_chunk_match`
- `_get_indexed_source_types`
- `_chunk_key`
- `extract_keywords`
- `extract_article_mentions`
- `search_all`

---

## 3. Ingestion pipeline

### 3.1 Primary runtime path (PostgreSQL + pgvector)

```text
KnowledgeBaseService.seed_official_sources
        ↓
SourceDocument rows
        ↓
SourceSyncService.sync_source  OR  SourceService.download_source  OR  POST upload-pdf
        ↓
local_path (+ sha256, etc.)
        ↓
SourceProcessingService.process_source
        ↓
SourceChunk rows + embeddings
        ↓
KnowledgeRetrievalService.search_all  (providers cosine search)
        ↓
AnalysisService.answer_question / generate_report / chat passages
```

**Steps in detail:**

1. **`KnowledgeBaseService.seed_official_sources(db)`** — inserts `SourceDocument` rows if missing (`source_id` unique lookup). `OFFICIAL_SOURCES` includes CONTRACT, ELM, CIM, LMOU (Knoxville stub).

2. **Download / local file:**
   - **`SourceSyncService.sync_source(db, source_id)`** — prefers first `*.pdf` in `uploads/<type>/`; else `urlretrieve` to `data/sources/<filename>`, handles `.zip` → first PDF; sets `local_path`, `sha256`.
   - **`SourceService.download_source(db, source_id)`** — HTTP GET `download_url` → `DATA_DIR/sources/`; sets `local_path`, `sha256`, `final_url`, `content_type`.
   - **`POST /sources/upload-pdf/`** — accepts arbitrary `source_type: str` with no enum validation.

3. **`SourceProcessingService.process_source(db, source_id)`**:
   - Requires `local_path`; errors if missing/not found.
   - Deletes existing chunks for that document.
   - `PdfReader` page-by-page.
   - Splits paragraphs (`\n\n`), then `split_text(max_chars=6000)`.
   - OpenAI `text-embedding-3-small` per chunk.
   - Inserts `SourceChunk` with `embedding`; commits.
   - Returns `{message, source_id, pages, chunks_created}` or `{error, ...}`.

4. **Retrieval** uses embeddings via providers (see §4).

**Embeddings consistency:** Both ingestion (`SourceProcessingService`) and query-time embedding (`EmbeddingService.create_embedding`) use **`text-embedding-3-small`**, aligned with `Vector(1536)` on `SourceChunk`.

### 3.2 Offline / CLI path (not used by `KnowledgeRetrievalService`)

| Component | Path | Role |
|-----------|------|------|
| **`source_manager.py`** | `app/services/source_manager.py` | `update_all_sources()` reads **`DATA_DIR/sources/source_registry.json`**, scrapes official pages, writes PDFs under `DATA_DIR/sources/<save_folder>/`, updates **`DATA_DIR/sources/manifest.json`**. |
| **`source_parser.py`** | `app/services/source_parser.py` | `build_source_index()` reads **`PROJECT_ROOT/app/sources/manifest.json`**, chunks to JSON **`app/sources/source_index.json`**. |
| Scripts | `scripts/download_sources.py`, `scripts/build_source_index.py` | Wire the above. |

**Path mismatch note:** Committed registry/manifest live under `app/sources/`, while `source_manager` expects `data/sources/source_registry.json`. Parser uses `app/sources/manifest.json`. These are parallel from the DB pipeline.

**`source_manager` key functions:** `load_registry()`, `discover_links()`, `choose_best_link()`, `download_file()`, `update_source()`, `update_all_sources()`.

### 3.3 HTTP source lifecycle

`app/api/routes/sources.py`:

- `POST /sources/seed-official/` → seed DB
- `POST /sources/{id}/sync` → `SourceSyncService.sync_source`
- `POST /sources/{id}/download` → `SourceService.download_source`
- `POST /sources/{id}/process` → `SourceProcessingService.process_source`
- `GET /sources/search/`, `/ask/`, `/report/` → `KnowledgeRetrievalService.search_all` (+ analysis/report)

### 3.4 Dual download systems

- **`SourceService.download_source`** (API `/sources/{id}/download`)
- **`SourceSyncService.sync_source`** (API `/sources/{id}/sync`)
- **`source_manager.update_all_sources`** (CLI/offline)

Different directories and manifest formats; operational choice matters before `process`. Retrieval only cares that **`/process`** has run and embeddings exist.

---

## 4. Providers

All live under `app/services/providers/`. There is **no** `__init__.py`; consumers import concrete modules directly.

| Class | File | `source_type` | `name` | Key method |
|--------|------|---------------|--------|------------|
| `BaseProvider` | `base_provider.py` | `""` (abstract) | `""` | `search(self, db, query_embedding, limit=5) -> list[tuple]` |
| `ContractProvider` | `contract_provider.py` | `"CONTRACT"` | `"National Agreement"` | Same `search` |
| `ELMProvider` | `elm_provider.py` | `"ELM"` | `"Employee & Labor Relations Manual"` | Same |
| `CIMProvider` | `cim_provider.py` | `"CIM"` | `"Contract Interpretation Manual"` | Same |
| `LMOUProvider` | `lmou_provider.py` | `"LMOU"` | `"Local Memorandum of Understanding"` | Same |

### Base contract

```python
class BaseProvider(ABC):
    name = ""
    source_type = ""

    @abstractmethod
    def search(self, db: Session, query_embedding, limit=5) -> list[tuple]:
        """Return list of (SourceChunk, cosine_distance) tuples ordered by
        ascending distance (best match first)."""
```

### Implementation pattern

All four concrete providers are identical aside from class attrs:

- pgvector cosine distance on `SourceChunk.embedding`
- join `SourceDocument`
- filter `SourceDocument.source_type == self.source_type`
- require non-null embeddings
- order by distance ascending
- limit
- return `[(chunk, float(dist)), ...]`

Callers convert to similarity as `1.0 - distance`.

### Registration

```python
# KnowledgeRetrievalService.providers
providers = [
    ContractProvider(),
    ELMProvider(),
    CIMProvider(),
    LMOUProvider(),
]
```

No other Python modules import providers besides `knowledge_retrieval_service.py`.

### Extending providers (compatibility)

- Subclass **`BaseProvider`**, set class-level **`name`** and **`source_type`** (must match `SourceDocument.source_type`).
- Implement **`search(db, query_embedding, limit=5) -> list[tuple[SourceChunk, float]]`** with ascending cosine distance.
- Use **`SourceChunk.embedding.cosine_distance(query_embedding)`** and **`.filter(SourceChunk.embedding.isnot(None))`**.
- **Register instance** on `KnowledgeRetrievalService.providers` (manual list; no plugin registry).
- Import as `from app.services.providers.<module> import <Class>` (no package `__init__`).

---

## 5. Source types

There is **no** `SourceType` enum in the repo. Types are **uppercase string labels** on `SourceDocument.source_type`, compared case-insensitively in several places via `.upper()`.

### First-class (provider + analyzer + weights)

| String | Provider | Seeded in KB | Registry (offline) | `LegalIssueAnalyzer.ALLOWED_SOURCE_TYPES` | `SOURCE_TYPE_WEIGHTS` |
|--------|----------|--------------|--------------------|-------------------------------------------|------------------------|
| `CONTRACT` | `ContractProvider` | Yes | Yes (`app/sources/source_registry.json`) | Yes | 18 |
| `ELM` | `ELMProvider` | Yes | Yes | Yes | 14 |
| `CIM` | `CIMProvider` | Yes | Yes | Yes | 16 |
| `LMOU` | `LMOUProvider` | Yes (Knoxville stub) | No | Yes | 14 |

**Issue analyzer gate:** `LegalIssueAnalyzer.ALLOWED_SOURCE_TYPES` and `_normalize_sources()` — LLM prompt restricts labels to CONTRACT, ELM, CIM, LMOU; unknown labels are dropped, defaulting to all four.

**Relevance backfill templates:** `SOURCE_TYPE_ISSUE_BACKFILL_TEMPLATES` (and related leave-revocation maps) in `relevance_utils.py` — keyed by `CONTRACT`, `CIM`, `ELM` (not LMOU in those template dicts). LMOU still participates via providers and issue-type local_agreement templates.

### Extended strings (sync folders / future types, no providers)

`SourceSyncService.get_local_folder_for_source()` folder_map:

```python
folder_map = {
    "CONTRACT": Path("uploads/contract"),
    "ELM": Path("uploads/elm"),
    "CIM": Path("uploads/cim"),
    "LMOU": Path("uploads/lmou"),
    "ARBITRATION": Path("uploads/arbitration"),
    "STEP4": Path("uploads/step4"),
    "MOU": Path("uploads/mou"),
}
```

Documents with these extended types can be stored and embedded, but **only the four provider types participate in vector search** unless a new provider is added and registered.

### Analysis / gap coupling for source types

- **`AnalysisService._source_types_relevant_to_analysis`** — hard-coded hints for LMOU/ELM/CONTRACT/CIM; governs **`missing_source_types`**.
- **`missing_source_types` logic** (`AnalysisService._build_retrieval_gaps`): only **`relevant_types & indexed - found_types`**; suppresses ELM/LMOU if CONTRACT or CIM found; mutual suppress CONTRACT vs CIM if one found.
- **`compute_unindexed_sources_requested`**: only adds **`LMOU`** when local signals appear and LMOU not indexed — not a general extensibility hook.
- **Chunks from indexed types without a provider** can exist in DB but won’t be retrieved via embedding search; **`results_by_source`** only buckets keys from `KnowledgeRetrievalService.providers`.

---

## 6. Database interactions

### 6.1 `SourceDocument` (`source_documents`)

From `app/database/models.py`:

- `id`, `organization_id` (optional FK)
- `source_id` (string, business key)
- `name`, **`source_type`** (string, required, `String(100)`)
- `official_page`, `download_url`, `final_url`, `local_path`
- `sha256`, `content_type`
- `is_current`, `created_at`
- Relationship: `chunks` → `SourceChunk`

### 6.2 `SourceChunk` (`source_chunks`)

- `id`
- `source_document_id` (FK)
- `chunk_index`, `page_number`, `section_label` (unused by `SourceProcessingService` today)
- `text`
- **`embedding`**: `Vector(1536)`, nullable until processed
- `created_at`
- Relationship: `source_document`

### 6.3 Retrieval usage of DB

- Providers query chunks + join document by `source_type`.
- `_get_indexed_source_types` requires at least one chunk with `embedding IS NOT NULL`.
- Chunk identity in pools: `(source_document_id, page_number, chunk_index)` (`_chunk_key`).
- KRS attaches ephemeral `chunk.retrieval_metadata` on ORM objects before returning `all_chunks` (not a DB column).

### 6.4 Downstream dict shape from `AnalysisService.chunk_to_source_dict(chunk)`

```python
{
    "source_id": getattr(source, "source_id", None),
    "document_name": source.name,
    "document_type": source.source_type,  # document_type = source_type
    "page": chunk.page_number,
    "chunk": chunk.chunk_index,
    "text": chunk.text,
    "retrieval_metadata": getattr(chunk, "retrieval_metadata", {}) or {},
    "retrieval_relationship": "embedding_retrieval",
}
```

---

## 7. Retrieval scoring

### 7.1 Pipeline

1. **`combine_retrieval_score`** — weighted embedding + keyword (+ procedural bonus cap), source-type bump, boilerplate penalty.

2. **`_score_chunk_core`** — distinctive/generic keyword overlap, article mention +0.08, substantive/procedural adjustments, **`compute_direction_penalty`**, hard zero if **`chunk_fails_actor_direction_gate`**.

3. **`score_chunk_for_issue`** — issue keywords vs optional **`global_keywords`** (max of two cores); writes metadata.

4. **`KnowledgeRetrievalService._score_chunk_match`** — builds article mentions from keywords + delegates to `score_chunk_for_issue`.

### 7.2 `combine_retrieval_score` formula

```text
score =
  EMBEDDING_SCORE_WEIGHT * embedding_similarity          # 0.60
  + KEYWORD_SCORE_WEIGHT * min(keyword_overlap + procedural_bonus, 1.0)  # 0.40
  + 0.05 * normalized_source_weight                      # source_weight / 18.0 capped at 1.0

if boilerplate:
  score -= BOILERPLATE_PENALTY / 100.0                   # 50.0 / 100 = 0.5

return max(score, 0.0)
```

### 7.3 Additional adjustments in `_score_chunk_core`

- If `compute_substantive_score(text) >= 0.25`: `+= SUBSTANTIVE_RULE_BONUS` (0.08)
- If `is_procedural_only_passage(text)`: `-= PROCEDURAL_ONLY_PENALTY` (0.12)
- `-= compute_direction_penalty(...)`
- If `chunk_fails_actor_direction_gate(...)`: `score = 0.0`
- Article mentions found in text: `keyword_overlap = min(keyword_overlap + 0.08, 1.0)`
- Distinctive keyword overlap preferred over generic; floor at `generic_overlap * 0.5`

### 7.4 `retrieval_metadata` after scoring (`score_chunk_for_issue`)

Written onto `RetrievedChunk.retrieval_metadata`:

- `embedding_similarity`
- `keyword_overlap`
- `matched_query_count`
- `is_boilerplate`
- `substantive_score`
- `direction_penalty`
- `matched_issue_ids`
- Optional `primary_issue_id` when `issue` passed

**Note:** `combined_score` lives on the **`RetrievedChunk` dataclass**, not inside `retrieval_metadata` unless copied elsewhere. Chat code looks for `combined_score` via metadata from `chunk_to_source_dict` — currently metadata comes from `retrieval_metadata` only (combined_score is on the dataclass / may need care in refactor).

### 7.5 Direction / leave-specific scoring helpers

Important helpers in `relevance_utils.py`:

- `dispute_concerns_management_revoking_approved_leave`
- `passage_describes_employee_initiated_leave_cancellation`
- `passage_describes_management_leave_commitment`
- `passage_states_employee_entitlement_rule`
- `compute_actor_action_direction_mismatch`
- `chunk_fails_actor_direction_gate`
- `compute_direction_penalty`
- `compute_direction_match_score`
- Signal lists: `EMPLOYEE_INITIATED_LEAVE_CANCELLATION_SIGNALS`, `MANAGEMENT_LEAVE_COMMITMENT_SIGNALS`, `MANAGEMENT_REVOCATION_LEAVE_SIGNALS`, `EMPLOYEE_ENTITLEMENT_RULE_SIGNALS`, etc.

### 7.6 Ranker-side (post-retrieval, not inside `search_all`)

Same `retrieval_config.py` also holds ranker/report constants consumed by **`AuthorityRanker`** / **`AnalysisService.generate_report`**, not by `search_all`:

- `MAX_AUTHORITIES_TO_RANKER`, `MAX_DISTINCT_REPORT_AUTHORITIES`
- `MIN_AUTHORITY_RELEVANCE_SCORE`, `MIN_KEY_AUTHORITY_RELEVANCE_SCORE`, `MIN_MANAGEMENT_LIMITING_RELEVANCE_SCORE`
- Keyword overlap thresholds for authority roles
- `TOPIC_MISMATCH_PENALTY_THRESHOLD` / `exceeds_topic_mismatch_threshold` (ranker-side topic mismatch)
- `REPORT_BRAND`, `REPORT_TITLE`, `RESEARCH_DRAFT_NOTICE`

---

## 8. Retrieval gates

### 8.1 Pre-pool embedding / boilerplate filters (in `_retrieve_queries_into_pool`)

Before a chunk even enters a candidate map:

1. `embedding_similarity < MIN_EMBEDDING_SIMILARITY` (0.62) → skip
2. `is_boilerplate_chunk(text)` → skip

### 8.2 Primary retrieval gate — `passes_retrieval_gate`

```python
def passes_retrieval_gate(
    retrieved: RetrievedChunk,
    combined_score: float,
    dispute_frame: dict | None = None,
    question: str = "",
) -> bool:
```

**Hard fail first:**

- If **`chunk_fails_actor_direction_gate(text, dispute_frame, question)`** → `False`
  - Specifically: management-revoking-approved-leave dispute frame + employee-initiated leave cancellation passage → contradiction ≥ `DIRECTION_CONTRADICTION_PENALTY` (0.25)

**Pass if any of:**

1. `combined_score >= MIN_COMBINED_RETRIEVAL_SCORE` (0.30)
2. `embedding_similarity >= EMBEDDING_FALLBACK_THRESHOLD` (0.68) **and** `matched_query_count >= 1` **and** not boilerplate
3. `embedding_similarity >= MIN_EMBEDDING_SIMILARITY` (0.62) **and** `compute_substantive_score(text) >= 0.25` **and** not boilerplate

Otherwise `False`.

### 8.3 Where the gate is applied

- Per-issue primary scoring loop
- Global fallback assignment
- `_append_passing_chunks_to_pool` (used by empty-pool backfill, missing-source-type backfill, contract leave supplement)

---

## 9. Backfill logic

### 9.1 Query builders (`relevance_utils`)

| Function | Purpose |
|----------|---------|
| **`build_queries_for_issue`** | Primary per-issue queries (issue name, search_queries, legal_synonyms, dispute frame snippet, safety expansions) |
| **`build_issue_type_backfill_queries`** | `ISSUE_TYPE_BACKFILL_TEMPLATES` keyed by issue_type |
| **`build_source_type_backfill_queries`** | `SOURCE_TYPE_ISSUE_BACKFILL_TEMPLATES` + dispute leave templates `DISPUTE_LEAVE_REVOCATION_BACKFILL` |
| **`build_dispute_frame_summary`** | Frame text for query suffixes |
| **`dispute_concerns_management_revoking_approved_leave`** | Triggers CONTRACT-focused backfill/supplement |

### 9.2 `ISSUE_TYPE_BACKFILL_TEMPLATES`

Keyed by: `legal`, `remedy`, `timeline`, `information_rights`, `local_agreement`.

### 9.3 `SOURCE_TYPE_ISSUE_BACKFILL_TEMPLATES`

Keyed by source type → issue type:

- `CONTRACT` → legal / remedy / timeline / information_rights
- `CIM` → same
- `ELM` → same
- **No LMOU entries** in this dict (falls back to issue-type templates when empty)

### 9.4 `DISPUTE_LEAVE_REVOCATION_BACKFILL`

Dispute-aware extra templates for CONTRACT / CIM / ELM when management-revocation leave frame is detected.

### 9.5 `_backfill_empty_issue_pools`

- Second-pass for issue pools still empty after global fallback.
- Skip `local_agreement` if LMOU not indexed.
- Up to 8 backfill queries.
- `allowed_source_types=indexed_source_types`.
- Score + gate via `_append_passing_chunks_to_pool`.

### 9.6 `_backfill_missing_source_types`

- One retrieval pass per indexed source type absent from all issue pools.
- Applicable issue types: `legal`, `remedy`, `timeline`, `information_rights`.
- If no applicable issues → return `[]` audit.
- If type already in pools: disposition **`retained_in_pool`**, `queries_issued: []`.
- Else: combined queries (deduped, capped), retrieve only that type, append passing chunks into each applicable issue pool, tag `matched_issue_ids`.
- CONTRACT + leave-revocation special: prepend question[:160], allow up to 10 queries.
- Disposition:
  - `retained_in_pool` if any retained
  - `none_passed_gates` if found but none retained
  - `no_embedding_matches` if none found

### 9.7 `_supplement_contract_leave_commitment_pool`

- Only when `dispute_concerns_management_revoking_approved_leave`.
- Skip if pool already has CONTRACT passage with management leave commitment or employee entitlement rule language.
- Target first `legal` issue, else first `legal`/`remedy`.
- Fixed supplement queries + question[:160], `allowed_source_types={"CONTRACT"}`.
- Append via `_append_passing_chunks_to_pool`.

---

## 10. Merge logic

### `merge_issue_retrieval_pools(issue_pools, max_total)` (`relevance_utils.py`)

1. For each issue pool:
   - Sort by `combined_score` descending.
   - Keep top **`MAX_CHUNKS_PER_ISSUE`** (12).
2. Global dedupe by `(source_document_id, page_number, chunk_index)`:
   - Merge `matched_issue_ids`.
   - Keep higher `combined_score` (and related fields when replacing).
3. Global sort by `combined_score`.
4. Truncate to **`max_total`** (`MAX_CHUNKS_TO_RANKER` = 50 when called from `search_all`).
5. `MIN_CHUNKS_PER_ISSUE` (2) used for merge metadata bookkeeping when pool smaller than minimum (setdefault counts).
6. Return `(merged_list, metadata)` where:
   ```python
   metadata = {
       "per_issue_counts": per_issue_counts,  # dict[str, int]
       "total_merged": len(merged),
   }
   ```

After merge in `search_all`:

- `all_chunks = [item.chunk for item in retrieved_chunks]`
- Each chunk gets `chunk.retrieval_metadata = retrieved.retrieval_metadata`
- `results_by_source` built from merged `retrieved_chunks`, capped per provider type at `limit_per_source`

---

## 11. Source-coverage behavior

### 11.1 Detection / raw audit (inside KRS)

Produced by `_backfill_missing_source_types`:

```python
{
  "source_type": str,
  "searched": True,
  "queries_issued": list[str],  # empty if retained_in_pool short-circuit
  "passages_found": int,
  "passages_retained": int,
  "disposition": "retained_in_pool" | "none_passed_gates" | "no_embedding_matches",
}
```

Returned from `search_all` as **`source_coverage_audit`** (raw list).

### 11.2 Indexed types

`indexed_source_types` on the return is a **sorted list[str]** of uppercased types that have at least one embedded chunk.

### 11.3 Report-side summarization (AnalysisService — not part of KRS return)

`AnalysisService._summarize_source_coverage_audit` transforms KRS audit + ranked authorities + pool into summarized entries with richer fields such as:

- `final_disposition` values like: `authorities_ranked`, `retrieved_not_ranked`, `found_rejected_by_gates`, `searched_no_matches`, `not_searched`
- Additional counts like `passages_ranked`, `passages_retained_in_pool`, etc.

`AnalysisService._build_retrieval_gaps` takes KRS **list** gaps (`retrieval_gaps_list`) and builds an enriched **dict** for the report, including nested summarized `source_coverage_audit`, `missing_source_types`, issues without supporting authority, etc.

**Critical split:**

| Stage | `retrieval_gaps` type | `source_coverage_audit` shape |
|-------|----------------------|-------------------------------|
| KRS `search_all` return | **list[dict]** per-issue gaps | **raw list** with `disposition` |
| Report / API after `generate_report` | **dict** (enriched) | **summarized** entries with `final_disposition` |

Do not conflate these in a refactor.

---

## 12. Public API contracts

### 12.1 `KnowledgeRetrievalService.search_all()` return dict

Exact keys (source of truth in `knowledge_retrieval_service.py` ~769–789):

| Key | Type / shape |
|-----|----------------|
| **`query`** | `str` |
| **`known_facts`** | `list` (default `[]`) |
| **`issue_analysis`** | `dict` — full **`LegalIssueAnalyzer`** output |
| **`decomposed_issues`** | `list[dict]` — from `collect_decomposed_issues` |
| **`expanded_queries`** | `list[str]` |
| **`issue_keywords`** | `list[str]` (≤30) |
| **`keywords`** | `list[str]` — from `KnowledgeRetrievalService.extract_keywords(query)` (≤12, query-only stopword filter) |
| **`article_mentions`** | `list[str]` — article/section/elm patterns from query |
| **`limit_per_source`** | `int` |
| **`results_by_source`** | `dict[str, list[dict]]` — keys **`CONTRACT`**, **`ELM`**, **`CIM`**, **`LMOU`** (provider order); each list length ≤ `limit_per_source` |
| **`all_chunks`** | `list[SourceChunk]` — merged ranker input (≤50) |
| **`retrieved_chunks`** | `list[RetrievedChunk]` — dataclass instances (same order as `all_chunks`) |
| **`issue_pools`** | `dict[str, list[RetrievedChunk]]` — post-backfill, pre-merge pools |
| **`merge_metadata`** | `dict` with `per_issue_counts`, `total_merged` |
| **`retrieval_gaps`** | `list[dict]` — only issues **still** empty after backfill |
| **`indexed_source_types`** | `list[str]` — sorted uppercased types with embeddings |
| **`source_coverage_audit`** | `list[dict]` — raw audit from `_backfill_missing_source_types` |

**Not named** top-level `results`, `sources`, or `metadata`. Closest public names are `results_by_source`, `merge_metadata`, and `retrieval_metadata` on chunk/source dicts.

### 12.2 `issue_analysis` (from `LegalIssueAnalyzer`)

Top-level keys from `_empty_analysis`:

- `primary_issue: str`
- `issue_categories: list[str]`
- `facts_needed: list[str]`
- `possible_sources: list[str]` — subset of `CONTRACT`, `ELM`, `CIM`, `LMOU`
- `legal_issues`, `remedial_issues`, `timeline_issues`, `information_rights_issues`, `local_agreement_issues`: each `list[dict]` with  
  `issue_id`, `issue`, `why_it_matters`, `search_queries`, `legal_synonyms`
- `dispute_frame: dict` with `summary`, `management_actions`, `employee_actions`, `union_concerns`, `information_sought`

**Note:** `AnalysisService._resolve_dispute_frame` (adds `actor`, `action`, etc.) runs only in **`answer_question` / `generate_report`**, not inside `search_all`. Consumers of raw `search_all` see the analyzer’s dispute frame only.

### 12.3 `decomposed_issues[]` item

```python
{
  "issue_id": str,
  "issue_type": str,  # legal | remedy | timeline | information_rights | local_agreement | primary
  "issue": str,
  "search_queries": list[str],
  "legal_synonyms": list[str],
}
```

### 12.4 `results_by_source` chunk dict

See §6.4 `chunk_to_source_dict`.

### 12.5 `RetrievedChunk` dataclass

```python
@dataclass
class RetrievedChunk:
    chunk: Any                    # SourceChunk ORM
    best_embedding_distance: float
    matched_query_count: int
    keyword_overlap: float
    combined_score: float
    retrieval_metadata: dict
```

### 12.6 `retrieval_gaps[]` item (KRS list shape)

```python
{
  "issue_id": str,
  "issue_type": str | None,
  "issue": str | None,
  "reason": "no_chunks_above_retrieval_threshold",
}
```

### 12.7 Signature / parameter contract

```python
def search_all(
    db: Session,
    query: str,
    limit_per_source: int = 8,
    known_facts: list[str] | None = None,
) -> dict:
```

Callers pass `known_facts` optionally (report route + case preview + chat).

### 12.8 AnalysisService report/ask contracts that depend on KRS outputs

`answer_question` uses: chunks (`all_chunks`), issue_analysis, issue_keywords.

`generate_report` uses:

```python
generate_report(
    ...,
    chunks=...,
    ...,
    retrieval_gaps_list=...,      # KRS list
    indexed_source_types=...,
    source_coverage_audit=...,    # KRS raw list
)
```

Report result then exposes enriched `retrieval_gaps` **dict**.

---

## 13. Dependencies, callers, and tests

### 13.1 Application callers of `search_all()` and fields consumed

**1. `app/api/routes/sources.py`**

| Route | Fields accessed | Downstream |
|-------|-----------------|------------|
| `GET /search/` | `query`, `limit_per_source`, `results_by_source` | JSON subset only |
| `GET /ask/` | `all_chunks`, `issue_analysis`, `issue_keywords` | `AnalysisService.answer_question(...)` |
| `GET /report/` | `all_chunks`, `issue_analysis`, `issue_keywords`, `retrieval_gaps`, `indexed_source_types`, `source_coverage_audit` | `AnalysisService.generate_report(...)` |

**2. `app/services/case_service.py` — `build_analysis_report_preview`**

- `results["all_chunks"]` → `generate_report(chunks=...)`
- `results.get("issue_analysis")`, `issue_keywords`, `all_chunks`, `retrieval_gaps`, `indexed_source_types`, `source_coverage_audit`
- After report: `report_result["retrieval_gaps"]` (dict); falls back to `results.get("source_coverage_audit")` if audit not nested in gaps dict
- Preview payload exposes `retrieval_gaps`, `source_coverage_audit`, `issue_analysis`, etc. (not raw `issue_pools`)

**3. `app/services/follow_up_chat_service.py` — `retrieve_indexed_source_passages`**

- `results.get("all_chunks")` — slice to `max_passages`; each chunk via `AnalysisService.chunk_to_source_dict`
- Reads passage fields + metadata (`combined_score` / article-or-section style fields)
- `results.get("indexed_source_types")`
- Does **not** read `results_by_source`, `retrieval_gaps`, `issue_analysis`, or `merge_metadata`
- Related: `_live_indexed_source_types` uses `KnowledgeRetrievalService._get_indexed_source_types(db)` only

### 13.2 Scripts

**4. `scripts/diagnose_regression.py` — `run_question`**

- `retrieved_chunks`, `issue_pools`, `retrieval_gaps` (list)
- `all_chunks` → ranker + `generate_report`
- `retrieval_gaps`, `indexed_source_types` → report path
- Record: `merge_metadata`

**5. `scripts/phase1_1_verification.py` — `_run_live_report`**

- Same report pipeline fields as `/report/`
- Also `len(results.get("all_chunks"))` for metrics

**6. `scripts/phase1_1_source_coverage_diagnostic.py` — `run_diagnostic`**

- `issue_pools`, `all_chunks`, `retrieved_chunks`, `retrieval_gaps`, `indexed_source_types`, `merge_metadata`

### 13.3 Not direct callers of `search_all`

- **`analysis_service.py`** — no `search_all`; consumes passed-through chunks + `retrieval_gaps_list` + `source_coverage_audit`
- **`legal_issue_analyzer.py`** — invoked **inside** `search_all` only; no dependency on return structure
- **`LegalIssueIdentifier`** — post-retrieval (report narrative), not part of `search_all`
- **`RetrievalService`** (`app/services/retrieval_service.py`) — separate, simpler path with **no** `search_all` usage

### 13.4 Tests that mock `search_all` return (contract for callers)

**`tests/test_chat_source_retrieval.py`**

Mocks expect minimal dicts:

- `all_chunks` + `indexed_source_types` (most tests)
- Side effect / failure paths

**`tests/test_case_service.py` — `test_generate_report_version_persists_audit_columns`**

Mock return:

```python
{
  "all_chunks": [],
  "issue_analysis": ...,
  "retrieval_gaps": [],  # KRS list shape
  "indexed_source_types": ["CONTRACT", "CIM", "ELM"],
  "source_coverage_audit": [...],
}
```

Asserts persisted `source_coverage_audit` / `retrieval_gaps` from **report** result, not raw KRS list.

**`tests/test_case_api.py`**

- Patches `search_all` only to assert **not called** on HTML export (`test_export_html_does_not_call_retrieval`).

### 13.5 No unit/integration test calls real `search_all()` end-to-end

Pipeline integration: `tests/test_regression_harness.py` hits `GET /sources/report/` (live DB when `RUN_REGRESSION=1`); asserts HTTP 200 + `score_report_completeness` on **report** JSON, not individual KRS keys.

### 13.6 Scoring / gates / merge / backfill unit tests

| File | What it asserts |
|------|-----------------|
| `tests/test_knowledge_retrieval_scoring.py` | `_score_chunk_match` ordering; `combine_retrieval_score` / overlap helpers |
| `tests/test_relevance_utils.py` | Overlap, boilerplate, `combine_retrieval_score`, `verify_quote_in_chunk` |
| `tests/test_relevance_phase0.py` | `passes_retrieval_gate`, direction/substantive scoring, **`merge_issue_retrieval_pools`** → `metadata["total_merged"]`, `metadata["per_issue_counts"]`, `_append_passing_chunks_to_pool`, **`_backfill_empty_issue_pools`** |
| `tests/test_phase1_1_source_coverage.py` | `build_source_type_backfill_queries`; **`AnalysisService._summarize_source_coverage_audit`** on KRS-style audit entries |
| `tests/test_phase1_1_retrieval_stability.py` | Direction/gates, backfill query helpers, audit summary + ranker mix; **`passes_retrieval_gate`** with dispute frame |
| `tests/test_retrieval_gaps.py` | **`AnalysisService._build_retrieval_gaps`** with `retrieval_gaps_from_krs=[]` and chunk pools |
| `tests/test_phase0_1_iteration_a.py` | `_build_retrieval_gaps` with **KRS-shaped list** gaps |
| `tests/test_report_export_presentation.py` | `format_source_coverage_caveat` on summarized audit entries |

### 13.7 Related ranker / narrative / authority / case persistence tests

- `tests/test_authority_ranker_filters.py`
- `tests/test_narrative_generator.py`
- `tests/test_follow_up_chat.py`
- `tests/test_case_lifecycle_workspace_restoration.py`
- `tests/test_steward_artifact_workflow.py`
- `tests/test_case_workspace_action_w2.py`
- `tests/test_case_workspace_action_api.py`
- `tests/test_case_save_and_print_artifacts.py`
- Fixtures: `tests/conftest.py` (`mock_chunk_factory`, annual_leave fixtures)

### 13.8 Knowledge ingestion / source processing tests

No tests named `*ingest*` or `*process*`. Embedding/index behavior appears via fixtures and `retrieval_relationship: "embedding_retrieval"` in lifecycle tests.

---

## 14. Import and compatibility constraints

### 14.1 Imports / packaging

- **No package-level re-exports** of `KnowledgeRetrievalService` from `app/services/__init__.py`; imports are always:
  ```python
  from app.services.knowledge_retrieval_service import KnowledgeRetrievalService
  ```
- Providers: direct module imports; no `providers/__init__.py`.
- **`LegalIssueAnalyzer`** is **lazy-imported inside `search_all`** only — likely to limit import cycles; callers still use `from app.services.legal_issue_analyzer import LegalIssueAnalyzer` elsewhere.
- **`relevance_utils`** is a **shared public surface** for tests, `AuthorityRanker`, `EvidenceExtractor`, `CitationValidator` (`verify_quote_in_chunk`), scripts — many named functions are part of the de facto API.

### 14.2 Dual keyword extractors (both appear in `search_all` return)

- `KnowledgeRetrievalService.extract_keywords` — query-only, ≤12 terms → return key **`keywords`**
- `extract_issue_keywords` / `extract_issue_keywords_for_issue` in `relevance_utils` → return key **`issue_keywords`**

### 14.3 Embedding model consistency

- Ingest: `SourceProcessingService` → `text-embedding-3-small`
- Query: `EmbeddingService.create_embedding` → `text-embedding-3-small`
- DB: `SourceChunk.embedding` → `Vector(1536)`

Changing any of these without migrating embeddings breaks retrieval.

### 14.4 Type splits callers must respect

- KRS `retrieval_gaps` = **list** → `generate_report(..., retrieval_gaps_list=...)`
- Report/API `retrieval_gaps` = **dict**
- Raw KRS `source_coverage_audit` list ≠ summarized report audit entries
- `results_by_source` values must stay compatible with `chunk_to_source_dict` shape
- Chat depends on `all_chunks[].retrieval_metadata` being set in KRS before `chunk_to_source_dict`
- `merge_metadata` only referenced in diagnostic scripts, not production routes — safe to extend but scripts log it
- `AnalysisService` shims to preserve when changing metadata:
  - `retrieval_relationship` always `"embedding_retrieval"` in `chunk_to_source_dict`
  - Report/answer authority dicts: **`authority_metadata` or `retrieval_metadata`**; **`version_or_effective_date` or `effective_date`**; **`chunk` vs `chunk_index`** naming differences between ranked output and source dict field **`chunk`**

### 14.5 `source_manager` vs sync/process

- Registry/download script path vs DB-backed sync used by API
- Retrieval only cares that process has run
- Do not assume refactoring KRS requires changing `source_manager`

### 14.6 Separate `RetrievalService`

`app/services/retrieval_service.py` is a separate, simpler path. Do not assume it shares contracts with `KnowledgeRetrievalService.search_all`.

---

## 15. Config knobs (`retrieval_config.py`)

### Used directly in retrieval path

| Constant | Value | Used in |
|----------|-------|---------|
| `MIN_EMBEDDING_SIMILARITY` | 0.62 | `_retrieve_queries_into_pool`; gate fallback in `passes_retrieval_gate` |
| `MIN_COMBINED_RETRIEVAL_SCORE` | 0.30 | `passes_retrieval_gate` primary pass |
| `EMBEDDING_FALLBACK_THRESHOLD` | 0.68 | Gate: strong embedding + ≥1 matched query |
| `MAX_CHUNKS_TO_RANKER` | 50 | `merge_issue_retrieval_pools` |
| `MIN_CHUNKS_PER_ISSUE` | 2 | merge metadata bookkeeping |
| `MAX_CHUNKS_PER_ISSUE` | 12 | per-issue cap before global merge |
| `EMBEDDING_SCORE_WEIGHT` | 0.60 | `combine_retrieval_score` |
| `KEYWORD_SCORE_WEIGHT` | 0.40 | `combine_retrieval_score` |
| `SOURCE_TYPE_WEIGHTS` | CONTRACT 18, CIM 16, ELM/LMOU 14 | normalized +0.05 boost in combine |
| `DEFAULT_SOURCE_WEIGHT` | 8.0 | unknown source types |
| `BOILERPLATE_PENALTY` | 50.0 | subtract 0.5 from combined score if boilerplate |
| `DIRECTION_CONTRADICTION_PENALTY` | 0.25 | direction / actor mismatch |
| `SUBSTANTIVE_RULE_BONUS` | 0.08 | substantive_score ≥ 0.25 |
| `PROCEDURAL_ONLY_PENALTY` | 0.12 | procedural-only passages |
| `TOPIC_MISMATCH_PENALTY_THRESHOLD` | 0.75 | ranker-side (`exceeds_topic_mismatch_threshold`), not retrieval gate |

### Post-retrieval (ranker/report)

| Constant | Role |
|----------|------|
| `MAX_AUTHORITIES_TO_RANKER` | 15 |
| `MAX_DISTINCT_REPORT_AUTHORITIES` | 5 |
| `MIN_AUTHORITIES_PER_DECOMPOSED_ISSUE` | 1 |
| `MIN_AUTHORITY_RELEVANCE_SCORE` | 65 |
| `MIN_KEY_AUTHORITY_RELEVANCE_SCORE` | 75 |
| `MIN_MANAGEMENT_LIMITING_RELEVANCE_SCORE` | 50 |
| `MIN_KEYWORD_OVERLAP_FOR_SUPPORTING` | 0.15 |
| `MIN_KEYWORD_OVERLAP_FOR_MANAGEMENT` | 0.08 |
| `MIN_KEYWORD_OVERLAP_RECLASSIFY_BACKGROUND` | 0.10 |
| `REPORT_BRAND` / `REPORT_TITLE` / `RESEARCH_DRAFT_NOTICE` | report presentation |

Changing gates/scoring thresholds affects KRS output **without** necessarily changing the return **key** set — preserve key names unless callers are updated.

---

## 16. Files inspected

### Core retrieval / relevance / analysis

- `app/services/knowledge_retrieval_service.py`
- `app/services/relevance_utils.py`
- `app/retrieval_config.py`
- `app/services/legal_issue_analyzer.py`
- `app/services/analysis_service.py`
- `app/services/embedding_service.py` (referenced for model consistency)
- `app/services/authority_ranker.py` (post-retrieval consumer; config shared)

### Source processing / sync / manager / providers

- `app/services/source_processing_service.py`
- `app/services/source_manager.py`
- `app/services/source_sync_service.py`
- `app/services/source_service.py` (download path)
- `app/services/source_parser.py` (offline index path)
- `app/services/knowledge_base_service.py` (seeding / OFFICIAL_SOURCES)
- `app/services/providers/base_provider.py`
- `app/services/providers/contract_provider.py`
- `app/services/providers/elm_provider.py`
- `app/services/providers/cim_provider.py`
- `app/services/providers/lmou_provider.py`

### Models / API / case / chat

- `app/database/models.py` (`SourceDocument`, `SourceChunk`, related)
- `app/api/routes/sources.py`
- `app/services/case_service.py` (report preview / `search_all` caller)
- `app/services/follow_up_chat_service.py`

### Tests (retrieval / scoring / coverage / gaps / callers)

- `tests/test_knowledge_retrieval_scoring.py`
- `tests/test_relevance_phase0.py`
- `tests/test_relevance_utils.py`
- `tests/test_chat_source_retrieval.py`
- `tests/test_case_service.py`
- `tests/test_case_api.py`
- `tests/test_retrieval_gaps.py`
- `tests/test_phase1_1_source_coverage.py`
- `tests/test_phase1_1_retrieval_stability.py`
- `tests/test_phase0_1_iteration_a.py`
- `tests/test_regression_harness.py`
- `tests/test_report_export_presentation.py`
- `tests/test_authority_ranker_filters.py`
- `tests/test_narrative_generator.py`
- `tests/test_follow_up_chat.py`
- `tests/conftest.py`

### Scripts / diagnostics

- `scripts/diagnose_regression.py`
- `scripts/phase1_1_verification.py`
- `scripts/phase1_1_source_coverage_diagnostic.py`
- `scripts/download_sources.py` / `scripts/build_source_index.py` (offline path awareness)

---

## 17. Refactor-critical notes

These items are especially important during the W5 retrieval architecture refactor:

1. **Treat current workspace code as source of truth.** Do not restore older implementations or remove existing retrieval behavior (gates, backfills, leave-direction logic, coverage audit) unless the implementation prompt explicitly requires it.

2. **Preserve `search_all()` public key set** unless all callers (API routes, case preview, chat, scripts, mocks) are updated in the same change.

3. **Preserve the list-vs-dict split** for `retrieval_gaps` (KRS list → report dict) and the raw-vs-summarized split for `source_coverage_audit`.

4. **Preserve provider contract:** `(SourceChunk, cosine_distance)` ascending; registration on `KnowledgeRetrievalService.providers`.

5. **Preserve embedding model / dimension** across ingest and query (`text-embedding-3-small` / 1536).

6. **`relevance_utils` is a shared public surface** — scoring, gate, merge, backfill builders, leave helpers are heavily tested and used outside KRS.

7. **Leave-revocation / actor-direction behavior is intentional W5 logic** — `passes_retrieval_gate`, direction penalties, CONTRACT leave-commitment supplement, dispute-aware backfill templates. Removing these would regress coverage/stability tests.

8. **Source coverage audit dispositions** (`retained_in_pool`, `none_passed_gates`, `no_embedding_matches`) are consumed by AnalysisService summarization and phase1.1 tests.

9. **`all_chunks` is the primary production payload** for ask/report/chat; `results_by_source` is mainly for `/search/` and is capped differently (`limit_per_source` vs merge 50).

10. **Attach `retrieval_metadata` onto chunk objects** before returning `all_chunks` — chat and `chunk_to_source_dict` depend on it.

11. **Lazy import of `LegalIssueAnalyzer` inside `search_all`** — preserve unless import-cycle analysis confirms a safer arrangement.

12. **No SourceType enum** — string labels throughout; analyzer allow-list and weights are separate hard-coded sets that must stay in sync when adding types.

13. **Offline `source_manager` / JSON index path is parallel**, not a substitute for DB retrieval — do not wire KRS to it accidentally during refactor.

14. **`RetrievalService` is a separate simpler path** — do not assume shared behavior with KRS.

15. **Extending source types requires coordinated updates:** provider + `providers` list + analyzer allow-list + weights + optional backfill templates + AnalysisService relevance/gap logic.

16. **Diagnostic scripts depend on internal-ish keys** (`issue_pools`, `retrieved_chunks`, `merge_metadata`) even if HTTP routes do not — keep or update scripts deliberately.

17. **Two keyword channels** (`keywords` vs `issue_keywords`) are both public return fields — do not collapse without caller review.

18. **Chunk identity key** `(source_document_id, page_number, chunk_index)` is used for dedupe across retrieve/backfill/merge — changing this requires updating all three.

19. **Re-process deletes all chunks** for a document — ingestion idempotency is “replace all,” not incremental upsert by chunk_index alone across versions of the file content.

20. **Ranker/report thresholds live in the same config file** as retrieval thresholds — changes to `retrieval_config.py` can affect both layers.

---

## 18. Condensed flow diagram

```text
Entry: API / Case / Chat / Scripts
        │
        ▼
KnowledgeRetrievalService.search_all
        │
        ├─ LegalIssueAnalyzer.analyze + build_search_queries
        ├─ collect_decomposed_issues + extract_issue_keywords
        │
        ├─ Per-issue: build_queries_for_issue
        │       → EmbeddingService.create_embedding
        │       → Providers.search (cosine)
        │       → score_chunk_for_issue + passes_retrieval_gate
        │       → issue_pools / retrieval_gaps
        │
        ├─ Global fallback retrieval + best-issue assignment
        │
        ├─ _backfill_empty_issue_pools
        ├─ _backfill_missing_source_types → source_coverage_audit
        ├─ _supplement_contract_leave_commitment_pool
        ├─ drop filled gaps
        │
        ├─ merge_issue_retrieval_pools (≤50)
        ├─ all_chunks (+ retrieval_metadata)
        ├─ results_by_source (chunk_to_source_dict)
        │
        └─ return public dict
                │
                ├─ AnalysisService.answer_question / generate_report
                └─ FollowUpChatService passages

Upstream:
  SourceSyncService / SourceService / upload
        → SourceProcessingService.process_source
        → SourceChunk + embedding
        → Providers
```

---

## Appendix A — LegalIssueAnalyzer `ALLOWED_SOURCE_TYPES` / empty analysis

```python
ALLOWED_SOURCE_TYPES = {
    "CONTRACT",
    "ELM",
    "CIM",
    "LMOU",
}

ISSUE_LIST_FIELDS = (
    "legal_issues",
    "remedial_issues",
    "timeline_issues",
    "information_rights_issues",
    "local_agreement_issues",
)
```

Empty analysis dispute_frame fields: `summary`, `management_actions`, `employee_actions`, `union_concerns`, `information_sought`.

## Appendix B — `ISSUE_TYPE_FIELDS` mapping used by `collect_decomposed_issues`

```python
ISSUE_TYPE_FIELDS = [
    ("legal_issues", "legal"),
    ("remedial_issues", "remedy"),
    ("timeline_issues", "timeline"),
    ("information_rights_issues", "information_rights"),
    ("local_agreement_issues", "local_agreement"),
]
```

## Appendix C — End of inspection

This document captures the complete pre-implementation inspection for the W5 retrieval refactor. No code was modified during inspection. Use this file as the temporary working reference when applying the implementation prompt.
