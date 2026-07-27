# W6 M4 — Evidence Uploads and Case Asset References Report

1. **Date:** 2026-07-24
2. **Branch:** `main`
3. **Starting HEAD:** `43f72869825322a97dfa3db8bf8e6e39efcacd0d`
4. **Verified M3 commits**
   - `4828eee` — `feat(w6): implement case conversation and retrieval`
   - `43f7286` — `fix(w6): verify live retrieval and citations`
5. **Pre-M4 Git status**
   - Branch `main` ahead of `origin/main` by 7 commits
   - Working tree clean of tracked M3 changes
   - Untracked only (deliberately excluded): `docs/temp/_explain_embedding.py`, `_pytest_run1.txt` … `_pytest_run3b.txt`

6. **Asset routes inspected**
   - `app/api/routes/cases.py`: `GET /{case_uuid}/assets`, `POST /{case_uuid}/assets`, `GET /{case_uuid}/assets/{asset_uuid}`
   - Interaction route already used by M3: `POST /{case_uuid}/interactions` with `upload_refs`
7. **Schemas inspected**
   - `CaseAssetMetadata`, `CaseAssetListResponse`, `CaseAssetUploadResponse`, `CaseAssetCategory` in `app/schemas/case_asset_schema.py`
   - `CaseInteractionRequest.upload_refs: list[str]` in `app/schemas/case_workspace_action_schema.py`
8. **OpenAPI verification**
   - Paths present for list/upload/detail assets
   - Multipart body: required `file`; `category` enum default `uploaded_document`; optional `uploaded_by`; `source` default `api`
   - Asset response schemas empty in OpenAPI — **Pydantic `model_dump` / service serialization is source of truth**
9. **Storage implementation inspected**
   - `app/services/case_asset_service.py` + `CASE_ASSET_DIR` / `CASE_ASSET_MAX_UPLOAD_BYTES` in `app/config.py`
   - Local filesystem under `data/case_assets/{case_uuid}/`; SHA-256 computed server-side; timeline + Case Memory evidence recording on upload
10. **Existing tests inspected / run**
    - `tests/test_case_asset_foundation.py`
    - `tests/test_case_ai_first_chat_workspace.py::test_referenced_asset_uuids_resolve`
    - `tests/test_chat_source_retrieval.py` (includes cross-case `upload_refs` rejection)
    - Result: **36 passed**

11. **Exact Asset List contract**
    - `GET /cases/{case_uuid}/assets`
    - Optional query: `category` (`CaseAssetCategory`)
    - Response: `{ case_uuid, count, assets: CaseAssetMetadata[] }`
    - Active assets only by default; ordered by `created_at` asc
    - 404: `{ detail: "Case not found" }`
12. **Exact Asset Upload contract**
    - `POST /cases/{case_uuid}/assets` multipart/form-data
    - Fields: `file` (required), `category` (default `uploaded_document`), `uploaded_by` (optional), `source` (default `api`; UI sends `manual_ui`)
    - Response: `{ case_uuid, asset: CaseAssetMetadata, message }`
    - 400 placeholder category / validation; 404 missing case
13. **Exact Asset Detail contract**
    - `GET /cases/{case_uuid}/assets/{asset_uuid}` → `CaseAssetMetadata` (no file body)
    - 404 case or asset not found
14. **Supported categories**
    - Executable upload: `uploaded_document` only
    - Placeholder (not uploadable via public create): `generated_report`, `generated_grievance`, `future_export`, `future_attachment`
15. **File validation**
    - Empty content rejected (`Uploaded file is empty.`)
    - Max size `25 * 1024 * 1024` bytes
    - No MIME whitelist
    - Filename sanitized; duplicates allowed (new UUID each upload)
16. **Exact `upload_refs` contract**
    - `CaseInteractionRequest.upload_refs: list[str]` (default `[]`)
    - Preferred values: case asset UUIDs for the same case
    - Cross-case UUID refs resolve as rejected (`asset_not_on_case`) and are not loaded
    - Multiple refs supported
