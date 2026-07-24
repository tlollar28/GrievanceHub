# Retrieval-Agent Implementation Report

**Date:** 2026-07-23  
**Status:** Complete  
**Active branch:** `main`  
**Starting HEAD:** `58b2efbe02fd002b3053d6aacc8577d7bca99370`  
**Ending HEAD:** `58b2efbe02fd002b3053d6aacc8577d7bca99370` (implementation remains uncommitted in the working tree)

## 1. Active branch

`main`

## 2. Starting HEAD

`58b2efbe02fd002b3053d6aacc8577d7bca99370`

## 3. Ending HEAD

`58b2efbe02fd002b3053d6aacc8577d7bca99370`

No commit was created. All retrieval-agent work is present as working-tree changes on `main`.

## 4. Initial Git status

Pre-implementation workspace already contained completed W5 Knowledge Foundation work plus an in-progress retrieval package. Confirmed before changes:

- Branch: `main` tracking `origin/main`
- Alembic head: `h9c0d1e2f3a4`
- Supervisor Manual corpus:
  - `supervisor_manual_el921_grievance_2015` — completed, 49 chunks / 49 embeddings
  - `supervisor_manual_el801_safety_2020` — completed, 101 chunks / 101 embeddings
  - `supervisor_manual_f21_time_attendance_2016` — completed, 383 chunks / 383 embeddings
- Total Supervisor Manual embeddings: 533

## 5. Final Git status

Uncommitted on `main`. Retrieval-agent additions/modifications are listed in sections 6–7. W5 assets and reports were preserved. No branch switch, merge, rebase, stash, reset, push, or source reprocessing occurred.

## 6. Files added

Retrieval package:

- `app/services/retrieval/__init__.py`
- `app/services/retrieval/models.py`
- `app/services/retrieval/base_agent.py`
- `app/services/retrieval/contract_agent.py`
- `app/services/retrieval/supervisor_manual_agent.py`
- `app/services/retrieval/orchestrator.py`

Tests and diagnostics:

- `tests/test_retrieval_agents.py`
- `tests/test_retrieval_agent_performance.py`
- `tests/test_retrieval_agent_security.py`
- `scripts/retrieval_agent_diagnostic.py`

Documentation:

- `docs/temp/RETRIEVAL_AGENT_IMPLEMENTATION_REPORT.md` (this file)

## 7. Files modified

Retrieval-relevant:

- `app/retrieval_config.py` — agent bounds, candidate-similarity floor, embedding timeout/retry defaults
- `app/services/knowledge_retrieval_service.py` — `retrieve_with_agents` / `search_with_agents` compatibility adapters
- `app/services/embedding_service.py` — timeout and bounded retries
- `app/api/routes/sources.py` — `/sources/search/` routes through the agent adapter
- `app/services/follow_up_chat_service.py` — system prompt labels retrieved text as untrusted evidence

Preserved W5 / unrelated workspace files were not rewritten for this task.

## 8. Existing retrieval system discovered

Traced call paths:

| Entry | Path | Behavior |
|-------|------|----------|
| `GET /sources/search/` | `sources.py` → `KnowledgeRetrievalService.search_with_agents` → `RetrievalOrchestrator` | New bounded agent path |
| `GET /sources/ask/` | `search_all` → `AnalysisService.answer_question` | Legacy issue-decomposition path |
| `GET /sources/report/` | `search_all` → `AnalysisService.generate_report` | Legacy report path |
| `CaseService.build_analysis_report_preview` | `search_all` | Legacy |
| `FollowUpChatService.retrieve_indexed_source_passages` | `search_all` | Legacy chat retrieval |
| Providers | `ContractProvider`, `ELMProvider`, `CIMProvider`, `LMOUProvider` | Cosine-distance SQL per source type |

Legacy engine characteristics retained:

