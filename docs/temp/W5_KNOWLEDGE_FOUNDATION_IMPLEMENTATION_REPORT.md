# W5 Knowledge Foundation Implementation Report

**Date:** 2026-07-23  
**Branch:** `main`  
**Status:** Complete  
**Retrieval-agent implementation:** Not started

## 1. Outcome

The remaining W5 Knowledge Foundation work is complete.

- Recovered W5 lifecycle code was runtime-validated.
- Source synchronization now uses a real path/SHA dirty check.
- Destructive chunk replacement was validated with real SQLAlchemy and PostgreSQL transactions.
- Temporary recovery blobs were removed.
- Official Step 1 and Step 2 AcroForm PDFs were integrated.
- All three Supervisor Manuals were registered, synchronized, processed, and embedded in the configured local PostgreSQL database.
- The final full test suite passed.

Recommendation: retrieval-agent implementation may begin after this report. No retrieval orchestrator or retrieval-agent class was implemented during W5.

## 2. Runtime validation

The terminal execution failure from the independent review was reproduced once in the parent runner. Validation was then completed through a working execution path with confirmed exit codes.

The five previously unverified baseline pytest commands completed:

- Recovered W5 lifecycle: 12 passed, 0 failed.
- Case lifecycle source filter: 2 passed, 0 failed, 34 deselected.
- W5/relevance/scoring subset: 19 passed, 0 failed.
- Retrieval regression subset: 65 passed, 0 failed.
- Pre-implementation full suite: 484 passed, 0 failed, 32 skipped.

Final post-implementation validation:

- W5 lifecycle: 18 passed, 0 failed, 0 skipped.
- Official grievance PDF export: 4 passed, 0 failed, 0 skipped.
- Grievance integration suites: 126 passed, 0 failed, 0 skipped.
- Retrieval regression subset: 65 passed, 0 failed, 0 skipped.
- Full suite: 525 passed, 0 failed, 0 errors, 1 skipped, 331 warnings.

The one intentional skip was:

- `tests/test_regression_harness.py::test_regression_live_pipeline_smoke`
- Reason: requires the opt-in environment variable `RUN_REGRESSION=1`.

Additional checks:

- Changed-module compilation: 15/15 passed.
- Changed-module imports: 13/13 passed.
- `git diff --check`: passed.

## 3. Migration validation

Alembic remains linear with one head:

- Current/head revision: `h9c0d1e2f3a4`
- W5 parent: `g8b9c0d1e2f3`

Validation completed:

- Alembic heads/history: passed.
- Offline W5 upgrade SQL generation: passed.
- Offline W5 downgrade SQL generation: passed.
- Disposable PostgreSQL/pgvector upgrade, backfill, downgrade, and re-upgrade: passed.
- Configured local development database upgrade to head: passed.

The disposable database proved:

- All seven W5 `source_documents` columns were created.
- `source_chunks.chunk_metadata` was created.
- `processing_status` was non-null with the `pending` server default.
- A pre-W5 row was backfilled to `pending`.
- `ix_source_documents_processing_status` was created.
- Downgrade removed only W5 objects and retained the preexisting row/core schema.
- Re-upgrade restored the W5 schema.

### pgvector fresh-install correction

A fresh database exposed an existing migration-chain defect: revision `2d6d4a6b4613` added `vector(1536)` before enabling the PostgreSQL `vector` extension.

The migration now executes:

`CREATE EXTENSION IF NOT EXISTS vector`

before adding the embedding column. A new blank database with no pre-enabled extension now upgrades directly to `h9c0d1e2f3a4`, and offline SQL places extension creation before the vector column.

## 4. Rollback validation

The original mocked failure test was retained and a real-transaction test was added.

Real PostgreSQL validation forced the second embedding call to fail after:

- old chunks were deleted;
- one replacement chunk was staged and flushed.

Observed result:

- Embedding calls: 2.
- Service result: failure response.
- Source final status: `failed`.
- Original chunk survived exactly.
- Partial replacement chunks surviving: 0.

This validates atomic delete-and-rebuild rollback behavior.

## 5. SourceSyncService dirty check

`SourceSyncService` now compares the stored and computed:

- `local_path`
- `sha256`

`processing_status` is reset to `pending` only when either value changes. An unchanged synchronized source preserves `completed`, avoiding unnecessary reprocessing and embedding cost.

Multi-PDF source folders were also corrected:

- an existing `local_path` is preferred;
- otherwise `document_metadata.local_filename` is matched;
- a sole PDF remains the backward-compatible fallback;
- ambiguous multi-PDF folders return an explicit error instead of selecting an arbitrary first file.

## 6. Grievance generation architecture

Before W5, Generate Grievance produced a small editable field dictionary. Save and Print persisted that dictionary, then rendered an HTML table through WeasyPrint. It did not fill an official grievance form.

The persistence, artifact, workflow, versioning, event, and download architecture was preserved. Only draft/template selection and grievance PDF rendering were changed.

The new export path is:

1. Generate an editable Step 1 or Step 2 draft from the registered template mapping.
2. Steward reviews/edits field values.
3. Save persists the existing `CaseFormDraftRecord` and `CaseSavedArtifact`.
4. Save and Print fills the authoritative AcroForm PDF with `pypdf`.
5. The existing `CaseAssetService` stores the generated PDF.

The steward verification UI now renders the returned field IDs dynamically instead of hardcoding six fields.

## 7. Official form inspection

### Step 1

Source: `Grievance Worksheet Step 1.pdf`

