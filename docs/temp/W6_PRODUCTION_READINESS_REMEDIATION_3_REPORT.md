# W6 Production Readiness Remediation — Batch 3 — Completion Report

**Scope:** ARCH-2 / MAINT-1 step-progression dead-code and naming-collision
cleanup; pre-existing Alembic ORM/schema metadata-drift reconciliation.

**Status:** COMPLETE — implementation, full regression, Alembic, and live
validation finished. See §11 for the final verdict.

## 1. Starting state

- Branch: `main`
- Starting HEAD: `1111b4e` (`fix(w6): harden idempotency and case query indexes`)
- Expected Batch 1: `4ab328d`
- Expected Batch 2: `1111b4e`
- Starting tracked tree: inherited documentation modifications only
  (`PROJECT_STATE.md`, `docs/ARCHITECTURE.md`) plus the untracked authoritative
  handoff; unrelated untracked `docs/temp/` diagnostics were preserved.
- Starting Alembic current/head: single `i0j1k2l3m4n5`.
- Batch 2 checkpoint verdict: PASS WITH NON-BLOCKING FINDINGS.
- Documentation finalization commit:
  `83181e4` (`docs(w6): finalize remaining roadmap and expanded W7 plan`).

## 2. Verified step-progression inventory

### Active production workflow authority

- `app/services/case_workflow_service.py::CaseWorkflowService` owns the
  explicit persisted workflow FSM in Case Memory / `case_memories.workflow_state`.
- `GET /cases/{case_uuid}/workflow` and
  `POST /cases/{case_uuid}/workflow/transitions` call
  `CaseWorkflowService` directly.
- Outcome recording and lifecycle paths continue to use
  `CaseWorkflowService` to update and return the explicit workflow state.

### Active persisted step/history behavior

- `CaseStepProgressionPersistenceService` owns SQLAlchemy-backed `case_steps`,
  `case_step_outcomes`, `case_form_draft_records`, and
  `case_timeline_events` records.
- Production call sites include case create/workspace restoration,
  action availability, Save-and-Print, outcome/appeal progression, and
  close/settle/archive/reopen paths in `cases.py`, `case_service.py`,
  `saved_case_service.py`, `case_workspace_action_service.py`, and
  `case_saved_artifact_service.py`.
- This persisted record service was not rewritten and its public route-facing
  return shapes were preserved.

### Active stateless behavior

The removed in-memory class was used by production only for:

- Step 1/Step 2 template availability;
- Step 3 unavailable/deferred-form disclosure;
- buildable-template ID selection;
- step-number/next-step/resolved-outcome rules used by persisted progression;
- pure Step 1/Step 2 draft construction with `record_history=False`;
- pure timeline sorting.

These behaviors now live in
`app/services/case_step_progression_rules.py`, which has no mutable store.
Shared persisted-progression exceptions now live in
`app/services/case_step_progression_errors.py`.

### Test-only and dead behavior

`CaseStepProgressionService` previously held `self._states` and the following
stateful methods, exercised only by `tests/test_case_step_progression.py`:

- `create_case_progression`
- `get_progression`
- `update_step_status`
- `add_step_outcome`
- `close_step` / `close_case`
- `reopen_step` / `reopen_case`
- `appeal_to_next_step`
- `record_form_draft_created`
- `clear`

No production router imported or instantiated the class. No production service
called a stateful method. `CaseStepProgressionPersistenceService` instantiated
it only to call draft construction with `record_history=False`, so `_states`
was never read or written on that path.

### Compatibility and naming classification

- No external compatibility shim or client dependency was found in the
  repository.
- Tests that imported progression exceptions were internal imports, not
  compatibility use; they now import the dedicated errors module.
- The misleading `CaseStepProgressionService` /
  `CaseStepProgressionPersistenceService` naming collision is eliminated
  because the in-memory service and its stateful API were deleted.
- No deprecated stateful shim was retained.

