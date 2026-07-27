# W6 Remaining Roadmap and W7 Handoff

**Status:** Authoritative implementation handoff (documentation only)  
**Created:** 2026-07-26  
**Last updated:** 2026-07-26 (W6 Batch 4 / M10 completion)
**Branch at authoring:** `main`  
**Batch 4 starting HEAD:** `35d5945` (`fix(w6): reconcile schema metadata and step progression`)

This document records the completed W6 production-readiness sequence,
disposition of audit findings, and the expanded W7 plan (AI quality + retrieval
modernization). Batches 1–4 and W6 M0–M10 are complete. W7 remains planned,
gated, and not started.

---

## 1. Executive summary

GrievanceHub has completed W6 M0–M10 and all four production-readiness
remediation batches:

| Batch | Commit | Scope |
|-------|--------|-------|
| Batch 1 | `4ab328d` | FE-1, BE-2, BE-3, BE-6/SEC-2, export tests, MAINT-2 |
| Batch 2 | `1111b4e` | BE-1 (service-layer idempotency), BE-4 (query indexes) |
| Batch 3 | `35d5945` | ARCH-2/MAINT-1 progression cleanup and Alembic metadata reconciliation |
| Batch 4 / M10 | This completion commit | UI/a11y/PDF polish, Step 3 contract correction, live validation, W6 exit review |

**W6 is complete.** Batch 3 removed the dead progression service and reconciled
ORM/schema metadata without migration changes. Batch 4/M10 completed workspace
state polish, keyboard/accessibility foundations, print/PDF UX, realistic
analysis and grievance PDF validation, the Step 3 pre-persistence contract
correction, and the final W6 regression/exit review.

**Explicit deferrals** remain: FE-2 global TypeScript strict mode,
`datetime.utcnow()` cleanup, React Router remediation, and `case_service.py`
splitting remain post-W7 unless intentionally reprioritized. CI/CORS remain
W11; production identity/authorization remain W9.

**W7 has not begun.** Its W6 entry gate is now satisfied, but implementation
still requires its own authorization. W7 retains its
canonical scope from `docs/ROADMAP.md` and is **expanded** with two integrated
tracks: **Track A** (AI evaluation, hallucination detection, quality
guardrails) and **Track B** (retrieval modernization, pgvector baseline,
conditional TurboVec evaluation). PostgreSQL remains the system of record;
TurboVec adoption remains conditional on benchmark results.

---

## 2. Current branch and commit state

| Item | Value | Source | Confidence |
|------|-------|--------|------------|
| Branch | `main` | `git status`, `git log` | HIGH |
| Batch 1 SHA | `4ab328d` (`fix(w6): address production readiness findings`) | `git log` | HIGH |
| Batch 2 SHA | `1111b4e` (`fix(w6): harden idempotency and case query indexes`) | `git log` | HIGH |
| Batch 3 SHA | `35d5945` (`fix(w6): reconcile schema metadata and step progression`) | `git log` | HIGH |
| Batch 4 starting HEAD | `35d5945` | `git log --decorate -5` | HIGH |
| Tracked working tree at Batch 4 start | Clean | Batch 4 checkpoint | HIGH |
| Untracked files | Pre-existing and Batch-era `docs/temp/` diagnostics, baselines, smoke helpers, audit reports | `git status` | HIGH |
| Alembic current | `i0j1k2l3m4n5` (head) | `python -m alembic current` via venv | HIGH |
| Alembic heads | Single head: `i0j1k2l3m4n5` | `python -m alembic heads` | HIGH |

Batches 1–3 are committed. Batch 4 proceeded on a clean tracked tree atop
Batch 3 while preserving inherited untracked diagnostics.

---

## 3. W6 status

