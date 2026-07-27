# W6 M9 — Sources Research UI and Safe Server-Side Research Boundary Report

1. **Date:** 2026-07-25
2. **Branch:** `main`
3. **Starting HEAD:** `717ec65faea2230087bddfacd2af64621457d920`
4. **Verified M8 commit SHA:** `717ec65faea2230087bddfacd2af64621457d920` — `feat(w6): implement workflow outcomes and case lifecycle`
5. **Pre-M9 Git status**
   - Branch `main` ahead of `origin/main` by 12 commits
   - Working tree clean of tracked changes
   - Untracked only (left untouched): prior M4–M8 smoke helpers and pytest temp logs under `docs/temp/`
6. **Pre-M9 backend baseline:** **610 passed**, **9 failed**, 1 deselected
7. **Exact baseline failed backend node IDs**
   - `tests/test_case_api.py::test_export_html_does_not_call_retrieval`
   - `tests/test_report_export_security.py::test_html_preview_headers`
   - `tests/test_report_export_security.py::test_html_download_headers`
   - `tests/test_report_export_security.py::test_pdf_download_headers`
   - `tests/test_report_export_security.py::test_latest_version_selected`
   - `tests/test_report_export_security.py::test_historical_version_selected`
   - `tests/test_report_export_security.py::test_version_not_found`
   - `tests/test_report_export_security.py::test_no_report_versions`
   - `tests/test_report_export_security.py::test_export_never_calls_analysis_service`
8. **Exact baseline backend error class:** `sqlalchemy.orm.exc.UnmappedInstanceError: Class 'types.SimpleNamespace' is not mapped` (all nine)
9. **Pre-M9 frontend baseline:** **127 passed / 0 failed** (12 files)
10. **Existing `/sources` routes inventoried**
    - `GET /sources/` — list sources (read, API key)
    - `POST /sources/upload-pdf/` — ingest (admin)
    - `POST /sources/seed-official/` — seed (admin)
    - `GET /sources/embedded/` — embedding stats (read, API key)
    - `GET /sources/search/` — agent search (read, API key)
    - `GET /sources/ask/` — retrieval + generated answer (read, API key)
    - `GET /sources/report/` — analysis report helper (read, API key)
    - `POST /sources/` — create metadata (admin)
    - `POST /sources/{id}/sync|download|process` — mutate (admin)
    - `GET /sources/{id}/chunks/{chunk_index}` — chunk detail (read, API key)
11. **Read-only versus administrative classification**
    - Read-only: list, embedded, search, ask, report, chunk detail
    - Administrative/mutating: upload-pdf, seed-official, create, sync, download, process
12. **Authentication boundary inspected**
    - `GRIEVANCEHUB_API_KEY` / `GRIEVANCEHUB_ADMIN_API_KEY`
    - Headers: `Authorization: Bearer` or `X-API-Key`
    - External callers get global-corpus retrieval scope only
13. **Services inspected**
    - `KnowledgeRetrievalService.retrieve_with_agents` / `search_with_agents` / `search_all`
    - `RetrievalOrchestrator`, `ContractAgent`, `SupervisorManualAgent`
    - Source lifecycle/process/sync services (not exposed to browser research)
14. **Schemas inspected**
    - Retrieval dataclasses in `app/services/retrieval/models.py`
    - No prior dedicated browser research Pydantic schemas (added in M9)
15. **Exact browser-safe research routes added**
    - `GET /research/meta`
    - `GET /research/sources`
    - `GET /research/sources/{source_document_id}`
    - `POST /research/search`
    - `GET /research/passages/{source_chunk_id}`
16. **Architectural reason for route design**
    - Explicit research naming; not a generic `/sources` proxy
    - Workspace UI at `/cases/:caseUuid/research` for continuity; case UUID is not authentication
    - In-process service reuse avoids FastAPI calling itself with an API key
17. **Confirmation services are reused directly:** yes — `ResearchService` calls `KnowledgeRetrievalService.retrieve_with_agents` and ORM reads
18. **Exact search request contract (`ResearchSearchRequest`)**
    - `query` (1–2000 chars), `source_types[]`, `source_ids[]`, `limit` (1–24), `limit_per_source` (1–5), `offset` (0–200), `domain` (default `auto`)
19. **Exact search response contract (`ResearchSearchResponse`)**
    - `query`, `retrieval_status` (`ok|empty|failed|skipped|partial`), `retrieval_status_raw`, `partial`, `result_count`, `total_matched`, `limit`, `offset`, `limit_per_source`, `results[]`, `failures[]`, `authority_notice`
20. **Exact source-detail contract (`ResearchSourceDetail`)**
    - document id, canonical id, title, type/label, current/processing/indexed flags, official_page, version, content_type, chunk counts, authority_notice
