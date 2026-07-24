# W5 Source-Lifecycle Recovery — Independent Review

**Review date:** 2026-07-23  
**Active branch:** `main`  
**Current HEAD:** `58b2efbe02fd002b3053d6aacc8577d7bca99370`  
**Checkpoint inspected:** `305ec5871133817102f798586e0348bde6e959b0`  
**Verdict:** **D. INCONCLUSIVE**  
**Retrieval-agent work may begin:** **No**

## 1. Executive verdict

The working-tree recovery is tightly scoped and is internally coherent on static inspection. The recovered ORM and service behavior matches checkpoint `305ec58` except for two end-of-file whitespace differences. The new migration is a real 2,487-byte implementation, not the checkpoint's zero-byte blob. Its fields, types, existing-row default, index, downgrade, and revision graph are structurally correct.

No application-code blocker was found. The review nevertheless cannot issue PASS or PASS WITH NON-BLOCKING FINDINGS because the terminal execution subsystem stopped returning exit status or output, including for harmless probes. Consequently:

- no pytest result was independently obtained;
- offline upgrade/downgrade SQL generation was not independently completed;
- no disposable-database upgrade/downgrade was completed;
- the destructive chunk-replacement rollback was not exercised with a real transaction.

The implementation report's claimed `12 passed`, `2 passed / 34 deselected`, and `19 passed` results are therefore not adopted as independent evidence.

Finding counts:

- **BLOCKER:** 1 validation/environment blocker
- **HIGH:** 0
- **MEDIUM:** 3
- **LOW:** 3

The code appears likely usable, but the required execution evidence is missing. Retrieval-agent implementation must wait for the validation commands in section 12 to be rerun successfully.

## 2. Git/change-scope review

### Pre-review repository state

The branch and commit were verified directly:

```text
main
58b2efbe02fd002b3053d6aacc8577d7bca99370
```

The exact pre-review status was:

```text
 M app/database/models.py
 M app/services/source_manager.py
 M app/services/source_processing_service.py
 M app/services/source_sync_service.py
?? alembic/versions/h9c0d1e2f3a4_add_source_processing_metadata.py
?? docs/temp/PROJECT_INSPECTION_W5.md
?? docs/temp/RETRIEVAL_ARCHITECTURE_PLAN.md
?? docs/temp/W5_CHANGE_RECOVERY_AUDIT.md
?? docs/temp/W5_RECOVERY_IMPLEMENTATION_REPORT.md
?? docs/temp/W5_RECOVERY_RECOMMENDATION.md
?? docs/temp/_recovery_blobs/models_checkpoint.py
?? docs/temp/_recovery_blobs/source_manager.py
?? docs/temp/_recovery_blobs/source_processing_service.py
?? docs/temp/_recovery_blobs/source_sync_service.py
?? tests/test_w5_source_lifecycle.py
```

Relative to starting commit `58b2efbe02fd002b3053d6aacc8577d7bca99370`:

- Modified tracked files: the four `app/` files above.
- Added tracked files: none.
- Deleted tracked files: none.
- Renamed tracked files: none.
- Untracked files: the eleven files listed above.
- Tracked diff: 4 files, 96 insertions, 23 deletions.
- `git diff --check`: passed with no output.

Untracked files do not appear in ordinary `git diff`; the migration, focused test, and reports must therefore be reviewed and preserved separately.

### Scope boundaries

Direct path and diff checks confirmed:

- `tree.txt` was not restored.
- No unrelated checkpoint file was restored.
- `app/services/retrieval/` does not exist.
- `app/services/knowledge_retrieval_service.py` is unchanged.
- `app/services/relevance_utils.py` is unchanged.
- `app/retrieval_config.py` is unchanged.
- All `models.py` changes are confined to `SourceDocument` and `SourceChunk`.
- `alembic/versions/g8b9c0d1e2f3_add_case_domain_events_workflow.py` is unchanged.
- Retrieval remains read-only and no retrieval-agent architecture implementation has started.

### Recovery blobs

