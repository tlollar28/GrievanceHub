# W6 M7 — Artifact Library, Official Case Record, History, Comparison, and Jump-to-Context Report

1. **Date:** 2026-07-25
2. **Branch:** `main`
3. **Starting HEAD:** `77ae7396f06d4c154d5ec561b1e5ef50abb3abab`
4. **Verified M6 commit SHA:** `77ae7396f06d4c154d5ec561b1e5ef50abb3abab` — `feat(w6): implement grievance drafting and official forms`
5. **Pre-M7 Git status**
   - Branch `main` ahead of `origin/main` by 10 commits
   - Working tree clean of tracked M6 changes
   - Untracked only (deliberately excluded / left untouched): prior M4–M6 smoke helpers and pytest temp logs under `docs/temp/`

6. **Backend routes inspected**
   - `GET /cases/{case_uuid}/artifacts`
   - `GET /cases/{case_uuid}/artifacts/{artifact_uuid}`
   - `GET /cases/{case_uuid}/artifacts/{artifact_uuid}/pdf`
   - `POST /cases/{case_uuid}/artifacts/compare`
   - `GET /cases/saved/{case_uuid}/history`
   - `GET /cases/saved/{case_uuid}/timeline`
   - `GET /cases/{case_uuid}/history/{event_id}/context`
   - Supporting: `GET /cases/{case_uuid}/versions`, `GET /cases/{case_uuid}/workspace`
7. **Schemas and serializers inspected**
   - `CaseSavedArtifactSummary` / `Detail` / `ListResponse` / `CaseHistoryItem` / `CaseHistoryResponse` / `ArtifactCompareResponse` in `app/schemas/case_saved_artifact_schema.py`
   - `CompareArtifactsRequest` inline in `app/api/routes/cases.py`
   - `CaseHistoryContextResponse` / `HistoricalConversationWindow` in `app/schemas/case_history_context_schema.py`
   - `SavedCaseTimelineResponse` in `app/schemas/saved_case_schema.py`
   - `CaseTimelineEvent` in `app/schemas/case_step_progression_schema.py`
8. **Services inspected**
   - `CaseSavedArtifactService.list_artifacts` / `get_artifact` / `get_artifact_pdf_bytes` / `list_steward_case_history` / `compare_artifacts` / `compare_artifact_versions`
   - `SavedCaseService.get_case_timeline`
   - `CaseHistoryContextService.jump_to_context` (timeline events + artifact-only event IDs)
9. **Exact artifact list/detail/PDF contracts**
   - List: `{ case_uuid, count, artifacts[], groups: { analysis_reports, grievances, … } }`; optional `artifact_type=analysis_report|grievance_form`
   - Detail: summary fields + `content_json` + optional `pdf_download_path` (API path, not filesystem)
   - PDF: `application/pdf` bytes; 404 when no PDF snapshot / path missing
10. **Exact history contract**
    - `GET /cases/saved/{uuid}/history?order=oldest_first|newest_first&limit=1..200`
    - `{ case_uuid, label: "Official Case Record", count, order, events: CaseHistoryItem[] }`
11. **Exact timeline contract**
    - `GET /cases/saved/{uuid}/timeline?order=oldest_first|newest_first`
    - `{ case_uuid, order, count, events: CaseTimelineEvent[] }`
12. **Exact jump-to-context contract**
    - `GET /cases/{uuid}/history/{event_id}/context?conversation_window=2..20` (default 8)
    - Bounded read-only payload: `event_details`, `related_artifact`, `related_conversation`, workflow/decisions, previous/next, `mutates_current_memory: false`
13. **Exact compare request/response contract**
    - Request: `left_artifact_uuid` + `right_artifact_uuid` **or** `artifact_type` + `left_version` + `right_version`
    - Response: `{ case_uuid, artifact_type, left, right, changed_summary_keys, left_only_summary_keys, right_only_summary_keys, version_delta, retrieval_note }`
    - Incompatible types → HTTP 400 `"Compared artifacts must share the same artifact_type."`