| Milestone / workstream | State | Source |
|------------------------|-------|--------|
| W6 M0–M10 | **Complete** | `PROJECT_STATE.md`, Batch 4 report |
| Production-readiness Batch 1 | Complete — `4ab328d` | Batch 1 report, git log |
| Production-readiness Batch 2 | Complete — `1111b4e` | Batch 2 report, git log |
| Production-readiness Batch 3 | **Complete — `35d5945`** | Batch 3 report, git log |
| Production-readiness Batch 4 | **Complete as W6 M10** | Batch 4 report |
| W6 M10 — Polish & a11y | **Complete** | Batch 4 report |
| W6 exit (roadmap) | **PASS WITH NON-BLOCKING FINDINGS — W6 COMPLETE** | Batch 4 report §24–28 |
| W7 | Next phase; planned, gated, and not started | §10, `docs/ROADMAP.md` |

---

## 4. Batch 1 verified summary

**Verdict:** PASS  
**Commit:** `4ab328d`  
**Source:** `docs/temp/W6_PRODUCTION_READINESS_REMEDIATION_1_REPORT.md`, `git show 4ab328d`

| ID | Audit finding | Remediation | Verified outcome |
|----|---------------|-------------|----------------|
| A | FE-1 | Cache invalidation after Save/Save-and-Print | `artifactKeys` + `workflowKeys` invalidated case-scoped; `saveCacheInvalidation.test.tsx` |
| B | BE-2 (+2 same-class sites) | Structured `logger.warning` replacing silent swallow | 4 sites in 3 services; caplog tests |
| C | BE-3 | Bounded previous/next timeline queries | `case_history_context_service.py`; 17+ adjacency tests |
| D | BE-6 / SEC-2 | Chunked upload (1 MiB), cleanup on failure | Route helper + service try/except; 18 upload tests |
| E | Export tests | Test fixture isolation (`get_db` MagicMock) | 9 previously failing tests pass; production unchanged |
| F | MAINT-2 | Route doc drift in `W6_UI_ARCHITECTURE.md` | `/history`, `/memory` removed as routes |

**Validation (reported):** 664 backend non-integration tests passed; frontend
typecheck, lint, 140 tests, build passed; live validation PASS.

**Explicitly deferred from Batch 1:** idempotency DB constraints, FK indexes,
pgvector ANN, `case_service.py` split, step-progression rewrite, TS strict,
CI, CORS, auth, dependency upgrades — Batch 1 report §8.

---

## 5. Batch 2 verified summary

**Verdict:** PASS WITH NON-BLOCKING FINDINGS  
**Commit:** `1111b4e`  
**Source:** `docs/temp/W6_PRODUCTION_READINESS_REMEDIATION_2_REPORT.md`, `git show 1111b4e`, repository inspection

### Scope completed

| Objective | Verified |
|-----------|----------|
| BE-1 idempotency race handling | Service-layer `begin_nested()` + narrow `IntegrityError` classification in 3 call sites |
| BE-4 case-query indexes | 5 new composite indexes; 3 pre-existing indexes reconciled in ORM only |

### Database idempotency (verified)

Three **pre-existing** PostgreSQL unique indexes confirmed (not created by Batch 2):

| Index | Table | Scope |
|-------|-------|-------|
| `ix_case_domain_events_case_idempotency` | `case_domain_events` | `(case_uuid, idempotency_key)` |
| `ix_case_form_draft_records_idempotency` | `case_form_draft_records` | `(case_uuid, idempotency_key)` |
| `ix_case_saved_artifacts_idempotency` | `case_saved_artifacts` | `(case_uuid, idempotency_key)` |

Nullable `idempotency_key` values remain permitted (PostgreSQL NULL-distinct
semantics). Duplicate diagnostics: **0 duplicate groups, 0 affected rows**.

### Service-layer concurrency (verified)

- Normal existing-record fast path
- `begin_nested()` savepoints around contested inserts only
- `app/services/idempotency_conflict_utils.py` — constraint-name classification
- Winner-row recovery; replay-safe responses; no duplicate downstream side effects

### Query indexes added (verified)

| Index | Table |
|-------|-------|
| `ix_case_messages_case_id_created_at` | `case_messages` |
| `ix_case_report_versions_case_id_version` | `case_report_versions` |
| `ix_case_step_outcomes_case_id_recorded_at` | `case_step_outcomes` |
| `ix_case_timeline_events_case_id_event_timestamp` | `case_timeline_events` |
| `ix_case_form_draft_records_case_id_created_at` | `case_form_draft_records` |