## 3. Selected remediation

The smallest safe solution was:

1. Delete `case_step_progression_service.py` and its unreachable in-memory
   authoritative-looking state.
2. Move active pure rules/draft behavior to
   `case_step_progression_rules.py`.
3. Move shared exception types to `case_step_progression_errors.py`.
4. Update production and test imports.
5. Replace in-memory lifecycle tests with structural and behavioral stateless
   rules tests; retain the existing persisted progression and workflow suites.

This prevents an in-memory object from being mistaken for production workflow
state while leaving the persisted step records, workflow FSM, HTTP contracts,
Step 1/2 generation, and Step 3 tracking behavior unchanged.

## 4. Alembic drift baseline and root causes

Initial `alembic check` reported:

- removed live unique constraints for:
  `case_assets.asset_uuid`, `case_domain_events.event_id`,
  `case_form_draft_records.draft_uuid`,
  `case_saved_artifacts.artifact_uuid`,
  `case_step_outcomes.outcome_uuid`, and
  `case_timeline_events.event_uuid`;
- added ORM-derived unique indexes for `case_domain_events.event_id`;
- added redundant ORM-derived indexes for
  `case_domain_events.id`, `case_saved_artifacts.id`, and
  `case_memories.id`;
- for `case_memories`, removed live unique constraints on `case_id` and
  `case_uuid`, changed the existing non-unique indexes to ORM-derived unique
  indexes, and removed the live `workflow_state` index.

### Verified root cause by object

| Object | Live migration/schema intent | Prior ORM declaration | Autogenerate mismatch | Classification / risk |
|---|---|---|---|---|
| `case_assets.asset_uuid` | named unique constraint plus named unique index | `unique=True, index=True` flags | ORM collapsed representation and omitted constraint identity | metadata/naming only; both live guarantees preserved |
| `case_domain_events.event_id` | named unique constraint only | `unique=True, index=True` | proposed dropping constraint and adding a unique index | metadata-only; no data defect |
| `case_form_draft_records.draft_uuid` | named unique constraint plus named unique index | `unique=True, index=True` | omitted live constraint identity | metadata/naming only |
| `case_saved_artifacts.artifact_uuid` | named unique constraint plus named unique index | `unique=True, index=True` | omitted live constraint identity | metadata/naming only |
| `case_step_outcomes.outcome_uuid` | named unique constraint plus named unique index | `unique=True, index=True` | omitted live constraint identity | metadata/naming only |
| `case_timeline_events.event_uuid` | named unique constraint plus named unique index | `unique=True, index=True` | omitted live constraint identity | metadata/naming only |
| `case_memories.case_id` | named unique constraint plus separate non-unique index | `unique=True, index=True` | ORM wanted a unique index and removal of the constraint/non-unique index | metadata-only; one-memory-per-case guarantee already enforced |
| `case_memories.case_uuid` | named unique constraint plus separate non-unique index | `unique=True, index=True` | same interaction | metadata-only |
| `case_memories.workflow_state` | named non-unique index from `g8b9c0d1e2f3` | no ORM index declaration | proposed removing the live index | metadata-only |
| scoped primary-key `id` indexes | migrations intentionally differ: present on asset/draft/outcome/timeline, absent on domain-event/memory/saved-artifact | unconditional `index=True` on all scoped PKs | proposed redundant indexes where migrations created none | metadata-only |

Live `pg_indexes` and `pg_constraint` were inspected for all seven tables.
No case content or confidential values were queried or printed.

Verified live uniqueness constraints:
`case_assets_asset_uuid_key`, `case_domain_events_event_id_key`,
`case_form_draft_records_draft_uuid_key`,
`case_saved_artifacts_artifact_uuid_key`,
`case_step_outcomes_outcome_uuid_key`,
`case_timeline_events_event_uuid_key`, `case_memories_case_id_key`, and
`case_memories_case_uuid_key`.

