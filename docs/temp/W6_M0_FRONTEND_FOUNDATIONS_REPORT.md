# W6 M0 — Frontend Foundations Report

1. **Date:** 2026-07-24
2. **Branch:** `main`
3. **Starting HEAD:** `8cabcbb1f0f94bb21f913c427c3c033daa8effdc`
4. **Pre-implementation Git status:**
   - Branch `main` ahead of `origin/main` by 1 commit
   - Untracked: `docs/W6_UI_ARCHITECTURE.md`, `docs/temp/_explain_embedding.py`, `docs/temp/_pytest_run*.txt`
   - No staged or modified tracked files before M0 work began

5. **Existing frontend inspection result:**
   - No existing `frontend/` directory
   - No root `package.json` or Node lockfile
   - No established frontend package-manager convention
   - FastAPI `GET /health` returns `{"status":"healthy","service":"GrievanceHub"}`
   - No CORS middleware required for M0 because the Vite `/api` proxy is same-origin
   - Root `.gitignore` already ignored `node_modules/` and `dist/`
   - `docs/W6_UI_ARCHITECTURE.md` was untracked and is included in this milestone

6. **Package-manager decision:** npm (no prior lockfile; commit `package-lock.json`)

7. **Exact dependencies and versions:**

| Package | Version | Role |
|---------|---------|------|
| react | 19.2.8 | UI |
| react-dom | 19.2.8 | DOM renderer |
| react-router-dom | 7.18.1 | Routing |
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

8. **Files created:** `frontend/**` (application, tests, config, lockfile), `docs/W6_UI_ARCHITECTURE.md` (tracked with corrections), `docs/temp/W6_M0_FRONTEND_FOUNDATIONS_REPORT.md`

9. **Files modified:** `.gitignore`, `PROJECT_STATE.md`, `README.md`, `docs/ARCHITECTURE.md`

10. **Application-shell implementation:**
    - `AppShell`, `TopBar`, `SideNav`, `EnvironmentBadge`, `ConnectionStatus`
    - Skip-to-content link, main outlet, route error boundary, not-found route
    - Nav: Dashboard, Cases, New Case, Help (Sources intentionally omitted)

11. **Routing implementation:**
    - `/` → `/dashboard`
    - `/dashboard`, `/cases`, `/cases/new`, `/help`
    - Catch-all not-found page with return link
    - Minimal status-accurate page content; no mock case data

12. **API-client implementation:**
    - `frontend/src/api/client.ts` typed fetch wrapper
    - Configurable `VITE_API_BASE_URL`, JSON/empty responses, AbortSignal
    - `ApiError` with safe `status`, optional `code`, `message`, `path`
    - No credential or sensitive-response logging

13. **Health-check implementation:**
    - Typed client for `GET /api/health` matching FastAPI `{status, service}`
    - TanStack Query-driven `ConnectionStatus`: Checking / Connected / Unavailable
    - Non-blocking, accessible text + retry when unavailable

14. **Design-system foundation:**
    - CSS custom properties in `src/styles/tokens.css` (backgrounds, text, accent,
      success/warning/danger, spacing, typography, focus, panel dimensions)
    - CSS Modules + global styles; no Tailwind; system font stack for M0

15. **Accessibility foundation:**
    - Skip link; semantic header/nav/main/aside
    - Visible `:focus-visible`; `aria-current` on active nav
    - Connection status `role="status"` + `aria-live="polite"`
    - Reduced-motion support; color-independent status labels

16. **Tests added:**
    - Root redirects to `/dashboard`
    - AppShell primary navigation
    - Active nav `aria-current="page"`
    - Health Connected state
    - Health Unavailable + Retry
    - Not-found usable page
    - No source API key read/render in production frontend code

17. **Exact commands run:**
    ```bash
    npm create vite@latest frontend -- --template react-ts
    npm install
    npm install react-router-dom @tanstack/react-query
    npm install -D vitest @testing-library/react @testing-library/jest-dom @testing-library/user-event jsdom
    npm run typecheck
    npm run lint
    npm run test:run
    npm run build
    ```

18. **Exact test, lint, typecheck, and build results:**
    - typecheck: PASS (`tsc -b --pretty false`)
    - lint: PASS (`oxlint src`, clean)
    - unit tests: PASS — 4 files, 7 tests
    - production build: PASS (`tsc -b && vite build`)

19. **Live FastAPI proxy smoke-test result:**
    - **Not run.** `http://127.0.0.1:8000/health` was unreachable during M0
      validation (`Unable to connect to the remote server`).
    - Automated tests mock the HTTP boundary for health.
    - Response shape was verified against `app/main.py` source.

20. **Architecture-document corrections:**
    - Component inventory count corrected from 42 → **64**
    - Removed browser `VITE_GRIEVANCEHUB_API_KEY` recommendation; stated no
      browser source API secrets; Sources deferred; no M0 key handling
    - Added API-contract verification rule (routes vs FastAPI / Pydantic /
      `/openapi.json` before later milestones)
    - Added implementation-progress section marking M0 complete

21. **Files deliberately excluded:**
    - `docs/temp/_explain_embedding.py`
    - `docs/temp/_pytest_run1.txt`
    - `docs/temp/_pytest_run2.txt`
    - `docs/temp/_pytest_run3.txt`
    - `docs/temp/_pytest_run3b.txt`
    - `frontend/node_modules/`
    - `frontend/dist/`
    - local `.env` files (none committed)

22. **Known non-blocking limitations:**
    - Live Vite → FastAPI proxy smoke test not executed (API not running)
    - System font stack used in M0 (approved branded fonts deferred)
    - Sources navigation intentionally absent pending safe auth boundary
    - npm audit reported 2 high-severity advisories in the dependency tree;
      not investigated as an M0 blocker

23. **M1 handoff items:**
    - Implement Saved Cases dashboard/list against verified `GET /cases/saved`
    - Confirm OpenAPI/Pydantic/route contracts before coding
    - Open/reopen flows and filters per `saved_cases_ui_contract.md`
    - Do not begin chat, analysis, grievance, artifacts, or Sources admin

24. **Final verdict before commit:** **PASS WITH NON-BLOCKING FINDINGS**

Non-blocking finding: live FastAPI proxy smoke test was not run because the
local API was unavailable. All automated frontend validation passed.