- Embedding model: OpenAI `text-embedding-3-small`, dimension 1536
- Distance: pgvector cosine distance (`<=>` / SQLAlchemy `.cosine_distance`)
- Shared scoring: `relevance_utils.combine_retrieval_score`
- Source taxonomy includes `CONTRACT`, `CIM`, `ELM`, `LMOU`, `ARBITRATION`, `SUPERVISOR_MANUAL`
- Official grievance PDF export does not call retrieval

## 9. Threat model

See the pre-implementation threat model retained at the top of this file’s prior draft and summarized here:

### Assets

- Indexed labor-reference corpus (global and organization-owned)
- Case questions / known facts that may contain grievance narratives and PII
- Retrieved titles, filenames, URLs, and chunk text (untrusted)

### Actors

Authenticated/local API callers, stewards, future admins, application process, PostgreSQL, OpenAI embeddings, downstream LLMs.

## 10. Trust boundaries

| Boundary | Policy enforced |
|----------|-----------------|
| API → app | Explicit `RetrievalAuthorizationContext`; unauthenticated rejected |
| App → PostgreSQL | Parameterized SQLAlchemy; org/global filters in SQL |
| App → OpenAI | One bounded query embedding; no secret/query logging |
| App → filesystem | Retrieval is DB-only; no `local_path` serialization |
| Retrieval → LLM | Content labeled `untrusted_evidence`; chat prompt forbids instruction-following |
| Logs/telemetry | Correlation ID, query hash/length, counts, durations, error class only |

Inherited limitation: `/sources` routes still lack application-wide authentication. The retrieval layer does not invent a user/role model; trusted internal adapters default to global (`organization_id IS NULL`) sources only.

## 11. Shared retrieval contract

`RetrievalEvidence` / `AgentRetrievalResult` / `OrchestrationResult` in `app/services/retrieval/models.py`.

Preserved fields include source document ID, canonical source ID, title, type, version, SHA, chunk ID/index/page/text, raw distance/similarity, normalized and final scores, agent name, domain, evidence role, processing strategy, safe metadata, alternate provenance, and `content_trust`.

Explicitly excluded from serialization: ORM entities, embedding vectors, local paths, secrets, DB URLs, stack traces.

Statuses: `success`, `no_eligible_sources`, `no_relevant_results`, `partial_failure`, `complete_failure`, `authorization_failure`, `validation_failure`.

## 12. Agent interface

`RetrievalAgent` protocol and `SqlVectorRetrievalAgent` base:

- Stable identity (`name`, `domain`, `supported_source_types`)
- Eligibility against validated request domains/agent names
- One projection SQL query with join + filters + vector order + limit
- Batched provenance in the same projection (no N+1)
- Structured success/failure results
- Deterministic sort and per-source diversity

No autonomous planning, tool loops, conversational memory, or LLM routing.

## 13. ContractAgent implementation

Eligible source types (from repository taxonomy):

- `CONTRACT`
- `CIM`
- `ELM`
- `LMOU`
- `ARBITRATION`

Excluded: `SUPERVISOR_MANUAL`, templates, failed/stale/unembedded rows.

Processing predicate:

- Preferred: `processing_status == completed` and non-stale `processed_sha256`
- Compatibility: pre-W5 `pending` rows with SHA, no processing error, and persisted embeddings

Evidence roles distinguish controlling contract language, CIM interpretation, ELM rules, LMOU provisions, and arbitral support.

## 14. SupervisorManualAgent implementation

Eligible source type: exactly `SUPERVISOR_MANUAL`.

Requires completed, non-stale processed SHA and non-null embeddings. Evidence role is always `supervisory_guidance_non_controlling`. Per-source diversity prevents F-21 domination. No hardcoded database IDs.

## 15. RetrievalOrchestrator implementation

High-level entry point:

1. Validate/cap request
2. Validate authorization
3. Deterministic domain routing
4. Create one query embedding
5. Invoke eligible agents sequentially (Session safety)
6. Merge, normalize-aware rank, dedupe, diversify, cap
7. Return structured status including partial failure

## 16. Routing rules

Deterministic allowlists:

- Domains: `auto`, `contract`, `supervisor_manual`, `combined`
- Explicit agent names and source types further narrow selection
- Workflow contexts: `contract_analysis`, `supervisor_guidance`, `grievance_analysis`, `report_evidence`, etc.
- Auto keyword signals:
  - Contract: agreement, article, CBA, CIM, ELM, LMOU, remedy, violation, arbitration, …
  - Supervisor: supervisor, Step 1 meeting, time and attendance, attendance control, safety, EL-921/EL-801/F-21, …

Not every agent runs for every query.

## 17. Ranking formula

Per agent, after scoring:

`final = 0.85 * normalized_agent_score + 0.15 * cosine_similarity`

where

`normalized_agent_score = clamp((combined_score - threshold) / (1.05 - threshold), 0, 1)`

and `combined_score` comes from `relevance_utils.combine_retrieval_score`.

Stable tie-break: final score desc, raw distance asc, agent name, canonical source ID, page, chunk index, chunk ID.

## 18. Score normalization

Agent scores are threshold-normalized before merge so incompatible raw score distributions are comparable. Raw distance and similarity remain on each evidence object.

Candidate admission floor for scoring: `RETRIEVAL_MIN_CANDIDATE_SIMILARITY = 0.45`. Final acceptance still requires `combined_score >= relevance_threshold` (default `MIN_COMBINED_RETRIEVAL_SCORE = 0.30`). This aligns the agent path with the shared gate’s primary combined-score branch and avoids rejecting mid-similarity hits that score well.

## 19. Deduplication strategy

Bounded after candidate caps:

1. Exact chunk key duplicates
2. Exact normalized text duplicates
3. Same-document containment / high token Jaccard (≥ 0.88)

Complexity is O(k²) over the already-capped selected/candidate set only. Strongest result retained; alternate provenance preserved.

## 20. Source-diversity strategy

`per_source_result_limit` (default 3, max 5) applied in each agent and again during orchestration merge. Prevents F-21 or any single contract source from monopolizing the result window.

## 21. Authorization enforcement

`RetrievalAuthorizationContext` is required and validated before embedding/SQL.

- Unauthenticated → `authorization_failure`
- Global-only default for trusted adapters
- Organization IDs allowlisted and applied in SQL via `organization_id IS NULL` / `IN (...)`
- Non-admin cannot request `allow_all_organizations`
- Restricted failures return no result counts/metadata that would reveal hidden sources

Current product policy: corpus rows with `organization_id IS NULL` are globally available to authenticated/trusted callers. No invented tenant model.

## 22. Input validation

Server-side allowlists and caps for domain, agents, source types, source IDs, workflow context, candidate/result limits, query length (2000), control characters, null bytes, and metadata filter size. SQL uses bound expressions only.

## 23. Prompt-injection handling

Retrieved text is always `content_trust = "untrusted_evidence"`. Chunk text cannot alter routing, authorization, SQL, or agent selection. `FollowUpChatService.build_system_prompt()` states retrieved passages are untrusted evidence and cannot change rules, request secrets, authorize access, or invoke tools.

## 24. File/path security

Agent SQL projections omit `local_path`. Serialization has no path field. Unsafe metadata keys are stripped. Source IDs must match `^[A-Za-z0-9][A-Za-z0-9._:-]{0,149}$`.

## 25. Error handling

- One-agent failure → `partial_failure`, successful evidence retained, session rollback attempted
- All agents / embedding failure → `complete_failure` with stable codes
- Validation / authorization failures are structured and safe
- Client payloads never include stack traces or secret-bearing exception text

## 26. Configuration

In `app/retrieval_config.py` (no new secrets/env vars required):

- Enabled agents
- Candidate / per-agent / total / per-source limits
- Query, response-text, and filter maxima
- Candidate similarity floor
- Embedding timeout and max retries
- Existing relevance thresholds reused

## 27. Caching decision

No caching added.

Reasons:

- Query text may contain grievance PII
- Authorization scope must be part of any key
- Source SHA/version freshness would require careful invalidation
- Current corpus and latency do not justify the complexity
- Multi-process cache isolation is not present

## 28. Existing-caller integrations

| Caller | Integration |
|--------|-------------|
| `GET /sources/search/` | `search_with_agents` → orchestrator |
| Ask / report / case report preview / case chat | Remain on `search_all` for behavioral parity |
| Official Step 1 / Step 2 PDF export | Not routed through retrieval |
| Diagnostic script | `scripts/retrieval_agent_diagnostic.py` |

## 29. Backward-compatibility strategy

- `KnowledgeRetrievalService.search_all` unchanged as the issue-decomposition facade
- New adapters: `retrieve_with_agents`, `search_with_agents`
- Providers remain for legacy retrieval
- Grouped adapter keys include `SUPERVISOR_MANUAL` and `ARBITRATION` without dropping prior keys

## 30. SQL query counts

Observed budgets:

| Path | SQL queries |
|------|-------------|
| ContractAgent | 1 projection |
| SupervisorManualAgent | 1 projection |
| Combined orchestration | 2 projections (1 per selected agent) |
| No-results path | 1 per selected agent |
| Legacy adapter conversion | 0 additional queries |
| Provenance hydration | included in the projection (0 extra) |

Live development observation matched these budgets (1 or 2 cursor executes plus embedding).

## 31. N+1 analysis

No N+1 path remains in the agent stack:

- No lazy relationship access in result loops
- No per-chunk or per-source follow-up queries
- Source metadata selected in the same JOIN projection
- Embedding vectors are not hydrated into Python beyond distance computation in SQL

## 32. Query-count test budgets

From `tests/test_retrieval_agent_performance.py`:

- Contract one vs many results: budget `1`
- Three-manual supervisor results: budget `1`
- Combined orchestration: budget `2`
- No-results combined: budget `2`
- Legacy adapter: budget `0` extra DB queries
- One embedding call per orchestrated request

## 33. PostgreSQL query plans

Representative `EXPLAIN ANALYZE` for Supervisor Manual exact search (`LIMIT 48`):

```text
Limit
  -> Sort (top-N heapsort, 35kB)
       -> Hash Join (source_chunks ⋈ source_documents)
            -> Seq Scan on source_chunks (embedding IS NOT NULL)  actual rows=1902
            -> Hash / Seq Scan on source_documents
                 Filter: SUPERVISOR_MANUAL + completed + processed_sha + global org
                 actual rows=3
Planning Time: ~2.5 ms
Execution Time: ~5.5 ms
```

Filters for source type, processing status, org scope, and null embeddings occur in SQL. Candidate limit is applied by PostgreSQL.

## 34. Indexes used

Present:

- `source_chunks_pkey` / `ix_source_chunks_id`
- `source_documents_pkey` / `ix_source_documents_id`
- `ix_source_documents_processing_status`

No HNSW/IVFFlat vector index is present. Plans use sequential scan + hash join, appropriate at current scale.

## 35. ANN-index decision

**Do not add an ANN index now.**

Evidence:

- Corpus ≈ 1.9k embedded chunks; Supervisor Manual subset = 533
- Exact search execution ≈ 5.5 ms locally
- High filter selectivity on source type / processing status
- Recall requirements favor exact ordering for citation evidence
- Update frequency is administrative reprocessing, not high-churn writes

Revisit HNSW (cosine ops) when embedded chunks grow by roughly an order of magnitude or measured DB time becomes a material share of request latency.

## 36. Memory and computational bounds

Enforced server-side:

- Query ≤ 2000 chars
- Candidates ≤ 96
- Per-agent results ≤ 16
- Total results ≤ 24
- Per-source ≤ 5
- Domains ≤ 2
- Source filters ≤ 16
- Chunk text ≤ 6000 chars
- Response text aggregate ≤ 60000 chars
- Dedup only over capped sets
- Agents sequential and finite

## 37. Benchmark / diagnostic results

