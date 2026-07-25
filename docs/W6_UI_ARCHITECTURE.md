# W6 — Interactive Steward Workspace UI Architecture

**Status:** W6 in progress — M0–M8 complete (Foundations through Workflow outcomes)
**Date:** 2026-07-25
**Depends on:** W5 complete backend (case workspace, retrieval, analysis, grievances, artifacts, official forms)
**Canonical companions:** [`ROADMAP.md`](ROADMAP.md), [`ARCHITECTURE.md`](ARCHITECTURE.md), [`saved_cases_ui_contract.md`](saved_cases_ui_contract.md)

This document is the implementation blueprint for the W6 steward workspace. Another engineer should be able to implement the UI from this spec without inventing parallel workflows or guessing API contracts.

### Implementation progress

| Milestone | Status |
|-----------|--------|
| **M0 — Foundations** | **Complete** — `frontend/` Vite/React/TS shell, design tokens, AppShell, typed apiClient, `/api` proxy, health ConnectionStatus, accessibility foundations, Vitest coverage |
| **M1 — Saved cases** | **Complete** — Dashboard + Cases list against `GET /cases/saved`, URL filters/search/pagination, open/reopen, `/cases/:caseUuid` entry |
| **M2 — Create + workspace restore** | **Complete** — Create Case form; durable `GET /cases/{uuid}/workspace` restore; `CaseWorkspaceShell` + Case Rail; overview/memory/facts; facts `PATCH` |
| **M3 — Conversation** | **Complete** — `/cases/:caseUuid/conversation`; `GET .../messages` + `POST .../interactions`; retrieval statuses; citations/research panel; disclosures; facts-needed; no artifacts from chat |
| **M4 — Evidence** | **Complete** — `/cases/:caseUuid/evidence`; `GET/POST .../assets`; metadata detail; Conversation `upload_refs` picker; no case-file RAG; no analysis/grievance/artifact side effects |
| **M5 — Analysis** | **Complete** — `/cases/:caseUuid/analysis`; Generate temporary preview; Cancel/no-persist; Save / Save and Print; versions; HTML/PDF export; idempotency + `saved_pdf_failed` handling |
| **M6 — Grievance** | **Complete** — `/cases/:caseUuid/grievance`; Generate → Edit → Validate → Save / Save and Print for Step 1/2 official forms only; temporary local React draft state; limited saved `grievance_form` list/detail/PDF |
| **M7 — Artifacts & history** | **Complete** — `/cases/:caseUuid/artifacts`; Artifact Library (analysis + grievance), read-only detail/PDF, Official Case Record, timeline, compare, jump-to-context; no generation workflows |
| **M8 — Workflow outcomes** | **Complete** — `/cases/:caseUuid/workflow`; workflow/step display, progression, Record Outcome, same-case appeal, close/settle/archive/reopen; no artifact creation; Step 3 form generation unsupported |
| M9 — Sources research | Planned |
| M10 — Polish & a11y | Planned |

### API-contract verification rule

Before implementing each later milestone, verify every referenced route against:

1. FastAPI route definitions under `app/api/`
2. Pydantic schemas under `app/schemas/`
3. Live `/openapi.json` from the running API when available

Do not treat an architecture-document route as implemented merely because it is listed here.

---

## 0. First principles

1. **The application manages workflow. The steward manages the grievance.**
2. **Normal conversation never creates reports or grievances.** Chat retrieves, answers, cites, persists messages, and may update Case Memory. It creates no `CaseReportVersion`, saved artifact, or Official Case Record noise.
3. **Analysis and grievances are explicit steward actions:** Generate → Preview/Edit → Save / Save and Print / Cancel.
4. **Temporary work is client-held until Save.** Cancel discards the temporary payload with no version number consumed and no Official Case Record event.
5. **The UI exposes the existing W5 backend exactly as implemented.** No backend redesign unless a concrete blocker is proven during implementation.
6. **Content provenance must be visually unmistakable:** source quotes ≠ generated analysis ≠ recommendations ≠ citations ≠ warnings/limitations.
7. **Desktop-first professional legal/workflow application,** not a chatbot shell.

### Explicit non-goals for W6 UI

- Production authentication / identity (W9)
- Formal evaluation gates (W7)
- Multi-agent product orchestration (W8)
- LMOU / arbitration corpus expansion (W10)
- Production packaging (W11)
- Public internet exposure
- Ingestion of private operational grievance data
- Case-file RAG over uploaded documents (uploads are metadata/`upload_refs` context only)
- Step 3 grievance generation / official form (out of scope for W6 steward UI; official generation ends at Step 2)

### Steward controls that must NOT appear

Do not render as steward buttons:

- Save Context
- Update Analysis
- Reanalyze
- Refresh Report
- Start Chat (chat is always present on case-work pages)

`save_and_update_analysis` is internal (`steward_visible: false`). Prefer `POST /cases/{uuid}/interactions` for chat and dedicated generate/save routes for artifacts.

---

## 1. Recommended frontend stack

| Concern | Recommendation | Why |
|---------|----------------|-----|
| Framework | **React 19 + TypeScript + Vite** | No SPA exists today; Vite gives a clean client app against FastAPI without Next.js SSR complexity. Desktop workspace UX is client-heavy. |
| Routing | **React Router v7 (data-aware routes)** | Nested case workspace routes, loaders for workspace restore, clear URL ↔ case context. |
| Server state | **TanStack Query v5** | Cases, messages, artifacts, history, sources are remote resources with cache, invalidation, retries, and stale-while-revalidate. |
| Client/ephemeral state | **Local React state and/or Zustand** | Temporary analysis preview and grievance draft (M5/M6 use local state); panel collapse, citation selection, toast queue — not server truth. |
| Forms | **React Hook Form + Zod** | Grievance field editing, case create, fact edits; Zod schemas mirrored from Pydantic. |
| Styling | **CSS variables + CSS Modules (or Tailwind with custom tokens only)** | Enterprise control over density/contrast; avoid default AI purple/cream themes. |
| Icons | **Lucide** (outline, consistent stroke) | Neutral enterprise iconography. |
| PDF preview | Browser native PDF viewer via blob URL / iframe for official PDFs; HTML iframe for analysis preview export | Matches existing HTML/PDF export endpoints. |
| HTTP client | **fetch wrapper** (`apiClient`) with typed errors | Thin abstraction over OpenAPI-shaped responses; no heavy SDK required. |
| Types | Generated or hand-mirrored from `app/schemas/*.py` | Start with hand-mirrored TS types for critical paths; optionally generate from `/openapi.json` later. |
| Testing | Vitest + React Testing Library + Playwright | Unit for components; e2e for Generate → Save workflows. |
| Dev proxy | Vite proxy `/cases`, `/sources`, `/health` → FastAPI | Same-origin during local development. |

**Not recommended for W6:** Next.js App Router (SSR/auth complexity before W9), Redux Toolkit (overkill vs Query + Zustand), GraphQL (backend is REST), WebSocket chat (backend is request/response).

**Streaming note:** Current `POST /interactions` returns a complete `CaseInteractionResponse`. Design chat UI for full-response turns with clear loading states. Do not invent SSE/WebSocket clients until the backend adds streaming.

---

## 2. Overall application layout

