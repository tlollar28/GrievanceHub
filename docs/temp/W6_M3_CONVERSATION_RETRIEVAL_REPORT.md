# W6 M3 — Conversation and Retrieval Report

1. **Date:** 2026-07-24
2. **Branch:** `main`
3. **Starting HEAD:** `6d254c0a32854267c30840a715936b1ca2655977`
4. **Verified M2 commit SHA:** `6d254c0a32854267c30840a715936b1ca2655977` — `feat(w6): implement case creation and workspace restore`
5. **Pre-M3 Git status:**
   - Branch `main` ahead of `origin/main` by 5 commits
   - Working tree clean of tracked M2 changes
   - Untracked only (deliberately excluded): `docs/temp/_explain_embedding.py`, `docs/temp/_pytest_run1.txt` … `_pytest_run3b.txt`

6. **Backend routes inspected**
   - `app/api/routes/cases.py`: `GET /{case_uuid}/messages`, `POST /{case_uuid}/interactions`
   - Legacy (not used by M3 UI): `POST /{case_uuid}/messages`, `POST /{case_uuid}/followups`
7. **Pydantic schemas inspected**
   - `CaseInteractionRequest`, `CaseInteractionResponse`, `CaseInteractionMessageSummary`, `RetrievalStatus`, `CaseMemoryUpdateStatus` in `app/schemas/case_workspace_action_schema.py`
   - `FollowUpCitation` in `app/schemas/follow_up_schema.py` (runtime citation shape; OpenAPI types interaction citations as `list[dict]`)
8. **OpenAPI paths verified** (via `app.main:app.openapi()`)
   - `GET,POST /cases/{case_uuid}/messages`
   - `POST /cases/{case_uuid}/interactions` with `response_model=CaseInteractionResponse`
   - Messages GET response schema empty in OpenAPI (no `response_model`) — **CaseService.list_case_messages dict is source of truth**
9. **Existing backend tests inspected / run**
   - `tests/test_case_ai_first_chat_workspace.py`
   - `tests/test_chat_source_retrieval.py`
   - `tests/test_case_lifecycle_workspace_restoration.py::test_list_case_messages_is_paginated_and_case_scoped`
   - `tests/test_case_lifecycle_workspace_restoration.py::test_list_case_messages_rejects_missing_case`
   - Result: **36 passed**

10. **Exact Messages contract**
    - `GET /cases/{case_uuid}/messages`
    - Query: `limit` (default 50), `offset` (default 0), `order` (`oldest_first` | `newest_first`, default `oldest_first`)
    - Max limit: 100 (`CONVERSATION_HISTORY_MAX_LIMIT`)
    - Response: `{ case_uuid, count, total, limit, offset, order, has_more, messages: [{ id, role, content, metadata, created_at }] }`
    - 404: `{ detail: "Case not found" }`
11. **Exact Interaction request contract**
    - `POST /cases/{case_uuid}/interactions`
    - Body (`CaseInteractionRequest`): `message?`, `clarification?`, `fact_updates?`, `upload_refs?` (default `[]`), `source` (`manual_ui` | `ai_command` | `system`, default `manual_ui`), `pinned_report_version?` (int ≥ 1)
    - M3 sends: `{ message, source: "manual_ui" }` only
12. **Exact Interaction response contract**
    - `CaseInteractionResponse` (OpenAPI complete): `case_uuid`, `status`, `message`, `workspace_current`, `user_message`, `assistant_message`, `ai_answer`, `answer_type`, `citations`, `disclosures`, `facts_needed`, `retrieval_status`, `retrieval_error`, `case_memory_update_status`, report version ids/numbers, `analysis_update`, `available_actions`, `generate_grievance_available`, `missing_prerequisites`, `timeline_events`, `grievance_draft_created`, `generation_snapshot_persisted`, `export_attempted`, `analysis_versions_created`
    - Soft failures may return HTTP 200 with `status` in `{ prerequisites_not_met, invalid_request, case_not_found }` (route maps `case_not_found` to HTTP 404)
    - Completed chat returns persisted `user_message` + `assistant_message`
13. **Exact retrieval-status contract**
    - Literal: `ok` | `empty` | `failed` | `skipped` (nullable on response)
    - `retrieval_error: bool` accompanies failed retrieval when set by follow-up grounding
14. **Exact citation contract**
    - Runtime `FollowUpCitation`: `document_type`, `document_name`, `article_or_section`, `page` (int|null), `quote`, `grounded`, `grounding_provenance` (`retrieved_passage` | `saved_report_authority` | `ungrounded`), optional grounding indices
    - Also persisted on assistant `metadata.citations` for history restore
