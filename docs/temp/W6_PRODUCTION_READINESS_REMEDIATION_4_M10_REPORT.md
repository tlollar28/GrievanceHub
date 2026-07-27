# W6 Production Readiness Remediation — Batch 4 / M10

**Status:** COMPLETE
**Final verdict:** **PASS WITH NON-BLOCKING FINDINGS — W6 COMPLETE**

## 1. Starting checkpoint

- Branch: `main`
- Starting HEAD: `35d5945` (`fix(w6): reconcile schema metadata and step progression`)
- Batch 3 documentation commit: `83181e4`
- Batch 3 implementation commit: `35d5945`
- Batch 1 commit: `4ab328d`
- Batch 2 commit: `1111b4e`
- Starting tracked tree: clean (`git diff --stat` produced no output)
- Starting untracked state: inherited `docs/temp/` audit reports, smoke helpers,
  baselines, and diagnostics only. They were not modified, removed, cleaned, or
  staged by this batch.
- Branch was 17 commits ahead of `origin/main`.
- Alembic current: `i0j1k2l3m4n5 (head)`
- Alembic heads: one head, `i0j1k2l3m4n5`
- Alembic check: `No new upgrade operations detected.`

The checkpoint therefore satisfied the Batch 4 entry gate. Batch 3 was already
committed; no Batch 3 work was adopted or committed by this batch.

## 2. Source documents inspected

The review used the comprehensive production-readiness audit, remediation Batch
1–3 reports, W6 M0–M9 reports, `PROJECT_STATE.md`, `docs/ARCHITECTURE.md`,
`docs/ROADMAP.md`, `docs/W6_UI_ARCHITECTURE.md`, and
`docs/temp/W6_REMAINING_ROADMAP_AND_W7_HANDOFF.md`. Repository behavior and
tests remain the source of truth where documentation and implementation differ.

## 3. UI-state implementation inventory (pre-remediation)

### Saved Cases dashboard and Cases list

- Initial loading: explicit “Loading saved cases…” status.
- Background refresh: pagination is disabled while fetching; existing content
  needs to remain visible and receive a non-blocking refresh status.
- Empty: current filters are named and the New Case route remains available.
- Recoverable error: safe inline alert with Retry.
- Not found / unavailable: not applicable to list; case activation handles
  closed/reopen and mutation failure inline.
- Mutation pending/failure: selected row is disabled while opening/reopening;
  status region announces result or failure.
- Keyboard/focus/screen reader: semantic table, buttons/links, heading,
  navigation, and polite status region.
- Existing tests: list loading/empty/error/retry, filters, pagination,
  open/reopen, URL restoration.
- Missing coverage identified: non-blocking stale-data refresh behavior and
  route-heading focus.

### Create Case

- Initial/empty: form is immediately usable; no remote initial state.
- Mutation pending: all fields and submit are disabled; submit copy changes to
  “Creating case…”.
- Validation/mutation failure: required field is associated with its message
  and focused; API error is announced.
- Retry: resubmitting the preserved form is the retry path.
- Keyboard/focus/screen reader: native form controls, labels, fieldset/legend,
  required/invalid/described-by relationships.
- Existing tests: validation, pending, API failure, request contract,
  navigation, and no automatic chat/analysis.
- Missing coverage identified: route-heading focus after navigation.

### Case workspace shell and Case Rail

- Initial loading: dedicated workspace-restoration page, heading, `aria-busy`,
  and loading description.
- Background refresh: loaded shell remains mounted and is marked busy.
- Empty/not found/error: no-data, 404, and connection/API failure are distinct;
  transient failures offer Retry, 404 does not.
- Unavailable features: terminal status and action reasons are visible.
- Mutation pending/failure: Facts editor and route actions own their pending and
  failure states.
- Keyboard/focus/screen reader: case `h1`, semantic workspace navigation, Case
  Rail links/buttons, and route focus support.
- Existing tests: restore loading/error/retry/not-found distinction, empty
  memory/overview, fact mutation, and cross-case restoration.
- Missing coverage identified: consistent heading focus on every shell route.

