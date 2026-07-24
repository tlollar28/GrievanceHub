# Retrieval Security and Integration Report

**Date:** 2026-07-23  
**Status:** Complete (safe interim controls; long-term identity remains a product decision)  
**Workspace:** `C:\Users\tloll\Documents\GrievanceHub`

## 1. Active branch

`main`

## 2. Starting and ending HEAD

- **Starting HEAD:** `58b2efbe02fd002b3053d6aacc8577d7bca99370`
- **Ending HEAD:** `58b2efbe02fd002b3053d6aacc8577d7bca99370`

No commit was created. All security, migration, and verification work remains in the working tree on `main`.

## 3. Initial and final Git status

### Initial (pre-task)

Uncommitted W5 + retrieval-agent work already present on `main` (same HEAD). Retrieval package, W5 lifecycle, grievance PDF assets, and related tests were untracked or modified.

### Final

Still uncommitted on `main`. Additional security/integration files added or modified in this task (see §§5). No reset, rebase, stash, merge, cherry-pick, branch switch, push, source reprocessing, or embedding regeneration occurred.

## 4. Files inspected

Independently reviewed (code, not only prior reports):

- `docs/temp/RETRIEVAL_AGENT_IMPLEMENTATION_REPORT.md`
- `docs/temp/W5_KNOWLEDGE_FOUNDATION_IMPLEMENTATION_REPORT.md`
- `docs/temp/RETRIEVAL_ARCHITECTURE_PLAN.md`
- `docs/temp/PROJECT_INSPECTION_W5.md`
- `app/services/retrieval/{models,base_agent,contract_agent,supervisor_manual_agent,orchestrator,__init__}.py`
- `app/services/knowledge_retrieval_service.py`
- `app/services/embedding_service.py`
- `app/services/follow_up_chat_service.py`
- `app/services/case_service.py` (report preview)
- `app/api/routes/sources.py`
- `app/retrieval_config.py`
- `app/services/providers/*`
- `app/main.py`, `app/config.py`, `.env.example`
- `tests/test_retrieval_agents.py`
- `tests/test_retrieval_agent_performance.py`
- `tests/test_retrieval_agent_security.py`
- Related chat/case/regression callers and mocks

## 5. Files modified (this security/integration task)

### Added

- `app/api/__init__.py`
- `app/api/auth.py` — interim API-key authentication
- `tests/test_retrieval_api_auth.py`
- `tests/test_retrieval_legacy_budgets.py`
- `tests/test_retrieval_quality_golden.py`
- `docs/temp/RETRIEVAL_SECURITY_AND_INTEGRATION_REPORT.md` (this file)

### Modified (security/integration)

- `app/api/routes/sources.py` — auth, path suppression, embedded N+1 fix, safe sync errors
- `app/services/knowledge_retrieval_service.py` — fail-closed adapters, internal helpers, legacy budgets
- `app/services/providers/base_provider.py` (+ contract/cim/elm/lmou) — org SQL filters + `joinedload`
- `app/services/follow_up_chat_service.py` — orchestrator migration
- `app/services/case_service.py` — explicit internal search helper
- `app/retrieval_config.py` — legacy fan-out budgets
- `.env.example` — API key + reverse-proxy rate-limit notes
- `scripts/{diagnose_regression,phase1_1_verification,phase1_1_source_coverage_diagnostic}.py`
- Tests updated: retrieval agents/performance, chat retrieval, case service/api, regression harness, relevance phase0 mocks

Preserved preexisting W5 / retrieval-agent working-tree files without resetting them.

## 6. Independent findings by severity

### BLOCKER (fixed)

1. **Adapter fail-open:** `retrieve_with_agents` / `search_with_agents` defaulted `authorization=None` to `global_corpus()`, undoing orchestrator fail-closed behavior for `/sources/search/`.
2. **No HTTP authentication on `/sources/*`:** every listing, retrieval, and mutation endpoint was anonymous.
3. **Unauthenticated mutating source operations:** upload, seed, create, sync, download, process.

### HIGH (fixed)

4. **Legacy `search_all` / providers lacked organization SQL filters** — defaulted to scanning all orgs.
5. **Legacy ask/report/chat/case preview had no authorization parameter** and no explicit trust declaration.
6. **`local_path` leakage** on source listing / embedded / upload responses.
7. **Security tests gave false confidence** — orchestrator fail-closed while the public adapter fail-opened; no adapter regression test.

### MEDIUM (fixed where safe)

