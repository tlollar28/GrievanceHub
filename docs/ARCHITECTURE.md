# GrievanceHub Architecture

Technical system design for the current GrievanceHub backend through W5, plus the
W6 M0–M5 frontend steward shell now present on `main`.

For a concise product overview, see [`README.md`](../README.md). For the
canonical post-W5 delivery plan, see [`docs/ROADMAP.md`](ROADMAP.md). For the W6
UI blueprint, see [`docs/W6_UI_ARCHITECTURE.md`](W6_UI_ARCHITECTURE.md).

---

## 1. System overview

GrievanceHub is a FastAPI service that manages persistent grievance case workspaces. The unit of work is a long-lived `GrievanceCase`. Conversation, Case Memory, evidence, reports, grievances, artifacts, and workflow state remain attached to that case across open, close, and reopen.

```text
React steward shell (frontend/) / API client / /ui shell
        │
        ▼
   FastAPI routers
   (/cases, /sources, exports, /ui, /health)
        │
        ▼
   Service layer
   (workspace, memory, workflow, retrieval, artifacts)
        │
        ├─► PostgreSQL 16 + pgvector
        └─► Local filesystem storage (case assets, generated reports)
```

### Frontend steward shell (W6 M0–M5)

`frontend/` is a Vite + React + TypeScript application. Implemented:

- **M0:** Application shell (TopBar, SideNav, outlet), routing foundations,
  TanStack Query, typed `fetch` API client, FastAPI health indicator via
  `GET /api/health` (Vite proxy → `/health`), design tokens, a11y foundations
- **M1:** Saved Cases dashboard/list (`GET /cases/saved`), URL filters/search/
  pagination, open/reopen into `/cases/:caseUuid`
- **M2:** Create Case (`POST /cases/` from `/cases/new`), durable workspace
  restore (`GET /cases/{uuid}/workspace`), reusable `CaseWorkspaceShell` with
  Case context header and left Case Rail (overview, Case Memory, workflow,
  timeline/upload summaries), known-facts editing (`PATCH /cases/{uuid}/facts`)
- **M3:** Case conversation on `/cases/:caseUuid/conversation` (default child of
  the workspace layout). Message history via `GET /cases/{uuid}/messages`
  (paginated; default `limit=50`, `order=oldest_first`). Turns via
  `POST /cases/{uuid}/interactions` with `{ message, source: "manual_ui" }`
  (request/response only — no SSE/WebSocket). Retrieval statuses
  `ok | empty | failed | skipped`, citation chips + research panel (FollowUpCitation
  shape), disclosures, and facts-needed CTAs into the Known Facts editor.
  Interaction cache reconciliation merges persisted `user_message` /
  `assistant_message` by id; Case Memory / workspace queries invalidate only when
  `case_memory_update_status === "updated"`. Normal chat does not create reports,
  grievances, or artifacts.
- **M4:** Evidence on `/cases/:caseUuid/evidence` with case-scoped asset list
  (`GET /cases/{uuid}/assets`), multipart upload (`POST /cases/{uuid}/assets`
  with `file`, `category=uploaded_document`, `source=manual_ui`, optional
  `uploaded_by`), and metadata detail (`GET /cases/{uuid}/assets/{asset_uuid}`).
  Conversation composer can attach current-case asset UUIDs as `upload_refs`.
  Uploaded evidence is stored as a case asset reference (`content_embedded=false`
  in continuity); it is not indexed, embedded, or searched as authority-corpus
  RAG. Storage paths from the API are never rendered.
- **M5:** Analysis on `/cases/:caseUuid/analysis`. Explicit
  `POST /cases/{uuid}/reports/generate` returns a temporary read-only preview
  (`persisted: false`, `report_version: null`) held only in ephemeral client
  state. Cancel discards without Save. Persistence uses
  `POST /cases/{uuid}/reports/save-and-print` with the preview payload,
  client `idempotency_key`, and `prepare_pdf: false` (Save) or `true` (Save and
  Print). Statuses `saved` / `saved_pdf_failed` / `idempotent_replay` are
  steward-facing. Saved versions use `GET /cases/{uuid}/versions` and
  `GET /cases/{uuid}/versions/{n}`. Exports use version-scoped HTML/PDF routes
  with official PDF requiring prior Save and Print (`409` otherwise;
  `working_draft=true` for non-official preview). Legacy
  `POST .../reports/regenerate` is not used by the W6 UI.

Query ownership:

- Workspace: `["caseWorkspace", caseUuid]`
- Messages: `["caseMessages", "list", caseUuid, { limit, offset, order }]`
- Assets: `["caseAssets", "list", caseUuid, { category }]` /
  `["caseAssets", "detail", caseUuid, assetUuid]`
- Analysis versions: `["analysisVersions", "list", caseUuid]` /
  `["analysisVersion", caseUuid, versionNumber]`

Open/reopen may seed the workspace cache; the workspace layout refetches on mount
and treats the server response as authoritative. Message history is loaded when
the Conversation panel mounts and is not embedded in the lean workspace payload.
Asset lists are case-scoped and invalidated only for the affected case after upload.

The W6 browser must not receive source API secrets
(`GRIEVANCEHUB_API_KEY` / `GRIEVANCEHUB_ADMIN_API_KEY`). Sources UI remains
deferred until an approved safe boundary exists.
### Implementation lineage

Historical commits use earlier internal labels such as `Phase 0`, `Phase 1.x`,
`Phase 2`, and `Phase 3`. The current public engineering roadmap maps the
resulting architecture to:

| Milestone | Architectural scope |
|-----------|---------------------|
| W1 — Case Interaction Contract | Canonical interaction/action schemas and service boundaries |
| W2 — AI Case Interaction Orchestration | Persistent chat, bounded context, retrieval, grounded answers, and analysis orchestration foundations |
| W3 — Case Evidence and Asset Management | Case assets, uploads, metadata, safe storage, and case-context references |
| W4 — Case Lifecycle, Memory, Workflow, and Artifacts | Workspace restoration, Case Memory, domain events, workflow FSM, steward-controlled Generate/Save actions, artifacts, and Official Case Record |
| W5 — Knowledge Foundation | Official Step 1/Step 2 forms, Supervisor Manuals, source lifecycle metadata, bounded retrieval agents, and interim `/sources` API-key safety boundary |

The historical labels remain in Git history but are not the current public
roadmap.

### Workspace paths

```text
Persistent Case Workspace
    │
    ├── Continuous AI Conversation
    │       ├── Case Memory
    │       ├── Bounded Conversation Context
    │       ├── Relevant Source Retrieval
    │       └── Grounded Conversational Answer
    │
    ├── Generate Analysis Report
    │       ├── Full Case Context
    │       ├── Structured RAG Analysis Pipeline
    │       └── Read-only Temporary Preview
    │
    └── Generate Grievance
            └── Editable Temporary Field-Value Draft

Save / Save and Print
      ↓
Versioned Artifacts
      ↓
Official Case Record
```

Chat and analysis share retrieval infrastructure. Chat does not run the full report-construction pipeline. Analysis reports and grievances are created only through explicit steward actions.

---

## 2. Request lifecycle

1. HTTP request reaches a FastAPI router.
2. Input is validated with Pydantic schemas.
3. A service method executes against a SQLAlchemy session.
4. The service may update case state, emit domain events, project Case Memory, transition workflow state, retrieve indexed sources, or persist artifacts.
5. A typed response envelope is returned.

Canonical chat:

```http
POST /cases/{case_uuid}/interactions
```

Explicit analysis preview:

```http
POST /cases/{case_uuid}/reports/generate
```

Persistence / versioning:

```http
POST /cases/{case_uuid}/reports/save-and-print
POST /cases/{case_uuid}/grievances/save-and-print
```

---

## 3. FastAPI application

Entry point: `app/main.py`.

| Router | Module | Responsibility |
|--------|--------|----------------|
| Cases | `app/api/routes/cases.py` | Case lifecycle, workspace, chat, actions, memory, workflow, artifacts, assets |
| Sources | `app/api/routes/sources.py` | Source ingest and search helpers |
| Exports | `app/api/routes/exports.py` | HTML/PDF export of saved analysis versions |
| Steward UI | `app/api/routes/steward_ui.py` | FastAPI HTML verification shell (`/ui`) |
| Health | `GET /health` | Service liveness |

---

## 4. API surface (case workspace)