### 2.1 Shell structure

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ TopBar: brand · global search (cases) · environment badge · status       │
├────────────┬─────────────────────────────────────────────────────────────┤
│ SideNav    │ Main content (route outlet)                                 │
│            │                                                             │
│ Dashboard  │  For /cases/:id/* → CaseWorkspaceShell (3-panel)            │
│ Cases      │                                                             │
│ Sources*   │                                                             │
│ Help       │                                                             │
└────────────┴─────────────────────────────────────────────────────────────┘
│ GlobalToastRegion · ConfirmDialogHost · ModalHost                        │
└──────────────────────────────────────────────────────────────────────────┘
```

\* Sources admin is secondary and must not receive browser-held API secrets.
  Hide Sources until an approved server-side boundary exists (deferred past M0).

### 2.2 Top bar

| Element | Behavior |
|---------|----------|
| Brand mark + “GrievanceHub” | Links to `/dashboard`. Brand is visible but not marketing-hero scale inside the app shell. |
| Case context chip | When on a case route: case number/title, workspace status badge, current step. Click focuses left panel overview. |
| Global case search | Filters/navigates Saved Cases (`search` query param → `GET /cases/saved?search=`). |
| Environment badge | `Local` / `Dev` only — never imply production security. |
| Connection status | Subtle indicator when API health fails. |
| Notifications | Bell opens recent toast history (session-scoped; no backend notification API in W5). |

### 2.3 Side navigation

Primary items:

| Nav item | Route | Notes |
|----------|-------|-------|
| Dashboard | `/dashboard` | Saved-case oriented home |
| Cases | `/cases` | Full saved-case list |
| New case | `/cases/new` | Create flow |
| Sources | `/sources` | Deferred past M0; no browser source API secrets |
| Help | `/help` | Short workflow guidance |

Collapsed icon rail on medium widths; full labels at ≥1280px.

### 2.4 Case context

Case context is **route-owned** (`/cases/:caseUuid/...`). Entering a case:

1. Resolve open vs reopen from list click rules (see §4).
2. Prefer workspace payload from open/reopen response.
3. Otherwise `GET /cases/{uuid}/workspace`.
4. Load messages separately via `GET /cases/{uuid}/messages` when Conversation panel mounts.

Leaving a case clears ephemeral preview/draft stores and aborts in-flight interaction requests.

### 2.5 Global notifications

Use a toast system with severity: `info`, `success`, `warning`, `error`.

| Event | Toast |
|-------|-------|
| Case opened/reopened | success, brief |
| Interaction failed | error, sticky until dismiss |
| Retrieval empty | warning inline in chat (not global toast) |
| Analysis saved | success + deep link to artifact |
| Save PDF failed (`saved_pdf_failed`) | warning: saved but PDF pending/failed |
| Upload succeeded | success |
| Session/auth future (W9) | reserved |

Confirm dialogs for: close case, settle, archive, discard unsaved grievance edits, cancel analysis preview with edits N/A (analysis is read-only).

### 2.6 Loading behavior

| Scope | Pattern |
|-------|---------|
| App boot | Minimal shell skeleton; health check non-blocking |
| Route navigation | Route-level suspense/skeleton in main outlet |
| Case workspace restore | Full 3-panel skeleton with labeled regions |
| Chat send | Disable composer; show assistant typing placeholder in thread |
| Generate analysis/grievance | Modal busy state with cancel of **request** only (not of persisted work) |
| Artifact/PDF fetch | Panel-level spinner; keep surrounding UI interactive |
| Background refetch | Silent Query refetch; no full-page flash |

Never show raw stack traces. Map HTTP errors to steward language (§12).

### 2.7 Responsive behavior

**Desktop-first.** Target: 1280×800 minimum comfortable; 1440+ ideal.

| Breakpoint | Layout |
|------------|--------|
| ≥1440px | 3-panel case workspace (left ~280px, center flex, right ~360px) |
| 1100–1439px | 3-panel with collapsible right; citation drawer toggle |
| 800–1099px | Left collapses to drawer; center + right stacked tabs |
| <800px | Supported but degraded: single column with bottom tab bar (Case / Chat / Research / Artifacts). Not the primary design target. |

Do not build a mobile-first chatbot layout.

---

## 3. Route hierarchy

```text
/
├── /dashboard                          # Saved cases home (default after entry)
├── /cases                              # Full case list (filters in URL)
├── /cases/new                          # Create case
├── /cases/:caseUuid                    # Case workspace (default: overview + chat)
│   ├── /cases/:caseUuid/conversation   # Chat-focused (same shell, center = chat)
│   ├── /cases/:caseUuid/evidence       # Uploads / assets focused
│   ├── /cases/:caseUuid/analysis       # Analysis review / versions
│   ├── /cases/:caseUuid/grievance      # Grievance draft / Step 1–2 official forms
│   ├── /cases/:caseUuid/artifacts      # Artifact library
│   ├── /cases/:caseUuid/history        # Official Case Record
│   ├── /cases/:caseUuid/memory         # Case Memory / overview (read-mostly)
│   └── /cases/:caseUuid/workflow       # Step progression / outcomes
├── /cases/:caseUuid/analysis/preview   # Full-page temporary preview (optional deep link)
├── /cases/:caseUuid/artifacts/:artifactUuid
├── /cases/:caseUuid/print/analysis/:version?   # Print-oriented view (no chat)
├── /cases/:caseUuid/print/grievance/:artifactUuid
├── /sources                            # Source corpus browser
├── /sources/search                     # Ad-hoc retrieval research
├── /sources/:sourceId                  # Source detail / chunks (read)
└── /help
```

### Routing rules

| Rule | Detail |
|------|--------|
| Default entry | `/` → redirect `/dashboard` |
| Case identity | Always `caseUuid` (UUID string), never numeric `case_id` in URLs |
| Chat presence | Present on all case-work routes except `/print/*` |
| Filters | Saved-case filters live in query string: `?status=&step=&search=&order=&limit=&offset=` |
| Open vs reopen | Performed before navigating into workspace; do not land on a closed case without reopen |
| Legacy `/ui` | Keep FastAPI verification shell during W6; do not remove until SPA reaches parity |

### Planned page count

**16 route-level pages/views** (including print and sources). Most case sub-routes share one `CaseWorkspaceShell` and swap center/right emphasis — they are not 16 separate layouts.

| # | Page |
|---|------|
| 1 | Dashboard |
| 2 | Cases list |
| 3 | New case |
| 4 | Case workspace (default) |
| 5 | Conversation focus |
| 6 | Evidence |
| 7 | Analysis |
| 8 | Grievance |
| 9 | Artifacts list |
| 10 | Artifact detail |
| 11 | Official Case Record (history) |
| 12 | Case Memory |
| 13 | Workflow / outcomes |
| 14 | Analysis print view |
| 15 | Grievance print view |
| 16 | Sources (+ search/detail as subviews of sources area; count as one admin area with 2–3 views) |

---

## 4. Case list and open/reopen

### 4.1 Dashboard and Cases list

**Data:** `GET /cases/saved` with filters from [`saved_cases_ui_contract.md`](saved_cases_ui_contract.md).

Display columns:

- Case number, title, issue summary
- Current step + step status
- Workspace status badge (`open` / `closed` / `reopened` / `appealed` / `settled` / `archived`)
- Last activity
- Latest outcome summary
- Available actions (steward-visible only)

### 4.2 Row click

1. If `workspace_status === "closed"` → `POST /cases/saved/{uuid}/reopen` `{ "source": "manual_ui" }`
2. Else → `POST /cases/saved/{uuid}/open` `{ "source": "manual_ui" }`
3. On success, place `workspace` into Query cache and navigate to `/cases/{uuid}`
4. If `action_taken === "closed_requires_reopen"`, prompt reopen instead of navigating

Use the same resolution logic as `app/clients/saved_case_client.py` (`resolve_case_click_action` / `activate_case`).

### 4.3 Create case

**Route:** `/cases/new`
**API:** `POST /cases/` with `{ question, user_name?, local_number?, known_facts? }`

Verified notes (M2):

- OpenAPI also lists `limit_per_source` on `CreateCaseRequest`, but the create
  route does **not** pass it into `CaseService.create_case` — omit from the
  steward form.
- Response is `{ case, report_version: null }` (case detail/summary), **not** a
  workspace payload. Navigate to `/cases/{uuid}` and restore via
  `GET /cases/{uuid}/workspace` (or cached open/reopen workspace).

Behavior:

- Creates case **without** auto-analysis (`report_version: null`)
- On success, navigate to `/cases/{uuid}` and restore the workspace shell
- Initial `question` is shown in Case Overview / identity; M2 does **not** send
  the first chat interaction (avoids surprise AI spend). Conversation is M3.

---

## 5. Case workspace (primary experience)

### 5.1 Three-panel layout

```text
┌───────────────────┬──────────────────────────────┬─────────────────────┐
│ LEFT (~280px)     │ CENTER (flex)                │ RIGHT (~360px)      │
│ Case rail         │ Primary work surface         │ Context / research  │
│                   │                              │                     │
│ Overview          │ Default: Conversation        │ Citations           │
│ Facts / Issues    │ Analysis: preview / body     │ Retrieved authority │
│ Step / Workflow   │ Grievance: field editor      │ Memory snapshot     │
│ Timeline slice    │ Evidence: upload table       │ Available actions   │
│ Uploads summary   │ Artifacts: library           │                     │
│ Artifacts shortcut│                              │                     │
│ Official Record   │                              │                     │
└───────────────────┴──────────────────────────────┴─────────────────────┘
│ Bottom action bar: Generate Analysis · Generate Grievance · Upload ·   │
│ Record Outcome · Close/Settle (from available_actions)                 │
└────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Left panel — Case rail

Owns durable case identity and navigation within the case.

| Section | Content | API |
|---------|---------|-----|
| Identity | Title, case number, UUID (copy), status, step | workspace / overview |
| Case Overview | Employee, issue, recommendation, open questions, counts | `case_overview` in workspace (or `GET .../overview`) |
| Facts | Editable `known_facts` key/value | `PATCH .../facts` |
| Issues | Outstanding issues / open questions from memory | memory/overview |
| Step progression | Current step, permitted transitions, outcome CTA | workflow + outcomes |
| Timeline (slice) | Recent steward timeline events | workspace timeline slice; full → history route |
| Uploads | Asset count + recent filenames; link to Evidence | `assets` |
| Artifacts | Latest official analysis/grievance titles | `artifacts` groups |
| Official Case Record | Shortcut list of recent official events | history slice |
| Memory | Compact “what the system understands” | `case_memory` |

Left panel is **not** the chatbot. It reinforces that the steward is managing a case file.

### 5.3 Center panel — Primary work surface

Route-driven:

| Route | Center content |
|-------|----------------|
| `/cases/:id` and `/conversation` | `ConversationPanel` |
| `/evidence` | `UploadPanel` + asset table |
| `/analysis` | Saved versions list + latest report body or empty state with Generate CTA |
| `/grievance` | Step 1/2 draft editor or saved Step 1/2 grievance; Generate when backend returns a supported template |
| `/artifacts` | Grouped artifact library |
| `/history` | Full Official Case Record |
| `/memory` | Structured Case Memory viewer |
| `/workflow` | FSM state, transitions, record outcome form |

### 5.4 Right panel — Research and provenance

| Mode | Content |
|------|---------|
| Chat-active | Citations for selected/latest assistant message; retrieval status; disclosures; facts needed |
| Analysis-active | Authority sections, citation validation summary, limitations |
| Grievance-active | Field provenance, never-invent warnings, validation checklist |
| Idle | Case Memory highlights + available actions |

Selecting a citation highlights the corresponding quote region when present in analysis HTML; for chat, expands citation card with document, article/section, page, quote, grounded flag.

### 5.5 Sticky action bar

Render primary actions from `available_actions` where `steward_visible !== false`, plus fixed W6 primaries:

| Action | Control | API |
|--------|---------|-----|
| Generate Analysis Report | Primary button | `POST .../reports/generate` |
| Generate Grievance | Primary button | `POST .../actions` `{ action: "generate_grievance" }` |
| Upload evidence | Secondary | opens Evidence / file picker → `POST .../assets` |
| Record outcome | Secondary when permitted | `POST .../outcomes` |
| Close / Settle / Archive | Destructive/secondary from saved-case actions | respective saved-case routes |

Disable Generate when prerequisites missing; show `missing_prerequisites` messages, not silent disable.

---

## 6. Chat experience

### 6.1 Placement

Persistent AI chat on active case-work pages (New Case after create, workspace, evidence, analysis, grievance before final print).

**Omit chat** on: print preview routes, sources admin, help, login/settings (future).

Each case owns its own conversation. Context is never shared across cases.

### 6.2 Conversation layout

```text
┌─────────────────────────────────────────────┐
│ Thread (scroll, newest at bottom)           │
│  [Steward bubble]                           │
│  [Assistant bubble + citation chips]        │
│  [System/disclosure banners as needed]      │
├─────────────────────────────────────────────┤
│ Composer                                    │
│  textarea · attach upload_refs · Send       │
│  helper: “Chat does not create reports”     │
└─────────────────────────────────────────────┘
```

### 6.3 Message model (UI)

Map from `GET /cases/{uuid}/messages` and interaction response summaries:

| UI field | Source |
|----------|--------|
| id | message id |
| role | `user` / `assistant` / (ignore system noise) |
| content | text |
| created_at | timestamp |
| citations | from assistant metadata or last interaction response |
| retrieval_status | interaction response |
| disclosures / facts_needed | interaction response |

### 6.4 Send flow

1. Optimistic steward message in thread (pending).
2. `POST /cases/{uuid}/interactions` with:
   ```json
   {
     "message": "...",
     "clarification": null,
     "fact_updates": null,
     "upload_refs": ["asset-uuid-..."],
     "source": "manual_ui",
     "pinned_report_version": null
   }
   ```
3. On success: replace pending with `user_message` + append `assistant_message`; update right-panel citations; patch `available_actions`; optionally invalidate memory/overview queries if `case_memory_update_status === "updated"`.
4. On failure: mark pending message failed with Retry; do not invent an assistant answer.

### 6.5 Streaming

**W6 baseline:** no token streaming. Show a determinate/indeterminate “Researching authorities…” state while the request is in flight. Distinguish:

- Waiting on network
- Long-running AI (after ~2s show secondary copy: “Retrieving sources and drafting an answer”)

If backend later adds SSE, confine changes to the interaction client and message reducer.

### 6.6 Citations in chat

Each assistant turn may include `citations[]` with fields such as:

- `document_type`, `document_name`, `article_or_section`, `page`, `quote`, `grounded`, `grounding_provenance`

UI rules:

- Render citation chips under the answer.
- Click opens right-panel `CitationDetail`.
- Ungrounded or failed validation → warning styling; never present as controlling authority.
- Empty citations + `retrieval_status: "ok"` → answer may be general; show disclosure if provided.
- `retrieval_status: "empty"` → empty-results panel: “No matching authorities found in the indexed corpus.”
- `retrieval_status: "failed"` → error panel with retry; preserve steward message.
- `retrieval_status: "skipped"` → explain skip reason from disclosures/message when present.

### 6.7 Low confidence / disclosures / facts needed

- Render `disclosures` as non-dismissible-until-read banners on the turn (or persistent callouts).
- Render `facts_needed` as checklist CTAs that deep-link to Facts editor in the left panel.
- Low-confidence language from the model stays in the answer body; do not upgrade confidence visually.

### 6.8 Follow-up questions

Follow-ups are ordinary new interactions in the same case thread. Do not use legacy `POST /followups` in new UI.

Optional UI affordance: suggest chips from `facts_needed` or prior disclosures — still sent as normal `/interactions` messages.

### 6.9 Conversation continuity and session restoration

On case enter:

1. Restore workspace (memory first — backend already does this).
2. Fetch messages page (`GET .../messages?limit=...`).
3. Do **not** replay full transcript into generate calls; backend uses Case Memory + bounded `ai_continuity_context`.

On case switch:

1. Abort in-flight interaction.
2. Clear ephemeral stores (preview/draft/citation selection).
3. Load new workspace + messages.

On browser refresh:

1. Route still has `:caseUuid`.
2. `GET .../workspace` + `GET .../messages`.
3. Ephemeral unsaved analysis preview / grievance draft are **lost** (correct: temporary until Save). Warn with `beforeunload` if draft store is dirty.

### 6.10 Composer constraints

- Enter sends (Shift+Enter newline) on desktop.
- Block empty sends.
- Attaching existing case assets as `upload_refs` is implemented (M4): composer
  “Attach case evidence” selects current-case asset UUIDs only. Message-only
  submissions still send `{ message, source: "manual_ui" }` without
  `upload_refs`. Uploaded evidence is case context, not authority-corpus RAG.
- Optional `fact_updates` advanced mode collapsed by default (power users); default fact edits go through Facts panel `PATCH`.

---

## 7. Analysis workflow

```text
Generate Analysis
      ↓
Temporary read-only Preview  (client-held; persisted:false)
      ↓
  ┌───┴────────────────────────┐
  │                            │
Cancel                      Save / Save and Print
(discard; no version)          ↓
                        CaseReportVersion + Artifact
                               ↓
                        Official Case Record event
                               ↓
                     Optional PDF (prepare_pdf)
```

### 7.1 Generate

**Trigger:** Action bar / Analysis page CTA.
**API:** `POST /cases/{uuid}/reports/generate` `{ limit_per_source?: number }`
**Response (conceptual):** analysis preview JSON + `persisted: false`, `report_version: null`.

UI:

- Open `AnalysisPreviewModal` or navigate to analysis center with **Temporary preview** banner.
- Banner copy: “Unsaved preview — Cancel discards this report. Save creates version N.”
- Body is read-only structured report (see §7.4).
- Right panel shows authorities / limitations / citation validation from preview.

### 7.2 Preview vs saved

| State | Indicator | Persistence |
|-------|-----------|-------------|
| Temporary preview | Amber “Unsaved preview” badge | Client store only |
| Saved version | Version number chip `vN` | `CaseReportVersion` |
| Official artifact | “Official” + printed flag | `CaseSavedArtifact` |
| Working draft PDF | Query `working_draft=true` | Non-official preview export only |

### 7.3 Save / Save and Print

**API:** `POST /cases/{uuid}/reports/save-and-print`

```json
{
  "preview": { /* temporary preview payload */ },
  "title": "optional",
  "prepare_pdf": true,
  "idempotency_key": "client-generated-uuid"
}
```

| Button | `prepare_pdf` | Result |
|--------|---------------|--------|
| Save | `false` or `true` per product choice — **recommend Save → `prepare_pdf: false`, Save and Print → `true`** | Artifact created; PDF optional |
| Save and Print | `true` | Artifact + PDF when possible; open print view |

Handle `status`:

- `saved` → success; clear preview store; invalidate versions/artifacts/history/workspace
- `saved_pdf_failed` → success with warning; allow retry PDF via export endpoints
- `idempotent_replay` → treat as success; do not duplicate toasts aggressively

### 7.4 Analysis display structure

Render `GrievanceHubReport` sections with clear visual taxonomy:

| Kind | Sections (examples) | Visual treatment |
|------|---------------------|------------------|
| Meta | report_title, brand, generated_at, case_information | Header |
| Assessment | quick_assessment, secondary_issues | Summary cards with confidence badge |
| Generated analysis | detailed_analysis, key_contract_violations, recommended_remedy | “Generated analysis” labeled region |
| Authority (by role) | union_supporting_authority, management_limiting_authority, background_authority, etc. | Role labels; controlling vs non-controlling |
| Evidence | supporting_evidence with quotes | Quote blocks + citation links |
| Warnings | limitations, research_draft_notice, citation_validation | Warning/alert styling |
| References | source_references, source_summary | Reference list |

Never style generated narrative like a source quote block.

### 7.5 Versions

- List: `GET /cases/{uuid}/versions`
- Detail: `GET /cases/{uuid}/versions/{n}`
- Export: `/export/preview|html|pdf` and version-scoped export routes
- Official PDF without prior Save and Print → `409` unless `working_draft=true` for non-official preview

### 7.6 Compatibility

Do not call `POST .../reports/regenerate` from W6 UI (legacy immediate version creation).

---

## 8. Grievance workflow (M6 — Complete)

**Status:** Complete. Official grievance generation currently ends at Step 2.
The backend workflow FSM may still track Step 3 and later case states; the
steward UI must not expose unsupported official grievance forms (no Step 3
placeholder/unavailable cards). Offer Generate only when the backend returns one
of the two supported templates below.

```text
Generate Grievance
      ↓