8. **`GET /sources/embedded/` N+1** — per-source count queries replaced with one grouped query.
9. **Legacy embedding fan-out** — identical queries re-embedded; issue/query/backfill counts uncapped.
10. **Sync endpoint returned raw exception strings** — now stable 500 detail.
11. **Upload filename path handling** — restricted to a safe basename pattern.

### LOW / INFORMATIONAL

12. `/cases` and steward UI remain without application auth (product/UX decision; case UUID is still obscurity-based).
13. No persisted User/Role/Organization membership model.
14. Ask/report retain `search_all` for issue-decomposition compatibility (secured + bounded; Supervisor Manual still primarily via agent/chat path).
15. Exact vector search remains sequential at current corpus size.
16. Bandit / pip-audit not installed; not added in this task.

## 7. Authentication mechanism discovered or implemented

**Discovered:** none for HTTP callers. Only `Depends(get_db)` and outbound `OPENAI_API_KEY`.

**Implemented (interim):** `app/api/auth.py`

- Secrets: `GRIEVANCEHUB_API_KEY` (read), `GRIEVANCEHUB_ADMIN_API_KEY` (admin)
- Headers: `Authorization: Bearer <key>` or `X-API-Key: <key>`
- Comparison: `hmac.compare_digest`
- Fail closed on missing/invalid credentials and when required keys are unset (503 for unconfigured server keys)
- Credentials never logged; principal IDs use key fingerprints only

## 8. Interim versus final authentication limitations

This is an **interim API-key boundary**, not multi-user identity management.

Limitations:

- No user accounts, sessions, OAuth, or steward memberships
- No organization membership derivation
- Admin vs read is two server-configured secrets, not RBAC
- `/cases`, exports, and steward UI are not covered by this boundary
- Long-term identity provider selection remains a **product decision**

## 9. Principal binding

`AuthenticatedPrincipal` is server-derived from the validated API key:

- `role`: `read` | `admin`
- `principal_id`: `api-read:<sha256-prefix>` or `api-admin:<sha256-prefix>`

Clients cannot supply principal IDs, roles, organization IDs, or admin flags as trusted request fields.

## 10. RetrievalAuthorizationContext construction

External routes:

```text
principal.retrieval_authorization()
→ authenticated=True
→ allow_global_sources=True
→ allowed_organization_ids=∅
→ is_admin=False
→ allow_all_organizations=False
```

Trusted internal helpers (API routes must not call these):

- `retrieve_global_corpus_internal(principal_id=...)`
- `search_global_corpus_internal(principal_id=...)`

These construct `RetrievalAuthorizationContext.global_corpus(principal_id=...)` explicitly in code.

## 11. Fail-open behavior removed

| Before | After |
|--------|-------|
| `authorization or global_corpus(...)` | `authorization` required; `None` → unauthenticated → `authorization_failure` |
| Missing auth on `/sources/search/` | 401 |
| Implicit trusted default for unknown callers | Explicit internal helpers only |

Regression coverage in `tests/test_retrieval_api_auth.py`.

## 12. Source-route permission matrix

| Route | Permission |
|-------|------------|
| `GET /sources/` | read |
| `GET /sources/embedded/` | read |
| `GET /sources/search/` | read |
| `GET /sources/ask/` | read |
| `GET /sources/report/` | read |
| `GET /sources/{id}/chunks/{index}` | read |
| `POST /sources/upload-pdf/` | admin |
| `POST /sources/seed-official/` | admin |
| `POST /sources/` | admin |
| `POST /sources/{id}/sync` | admin |
| `POST /sources/{id}/download` | admin |
| `POST /sources/{id}/process` | admin |

Read responses suppress `local_path` unless the principal is admin. Chunk payloads strip `local_path`.

## 13. Legacy consumer migration decisions

| Consumer | Decision | Rationale |
|----------|----------|-----------|
| `/sources/search/` | Agent path + auth | Already on orchestrator; now principal-bound |
| `/sources/ask/` | Retain bounded `search_all` + auth | Needs issue decomposition for `AnalysisService.answer_question` |
| `/sources/report/` | Retain bounded `search_all` + auth | Needs gaps, coverage audit, issue analysis |
| Case report preview | `search_global_corpus_internal` | Preserve report contract; explicit trust |
| Follow-up chat | Migrate to `retrieve_global_corpus_internal` | Passage-oriented; gains Supervisor Manual; avoids report fan-out |

## 14. Ask integration