`docs/temp/_recovery_blobs/` contains:

- `models_checkpoint.py` — 25,626 bytes
- `source_manager.py` — 3,524 bytes
- `source_processing_service.py` — 4,260 bytes
- `source_sync_service.py` — 3,938 bytes

All four are untracked. They are not imported by the application and are not under an application package, so they are not application-executable in the normal runtime path. They are nevertheless valid Python source that could be manually imported or run. They duplicate production definitions, pollute searches, and can become stale or be committed accidentally. They should not remain after recovery verification, but they were not deleted during this review.

## 3. Model review

`SourceDocument` contains all required fields:

- `version`: `String(80)`, nullable, no explicit Python default, no server default, not indexed.
- `document_metadata`: `JSON`, nullable, no explicit Python or server default, not indexed.
- `processing_strategy`: `String(80)`, nullable, no explicit Python or server default, not indexed.
- `processing_status`: `String(40)`, non-null, Python default `"pending"`, indexed.
- `processed_sha256`: `String(128)`, nullable, no explicit Python or server default, not indexed.
- `processed_at`: project-conventional naive `DateTime`, nullable, no explicit Python or server default, not indexed.
- `processing_error`: `Text`, nullable, no explicit Python or server default, not indexed.

`SourceChunk` contains:

- `chunk_metadata`: `JSON`, nullable, no explicit Python or server default, not indexed.

All nullable columns are compatible with existing records. `processing_status` compatibility is supplied by the migration's server default, not by the ORM's Python default.

The status index generated by `index=True` agrees with migration index `ix_source_documents_processing_status`. No check constraint restricts status strings; consistency is by service convention.

The current `models.py` is byte-identical to checkpoint `305ec58`. No unrelated model definitions changed. `CaseDomainEvent.processing_status` and `CaseDomainEvent.processed_at` remain separate fields on `case_domain_events` and were not confused with the new source-document fields.

## 4. Migration review

### Revision graph

Direct Alembic execution established the linear graph:

```text
8c122243395f
  -> 2d6d4a6b4613
  -> a1b2c3d4e5f6
  -> b2c3d4e5f6a7
  -> c4d5e6f7a8b9
  -> d5e6f7a8b9c0
  -> e6f7a8b9c0d1
  -> f7a8b9c0d1e2
  -> g8b9c0d1e2f3
  -> h9c0d1e2f3a4
```

`alembic heads` returned:

```text
h9c0d1e2f3a4 (head)
```

There is one base, one head, no branch, no missing parent, and no cycle. `g8b9c0d1e2f3` is the correct parent.

### Checkpoint and ref inspection

The checkpoint's migration path is blob `e69de29bb2d1d6434b8b29ae775ad8c2e48c5391`, size zero. It declares no Alembic revision and contains no upgrade or downgrade.

The current working file is blob `d17c42ea5856ad2c58471dd557f66bece146ed44`, size 2,487 bytes. It declares:

```text
revision = h9c0d1e2f3a4
down_revision = g8b9c0d1e2f3
```

All 25 existing local and remote-tracking ref roots and all 47 commits reachable from them were searched without fetching. The filename occurs in reachable history only at checkpoint `305ec58`, where it is empty. No reachable commit contains a non-empty or conflicting `h9c0d1e2f3a4` revision.

Reusing the intended checkpoint filename and ID is **technically valid but operationally risky**, not incorrect:

- the empty checkpoint file could never have applied this DDL through Alembic because it declared no revision;
- there is no conflicting implementation in reachable history;
- the same path on `reconcile-main` can still cause an add/add conflict or human confusion if that branch is later merged;
- the current complete migration is untracked and must be preserved as the canonical implementation.

### Upgrade review

The upgrade correctly adds:

- `source_documents.version` — `String(80)`, nullable;
- `source_documents.document_metadata` — `JSON`, nullable;
- `source_documents.processing_strategy` — `String(80)`, nullable;
- `source_documents.processing_status` — `String(40)`, non-null, server default `"pending"`;
- `source_documents.processed_sha256` — `String(128)`, nullable;
- `source_documents.processed_at` — `DateTime`, nullable;
- `source_documents.processing_error` — `Text`, nullable;
- `source_chunks.chunk_metadata` — `JSON`, nullable.