### Conversation

- Initial loading: explicit conversation loading status, distinct from empty.
- Background refresh: loaded messages remain available.
- Empty: explains that a steward can send a question and what that action does.
- Query/mutation failure: history has Retry; failed turns preserve steward text
  and attachments and expose Retry.
- Mutation pending: composer is disabled, pending turn is visible, and the
  research status progresses from “Researching authorities…” to a longer-running
  explanation.
- Keyboard/focus/screen reader: Enter sends, Shift+Enter adds a newline,
  citations are buttons, message list is a live log, assistant completion is
  announced, and attachment controls have names.
- Existing tests: loading/empty/retry, composer keys, pending/failure/retry,
  citations, retrieval states, attachments, and no artifact side effects.
- Missing coverage identified: no material behavior gap.

### Evidence

- Initial loading: explicit evidence loading status.
- Background refresh: existing asset data remains available.
- Empty: states that no evidence is uploaded; Upload is the available action.
- Query/mutation failure: list has Retry; upload preserves actionable safe
  errors.
- Mutation pending: upload button and controls disable and announce upload work.
- Unavailable: terminal/read-only cases disable upload.
- Keyboard/focus/screen reader: semantic table/caption, labeled file input,
  keyboard-reachable detail buttons, status and error regions.
- Existing tests: loading/empty/error/retry, upload pending/success/failure,
  keyboard detail access, attachment distinction, and cross-case isolation.
- Missing coverage identified: inherited direct-navigation test uses a
  low-level router transition that is timing-sensitive in parallel execution.

### Analysis

- Initial loading: saved-version loading is distinct from empty.
- Background refresh: saved versions remain available.
- Empty: explains Generate → temporary preview → Save.
- Query/generate/save failures: list and Generate have Retry; Save retry reuses
  the same idempotency key.
- Mutation pending: Generate and Save actions prevent duplicate submission and
  use busy labels/`aria-busy`.
- Unavailable/disabled: closed cases and backend prerequisites show reasons.
- Save/print states: temporary, official, working-draft, `saved_pdf_failed`, and
  idempotent replay are separately labeled.
- Keyboard/focus/screen reader: native controls, named action group, temporary
  preview status, export controls, and announced result states.
- Existing tests: loading/empty/retry, Generate/Cancel, pending, payloads,
  stable retry key, PDF failure, replay, labels, and read-only export.
- Missing coverage identified: cancel dialog focus trap/Escape/restoration and
  failed-PDF idempotent replay messaging.

### Grievance

- Initial loading: saved-grievance loading is distinct from empty.
- Background refresh: saved entries remain available.
- Empty: explains supported Step 1/Step 2 generation and Save.
- Query/generate/save failures: list and Generate have Retry; Save retry
  preserves its idempotency key.
- Mutation pending: Generate and Save actions prevent duplicates and announce
  progress.
- Unavailable: prerequisite and terminal reasons are visible; unsupported
  templates do not open the editor.
- Validation: required/protected fields are associated with controls and the
  first invalid field receives focus.
- Save/print states: temporary, official, PDF failed, and replay states are
  distinct.
- Existing tests: Step 1/2 Generate/Edit/Validate/Save/Print, pending, retry,
  PDF labels/failures, replay, case switching, and no Step 3 UI.
- Missing coverage identified: cancel dialog focus trap/Escape/restoration,
  failed-PDF replay messaging, and backend rejection of an attempted official
  Step 3/unknown-template save before persistence.

### Artifacts and History

- Initial loading: library, detail, Official Case Record, timeline, context, and
  PDF have panel-scoped loading states.
- Background refresh: surrounding workspace and loaded data remain usable.
- Empty: library/history/timeline/detail each explain what is absent.
- Recoverable error: library/detail/history/timeline have Retry; context detail
  still needs a retry control.
- Not found/PDF unavailable: missing artifact detail and unavailable/failed PDF
  are distinct.
- Mutation pending/failure: comparison is the only operation; browsing, context,
  and PDF access remain read-only.