`scripts/retrieval_agent_diagnostic.py` records status, selected agents, query hash, SQL count, embedding/DB/merge durations, and provenance without text/secrets.

Live read-only verification (one embedding per query; no source reprocessing):

| Query class | Status | SQL | Notable sources |
|-------------|--------|-----|-----------------|
| Supervisor grievance handling | success | 1 | EL-921, EL-801 |
| Step 1 meeting procedures | success | 1 | EL-921, EL-801 |
| Time/attendance documentation | success | 1 | F-21 |
| Attendance control | success | 1 | F-21 |
| Employee safety | success | 1 | EL-801, EL-921 |
| Contract-only | success | 1 | National Agreement, CIM |
| Combined | success | 2 | Contract + CIM + all three manuals |

Domain integrity:

- ContractAgent returned no `SUPERVISOR_MANUAL`
- SupervisorManualAgent returned no contract-only types
- Combined preserved agent/domain/evidence-role provenance
- Manual evidence role remained `supervisory_guidance_non_controlling`

## 38. Functional tests

`tests/test_retrieval_agents.py` — 23 test functions, including parametrized routing cases.

Coverage includes shared contract serialization, ContractAgent/SupervisorManualAgent provenance and filters, diversity, orchestrator routing, shared embedding, partial/complete failure, merge/dedupe, and legacy adapter shape.

## 39. Performance tests

`tests/test_retrieval_agent_performance.py` — 9 tests.

Coverage includes query-count budgets, combined budget, legacy adapter cost, server-side caps, response-text bounds, dedup determinism, and single embedding reuse.

## 40. Security tests

`tests/test_retrieval_agent_security.py` — 17 test functions (20 collected with parametrization).

Coverage includes auth rejection, org SQL filters, allowlists, injection-like input, oversized query/filters, path/metadata stripping, prompt-injection labeling, no embedding/path leakage, redacted errors, restricted-scope non-leakage, and safe logging.

## 41. Full test-suite results

Command:

```text
.\venv\Scripts\python.exe -m pytest -q --tb=line
```

Result:

- **579 passed**
- **0 failed**
- **0 errors**
- **1 skipped** (`tests/test_regression_harness.py::test_regression_live_pipeline_smoke`, requires `RUN_REGRESSION=1`)
- **331 warnings** (existing datetime.utcnow deprecations)

Retrieval-agent suite alone:

```text
.\venv\Scripts\python.exe -m pytest tests/test_retrieval_agents.py tests/test_retrieval_agent_performance.py tests/test_retrieval_agent_security.py -q
```

- **54 passed**

## 42. Live read-only verification

Completed against the configured local PostgreSQL corpus. Unchanged Supervisor Manuals were not reprocessed. No private grievance narrative was used. No secrets were printed.

Representative Supervisor Manual result:

- Query class: supervisor grievance handling
- Agent: `SupervisorManualAgent`
- Sources: `supervisor_manual_el921_grievance_2015`, `supervisor_manual_el801_safety_2020`
- Evidence role: `supervisory_guidance_non_controlling`
- Pages/versions/SHAs present
- SQL queries: 1

## 43. Known limitations

1. Application-wide authentication is still absent on `/sources` routes; retrieval accepts an explicit auth context rather than inventing identity.
2. `search_all` (ask/report/chat) still uses legacy providers and does not yet surface Supervisor Manual evidence.
3. Contract corpus rows remain `processing_status=pending` with the pre-W5 compatibility predicate; they are searchable when embeddings exist but are not W5-completed.
4. Exact vector search uses sequential scan at current scale.
5. No result/embedding cache.

## 44. Remaining blockers

None for completing the retrieval-agent architecture task.

Optional follow-ups are product decisions, not blockers:

- Endpoint authentication / principal binding
- Migrating chat/report callers onto orchestrator when Supervisor Manual evidence is desired there
- Marking legacy contract rows `completed` through normal W5 processing when intentionally refreshed

