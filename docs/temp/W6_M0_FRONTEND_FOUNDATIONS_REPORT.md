# W6 M0 — Frontend Foundations Report

1. **Date:** 2026-07-24
2. **Branch:** `main`
3. **Starting HEAD (original M0 implementation):** `8cabcbb1f0f94bb21f913c427c3c033daa8effdc`
4. **Pre-implementation Git status:**
   - Branch `main` ahead of `origin/main` by 1 commit
   - Untracked: `docs/W6_UI_ARCHITECTURE.md`, `docs/temp/_explain_embedding.py`, `docs/temp/_pytest_run*.txt`
   - No staged or modified tracked files before M0 work began
5. **Finalization HEAD (before this report update / follow-up commit):** `3802a91e2b2830ef9800a88c7197d0c6c12334e5`
   - Initial M0 implementation commit already present on `main`
   - Working tree clean except deliberately excluded W5 temp captures

6. **Existing frontend inspection result:**
   - No existing `frontend/` directory at M0 start
   - No root `package.json` or Node lockfile
   - No established frontend package-manager convention
   - FastAPI `GET /health` returns `{"status":"healthy","service":"GrievanceHub"}`
   - No CORS middleware required for M0 because the Vite `/api` proxy is same-origin
   - Root `.gitignore` already ignored `node_modules/` and `dist/`
   - `docs/W6_UI_ARCHITECTURE.md` was untracked and is included in this milestone

7. **Package-manager decision:** npm (no prior lockfile; commit `package-lock.json`)

8. **Exact dependencies and versions:**

| Package | Version | Role |
|---------|---------|------|
| react | 19.2.8 | UI |
| react-dom | 19.2.8 | DOM renderer |
| react-router-dom | 7.18.1 | Routing (direct) |
| react-router | 7.18.1 | Routing core (transitive via react-router-dom) |
| @tanstack/react-query | 5.101.4 | Server state |
| typescript | 6.0.3 | Types |
| vite | 8.1.5 | Bundler / dev server |
| @vitejs/plugin-react | 6.0.4 | React plugin |
| vitest | 4.1.10 | Unit tests |
| @testing-library/react | 16.3.2 | Component tests |
| @testing-library/jest-dom | 7.0.0 | DOM matchers |
| @testing-library/user-event | 14.6.1 | Interaction tests |
| jsdom | 29.1.1 | Test DOM |
| oxlint | 1.75.0 | Lint (Vite scaffold default) |
| @types/node | 24.13.3 | Node types |
| @types/react | 19.2.17 | React types |
| @types/react-dom | 19.2.3 | React DOM types |

**Dependency changes during finalization:** none. No lockfile edits. No `npm audit fix` applied.

9. **Files created (M0 implementation):** `frontend/**` (application, tests, config, lockfile), `docs/W6_UI_ARCHITECTURE.md` (tracked with corrections), `docs/temp/W6_M0_FRONTEND_FOUNDATIONS_REPORT.md`

10. **Files modified (M0 implementation):** `.gitignore`, `PROJECT_STATE.md`, `README.md`, `docs/ARCHITECTURE.md`

11. **Files modified after initial M0 implementation (finalization):**
    - `docs/temp/W6_M0_FRONTEND_FOUNDATIONS_REPORT.md` (audit + live smoke + final validation)
    - `docs/ARCHITECTURE.md` (status table: Interactive steward workspace → in progress / M0 complete)

12. **Application-shell implementation:**
    - `AppShell`, `TopBar`, `SideNav`, `EnvironmentBadge`, `ConnectionStatus`
    - Skip-to-content link, main outlet, route error boundary, not-found route
    - Nav: Dashboard, Cases, New Case, Help (Sources intentionally omitted)

13. **Routing implementation:**
    - `/` → `/dashboard`
    - `/dashboard`, `/cases`, `/cases/new`, `/help`
    - Catch-all not-found page with return link
    - Minimal status-accurate page content; no mock case data

14. **API-client implementation:**
    - `frontend/src/api/client.ts` typed fetch wrapper
    - Configurable `VITE_API_BASE_URL`, JSON/empty responses, AbortSignal
    - `ApiError` with safe `status`, optional `code`, `message`, `path`
    - No credential or sensitive-response logging

15. **Health-check implementation:**
    - Typed client for `GET /api/health` matching FastAPI `{status, service}`
    - TanStack Query-driven `ConnectionStatus`: Checking / Connected / Unavailable
    - Non-blocking, accessible text + retry when unavailable

16. **Design-system foundation:**
    - CSS custom properties in `src/styles/tokens.css`
    - CSS Modules + global styles; no Tailwind; system font stack for M0

17. **Accessibility foundation:**
    - Skip link; semantic header/nav/main/aside
    - Visible `:focus-visible`; `aria-current` on active nav
    - Connection status `role="status"` + `aria-live="polite"`
    - Reduced-motion support; color-independent status labels

18. **Tests added:**
    - Root redirects to `/dashboard`
    - AppShell primary navigation
    - Active nav `aria-current="page"`
    - Health Connected state
    - Health Unavailable + Retry
    - Not-found usable page
    - No source API key read/render in production frontend code

19. **npm audit investigation**

### Commands
```bash
cd frontend
npm audit
npm audit --json
npm audit fix --dry-run
npm ls react-router react-router-dom
```

### Advisory classification (2 high findings = same chain counted twice)