- Keyboard/focus/screen reader: semantic lists, checkboxes, buttons, status
  labels, named PDF frames, and context dialog Escape/restoration.
- Existing tests: loading/empty/error, detail/PDF, no storage paths, history,
  timeline, compare, context, Escape, and read-only behavior.
- Missing coverage identified: complete dialog focus trap and context retry.

### Workflow and Outcomes

- Initial loading: workflow loading status.
- Background refresh: existing workflow remains available.
- Error: safe workflow error with Retry; mutation errors are inline.
- Empty/unavailable: no permitted next state and terminal/outcome-unavailable
  explanations are explicit.
- Mutation pending/failure: outcome/lifecycle actions disable duplicate
  submission, announce work, validate fields, and preserve a retryable form.
- Keyboard/focus/screen reader: native form controls, error summary,
  progression list, confirmation dialogs, Escape, and focus restoration.
- Existing tests: workflow loading/error, validation/pending, outcomes,
  lifecycle confirmation/Escape, Step 3 disclosure, and safe errors.
- Missing coverage identified: confirmation-dialog Tab focus trap.

### Sources Research

- Initial loading: search starts in an instructional state; filter-metadata
  loading/error was not visibly distinguished.
- Background refresh: existing search results remain while fetching.
- Empty/failed/skipped/partial: distinct retrieval notices.
- Recoverable error: search can be resubmitted; passage detail needs explicit
  Retry.
- Mutation pending: search form disables and announces corpus search.
- Keyboard/focus/screen reader: semantic search form, result buttons, pagination,
  status announcements, and read-only passage dialog.
- Existing tests: safe endpoint use, URL restore, empty/failed states, keyboard
  result activation, dialog close, and no admin/API-key exposure.
- Missing coverage identified: duplicate route-level `h1`, metadata
  loading/error/retry, dialog focus trap/restoration, and user-visible mojibake
  characters in status/detail text.

### Shared shell, dialogs, connection, route error, and not-found

- Skip link and `main` landmark exist; global focus-visible styling is present.
- Connection status has checking/connected/unavailable labels and Retry.
- Not-found route has a clear heading and return link.
- Route render errors currently risk rendering raw `Error.message` or route
  response text and require sanitization.
- Modal dialogs enter focus and restore it, but do not consistently trap Tab;
  Analysis/Grievance discard dialogs do not yet implement Escape/focus
  restoration.
- Missing shared coverage: route heading focus, safe route-error copy, and
  deterministic focus trapping across all modal dialogs.

## 4. Accessibility inventory (pre-remediation)

Verified foundations already present:

- semantic `header`, `nav`, `main`, `section`, table/list/form structures;
- a visible-on-focus skip link targeting `#main-content`;
- one workspace case heading plus route section headings (except the duplicate
  Sources Research `h1` finding);
- global `:focus-visible` outline using existing design tokens;
- labeled controls and native button/link semantics;
- live status/error regions for major queries and mutations;
- keyboard-accessible citation, research, artifact, PDF, and evidence controls;
- associated required-field and validation messages;
- Step 3 deferred-form disclosure exposed as text/`role="note"`;
- no hover-only critical action and no color-only status.

Required narrow corrections:

1. central modal Tab trapping, Escape handling, focus entry, and restoration;
2. focus the page heading on route changes;
3. reduce Sources Research to the single workspace-level `h1`;
4. surface research metadata loading/error/retry;
5. sanitize route-level and API errors before rendering;
6. repair mojibake in Sources Research copy;
7. add `role="status"` to remaining loading/empty descriptions.

## 5. Frontend parallel-test investigation — baseline

The machine was otherwise idle: no backend pytest run or frontend build was
running. The first required unmodified standard run was:

```text
npm run test:run
14 files: 13 passed, 1 failed
140 tests: 139 passed, 1 failed
Vitest duration: 136.90s
```

Exact failure:

`src/test/evidence.test.tsx` →
`supports direct navigation and browser-style refresh restore` timed out after
the low-level `router.navigate(...)` call while waiting for the Conversation
heading. The workspace itself was already rendered and healthy. The test uses
the router API directly for a browser interaction and waits on the default
short element-query deadline. The application route and message mock are
present; this is currently classified as a test-harness scheduling assumption,
not evidence of an application race. The planned correction is to navigate
through the visible workspace links with `userEvent`, which is wrapped in React
test updates and observes the same behavior a keyboard/pointer user invokes.
No sleep, global timeout increase, or worker serialization will be used.

Later parallel runs exposed a second harness assumption: several route tests
used default short `findBy*` deadlines while the shell still legitimately
displayed “Restoring case workspace…”. The focused correction was:

- navigate the evidence route through its visible link with `userEvent`;
- add `waitForWorkspaceReady` in `frontend/src/test/testUtils.tsx`;
- give that helper a local 5-second timeout;
- wait for the restore heading to disappear, then optionally wait for a named
  heading or text node;
- retain normal Vitest parallel execution.

No global query/test timeout was inflated, no sleeps were added, and
`maxWorkers=1` was not used as acceptance. Three consecutive unmodified
standard runs passed:

1. 14 files / 142 tests / 124.57s — PASS
2. 14 files / 142 tests / 128.89s — PASS
3. 14 files / 142 tests / 109.41s — PASS

## 6. Scope-control checkpoint

No W7 work, dependency change, migration change, global TypeScript strict-mode
change, auth/RBAC, CORS, CI, source administration, pgvector ANN/TurboVec work,
Step 3 official form, workflow redesign, or visual-system rewrite has been
introduced. PostgreSQL remains the system of record and pgvector remains the
retrieval backend.

## 7. Contract defect discovered before correction

The frontend correctly exposes no Step 3 official form, and the PDF renderer
rejects an unknown Step 3 template. However, inspection found that
`CaseSavedArtifactService.save_and_print_grievance` validated the template only
inside the optional PDF-rendering branch. A direct request with
`prepare_pdf=false` and an unregistered or Step 3 template could therefore
persist an official grievance artifact before any template rejection. That
violates the established W6 contract that only Step 1 and Step 2 have official
forms and that Step 3 is workflow tracking with a deferred-form disclosure.

The approved narrow, backward-compatible correction is to reject an
unregistered official template and any `step_3` grievance save before creating
a draft, artifact, timeline event, or workflow transition. Existing Step 1,
Step 2, and legacy Step 2 template aliases remain accepted. No request or
response schema changes, persisted workflow changes, migration, or Step 3
template are introduced.

## 8. Files changed (final implementation)

Frontend:

- `frontend/src/components/useModalDialogFocus.ts` (new)
- `frontend/src/components/RouteFocusManager.tsx` (new)
- `frontend/src/components/AppShell.tsx`
- `frontend/src/components/RouteErrorBoundary.tsx`
- `frontend/src/api/client.ts`
- `frontend/src/components/workflow/ConfirmActionDialog.tsx`
- `frontend/src/components/research/SourceDetailDialog.tsx`
- `frontend/src/components/research/SourcesResearchPanel.tsx`
- `frontend/src/components/research/SourceResultItem.tsx`
- `frontend/src/components/research/SourceResultsList.tsx`
- `frontend/src/components/research/RetrievalStatusNotice.tsx`
- `frontend/src/components/artifacts/HistoryContextDialog.tsx`
- `frontend/src/components/analysis/AnalysisPanel.tsx`
- `frontend/src/components/analysis/AnalysisPreview.tsx`
- `frontend/src/components/analysis/AnalysisSaveActions.tsx`
- `frontend/src/components/grievance/GrievancePanel.tsx`
- `frontend/src/components/grievance/GrievanceDraftEditor.tsx`
- `frontend/src/components/grievance/GrievanceSaveActions.tsx`
- `frontend/src/components/grievance/GrievancePdfActions.tsx`
- `frontend/src/test/evidence.test.tsx`
- `frontend/src/test/analysis.test.tsx`
- `frontend/src/test/sourcesResearch.test.tsx`
- `frontend/src/test/grievance.test.tsx`

Backend:

