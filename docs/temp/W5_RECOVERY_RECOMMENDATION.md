# W5 Recovery Recommendation

**Status:** Recommendation only — nothing restored, no application code modified  
**Basis:** `docs/temp/W5_CHANGE_RECOVERY_AUDIT.md`  
**Active branch:** `main`  
**Date:** 2026-07-23  
**Principle:** Preserve existing W5 lifecycle work; reconstruct only what is truly missing.

---

## Verdict (short)

| Question | Answer |
|----------|--------|
| Does the missing W5 lifecycle work exist? | **Yes** — local `reconcile-main` @ `305ec58` |
| Is it complete? | **Almost** — services + ORM are complete and consistent; **migration is missing** (empty file) |
| Is recovery possible? | **Yes** — selective file recovery from `305ec58` |
| Is reconstruction required? | **Partially** — author a real Alembic migration; do not rewrite the services |
| Complete lifecycle before retrieval-agent refactor? | **Yes** |

---

## 1. Summary of recovered W5 work

The first W5 phase was a **source lifecycle** so retrieval can trust indexed knowledge:

```text
Official Source
        ↓
Download / Update          (SourceManager)
        ↓
Synchronize SourceDocument (SourceSyncService)
        ↓
Detect file changes / mark needing processing
        ↓
Chunk PDF → embeddings → SourceChunk
        ↓
Store processing metadata  (SourceProcessingService + SourceDocument fields)
        ↓
Safe retrieval
```

That work was checkpointed on local branch **`reconcile-main`** in a single commit:

| Field | Value |
|-------|--------|
| Commit | `305ec5871133817102f798586e0348bde6e959b0` (`305ec58`) |
| Message | `checkpoint before checking out main` |
| Relation to main | Exactly **one commit ahead** of `main` / `origin/main` (`58b2efbe…`) |
| On remotes? | **No** — `origin` has no `reconcile-main`; local-only recovery path |
| Stash / other branches / backup copies? | **No** |

**Files in that commit that matter:**

| Path | Role |
|------|------|
| `app/services/source_manager.py` | Manifest `"id"` + optional `"version"` |
| `app/services/source_sync_service.py` | `SUPERVISOR_MANUAL` folder + `processing_status = "pending"` on sync |
| `app/services/source_processing_service.py` | Lifecycle status, rollback, timestamps, SHA, strategy, chunk_metadata |
| `app/database/models.py` | SourceDocument processing fields + SourceChunk.chunk_metadata |
| `alembic/versions/h9c0d1e2f3a4_add_source_processing_metadata.py` | **Empty (0 bytes) — not usable** |
| `tree.txt` | Unrelated large binary — **do not recover** |

**Internal consistency of recovered service + model code:** High. The three services and the ORM fields on `305ec58` were written to work together (same status strings, same strategy label `generic_pdf_v1`, same `chunk_metadata` shape). They are **not** consistent with current `main` models until those fields (and a real migration) land on `main`.

---

## 2. Which portions are complete

### 2.1 Source Management (`source_manager.py`) — COMPLETE

On `305ec58`:

- Canonical source identity preserved inside manifest values as `"id": source["id"]` (in addition to dict key)
- Optional `"version": source.get("version")`
- Existing deterministic download/update/hash/local_path flow preserved

No DB dependency. Can be recovered independently with negligible risk.

### 2.2 Source Synchronization (`source_sync_service.py`) — COMPLETE (given models)

On `305ec58`:

- Local path + SHA synchronization preserved
- `SUPERVISOR_MANUAL` → `uploads/supervisor_manual`
- Sets `processing_status = "pending"` when path/SHA updated (local PDF path and download path)

Complete relative to the intended sync design **assuming** `SourceDocument.processing_status` exists.

### 2.3 Source Processing (`source_processing_service.py`) — COMPLETE (given models)

On `305ec58`:

- Processing lifecycle: `processing` → `completed` / `failed`
- Explicit `db.rollback()` on failure, then re-query and persist fail status + `processing_error`
- `processed_at`, `processed_sha256`, `processing_strategy = "generic_pdf_v1"`
- Richer `chunk_metadata` on each chunk
- Deterministic PDF → paragraph/`split_text` → `text-embedding-3-small` → `SourceChunk` pipeline preserved

### 2.4 ORM models (`SourceDocument` / `SourceChunk`) — COMPLETE on `305ec58`

Adds on `SourceDocument`:

- `version`
- `document_metadata`
- `processing_strategy`
- `processing_status` (default `"pending"`, indexed)
- `processed_sha256`
- `processed_at`
- `processing_error`

Adds on `SourceChunk`:

- `chunk_metadata`

These are the supporting fields the services expect. **Do not confuse** with existing `CaseDomainEvent.processing_status` / `processed_at` already on `main`.

