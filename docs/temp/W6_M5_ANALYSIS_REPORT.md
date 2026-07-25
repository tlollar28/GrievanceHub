# W6 M5 — Analysis Generate, Preview, Save, and Print Report

1. **Date:** 2026-07-24
2. **Branch:** `main`
3. **Starting HEAD:** `bb389990c2b90cbfd104688dc0baa7f51e6e2439`
4. **Verified M4 commit SHA:** `bb389990c2b90cbfd104688dc0baa7f51e6e2439` — `feat(w6): implement case evidence uploads`
5. **Pre-M5 Git status**
   - Branch `main` ahead of `origin/main` by 8 commits
   - Working tree clean of tracked M4 changes
   - Untracked only (deliberately excluded): `docs/temp/_explain_embedding.py`, `_pytest_run1.txt` … `_pytest_run3b.txt`, plus M4 smoke helpers (`_m4_live_smoke.py`, `w6_m4_evidence_smoke.txt`, `_m4_live_case_uuid.txt`)

6. **Report routes inspected**
   - `POST /cases/{case_uuid}/reports/generate`
   - `POST /cases/{case_uuid}/reports/save-and-print`
   - `GET /cases/{case_uuid}/versions`
   - `GET /cases/{case_uuid}/versions/{version_number}`
   - `GET /cases/{case_uuid}/export/preview|html|pdf`
   - `GET /cases/{case_uuid}/versions/{n}/export/preview|html|pdf`
   - `GET /cases/{case_uuid}/artifacts/{artifact_uuid}/pdf`
7. **Schemas inspected**
   - `SaveAndPrintReportRequest`, `SaveAndPrintResponse`, `CaseSavedArtifactSummary` in `app/schemas/case_saved_artifact_schema.py`
   - `WorkspaceActionResponse` / preview fields in `app/schemas/case_workspace_action_schema.py`
   - `GrievanceHubReport` / `REPORT_SECTIONS` in `app/schemas/report_schema.py`
   - Inline `RegenerateReportRequest` for generate body in `app/api/routes/cases.py`
8. **OpenAPI paths verified**
   - Generate, save-and-print, versions list/detail, and export paths present
   - Report response shapes incomplete in OpenAPI — **Pydantic / service serialization is source of truth**
9. **Services/export code inspected**
   - `CaseWorkspaceActionService.generate_analysis_report`
   - `CaseService.build_analysis_report_preview` / `persist_report_version_from_preview`
   - `CaseSavedArtifactService.save_and_print_report`
   - `ReportExportService` + HTML/PDF generators; `exports.py` official-vs-working-draft gate
10. **Existing backend tests inspected / run**
    - `tests/test_steward_artifact_workflow.py`
    - `tests/test_case_save_and_print_artifacts.py`
    - `tests/test_case_lifecycle_workspace_restoration.py::test_official_print_requires_save_without_working_draft_flag`
    - `tests/test_report_html_export.py`, `tests/test_report_pdf_export.py`
    - New: `tests/test_indexed_source_types_helper.py`, `tests/test_report_export_load_version_refresh.py`

11. **Exact Generate contract**
    - `POST /cases/{uuid}/reports/generate` body `{ limit_per_source?: int }` default `8`
    - Response: `WorkspaceActionResponse` dump + `review_mode="read_only"`, `editable=false`, `persisted=false`, `report_version=null`, `preview` (= `analysis_preview`)
    - 404 case_not_found; 400 prerequisites_not_met (closed/settled/archived)
12. **Exact temporary-preview behavior**
    - Preview dict: `temporary`, `persisted=false`, `review_mode`, `editable`, `suggested_version_number_if_saved`, `report_data`, authorities/gaps/summary
    - No `CaseReportVersion`, no artifact, no Official Case Record event
13. **Exact Save-and-Print contract**
    - Single endpoint `POST .../reports/save-and-print`
    - Body: `preview`, optional `title`/`saved_by`/`grievance_step`, `idempotency_key` (max 120), `prepare_pdf` (default true)
    - M5 UI: Save → `prepare_pdf:false`; Save and Print → `prepare_pdf:true`
14. **Exact version-list contract**
    - `{ case_uuid, count, versions: [{ id, version_number, trigger_message_id, created_at, retrieval_gaps, source_coverage_audit, report_summary }] }`
15. **Exact version-detail contract**
    - List fields + `report_data`, `ranked_authorities`, `issue_analysis`, `evidence_items`