- `app/services/case_saved_artifact_service.py`
- `app/services/grievance_pdf_export_service.py`
- `tests/test_case_save_and_print_artifacts.py`

Documentation/report:

- `docs/temp/W6_PRODUCTION_READINESS_REMEDIATION_4_M10_REPORT.md`

## 9. Exact user-facing behavior changes

Accessibility and keyboard:

- Modal dialogs now share native focus trapping, Escape close, initial focus, and
  focus restoration.
- Route changes move focus into the main content landmark / page heading path.
- Sources Research uses a section `h2`, leaving the case title as the sole page
  `h1`.
- Research metadata loading and recoverable failure now announce status and
  expose Retry.
- Passage-detail and history-context dialogs expose Retry on recoverable load
  failures.
- Route-level errors no longer render raw exception or internal response text.
- Mojibake punctuation in Sources Research copy was corrected.

Loading / empty / error:

- API client suppresses server (5xx) body text and filters internal detail
  patterns from client-facing messages.
- Save and Save-and-Print buttons announce distinct pending labels
  (`Saving…` vs `Saving and preparing PDF…`).

Print / PDF:

- Saved-but-PDF-failed messaging states that the official artifact remains saved
  and that PDF access is read-only / non-duplicating.
- Grievance PDF unavailable/failed copy no longer suggests that opening PDF
  regenerates or replaces the artifact.
- Backend `pdf_error` no longer includes exception class names.

Contract correction:

- Unsupported and Step 3 grievance save-and-print requests are rejected before
  draft/artifact persistence.

## 10. Validation summary

All required validation passed:

- frontend typecheck: PASS;
- frontend lint: PASS;
- frontend production build: PASS in the successful Batch 4 validation run;
- frontend standard tests: three consecutive 14-file / 142-test parallel runs
  passed (124.57s, 128.89s, 109.41s);
- backend non-integration: 670 passed, 6 deselected, 397 warnings in 39.29s;
- PostgreSQL integration: 5 passed, 1 skipped, 670 deselected, 140 warnings in
  12.46s;
- Alembic current/heads/check: PASS;
- realistic analysis, Step 1, Step 2, Step 3 boundary, and controlled PDF
  failure live validation: PASS.

## 11. Frontend parallel-test conclusion

The original failure was the low-level `router.navigate` timing in
`evidence.test.tsx` under parallel load. Subsequent failures were default-short
workspace restore waits, not application route failures. The helper-local
5-second `waitForWorkspaceReady` contract waits until “Restoring case
workspace…” is absent and can then require optional heading/text evidence.
Evidence navigation now uses `userEvent`. This hardens observable test
readiness without globally weakening timeout discipline or serializing workers.

## 12. Frontend static validation

| Check | Result |
|-------|--------|
| TypeScript typecheck | **PASS** |
| ESLint | **PASS** |
| Vite production build | **PASS** |
| Dependency changes | **None** |

The build result is cited from the successful Batch 4 validation run; it was
not necessary to change dependencies or build configuration.

## 13. Backend validation

| Suite | Result |
|-------|--------|
| Non-integration | **670 passed, 6 deselected, 397 warnings in 39.29s** |
| PostgreSQL integration | **5 passed, 1 skipped, 670 deselected, 140 warnings in 12.46s** |

The expected integration skip was
`tests/test_regression_harness.py::test_regression_live_pipeline_smoke`.
No failing backend tests remained.

## 14. Alembic validation

- `alembic current`: `i0j1k2l3m4n5 (head)`
- `alembic heads`: `i0j1k2l3m4n5`
- `alembic check`: `No new upgrade operations detected.`

Batch 4 introduced no migration or DDL change.

## 15. Live analysis PDF validation

**PASS.** Synthetic case
`0520a65d-4b17-450a-a016-926d5da634cb` generated a temporary analysis, saved
artifact `0953db1e-bfef-47cc-beeb-99e0fd93158c`, and returned a ready six-page
PDF of **34,767 bytes**. Representative extracted headings/text included
“GrievanceHub Analysis Report”, “Quick Assessment”, and the synthetic case
title. Idempotent replay returned the same artifact with one report version and
one matching idempotency-key row.