Temporary editable draft (field_values) — local React state
      ↓
Field editing + client validation
      ↓
  ┌───┴────────────────────────┐
  │                            │
Cancel                      Save / Save and Print
(discard)                      ↓
                        Official grievance_form artifact (Step 1 / Step 2)
                               ↓
                        AcroForm PDF when prepare_pdf
                               ↓
                        Official Case Record (on Save)
```

### 8.1 Generate

**Route:** `/cases/:caseUuid/grievance`
**API:** `POST /cases/{uuid}/actions`
```json
{ "action": "generate_grievance" }
```

Use `WorkspaceActionResponse.grievance_generation`:

- `editable: true`
- `field_values: { ... }`
- `template_id`, `step_type`, `draft_status`

Hold the temporary draft in **local React component state** (same pattern as M5
analysis preview — not required to be Zustand). Discard on Cancel / case switch.
If `template_id` is not one of the two supported IDs, show a concise unsupported
notice and do **not** open an editor or later-step placeholder UI.

### 8.2 Field editing

`GrievanceDraftEditor` renders fields from the Step 1 / Step 2 template mapping
(`templateFields`); edit the flat `field_values` map returned by Generate.

Rules:

- **Never-invent / protected fields** — empty by default; steward must fill; show protected-field warning styling.
- **Required fields** — client validation surfaces `missing_required_field_ids`; backend remains authoritative on Save.
- Track `steward_override_field_ids` for fields the steward changed after Generate.
- Provenance: “Generated draft value” vs “Steward edited” from `generated_field_values` vs overrides.

### 8.3 Validation

Client-side pre-check + server authority on save:

1. Required non-empty
2. Protected blank fields flagged for steward attention
3. Supported-template gate: only
   `official_grievance_worksheet_step_1` and
   `official_standard_grievance_form_step_2`

Do not add empty-state cards for later official forms. Prerequisites from
`available_actions` / `missing_prerequisites` (for example `template_unavailable`,
`case_closed_requires_reopen`) disable or explain Generate without inventing
Step 3 UI.

### 8.4 Preview / PDF

- In-app field editor is the temporary-draft review surface
- After Save, PDF via `GET .../artifacts/{artifactUuid}/pdf` when `pdf_status` allows
- Handle `saved_pdf_failed` without losing the official artifact

### 8.5 Save / Save and Print

**API:** `POST /cases/{uuid}/grievances/save-and-print`

```json
{
  "template_id": "official_grievance_worksheet_step_1",
  "field_values": { },
  "steward_override_field_ids": [],
  "missing_required_field_ids": [],
  "validation_status": "ready_for_steward_review",
  "draft_status": "ready_for_steward_review",
  "prepare_pdf": true,
  "idempotency_key": "..."
}
```

| Button | `prepare_pdf` |
|--------|---------------|
| Save | `false` |
| Save and Print | `true` |

Official templates supported by the W6 steward UI:

| template_id | Form |
|-------------|------|
| `official_grievance_worksheet_step_1` | Step 1 worksheet |
| `official_standard_grievance_form_step_2` | Step 2 standard form |

### 8.6 Saved grievance browsing (M6-limited)

M6 lists/details/PDFs saved Step 1/2 `grievance_form` artifacts on the grievance
route (`GET .../artifacts?artifact_type=grievance_form`, detail + PDF). M7 provides
the general Artifact Library, Official Case Record browser, timeline, compare,
and jump-to-context on `/cases/:caseUuid/artifacts`.

---

## 9. Artifact management

### 9.1 Library (M7 complete)

**Route:** `/cases/:caseUuid/artifacts` under `CaseWorkspaceShell` (nav:
Artifacts & History).

**API:** `GET /cases/{uuid}/artifacts` → `artifacts` + `groups`
(`analysis_reports`, `grievances`, …). Optional `artifact_type` filter:
`analysis_report` | `grievance_form`.

UI: `ArtifactsPanel` / Artifact Library with type filter, newest/oldest sort
(URL search params), version labels, printed flag, pdf_status
(`pending` | `ready` | `failed`). Analysis and grievance artifacts both listed.
`stored_path` is never rendered. Empty/loading/error states are accessible.

### 9.2 Detail and download (M7 complete)

| Action | API |
|--------|-----|
| View detail (read-only) | `GET .../artifacts/{artifactUuid}` |
| Download/preview PDF | `GET .../artifacts/{artifactUuid}/pdf` (blob URL; revoke on close/case switch) |
| Analysis HTML preview | export preview routes (Analysis workspace) |
| Compare two versions | `POST .../artifacts/compare` |

Detail is read-only. Opening an artifact does not regenerate or modify it.
PDF unavailable / pending / failed states are steward-facing.

### 9.3 Official Case Record vs artifacts (M7 complete)

| Concept | Meaning | API |
|---------|---------|-----|
| Artifacts | Document library of saved analysis/grievance docs | `/cases/:caseUuid/artifacts` |
| Official Case Record | Chronological meaningful saved events | `GET /cases/saved/{uuid}/history` |
| Timeline | Broader steward timeline events | `GET /cases/saved/{uuid}/timeline` |
| Domain events | Internal projections — **do not primary-surface** | `/domain-events` (debug/advanced only) |

Jump-to-context: `GET /cases/{uuid}/history/{event_id}/context` opens a bounded
read-only dialog (nearby messages, related artifact/workflow, event position).
Escape closes; focus restores. Does not mutate Case Memory or create messages /
artifacts. Comparison requires same `artifact_type` and distinct UUIDs; creates
no new official artifact.

### 9.4 PDF export rules

- Official print requires prior Save and Print.
- Without it, only `working_draft=true` non-official preview.
- Surface `409` as: “Official PDF is available after Save and Print.”

---

## 10. Evidence uploads

| Action | API |
|--------|-----|
| List | `GET /cases/{uuid}/assets?category=uploaded_document` |
| Upload | `POST /cases/{uuid}/assets` multipart: `file`, `category=uploaded_document`, `uploaded_by?`, `source=manual_ui` |
| Metadata | `GET /cases/{uuid}/assets/{assetUuid}` |

Verified backend constraints (W3/M4):

- Executable upload category: `uploaded_document` only (other categories 400 placeholder).
- Max size: `CASE_ASSET_MAX_UPLOAD_BYTES` = 25 MiB; empty files rejected.
- No MIME whitelist on the backend.
- Response may include `stored_path` / `stored_filename` — **never render storage paths**.
- `upload_refs` on interactions is `list[str]` of case asset UUIDs (multiple allowed).
- Continuity marks evidence `content_embedded: false`; uploads are not corpus-ingested.

UI notes (M4 complete):

- Route `/cases/:caseUuid/evidence` under `CaseWorkspaceShell` with Conversation/Evidence nav.
- Show filename, asset UUID, category, mime, size, sha256, uploaded_by, source, created_at, status.
- **No case-file RAG:** disclose “Uploaded evidence is attached as case context. It is not full-text searched like the indexed authority corpus.”
- After upload, asset UUID is available to the Conversation attachment picker via `upload_refs`.

Source-processing status for the **authority corpus** lives under `/sources` (admin), not the case upload panel.

---

## 11. Sources / research (secondary)

Steward research against the indexed corpus (API-key protected):

| Screen | API |
|--------|-----|
| List sources | `GET /sources/` |
| Embedded stats | `GET /sources/embedded/` |
| Search | `GET /sources/search/?query=&limit_per_source=&domain=` |
| Ask | `GET /sources/ask/` |
| Chunk | `GET /sources/{id}/chunks/{chunk_index}` |

Admin mutations (upload-pdf, process, sync) may be behind an “Admin” disclosure; W6 can ship read/search first.

Case chat already performs retrieval — Sources pages are for corpus inspection and debugging weak retrieval, supporting W6’s continuous RAG validation goal.

---

## 12. State management

### 12.1 Strategy summary

| State kind | Tool | Examples |
|------------|------|----------|
| URL / routing | React Router | caseUuid, tab, filters |
| Server resources | TanStack Query | workspace, messages, artifacts, saved cases |
| Ephemeral workflow | Local React state (M5/M6) or Zustand | analysis preview, grievance draft, dirty flags |
| Local UI | Zustand or component state | panel collapsed, selected citation id, toast queue |

### 12.2 Why this split

- **Routing as source of case identity** prevents “chat without a case” and enables refresh restore.
- **TanStack Query** matches REST resources with explicit invalidation after Save/Upload/Outcome — better than global Redux mirrors of the server.
- **Ephemeral local state (or Zustand) for previews/drafts** because temporary Generate payloads are intentionally **not** server resources until Save. M5 analysis preview and M6 grievance draft use local React state.
- Avoid optimistic Save for artifacts (versioning/Official Case Record must be server-authoritative). Optimistic UI is appropriate for chat steward messages and fact text edits with rollback.

### 12.3 Caching and invalidation

| Mutation | Invalidate / update |
|----------|---------------------|
| Interaction success | messages (append), available_actions, memory/overview if updated |
| Facts patch | workspace, memory, overview |
| Upload | assets, workspace |
| Generate analysis | none (client state only) |
| Save analysis | versions, artifacts, history, workspace, overview |
| Generate grievance | none (client state only) |
| Save grievance | grievance artifact list/detail, workspace, workflow |
| Open/reopen/close/settle | saved list + workspace |
| Outcome / workflow transition | workflow, memory, workspace, saved summary |

### 12.4 Polling vs refresh

| Resource | Strategy |
|----------|----------|
| Messages | Refresh on focus + after send; no polling |
| pdf_status pending | Short poll (2–3s, max ~30s) on artifact detail only |
| Saved case list | Refetch on window focus / interval 60s optional |
| Workspace | Refetch after mutations; not continuous poll |

### 12.5 Error handling and retry

- Query: retry 1–2 times on network 5xx/0; **do not** retry 4xx.
- Mutations: manual Retry buttons for interactions and generates.
- Idempotency keys on Save and Print (analysis + grievance).
- Global error boundary for render failures; route error elements for loader failures.

### 12.6 API abstraction

```text
src/
  api/
    client.ts          # base URL, headers, error normalize
    cases.ts
    interactions.ts
    reports.ts
    grievances.ts
    artifacts.ts
    assets.ts
    savedCases.ts
    sources.ts
    types/             # mirrored Pydantic types
  features/
    cases/
    conversation/
    analysis/
    grievance/
    artifacts/
    sources/
  stores/
    analysisPreviewStore.ts   # optional; M5 used local React state
    uiShellStore.ts
  # M6 grievance temporary draft: local React state in GrievancePanel (not a required Zustand store)
