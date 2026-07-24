# W6 M1 — Saved Cases Report

1. **Date:** 2026-07-24
2. **Branch:** `main`
3. **Pre-implementation HEAD:** `9d7c463` (`feat(w6): establish frontend foundations`)
4. **Pre-implementation Git status:**
   - Branch `main` ahead of `origin/main` by 3 commits
   - Untracked only: `docs/temp/_explain_embedding.py`, `docs/temp/_pytest_run*.txt`
   - Working tree otherwise clean; M0 confirmed complete

5. **API-contract verification (required before coding)**

| Source | Result |
|--------|--------|
| FastAPI routes `app/api/routes/cases.py` | `GET /cases/saved`, `GET /cases/saved/{uuid}`, `POST .../open`, `POST .../reopen`, `GET /cases/{uuid}/workspace` present |
| Pydantic `app/schemas/saved_case_schema.py` | Mirrored into `frontend/src/api/types/savedCases.ts` |
| OpenAPI (via `app.main:app.openapi()`) | Query enums verified: status, step (`step_1_initial` \| `step_2_appeal` \| `step_3_appeal`), search, order, limit (1–100), offset; open/reopen request bodies use `OpenCaseRequest` / `ReopenCaseRequest` |
| Response models in OpenAPI | Empty `{}` schemas because routes return `.model_dump()` without `response_model=` — **Pydantic models remain source of truth for response shapes** |

6. **Verified contract corrections vs older docs**

| Topic | Docs / helper said | Verified backend |
|-------|--------------------|------------------|
| Step 3 filter | `step_3_arbitration` in older UI contract | `step_3_appeal` (`StepLevel`) |
| Status filter | sometimes omitted settled/archived | includes `settled`, `archived` |
| Click → reopen | Python client only checks `closed` | `open_case` returns `closed_requires_reopen` for `closed` \| `settled` \| `archived`; `/ui` shell matches terminal set |
| Pagination | optional in some notes | `limit`/`offset`/`total`/`has_more` on `SavedCaseListResponse` |

Frontend click resolution uses the terminal set (`closed`/`settled`/`archived`) and still handles `closed_requires_reopen` with an explicit reopen confirm.

7. **Files created**

- `frontend/src/api/types/savedCases.ts`
- `frontend/src/api/savedCases.ts`
- `frontend/src/features/cases/*` (actions, filters, query/mutation hooks)
- `frontend/src/components/cases/*` (panel, table, filters, pagination, status badge)
- `frontend/src/routes/CaseWorkspaceEntryPage.tsx` (+ CSS module)
- `frontend/src/test/savedCases.test.tsx`, `frontend/src/test/savedCasesFixtures.ts`
- `docs/temp/W6_M1_SAVED_CASES_REPORT.md`

8. **Files modified**

- `frontend/src/app/routes.tsx`
- `frontend/src/routes/DashboardPage.tsx`, `CasesPage.tsx`
- `frontend/src/components/TopBar.tsx` (+ CSS — global case search)
- `docs/W6_UI_ARCHITECTURE.md`, `docs/ARCHITECTURE.md`, `docs/saved_cases_ui_contract.md`
- `PROJECT_STATE.md`, `README.md`

9. **Implementation summary**

- **Dashboard** (`/dashboard`): recent Saved Cases (`limit` default 10), filters in URL, link to full list
- **Cases** (`/cases`): full list with search, status/step/order filters, pagination (`limit` default 25)
- **Open/Reopen:** `POST /cases/saved/{uuid}/open|reopen` with `{ source: "manual_ui" }`; workspace cached in TanStack Query; navigate to `/cases/:caseUuid`
- **Workspace entry:** minimal identity page backed by cached open/reopen payload or `GET /cases/{uuid}/workspace` — no chat/analysis/grievance (M2+)
- **Global search:** TopBar search navigates to `/cases?search=`
- **No mock production data**; all list/open/reopen/workspace calls use real API client paths
- **No backend redesign**

10. **Accessibility**

- Labeled filters and search forms; table caption (visually hidden)
- Status badges use text labels (not color alone)
- Pagination `role="navigation"` with Previous/Next
- Live `role="status"` for activation messages; `role="alert"` + Retry on list failure
- Reopen-required confirm region with explicit actions
- Focus-visible styles preserved from M0 tokens

11. **Tests added**

- Click-action resolution for terminal vs active statuses
- Dashboard loads `GET /cases/saved`
- Cases URL filters (status + search) drive API query string
- Open navigates to workspace entry
- Reopen posts `source: manual_ui`
- `closed_requires_reopen` prompts then reopens
- Pagination updates `offset`
- TopBar global search routes to `/cases?search=`
- List error + Retry

12. **Validation commands and results**

```bash
cd frontend
npm run typecheck   # PASS
npm run lint        # PASS
npm run test:run    # PASS — 5 files, 17 tests
npm run build       # PASS
```

Backend code unchanged — no backend pytest run required for M1.

13. **Out of scope (intentionally not started)**

- M2 create case / full workspace restore shell
- Chat, analysis, grievance, artifacts, Sources admin
- W7–W11

14. **Final verdict:** **PASS**

15. **Commit message:** `feat(w6): implement saved cases workspace entry`