## 16. Live Step 1 grievance PDF validation

**PASS.** Synthetic case
`d3e5bf39-2f8b-4588-824b-61764c5c10e1` saved artifact
`5298a827-84a1-4bf1-a3dd-83f3966ed12f` and returned a ready two-page PDF of
**691,653 bytes**. Representative AcroForm values were `M10-S1-001`,
`Avery Synthetic`, and “Management changed Avery Synthetic's posted schedule.”
One official draft and one artifact were retained; replay was idempotent.

## 17. Live Step 2 grievance PDF validation

**PASS.** Synthetic case
`0da3cc6d-2269-4e95-876a-c7e969364833` advanced to Step 2, saved artifact
`0e656d7e-5b13-48bf-b9fb-fd33896d7a4d`, and returned a ready one-page PDF of
**157,345 bytes**. Representative fields were `M10-S2-001`,
`Jordan Synthetic`, and `Articles 8 and 15`. One official draft and one
artifact were retained; replay was idempotent.

## 18. Live Step 3 boundary validation

**PASS.** Synthetic case
`03f44984-905b-4628-b35e-b897e22f8527` advanced to
`step_3_analysis`. Generate returned the deferred
`step_3_template_deferred` disclosure. Save attempts for both that deferred
template and an unknown template returned HTTP 400 **before persistence**.
Post-check counts remained zero official artifacts, zero official drafts, and
zero generated grievance PDFs.

The corrected contract is explicit: unsupported and Step 3 official grievance
saves are rejected before draft, artifact, event, or PDF persistence.

## 19. Controlled PDF failure validation

**PASS.** Synthetic case
`5f6cdd98-b63d-4fca-85e6-03abf6c29a3b` retained official artifact
`214a8849-b054-43b2-acb4-36380fe3a368` with status `saved_pdf_failed`.
`pdf_error` was the safe text “PDF generation failed after the artifact was
saved.” It exposed no exception class, stack trace, path, or sentinel detail.
Replay returned `idempotent_replay`, retained the same failed artifact, and
created no duplicate report version or artifact.

## 20. Live evidence files and cleanup disposition

Evidence is preserved in:

- `docs/temp/_m10_live_smoke.py`
- `docs/temp/_m10_live_smoke_out.txt`
- `docs/temp/_m10_live_case_uuids.txt`

The PostgreSQL container was stopped and had to be restarted before live
validation. The repository has no established synthetic-case deletion cleanup
API, so the five synthetic records and their referenced generated files were
retained rather than deleted through ad hoc database/file operations.

## 21. Accessibility and focus results

**PASS.** Batch 4 added:

- `useModalDialogFocus` for initial focus, Tab/Shift+Tab containment, Escape,
  and trigger-focus restoration;
- `RouteFocusManager` for route-level main heading focus;
- focus behavior for workflow confirmation, history context, research source
  detail, analysis discard, and grievance discard dialogs;
- a single page-level `h1` in the case workspace with Sources Research as `h2`;
- metadata and passage loading/error/retry announcements.

Regression tests cover focus entry, trapping, Escape, restoration, route
heading focus, and retry behavior.

## 22. Safe error and content-polish results

**PASS.** API 5xx response bodies and internal-pattern client messages are not
rendered to stewards. Route errors use safe fixed copy rather than raw exception
or response text. Sources Research mojibake punctuation was repaired, and
research metadata/detail failures now provide safe retry controls.

## 23. Save and PDF UX results

**PASS.** Analysis and grievance actions distinguish `Saving…` from
`Saving and preparing PDF…`. `saved_pdf_failed` messaging states that the
official artifact remains saved. Failed/unavailable PDF actions are described
as read-only and non-regenerating so stewards are not led to expect duplicate
artifact creation.

## 24. W6 exit matrix