Authenticated. Uses `search_all(..., authorization=principal.retrieval_authorization())`. Issue decomposition preserved. Supervisor Manual evidence is not injected into ask in this phase (compatibility choice).

## 15. Report integration

Authenticated. Same secured `search_all` path. Report builders continue to receive `all_chunks`, gaps, indexed types, and coverage audit.

## 16. Case preview integration

`CaseService.build_analysis_report_preview` calls `search_global_corpus_internal(principal_id="case-report-preview-internal")`. No client-supplied scope.

## 17. Follow-up chat integration

`retrieve_indexed_source_passages` now uses the orchestrator via `retrieve_global_corpus_internal(principal_id="follow-up-chat-internal")`.

Passages include `evidence_role`, `content_trust=untrusted_evidence`, and `retrieval_agent`. Known facts remain in the query text via `build_chat_retrieval_query`.

## 18. Agent query counts

Unchanged budgets (verified by performance tests):

| Path | SQL statements |
|------|----------------|
| ContractAgent | 1 |
| SupervisorManualAgent | 1 |
| Combined orchestration | 2 |
| No-results combined | 2 |
| Provenance hydration | 0 extra |
| Adapter conversion | 0 extra DB |

One query embedding per orchestrated request.

## 19. Legacy/migrated query counts

| Path | Behavior |
|------|----------|
| Legacy `search_all` | Intentional multi-query fan-out, now capped |
| Provider search | 1 SQL per provider call; `joinedload(source_document)` prevents ORM N+1 |
| Indexed source types | 1 distinct query, org-filtered |
| Embedded listing | 1 grouped count query (was N+1) |
| Follow-up chat (migrated) | Agent budgets (1–2 SQL + 1 embedding) |

## 20. Embedding-call budgets

| Path | Budget |
|------|--------|
| Orchestrator | 1 embedding / request |
| Legacy identical-text reuse | request-local cache |
| Legacy max embeddings | `LEGACY_MAX_TOTAL_EMBEDDING_CALLS = 48` |
| Legacy max queries/issue | `LEGACY_MAX_QUERIES_PER_ISSUE = 6` |
| Legacy max issues | `LEGACY_MAX_DECOMPOSED_ISSUES = 8` |
| Embedding timeout/retries | 20s / 1 retry |

## 21. N+1 findings

| Finding | Status |
|---------|--------|
| Agent path per-result/source queries | None (projection join) |
| Legacy provider lazy `source_document` | Fixed with `joinedload` |
| Embedded listing per-source counts | Fixed with grouped query |
| Intentional multi-query retrieval | Not labeled N+1; now budgeted |

## 22. Query fan-out findings

Legacy `search_all` deliberately expands issues/queries/backfills. That is algorithmic fan-out, not ORM N+1. Duplicate identical query embeddings within one request are eliminated. Caps added for issues, queries, backfills, provider calls, embeddings, and candidate chunks.

## 23. Retrieval-quality evaluation

Deterministic golden suite: `tests/test_retrieval_quality_golden.py`

Covered:

- clear contract / supervisor / combined routing
- article numbers, grievance handling, Step 1, attendance, safety, annual leave, arbitration
- ambiguous / irrelevant / no-evidence defaults
- candidate floor vs final gate
- supervisor role labeling (`supervisory_guidance_non_controlling`)
- empty corpus → no fabricated results

No live OpenAI calls in automated tests.

## 24. Threshold decision

**Unchanged.**

- Agent candidate floor: `RETRIEVAL_MIN_CANDIDATE_SIMILARITY = 0.45`
- Final acceptance: `MIN_COMBINED_RETRIEVAL_SCORE = 0.30`
- Legacy provider floor: `MIN_EMBEDDING_SIMILARITY = 0.62`

Reason: mid-similarity candidates may be scored, but weak combined scores still fail the shared gate. Correct no-result outcomes remain preferred to irrelevant evidence. No threshold retuning was justified by the golden checks.

## 25. Security tests

Suites:

- `tests/test_retrieval_agent_security.py` (orchestrator/agent)
- `tests/test_retrieval_api_auth.py` (HTTP + adapter fail-closed + principal binding)

Covered: missing/invalid auth, read vs admin, fail-open removal, org SQL filters, escalation resistance, path suppression, untrusted evidence labeling, redacted errors, safe logging patterns.

Bandit / pip-audit: **not installed**; not introduced in this task.

## 26. Rate/cost controls

Application controls:

- Query length ≤ 2000
- Candidate/result/per-source caps
- Embedding timeout + retry bound
- One embedding reuse on agent path
- Legacy fan-out budgets
- Request-local embedding dedupe