## 45. Recommended next phase

1. Add application authentication to source/retrieval endpoints and bind `RetrievalAuthorizationContext` to real principals.
2. Optionally supplement case-chat retrieval with `retrieve_with_agents` for supervisor-procedure questions while keeping `search_all` for contract issue decomposition.
3. When embedded corpus exceeds ~20k chunks or DB time dominates, evaluate a cosine HNSW index via Alembic with recall comparison against exact search.
4. Consider a future arbitration-specialized ranking profile only if ARBITRATION volume and citation needs justify it; sources already route through ContractAgent.

## Pre-implementation threat model (retained)

This threat model was recorded before retrieval-agent code was introduced and
is the security baseline for the implementation.

### Assets and actors

- The indexed labor-reference corpus is application evidence. Global sources
  have `organization_id IS NULL`; organization-owned sources may be restricted.
- Case questions and known facts may contain grievance narratives, employee
  names, identifiers, attendance information, and other personal information.
- Retrieved document text, titles, filenames, URLs, and JSON metadata are
  untrusted content even when the source was administratively registered.
- Actors include local/API callers, stewards, future administrators, the
  application process, PostgreSQL, the embedding provider, and downstream LLMs.

### Trust boundaries

- API to application: the current repository has no authentication dependency
  on source/retrieval routes and no user-to-organization authorization model.
- Application to PostgreSQL: queries must be parameterized and authorization
  constraints must be part of candidate selection.
- Application to OpenAI: a bounded query leaves the application; credentials,
  full embeddings, provider payloads, and query text must not be logged.
- Application to local files: retrieval is database-only and must not open or
  return `SourceDocument.local_path`.
- Retrieval to downstream LLMs: source text is evidence, never an instruction.
- Application to logs/telemetry: only correlation IDs, query length/hash,
  allowlisted filters, counts, durations, and error classes are safe.

### Principal threats and required mitigations

- Cross-user/cross-case leakage: retrieval must never search case records or
  infer access from a case UUID. The new path defaults to global sources only.
- Cross-organization leakage: organization filters are applied in SQL. An
  explicit trusted scope is required before organization-owned sources qualify.
- SQL/filter injection: source domains, agent names, source types, and filters
  use allowlists and SQLAlchemy bound expressions; no user-built SQL fragments.
- Denial of service/cost abuse: query length, domains, filters, candidate
  counts, results, per-source diversity, response text, retries, and timeouts
  are server bounded.
- Prompt injection: returned chunks are labeled untrusted evidence; their text
  cannot change routing, authorization, database predicates, or tool behavior.
- Path/file disclosure: no raw local path is selected or serialized. Source
  URLs are omitted from the shared result contract.
- Stale/failed sources: failed, processing, missing-embedding, non-current, and
  stale completed documents are filtered before results are returned. Legacy
  pre-W5 contract rows with persisted embeddings require a narrow compatibility
  rule because W5 intentionally backfilled their lifecycle state to `pending`.
- Authority confusion: Supervisor Manual evidence is labeled non-controlling
  supervisory guidance and never presented as contract language.
- Sensitive observability/error leakage: client failures use stable codes and
  safe messages; logs exclude query/chunk text, embeddings, employee data,
  secrets, database URLs, paths, and raw provider bodies.
- Partial failure: each agent has a structured result. Successful evidence is
  retained when another agent fails; all-agent and embedding failures are
  explicit and safely serialized.

### Inherited authorization limitation

The repository currently has no authenticated principal dependency on
`/sources` retrieval or source-management endpoints and no persisted user/role
model from which steward/admin permissions can be derived. Adding such a model
inside this retrieval refactor would invent product policy and break existing
callers. The new retrieval API therefore accepts an explicit authorization
context, rejects unauthenticated contexts, defaults trusted compatibility calls
to global (`organization_id IS NULL`) sources, and never broadens access to
organization-owned rows. Endpoint-wide authentication remains a documented
application-level limitation rather than being simulated in the retrieval
layer.