Three tables reconciled in ORM metadata without new DDL:
`CaseStep` (`ix_case_steps_case_id_step_type`), `CaseSavedArtifact`
(`ix_case_saved_artifacts_case_type`), `CaseAsset`
(`ix_case_assets_case_id_category`).

### Validation (verified against report + commit)

| Check | Result |
|-------|--------|
| Backend non-integration | 676 passed |
| PostgreSQL integration | 5 passed; 1 unrelated skipped |
| Frontend typecheck / lint / test / build | Pass (140 tests) |
| Migration upgrade/downgrade/re-upgrade | Passed (prior session + re-confirmed) |
| Alembic heads | Single head `i0j1k2l3m4n5` |
| Live smoke | 14/14 checks (PDF `saved_pdf_failed` on minimal stub — pre-existing) |

---

## 6. Complete audit-finding disposition matrix

Source: `docs/temp/W6_COMPREHENSIVE_PRODUCTION_READINESS_AUDIT.md` Pass 1–7
prioritized plan.

| ID | Finding | Severity | Disposition | Notes / source |
|----|---------|----------|-------------|----------------|
| FE-1 | Missing artifact/workflow cache invalidation | Medium | **COMPLETED BY BATCH 1** | Remediation A |
| ARCH-2 | Two step-progression services; naming collision | Medium | **COMPLETED BY BATCH 3** | Dead in-memory service removed; persistence/rules names clarified |
| MAINT-1 | Dead in-memory step-progression state | Medium | **COMPLETED BY BATCH 3** | `35d5945` |
| BE-1 | Idempotency TOCTOU | Medium | **COMPLETED BY BATCH 2** | Service layer + ORM reconciliation |
| BE-2 | Silent exception swallowing | Medium | **COMPLETED BY BATCH 1** | Remediation B (+2 sites) |
| BE-4 | Missing `case_id` FK/query indexes | Medium | **COMPLETED BY BATCH 2** | 5 new + 3 ORM-only |
| BE-5 | No pgvector ANN index | Medium | **DEFERRED TO W7** | Audit explicitly: "revisit at W7"; Batch 2 §10 |
| OPS-1 | No CI workflow | Medium | **DEFERRED TO DEPLOYMENT HARDENING (W11)** | Audit milestone W11 |
| BE-6 / SEC-2 | Upload buffer-before-validate | Low-Med | **COMPLETED BY BATCH 1** | Remediation D (streamed reads) |
| FE-2 | TypeScript strict mode disabled | Low | **DEFERRED POST-W7** | Explicit project-owner decision |
| BE-3 | Unbounded timeline adjacency | Low | **COMPLETED BY BATCH 1** | Remediation C |
| SEC-1 | No CORS middleware | Low | **DEFERRED TO DEPLOYMENT HARDENING (W11)** | Audit milestone W11 |
| OPS-2 | `pytest.ini` minimal config | Low | **DEFERRED POST-W7** or W11 | No CI to enforce; audit backlog/W11 |
| MAINT-2 | Route documentation drift | Low | **COMPLETED BY BATCH 1** | Remediation F |
| ARCH-1 / MAINT-3 | `case_service.py` oversized | Low | **DEFERRED POST-W7** | Large refactor; audit backlog |
| — | Pre-existing Alembic metadata drift | Non-blocking | **COMPLETED BY BATCH 3** | ORM metadata reconciled; no DDL; Alembic check clean |
| — | ~397 `datetime.utcnow()` warnings | Non-blocking | **DEFERRED POST-W7** | Batch 2 report §10.3 |
| — | Realistic PDF live-smoke | Non-blocking | **COMPLETED BY BATCH 4** | Analysis, Step 1, Step 2, Step 3 boundary, controlled failure PASS |
| — | React Router npm audit advisory | Non-blocking | **DEFERRED POST-W7** | Batch 1 §6; not introduced by remediation |
| W6 M10 | Polish, a11y, empty/error states, print/PDF validation, exit review | Milestone | **COMPLETED BY BATCH 4** | Final verdict: PASS WITH NON-BLOCKING FINDINGS |
| W9 auth | No production authentication | Intentional | **DEFERRED TO W9** | Roadmap; not an audit defect |
| W11 deploy | Packaging, CORS, CI | Intentional | **DEFERRED TO DEPLOYMENT HARDENING** | Roadmap |