It then creates non-unique index `ix_source_documents_processing_status`. The name is valid and no conflicting index exists in the migration history.

Adding the non-null status with `server_default="pending"` safely populates existing rows. Existing sources with older chunks intentionally become `pending` until reprocessed. The migration leaves the server default in place while the ORM also supplies a Python default. Their semantic result agrees; the mechanism differs for raw SQL versus ORM inserts.

Generic `JSON` and naive `DateTime` match existing project conventions.

### Downgrade review

The downgrade:

1. drops `source_chunks.chunk_metadata`;
2. drops the processing-status index before its column;
3. drops all seven added `source_documents` columns;
4. touches no unrelated table or schema object.

The dependency order is safe and symmetric.

### Runtime limitation

`alembic heads` and `alembic history` completed. Independent offline upgrade SQL, offline downgrade SQL, and a disposable PostgreSQL upgrade/downgrade did not complete because the terminal runner stopped returning command status. No configured or production database was touched. Migration runtime behavior therefore remains unverified.

## 5. SourceManager review

`app/services/source_manager.py:110-120` writes under canonical key `source["id"]` and includes:

```text
"id": source["id"]
"version": source.get("version")
```

Missing version is supported as `None`. Existing fields—name, type, URLs, path, SHA, and content type—remain. Link discovery, selection, download, hashing, unchanged-SHA detection, and file output are otherwise unchanged from the starting commit.

The file is byte-identical to checkpoint `305ec58`.

One inherited edge case remains: `update_source` returns immediately when the downloaded SHA is unchanged (`lines 99-102`). It therefore does not backfill a missing inline `id` or refresh registry metadata/version for an old manifest entry unless the bytes change.

The focused tests execute `update_source` with mocked network responses and inspect an in-memory dictionary plus the downloaded temporary file. They do not call `save_manifest`, reload JSON, or prove physical manifest persistence. They test behavior rather than source text, but not persisted output.

The manager's optional manifest version support does **not** automatically populate `SourceDocument.version`. No service currently claims or implements that propagation.

## 6. SourceSyncService review

Existing mappings remain unchanged and `SUPERVISOR_MANUAL` maps to `uploads/supervisor_manual`.

The control flow remains:

1. query the source;
2. prefer a local PDF from the mapped folder;
3. otherwise use `download_url`;
4. extract the first PDF if the download is a ZIP;
5. calculate SHA256;
6. set `local_path`, `sha256`, and `processing_status="pending"`;
7. commit and refresh.

Both successful local and download paths set pending. Missing source, missing local PDF plus missing URL, download failure, hash failure, and a ZIP with no PDF do not reach the assignments or commit, so they do not falsely persist a synchronized/pending source. Commit failures are not caught locally, but do not represent a successful synchronization.

No retrieval behavior was introduced.

### Pending semantics

Actual behavior: every successful sync sets pending, even when the selected path and SHA are identical to the stored values.

- This exactly matches checkpoint `305ec58`.
- It satisfies the broad lifecycle statement that a synchronized source becomes pending.
- It does not implement the narrower documented idea of marking pending only when path or content changes.
- It can trigger unnecessary reprocessing and embedding cost and can move an already current source from `completed` back to `pending`.
- Classification: **non-blocking defect**, not a blocker.

The focused tests cover the two success paths and mapping, but not unchanged content, missing-source/no-URL/ZIP/download/commit failures, or persisted database state.

## 7. SourceProcessingService review

### Lifecycle

Before processing:

- the source is queried and preconditions are checked;
- status becomes `processing`;
- prior `processing_error` is cleared;
- that transition is intentionally committed before PDF work.

Processing:

- the existing PDF extraction and paragraph/`MAX_CHARS=6000` chunking remain;
- prior chunks are deleted;
- embeddings still use `text-embedding-3-small`;
- each new `SourceChunk` receives document ID, zero-based chunk index, page number, text, embedding, and:
  - `page`;
  - `chunking_strategy="generic_pdf_v1"`;
  - `source_type`.

Success:

- status becomes `completed`;
- `processed_at` is populated;
- `processed_sha256` is copied from `source.sha256`;
- strategy becomes `generic_pdf_v1`;
- the previously cleared error remains clear;
- replacement chunks and success metadata are committed together.

Failure:

- the replacement transaction is rolled back;
- `SourceDocument` is re-queried;
- status becomes `failed`;
- the exception text is persisted;
- the failure state is committed;
- the public `{error, type}` response shape is preserved.

The current implementation matches checkpoint `305ec58` semantically. The only difference is one trailing blank line.

### Transaction assessment

- Committing `processing` before deletion makes the attempt observable. It also means a hard process crash can leave status stuck at `processing`; old chunks remain because replacement work has not committed.
- Delete and rebuild share one transaction. Under normal SQLAlchemy/database semantics, a rollback after a partial replacement restores the previous usable chunks and removes partial inserts.
- The focused failure test raises while constructing `PdfReader`, before deletion or any insert. It therefore does not prove atomic delete-and-rebuild or absence of partial chunks.
- The rollback/re-query pattern is sound: rollback expires failed transaction state, and the query obtains safe ORM state for the failure update.
- A failure while committing the failed status is not caught; in that exceptional case failed status and the compatible error response are not guaranteed.
- There is no per-source lock or SHA fence. A concurrent sync can change path/SHA while processing uses the earlier `pdf_path`; the final `processed_sha256` can then describe a different source state. Concurrent processors can also race on delete/rebuild. This is inherited checkpoint behavior.

The crash, failed-status-commit, and concurrency cases are future hardening concerns. They are not recovery drift, but the SHA/concurrency gap is material to provenance and is recorded as MEDIUM.

## 8. Cross-file consistency

The following agree across ORM, migration, services, and tests:

- statuses: `pending`, `processing`, `completed`, `failed`;
- fields: `version`, `document_metadata`, `processing_strategy`, `processing_status`, `processed_sha256`, `processed_at`, `processing_error`, `chunk_metadata`;
- strategy: `generic_pdf_v1`.

Every service-referenced field exists in the ORM. Every added ORM field exists in the migration. Types and lengths agree. Tests use the same spellings.

No stale alternate schema exists under `app/`; the only duplicate definitions are the untracked recovery blobs under `docs/temp`.

Manifest version support is correctly limited to manifest output. It is not DB version synchronization.

## 9. Test-quality review

`tests/test_w5_source_lifecycle.py` contains 12 tests and makes no live OpenAI call.

Meaningful coverage:

- required ORM field presence;
- status nullability, Python default, and index;
- chunk metadata presence/nullability;
- Alembic head and parent;
- non-empty migration guard;
- manager canonical ID/version and missing version;
- Supervisor Manual mapping;
- local/download sync success assignments;
- processing success fields and chunk metadata;
- explicit rollback call, re-query target, and failed/error assignment;
- `split_text` smoke behavior.

Important gaps:

- most ORM types, lengths, defaults, and nullability are not asserted;
- migration tests inspect graph and source text but never execute DDL;
- existing-row backfill is inferred from a source substring;
- downgrade is checked by string position only;
- manager tests do not persist and reload the manifest;
- sync uses `MagicMock`, does not prove DB persistence, and has no failure tests;
- processing uses `MagicMock`;
- the failure is before destructive replacement;
- no assertion proves old chunks survive or partial chunks are absent;
- `db.commit.call_count >= 2` is permissive and does not establish ordering;
- the split assertion only proves non-empty concatenated output;
- no real transaction, vector dimension, or PostgreSQL behavior is exercised.

The tests are useful behavioral smoke tests but are not, by themselves, adequate evidence for migration safety or destructive-rebuild transaction safety.

The tests use `tmp_path` and mocks and appear order-independent. Migration path checks assume execution from the repository root. No live API call is intended.