- Classification: fillable AcroForm PDF.
- Pages: 2.
- Terminal fields: 48.
- XFA: absent.
- Encrypted: no.
- SHA256: `67ceeb1bd29da665c82de11f786ab3681f9d83ab04dcb3e379579ac20cc0ddc7`.

### Step 2

Source: `Standard Grievance Form Step 2.pdf`

- Classification: fillable AcroForm PDF.
- Pages: 1.
- Terminal fields: 53.
- XFA: absent.
- Encrypted: yes; the document permits its empty user password.
- SHA256: `2649cc9acade62e78be89d569ae8f857b6c1acd9ac5cca1ad229838ddad138a1`.

The older three-page Local 300 PDF has no AcroForm fields and is retained only as a legacy/reference registry entry.

## 8. Step 1 implementation

Added and registered:

- Template ID: `official_grievance_worksheet_step_1`
- Asset: `app/assets/grievance_templates/official/step_1/Grievance_Worksheet_Step_1.pdf`
- Step: `step_1_initial`
- Usage status: confirmed

Step 1 progression now records the official template as available and can build a Step 1 draft.

The exporter fills the worksheet header, grievant, address, employment, installation, veteran/off-day/status, violations, facts, remedy, attachment, and page-2 continuation fields. Read-only page-2 mirror fields are explicitly synchronized because `pypdf` does not execute PDF JavaScript.

Printed Step 1 meeting/decision areas without AcroForm widgets remain part of the authoritative PDF but cannot be populated through AcroForm filling. No manual recreation of those areas was introduced.

## 9. Step 2 replacement

Added and registered:

- Template ID: `official_standard_grievance_form_step_2`
- Asset: `app/assets/grievance_templates/official/step_2/Standard_Grievance_Form_Step_2.pdf`
- Step: `step_2_appeal`

Step 2 progression now selects this official form. Legacy IDs:

- `local_300_form_79_1`
- `local_300_standard_grievance_form_79_1`

resolve to the official Step 2 exporter so existing callers continue to work.

The exporter maps text fields and checkbox groups, including Step 1 context, grievant/employment data, violations, facts/contentions, remedy, union representative, veteran status, off days, and employment status.

Generated PDFs preserve explicit appearance streams and set `/NeedAppearances` to false. Appearance validation found:

- Step 1: 21/21 populated sample widgets had appearances; 17/17 text appearances contained the filled text.
- Step 2: 20/20 populated sample widgets had appearances; 16/16 text appearances contained the filled text.

Step 3 was not implemented.

## 10. Supervisor Manual registration and synchronization

Three production `SUPERVISOR_MANUAL` sources were added to `KnowledgeBaseService`:

- `supervisor_manual_el921_grievance_2015`
- `supervisor_manual_el801_safety_2020`
- `supervisor_manual_f21_time_attendance_2016`

Each source has a distinct local path, version, PDF content type, and `document_metadata.local_filename`.

Synchronized SHA256 values:

- EL-921: `bc3905d1f0243eb4a7c599ef5d76e55da02a1f8d70a61079c37cfc1571872747`
- EL-801: `a39283fa9a9e6d73214a977bb1c4bd37e0535fecec4163b7680069fe024685d5`
- F-21: `b31b18c0a4bc4d17488f741be059dd9c6c8007b840207b7419e8aa0b6de7e15e`

All three distinct hashes and paths were verified.

## 11. Processing verification

Processing used the recovered W5 lifecycle and real OpenAI `text-embedding-3-small` embeddings against the configured local PostgreSQL database.

Observed lifecycle for every manual:

- `pending` observed after synchronization.
- `processing` observed after the committed processing transition.
- `completed` observed after chunk/embedding commit.
- `processed_at` populated.
- `processed_sha256 == sha256`.
- `processing_error` null.
- `processing_strategy == "generic_pdf_v1"`.

Persisted results:

- EL-921, DB ID 8, version `2015-04`: 50 pages, 49 chunks, 49 embedded.
- EL-801, DB ID 9, version `2020-07`: 102 pages, 101 chunks, 101 embedded.
- F-21, DB ID 10, version `2016-02`: 384 pages, 383 chunks, 383 embedded.
- Total: 533 chunks, 533 embeddings.

For all 533 chunks:

- embedding was present;
- embedding dimension was 1536;
- `chunk_metadata.page` was present;
- `chunk_metadata.chunking_strategy == "generic_pdf_v1"`;
- `chunk_metadata.source_type == "SUPERVISOR_MANUAL"`;
- `page_number` agreed with metadata page.

Final read-only verification after the full test suite confirmed all three sources remain completed with the same chunk counts and provenance.

## 12. Recovery cleanup

The four temporary files under `docs/temp/_recovery_blobs/` were deleted after validation. No recovery-blob Python files remain.

## 13. Remaining blockers

No blocker remains for the W5 Knowledge Foundation.

Non-blocking notes:

- The opt-in live regression harness remains skipped unless `RUN_REGRESSION=1` is set.
- The official Step 1 PDF contains printed areas without AcroForm widgets; future coordinate-overlay work would be required only if those non-widget areas must be machine-filled.
- Existing `datetime.utcnow()` deprecation warnings remain outside the W5 scope.
- The local PostgreSQL container remains running with the processed knowledge foundation persisted.

## 14. Retrieval-agent recommendation

**Retrieval-agent implementation may begin.**

The prerequisite knowledge foundation now has:

- validated schema and migrations;
- reliable dirty detection and rollback behavior;
- registered and embedded Supervisor Manual sources;
- verified provenance and chunk metadata;
- official Step 1 and Step 2 grievance generation;
- a green final full suite.

No `RetrievalOrchestrator`, `ContractAgent`, or `SupervisorManualAgent` implementation was added during this work.
