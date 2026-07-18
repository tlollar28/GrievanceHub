# Saved Cases UI Contract

Frontend for a production saved-cases screen is deferred. No React/Next.js app
exists in this repository. A FastAPI HTML verification shell at `/ui` implements
the current interaction model for local verification.

This document defines the route and component contract so a future production
screen can use the existing backend without inventing a parallel workflow.

**Docs sync:** 2026-07-18 — W4 steward-controlled artifacts; chat retrieves from
the indexed corpus; W5 = Local 300 Form 79-1 overlay PDF assembly.

## Product principle

**The application manages the workflow. The steward manages the grievance.**

The UI should not require separate steward controls for Save Context, Update
Analysis, Reanalyze, Refresh Report, or Start Chat. Continuous chat persists
conversation, retrieves indexed sources, and may update Case Memory. Analysis
reports and grievances are created only when the steward chooses **Generate
Analysis Report** or **Generate Grievance**.

## Case workspace expectations

When a steward creates, opens, or reopens a case, the workspace presents an
active case-specific AI conversation. Each case owns its own conversation;
context is not shared across cases.

### Where chat belongs

Include persistent AI chat on active case-work pages such as:

- New Case
- Existing Case / Case Workspace
- Reopened Case
- Evidence Review
- Analysis Review
- Grievance Workspace (before final print)

Omit chat from non-interactive or administrative/output pages such as print
preview, login, settings, and source-management screens.

### Chat submission behavior

On each successful `POST /cases/{case_uuid}/interactions` the backend:

1. Loads Case Memory and bounded conversation/workflow context
2. Retrieves relevant passages from the configured indexed source corpus
3. Returns a conversational answer with citations when sources are found
4. Persists steward and assistant messages
5. Updates Case Memory when durable meaning is present
6. Returns refreshed action availability

Chat does not:

- Run the full analysis-report construction pipeline
- Create a `CaseReportVersion`
- Create a saved artifact
- Append ordinary chat noise to the Official Case Record

Analysis reports use Generate → temporary preview → Save / Save and Print /
Cancel. Grievances use Generate → temporary editable draft → Save / Save and
Print / Cancel.

## Backend endpoints

| Method | Route | Purpose | Status |
|--------|-------|---------|--------|
| `POST` | `/cases/{case_uuid}/interactions` | Canonical case chat + retrieval | Preferred |
| `POST` | `/cases/{case_uuid}/reports/generate` | Generate Analysis Report (temporary preview) | Current |
| `POST` | `/cases/{case_uuid}/reports/save-and-print` | Save / Save and Print analysis | Current |
| `POST` | `/cases/{case_uuid}/actions` | `generate_analysis_report`, `generate_grievance`; compatibility `save_and_update_analysis` | Current / overlay deferred |
| `POST` | `/cases/{case_uuid}/grievances/save-and-print` | Save / Save and Print grievance | Current |
| `GET` | `/cases/{case_uuid}/artifacts` | Artifact library (+ groups) | Current |
| `GET` | `/cases/saved` | List saved cases | Current |
| `GET` | `/cases/saved/{case_uuid}` | Saved case summary/detail | Current |
| `POST` | `/cases/saved/{case_uuid}/open` | Open active case (returns restored `workspace`) | Current |
| `POST` | `/cases/saved/{case_uuid}/reopen` | Reopen closed case (returns restored `workspace`) | Current |
| `GET` | `/cases/saved/{case_uuid}/timeline` | Case timeline history | Current |
| `GET` | `/cases/{case_uuid}/workspace` | Restored workspace | Current |

### Compatibility routes

| Method | Route | Note |
|--------|-------|------|
| `POST` | `/cases/{uuid}/messages` | Legacy message path |
| `POST` | `/cases/{uuid}/followups` | Legacy grounded Q&A |
| `POST` | `/cases/{uuid}/reports/regenerate` | Legacy regen |
| `POST` | `/cases/{uuid}/actions` + `save_and_update_analysis` | Internal compatibility (`steward_visible: false`) |

Future UI should use one primary chat path (`/interactions`). Open/reopen should
call the saved-case routes with `source` set to `manual_ui` or `ai_command`.

After open/reopen, use the restored `workspace` payload (or
`GET /cases/{case_uuid}/workspace`). Chat is available immediately. Case Memory
and bounded `ai_continuity_context` support continuity without replaying the
full transcript into every request.

## Case assets

| Method | Route | Purpose |
|--------|-------|---------|
| `GET` | `/cases/{case_uuid}/assets` | List case assets |
| `POST` | `/cases/{case_uuid}/assets` | Upload `uploaded_document` |
| `GET` | `/cases/{case_uuid}/assets/{asset_uuid}` | Asset metadata |

Chat may reference asset UUIDs via `upload_refs`.

## Python client helper

`app/clients/saved_case_client.py` wraps saved-case endpoints. Use
`resolve_case_click_action()` and `activate_case()` for row-click open/reopen
behavior. Future helpers can wrap `/interactions`, `/reports/generate`, and
`generate_grievance`.

## Screen: Saved Cases

**Proposed production route:** `/cases/saved` or `/saved-cases`  
**Current verification shell:** `GET /ui`  
**Data source:** `GET /cases/saved?order=newest_first`

### List fields

| Field | Schema key |
|-------|------------|
| Case number | `case_number` |
| Case UUID | `case_uuid` |
| Title | `title` |
| Issue summary | `issue_summary` |
| Current step | `current_step_type` |
| Step status | `current_step_status` |
| Workspace status | `workspace_status` |
| Last activity | `last_activity_at` |
| Created / closed / reopened | `created_at`, `closed_at`, `reopened_at` |
| Latest outcome | `latest_outcome_summary` / `latest_outcome_type` |
| Available actions | `available_actions` |

### Row click behavior

1. Closed case → `POST /cases/saved/{case_uuid}/reopen` with `{ "source": "manual_ui" }`
2. Open / reopened / appealed → `POST /cases/saved/{case_uuid}/open` with `{ "source": "manual_ui" }`
3. On success, navigate to the case workspace with chat ready

### Explicit action buttons

Render from `available_actions` where `steward_visible !== false`:

| Action | API |
|--------|-----|
| Open | `POST .../open` |
| Reopen | `POST .../reopen` |
| Timeline | `GET .../timeline` |
| Generate Analysis Report | `POST /cases/{uuid}/reports/generate` |
| Generate Grievance | `POST /cases/{uuid}/actions` |

The production workspace exposes Generate Analysis Report and Generate Grievance
as the steward artifact actions. Save Context / Update Analysis / Reanalyze are
not separate steward controls.

### Review modals

- Analysis: read-only temporary preview with Save / Save and Print / Cancel
- Grievance: editable temporary draft with Save / Save and Print / Cancel
- Cancel discards the temporary payload with no version, artifact, or Official Case Record event

## Filters (optional)

- Status: `all` | `open` | `closed` | `reopened` | `appealed`
- Step: `step_1_initial` | `step_2_appeal` | `step_3_arbitration`
- Search: uuid, title, or numeric case id
- Order: `newest_first` (default) | `oldest_first`

## Out of scope for this contract

- Production React implementation
- Full Local 300 overlay PDF assembly (next phase)
- Source ingestion tooling
- Production authentication

## TypeScript types (future)

Mirror `app/schemas/saved_case_schema.py` and
`app/schemas/case_workspace_action_schema.py` when the frontend is implemented.