16. **Exact HTML/PDF export contracts**
    - HTML preview/download: `text/html`, `Cache-Control: no-store`
    - PDF: `application/pdf` + `X-GrievanceHub-Print-Mode: working_draft_preview | official_saved_artifact`
17. **Official-versus-working-draft rules**
    - Official PDF requires prior Save and Print → else **409**
    - `working_draft=true` only for non-official preview
18. **Idempotency behavior**
    - Matching `case_uuid` + `idempotency_key` → `status=idempotent_replay`, no new version/commit
19. **PDF-failure behavior**
    - Artifact + version persist; `status=saved_pdf_failed`; `pdf_status=failed`; recoverable via export
20. **Verification Generate creates no version/artifact**
    - Live DB after Generate: versions=0, artifacts=0, analysis_events=0
21. **Verification Cancel creates no version/artifact/event**
    - Cancel is client-only discard; live DB unchanged after Generate without Save

22. **Architecture corrections / narrow backend fixes**
    1. **Python 3.14 abstract `BaseProvider.__new__`:** `_get_indexed_source_types` used `BaseProvider.__new__(BaseProvider)`, which raises on Python 3.14 and blocked live Generate. Fixed by making `_authorization_predicates` a `@staticmethod` and calling it without instantiation. Regression: `tests/test_indexed_source_types_helper.py`.
    2. **Save-and-Print PDF stale relationship:** after `persist_report_version_from_preview(..., commit=False)`, export `_load_version` read a stale `case.report_versions` collection and raised `ReportVersionNotFoundError` → `saved_pdf_failed`. Fixed by `db.expire(case, ["report_versions"])` before reload. Regression: `tests/test_report_export_load_version_refresh.py`. Re-verified live: `status=saved`, `pdf_status=ready`.
    - OpenAPI report response schemas remain incomplete — documented; Pydantic used.

23. **Files created**
    - `frontend/src/api/types/reports.ts`
    - `frontend/src/api/reports.ts`
    - `frontend/src/features/cases/useAnalysisVersionsQuery.ts`
    - `frontend/src/features/cases/useAnalysisVersionQuery.ts`
    - `frontend/src/features/cases/useGenerateAnalysisMutation.ts`
    - `frontend/src/features/cases/useSaveAnalysisMutation.ts`
    - `frontend/src/components/analysis/*` (panel, preview, report view, versions, export/save actions, authority/limitations/citation validation + CSS)
    - `frontend/src/routes/CaseAnalysisPage.tsx`
    - `frontend/src/test/analysis.test.tsx`
    - `tests/test_indexed_source_types_helper.py`
    - `tests/test_report_export_load_version_refresh.py`
    - `docs/temp/W6_M5_ANALYSIS_REPORT.md`
24. **Files modified**
    - `frontend/src/api/client.ts` (`apiBinaryRequest`)
    - `frontend/src/features/cases/savedCaseActions.ts` (`analysisKeys`)
    - `frontend/src/app/routes.tsx`
    - `frontend/src/components/workspace/WorkspaceSectionNav.tsx`
    - `frontend/src/test/savedCasesFixtures.ts`
    - `app/services/providers/base_provider.py`
    - `app/services/knowledge_retrieval_service.py`
    - `app/services/report_export_service.py`
    - `PROJECT_STATE.md`, `README.md`, `docs/ARCHITECTURE.md`, `docs/W6_UI_ARCHITECTURE.md`
25. **Dependencies changed:** none
26. **Routing:** `/cases/:caseUuid/analysis` under `CaseWorkspaceShell`; WorkspaceSectionNav adds Analysis
27. **Generate implementation:** explicit button; no auto-generate; pending disables duplicates; preview stored only in component state
28. **Temporary preview:** unsaved banner; read-only taxonomy; not written into TanStack Query as a saved version
29. **Cancel behavior:** confirmation dialog; clears preview; no Save API; no version/artifact/event
30. **Save behavior:** `prepare_pdf:false`; stable idempotency key on retry; clears preview only after persisted success; invalidates versions + workspace
31. **Save and Print behavior:** `prepare_pdf:true`; same endpoint; handles `saved_pdf_failed` as saved-with-warning
32. **Version list/detail:** loading/empty/error+Retry; URL `?version=N`; official badge; temporary previews never listed
33. **Export/preview behavior:** HTML iframe; working-draft vs official PDF labels; blob URL revoke; 409 steward language
34. **Query/state ownership:** TanStack for versions/detail/workspace; ephemeral for preview/dirty/idempotency; mutations `retry:false`
35. **Case isolation:** preview cleared on `caseUuid` change; version queries keyed by case
36. **Accessibility:** labelled Generate/Save/Cancel; `aria-busy`; `role=alert`/`status`; heading structure; keyboard version list; confirm dialog; focus return; reduced-motion via tokens