### 2.5 Lifecycle intent — COMPLETE as a design unit on that commit

Together, manager + sync + processing + models implement provenance and “mark dirty → reprocess → audit completion” so retrieval need not trust stale/partial indexes **once the DB schema matches**.

---

## 3. Which portions are missing

| Gap | Severity | Notes |
|-----|----------|--------|
| **Real Alembic migration body** | **Blocking** | File `h9c0d1e2f3a4_add_source_processing_metadata.py` is **0 bytes**. No `upgrade()`/`downgrade()`. Columns will not be created. |
| Code on `main` | Blocking for use | All of the above lives only on `reconcile-main`; current workspace `main` lacks it |
| Remote backup of `reconcile-main` | Operational risk | Not on `origin` — local branch loss would lose the only copy |
| Alternate workspace/backup Python copies | N/A | Audit found none |
| Optional follow-ons not in `305ec58` | Non-blocking for recovery | e.g. API surfaces exposing processing status, tests for lifecycle, seed/docs for Supervisor Manual PDFs, stricter “detect change vs prior SHA” beyond setting pending on every successful sync write |

**Nothing requires rewriting the three services from scratch.** The only mandatory reconstruction is the **migration** (and applying the recovered files onto `main` when instructed).

---

## 4. Required database support

For the recovered services to run safely, `SourceDocument` must have at least:

| Field | Used by |
|-------|---------|
| `processing_status` | Sync (set `pending`); Processing (`processing` / `completed` / `failed`) |
| `processed_at` | Processing on success |
| `processed_sha256` | Processing on success (copied from `source.sha256`) |
| `processing_strategy` | Processing on success (`generic_pdf_v1`) |
| `processing_error` | Processing on failure |

Also present on `305ec58` and used/ready:

| Field | Used by |
|-------|---------|
| `version` | Model support for corpus versioning (manager writes version to **manifest**, not necessarily this column yet) |
| `document_metadata` | Model readiness for corpus-aware metadata |
| `SourceChunk.chunk_metadata` | Processing writes page / strategy / source_type |

**Recommendation:** Recover the full ORM hunk from `305ec58` (all listed fields), not a subset, so services and models stay consistent.

---

## 5. Required migrations

| Item | Status | Action |
|------|--------|--------|
| Empty `h9c0d1e2f3a4_add_source_processing_metadata.py` on `305ec58` | Unusable | Do **not** apply as-is; do not trust it |
| New real Alembic revision on `main` | **Must be authored** | Add nullable/defaulted columns matching the recovered models; include `source_chunks.chunk_metadata` |
| Existing `g8b9c0d1e2f3_…` CaseDomainEvent migration | Unrelated | Leave alone; different table |

**Suggested migration scope (reconstruction):**

- Table `source_documents`: add `version`, `document_metadata`, `processing_strategy`, `processing_status` (server default `'pending'`), `processed_sha256`, `processed_at`, `processing_error`; index on `processing_status` if matching the model
- Table `source_chunks`: add `chunk_metadata` (JSON, nullable)
- Provide a working `downgrade()` that drops those columns

Backfill: existing rows should get `processing_status='pending'` via default; `processed_*` remain null until reprocessed.

---

## 6. Recommended recovery order

**Optimize for preserving `305ec58` work. Do not rewrite services.**

### Order (when recovery is explicitly approved)

1. **Stay on `main`.** Prefer selective path restore from `305ec58`, not whole-commit merge/cherry-pick (avoids empty migration + `tree.txt`).
2. **Author and apply a real Alembic migration** for SourceDocument (+ SourceChunk.chunk_metadata) fields matching `305ec58` models.
3. **Restore `app/database/models.py` hunks** from `305ec58` (SourceDocument + SourceChunk only — review full file diff before applying).
4. **Restore `app/services/source_manager.py`** from `305ec58` (or apply the two-line manifest change).
5. **Restore `app/services/source_sync_service.py`** from `305ec58`.
6. **Restore `app/services/source_processing_service.py`** from `305ec58`.
7. **Smoke-verify lifecycle:** sync sets `pending` → process sets `processing`/`completed` + metadata → fail path rolls back and sets `failed`.
8. **Add focused tests** for processing status transitions, rollback, and sync pending reset (if not already present after restore).
9. **Optional hardening:** push or otherwise back up `reconcile-main` / ensure `305ec58` is not the only copy.
10. **Only then** resume the Retrieval Agent architecture plan (`docs/temp/RETRIEVAL_ARCHITECTURE_PLAN.md`).

### Explicitly do not

- Blind `git merge reconcile-main` or cherry-pick `305ec58` without filtering empty migration / `tree.txt`
- Restore processing/sync onto `main` **before** migration + models
- Reconstruct the three services from scratch while `305ec58` still exists locally
- Start RetrievalOrchestrator / ContractAgent extraction relying on “trusted index” assumptions until lifecycle metadata is live

