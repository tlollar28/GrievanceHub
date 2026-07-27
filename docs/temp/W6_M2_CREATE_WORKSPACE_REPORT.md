# W6 M2 — Create Case and Workspace Restoration Report

1. **Date:** 2026-07-24
2. **Branch:** `main`
3. **Starting HEAD:** `38f4343b7ffc9dd30092e75e22a10d06a545475e`
4. **M1 commit verification:** Present at starting HEAD — `feat(w6): implement saved cases workspace entry`
5. **Pre-M2 Git status:**
   - Branch `main` ahead of `origin/main` by 4 commits
   - Working tree clean of tracked M1 changes
   - Untracked only (deliberately excluded): `docs/temp/_explain_embedding.py`, `docs/temp/_pytest_run1.txt` … `_pytest_run3b.txt`

6. **Backend routes inspected**
   - `app/api/routes/cases.py`: `POST /`, `GET /{case_uuid}/workspace`, `PATCH /{case_uuid}/facts`, `GET /{case_uuid}/overview`, `GET /{case_uuid}/memory`, `GET /{case_uuid}/workflow`
7. **Pydantic / request schemas inspected**
   - Inline `CreateCaseRequest`, `UpdateFactsRequest` in `cases.py`
   - `CaseOverview`, `CaseMemoryResponse` in `app/schemas/case_memory_schema.py`
   - `WorkflowStateView` in `app/schemas/case_workflow_schema.py`
   - Workspace aggregate built in `CaseService.get_case_workspace` (dict, no `response_model`)
8. **OpenAPI paths verified** (via `app.main:app.openapi()`)
   - `POST,GET /cases/`
   - `GET /cases/{case_uuid}/workspace`
   - `PATCH /cases/{case_uuid}/facts`
   - `GET /cases/{case_uuid}/memory`
   - `GET /cases/{case_uuid}/overview`
   - `GET /cases/{case_uuid}/workflow`
   - Schemas present: `CreateCaseRequest`, `UpdateFactsRequest`
   - `CaseOverview` / `CaseMemoryResponse` / `WorkflowStateView` absent from OpenAPI components because those routes omit or partially omit response models / return dicts — **service + Pydantic source of truth used**
9. **Existing backend tests inspected / run**
   - `tests/test_case_api.py`
   - `tests/test_case_lifecycle_workspace_restoration.py`
   - `tests/test_saved_case_service.py`
   - `tests/test_case_memory.py`
   - Result: **73 passed**

10. **Exact Create Case contract**
    - `POST /cases/`
    - Request: `{ question: string (min 1), user_name?, local_number?, known_facts?, limit_per_source?=8 }`
    - `limit_per_source` accepted by Pydantic but **not passed** to `CaseService.create_case` — omitted from steward form
    - Response: `{ case: <case detail/summary + messages/report fields>, report_version: null }`
    - No auto-analysis; no first chat interaction
11. **Exact Workspace contract**
    - `GET /cases/{case_uuid}/workspace`
    - Path param: `case_uuid`
    - 404: `{ detail: "Case not found" }`
    - Response source: `CaseService.get_case_workspace` dict (no `response_model`)
    - Key fields used by M2: `case_uuid`, `title`, `user_name`, `local_number`, `initial_question`, `known_facts`, `status`, `message_count`, `messages: []`, `workspace_summary`, `case_overview`, `case_memory`, `timeline`, `step_progression`, `uploaded_assets` / `assets`, `official_artifacts`
12. **Exact Facts contract**
    - `PATCH /cases/{case_uuid}/facts`
    - Request: `{ known_facts: dict }` (full replace)
    - Response: case list summary via `serialize_case_list_summary` (not workspace)
13. **Overview / Memory / Workflow contracts**
    - Separate routes exist and work
    - M2 uses embedded `case_overview` + `case_memory` from workspace (no duplicate fetches)
    - Workflow summary taken from `workspace_summary` / `step_progression` / overview `explicit_workflow_state`
14. **Architecture corrections discovered**
    - Create response is **not** a workspace payload
    - Workspace overview field is `case_overview` (not `overview`)
    - `limit_per_source` on create is unused by service
    - Docs updated accordingly; no backend redesign

15. **Files created**
    - `frontend/src/api/types/cases.ts`
    - `frontend/src/api/types/workspace.ts`
    - `frontend/src/api/cases.ts`
    - `frontend/src/api/workspace.ts`
    - `frontend/src/features/cases/useCreateCaseMutation.ts`
    - `frontend/src/features/cases/useUpdateFactsMutation.ts`
    - `frontend/src/features/cases/knownFactsForm.ts`
    - `frontend/src/components/workspace/*` (shell, header, rail, overview, memory, facts + CSS)
    - `frontend/src/routes/CaseWorkspacePage.tsx` (+ CSS)
    - `frontend/src/routes/NewCasePage.module.css`
    - `frontend/src/test/createCaseWorkspace.test.tsx`
    - `docs/temp/W6_M2_CREATE_WORKSPACE_REPORT.md`