17. **Uploaded-evidence processing behavior**
    - Persisted as case asset + local bytes + SHA-256
    - Timeline event `files_uploaded` (or management-response variant)
    - Case Memory `record_evidence`
    - Continuity / AI context uses metadata with `content_embedded: false`
    - Not chunked, embedded, or admitted to the authority corpus
18. **Verification uploads are not authority-corpus RAG**
    - Live DB: zero `source_documents` matching smoke filename/path
    - UI disclosure states case-context attachment only
19. **Verification reference interaction creates no report/grievance/artifact**
    - Live interaction: `analysis_versions_created=0`, `grievance_draft_created=false`
    - Workspace: `report_versions=[]`, `official_artifacts=[]`
    - DB: `case_report_versions` count=0 for smoke case
20. **Architecture corrections**
    - OpenAPI asset response schemas empty — documented; Pydantic used
    - API `source` default is `api`; steward UI must send `manual_ui`
    - `stored_path` is returned by API but must not be rendered
    - No backend redesign; no speculative backend changes

21. **Files created**
    - `frontend/src/api/types/assets.ts`
    - `frontend/src/api/assets.ts`
    - `frontend/src/features/cases/assetValidation.ts`
    - `frontend/src/features/cases/useCaseAssetsQuery.ts`
    - `frontend/src/features/cases/useCaseAssetQuery.ts`
    - `frontend/src/features/cases/useUploadAssetMutation.ts`
    - `frontend/src/components/evidence/*` (panel, list, upload, detail + CSS)
    - `frontend/src/components/conversation/AttachmentPicker.tsx`
    - `frontend/src/components/workspace/WorkspaceSectionNav.tsx` (+ CSS)
    - `frontend/src/routes/CaseEvidencePage.tsx`
    - `frontend/src/test/evidence.test.tsx`
    - `docs/temp/W6_M4_EVIDENCE_REPORT.md`
22. **Files modified**
    - `frontend/src/api/client.ts` (multipart helper; no manual Content-Type)
    - `frontend/src/features/cases/savedCaseActions.ts` (`assetKeys`)
    - `frontend/src/components/conversation/ConversationComposer.tsx`
    - `frontend/src/components/conversation/ConversationPanel.tsx` (+ CSS)
    - `frontend/src/components/workspace/CaseWorkspaceShell.tsx`
    - `frontend/src/components/workspace/CaseRail.tsx`
    - `frontend/src/app/routes.tsx`
    - `frontend/src/test/savedCasesFixtures.ts`
    - `PROJECT_STATE.md`, `README.md`, `docs/ARCHITECTURE.md`, `docs/W6_UI_ARCHITECTURE.md`
23. **Dependencies changed:** none. Playwright remains untracked leftover from M3 validation and is not a package.json dependency.
24. **Routing:** `/cases/:caseUuid/evidence` nested under `CaseWorkspacePage`; WorkspaceSectionNav for Conversation/Evidence; Case Rail “Open Evidence” link
25. **Asset list:** loading skeleton, empty, error+Retry; table semantics; safe fields only
26. **Upload panel:** labelled file input; explicit Submit; selected name/size; category `uploaded_document`; `source=manual_ui`; optional `uploaded_by` from workspace steward name; cancel/reset; client empty/size validation; no auto-upload on select
27. **Multipart client behavior:** `apiMultipartRequest` omits Content-Type so the browser sets the boundary; JSON `apiRequest` unchanged
28. **Asset detail:** safe metadata expansion; never renders `stored_path` / `stored_filename`
29. **Attachment selector:** current-case assets only; multi-select; remove-before-send; count announcement; disclosure; focus return on close
30. **Interaction integration:** message-only unchanged; with selection sends `upload_refs: string[]`; success clears refs; failure preserves refs; case switch clears refs
31. **Query cache:** `assetKeys` list/detail; upload mutations never retry; invalidate only affected case assets + that case workspace
32. **Case isolation:** caseUuid resets selection/detail; picker lists only current-case assets; abort upload on cancel
33. **Accessibility:** labelled file input; keyboard picker; `aria-busy`; `role="alert"` / `role="status"`; table caption; named remove buttons; focus indicators; reduced-motion via tokens