---

## 7. Risks

| Risk | Level | Mitigation |
|------|-------|------------|
| Loss of local-only `reconcile-main` | High operational | Preserve commit; avoid deleting branch; consider remote backup when allowed |
| Applying empty Alembic file | High | Author new revision; never use 0-byte file |
| Restoring services without columns | High | Migration + models first |
| Confusing CaseDomainEvent fields with SourceDocument | Medium | Keep tables distinct in migration/review |
| Whole-commit brings `tree.txt` | Medium | Selective file restore only |
| Stale embeddings after sync without reprocess | Medium (product) | Sync already marks `pending`; ops/UI must still run process |
| Drift if services rewritten instead of recovered | Medium | Prefer `git show 305ec58:<path>` copy |
| Retrieval-agent work on incomplete lifecycle | Medium | Sequence: lifecycle first, agents second |

---

## 8. Whether recovery should occur before continuing the Retrieval Agent refactor

**Yes. Complete the W5 source lifecycle on `main` before continuing the retrieval-agent architecture.**

Reasons:

1. **Intended W5 sequence:** management → sync → processing → then retrieval agents. Agents assume a trustworthy indexed corpus.
2. **SupervisorManualAgent / ArbitrationAgent** depend on sync folders (`SUPERVISOR_MANUAL`, `ARBITRATION`) and processable documents with status/hash tracking so “indexed vs pending vs failed” is observable.
3. **ContractAgent extraction** can proceed on current embeddings technically, but doing so before lifecycle recovery risks building orchestration on the incomplete foundation and re-touching the same services later.
4. Recoverable work already exists; delaying recovery increases chance of losing the only local copy.

**Exception (narrow):** Pure Stage 1 docs/models under `app/services/retrieval/` with **zero** behavior change could theoretically proceed in parallel, but is not recommended until lifecycle recovery is finished — focus and risk control favor lifecycle first.

---

## 9. Step-by-step plan if reconstruction is required instead of recovery

**Primary path is recovery, not reconstruction.** Use this section only if `305ec58` / `reconcile-main` becomes unavailable.

### 9.A Prefer recovery (current state)

1. Confirm `git cat-file -t 305ec58` still resolves.
2. Follow §6 recovery order.
3. Reconstruct **only** the Alembic migration.

### 9.B If reconstruction becomes necessary (lost commit)

Rebuild to match the known `305ec58` design (from audit excerpts), in this order:

1. **Migration + models**  
   - Add SourceDocument fields listed in §4  
   - Add SourceChunk.chunk_metadata  
   - Apply migration  

2. **SourceManager**  
   - When writing manifest entries, include `"id"` and `"version": source.get("version")`  

3. **SourceSyncService**  
   - Add `"SUPERVISOR_MANUAL": Path("uploads/supervisor_manual")`  
   - After successful `local_path`/`sha256` update paths, set `processing_status = "pending"`  

4. **SourceProcessingService**  
   - Set status `processing` (clear error), commit  
   - Delete existing chunks; PDF → chunk → embed → SourceChunk with `chunk_metadata`  
   - On success: `completed`, `processed_at`, `processed_sha256 = sha256`, `processing_strategy = "generic_pdf_v1"`  
   - On failure: `rollback`, re-query, `failed` + `processing_error`, commit  

5. **Tests** for status transitions, rollback, sync pending, strategy/SHA fields  

6. **Then** resume retrieval-agent Stages 1–7 per `RETRIEVAL_ARCHITECTURE_PLAN.md`

Reconstruction cost is moderate but unnecessary while `305ec58` exists — **preserve and restore that work**.

---

## 10. Decision matrix

| Scenario | Action |
|----------|--------|
| `305ec58` available (current) | **Recover** services + models; **reconstruct** migration only |
| `305ec58` lost | Full reconstruction per §9.B |
| Want retrieval agents immediately | **Defer agents**; finish lifecycle first |
| Tempted to merge whole `reconcile-main` | **Decline**; selective restore only |

---

## 11. Relationship to retrieval architecture docs

| Document | Role after this recommendation |
|----------|--------------------------------|
| `PROJECT_INSPECTION_W5.md` | Accurate for **current main** (lifecycle absent) |
| `RETRIEVAL_ARCHITECTURE_PLAN.md` | Remains valid; **pause implementation** until lifecycle recovered |
| `W5_CHANGE_RECOVERY_AUDIT.md` | Locates the code |
| **This file** | How to bring lifecycle onto `main` safely before agents |

---

## End of recommendation

No files were restored. No application code was modified.  
Next action (when explicitly instructed): selective recovery from `305ec58` + author real Alembic migration on `main`, then resume retrieval-agent work.