37. **Tests added:** `analysis.test.tsx` (16) covering restore/direct/refresh, loading/empty/error, generate contract/no-auto/duplicate, temporary banner/taxonomy/missing fields, cancel/no-save, case-switch clear, Save/Save-and-Print `prepare_pdf`, idempotency retry, `saved_pdf_failed`/replay, export/409/blob revoke, no grievance UI, conversation/evidence do not generate; M0–M4 suites still pass (77 total frontend tests)
38. **Commands run**
    ```bash
    cd frontend
    npm install   # already satisfied; no dependency changes
    npm run typecheck
    npm run lint
    npm run test:run
    npm run build
    npm audit
    # repo root
    .\venv\Scripts\python.exe -m pytest tests/test_steward_artifact_workflow.py \
      tests/test_case_save_and_print_artifacts.py \
      tests/test_case_lifecycle_workspace_restoration.py::test_official_print_requires_save_without_working_draft_flag \
      tests/test_report_html_export.py tests/test_report_pdf_export.py \
      tests/test_indexed_source_types_helper.py \
      tests/test_report_export_load_version_refresh.py -q
    # live: uvicorn + vite + docs/temp/_m5_live_smoke.py via proxy
    ```
39. **Frontend validation**
    - Typecheck: PASS
    - Lint: PASS
    - Unit tests: PASS — **9 files, 77 tests, 0 failed**
    - Production build: PASS
40. **Backend validation:** PASS — focused suites green (40 initially; + regression helpers → 23 in focused re-run including new tests; full listed suites green)
41. **Direct health:** `GET http://127.0.0.1:8000/health` → 200 `{"status":"healthy","service":"GrievanceHub"}`
42. **Proxy result:** `GET http://127.0.0.1:5173/api/health` → 200 same body
43. **Live Generate result:** case `56aa6843-67b3-48b5-ba23-e402e1a8ce1a` (`W6 M5 local analysis smoke test`); `persisted=false`, `report_version=null`, preview present; DB versions/artifacts/events = 0
44. **Live Cancel result:** no Save call; DB unchanged after Generate
45. **Live Save result:** `status=saved`, version 1, `pdf_status=pending`, analysis_events=1
46. **Live Save-and-Print result:** after export-refresh fix recheck on case `9cc62924-71b5-4d6c-98b6-90a87e97bb94`: `status=saved`, `pdf_status=ready`, `print_ready=true`, artifact PDF 200
47. **Live version restoration:** `GET .../versions` count=2 (smoke) / 1 (recheck); detail 200
48. **Live export result:** HTML preview 200 (~17KB); working-draft PDF 200 with `working_draft_preview`; official artifact PDF 200 after fix
49. **Verification Conversation remains artifact-free:** interaction `analysis_versions_created=0`, `grievance_draft_created=false`
50. **Verification no grievance was created:** `grievance_artifacts=0` throughout
51. **npm audit:** exit 1 — 2 high (React Router RSC CSRF advisory GHSA-qwww-vcr4-c8h2); **did not** run `npm audit fix --force`
52. **React Router advisory status:** Unchanged — Data Mode SPA only; no RSC / Framework Mode / unstable RSC APIs introduced
53. **Documentation:** `PROJECT_STATE.md`, `README.md`, `docs/ARCHITECTURE.md`, `docs/W6_UI_ARCHITECTURE.md`, this report
54. **Excluded files:** prior temp pytest/embedding notes; M4 smoke helpers; M5 smoke helpers `docs/temp/_m5_live_smoke.py`, `docs/temp/_m5_live_case_uuid.txt`; runtime uploads/PDFs; `frontend/dist`; node_modules
55. **Known limitations**
    - OpenAPI report response schemas remain incomplete
    - React Router advisory remains (accepted; no force fix)
    - Temporary preview is not restored after browser refresh (by design; no backend temporary-draft resource)
    - First live Save-and-Print before the export-refresh fix returned `saved_pdf_failed`; fixed and re-verified
56. **M6 handoff items**
    - Grievance generate / editable draft / Save and Print
    - Do not start general artifact library or Official Case Record browsing beyond analysis artifacts already exposed
57. **Final verdict:** **PASS WITH NON-BLOCKING FINDINGS**
    - Non-blocking: React Router advisory; OpenAPI schema gap; temporary preview intentionally non-durable across refresh

**Commit message:** `feat(w6): implement analysis preview and saving`