---

## 7. Completed Batch 3 scope

**Project-owner decision (2026-07-26):**

1. Resolve audit findings **ARCH-2 / MAINT-1**:
   - inventory all progression/workflow classes and call sites;
   - preserve `CaseWorkflowService` as the authoritative persisted FSM;
   - preserve actively used stateless template-availability and grievance-draft
     helpers;
   - delete or explicitly quarantine verified dead in-memory stateful behavior;
   - remove the misleading service naming collision;
   - prove no production router depends on in-memory progression state.
2. Independently investigate and safely reconcile the pre-existing Alembic
   ORM/schema metadata drift concerning `case_assets.asset_uuid`,
   `case_domain_events.event_id`, `case_form_draft_records.draft_uuid`,
   `case_saved_artifacts.artifact_uuid`, `case_step_outcomes.outcome_uuid`,
   `case_timeline_events.event_uuid`, and `case_memories`.

**Implementation boundaries:** no workflow redesign; no product-semantic
change; no Step 3 form; no destructive DDL; no old-migration edits; no
pgvector ANN work; no `case_service.py` split.

**Expected commit boundary:**
`fix(w6): reconcile schema metadata and step progression`.

**Completion:** Implemented and committed as `35d5945`. Alembic current and
heads remain `i0j1k2l3m4n5`; `alembic check` reports no new operations.

---

## 8. Completed Batch 4 scope — W6 M10

**Project-owner decision (2026-07-26):** Batch 4 and W6 M10 are the same
remaining work unit:

- workspace empty/loading/error-state polish;
- keyboard navigation and accessibility;
- print-route polish;
- realistic analysis and grievance PDF live validation;
- final W6 regression and exit review.

**Explicit exclusion:** FE-2 global TypeScript strict-mode migration is
deferred post-W7 unless intentionally reprioritized.

**Completion:** Batch 4/M10 is complete. UI-state, keyboard/focus, safe-error,
and PDF UX changes are implemented; realistic PDF paths and the final W6 exit
matrix passed. See
`docs/temp/W6_PRODUCTION_READINESS_REMEDIATION_4_M10_REPORT.md`.

---

## 9. Known unresolved W6 findings

Carried from Batch 2 and audit; none block Batch 2 correctness.

### A. Pre-existing Alembic metadata drift

**Columns/tables:** `case_assets.asset_uuid`, `case_domain_events.event_id`,
`case_form_draft_records.draft_uuid`, `case_saved_artifacts.artifact_uuid`,
`case_step_outcomes.outcome_uuid`, `case_timeline_events.event_uuid`,
entire `case_memories` table.

**Cause (reported):** SQLAlchemy `unique=True` + `index=True` autogenerate
interaction predating Batch 2.

**Status:** Resolved by Batch 3 without migration or DDL.
**Do not assume correction approach** without migration review.

**Source:** Batch 2 report §10.1; `alembic check` output referenced therein.
**Confidence:** HIGH (finding); LOW (remediation assignment).

### B. BE-5 — no pgvector ANN index

Explicitly deferred from Batch 2. Audit assigns natural revisit to **W7**
(retrieval performance measurement). **Not** automatically Batch 3/4.

**Source:** Audit BE-5; Batch 2 §10.2. **Confidence:** HIGH.

### C. ~397 `datetime.utcnow()` deprecation warnings

Pre-existing across codebase; unrelated to Batch 2 changes.

**Source:** Batch 2 §8.1, §10.3. **Confidence:** HIGH.

### D. PDF live-smoke limitation

Batch 2 live smoke: artifact persisted; PDF returned `saved_pdf_failed` on
minimal synthetic `report_data` — pre-existing graceful degradation, not a
Batch 2 regression.

**Realistic PDF live validation:** Completed by Batch 4/M10 for analysis,
Step 1, Step 2, Step 3 rejection-before-persistence, and controlled PDF failure.