```

### Source administration and browser secrets

The W6 browser must not receive source API secrets. Never put
`GRIEVANCEHUB_API_KEY` or `GRIEVANCEHUB_ADMIN_API_KEY` into browser environment
variables (including any `VITE_*` key).

- Source administration remains deferred.
- Read-only source inspection may be implemented later only through an explicitly
  approved server-side boundary or another safe local-development mechanism.
- No source API key handling is part of M0.
- M0 does not expose a Sources navigation entry for this reason.

---

## 13. API mapping (screens → backend)

### 13.1 Dashboard / Cases list

| Item | Detail |
|------|--------|
| Endpoint | `GET /cases/saved` |
| Purpose | List steward cases |
| Request | Query: `status`, `step`, `search`, `order`, `limit`, `offset` |
| Response | `SavedCaseListResponse` |
| Loading | Table skeleton |
| Failure | Page error + retry |

### 13.2 Open / Reopen

| Item | Detail |
|------|--------|
| Endpoints | `POST /cases/saved/{uuid}/open`, `.../reopen` |
| Request | `{ source: "manual_ui" }` (+ reopen reason optional) |
| Response | summary + `workspace` |
| Loading | Row spinner / full-page transition |
| Failure | Toast; stay on list |

### 13.3 Create case

| Item | Detail |
|------|--------|
| Endpoint | `POST /cases/` |
| Request | `{ question, user_name?, local_number?, known_facts? }` |
| Response | `{ case, report_version: null }` |
| Loading | Submit busy |
| Failure | Inline form errors |

### 13.4 Workspace restore

| Item | Detail |
|------|--------|
| Endpoint | `GET /cases/{uuid}/workspace` |
| Purpose | Lean bootstrap (no full transcript) |
| Loading | 3-panel skeleton |
| Failure | Case not found page |

### 13.5 Messages

| Item | Detail |
|------|--------|
| Endpoint | `GET /cases/{uuid}/messages` |
| Purpose | Full transcript |
| Loading | Thread skeleton |
| Failure | Inline error in center panel |

### 13.6 Chat interaction

| Item | Detail |
|------|--------|
| Endpoint | `POST /cases/{uuid}/interactions` |
| Request | `CaseInteractionRequest` |
| Response | `CaseInteractionResponse` |
| Loading | Pending assistant placeholder |
| Failure | Failed turn + retry; show `retrieval_error` when set |

### 13.7 Facts / status

| Endpoint | Purpose |
|----------|---------|
| `PATCH /cases/{uuid}/facts` | Update known facts |
| `PATCH /cases/{uuid}/status` | Legacy status update (prefer saved-case close/settle/archive when applicable) |

### 13.8 Analysis generate / save

| Endpoint | Purpose | Failure |
|----------|---------|---------|
| `POST .../reports/generate` | Temporary preview | AI/retrieval failure message in modal |
| `POST .../reports/save-and-print` | Persist version + artifact | Validation / PDF failure statuses |
| `GET .../versions` | List | Empty state |
| `GET .../versions/{n}` | Body | Not found |
| `GET .../export/preview` | HTML preview | Error panel |
| `GET .../export/pdf?working_draft=` | PDF rules | `409` mapped to steward copy |

### 13.9 Grievance generate / save (M6 — Step 1/2 only)

| Endpoint | Purpose |
|----------|---------|
| `POST .../actions` `{ "action": "generate_grievance" }` | Temporary editable draft |
| `POST .../grievances/save-and-print` | Official artifact + optional PDF |
| `GET .../artifacts?artifact_type=grievance_form` | M6 saved Step 1/2 list (filter client-side to supported templates) |
| `GET .../artifacts/{id}` | Saved grievance detail |
| `GET .../artifacts/{id}/pdf` | Saved grievance PDF |

Prerequisites surfaced via `available_actions` / `missing_prerequisites` (`template_unavailable`, `case_closed_requires_reopen`, etc.). Official generation ends at Step 2.

### 13.10 Artifacts / history / memory / workflow

| Endpoint | Screen |
|----------|--------|
| `GET .../artifacts` | Artifact library |
| `GET .../artifacts/{id}` | Detail |
| `GET .../artifacts/{id}/pdf` | Download/preview |
| `POST .../artifacts/compare` | Compare |
| `GET /cases/saved/{id}/history` | Official Case Record |
| `GET /cases/saved/{id}/timeline` | Timeline |
| `GET .../history/{event_id}/context` | Jump context |
| `GET .../memory` | Memory page |
| `GET .../overview` | Overview refresh |
| `GET .../workflow` | Workflow page |
| `POST .../workflow/transitions` | Explicit transition |
| `POST .../outcomes` | Record step decision |

### 13.11 Assets

| Endpoint | Screen |
|----------|--------|
| `GET/POST .../assets` | Evidence |
| `GET .../assets/{id}` | Metadata |

### 13.12 Sources

| Endpoint | Auth | Screen |
|----------|------|--------|
| `GET /sources/`, `/search/`, `/ask/`, `/embedded/` | API key | Sources |
| Admin POSTs | Admin key | Optional admin |

### 13.13 Health

`GET /health` → shell connection indicator.

### 13.14 Do not use in W6 product UI

| Endpoint | Reason |
|----------|--------|
| `POST .../messages` | Legacy save-only |
| `POST .../followups` | Legacy Q&A |
| `POST .../reports/regenerate` | Immediate versioning legacy |
| `save_and_update_analysis` | Internal |
| `GET .../domain-events` | Internal (optional debug) |

---

## 14. Component hierarchy

Reusable components (**design only for later milestones**). Planned inventory: **64** components/modules below (feature panels + primitives).

### 14.1 Shell

- `AppShell`
- `TopBar`
- `SideNav`
- `CaseContextChip`
- `GlobalToastRegion`
- `ConfirmDialog`
- `EnvironmentBadge`
- `ConnectionStatus`

### 14.2 Cases

- `SavedCaseTable`
- `CaseCard` (compact dashboard variant)
- `CaseStatusBadge`
- `StepBadge`
- `CaseFiltersBar`
- `CreateCaseForm`
- `AvailableActionsMenu`

### 14.3 Workspace

- `CaseWorkspaceShell`
- `CaseRail` (left)
- `CaseOverviewSection`
- `FactsEditor`
- `IssuesList`
- `Timeline`
- `UploadSummary`
- `WorkspaceActionBar`
- `PanelTabs` (responsive collapse)

### 14.4 Conversation

- `ConversationPanel`
- `MessageList`
- `MessageBubble`
- `Composer`
- `RetrievalStatusBanner`
- `FactsNeededList`
- `DisclosureBanner`

### 14.5 Citations / research

- `CitationPanel`
- `CitationChip`
- `CitationDetail`
- `AuthorityList`
- `SourceQuoteBlock` (source text only)
- `GeneratedTextBlock` (analysis/recommendations)

### 14.6 Analysis

- `AnalysisPreview`
- `AnalysisReportView`
- `AnalysisVersionList`
- `ConfidenceBadge`
- `LimitationsPanel`
- `CitationValidationSummary`
- `SaveArtifactDialog` (Save vs Save and Print)

### 14.7 Grievance (M6)

- `GrievancePanel`
- `GrievanceDraftEditor`
- `DraftValidationSummary`
- `GrievanceSaveActions`
- `GrievanceArtifactList`
- `GrievanceArtifactDetail`
- `GrievancePdfActions`

### 14.8 Artifacts / history

- `ArtifactLibrary`
- `ArtifactViewer`
- `ArtifactCompareView`
- `OfficialCaseRecord`
- `HistoryContextModal`
- `PdfFrame`

### 14.9 Evidence / sources

- `UploadPanel`
- `AssetTable`
- `SourceBrowser`
- `SourceSearchPanel`

### 14.10 Feedback

- `EmptyState`
- `ErrorState`
- `LoadingSkeleton`
- `InlineAlert`

---

## 15. Design system

Enterprise legal/workflow — dense, calm, high-signal. Avoid chatbot chrome, purple gradients, cream/terracotta marketing looks, and neon glows.

### 15.1 Color tokens

| Token | Role | Suggested direction |
|-------|------|---------------------|
| `--bg-app` | App background | Cool neutral gray-blue (`#F4F6F8`) |
| `--bg-surface` | Panels | `#FFFFFF` |
| `--bg-subtle` | Rail / tables | `#EEF1F4` |
| `--border` | Hairline separators | `#D5DCE3` |
| `--text-primary` | Body | `#1B2430` |
| `--text-secondary` | Meta | `#5B6775` |
| `--accent` | Primary actions | Deep slate-blue `#1F4B7A` |
| `--accent-hover` | | `#163A5F` |
| `--success` | Saved / open | `#2F6F4E` |
| `--warning` | Unsaved preview / empty retrieval | `#8A6D1B` |
| `--danger` | Errors / closed destructive | `#8B2E2E` |
| `--source-quote-bg` | Source excerpts | `#F0F4F1` + left border green-gray |
| `--generated-bg` | Generated analysis | `#F7F8FA` + left border slate |
| `--recommend-bg` | Recommendations | `#F3F0FA` subtle (not purple UI chrome) |
| `--citation-chip` | | Border accent, transparent fill |