14. **Files created**
    - `frontend/src/api/types/artifacts.ts`
    - `frontend/src/api/artifacts.ts`
    - `frontend/src/features/artifacts/artifactLibraryFilters.ts`
    - `frontend/src/features/cases/useCaseArtifactsQuery.ts`
    - `frontend/src/features/cases/useCaseArtifactQuery.ts`
    - `frontend/src/features/cases/useCaseHistoryQuery.ts`
    - `frontend/src/features/cases/useCaseTimelineQuery.ts`
    - `frontend/src/features/cases/useHistoryContextQuery.ts`
    - `frontend/src/features/cases/useCompareArtifactsMutation.ts`
    - `frontend/src/components/artifacts/*` (panel, library list, detail, PDF, compare, Official Case Record, timeline, context dialog, CSS)
    - `frontend/src/routes/CaseArtifactsPage.tsx`
    - `frontend/src/test/artifactsHistory.test.tsx`
    - `docs/temp/W6_M7_ARTIFACTS_HISTORY_REPORT.md`
    - Untracked smoke helpers (not for commit): `docs/temp/_m7_live_smoke.py`, `_m7_live_case_uuid.txt`
15. **Files modified**
    - `frontend/src/app/routes.tsx`
    - `frontend/src/components/workspace/WorkspaceSectionNav.tsx`
    - `frontend/src/components/workspace/CaseRail.tsx`
    - `frontend/src/features/cases/savedCaseActions.ts` (`artifactKeys`)
    - `frontend/src/test/savedCasesFixtures.ts`
    - `frontend/src/test/createCaseWorkspace.test.tsx`
    - `PROJECT_STATE.md`, `README.md`, `docs/ARCHITECTURE.md`, `docs/W6_UI_ARCHITECTURE.md`
16. **Dependencies changed:** none
17. **Route implementation**
    - `/cases/:caseUuid/artifacts` under `CaseWorkspaceShell`
    - WorkspaceSectionNav adds **Artifacts & History**
    - Conversation / Evidence / Analysis / Grievance retained
    - Direct navigation and refresh restore durable Query data
18. **Artifact Library behavior**
    - Lists `analysis_report` and `grievance_form`
    - Filter by type + sort newest/oldest via URL params (`type`, `sort`, `artifact`)
    - Metadata: type, short UUID, version, template/step when present, saved_at, PDF status, print readiness, validation when present, title
    - Empty / loading / error states with `role="status"` / `role="alert"` / `aria-busy`
19. **Artifact detail behavior**
    - Read-only; no edit/generate/save controls in the detail surface
    - Analysis: saved summary / quick assessment fields from `key_summary` / `content_json`
    - Grievance: labeled `field_values` from `content_json`
    - Never renders `stored_path`
20. **PDF behavior**
    - Uses `GET .../artifacts/{uuid}/pdf` via `apiBinaryRequest`
    - Blob URL preview + download; revoke on close / artifact or case change
    - Pending disables preview; failed/404 show clear alerts
21. **Official Case Record behavior**
    - Uses saved-case history API with sort control
    - Shows timestamp, type, title, details, related artifact/version, record class
    - Jump-to-context + open related artifact actions
22. **Timeline behavior**
    - Broader timeline via saved-case timeline API with sort control
    - Read-only; no M8 outcome controls
    - Case Rail recent timeline slice retained
23. **Jump-to-context behavior**
    - Accessible modal dialog; Escape closes; focus restores
    - Loads bounded context; discloses read-only / non-mutating nature
24. **Comparison behavior**
    - Two-select checkboxes; same artifact cannot occupy both slots
    - Client blocks incompatible types; backend 400 also surfaced
    - Displays changed / left-only / right-only summary keys and version delta
    - Creates no artifact
25. **Query/state ownership**
    - TanStack Query via `artifactKeys` for list/detail/history/timeline/context
    - Compare via mutation (not durable official state)
    - Local state: compare selection, context dialog open
26. **Case-switch isolation**
    - Clears compare selection and context dialog on `caseUuid` change
    - Query keys scoped by caseUuid; PDF blob URLs revoked on artifact/case change
27. **Accessibility**
    - Semantic headings, labeled filters, keyboard lists/controls, visible focus
    - `role="status"` / `role="alert"` / `aria-busy`, dialog name, iframe titles, SR type/status text, reduced-motion CSS
28. **Tests added**
    - `frontend/src/test/artifactsHistory.test.tsx` covering route/nav, refresh restore, analysis+grievance render, filters, read-only detail, no `stored_path`, PDF binary route + failure, history order, timeline, jump-to-context read-only, compare compatible/same/incompatible, case-switch isolation, API errors/empty/loading a11y, no M8/Step3/Sources keys, M3–M6 nav intact
