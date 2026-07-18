# GrievanceHub Architecture

Technical system design for the current GrievanceHub backend, including W4 case-lifecycle behavior in the working tree.

For a concise product overview, see [`README.md`](../README.md).

---

## 1. System overview

GrievanceHub is a FastAPI service that manages persistent grievance case workspaces. The unit of work is a long-lived `GrievanceCase`. Conversation, Case Memory, evidence, reports, grievances, artifacts, and workflow state remain attached to that case across open, close, and reopen.

```text
Steward / API client / /ui shell
        │
        ▼
   FastAPI routers
   (/cases, /sources, exports, /ui)
        │
        ▼
   Service layer
   (workspace, memory, workflow, retrieval, artifacts)
        │
        ├─► PostgreSQL 16 + pgvector
        └─► Local filesystem storage (case assets, generated reports)
```

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

`GET /cases/{case_uuid}/workspace` (also returned by open/reopen) restores:

- Case identity, facts, and status
- Case Memory and Case Overview
- Saved analysis history
- Assets and artifact groups
- Official Case Record timeline slice
- Step progression and available actions
- Bounded `ai_continuity_context`

Full transcript remains available via `GET /cases/{case_uuid}/messages`. Workspace restore does not embed the entire conversation into every AI call.

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

Generate Grievance returns a temporary editable field-value draft independent of analysis-report existence. Save / Save and Print create official grievance artifacts. Full Local 300 Form 79-1 overlay PDF assembly remains the next implementation phase.

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

The FastAPI shell at `/ui` provides dashboard and case-workspace verification surfaces. It is not a production frontend. A future React application can integrate against the existing case and saved-case APIs; see [`docs/saved_cases_ui_contract.md`](saved_cases_ui_contract.md).

---

## 19. Security and production readiness

The current codebase is a production-oriented service architecture under active development. Production authentication, authorization, and RBAC are not yet implemented. Runtime outputs and private operational data remain outside the portfolio repository.

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
| Grievance field-value drafts | Partially implemented |
| Artifact management | Implemented |
| Official Case Record | Implemented |
| Uploads / Case Assets | Implemented |
| Steward UI shell | Implemented |
| Report HTML/PDF export | Implemented |
| Local 300 PDF overlay | Deferred |
| Authentication / RBAC | Deferred |
| Production React UI | Deferred |
| Cloud deployment | Deferred |

---

## 21. Testing

pytest covers retrieval scoring, case APIs, chat/retrieval grounding, steward artifact workflow, Case Memory / domain events / workflow, workspace restoration, and report export.

```bash
python -m pytest tests/test_chat_source_retrieval.py tests/test_steward_artifact_workflow.py -q
python -m pytest tests/ -m "not integration" -q
```

---

## 22. Production extension points

Natural future seams include object storage for case assets, managed PostgreSQL + pgvector, background workers for heavy RAG/PDF jobs, identity-provider auth in front of FastAPI, and a production React steward client. Multi-agent orchestration, if introduced later, should sit above Case Memory, domain events, and the workflow engine rather than replace them.

---

## Related documentation

- [`README.md`](../README.md)
- [`PROJECT_STATE.md`](../PROJECT_STATE.md)
- [`docs/saved_cases_ui_contract.md`](saved_cases_ui_contract.md)