Verified corresponding scoped indexes included:
`ix_case_assets_asset_uuid`, `ix_case_form_draft_records_draft_uuid`,
`ix_case_saved_artifacts_artifact_uuid`,
`ix_case_step_outcomes_outcome_uuid`,
`ix_case_timeline_events_event_uuid`, `ix_case_memories_case_id`,
`ix_case_memories_case_uuid`, `ix_case_memories_workflow_state`, and each
table's migration-created or primary-key index. Batch 2 idempotency and query
indexes remained present and unchanged.

## 5. Metadata reconciliation and migration decision

`app/database/models.py` now truthfully models the existing migrated schema:

- explicit named `UniqueConstraint` declarations match live constraints;
- explicit named `Index` declarations match live unique/non-unique indexes;
- ambiguous `unique=True, index=True` combinations were removed on scoped
  columns;
- PK `index=True` remains only where the migration created that index;
- no uniqueness guarantee was weakened or duplicated.

**Migration required: no.** The live schema already matches migration history
and enforces all intended guarantees. This is an ORM metadata correction only;
creating DDL would have been unnecessary and risked duplicate or destructive
operations. No old migration was modified.

Post-reconciliation:

```text
alembic check -> No new upgrade operations detected.
```

Final verification:

```text
alembic current -> i0j1k2l3m4n5 (head)
alembic heads   -> i0j1k2l3m4n5 (head)
alembic check   -> No new upgrade operations detected.
```

## 6. Files changed

- `app/database/models.py`
- `app/services/case_step_progression_errors.py` (new)
- `app/services/case_step_progression_rules.py` (new)
- `app/services/case_step_progression_service.py` (deleted)
- `app/services/case_step_progression_persistence_service.py`
- `app/services/case_saved_artifact_service.py`
- `app/services/case_service.py`
- `app/services/case_workspace_action_service.py`
- `app/services/saved_case_service.py`
- `tests/test_case_step_progression.py`
- tests that imported moved exception types
- `tests/test_saved_case_service.py` (made one shared-DB ordering fixture
  deterministic after the larger live synthetic dataset exposed its
  first-page assumption)
- `PROJECT_STATE.md`
- `docs/ARCHITECTURE.md`
- this report

No frontend feature, W7, migration, dependency, auth, CORS, CI, ANN-index,
Step 3 form, or `case_service.py` splitting work was introduced.

## 7. Tests added or updated

- `tests/test_case_step_progression.py` now verifies:
  - Step 1/2 template availability and draft-building behavior;
  - no official Step 3 form;
  - removal of the in-memory module and `_states`;
  - no production router dependency on old or stateless progression helpers;
  - `CaseWorkflowService` remains the explicit route authority;
  - complete production import coverage after helper moves.
- Existing persisted progression, workflow FSM, action contract, lifecycle,
  outcome, and Save-and-Print suites remain in place.
- Exception imports were updated in affected tests.

## 8. Validation results

### Focused

```text
pytest test_case_step_progression.py
       test_case_step_progression_persistence.py
       test_case_architecture_hardening.py
       test_case_workspace_action_contract.py -q
-> 57 passed
```

`compileall` for `app` plus the focused test passed.

The broader workflow-focused run covering persisted progression, workflow FSM,
lifecycle restoration, saved cases, Case Memory, Save-and-Print, case service,
and action contracts passed:

```text
138 passed
```

The first broad focused run exposed one pre-existing test-fixture assumption:
`test_saved_cases_list_newest_first` assumed its old synthetic timestamps would
remain on the first unfiltered development-database page. The test now filters
to its two UUID-prefix fixtures and gives the intended "newest" fixture a
current synthetic event timestamp. The isolated test and full focused rerun
passed. Production query behavior was not changed.

### Full backend

```text
python -m pytest tests/ -m "not integration" -q
-> 667 passed, 6 deselected, 397 warnings
```

