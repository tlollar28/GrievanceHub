# W6 M8 — Workflow Outcomes, Case Lifecycle, and Steward Workflow View Report

1. **Date:** 2026-07-25
2. **Branch:** `main`
3. **Starting HEAD:** `cf534ff6d7d13f651b2a25535598cc4af2811448`
4. **Verified M7 commit SHA:** `cf534ff6d7d13f651b2a25535598cc4af2811448` — `feat(w6): implement artifact library and case history`
5. **Pre-M8 Git status**
   - Branch `main` ahead of `origin/main` by 11 commits (after M7 commit)
   - Working tree clean of tracked M7 changes
   - Untracked only (left untouched): prior M4–M7 smoke helpers and pytest temp logs under `docs/temp/`
6. **Pre-M8 backend baseline result:** **610 passed**, **9 failed**, 1 deselected
7. **Exact pre-M8 backend failed node IDs**
   - `tests/test_case_api.py::test_export_html_does_not_call_retrieval`
   - `tests/test_report_export_security.py::test_html_preview_headers`
   - `tests/test_report_export_security.py::test_html_download_headers`
   - `tests/test_report_export_security.py::test_pdf_download_headers`
   - `tests/test_report_export_security.py::test_latest_version_selected`
   - `tests/test_report_export_security.py::test_historical_version_selected`
   - `tests/test_report_export_security.py::test_version_not_found`
   - `tests/test_report_export_security.py::test_no_report_versions`
   - `tests/test_report_export_security.py::test_export_never_calls_analysis_service`
   - Error class/message (all nine): `sqlalchemy.orm.exc.UnmappedInstanceError: Class 'types.SimpleNamespace' is not mapped`
8. **Pre-M8 frontend baseline result:** **109 passed / 3 failed** (112 tests). Failures were navigate/timeout flakes in create/analysis/grievance suites under parallel load (same class as M7). Isolated re-runs of those cases pass.
9. **Backend routes inspected**
   - `GET /cases/{case_uuid}/workflow`
   - `POST /cases/{case_uuid}/workflow/transitions`
   - `POST /cases/{case_uuid}/outcomes`
   - `POST /cases/saved/{case_uuid}/close`
   - `POST /cases/saved/{case_uuid}/settle`
   - `POST /cases/saved/{case_uuid}/archive`
   - `POST /cases/saved/{case_uuid}/reopen`
   - Supporting: workspace, timeline, history, memory, overview
10. **Schemas inspected**
    - `WorkflowStateView`, `WorkflowTransitionInput` (`case_workflow_schema.py`)
    - `RecordStepOutcomeRequest`, `CaseCloseRequest`, `CaseSettleRequest` (`case_memory_schema.py`)
    - `CaseStepOutcomeInput`, `OutcomeType`, progression models (`case_step_progression_schema.py`)
    - `ReopenCaseRequest` / responses (`saved_case_schema.py`)
    - Inline `UpdateStatusRequest` for archive body (`cases.py`)
11. **Services inspected**
    - `CaseWorkflowService`, `CaseStepProgressionService` / persistence, `SavedCaseService` close/settle/archive/reopen, `CaseMemoryService.record_outcome|record_close|record_settle|record_reopen`, domain event / timeline append paths
12. **Exact workflow response contract (`WorkflowStateView`)**
    - `case_uuid`, `explicit_state`, `current_grievance_step`, `case_status`, `inferred`, `inference_confidence` (`confirmed|inferred|unknown`), `permitted_next_states[]`, `updated_at`
13. **Exact transition request/response contract**
    - Request `WorkflowTransitionInput`: `to_state`, optional `reason`, `actor_id`, `grievance_step`, `allow_authorized_override`, `source_type`, `source_uuid`, `metadata`
    - Response: `WorkflowStateView`; invalid → HTTP 400 `CaseWorkflowError` detail
    - M8 UI does **not** expose generic transition buttons
14. **Exact outcome request/response contract**
    - Request `RecordStepOutcomeRequest`: `step_type?`, `outcome_type` (default `pending`), `decision_summary?`, `decision_date?`, `steward_notes?`, `close_case`, `close_step`, `appeal_to_next_step`, `decision_document_refs[]`, `resolution_type?`, `closed_by?`
    - Response envelope: `{ case_uuid, outcome, step, workflow, case_overview, workspace }`
    - Outcome route itself performs progression + workflow transitions (appeal/close/resolve) — frontend must not also call `/workflow/transitions` for the same action