Status badges: solid soft backgrounds, not pills-with-glow.

### 15.2 Typography

| Role | Recommendation |
|------|----------------|
| UI sans | **IBM Plex Sans** or **Source Sans 3** |
| Document / report | **IBM Plex Serif** or **Source Serif 4** |
| Mono (UUIDs, field ids) | **IBM Plex Mono** |

Avoid Inter, Roboto, Arial, system-ui as the brand/UI face.

Scale (desktop): 12 meta / 13–14 body / 16 section / 20 panel title. Dense but readable.

### 15.3 Spacing

8px grid. Panel padding 12–16px. Table row height ~40px. Modal max-width 960px for analysis preview.

### 15.4 Components styling

| Element | Guidance |
|---------|----------|
| Cards | Prefer flat sections with borders; cards only for interactive containers (case row click targets OK). No hero cards. |
| Tables | Primary for case list and assets |
| Buttons | Solid primary, outline secondary, quiet tertiary; destructive separate |
| Alerts | Inline, icon + text + optional action |
| Icons | 16–20px outline; pair with text labels for primary actions |
| Status indicators | Dot + label; color not sole channel |

### 15.5 Content taxonomy (critical)

Every text block in analysis/chat must declare one of:

1. **Source excerpt**
2. **Generated analysis**
3. **Generated recommendation**
4. **Citation reference**
5. **Warning / limitation**