16. **Files modified**
    - `frontend/src/api/savedCases.ts`, `frontend/src/api/types/savedCases.ts`
    - `frontend/src/features/cases/savedCaseActions.ts`, `useCaseWorkspaceQuery.ts`
    - `frontend/src/app/routes.tsx`
    - `frontend/src/routes/NewCasePage.tsx`
    - `frontend/src/test/savedCasesFixtures.ts`
    - `PROJECT_STATE.md`, `README.md`, `docs/ARCHITECTURE.md`, `docs/W6_UI_ARCHITECTURE.md`
17. **Files deleted**
    - `frontend/src/routes/CaseWorkspaceEntryPage.tsx` (+ CSS) — replaced by `CaseWorkspacePage`
18. **Dependencies added or changed:** none (lockfile unchanged)

19. **Create Case implementation:** Functional `/cases/new` form → `POST /cases/` with verified fields; loading/duplicate-submit prevention; invalidate Saved Cases; navigate to `/cases/{uuid}`
20. **Workspace restoration:** `useCaseWorkspaceQuery` key `["caseWorkspace", caseUuid]`, AbortSignal, `refetchOnMount: 'always'`, uses cache when present then authoritative GET
21. **CaseWorkspaceShell:** Header + left rail + main region (M3 conversation reserved note only)
22. **Case context:** Title, status badge+text, step, UUID copy, last activity, terminal-status note
23. **Case Rail:** Identity, overview, facts editor, workflow, timeline slice, uploads, optional artifact summary, Case Memory
24. **Overview:** From `case_overview` (+ initial question fallback); honest empty state
25. **Case Memory:** From embedded `case_memory`; not labeled as transcript; honest empty/unavailable state
26. **Facts:** Editable key/value → `PATCH .../facts`; Save/Cancel; dirty indicator; no optimistic official display; invalidate workspace on success; preserve edits on failure
27. **Query-cache strategy:** Create invalidates `savedCases` lists; open/reopen still seeds workspace; facts invalidate `caseWorkspace`; no Zustand
28. **Routing:** Same routes retained; `/cases/:caseUuid` hosts shell; focus moves to workspace heading on case change
29. **Accessibility:** semantic regions, status text, copy control, form errors + focus, `aria-busy`, `role="alert"` / `role="status"`, reduced-motion tokens, responsive rail toggle

30. **Tests added:** `createCaseWorkspace.test.tsx` (15 cases) covering create validation/request/nav/cache/error, workspace load/not-found/retry/header/rail/empty/facts/isolation, no interactions calls; M0/M1 suite retained
31. **Exact commands run**
    ```bash
    cd frontend
    npm run typecheck
    npm run lint
    npm run test:run
    npm run build
    npm audit
    # repo root
    .\venv\Scripts\python.exe -m pytest tests/test_case_api.py \
      tests/test_case_lifecycle_workspace_restoration.py \
      tests/test_saved_case_service.py tests/test_case_memory.py -q
    # live: uvicorn + vite + proxy smoke (create/workspace/facts/health)
    ```
32. **Frontend validation results**
    - Typecheck: PASS (exit 0)
    - Lint: PASS (exit 0)
    - Unit tests: PASS — **6 files, 32 tests, 0 failed**
    - Production build: PASS (exit 0)
33. **Backend test results:** PASS — 73 passed
34. **Direct FastAPI health:** `GET http://127.0.0.1:8000/health` → 200 `{"status":"healthy","service":"GrievanceHub"}`
35. **Vite proxy:** `GET http://127.0.0.1:5173/api/health` → 200 same body; Saved Cases list → 200
36. **Create Case live-smoke:** Created `W6 M2 local workspace smoke test` via proxy `POST /api/cases/` → 200, `report_version: null`
37. **Direct workspace navigation / restore:** `GET /api/cases/{uuid}/workspace` → 200 with overview/memory/facts; `messages` empty
38. **Refresh restoration:** Second workspace GET returned same UUID/question
39. **Facts live-smoke:** `PATCH /api/cases/{uuid}/facts` → 200; workspace reflected updated facts
40. **Final npm audit result:** exit 1 — 2 high (React Router RSC CSRF advisory GHSA-qwww-vcr4-c8h2); **did not** run `npm audit fix --force`
41. **React Router advisory status:** Unchanged classification from M0/M1 — Data Mode SPA only; no RSC / Framework Mode / unstable RSC APIs introduced
42. **Documentation updates:** `PROJECT_STATE.md`, `README.md`, `docs/ARCHITECTURE.md`, `docs/W6_UI_ARCHITECTURE.md`, this report
43. **Files deliberately excluded:** `docs/temp/_explain_embedding.py`, `_pytest_run1.txt` … `_pytest_run3b.txt`
44. **Known non-blocking limitations**
    - OpenAPI incomplete for workspace/overview/memory response models
    - Create request model includes unused `limit_per_source`
    - React Router advisory remains (accepted; no force fix)
    - Artifact/upload sections are summary-only from workspace payload (no M4–M7 features)
45. **M3 handoff items**
    - Conversation panel + `GET .../messages` + `POST .../interactions`
    - Citations / retrieval UI
    - Nested case routes under shell
46. **Final verdict before commit:** **PASS WITH NON-BLOCKING FINDINGS**
    - Non-blocking: React Router advisory; OpenAPI response-schema gaps; unused create `limit_per_source`

**Commit message:** `feat(w6): implement case creation and workspace restore`