| Method | Route | Behavior |
|--------|-------|----------|
| `POST` | `/cases/` | Create case; initialize progression and Case Memory |
| `GET` | `/cases/saved` | Dashboard list |
| `POST` | `/cases/saved/{uuid}/open` | Open case; return restored workspace |
| `POST` | `/cases/saved/{uuid}/reopen` | Reopen case; return restored workspace |
| `GET` | `/cases/{uuid}/workspace` | Lean restored workspace |
| `POST` | `/cases/{uuid}/interactions` | Continuous AI chat with source retrieval |
| `POST` | `/cases/{uuid}/reports/generate` | Temporary analysis preview |
| `POST` | `/cases/{uuid}/reports/save-and-print` | Persist analysis version (+ optional PDF) |
| `POST` | `/cases/{uuid}/actions` | `generate_analysis_report`, `generate_grievance`, compatibility refresh |
| `POST` | `/cases/{uuid}/grievances/save-and-print` | Persist grievance artifact (+ optional PDF) |
| `GET` | `/cases/{uuid}/artifacts` | Artifact library |
| `GET/POST` | `/cases/{uuid}/assets` | Case asset upload/list |
| `GET` | `/cases/{uuid}/memory` | Case Memory |
| `GET` | `/cases/{uuid}/overview` | Case Overview |
| `GET/POST` | `/cases/{uuid}/workflow...` | Workflow state and transitions |

Compatibility routes (`/messages`, `/followups`, `/reports/regenerate`, `save_and_update_analysis`) remain for API clients and are not primary steward UI paths.

---

## 5. Pydantic schemas

Contracts live under `app/schemas/`.

| Module | Role |
|--------|------|
| `case_workspace_action_schema.py` | Chat and Generate action envelopes |
| `case_memory_schema.py` | Case Memory and Case Overview |
| `case_domain_event_schema.py` | Domain-event payloads |
| `case_workflow_schema.py` | Workflow states, transitions, outcomes |
| `case_saved_artifact_schema.py` | Save/Print and artifact groups |
| `case_history_context_schema.py` | Jump-to-context windows |
| `saved_case_schema.py` | Saved-case list/open/reopen |
| `report_schema.py` | Structured analysis report |
| `case_asset_schema.py` | Upload metadata |

---

## 6. Service layer

| Concern | Primary module |
|---------|----------------|
| Case create / workspace restore | `case_service.py` |
| Saved list / open / reopen | `saved_case_service.py` |
| Chat and Generate actions | `case_workspace_action_service.py` |
| Conversational answers | `follow_up_chat_service.py` |
| Case Memory | `case_memory_service.py` |
| Domain events | `case_domain_event_service.py` |
| Workflow FSM | `case_workflow_service.py` |
| Saved artifacts | `case_saved_artifact_service.py` |
| Case assets | `case_asset_service.py` |
| Indexed retrieval | `knowledge_retrieval_service.py` |
| Analysis orchestration | `analysis_service.py` |
| Report HTML/PDF | `report_export_service.py` |

---

## 7. Persistence stack

| Component | Role |
|-----------|------|
| PostgreSQL 16 | Primary datastore |
| pgvector | Embedding similarity search |
| SQLAlchemy | ORM (`app/database/models.py`) |
| Alembic | Schema migrations (`alembic/versions/`) |

### Core models

`GrievanceCase`, `CaseMessage`, `CaseReportVersion`, step/timeline/draft records, `CaseAsset`, `CaseMemoryRecord`, `CaseDomainEvent`, `CaseSavedArtifact`.

### Recent migrations

| Migration | Adds |
|-----------|------|
| `e6f7a8b9c0d1_...` | `case_saved_artifacts`, draft fields |
| `f7a8b9c0d1e2_...` | `case_memories` |
| `g8b9c0d1e2f3_...` | `case_domain_events`, `workflow_state` |

---

## 8. Case creation and workspace restoration

Case creation initializes step progression and Case Memory in the same transaction. It does not create an analysis report.

**Create (`POST /cases/`):** request fields are `question` (required), optional
`user_name`, `local_number`, `known_facts`. Response is
`{ case, report_version: null }` — case metadata/detail only, not a workspace
payload. OpenAPI lists `limit_per_source` on the request model, but the create
route does not pass it to `CaseService.create_case`.

**Workspace (`GET /cases/{case_uuid}/workspace`)** (also returned by open/reopen)
restores:

- Case identity, `known_facts`, and status
- `case_memory` and `case_overview` (embedded; separate `/memory` and
  `/overview` routes also exist)
- Saved analysis history summaries
- Assets / upload summary and artifact summaries when present
- Timeline slice and Official Case Record history slice
- Step progression and available actions
- Bounded `ai_continuity_context` (not rendered as chat UI in M2)