Use labels and left-border color coding consistently.

---

## 16. Accessibility

| Area | Requirement |
|------|-------------|
| Keyboard | All actions reachable; roving tabindex in message list optional; Action bar buttons in tab order |
| Focus | Focus trap in modals; return focus to trigger on close; route changes move focus to main `h1` |
| Skip link | “Skip to case content” |
| ARIA | `aria-live="polite"` for new assistant messages and toasts; `aria-busy` on generating; dialog roles on previews |
| Labels | Icon-only controls need `aria-label` |
| Contrast | WCAG AA for text/status; do not rely on color alone for retrieval failure |
| Screen readers | Citation chips announce document + page; unsaved preview announced as “unsaved temporary preview” |
| Responsive | Collapsed panels remain operable via tabs; no hover-only actions |
| Reduced motion | Respect `prefers-reduced-motion` for panel transitions |

---

## 17. Error handling

| Failure | UI behavior |
|---------|-------------|
| Network down | Connection badge + mutation errors; queue not required in W6 |
| API 5xx | Toast + Retry |
| Case not found | Dedicated empty page |
| AI / interaction failure | Failed turn in thread; Retry; optional copy of steward text |
| Retrieval empty | Inline empty-results in right panel + turn disclosure |
| Retrieval failed | Error in turn; do not fake citations |
| Missing sources / corpus | Sources page empty state; chat disclosures |
| Generate analysis failure | Modal error; keep prior saved versions intact |
| Generate grievance prerequisites | Disable + list missing prerequisites |
| Unsupported grievance template (not Step 1/2) | Concise notice; do not open editor or later-step placeholder cards |
| Invalid export / PDF 409 | Explain Save and Print requirement; offer working_draft preview when appropriate |
| `saved_pdf_failed` | Artifact exists; show PDF retry |
| Upload validation | Inline field/file errors from API |
| Expired sessions (future W9) | Reserved: redirect to login, preserve return URL; stub interceptor only |

