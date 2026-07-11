# Saved Cases UI Contract (Phase 1.4F + AI-first workspace correction)

Frontend for saved cases is **deferred** until Phase 4 steward UI. This document
defines the route/component contract so a future React/Next.js screen can plug
into the existing backend without inventing a parallel workflow.

## Permanent product principle

**The application manages the workflow. The steward manages the grievance.**

The steward must never be required to click separate controls for:

- Save Context
- Update Analysis
- Reanalyze
- Refresh Report
- Start Chat

Those are system responsibilities. The steward explains what happened, asks
questions, adds or corrects context, uploads evidence, reviews analysis, and
optionally chooses **Generate Grievance**.

## AI-first case workspace

GrievanceHub is an AI-first grievance case workspace — not an app with a chatbot
attached. Whenever a steward creates, opens, or reopens a case, the workspace
contains an **active case-specific AI conversation**, ready immediately.

Each case owns its own conversation. Context from one case must never bleed into
another case.

### Where chat appears

Persistent AI chat belongs on active case-work pages, for example:

- New Case
- Existing Case / Case Workspace
- Reopened Case
- Evidence Review
- Analysis Review
- Grievance Workspace (before final print/finalization)

Chat must **not** appear on non-interactive or administrative/output pages:

- Print Preview / PDF Viewer / Final Print/Export
- Login / Settings
- Administrative configuration
- Source-management pages (unless later designed for an admin assistant)

### Automatic chat submission behavior

Every submitted steward chat interaction must automatically:

1. Persist the steward message and AI response
2. Preserve prior conversation
3. Merge safe fact updates and associate referenced Case Assets
4. Build cumulative case context
5. Run the full grievance analysis pipeline once
6. Create one new immutable analysis report version (prior versions retained)
7. Advance Current Analysis via latest-version semantics
8. Append timeline events
9. Return the AI reply plus refreshed workspace state
10. Return whether Generate Grievance is available

The chat submission **is** the workflow. No separate Update Analysis action.

## Backend endpoints (do not duplicate)

| Method | Route | Purpose | Status |
|--------|-------|---------|--------|
| `POST` | `/cases/{case_uuid}/interactions` | **Canonical** case chat + automatic analysis refresh | Preferred |
| `POST` | `/cases/{case_uuid}/actions` | Explicit actions (`generate_grievance`; compatibility `save_and_update_analysis`) | Generate Grievance = W5 |
| `GET` | `/cases/saved` | List saved cases | Current |
| `GET` | `/cases/saved/{case_uuid}` | Saved case summary/detail | Current |
| `POST` | `/cases/saved/{case_uuid}/open` | Open an active case workspace | Current |
| `POST` | `/cases/saved/{case_uuid}/reopen` | Reopen a closed case | Current |
| `GET` | `/cases/saved/{case_uuid}/timeline` | Case step/timeline history | Current |
| `GET` | `/cases/{case_uuid}/workspace` | Full workspace payload (includes assets) | Current |

### Compatibility routes (do not present as alternate UI chat paths)

| Method | Route | Note |
|--------|-------|------|
| `POST` | `/cases/{uuid}/messages` | Legacy message + regen |
| `POST` | `/cases/{uuid}/followups` | Legacy grounded Q&A without unified workspace refresh |
| `POST` | `/cases/{uuid}/reports/regenerate` | Legacy explicit regen |
| `POST` | `/cases/{uuid}/actions` + `save_and_update_analysis` | Internal/compatibility analysis refresh — **`steward_visible: false`** |

Future UI must not present multiple confusing ways to chat or update analysis.
One submitted `/interactions` call must not double-generate analysis versions.

Manual click reopen and future AI-command reopen **must** call
`POST /cases/saved/{case_uuid}/reopen` with `source` set to `manual_ui` or
`ai_command`. There is no separate UI reopen service.

After open/reopen succeeds, navigate to the case workspace:
`GET /cases/{case_uuid}/workspace`. Chat is active immediately with prior
history loaded. Workspace responses include first-class `assets` /
`uploaded_assets` (Phase W3).

## Case assets (Phase W3)