| Required item | Classification | Evidence / disposition |
|---------------|----------------|------------------------|
| Core case workflow usable through UI | **PASS** | M0–M10 routes/actions and regression suites |
| Retrieval available in normal workflow | **PASS** | Conversation + Sources Research |
| Citations visible and traceable | **PASS** | Citation/detail surfaces and tests |
| Generated analysis separated from source evidence | **PASS** | Established W6 content taxonomy |
| Grievance preview/generation | **PASS** | Step 1/2 Generate → Edit → Validate → Save |
| Official forms generated from case workflow | **PASS** | Live Step 1 and Step 2 PDFs |
| Common failures avoid raw stack traces | **PASS** | Safe API/route/PDF errors |
| UI-discovered defects have regressions | **PASS** | Step 3, PDF, focus, metadata, timing tests |
| No critical workflow requires manual DB edits/scripts | **PASS** | Steward APIs own workflows; smoke script is validation only |
| Empty/loading/error/retry states | **PASS** | Inventory plus M10 targeted corrections |
| Keyboard navigation and modal focus | **PASS** | Shared focus hook and route focus |
| Print/PDF behavior and failure retention | **PASS** | Live PDF matrix + controlled failure |
| Standard parallel frontend stability | **PASS WITH NON-BLOCKING FINDING** | Harness timing hardened; 3 consecutive passes |
| PostgreSQL availability during live validation | **PASS WITH NON-BLOCKING FINDING** | Container required restart, then all live checks passed |
| Warning-free backend run | **PASS WITH NON-BLOCKING FINDING** | `datetime.utcnow()` and Starlette TestClient deprecations remain |
| Live regression harness execution | **PASS WITH NON-BLOCKING FINDING** | One expected integration smoke skip |
| Synthetic-case cleanup | **PASS WITH NON-BLOCKING FINDING** | No established cleanup API; records retained safely |
| Production authentication / authorization | **DEFERRED BY ROADMAP** | W9 |
| CORS and CI/CD | **DEFERRED BY ROADMAP** | W11 |
| pgvector ANN / conditional TurboVec evaluation | **DEFERRED BY ROADMAP** | W7; TurboVec not selected |
| Multi-agent authority workflow | **DEFERRED BY ROADMAP** | W8 |
| LMOU / arbitration expansion | **DEFERRED BY ROADMAP** | W10 |
| Production packaging / deployment | **DEFERRED BY ROADMAP** | W11 |

No item is classified **FAIL — BLOCKS W6 EXIT**.

## 25. Non-blocking findings

1. PostgreSQL was stopped and required a container restart before live checks.
2. Existing `datetime.utcnow()` deprecation warnings remain.
3. Existing Starlette `TestClient` deprecation warnings remain.
4. The expected live-pipeline integration smoke remains skipped.
5. No established synthetic-case cleanup API exists.
6. Parallel Vitest failures were harness timing assumptions and are now
   hardened without global timeout inflation or worker serialization.

These findings do not invalidate W6 feature, contract, migration, or regression
results.

## 26. Roadmap deferrals and architecture guardrails

- Auth/identity/authorization: W9.
- CORS, CI/CD, packaging, deployment, and operations: W11.
- Formal quality evaluation, pgvector baseline tuning, and conditional
  TurboVec shadow evaluation: W7.
- Multi-agent authority workflow: W8.
- LMOU and arbitration expansion: W10.

PostgreSQL remains the system of record. TurboVec is conditional and was not
selected or implemented. Batch 4 contains no W7 implementation and does not
claim production security, deployment readiness, or elimination of
hallucinations.

## 27. Model-escalation decision

**Sonnet 5 review is not required.** No escalation criterion was met: there was
no destructive migration risk, security-critical authorization bypass,
unusually difficult concurrency defect, or failed lower-cost implementation
attempt requiring specialist escalation.

## 28. Final status and verdict

- W6 M10: **complete**
- Production-readiness Batch 4: **complete**
- W6 M0–M10 + Batches 1–4: **complete**
- Final verdict: **PASS WITH NON-BLOCKING FINDINGS — W6 COMPLETE**
- Next phase: **W7 — planned, gated, and not started**
- PostgreSQL: **system of record**
- TurboVec: **conditional; not selected**