## 10. Test execution

### Commands that completed

```text
venv\Scripts\python.exe -m alembic heads
venv\Scripts\python.exe -m alembic history
```

Results:

- one Alembic head: `h9c0d1e2f3a4`;
- complete ten-revision linear history;
- no warning captured.

### Pytest commands requested/attempted

```text
venv\Scripts\python.exe -m pytest tests/test_w5_source_lifecycle.py -v --tb=short
venv\Scripts\python.exe -m pytest tests/test_case_lifecycle_workspace_restoration.py -k "SUPERVISOR or supervisor or ARBITRATION or source" -v
venv\Scripts\python.exe -m pytest tests/test_w5_source_lifecycle.py tests/test_relevance_utils.py tests/test_knowledge_retrieval_scoring.py -q
venv\Scripts\python.exe -m pytest tests/test_app_surface_and_source_paths.py tests/test_phase1_1_source_coverage.py tests/test_chat_source_retrieval.py tests/test_relevance_phase0.py tests/test_phase1_1_retrieval_stability.py tests/test_retrieval_gaps.py -q
venv\Scripts\python.exe -m pytest tests/ -q
```

The runner returned no exit status/output before pytest could be verified. Therefore:

- passed: not available;
- failed: not available;
- skipped: not available;
- deselected: not available;
- warnings: not available;
- recovery-caused failures: cannot be determined;
- full suite: not executed/verified.

The same runner failure prevented:

```text
alembic upgrade g8b9c0d1e2f3:h9c0d1e2f3a4 --sql
alembic downgrade h9c0d1e2f3a4:g8b9c0d1e2f3 --sql
```

No configured database, production data, or persistent local application data was intentionally touched. Temporary probe locations were outside the repository and cleaned. Later Git status checks showed the original recovery state plus only this authorized review file.

## 11. Findings by severity

### BLOCKER-1 — Independent execution validation unavailable

- File/symbol: N/A — terminal execution subsystem.
- Observed: harmless commands repeatedly returned no exit status/output; pytest, offline SQL, real migration, and transaction probes could not be verified.
- Expected: independently reproducible test counts and a disposable migration/transaction result.
- Risk: the review cannot establish actual test success, PostgreSQL DDL behavior, or partial-chunk rollback.
- Recommended correction: restart/repair terminal execution and run section 12 exactly.
- Origin: environment; neither inherited from `305ec58` nor introduced by recovery.

### MEDIUM-1 — Sync always marks pending

- File/symbol: `app/services/source_sync_service.py:65-67,115-117`, `sync_source`.
- Observed: every successful sync sets pending.
- Expected: the change-detection interpretation would set pending only when path or SHA changes.
- Risk: unnecessary re-embedding cost and false pending state for an unchanged corpus.
- Recommended correction: compare stored and computed path/SHA before resetting status.
- Origin: inherited from `305ec58`.

### MEDIUM-2 — Focused tests do not validate persisted transaction/migration behavior

- File/symbol: `tests/test_w5_source_lifecycle.py:30-95,103-183,201-288,326-399`.
- Observed: migration source inspection, in-memory manifest assertions, and `MagicMock` sessions; failure occurs before chunk deletion.
- Expected: persisted manifest reload, disposable DB DDL, real-session sync, and failure after a partial replacement has been staged.
- Risk: regressions in backfill, downgrade, commit ordering, rollback, and partial-chunk removal can pass.
- Recommended correction: add disposable DB and real-session tests, including second-embedding failure.
- Origin: tests were introduced during recovery; service transaction design is inherited.

### MEDIUM-3 — No concurrency/SHA fence during processing

- File/symbol: `app/services/source_processing_service.py:68-75,82-128`, `process_source`.
- Observed: processing records `source.sha256` at completion without locking or verifying the processed file/source snapshot.
- Expected: final provenance should be tied to the exact bytes processed, with one processor per source.
- Risk: concurrent sync/process or two processors can produce misleading `processed_sha256` or racing chunk replacement.
- Recommended correction: capture and verify path/SHA, hash the processed bytes, and add per-source locking or optimistic concurrency.
- Origin: inherited from `305ec58`.