| Method | Route | Purpose |
|--------|-------|---------|
| `GET` | `/cases/{case_uuid}/assets` | List case assets (optional `category`) |
| `POST` | `/cases/{case_uuid}/assets` | Upload `uploaded_document` (multipart) |
| `GET` | `/cases/{case_uuid}/assets/{asset_uuid}` | Asset metadata |

Only `uploaded_document` is executable in W3. Other categories
(`generated_report`, `generated_grievance`, `future_export`,
`future_attachment`) are reserved for later phases.

Chat interactions may reference asset UUIDs via `upload_refs`; those assets
become part of cumulative case context.

## Python client helper

`app/clients/saved_case_client.py` — `SavedCaseApiClient` wraps saved-case
endpoints. Use `resolve_case_click_action()` and `activate_case()` for row-click
behavior. Future client work should add an interactions helper that calls
`POST /cases/{uuid}/interactions` (not a separate Update Analysis button).

## Screen: Saved Cases

**Route (proposed):** `/cases/saved` or `/saved-cases`

**Data source:** `GET /cases/saved?order=newest_first`

### List row / card fields

Display when available (never invent missing values):

| Field | Schema key |
|-------|------------|
| Case number | `case_number` |
| Case UUID (secondary) | `case_uuid` |
| Title | `title` |
| Issue summary | `issue_summary` |
| Current step | `current_step_type` |
| Step status | `current_step_status` |
| Workspace status | `workspace_status` |
| Last activity | `last_activity_at` |
| Created | `created_at` |
| Closed | `closed_at` (when closed) |
| Reopened | `reopened_at` (when reopened) |
| Latest outcome | `latest_outcome_summary` / `latest_outcome_type` |
| Available actions | `available_actions` |

### Row click behavior

1. **Closed case** (`workspace_status === "closed"`): call
   `POST /cases/saved/{case_uuid}/reopen` with `{ "source": "manual_ui" }`.
2. **Open / reopened / appealed case**: call
   `POST /cases/saved/{case_uuid}/open` with `{ "source": "manual_ui" }`.
3. On success, route steward to case workspace for `case_uuid` with chat ready.

Client equivalent: `SavedCaseApiClient.activate_case(summary)`.

### Explicit action buttons

Render from `available_actions` where `steward_visible !== false`:

| Action | When shown | API call |
|--------|------------|----------|
| Open | `open_case` in `available_actions` | `POST .../open` |
| Reopen | `reopen_case` in `available_actions` | `POST .../reopen` |
| Timeline | `view_timeline` in `available_actions` | `GET .../timeline` |
| Generate Grievance | workspace `generate_grievance` available | `POST /cases/{uuid}/actions` |

Do **not** render Update Analysis / Save Context / Reanalyze buttons.

### Timeline panel (optional v1)

When steward selects Timeline:

- Request `GET /cases/saved/{case_uuid}/timeline?order=oldest_first`
- Render `events[]` with `event_type`, `title`, `event_timestamp`
- Default sort: oldest first (chronological history)

## Filters (optional v1)

- Status: `all` | `open` | `closed` | `reopened` | `appealed`
- Step: `step_1_initial` | `step_2_appeal` | `step_3_arbitration`
- Search: uuid, title, or numeric case id
- Order: `newest_first` (default) | `oldest_first`

## Canonical workspace contract (AI-first)

| Steward experience | API |
|--------------------|-----|
| Persistent case chat (always present) | `POST /cases/{case_uuid}/interactions` |
| Generate Grievance (optional explicit) | `POST /cases/{case_uuid}/actions` `{ "action": "generate_grievance" }` (W5) |

After each successful interaction, UI may show system status such as:

- Analysis updated
- Current Analysis: Version N
- Generate Grievance available/unavailable

Those are confirmations — not buttons the steward must manage.

### Generate Grievance template rules (unchanged)

- Step 1 template unavailable
- Step 2 Local 300 Form 79-1 available when progression prerequisites are met
- Step 3 template deferred

## Out of scope (this contract phase)

- Frontend implementation
- Generate Grievance execution (W5)
- Grievance print/export
- Source ingestion
- Production authentication (Phase 1.7)

## TypeScript types (future)

Mirror `app/schemas/saved_case_schema.py` and
`app/schemas/case_workspace_action_schema.py` (`CaseInteractionRequest` /
`CaseInteractionResponse`) when the frontend is implemented.