15. **Disclosures and facts-needed contract**
    - `disclosures: list[str]`, `facts_needed: list[str]` on interaction response and assistant message metadata
16. **Case Memory update behavior**
    - `case_memory_update_status`: `updated` | `projection_failed` | `failed` | `unknown` | `not_applicable`
    - Frontend invalidates `caseWorkspace` only when status is `updated`
17. **Verification that normal chat creates no reports/grievances/artifacts**
    - Service asserts `analysis_versions_created=0`, no `generate_report_version`, no grievance draft, empty `timeline_events` for ordinary chat
    - Backend tests cover this; live smoke: `analysis_versions_created=0`, `grievance_draft_created=false`, workspace `analysis_report_count=0`, `official_grievance_count=0`, `official_artifacts=[]`
18. **Architecture corrections discovered**
    - Messages OpenAPI response schema empty — documented; service dict used
    - Interaction citations OpenAPI typed as free-form objects — FollowUpCitation used as verified shape
    - Closed/terminal cases return completed envelope with `status=prerequisites_not_met` (HTTP 200) rather than always 4xx
    - M3 does not send `upload_refs` (Evidence M4); docs updated accordingly
    - No backend redesign; no speculative backend changes

19. **Files created**
    - `frontend/src/api/types/messages.ts`
    - `frontend/src/api/types/interactions.ts`
    - `frontend/src/api/messages.ts`
    - `frontend/src/api/interactions.ts`
    - `frontend/src/features/cases/messageTurn.ts`
    - `frontend/src/features/cases/useCaseMessagesQuery.ts`
    - `frontend/src/features/cases/useSubmitInteractionMutation.ts`
    - `frontend/src/components/conversation/*` (panel, list, bubble, composer, retrieval/disclosure/facts, citation chip/detail/panel + CSS)
    - `frontend/src/routes/CaseConversationPage.tsx`
    - `frontend/src/test/conversation.test.tsx`
    - `docs/temp/W6_M3_CONVERSATION_RETRIEVAL_REPORT.md`
20. **Files modified**
    - `frontend/src/app/routes.tsx`
    - `frontend/src/routes/CaseWorkspacePage.tsx`
    - `frontend/src/components/workspace/CaseWorkspaceShell.tsx` (+ CSS)
    - `frontend/src/components/workspace/KnownFactsEditor.tsx`
    - `frontend/src/features/cases/savedCaseActions.ts`
    - `frontend/src/test/savedCasesFixtures.ts`
    - `frontend/src/test/createCaseWorkspace.test.tsx`
    - `frontend/src/test/savedCases.test.tsx`
    - `PROJECT_STATE.md`, `README.md`, `docs/ARCHITECTURE.md`, `docs/W6_UI_ARCHITECTURE.md`
21. **Dependencies added or changed:** none intentional. `npm install` rewrote root lockfile metadata (caret→exact pins); that churn was reverted so the M3 commit keeps the prior lockfile.

22. **Routing implementation:** Nested under `CaseWorkspacePage` layout — index redirects to `conversation`; `/cases/:caseUuid/conversation` renders `CaseConversationPage` via `Outlet` context (workspace fetched once in parent)
23. **Message-history implementation:** `listCaseMessages` + `useCaseMessagesQuery` key `["caseMessages","list",caseUuid,{limit,offset,order}]`, AbortSignal, default oldest_first limit 50, skeleton / empty / error+Retry
24. **Conversation-panel implementation:** Steward vs assistant bubbles; generated-text styling; research panel for citation detail; professional case workspace (not consumer chatbot)
25. **Composer implementation:** Labelled textarea; Enter send / Shift+Enter newline; blocks empty; helper copy that conversation does not create analysis/grievance; disabled while pending; terminal-case read-only note
26. **Interaction mutation and reconciliation:** Pending steward bubble → `POST .../interactions` → merge persisted messages by id into Query cache; soft non-`completed` statuses treated as failure; AbortController + caseUuid guard for switch isolation
27. **Retrieval-state implementation:** Banners for `ok` / `empty` / `failed` / `skipped` + unknown fallback; in-flight “Researching authorities…” / secondary copy after 2s
28. **Citation implementation:** Chips under assistant turn; detail panel shows supplied fields only; ungrounded warning; no fake page/section placeholders
29. **Disclosure implementation:** Per-turn `role="status"` banners from verified disclosures
30. **Facts-needed implementation:** Accessible list with “Open Known Facts editor” focusing `#known-facts-editor` (no silent fact mutation)
31. **Query-cache strategy:** Messages authoritative in TanStack Query; draft/pending/selection local; invalidate workspace only on memory `updated`; mutations never auto-retry
32. **Case-switch isolation:** Reset local state on `caseUuid` change; abort in-flight interaction; ignore late responses when case no longer matches
33. **Accessibility:** semantic conversation region; `role="log"`; labelled composer/send; chip keyboard; focus to research panel; return focus on clear; `aria-busy`; polite live region for completed answers (not full transcript); `role="alert"` for failed turns; reduced-motion via tokens; collapsible research panel