**Facts (`PATCH /cases/{case_uuid}/facts`):** body `{ known_facts: dict }`
replaces the full facts object and returns a case list summary (not workspace).

Full transcript remains available via `GET /cases/{case_uuid}/messages`.
Workspace restore does not embed the entire conversation (`messages: []`).

---

## 9. Conversation lifecycle

```text
Steward message
    ↓
Load Case Memory
    ↓
Load bounded recent conversation
    ↓
Load relevant case and workflow context
    ↓
Construct a retrieval query
    ↓
Search the configured indexed source corpus
    ↓
Apply relevance and citation-grounding controls
    ↓
Generate a conversational grounded answer
    ↓
Return relevant citations
    ↓
Persist the conversation
    ↓
Update Case Memory when durable meaning is present
```

Normal chat:

- Retrieves relevant indexed source information
- Answers conversationally with citations when sources are found
- Persists both messages
- Updates Case Memory when appropriate
- Creates no report version, saved artifact, or Official Case Record entry

Canonical implementation: `FollowUpChatService.answer_follow_up` via `POST /interactions`.

---

## 10. Source retrieval and citation grounding

Retrieval operates over the configured indexed labor-reference corpus.

The repository includes CONTRACT and CIM index artifacts for local development and testing. Live availability depends on the database index in the running environment.

Chat retrieval uses `KnowledgeRetrievalService.search_all` with existing relevance controls, then validates returned citation quotes against retrieved passage text (and any saved-report excerpts when present). Chat does not run AuthorityRanker, ReportBuilder, or report-level citation validation.

---

## 11. Case Memory and domain events

Case Memory is a modular JSON projection stored in `case_memories`. It is updated synchronously from domain events such as conversation meaning, evidence upload, analysis save, grievance save, close, settle, and reopen.

Domain events are persisted in `case_domain_events`, applied in-process (no external broker), and support idempotency keys. Ordinary chat meaning updates Case Memory without appending Official Case Record noise.

---

## 12. Workflow engine

`CaseWorkflowService` enforces an explicit finite-state machine for case open, Step 1/2/3 progression, management response, decision, appeal, settle, close, and reopen. State is mirrored on Case Memory. Artifact Save may advance the case into an official step state. The FSM does not require an analysis report before grievance drafting.

---

## 13. Analysis preview, persistence, and versioning

| Stage | Behavior |
|-------|----------|
| Generate | Temporary read-only preview; no version, artifact, or Official Case Record event |
| Cancel | Discard preview; no version number consumed |
| Save | Persist next `CaseReportVersion` + official artifact |
| Save and Print | Same + PDF |

Generate Analysis uses the full structured RAG pipeline:

```text
Question + case context
  → LegalIssueAnalyzer
  → KnowledgeRetrievalService
  → AuthorityRanker
  → EvidenceExtractor
  → ReportBuilder / NarrativeGenerator
  → CitationValidator
  → AnalysisService
```

Versioning begins at Save.

---

## 14. Grievance drafts

Generate Grievance returns a temporary editable field-value draft independent of analysis-report existence. Save / Save and Print create official grievance artifacts. Official USPS Step 1 and Step 2 AcroForm PDFs are filled through the W5 export path; Step 3 generation is not implemented.

---

## 15. Artifacts and Official Case Record

Artifacts are the case document library (analysis reports, grievances, evidence, and related documents).

The Official Case Record is the chronological steward timeline of meaningful saved activity. Previews and ordinary chat turns do not appear there. Jump-to-context endpoints return bounded historical windows for selected events.

---

## 16. Uploads and Case Assets

Uploads are stored as first-class `CaseAsset` rows with files under `data/case_assets/{case_uuid}/`. The current executable upload category is `uploaded_document`. Upload events can update Case Memory. Case-file RAG over uploaded evidence is not yet implemented.

---

## 17. Report rendering

Saved analysis versions export through Jinja2 HTML and WeasyPrint PDF. Export consumes persisted report JSON and does not re-run retrieval.

---

## 18. Steward UI shell and future frontend

The FastAPI shell at `/ui` provides dashboard and case-workspace verification
surfaces. It is not a production frontend. The interactive steward workspace is
planned for **W6** and can integrate against the existing case and saved-case
APIs; see [`docs/saved_cases_ui_contract.md`](saved_cases_ui_contract.md). W6 is
a vertical slice: UI work and RAG/generation validation happen together.

---

## 19. Security and production readiness