34. **Tests:** `evidence.test.tsx` (14) covering restore/direct nav/refresh, loading/empty/error, safe fields/no paths, validation, multipart fields/Content-Type, duplicate submit, disclosure, picker/`upload_refs`/multi/remove/failure preserve/case switch, message-only, no sources/analysis/grievance/artifact calls; M0–M3 suites still pass
35. **Commands run**
    ```bash
    cd frontend
    npm install   # already satisfied; no dependency changes
    npm run typecheck
    npm run lint
    npm run test:run
    npm run build
    npm audit
    # repo root
    .\venv\Scripts\python.exe -m pytest tests/test_case_asset_foundation.py \
      tests/test_case_ai_first_chat_workspace.py::test_referenced_asset_uuids_resolve \
      tests/test_chat_source_retrieval.py -q
    # live: uvicorn + vite + docs/temp/_m4_live_smoke.py via proxy
    ```
36. **Frontend validation results**
    - Typecheck: PASS
    - Lint: PASS
    - Unit tests: PASS — **8 files, 61 tests, 0 failed**
    - Production build: PASS
37. **Backend test results:** PASS — 36 passed
38. **Direct FastAPI health:** `GET http://127.0.0.1:8000/health` → 200 `{"status":"healthy","service":"GrievanceHub"}`
39. **Proxy result:** `GET http://127.0.0.1:5173/api/health` → 200 same body
40. **Live Evidence result:** case `cc08ae04-2e9b-492b-81b1-9bb7d6b923bb` (question/title smoke label `W6 M4 local evidence smoke test`); empty list then upload+list via Vite proxy
41. **Live upload result:** asset `7f4c8b0c-b5fe-4900-988c-d3197b637382`, filename `w6_m4_evidence_smoke.txt`, `source=manual_ui`, category `uploaded_document`
42. **Live asset detail:** filename/sha256/mime/size returned; `stored_path` present in API payload (UI never displays it)
43. **Refresh result:** second list GET returned count=1 for the same case UUID
44. **Live interaction-reference result:** `status=completed`, `upload_refs` + `case_asset_uuids` persisted on user message metadata; `retrieval_status=empty` expected for non-authority smoke text (not a RAG outage)
45. **No artifact/report/grievance verification:** interaction flags + workspace arrays + DB report count all zero
46. **No corpus-ingestion verification:** zero SourceDocument name/path hits for smoke filename
47. **Case-switch result:** second case asset count=0
48. **npm audit:** exit 1 — 2 high (React Router RSC CSRF advisory GHSA-qwww-vcr4-c8h2); **did not** run `npm audit fix --force`
49. **React Router advisory status:** Unchanged from M0–M3 — Data Mode SPA only; no RSC / Framework Mode / unstable RSC APIs introduced
50. **Documentation:** `PROJECT_STATE.md`, `README.md`, `docs/ARCHITECTURE.md`, `docs/W6_UI_ARCHITECTURE.md`, this report
51. **Excluded files:** prior temp pytest/embedding notes; live helpers `docs/temp/_m4_live_smoke.py`, `docs/temp/w6_m4_evidence_smoke.txt`, `docs/temp/_m4_live_case_uuid.txt`; untracked Playwright leftovers under `frontend/node_modules` from M3
52. **Known limitations**
    - OpenAPI asset response schemas remain empty
    - React Router advisory remains (accepted; no force fix)
    - No download/preview/delete/replace actions (not required for M4; no download API used)
    - Interaction smoke used a non-authority message → `retrieval_status=empty` (expected)
53. **M5 handoff items**
    - Analysis generate/preview/save UI
    - Do not start grievance/artifact from Analysis milestone unless that milestone’s scope requires it
54. **Final verdict:** **PASS WITH NON-BLOCKING FINDINGS**
    - Non-blocking: React Router advisory; OpenAPI asset response schema gap; optional empty retrieval on non-authority smoke interaction text

**Commit message:** `feat(w6): implement case evidence uploads`
