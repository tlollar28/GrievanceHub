# W5 Change Recovery Audit (Read-Only)

**Status:** Read-only recovery audit — no application code changed; nothing recovered or applied  
**Workspace:** `C:\Users\tloll\Documents\GrievanceHub`  
**Active branch during audit:** `main`  
**Audit date:** 2026-07-23  
**Rules followed:** No checkout/switch/merge/delete of branches; no worktree; no commit/cherry-pick/reset/stash/push

---

## Executive summary

The missing W5 source-processing / sync / model changes **were found**.

They exist in **exactly one place**:

| Item | Value |
|------|--------|
| Local branch | `reconcile-main` |
| Commit | `305ec5871133817102f798586e0348bde6e959b0` (short: `305ec58`) |
| Commit message | `checkpoint before checking out main` |
| Author / date | Tristan Lollar — Thu Jul 23 16:17:29 2026 -0400 |

They are **not** on `main` / `origin/main` (`58b2efbe02fd002b3053d6aacc8577d7bca99370`), not in stash, not on other local branch tips, and **not** pushed to `origin` (no remote `reconcile-main`).

**Critical caveat:** The companion Alembic file on that commit,

`alembic/versions/h9c0d1e2f3a4_add_source_processing_metadata.py`,

is a **0-byte empty blob** (`e69de29…`). ORM fields exist in `models.py`, but **no real migration body** exists. Recovering services + models without authoring a real migration would leave the DB incompatible.

Also present in the same commit: a large binary `tree.txt` (≈1.3 MB). Prefer **selective file restore** over blind merge/cherry-pick of the whole commit.

---

## Audit method (read-only)

Inspected without checking out other branches:

- `git status`, `git branch -a`, `git stash list`, `git reflog`
- `git log --all`, `git log main..reconcile-main`
- `git rev-parse main reconcile-main origin/main`
- `git show 305ec58` / `git show 305ec58:<path>`
- `git diff main..305ec58 -- <paths>`
- `git grep` on `main`, `305ec58`, and every local branch tip for `processed_sha256`, `processing_strategy`, `SUPERVISOR_MANUAL`, etc.
- Workspace file search for alternate copies of `source_processing*`, `source_sync*`, `source_manager*`
- Distinction from `CaseDomainEvent.processing_status` / `processed_at` on main

### Refs inspected

| Kind | Refs |
|------|------|
| Current | `main` @ `58b2efbe…` (= `origin/main`) |
| Target | `reconcile-main` @ `305ec58…` (1 commit ahead of main) |
| Other local | `backup-old-main`, `master`, `phase-W1…` through `phase-W3…`, `phase0-1…`, `phase1-*`, `phase3-html-pdf-export`, `report-cleanup` |
| Remote | `origin/main`, `origin/backup-old-main`, `origin/phase-W3…`, dependabot tips |
| Stash | empty |
| Workspace backups | No alternate `source_processing_service.py` / sync / manager copies outside `app/services/` |

`main..reconcile-main` = exactly one commit. `reconcile-main..main` empty (would be a clean fast-forward if applied later — **not recommended blindly** because of empty migration + `tree.txt`).

---

## Area 1 — `app/services/source_processing_service.py`

### 1. Desired implementation exists?

**Yes** — only on `reconcile-main` @ `305ec58`.

### 2. Exact location

- Branch: `reconcile-main`
- Path: `app/services/source_processing_service.py`
- Not in working tree on main; no backup/temp copies found

### 3. Commit hash / reference

`305ec5871133817102f798586e0348bde6e959b0`

### 4. Differences from current main

Main: simpler PDF → chunk → embed → insert; no status tracking; exception returns `{error}` without `db.rollback()`.

`305ec58` adds:

- Docstring describing W5 Knowledge Foundation processor
- Sets `processing_status = "processing"` and clears `processing_error` before work; `db.commit()`
- On success: `processing_status = "completed"`, `processed_at = datetime.utcnow()`, `processed_sha256 = source.sha256`, `processing_strategy = "generic_pdf_v1"`
- Stores `chunk_metadata` JSON on each `SourceChunk` (`page`, `chunking_strategy`, `source_type`)
- On failure: `db.rollback()`, re-query source, set `processing_status = "failed"`, `processing_error = str(e)`, commit
- Preserves PDF → paragraph/`split_text` → `text-embedding-3-small` → `SourceChunk` pipeline