Never display Python tracebacks or OpenAI raw errors to stewards. Log details to console in local/dev only.

---

## 18. Implementation order (milestones)

Each milestone is independently testable against the live W5 API.

| Milestone | Deliverable | Testable outcome |
|-----------|-------------|------------------|
| **M0 — Foundations** | Vite/React/TS app, design tokens, AppShell, apiClient, proxy, health | Shell loads; `/health` indicator works |
| **M1 — Saved cases** | Dashboard + Cases list + filters + open/reopen | Steward opens/reopens case into workspace shell |
| **M2 — Create + workspace restore** | Create case; CaseWorkspaceShell; left rail overview/facts/step | New case appears; workspace restores memory/overview |
| **M3 — Conversation** | **Complete** — Messages + interactions + citations + retrieval states | Chat with citations end-to-end; no artifacts created |
| **M4 — Evidence** | **Complete** — UploadPanel + asset table/detail + upload_refs in composer | Upload and reference in chat; not authority RAG |
| **M5 — Analysis** | **Complete** — Generate preview → Save / Save and Print → versions | Temporary vs saved clearly distinct; Official Case Record updates on Save |
| **M6 — Grievance** | **Complete** — Generate → Edit → Validate → Save / Save and Print → Step 1/2 PDF | Official Step 1/2 forms only; limited saved grievance list/detail/PDF |
| **M7 — Artifacts & history** | **Complete** — Library, detail, compare, Official Case Record, jump-to-context | Browse versions; download PDFs |
| **M8 — Workflow outcomes** | **Complete** — Record outcome, close/settle/archive, workflow view | Lifecycle without DB edits |
| **M9 — Sources research** | Source list/search/ask via approved safe boundary | Corpus inspection for RAG debugging (no browser API secrets) |
| **M10 — Polish & a11y** | Empty/error states, keyboard, print routes, regression hooks | Exit criteria checklist green |