15. **Exact valid outcome types:** `pending`, `resolved`, `granted`, `partially_granted`, `denied`, `withdrawn`, `settled`, `appealed`, `closed_no_appeal`, `unknown`
16. **Exact close contract (`CaseCloseRequest`):** required `outcome`, `resolution_type`; optional `outcome_notes`, `close_date`, `closed_by`, `final_grievance_step`, `supporting_document_refs[]` → `{ case, action_taken: "closed", message, closure, workspace }`
17. **Exact settle contract (`CaseSettleRequest`):** optional `settlement_notes`, `settlement_date`, `settlement_document_refs[]`, `settlement_amount`, `settled_by` → `{ case, action_taken: "settled", message, settlement, workspace }`
18. **Exact archive contract:** body optional; when sent must be `UpdateStatusRequest` with required `status: "archived"` and optional `reason`. Empty body also works. Response `{ case, action_taken: "archived", message, workspace }`
19. **Exact reopen contract:** `{ reason?, reopened_by?, source: "manual_ui"|"ai_command"|"system" }` → `ReopenCaseResponse` with same `case_uuid` + workspace
20. **Files created**
    - `frontend/src/api/types/workflow.ts`
    - `frontend/src/api/workflow.ts`
    - `frontend/src/features/workflow/workflowLabels.ts`
    - `frontend/src/features/cases/useCaseWorkflowQuery.ts`
    - `frontend/src/features/cases/useRecordOutcomeMutation.ts`
    - `frontend/src/features/cases/useCaseLifecycleMutations.ts`
    - `frontend/src/components/workflow/*` (panel, progression, outcome form, lifecycle, confirm dialog, CSS)
    - `frontend/src/routes/CaseWorkflowPage.tsx`
    - `frontend/src/test/workflowOutcomes.test.tsx`
    - `docs/temp/W6_M8_WORKFLOW_OUTCOMES_REPORT.md`
    - Untracked smoke helper (not for commit): `docs/temp/_m8_live_smoke.py`, `_m8_live_case_uuid.txt`
21. **Files modified**
    - `frontend/src/app/routes.tsx`
    - `frontend/src/components/workspace/WorkspaceSectionNav.tsx`
    - `frontend/src/components/workspace/CaseRail.tsx`
    - `frontend/src/features/cases/savedCaseActions.ts` (`workflowKeys`)
    - `frontend/src/test/savedCasesFixtures.ts`
    - `frontend/src/test/createCaseWorkspace.test.tsx`
    - `PROJECT_STATE.md`, `README.md`, `docs/ARCHITECTURE.md`, `docs/W6_UI_ARCHITECTURE.md`
22. **Dependencies changed:** none
23. **Route implementation**
    - `/cases/:caseUuid/workflow` under `CaseWorkspaceShell`
    - WorkspaceSectionNav adds **Workflow**
    - Conversation / Evidence / Analysis / Grievance / Artifacts & History retained
24. **Workflow overview behavior**
    - Case status, workflow state (readable + raw), current step, step status/open-closed, template availability, latest outcome, inference confidence, terminal flag, permitted next states
25. **Workflow visualization behavior**
    - Progression milestones: Case opened → Step 1 → Step 2 → Step 3 (workflow only) → Settled/Closed/Archived with Current/Completed/Upcoming/Unavailable text labels
26. **Outcome-form behavior**
    - Fields mirror `RecordStepOutcomeRequest` only; effect copy before submit; required summary; confirmation for close-step/close-case/appeal/settled; mutation `retry: false`; preserve values on failure; clear on success; no artifact creation
27. **Appeal behavior**
    - Explicit `appeal_to_next_step`; confirmation names case UUID; backend advances same case
28. **Same-case UUID verification**
    - Live Scenario A: appeal response `case_uuid` unchanged; Step 2 current
29. **Close-step behavior**
    - Deliberate checkbox on outcome form; confirmation when selected
30. **Close-case behavior**
    - Saved-case close route with required outcome + resolution_type; confirmation; history retained
31. **Settle behavior**
    - Saved-case settle route; optional notes/date/settled_by; confirmation; no settlement-document workflow
32. **Archive behavior**
    - Sends `{ status: "archived", reason }` when reason present, else empty body; confirmation; remains discoverable under `status=archived`
33. **Reopen behavior**
    - Reuses existing `reopenSavedCase` mutation; available when terminal; same UUID
34. **Step 3 workflow/form boundary**
    - Live Scenario E reached `step_3_analysis` / `step_3_appeal`; UI disclosure; no Generate Step 3 control
35. **Timeline/history integration**
    - Successful mutations invalidate workflow, workspace, saved cases, timeline, history (and artifact lists for safety)
36. **Query/state ownership**
    - TanStack Query `workflowKeys`; mutations for outcome/lifecycle; local state for form + confirm dialogs; caseUuid change clears form