Stat vs main: **+82 / −22** lines in this file (part of commit’s 96 insertions / 22 deletions overall for code files).

### 5. Complete and compatible with current main DB models?

**Incomplete relative to main models.** Requires `SourceDocument` fields and `SourceChunk.chunk_metadata` from the same commit. **Not compatible** with current main `SourceDocument` / `SourceChunk` as-is (runtime AttributeError / SQL errors).

### 6. Migration present?

Depends on Area 4. Migration **file exists but is empty** — not usable.

### 7. Recovery method

- **Recommended:** selective file copy from `git show 305ec58:app/services/source_processing_service.py` **after** models + a **real** Alembic revision
- Alternatively: checkout that path from `305ec58` onto main (when instructed) — still needs models/migration first
- Do **not** recover this file alone onto main

### 8. Conflicts with current main

Low textual conflict risk (main file is the pre-W5 baseline). **High runtime conflict** without schema support. Whole-commit apply also brings empty migration + `tree.txt`.

---

## Area 2 — `app/services/source_manager.py`

### 1. Desired implementation exists?

**Yes** (minimal two-line enhancement) on `reconcile-main` @ `305ec58`.

### 2. Exact location

- Branch: `reconcile-main`
- Path: `app/services/source_manager.py`

### 3. Commit hash / reference

`305ec5871133817102f798586e0348bde6e959b0`

### 4. Differences from current main

When writing `manifest["sources"][source["id"]]`, adds:

```python
"id": source["id"],
...
"version": source.get("version"),
```

Main already keys the dict by `source["id"]` but does not store `"id"` or `"version"` inside the value.  
Note: checked-in `app/sources/manifest.json` already has `version` fields for some sources; the **writer** on main does not emit them.

### 5. Complete and compatible with current DB models?

**Yes for DB** — manifest-only; no ORM dependency. Compatible with main models as a standalone change.

### 6. Migration present?

Not required.

### 7. Recovery method

- Copy the two-line manifest change / restore file from `305ec58`
- Lowest-risk independent recovery among the four areas

### 8. Conflicts with current main

Negligible. No overlap with CaseDomainEvent fields.

---

## Area 3 — `app/services/source_sync_service.py`

### 1. Desired implementation exists?

**Yes** on `reconcile-main` @ `305ec58`.

### 2. Exact location

- Branch: `reconcile-main`
- Path: `app/services/source_sync_service.py`

### 3. Commit hash / reference

`305ec5871133817102f798586e0348bde6e959b0`

### 4. Differences from current main

```diff
+ "SUPERVISOR_MANUAL": Path("uploads/supervisor_manual"),
```

And after setting `local_path` / `sha256` on **both** local-PDF and download/sync success paths:

```diff
+ source.processing_status = "pending"
```

Preserves existing local-path + SHA synchronization behavior.

### 5. Complete and compatible with current main DB models?

**Partially.** `SUPERVISOR_MANUAL` folder mapping alone is compatible with main models.  
Setting `processing_status = "pending"` **requires** `SourceDocument.processing_status` from Area 4 — **not** on main.

### 6. Migration present?

Required for the status-reset behavior (see Area 4). Empty migration on `305ec58` is insufficient.

### 7. Recovery method

- Restore file from `305ec58` together with models + real migration
- Or split: add folder map first; add status reset only after schema exists

### 8. Conflicts with current main

Low textual conflict. Runtime failure if status assignment applied without column.

**False positive on main:** `SUPERVISOR_MANUAL` appears in `tests/test_case_lifecycle_workspace_restoration.py` as a fixture `document_type` — **not** sync `folder_map` support.

---

## Area 4 — Database models and Alembic migrations (`SourceDocument`)

### 1. Desired implementation exists?

| Piece | Exists? |
|-------|---------|
| `SourceDocument` ORM fields | **Yes** on `305ec58` |
| `SourceChunk.chunk_metadata` | **Yes** on `305ec58` |
| Usable Alembic upgrade script | **No** — empty placeholder only |

### 2. Exact location

- Models: `reconcile-main` → `app/database/models.py`
- Migration path (empty): `alembic/versions/h9c0d1e2f3a4_add_source_processing_metadata.py`
- Blob: `e69de29bb2d1d6434b8b29ae775ad8c2e48c5391` size **0**

### 3. Commit hash / reference

`305ec5871133817102f798586e0348bde6e959b0`