**Engineering sequence rationale:** list → restore → chat (highest RAG signal) → uploads → explicit Generate flows → artifacts → lifecycle → sources admin → polish. This matches the roadmap’s vertical-slice and continuous RAG validation rules.

During M3–M6, log weak retrieval / bad citations as evaluation candidates for W7.

---

## 19. Engineering review

### 19.1 Architectural assessment

W5 already provides a coherent workspace API: restore, interact, generate, save-and-print, artifacts, memory, and workflow. W6 should be a **faithful client** of that model, not a second workflow engine. The highest product risk is UX drift toward “chatbot that writes grievances.” The shell, action bar, and temporary-vs-official visual language exist to prevent that drift.

### 19.2 Architectural risks

| Risk | Mitigation |
|------|------------|
| Chat accidentally framed as report generation | Persistent helper copy; no generate inside composer; separate Generate buttons |
| Temporary preview lost on refresh without warning | `beforeunload` when draft/preview present; amber unsaved badges |
| Treating uploads as searchable case RAG | Explicit disclosure; no fake “searching your PDF” copy |
| Calling legacy endpoints | Lint/code review checklist against §13.14 |
| Step 3 / later-form assumptions | Gate Generate on supported Step 1/2 `template_id` only; no placeholder later-step UI |
| Premature auth work | No login UI in W6; no browser-held source API keys |
| UI-complete but RAG-untested | M3 early; capture fixtures for W7 |
| Over-fetching full transcripts into client state | Paginate messages; workspace stays lean |

### 19.3 Technical debt avoided

- Not inventing a BFF that re-orchestrates Generate/Save
- Not duplicating Case Memory on the client as source of truth
- Not using legacy followups/regenerate paths
- Not building multi-agent UI for W8
- Not building identity before W9
- Keeping FastAPI `/ui` until SPA parity rather than a big-bang cutover

### 19.4 Questions to answer before coding

1. **Monorepo location:** `frontend/` at repo root vs separate package — recommend `frontend/` in this repo for W6.
2. **Create-case first message:** auto-send `question` as first interaction or wait for steward? (Recommend wait.)
3. **Save vs Save and Print PDF default:** confirm `prepare_pdf` false/true split.
4. **Analysis preview chrome:** modal vs full analysis route — recommend modal from action bar + route for deep review.
5. **Sources access UX:** the browser must not receive source API secrets. Defer
   Sources UI until an approved server-side boundary or other safe local-development
   mechanism exists. Do not use `VITE_GRIEVANCEHUB_API_KEY`.
6. **Print routes:** browser print of HTML export vs PDF iframe — support both; PDF authoritative for official forms.
7. **Multi-tab stewards:** accept last-write-wins for facts; no CRDT in W6.
8. **Type generation:** hand-written vs openapi-typescript from `/openapi.json` — recommend generate CI helper by M5.

### 19.5 Recommendations for implementation

1. Start M0–M3 quickly to exercise retrieval daily.
2. Mirror TS types from `case_workspace_action_schema.py`, `saved_case_schema.py`, `case_saved_artifact_schema.py` first.
3. Put temporary preview/draft exclusively in ephemeral client state (local React state is fine; Zustand optional); never write them into Query cache as “versions.”
4. Centralize action availability rendering from `available_actions`.
5. Add Playwright flows for: open case → chat → generate analysis → save → generate grievance → save and print.
6. Keep `/ui` shell for backend verification until M7.
7. File UI-discovered backend defects with pytest regressions in the same PR when practical.

### 19.6 Estimated implementation milestones

| Milestone | Calendar estimate (1 experienced FE + API access) |
|-----------|---------------------------------------------------|
| M0 | 1–2 days |
| M1 | 2–3 days |
| M2 | 2–3 days |
| M3 | 3–5 days |
| M4 | 1–2 days |
| M5 | 3–5 days |
| M6 | 3–5 days |
| M7 | 2–3 days |
| M8 | 2–3 days |
| M9 | 1–2 days |
| M10 | 2–4 days |
| **Total** | **~4–6 weeks** calendar, assuming parallel defect fixes in backend |

Estimates assume the W5 API remains stable; any backend gaps found during M3–M6 are fixed with minimal contract changes and tests, not redesign.

---

## 20. Exit criteria mapping

| Roadmap exit criterion | How this architecture satisfies it |
|------------------------|------------------------------------|
| Core case workflow through UI | M1–M8 routes and actions |
| Retrieval in normal workflow | M3 interactions + citation panel |
| Citations visible/traceable | Citation chips + detail + analysis authorities |
| Analysis separated from sources | Design taxonomy §15.5 + AnalysisPreview structure |
| Grievance preview/generate | M6 GrievancePanel / GrievanceDraftEditor + Step 1/2 official forms |
| Official forms from workflow | Save and Print → PDF frame |
| Failures without stack traces | §17 mapping |
| Regression tests for defects | M10 + ongoing |
| No DB/script dependency | All steward paths via documented APIs |

---

## 21. Document control

| Item | Value |
|------|-------|
| Path | `docs/W6_UI_ARCHITECTURE.md` |
| Phase | W6 Interactive Steward Workspace — M0–M8 complete |
| Implementation | M0–M8 complete (Foundations through Workflow outcomes); M9–M10 planned |
| Supersedes | None (complements `saved_cases_ui_contract.md`) |
| Next step | M9 Sources research |

---

*End of W6 UI Architecture specification.*