37. **Case-switch isolation**
    - Form reset on caseUuid; query keys scoped; tests cover cross-case non-leak
38. **Accessibility**
    - Semantic headings, labeled fields, effect descriptions, keyboard confirm dialogs (Escape, focus restore), `role="status"` / `role="alert"` / `aria-busy`, reduced-motion CSS
39. **Tests added**
    - `frontend/src/test/workflowOutcomes.test.tsx` — 15 tests covering route/nav, restore, overview, form validation, success/failure, appeal same UUID, close/settle/archive confirmations, terminal+reopen, case switch, Step 3 boundary, Artifacts read-only, error normalization, M3–M7 nav intact
40. **Backend fixes:** none (frontend-only; archive body contract aligned to verified `UpdateStatusRequest`)
41. **Regression tests for backend fixes:** N/A
42. **Exact validation commands**
    ```bash
    .\venv\Scripts\python.exe -m pytest tests/test_case_architecture_hardening.py tests/test_case_step_progression_persistence.py tests/test_case_lifecycle_workspace_restoration.py tests/test_saved_case_service.py tests/test_saved_cases_api.py -q
    .\venv\Scripts\python.exe -m pytest tests/ -m "not integration" -q
    cd frontend
    npm run typecheck
    npm run lint
    npm run test:run
    npm run build
    npm audit
    .\venv\Scripts\python.exe docs/temp/_m8_live_smoke.py
    ```
43. **Focused backend test results:** **90 passed**
44. **Full backend test results:** **610 passed**, **9 failed** (same nine export-security / HTML export `UnmappedInstanceError`s)
45. **Comparison with pre-M8 backend baseline:** identical pass/fail set and error class — no new backend failures
46. **Frontend typecheck result:** PASS (`tsc -b`)
47. **Frontend lint result:** PASS (`oxlint src`)
48. **Frontend test result:** M8 suite **15/15 passed**. Full suite **124/127** under load (conversation/grievance navigate/timeout flakes); isolated re-runs of those cases pass. No M8-specific assertion failures.
49. **Frontend build result:** PASS (Vite production build)
50. **npm audit result:** Known React Router advisory GHSA-qwww-vcr4-c8h2 (high); fix path is `npm audit fix --force` → react-router-dom@7.11.0 (breaking). **Not force-fixed**.
51. **Live health result:** Direct `GET /health` → 200; Vite proxy `GET /api/health` → 200
52. **Live Vite proxy result:** All M8 routes exercised through `http://127.0.0.1:5173/api`
53. **Live Step 1 outcome result:** Outcome recorded; workflow advanced
54. **Live Step 1 → Step 2 appeal result:** `explicit_state=step_2_analysis`, `current_grievance_step=step_2_appeal`
55. **Same case_uuid result:** Confirmed on appeal response
56. **Live close result:** `action_taken=closed`; workflow `case_status=closed`
57. **Live reopen result:** `action_taken=reopened`; same case UUID
58. **Live settle result:** `action_taken=settled`; artifact count unchanged
59. **Live archive result:** `action_taken=archived`; discoverable via `GET /cases/saved?status=archived` and detail
60. **Live Step 3 boundary result:** Progression to `step_3_analysis` / `step_3_appeal`; form generation not exposed
61. **Refresh-restoration result:** Frontend tests remount `/workflow` and restore state; durable `GET /workflow` re-fetchable
62. **Case-switch isolation result:** Frontend test clears unsaved form and avoids prior-case workflow labels
63. **Verification workflow actions created no artifacts:** Scenario A artifact count unchanged across appeal
64. **Verification no Step 3 form was exposed:** No Generate Step 3 control; disclosure present for Step 3 workflow
65. **Verification no Sources API keys were exposed:** No Sources admin UI; tests assert no `GRIEVANCEHUB_API_KEY` / `sk-`
66. **Known limitations**
    - Pre-existing backend export-security `UnmappedInstanceError` failures remain outside M8 scope
    - Full frontend suite has intermittent navigate/timeout flakes under parallel load
    - Known React Router npm advisory unchanged
    - Direct FSM transition route intentionally not exposed as steward buttons
67. **M9 handoff items**
    - Sources research UI only through an approved server-side boundary (no browser API keys)
    - Keep workflow/outcome mutations out of Artifacts & History
    - Keep Step 3 grievance generation unsupported
68. **Final verdict:** **PASS WITH NON-BLOCKING FINDINGS**
    - M8 objective delivered and live-validated
    - Non-blocking: known React Router advisory; intermittent full-suite frontend flakes; pre-existing unrelated backend export-security failures