**Source:** Batch 2 report §9; `test_save_and_print_report_*`. **Confidence:**
HIGH (limitation); LOW (future plan assignment).

---

## 10. Updated W7 project decision

**Explicit decision (this handoff, user directive 2026-07-26):**

1. **W7 begins only after W6 is complete** (M10 + remaining production-readiness
   batches confirmed by user + roadmap exit criteria).
2. **W7 retains** all scope from `docs/ROADMAP.md` § "W7 — RAG Evaluation and
   Output Quality."
3. **W7 is expanded** with two integrated engineering tracks (not separate
   post-W7 projects):

| Track | Focus |
|-------|-------|
| **Track A** | AI evaluation, hallucination detection, groundedness scoring, runtime guardrails, regression testing, evaluation dashboard, model comparison |
| **Track B** | Retrieval modernization — pgvector baseline, `VectorSearchBackend` abstraction, conditional TurboVec shadow evaluation and promotion |

4. Tracks share one **versioned benchmark** and evaluation framework because
   retrieval quality, citation quality, groundedness, and backend comparison
   require the same measurement substrate.

5. **W7 has not begun.** No benchmark, dashboard, TurboVec install, or ANN index
   work is in progress.

**Source:** User handoff directive; `docs/ROADMAP.md` W7 baseline. **Confidence:** HIGH (decision); HIGH (W7 not started).

---

## 11. Existing W7 scope (canonical)

From `docs/ROADMAP.md` — unchanged baseline:

- Versioned golden evaluation dataset with expected authorities, citations,
  required/prohibited conclusions, abstention cases
- Automated retrieval, citation-grounding, faithfulness, unsupported-claim metrics
- Regression comparisons, latency/cost measurement, failure categorization
- Tuning chunking, retrieval, reranking, prompts, synthesis
- Reproducible evaluation commands and recorded baselines
- Approved thresholds only after explicit user approval (not invented)
- Exit criteria: versioned dataset, reproducible commands, measured citation accuracy
  and unsupported-claim rate, retrieval regression detection, documented limitations

**Explicit W7 exclusions (canonical):** multi-agent as primary delivery (W8),
W9 security program, W10 sensitive corpus, W11 deployment.

**Dependencies (canonical):** W6 steward workflows sufficient for realistic
scenarios; existing single-pipeline architecture.

---

## 12. W7 Track A — AI quality and hallucination control

**Purpose:** Prove GrievanceHub produces reliable, evidence-based grievance
work — not to claim automatic elimination of hallucinations.

### Terminology (required)

Use: detect unsupported output; score groundedness; retry retrieval; regenerate
with improved evidence; block unsafe output; ask for clarification; abstain
safely; escalate for review.

Avoid claiming: automatic hallucination "fixing" or model self-certification
without independent checks.

### Guiding principle

Every material AI-generated claim should be traceable to retrieved authority or
approved case evidence.

### A. Evaluation dataset

Versioned benchmark of realistic grievance scenarios:

- Step 1 and Step 2 grievances; discipline; attendance; overtime; contract
  interpretation; local agreements
- Incomplete, conflicting, and weak-retrieval conditions; misleading prompts
- Cases where correct behavior is **abstention**

Per case define: approved evidence; expected authorities; expected material
conclusions; prohibited unsupported claims; citation expectations;
safe-abstention expectations; scoring rubric.

Synthetic or properly authorized data only — no real confidential grievance data.

### B. Automated evaluation pipeline

Measure at minimum: retrieval recall/precision; groundedness; citation presence,
correctness, entailment/support; unsupported-claim rate; completeness; relevance;
internal consistency; safe-abstention behavior; response latency; token/cost when
available.

Output: machine-readable, versioned results.

### C. Hallucination detection

Detect: nonexistent contract articles; invented arbitration decisions; fabricated
quotations; unsupported factual assertions; claims contradicted by evidence;
missing citations; citations that do not support claims; overconfident
conclusions from incomplete evidence.

### D. Recovery and runtime guardrails

On groundedness/citation failure (bounded retries only):