29. **Exact validation commands**
    ```bash
    .\venv\Scripts\python.exe -m pytest tests/test_case_save_and_print_artifacts.py tests/test_steward_artifact_workflow.py tests/test_case_architecture_hardening.py tests/test_saved_cases_api.py tests/test_case_lifecycle_workspace_restoration.py -q
    .\venv\Scripts\python.exe -m pytest tests/ -m "not integration" -q
    cd frontend
    npm run typecheck
    npm run lint
    npm run test:run
    npm run build
    npm audit
    .\venv\Scripts\python.exe docs/temp/_m7_live_smoke.py
    ```
30. **Backend test results**
    - Focused artifact/history/context/compare/lifecycle suites: **78 passed**
    - Full non-integration suite: **610 passed**, **9 failed** in pre-existing export-security / `test_case_api` HTML export tests (`UnmappedInstanceError: SimpleNamespace is not mapped`) — **no backend code changed in M7**; failures are unrelated to Artifacts & History UI
31. **Frontend typecheck result:** PASS (`tsc -b`)
32. **Frontend lint result:** PASS (`oxlint src`)
33. **Frontend test result:** M7 suite **13/13 passed**. Full suite intermittently **109/112** under load (evidence/grievance navigate/timeout flakes); re-run of those cases in isolation **PASS**. No M7-specific assertion failures.
34. **Frontend build result:** PASS (Vite production build)
35. **npm audit result:** Known React Router advisory GHSA-qwww-vcr4-c8h2 (high); fix path is `npm audit fix --force` → react-router-dom@7.11.0 (breaking). **Not force-fixed** (same known W6 advisory path).
36. **Live health result:** Direct `GET /health` → 200 healthy; Vite proxy `GET /api/health` → 200 healthy
37. **Live Vite proxy result:** Artifact/history/timeline/context/compare/PDF all exercised through `http://127.0.0.1:5173/api`
38. **Live artifact list result:** 3 artifacts; types `analysis_report` + `grievance_form`
39. **Live artifact detail result:** Analysis detail title/PDF status returned; UI contract does not surface `stored_path`
40. **Live PDF result:** 200 `application/pdf` (~35 KB) via proxy
41. **Live history result:** Official Case Record count 6, label present
42. **Live timeline result:** count 6
43. **Live context result:** event context loaded; `mutates_current_memory=false`
44. **Live comparison result:** compatible analysis pair 200 with changed keys; incompatible analysis/grievance 400
45. **Refresh restoration result:** Frontend tests remount route and restore list/history/timeline; live durable APIs re-fetchable after smoke case creation
46. **Verification browsing created no artifact:** DB artifact count unchanged (3 → 3) after list/detail/PDF/history/timeline/context/compare
47. **Verification no M8 workflow UI was added:** No close/settle/archive/appeal controls; disclosure states outcomes are out of scope
48. **Verification no Step 3 form was exposed:** No Step 3 generation UI; official generation remains Step 1/2 only
49. **Verification no Sources API keys were exposed:** No Sources admin UI; smoke payloads contain no `GRIEVANCEHUB_API_KEY` / `sk-`
50. **Known limitations**
    - Artifact-synthesized history rows may set `context_path` to the artifact path; UI always calls `/history/{event_id}/context` using `event_id` (supported for artifact-only IDs)
    - Comparison presents backend `key_summary` diffs only (no invented semantic field diffs)
    - Full frontend suite has intermittent navigate/timeout flakes under parallel load
    - Pre-existing backend export-security test failures remain outside M7 scope
    - Known React Router npm advisory unchanged
51. **M8 handoff items**
    - Workflow outcome controls (close / settle / archive / appeal) using existing progression/outcome APIs
    - Do not fold outcome mutations into Artifacts & History browsing
    - Keep Step 3 grievance generation unsupported
    - Keep Sources administration outside browser / no API keys in frontend
52. **Final verdict:** **PASS WITH NON-BLOCKING FINDINGS**
    - M7 objective delivered and live-validated
    - Non-blocking: known React Router advisory; intermittent full-suite frontend flakes; pre-existing unrelated backend export-security failures