34. **Tests added:** `conversation.test.tsx` (15 cases) covering restore, empty/loading/error, ordering, composer, request shape, duplicate send, reconcile/no-dupe, failure+retry, case-switch isolation, retrieval statuses, citations/ungrounded/missing fields, disclosures, facts focus, memory invalidation rules, no auto-send, no analysis/grievance/artifact/sources calls, Enter/Shift+Enter; M0–M2 suites updated for nested conversation route
35. **Exact commands run**
    ```bash
    cd frontend
    npm install
    npm run typecheck
    npm run lint
    npm run test:run
    npm run build
    npm audit
    # repo root
    .\venv\Scripts\python.exe -m pytest tests/test_case_ai_first_chat_workspace.py \
      tests/test_chat_source_retrieval.py \
      tests/test_case_lifecycle_workspace_restoration.py::test_list_case_messages_is_paginated_and_case_scoped \
      tests/test_case_lifecycle_workspace_restoration.py::test_list_case_messages_rejects_missing_case -q
    # live: uvicorn + vite + proxy smoke
    ```
36. **Frontend validation results**
    - Typecheck: PASS (exit 0)
    - Lint: PASS (exit 0)
    - Unit tests: PASS — **7 files, 47 tests, 0 failed**
    - Production build: PASS (exit 0)
37. **Backend test results:** PASS — 36 passed
38. **Direct FastAPI health:** `GET http://127.0.0.1:8000/health` → 200 `{"status":"healthy","service":"GrievanceHub"}`
39. **Vite proxy result:** `GET http://127.0.0.1:5173/api/health` → 200 same body
40. **Live interaction result (initial M3 smoke):** created case titled `W6 M3 local conversation smoke test` (`dbc043b3-8b4b-4c8e-99f2-8ba8c0d26782`); `POST .../interactions` with that same non-authority string → `status=completed`, `retrieval_status=empty`, citations=`[]`, `analysis_versions_created=0`. This was an invalid RAG smoke query, not a corpus/retrieval outage (see reopen section below).
41. **Live citation result (initial M3 smoke):** NOT demonstrated — empty retrieval from the non-authority smoke string. Citation UI remained covered by frontend unit tests only until reopen validation.
42. **Refresh restoration result (initial M3 smoke):** Second messages GET returned total=2 (`user,assistant`) for the same case UUID
43. **Case-switch isolation result:** Second case messages total=0; UUID distinct — PASS
44. **Verification that no artifact/report/grievance was created:** Live workspace `report_versions=[]`, `official_artifacts=[]`; interaction `grievance_draft_created=false`, `analysis_versions_created=0`
45. **Final npm audit result:** exit 1 — 2 high (React Router RSC CSRF advisory GHSA-qwww-vcr4-c8h2); **did not** run `npm audit fix --force`
46. **React Router advisory status:** Unchanged classification from M0–M2 — Data Mode SPA only; no RSC / Framework Mode / unstable RSC APIs introduced
47. **Documentation updates:** `PROJECT_STATE.md`, `README.md`, `docs/ARCHITECTURE.md`, `docs/W6_UI_ARCHITECTURE.md`, this report
48. **Files deliberately excluded:** `docs/temp/_explain_embedding.py`, `_pytest_run1.txt` … `_pytest_run3b.txt`, live reopen helper artifacts (`_m3_live_*`)
49. **Known non-blocking limitations**
    - Messages OpenAPI response schema gap
    - Interaction citation OpenAPI typed as free dicts
    - React Router advisory remains (accepted; no force fix)
    - `upload_refs` attachment UI deferred to M4
    - `article_or_section` may be empty on some CIM chunks even when page is present (page shown when available)
50. **M4 handoff items**
    - Evidence upload UI and asset listing
    - Optional `upload_refs` in conversation composer when architecture requires
    - Do not start analysis/grievance from Evidence milestone
51. **Initial M3 commit verdict:** **PASS WITH NON-BLOCKING FINDINGS** (later superseded for retrieval by reopen validation below)
    - Non-blocking at commit time: React Router advisory; OpenAPI schema gaps; live citation path not yet proven with an authority query

**Initial commit message:** `feat(w6): implement case conversation and retrieval`

---

## Live retrieval reopen validation (post-M3)