| Field | Finding |
|-------|---------|
| Advisory | [GHSA-qwww-vcr4-c8h2](https://github.com/advisories/GHSA-qwww-vcr4-c8h2) — RSC Mode CSRF Bypass Allows Action Execution Before 400 Response |
| npm severity | high |
| GitHub advisory severity | Moderate |
| Package | `react-router` |
| Direct or transitive | Transitive (via direct `react-router-dom`) |
| Dependency chain | `grievancehub-frontend` → `react-router-dom@7.18.1` → `react-router@7.18.1` |
| Runtime or development-only | **Runtime** (shipped in the production SPA bundle) |
| Affected version range | `>= 7.12.0, < 8.3.0` (npm audit text also shows `7.12.0 - 8.2.0`) |
| Installed version | `7.18.1` |
| Recommended fixed version | `react-router@8.3.0` (first patched) |
| Non-breaking fix available? | **No.** `npm audit fix` (without `--force`) makes no changes. `npm audit fix --force` proposes installing `react-router-dom@7.11.0` (breaking downgrade). `react-router-dom@8` is not published; latest `react-router-dom` remains `7.18.1`. |
| Included in production bundle? | **Yes** — `react-router` / `react-router-dom` are runtime SPA dependencies and appear in the Vite production build output. |
| Vulnerable code path used by M0? | **No.** Vendor note: “This only affects your application if you are using the unstable RSC APIs.” M0 uses Data Mode only (`createBrowserRouter` / `RouterProvider`). No Framework Mode, no unstable RSC APIs, no server actions. |
| Practical exposure in local-only W6 M0 | Negligible for the shipped M0 surface: local steward SPA, no RSC/server-action CSRF surface, no production internet exposure. The package remains an unpatched runtime dependency pending a compatible `react-router-dom` release that depends on `react-router>=8.3.0`, or an intentional major upgrade with regression testing. |
| Action taken | **No dependency change.** Did not run `npm audit fix --force`. Did not perform an unrelated major-version upgrade. |

### Final npm audit result (after finalization validation)
```
2 high severity vulnerabilities
react-router  7.12.0 - 8.2.0
Severity: high
React Router: RSC Mode CSRF Bypass ...
fix available via `npm audit fix --force`
Will install react-router-dom@7.11.0, which is a breaking change
```
Exit code: 1 (advisories remain; intentionally unresolved without breaking change)

20. **Live FastAPI and Vite proxy smoke tests**

### Direct FastAPI health
- Started with repository command: `venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
- Existing local `.env` present; no env values printed; no credentials created; no DB/schema changes
- `GET http://127.0.0.1:8000/health` → **200**
- Body: `{"status":"healthy","service":"GrievanceHub"}`
- Result: **PASS**

### Vite proxy health
- Started: `npm run dev -- --host 127.0.0.1 --port 5173`
- `GET http://127.0.0.1:5173/api/health` → **200**
- Body: `{"status":"healthy","service":"GrievanceHub"}`
- Browser dashboard DOM evaluation: `role="status"` text = `API: Connected`
- Result: **PASS**

### Cleanup
- Uvicorn and Vite processes started for this validation were stopped after testing.

21. **Exact frontend validation results (finalization re-run)**

| Check | Result |
|-------|--------|
| `npm run typecheck` | PASS (exit 0) |
| `npm run lint` | PASS (exit 0; oxlint clean) |
| `npm run test:run` | PASS — 4 files, 7 tests, 0 failed |
| `npm run build` | PASS (exit 0) |
| `npm audit` | 2 high advisories remain (classified above; exit 1) |

22. **Architecture-document corrections (during M0):**
    - Component inventory count corrected from 42 → **64**
    - Removed browser `VITE_GRIEVANCEHUB_API_KEY` recommendation
    - Added API-contract verification rule
    - Added implementation-progress section marking M0 complete

23. **Files deliberately excluded:**
    - `docs/temp/_explain_embedding.py`
    - `docs/temp/_pytest_run1.txt`
    - `docs/temp/_pytest_run2.txt`
    - `docs/temp/_pytest_run3.txt`
    - `docs/temp/_pytest_run3b.txt`
    - `frontend/node_modules/`
    - `frontend/dist/`
    - local `.env` files (none committed)

24. **Known non-blocking limitations:**
    - `react-router@7.18.1` remains in the npm audit high range until a compatible patched release path exists; M0 does not use unstable RSC APIs (vendor-scoped impact). Follow-up: upgrade when `react-router-dom` publishes a line depending on `react-router>=8.3.0`, with full frontend regression.
    - System font stack used in M0 (approved branded fonts deferred)
    - Sources navigation intentionally absent pending safe auth boundary

25. **M1 handoff items:**
    - Implement Saved Cases dashboard/list against verified `GET /cases/saved`
    - Confirm OpenAPI/Pydantic/route contracts before coding
    - Open/reopen flows and filters per `saved_cases_ui_contract.md`
    - Do not begin chat, analysis, grievance, artifacts, or Sources admin
    - Track react-router advisory remediation when a non-breaking path exists

26. **Final verdict before commit:** **PASS WITH NON-BLOCKING FINDINGS**

Non-blocking finding: npm reports 2 high-severity advisories on the runtime
`react-router` chain, but the advisory is scoped to unstable RSC APIs which M0
does not use; no safe non-breaking fix is available without a forced downgrade
or major upgrade. Live FastAPI health and Vite `/api/health` proxy smoke tests
passed. Automated frontend validation passed.