21. **Exact passage-detail contract (`ResearchPassageDetail`)**
    - chunk id/index, source ids/title/type, page, section_label, passage_text, safe metadata, processing/indexed, authority_notice
22. **Exact supported filters:** orchestrator `ALLOWED_SOURCE_TYPES` — `ARBITRATION`, `CIM`, `CONTRACT`, `ELM`, `LMOU`, `SUPERVISOR_MANUAL`
23. **Exact pagination behavior:** search fetches up to `offset+limit` (capped at 24) then slices; source list uses SQL `offset`/`limit` (max list limit 100)
24. **Exact maximum result limits:** total 24, per-source 5, query 2000 chars, offset 200
25. **Exact retrieval-score fields exposed:** `final_relevance_score`, `normalized_score` (raw vector distance omitted)
26. **Exact source-type fields:** `source_type`, `source_type_label`
27. **Exact fields omitted from browser responses**
    - embeddings, `local_path`, `final_url`, `sha256`/`source_sha256`, organization ids, processing errors, raw provider payloads, stack traces, DB URLs, SQL, auth predicates, API keys
28. **Files created**
    - `app/api/routes/research.py`
    - `app/schemas/research_schema.py`
    - `app/services/research_service.py`
    - `tests/test_research_api.py`
    - `frontend/src/api/research.ts`
    - `frontend/src/api/types/research.ts`
    - `frontend/src/features/research/*`
    - `frontend/src/components/research/*`
    - `frontend/src/routes/CaseResearchPage.tsx`
    - `frontend/src/test/sourcesResearch.test.tsx`
    - `docs/temp/W6_M9_SOURCES_RESEARCH_REPORT.md`
    - Untracked smoke helpers (not committed): `docs/temp/_m9_live_smoke.py`, `_m9_live_case_uuid.txt`, baseline/log temps
29. **Files modified**
    - `app/main.py`
    - `frontend/src/app/routes.tsx`
    - `frontend/src/components/workspace/WorkspaceSectionNav.tsx`
    - `frontend/src/components/workspace/CaseRail.tsx`
    - `frontend/src/test/noApiKeys.test.tsx` (includes `features/` scan)
    - `PROJECT_STATE.md`, `README.md`, `docs/ARCHITECTURE.md`, `docs/W6_UI_ARCHITECTURE.md`
30. **Dependencies changed:** none
31. **Route implementation**
    - Frontend: `/cases/:caseUuid/research` under `CaseWorkspaceShell`
    - Nav: Sources Research (Conversation/Evidence/Analysis/Grievance/Artifacts/Workflow retained)
32. **Search behavior:** deliberate Search submit; URL-backed `q`, `sourceType`, `sourceId`, `limit`, `offset`, `chunk`; no auto-search on every keystroke; `retry: false`
33. **Result-list behavior:** rank, title, type label, location, excerpt, relevance %, provenance; keyboard-focusable buttons; empty vs failed distinct
34. **Result-detail behavior:** modal dialog, Escape-to-close, focus restore, read-only passage via `/research/passages/{id}`
35. **Authority-versus-evidence distinction:** prominent notice text tested (`authority-evidence-notice`)
36. **Optional Ask Sources decision:** **Excluded.** Legacy `GET /sources/ask/` exists, but implementing it would create a second chatbot via `AnalysisService.answer_question`, duplicate Conversation, and is not required by the M9 objective list. Documented as intentional exclusion.
37. **Query-key design:** `researchKeys = { all: ['sourceResearch'], meta, sources, source, search, passage }`
38. **URL-state design:** `q`, `sourceType`, `sourceId`, `limit`, `offset`, `chunk`
39. **Case-switch isolation:** draft/selection sync from URL; navigating to another case without params clears query/detail; authority results are global corpus (not case evidence)
40. **Request cancellation:** TanStack Query AbortSignal via `apiRequest`
41. **Duplicate-request prevention:** Search button disabled/`aria-busy` while fetching
42. **Security boundary behavior:** no API key required; browser-supplied keys ignored; `/sources` remains protected
43. **Confirmation no browser source key is required:** yes (tests + live)
44. **Confirmation protected `/sources` authentication remains:** yes (`401` without key in live smoke)
45. **Confirmation no source mutation controls exist:** yes (frontend tests)
46. **Confirmation embeddings are not serialized:** yes (schema forbid + tests + live dump checks)
47. **Confirmation internal paths are not serialized:** yes
48. **Accessibility:** headings, labeled controls, status/alert roles, dialog semantics, Escape close, focus restore, reduced-motion tokens retained
49. **Tests added**
    - Backend: `tests/test_research_api.py` (19 tests)
    - Frontend: `frontend/src/test/sourcesResearch.test.tsx` (11 tests)
    - Secret scan extended to `features/`