### 4. Differences from current main (`SourceDocument`)

Adds:

- `version` (`String(80)`, nullable)
- `document_metadata` (`JSON`, nullable)
- `processing_strategy` (`String(80)`, nullable)
- `processing_status` (`String(40)`, not null, default `"pending"`, indexed)
- `processed_sha256` (`String(128)`, nullable)
- `processed_at` (`DateTime`, nullable)
- `processing_error` (`Text`, nullable)

Also adds on `SourceChunk`:

- `chunk_metadata` (`JSON`, nullable)

### 5. Complete and compatible with current main DB models?

ORM patch is coherent with the services on the same commit.  
**Not present on main.** Applying ORM without a real DB migration is **not** production-compatible.

### 6. Migration present?

**Placeholder only** — 0 bytes, 0 lines. Would not create columns. **Do not use as-is.**

### 7. Recovery method

1. Restore `models.py` fields from `305ec58` (selective hunks)
2. **Author a new real Alembic revision** adding the SourceDocument (+ optional `chunk_metadata`) columns
3. Discard or replace empty `h9c0d1e2f3a4_…` rather than trusting it
4. Then restore processing + sync services

### 8. Conflicts with current main

- ORM: additive; low merge conflict risk
- Naming collision risk with **`CaseDomainEvent.processing_status` / `processed_at`** (already on main) — different model/table; do not confuse
- Empty migration is a **landmine** if the whole commit is fast-forwarded/merged
- Same commit adds unrelated large `tree.txt`

### False positives (main)

| Location | Why not W5 SourceDocument |
|----------|---------------------------|
| `CaseDomainEvent.processing_status` / `processed_at` | Case domain-event processing, migration `g8b9c0d1e2f3_…` |
| `git grep processed_sha256 main -- app alembic` | **No matches** |

---

## Commit contents inventory (`305ec58`)

```
alembic/versions/h9c0d1e2f3a4_add_source_processing_metadata.py | 0 bytes (empty)
app/database/models.py                                         | +31
app/services/source_manager.py                                 | +2
app/services/source_processing_service.py                      | +82 / -22
app/services/source_sync_service.py                            | +3
tree.txt                                                       | Bin 0 → ~1.3 MB
```

---

## Final recovery table

| Area | Present on main | Found elsewhere | Reference/path | Model support present | Migration present | Recommended recovery method | Risk |
|------|-----------------|-----------------|----------------|----------------------|-------------------|----------------------------|------|
| 1. Source processing service | No | Yes | `reconcile-main` @ `305ec58` → `app/services/source_processing_service.py` | Only on that commit (not on main) | N/A for file; blocked by Area 4 | Selective copy/checkout of file **after** models + real migration | Medium–High if applied alone |
| 2. Source manager | No | Yes | `reconcile-main` @ `305ec58` → `app/services/source_manager.py` | N/A (manifest-only) | Not required | Copy two-line `"id"` + `"version"` manifest change | Low |
| 3. Source sync service | No | Yes | `reconcile-main` @ `305ec58` → `app/services/source_sync_service.py` | Needs Area 4 for status reset; folder map alone OK | Needs Area 4 for status | Selective copy with models+migration; or split folder map vs status | Medium |
| 4. SourceDocument models + migration | No | Partial | Models: `305ec58:app/database/models.py`; Migration: `h9c0d1e2f3a4_…` **empty** | Yes on `305ec58` | **Empty placeholder only** | Copy model fields; **write** real Alembic upgrade; do not use empty rev | **High** if empty migration applied / whole commit FF |

---

## Recommended recovery sequence (guidance only — not applied)

1. Stay on `main`.
2. Recover **only** from local `reconcile-main` / `305ec58` (not on origin).
3. Prefer **file-level restore** of:
   - `app/database/models.py` (SourceDocument + SourceChunk hunks)
   - `app/services/source_processing_service.py`
   - `app/services/source_sync_service.py`
   - `app/services/source_manager.py`
4. **Author a real Alembic migration** for the new columns; ignore/replace empty `h9c0d1e2f3a4_…`.
5. Avoid blind `merge` / `cherry-pick` of `305ec58` (empty migration + large `tree.txt`).
6. Do not confuse with `CaseDomainEvent` processing fields already on main.

---

## End of audit

No recovery was performed. No application code was modified. Only this report under `docs/temp/` was created.