**Not claimed:** multi-process in-memory rate limiting.

**Deployment requirement (documented in `.env.example`):** enforce reverse-proxy rate limits on `/sources/search/`, `/sources/ask/`, and `/sources/report/` before any internet exposure.

## 27. PostgreSQL query plans

Representative live `EXPLAIN ANALYZE` (Supervisor Manual exact vector order, `LIMIT 48`, global org filter):

```text
Limit
  -> Sort (top-N heapsort)
       -> Hash Join (source_chunks ⋈ source_documents)
            -> Seq Scan on source_chunks (embedding IS NOT NULL)
            -> Hash / Seq Scan on source_documents
                 Filter: SUPERVISOR_MANUAL + organization_id IS NULL
Planning Time: ~4.9 ms
Execution Time: ~102 ms
```

Filters applied in SQL. Candidate limit applied by PostgreSQL. Org/global predicate present.

## 28. ANN-index decision

**Do not add HNSW/IVFFlat now.**

Evidence: ~1.9k embedded chunks; exact search still suitable; high filter selectivity; citation recall prefers exact ordering.

Revisit when embedded chunks grow ~10× (~20k) or DB time becomes a material share of request latency.

## 29. Functional test results

Retrieval-focused subset (agents + performance + security + API auth + budgets + golden + chat):

- **107 passed** (earlier focused run)

Broader focused subsets:

- W5 / PDF / step progression: **62 passed**
- Case service/API/saved: **37 passed**

## 30. Full-suite result

```text
.\venv\Scripts\python.exe -m pytest -q --tb=line
```

- **614 passed**
- **0 failed**
- **0 errors**
- **1 skipped** (`tests/test_regression_harness.py::test_regression_live_pipeline_smoke`, requires `RUN_REGRESSION=1`)
- **0 deselected**
- **331 warnings** (existing `datetime.utcnow` deprecations)

No automated test made a live OpenAI request.

One suite failure during integration was caused by a stale mock in `tests/test_relevance_phase0.py` rejecting new `authorization=` kwargs; fixed and re-run green.

## 31. Remaining security limitations

1. Interim API keys are not end-user identity.
2. `/cases`, exports, and steward UI remain unauthenticated at the HTTP layer.
3. No organization membership model → external access is global-corpus-only by policy.
4. Contract corpus rows may still be searchable under the pre-W5 pending compatibility predicate when embeddings exist.
5. Reverse-proxy rate limiting is required for internet exposure and is not implemented in-app across processes.
6. Ask/report do not yet surface Supervisor Manual via agents (chat does).

## 32. Remaining blockers

**None for completing this security/integration task’s safe scope.**

Product decisions still required before production internet exposure:

- Long-term multi-user identity provider
- Whether `/cases` / steward UI adopt the same auth boundary
- Optional ask/report migration onto orchestrator while preserving issue-decomposition UX

## 33. Production-readiness classification

| Environment | Suitable? |
|-------------|-----------|
| Local development | **Yes** (set API keys in `.env`) |
| Controlled internal deployment | **Yes, with caveats** — API keys required, reverse-proxy recommended, network not public |
| Production internet exposure | **No** — interim API keys + unauthenticated case/steward surfaces are insufficient |

## 34. Recommended next phase

1. Product decision on identity (sessions/OIDC/etc.) and steward/org membership.
2. Extend authentication to `/cases` and steward UI without breaking local steward workflows.
3. Optionally migrate ask/report to a hybrid: keep LegalIssueAnalyzer, acquire evidence via orchestrator, preserve AnalysisService contracts.
4. Add reverse-proxy rate-limit configuration as checked deployment documentation/runbook.
5. Revisit ANN indexing only after measured latency/corpus growth triggers in §28.

---

## Acceptance criteria checklist

- [x] Externally reachable retrieval routes require authentication
- [x] Source mutations require stronger (admin) authorization
- [x] Public callers cannot receive an implicit trusted global context
- [x] Organization/admin scope cannot come from untrusted request parameters
- [x] Retrieval SQL remains parameterized
- [x] No demonstrated N+1 path remains in agent or migrated listing/provider paths
- [x] Query and embedding fan-out is bounded
- [x] Legacy consumers are secured
- [x] Migrated consumers preserve compatibility shapes
- [x] Retrieved text remains untrusted evidence
- [x] Sensitive data/secrets are not logged by the new auth/retrieval paths
- [x] Full regression suite passes