1. Retry retrieval  
2. Broaden/reformulate query within approved boundaries  
3. Regenerate with corrected context  
4. Re-evaluate revised output  
5. Ask user for missing evidence  
6. Safely abstain  
7. Flag for review  

No infinite self-correction loops. No model-only certification.

### E. Regression testing

Run benchmark after changes to prompts, retrieval, chunking, embeddings,
reranking, citation generation, LLM providers, model versions, guardrail logic.

Distinguish: offline evaluation vs integration testing vs runtime validation vs
future CI enforcement. **CI does not currently exist** (OPS-1).

### F. Evaluation dashboard

Plan displays for: overall score; unsupported-claim rate; citation success;
retrieval metrics; abstention accuracy; retry/recovery outcomes; latency; cost;
trends by benchmark version; model comparison; retrieval-backend comparison;
redacted failure examples.

### G. Model comparison

Framework remains model-agnostic — same benchmark across LLMs without
architecture rewrites.

**Mapping to canonical W7:** Extends ROADMAP W7 "In-scope work" with explicit
hallucination detection, guardrails, and dashboard — integrated, not a separate
project.

**Confidence:** HIGH (user directive and approved planning structure).

---

## 13. W7 Track B — Retrieval modernization and TurboVec

### Non-negotiable architectural principles

- PostgreSQL remains **system of record** and metadata/authorization truth
- **pgvector is not removed** during development
- Current RAG pipeline, case workflow, citation engine, evidence extraction,
  and report generation **remain intact**
- TurboVec is **not** promoted on marketing claims or synthetic latency alone
- Backend selection is **benchmark-driven**
- No retrieval backend may bypass source authorization or case isolation

### Current conceptual architecture

```text
UI → FastAPI → Retrieval Services → pgvector → Authority Ranking
  → Evidence Extraction → Citation Validation → Analysis / Grievance Generation
```

### Target conceptual architecture

```text
UI → FastAPI → Retrieval Orchestrator
  → PostgreSQL Metadata and Authorization Filter
  → Pluggable Vector Backend
  → Hybrid Ranking → Cross-Encoder Reranking
  → Authority Ranking → Evidence Extraction → Citation Validation
  → Analysis / Grievance Generation
```

### Planned implementation sequence

1. Establish pgvector baseline using W7 benchmark  
2. Introduce `VectorSearchBackend` abstraction — no user-visible change  
3. Implement `PgVectorSearchBackend` behind interface  
4. Implement `TurboVecSearchBackend` separately  
5. PostgreSQL owns metadata, authorization, allowlisting  
6. Search only allowlisted `SourceChunk` identifiers  
7. Reliable PG ↔ TurboVec sync (prefer outbox-driven if supported)  
8. TurboVec **shadow mode** beside pgvector  
9. Silent comparison on identical queries and benchmark cases  
10. Evaluate: latency, recall, precision, citation accuracy, groundedness, memory,
    stability, sync correctness, crash recovery, authorization isolation  
11. Promote TurboVec **only if** no citation regression, no auth leakage, equal or
    better retrieval quality, meaningful performance benefit, reliable sync  
12. Transparent backend switching and rollback  

TurboVec adoption is **not predetermined** — benchmark may keep pgvector in production.

**BE-5 ANN index:** Natural fit within Track B step 1 (pgvector baseline tuning)
before shadow deployment — aligns with audit "revisit at W7."

**Confidence:** HIGH (principles and approved W7.0–W7.8 planning structure).

---

## 14. Integrated W7 execution order

Sequence matters — benchmark and baseline precede replacement:

| Phase | Track | Activity | Depends on |
|-------|-------|----------|------------|
| W7.0 | A | Evaluation dataset v1 + rubric | W6 complete |
| W7.1 | A | Offline evaluation pipeline + baseline pgvector run | W7.0 |
| W7.1 | B | pgvector baseline metrics (includes BE-5 ANN evaluation) | W7.0 |
| W7.2 | A | Hallucination detector + unsupported-claim scoring | W7.1 |
| W7.2 | B | `VectorSearchBackend` + `PgVectorSearchBackend` (no behavior change) | W7.1 |
| W7.3 | B | TurboVec backend + sync design | W7.2 B |
| W7.4 | B | Shadow deployment + silent comparison | W7.3, W7.2 A metrics |
| W7.5 | A | Runtime guardrails (bounded retry/regenerate/abstain) | W7.2 A |
| W7.6 | A+B | Evaluation dashboard (models + backends) | W7.4, W7.5 |
| W7.7 | A | Regression harness + trend tracking | W7.1+ |
| W7.8 | A+B | Promotion decision or pgvector retention record | W7.4–W7.7 |
| Future | A | CI enforcement (optional) | OPS-1 / W11 CI exists |

**Approved planning structure:** Sub-milestone IDs W7.0–W7.8 are the current
W7 structure, subject to refinement during W7 implementation. W7 has not
started.

**Preserved canonical name:** "W7 — RAG Evaluation and Output Quality" (`docs/ROADMAP.md`).

---

## 15. Dependencies and risk register

| Risk | Impact | Mitigation | Phase |
|------|--------|------------|-------|
| Batch 3 metadata reconciliation exposes destructive DDL | Data-integrity risk | Mandatory safety stop and senior review | Batch 3 |
| Alembic drift remediation breaks autogenerate | Migration accidents | Batch 3 safety stop; upgrade/downgrade only if a migration is required | Batch 3 |
| Step-progression rename breaks imports | Test/route regression | Grep all call sites; keep stateless behavior stable | Batch 3 |
| M10 scope creep into auth/admin | Roadmap violation | M9 report exclusion list | Batch 4/M10 |
| W7 starts before W6 complete | Unrealistic benchmark scenarios | Gate on W6 exit | W7 |
| TurboVec promoted without citation parity | Steward trust loss | Shadow + shared benchmark; no promotion without metrics | W7 Track B |
| ANN index tuned on dev-scale data | Wrong production params | Corpus-size-aware tuning in W7.1 | W7 Track B |
| Guardrail infinite retry loops | Cost/latency runaway | Hard retry caps | W7 Track A |
| No CI | Regressions undetected until manual run | Document; defer enforcement to W11 | OPS-1 |
| Realistic PDF not in live suite | False confidence in print path | Required Batch 4/M10 validation | §9.D |

---

## 16. Recommended model for each remaining batch

Policy: prefer capable lower-cost model for complete batches; one agent per
batch through tests, report, and commit; Sonnet 5 only for exceptional risk.

| Work unit | Default model | Reason | Technical risk | Sonnet 5? |
|-----------|---------------|--------|----------------|-----------|
| **Batch 3** (ARCH-2/MAINT-1 + Alembic drift) | **Composer 2.5 Fast** (or equivalent capable agent) | Focused refactor + metadata reconciliation; patterns exist in Batch 2 | Medium — migration metadata, import renames | **No**, unless `alembic check` remediation requires destructive DDL or first attempt fails on drift |
| **Batch 4 / W6 M10** | **Composer 2.5 Fast** | UI/accessibility/print polish and regression validation; no concurrency/DDL | Low–Medium | **No**, unless a specific implementation failure requires escalation |
| **W7 Track A** (evaluation + guardrails) | **Composer 2.5 Fast** for implementation iterations; user may prefer stronger model for rubric design | Large but mostly new modules + tests; benchmark design is iterative | Medium | **Only** if guardrail pipeline requires novel concurrent runtime architecture after a failed attempt |
| **W7 Track B** (vector abstraction + shadow) | **Composer 2.5 Fast** for abstraction; consider escalation for sync/outbox | Sync correctness and auth isolation are subtle | Medium–High | **Yes** if shadow eval shows auth leakage or sync race that lower-cost agent cannot resolve in one pass |
| **W7 full milestone** | Single agent per **sub-milestone** (W7.0–W7.8), not per file | Keeps commits reviewable | — | Escalate per sub-milestone criteria above |

### Sonnet 5 escalation conditions (exact)

Escalate to **Claude Sonnet 5** only when:

1. Recovered scope includes **destructive migration risk** (Alembic drift correction
   affecting live UUID columns or `case_memories`) and the default agent has not
   produced a safe upgrade/downgrade proof.
2. **Security-critical architecture** — retrieval backend authorization bypass,
   case isolation failure, or idempotency regression reappears under concurrency.
3. **Unusually difficult concurrency** — new race not covered by Batch 2 patterns.
4. The **lower-cost agent failed** for a specific, documented technical reason on
   the same batch (not merely because the batch is large).

Do **not** escalate solely for batch size or file count.

---

## 17. Sonnet 5 escalation criteria

(See §16 table.) Sonnet 5 is an exception, not the default. Do not split a
defined remediation batch across models.

---

## 18. Source traceability

| Claim | Primary source |
|-------|----------------|
| Audit findings IDs and priority | `docs/temp/W6_COMPREHENSIVE_PRODUCTION_READINESS_AUDIT.md` |
| Batch 1 scope and verdict | Batch 1 prompt (transcript `90626d01`), report, `4ab328d` |
| Batch 2 scope and verdict | Batch 2 prompt (transcript `8b06d77b`, `0b0801c9`), report, `1111b4e` |
| W6 M0–M10 complete | `PROJECT_STATE.md`, `docs/W6_UI_ARCHITECTURE.md`, Batch 4 report |
| W7 canonical scope | `docs/ROADMAP.md` |
| W7 begins after W6; Track A/B expansion | User handoff directive 2026-07-26 |
| Idempotency/index implementation detail | `docs/ARCHITECTURE.md` §7.1, Batch 2 report |
| M10 handoff items | `docs/temp/W6_M9_SOURCES_RESEARCH_REPORT.md` §87 |
| Batch 3 and Batch 4 completed scopes | Batch 3 commit/report; Batch 4 report |
| TurboVec conditional / PG system of record | User handoff directive 2026-07-26 |
| OPS-1 no CI | Audit OPS-1; `.github/workflows` absent |

---

## 19. Reconstruction confidence

| Area | Confidence | Notes |
|------|------------|-------|
| Batch 2 committed and verified | **HIGH** | Git + report cross-check |
| Batch 1 committed and verified | **HIGH** | Git + report |
| Audit disposition matrix | **HIGH** | Direct mapping to audit IDs |
| W7 expanded tracks (user decision) | **HIGH** | Explicit in handoff task |
| W7 sub-milestone numbering W7.0–W7.8 | **HIGH** | Approved current planning structure; refinable during W7 |
| Batch 3 exact scope | **HIGH** | Approved project-owner decision, §7 |
| Batch 4 exact scope | **HIGH** | Approved project-owner decision, §8 |
| M10 vs Batch 4 relationship | **HIGH** | Batch 4 is W6 M10 |
| Realistic PDF live validation plan | **HIGH** | Required in Batch 4/M10 |
| datetime.utcnow cleanup assignment | **HIGH** | Explicitly deferred |

---

## 20. Approved decisions and remaining implementation decisions

Approved:

1. Batch 3 completed ARCH-2/MAINT-1 plus scoped Alembic metadata reconciliation.
2. Batch 4 completed W6 M10 with realistic PDF live validation and final exit review.
3. FE-2 global TypeScript strict mode, `datetime.utcnow()` cleanup, React
   Router remediation, and `case_service.py` splitting are deferred.
4. CI/CORS remain W11; identity/authorization remain W9.
5. W7.0–W7.8 is approved as the current planning structure. W7 has not started.

Implementation-time decisions remain bounded to selecting the smallest safe
Batch 3 cleanup and determining whether metadata-only reconciliation requires
no migration. Any destructive-DDL condition triggers the mandatory safety stop.

---

## Appendix A — Approved remaining W6 sequence

```text
Batch 3 → complete (`35d5945`)
Batch 4 / W6 M10 → complete
W6 exit criteria review → PASS WITH NON-BLOCKING FINDINGS
W7 next → Track A + Track B integrated, planned and not started (§14)
```

W6 is complete. W7 remains planned, gated, and not started; it requires its own
implementation authorization.

---

*End of handoff document.*