### LOW-1 — Unchanged SHA skips manifest metadata refresh

- File/symbol: `app/services/source_manager.py:99-102`, `update_source`.
- Observed: early return leaves an old entry without inline ID or refreshed version when bytes are unchanged.
- Expected: identity/version metadata can be refreshed independently of file content.
- Risk: stale manifest provenance.
- Recommended correction: merge metadata before returning on unchanged SHA.
- Origin: inherited control flow; exposed by the new metadata.

### LOW-2 — Crash/failure-state hardening

- File/symbol: `app/services/source_processing_service.py:73-75,137-149`.
- Observed: a hard crash after the first commit can leave `processing`; failure-status commit errors escape the response handler.
- Expected: stale-attempt recovery and guarded failure persistence.
- Risk: stuck status or missing failed-state record.
- Recommended correction: stale-processing recovery and nested handling around failed-state commit.
- Origin: inherited from `305ec58`.

### LOW-3 — Recovery blobs duplicate production code

- File/symbol: `docs/temp/_recovery_blobs/*.py`.
- Observed: four untracked Python copies remain.
- Expected: temporary extraction artifacts removed after verification.
- Risk: stale code-search results, accidental imports, or accidental commit.
- Recommended correction: delete them in an authorized cleanup after the review.
- Origin: introduced during recovery.

### Informational

- Model and service recovery is checkpoint-faithful.
- Existing rows intentionally become pending.
- The retained server default and ORM Python default both produce pending.
- The migration ID is unique in all reachable refs.
- `document_metadata` and `SourceDocument.version` are schema-ready but not currently populated by sync/processing.
- `datetime.utcnow()` is inherited project behavior and a future deprecation cleanup, not a W5 blocker.
- Zero extracted chunks can currently result in `completed`; retrieval's indexed-source check still requires an embedding, but explicit empty-document handling would be clearer.

## 12. Required corrections

No application-code correction was proven mandatory by this review.

The following validation correction is mandatory before retrieval-agent work:

1. Restore a functioning terminal runner.
2. Run all five pytest commands from section 10 with bytecode/cache disabled.
3. Generate and inspect offline upgrade and downgrade SQL.
4. On a disposable PostgreSQL/pgvector database:
   - upgrade to `g8b9c0d1e2f3`;
   - insert an existing `source_documents` row;
   - upgrade to `h9c0d1e2f3a4`;
   - verify all columns, index, and pending backfill;
   - downgrade to `g8b9c0d1e2f3`;
   - verify only W5 objects are removed.
5. Exercise a real transaction where embedding fails after deletion and at least one new chunk is staged; verify old chunks remain and no partial chunk survives.

The repository should also add the persistent/transactional tests in MEDIUM-2, although that is a test-hardening correction rather than evidence of incorrect service code.

## 13. Optional hardening

- Mark pending only on actual path/SHA change.
- Add a source SHA/version fence and one-processor-per-source protection.
- Recover stale `processing` attempts.
- Guard failure-status persistence errors.
- Refresh manifest identity/version even when bytes are unchanged.
- Treat a zero-chunk PDF as failed or completed-with-warning.
- Remove recovery blobs after approval.

## 14. Final recommendation

**D. INCONCLUSIVE.**

Static evidence strongly supports that the recovery is scoped, checkpoint-faithful, internally consistent, and structurally migration-safe. It does not support a final PASS because the independent execution gate failed at the environment level. Do not use the implementation report's prior pass counts as a substitute.

After the required commands complete successfully, the likely result would be **PASS WITH NON-BLOCKING FINDINGS**, with the sync dirty-check and test hardening retained as follow-up work.

## 15. Whether retrieval-agent work may begin

**No.**

The retrieval architecture has not started and should remain paused until the independent pytest, offline SQL, disposable migration, and partial-rollback validations complete successfully. No application code, migration, or test was modified during this review; only this report was created.