50. **Backend fixes:** none outside M9 research boundary
51. **Regression tests for backend fixes:** N/A
52. **Exact validation commands**
    - `python -m pytest tests/test_research_api.py tests/test_retrieval_api_auth.py -q`
    - `python -m pytest tests/ -m "not integration" -q`
    - `cd frontend && npm run typecheck && npm run lint && npm run test:run && npm run build && npm audit`
53. **Focused backend test result:** **33 passed**
54. **Full backend test result:** **629 passed**, **9 failed**, 1 deselected
55. **Comparison with pre-M9 backend baseline**
    - Passes: 610 → 629 (+19 research tests)
    - Failures: same nine export `UnmappedInstanceError` node IDs unchanged
56. **Frontend typecheck result:** pass
57. **Frontend lint result:** pass (`oxlint`)
58. **Frontend test result:** **138 passed / 0 failed** (13 files; +11 vs pre-M9 127)
59. **Frontend build result:** pass (`vite build`)
60. **npm audit result:** 2 high (`react-router` CSRF advisory); **did not** run `npm audit fix --force` (breaking). Pre-existing class of dependency advisory; not introduced by M9 code.
61. **Bundle secret-scan result**
    - Production JS: no `GRIEVANCEHUB_*`, no `postgresql://`, no long `sk-` secrets
    - `favicon.svg` contains substring `sk-` inside SVG `mask` attributes — false positive, not a credential
62. **Live health result:** `GET http://127.0.0.1:8000/health` → healthy
63. **Live Vite proxy result:** `GET http://127.0.0.1:5173/api/health` → healthy
64. **Live search result:** `POST /api/research/search` → `retrieval_status=ok`, results returned from local indexed corpus
65. **Live source-detail result:** passage + source detail 200; no `local_path`/`embedding`
66. **Live empty-result result:** query `zzzzzz-no-match-m9-xyz` → `retrieval_status=empty`
67. **Live failure result:** oversized `limit=999` → HTTP 422 (safe validation)
68. **Live pagination/result-limit result:** `limit=2` returned 2 results; server max 24 enforced
69. **Refresh-restoration result:** frontend tests cover URL restore; live page `GET /cases/{uuid}/research?q=overtime&sourceType=CONTRACT` returned 200 SPA shell
70. **Case-switch isolation result:** frontend test passes; research keys are corpus-scoped not case-message-scoped
71. **Verification no duplicate search request:** Search disabled while pending (frontend test)
72. **Verification no message was created:** research route does not call interaction/message create APIs (frontend + backend service mocks)
73. **Verification no Case Memory mutation occurred:** research service does not call CaseMemoryService
74. **Verification no artifact was created:** no artifact POST from research
75. **Verification no report version was created:** no report save/generate from research
76. **Verification no workflow mutation occurred:** no outcomes/transitions from research
77. **Verification no timeline/history event occurred:** research does not publish domain events
78. **Verification no source-document mutation occurred:** live smoke counts unchanged (`10` documents)
79. **Verification no source-chunk mutation occurred:** live smoke counts unchanged (`1902` chunks)
80. **Verification no evidence upload appeared as authority RAG:** UI notice + research queries only `SourceDocument`/`SourceChunk` authority tables
81. **Verification no Step 3 form was exposed:** no Step 3 generation control on research page
82. **Efficiency review:** deliberate submit; bounded limits; AbortSignal; no self-HTTP; no embedding serialization; search `retry: false`
83. **Elegance and maintainability review:** thin router, service reuse, allowlisted schemas, focused components, no second retrieval architecture
84. **Scalability review:** server caps, URL-backed filters, Query keys include result-affecting params, corpus growth assumed
85. **Security review:** interim browser-safe boundary only; `/sources` still API-key gated; secrets omitted; no production auth claim
86. **Known limitations**
    - Not production authentication (W9)
    - Browser research is intentionally open like other `/cases` routes until W9
    - Organization-scoped corpus browsing beyond global retrieval is not modeled
    - Ask Sources excluded
    - Nine pre-existing export test failures remain unfixed (out of scope)
    - `npm audit` react-router advisory remains (no `--force`)
87. **M10 handoff items**
    - Polish empty/error/print/a11y pass across all workspace sections
    - Broader keyboard/regression hooks
    - Do not expand research into admin/ingestion
88. **Final verdict:** **PASS WITH NON-BLOCKING FINDINGS**
    - Non-blocking: pre-existing nine export failures; react-router audit advisory; favicon `sk-` substring false positive
)