All warnings are the pre-existing Starlette/httpx warning and deferred
`datetime.utcnow()` deprecation warnings.

### Integration

```text
python -m pytest tests/ -m "integration" -v
-> 5 passed, 1 skipped, 667 deselected, 140 warnings
```

The skipped live regression-pipeline smoke is pre-existing and environment
gated. Real PostgreSQL idempotency concurrency tests all passed.

### Frontend regression

- `npm run typecheck`: PASS
- `npm run lint`: PASS
- Initial `npm run test:run` while the backend suite was consuming the same
  machine: 130/140 passed; ten UI tests timed out waiting for asynchronous
  workspace rendering.
- Immediate unmodified standard retry: 136/140 passed; four unrelated UI tests
  timed out or remained on the loading state.
- Deterministic full-suite rerun,
  `npm run test:run -- --maxWorkers=1`: PASS — 14 files, 140 tests.
- `npm run build`: PASS. Existing >500 kB chunk-size advisory only.

No frontend source or test file was changed. The standard parallel Vitest
timing sensitivity is recorded as a non-blocking inherited test-harness
finding; serialized execution proves all frontend assertions pass.

### Live validation

A fresh backend using the Batch 3 working tree ran on port 8001 against
PostgreSQL. Synthetic case
`34680824-cadd-4512-8212-0cda604c4400` exercised the real HTTP
router/service/database path:

1. health returned 200;
2. case creation succeeded;
3. workspace and explicit workflow loaded;
4. Step 1 generated the official Step 1 temporary draft;
5. a denied Step 1 outcome appealed the same case to Step 2;
6. a fresh DB session confirmed `case_memories.workflow_state` matched
   `GET /workflow` and persisted step rows were Step 1 + Step 2;
7. Step 2 generated the official Step 2 temporary draft;
8. a denied Step 2 outcome advanced persisted tracking to Step 3;
9. Step 3 had no registered official template. The pre-existing compatibility
   action returned `step_3_template_deferred`, with
   `official_artifact_created=false` and `export_attempted=false`; no official
   Step 3 form was exposed or created;
10. the workflow endpoint remained healthy and a missing-case 404 exposed no
    traceback, database-driver name, credential, or filesystem path.

Result: **10/10 PASS**. The temporary port-8001 backend was stopped. Inherited
port-8000/Vite processes were left untouched.

## 9. Deferred findings

- Batch 4/W6 M10 UI/a11y/print/PDF/exit-review scope
- FE-2 global TypeScript strict mode
- `datetime.utcnow()` cleanup
- React Router dependency remediation
- `case_service.py` splitting
- BE-5 pgvector ANN evaluation (W7)
- CI/CORS (W11)
- production identity/authorization (W9)

## 10. Scope control

No Batch 4/M10 or W7 implementation was performed. No dependency was installed
or upgraded. No destructive DDL, data correction, UUID rewrite, row deletion,
nullable/PK/FK change, table rebuild, or migration was performed. Unrelated
untracked diagnostics were not modified or staged.

## 11. Final verdict

**PASS WITH NON-BLOCKING FINDINGS**

ARCH-2 / MAINT-1 are resolved without changing the persisted workflow FSM or
route contracts. All scoped Alembic drift is reconciled in ORM metadata with no
migration or DDL, and `alembic check` is clean. Focused, complete backend,
PostgreSQL integration, serialized full frontend, build, and live HTTP
validation pass.

Non-blocking inherited findings:

1. the frontend suite's standard parallel execution is timing-sensitive on
   this machine (all 140 tests pass with one worker; no frontend files changed);
2. deferred `datetime.utcnow()` warnings remain;
3. the existing Step 3 compatibility action can construct a non-official
   `step_3_template_deferred` field-value draft, but no registered official
   Step 3 template, PDF, or artifact exists. This behavior was preserved rather
   than redesigned in Batch 3.

No destructive-migration question remains unresolved.