The current codebase is a production-oriented service architecture under active
development. W5 added an interim API-key boundary for `/sources` routes only.
Final application identity, authorization, case-level access control, upload
security, audit logging, and related protections remain planned for **W9 —
Security and Governance** and are not started. The system is not production
secure. Runtime outputs and private operational data remain outside the
portfolio repository.

---

## 20. Implementation status

| Subsystem | Status |
|-----------|--------|
| Case Workspace | Implemented |
| AI Conversation + indexed retrieval | Implemented |
| Case Memory | Implemented |
| Domain events | Implemented |
| Workflow engine | Implemented |
| Analysis reports (preview + Save versioning) | Implemented |
| Grievance field-value drafts | Implemented |
| Artifact management | Implemented |
| Official Case Record | Implemented |
| Uploads / Case Assets | Implemented |
| Steward UI shell | Implemented |
| Report HTML/PDF export | Implemented |
| Official USPS Step 1 and Step 2 forms | Implemented |
| USPS Supervisor Manual corpus | Implemented |
| Source processing lifecycle metadata | Implemented |
| Bounded retrieval-agent architecture | Implemented |
| Interim `/sources` API-key auth | Temporary W5 safety boundary |
| Interactive steward workspace | In progress (W6; M0–M5 complete, M6–M10 not started) |
| Formal RAG evaluation / quality gates | Planned (W7) |
| Multi-agent authority workflow | Planned (W8) |
| Application identity / governance | Planned (W9) |
| LMOU and arbitration corpus expansion | Planned (W10) |
| Production packaging and deployment | Planned (W11) |

---

## 21. Testing

pytest covers retrieval scoring, case APIs, chat/retrieval grounding, steward artifact workflow, Case Memory / domain events / workflow, workspace restoration, and report export.

```bash
python -m pytest tests/test_chat_source_retrieval.py tests/test_steward_artifact_workflow.py -q
python -m pytest tests/ -m "not integration" -q
```

---

## 22. Production extension points

Future implementation follows the canonical roadmap in
[`docs/ROADMAP.md`](ROADMAP.md). The former post-W5 sequence (Security → Steward
UI → Arbitration/LMOU → Deployment) is superseded.

- **W6 — Interactive Steward Workspace (in progress):** usable end-to-end steward UI as
  a vertical slice; continuous RAG and generation validation through realistic
  workflows. **M0–M5 are complete** (Foundations, Saved Cases, Create Case +
  workspace restore, Conversation + retrieval, Evidence uploads +
  `upload_refs`, Analysis generate/preview/save). **M6 Grievance is next.**
  M6–M10 are not started.
- **W7 — RAG Evaluation and Output Quality:** versioned golden evaluations,
  citation/faithfulness metrics, and approved quality thresholds before
  multi-agent complexity.
- **W8 — Multi-Agent Authority Workflow:** authority-specific agents only after
  the W7 baseline; must show measurable or clearly justified operational benefit.
- **W9 — Security and Governance:** application identity, authorization, audit
  logging, upload controls, and threat model before sensitive corpus expansion.
  Replace or integrate the interim `/sources` API-key boundary. Do not
  reintroduce an unapproved steward hierarchy merely because older notes
  mentioned RBAC.
- **W10 — LMOU and Arbitration Knowledge Expansion:** protected corpus expansion
  after W9; jurisdiction/date/authority-role metadata and corpus-specific
  evaluations.
- **W11 — Production Packaging and Deployment:** Dockerization, operations,
  monitoring, backup/restore, and CI/CD. Dockerization alone is not production
  readiness.

W5 retrieval agents (`RetrievalOrchestrator`, `ContractAgent`,
`SupervisorManualAgent`) are bounded retrieval infrastructure. They are not
completion of W8 multi-agent orchestration. Multi-agent work, if introduced in
W8, should sit above Case Memory, domain events, and the workflow engine rather
than replace them.

Authenticated stewards are planned to collaborate in a shared workspace without
a steward role hierarchy unless that product decision is intentionally revised.
Source administration may still require a distinct privileged boundary.

---

## Related documentation

- [`README.md`](../README.md)
- [`PROJECT_STATE.md`](../PROJECT_STATE.md)
- [`docs/ROADMAP.md`](ROADMAP.md)
- [`docs/W6_UI_ARCHITECTURE.md`](W6_UI_ARCHITECTURE.md)
- [`docs/saved_cases_ui_contract.md`](saved_cases_ui_contract.md)
