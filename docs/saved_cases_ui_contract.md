# Saved Cases UI Contract (Phase 1.4F)

Frontend for saved cases is **deferred** until Phase 4 steward UI. This document
defines the route/component contract so a future React/Next.js screen can plug
into the existing Phase 1.4E backend without a duplicate reopen workflow.

## Backend endpoints (do not duplicate)

| Method | Route | Purpose |
|--------|-------|---------|
| `GET` | `/cases/saved` | List saved cases (filters: `status`, `step`, `search`, `order`) |
| `GET` | `/cases/saved/{case_uuid}` | Saved case summary/detail |
| `POST` | `/cases/saved/{case_uuid}/open` | Open an active case workspace |
| `POST` | `/cases/saved/{case_uuid}/reopen` | Reopen a closed case (manual UI **and** AI command) |
| `GET` | `/cases/saved/{case_uuid}/timeline` | Case step/timeline history |

Manual click reopen and future AI-command reopen **must** call
`POST /cases/saved/{case_uuid}/reopen` with `source` set to `manual_ui` or
`ai_command`. There is no separate UI reopen service.

After open/reopen succeeds, navigate to the case workspace:
`GET /cases/{case_uuid}/workspace` (existing Phase 1.2 route).

## Python client helper

`app/clients/saved_case_client.py` — `SavedCaseApiClient` wraps the endpoints
above. Use `resolve_case_click_action()` and `activate_case()` for row-click
behavior.

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
3. On success, route steward to case workspace for `case_uuid`.

Client equivalent: `SavedCaseApiClient.activate_case(summary)`.

### Explicit action buttons

Render from `available_actions`:

| Action | When shown | API call |
|--------|------------|----------|
| Open | `open_case` in `available_actions` | `POST .../open` |
| Reopen | `reopen_case` in `available_actions` | `POST .../reopen` |
| Timeline | `view_timeline` in `available_actions` | `GET .../timeline` |

Closed cases must show **Reopen** (not a separate reopen code path).

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

## Out of scope (Phase 1.4F)

- PDF/DOCX export
- Source ingestion
- Generated filled forms
- Production authentication (Phase 1.7)
- OpenAI / AI-command UI (backend `source=ai_command` already supported)

## TypeScript types (future)

Mirror `app/schemas/saved_case_schema.py` Pydantic models when the frontend
is implemented. Key enums: `SavedCaseWorkspaceStatus`, `SavedCaseAction`,
`ReopenSource`.