52. **Reopen date:** 2026-07-24
53. **M4 status:** Not started
54. **Root cause of prior `retrieval_status=empty` / `citations=[]`**
    - The initial live smoke sent the interaction message `W6 M3 local conversation smoke test` (same string used as the create-case `question`).
    - That string has no indexed authority match; the orchestrator correctly returned empty results.
    - Indexed corpus was present and queryable. Direct retrieval with the known-good backend-test query succeeds.
    - Not a frontend citation bug, not an empty corpus, not a Vite proxy failure.
55. **Indexed source inventory (live DB at reopen)**
    - CONTRACT `NPMHU National Agreement 2022-2025` (id=1): 325 embedded chunks (`processing_status=pending`, admitted via ContractAgent legacy pre-W5 arm)
    - CIM `NPMHU-USPS Contract Interpretation Manual v6` (id=6): 1002 embedded chunks
    - ELM: 42 embedded; SUPERVISOR_MANUAL (EL-921 / EL-801 / F-21): 49+101+383 embedded (`processing_status=completed`)
    - Total embedded chunks: **1902**
    - Known authority passage used: CIM Article 10 / page 137 leave-cancellation Q&A (also CONTRACT Article 10.5 / page 44 advance-commitment language present)
56. **Known-good source used:** `NPMHU-USPS Contract Interpretation Manual v6` (CIM)
57. **Exact question:** `Can management cancel approved leave?`
    - Same question used throughout backend chat/retrieval tests (`tests/test_chat_source_retrieval.py`, `tests/test_case_api.py`, `tests/test_follow_up_chat.py`, etc.)
58. **Direct backend retrieval result**
    - `FollowUpChatService.retrieve_indexed_source_passages(...)` → `retrieval_status=ok`, `passage_count=4`, top hit CIM p.137, provenance `retrieved_passage`
59. **Direct backend / Vite-proxy interaction result**
    - Case `e2f86d84-66fc-4a17-be92-644939c09335`
    - `POST /api/cases/{uuid}/interactions` via Vite proxy → `status=completed`, `retrieval_status=ok`, **citation_count=1**, `analysis_versions_created=0`, `grievance_draft_created=false`
60. **Live UI retrieval result** (Playwright against real Vite UI + proxy; no frontend mocks)
    - Case `4c5543a3-20ca-43cd-b697-3eda953a3f06`
    - Composer sent the known-good question through `/cases/{uuid}/conversation`
    - Interaction response: `retrieval_status=ok`, citation_count=1
    - UI showed retrieval banner: “matched authorities available for this answer.”
    - Citation chip `CIM` opened Research panel
61. **Citation count:** **1**
62. **Citation document and location**
    - Document: `NPMHU-USPS Contract Interpretation Manual v6`
    - Type: `CIM`
    - Page: **137**
    - Article/section field: empty string on this chunk (page available and shown)
63. **Grounded status:** `grounded=true`
64. **Grounding provenance:** `retrieved_passage`
65. **Grounded source quote:** `management should give reasonable consideration to requests for annual leave cancellation, unless otherwise provided in the Local Memorandum of Understanding.`
66. **Refresh-persistence result:** PASS
    - Browser reload restored assistant turn with citation chip
    - Research panel again showed document, page 137, grounded status, `retrieved_passage`, and source excerpt
    - `GET .../messages` assistant `metadata.citations` retained 1 citation with the same fields
67. **No report / grievance / artifact created:** confirmed
    - Interaction: `analysis_versions_created=0`, `grievance_draft_created=false`
    - Workspace: `report_versions=[]`, `official_artifacts=[]`, `latest_report=null`
    - DB: `case_report_versions` count=0 for the UI case; messages=2
68. **Code changes:** none required — empty result was caused by the prior non-authority smoke query
69. **Exact tests / commands run during reopen**
    ```bash
    # inventory + leave-passage probes via SessionLocal SQL
    # direct retrieval:
    .\venv\Scripts\python.exe -c "FollowUpChatService.retrieve_indexed_source_passages(...)"
    # health + proxy interaction with known-good query
    # Playwright live UI script against http://127.0.0.1:5173 (real proxy)
    ```
    - FastAPI health: 200
    - Vite `/api/health` proxy: 200
    - Direct retrieval: `ok` / 4 passages
    - Proxy interaction: `ok` / 1 citation
    - Live UI + refresh: PASS (`pass=true`)
    - No defect found → no new backend regression test added; no frontend suite re-run required for a code fix
70. **Revised final verdict:** **PASS**
    - Live RAG + citation rendering demonstrated through the Vite UI/proxy
    - Remaining non-blocking items: React Router advisory; OpenAPI schema gaps; optional empty `article_or_section` when page is present
71. **Follow-up commit message (report correction only):** `fix(w6): verify live retrieval and citations`
