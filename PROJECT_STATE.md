# GrievanceHub Engineering Status

Last updated: 2026-07-25

Concise public engineering status for the current working tree. Detailed system
design lives in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). The canonical
post-W5 delivery plan lives in [`docs/ROADMAP.md`](docs/ROADMAP.md).

## Current status

| Item | State |
|------|--------|
| Current branch | `main` |
| Current completed phase | W5 — Knowledge Foundation |
| Current implementation state | W6 in progress — M0–M7 complete (Foundations through Artifacts & History) |
| Next milestone | W6 M8 — Workflow outcomes |
| W1 — Case Interaction Contract | Complete and committed |
| W2 — AI Case Interaction Orchestration | Complete and committed |
| W3 — Case Evidence and Asset Management | Complete and committed |
| W4 — Case Lifecycle, Memory, Workflow, and Artifacts | Complete and committed |
| W5 — Knowledge Foundation | Complete and committed |
| W6 — Interactive Steward Workspace | In progress (M0–M7 complete; M8–M10 not started) |
| W6 M0 — Frontend Foundations | Complete and committed |
| W6 M1 — Saved Cases | Complete and committed |
| W6 M2 — Create Case + workspace restore | Complete and committed |
| W6 M3 — Conversation + retrieval | Complete and committed |
| W6 M4 — Evidence uploads + asset references | Complete and committed |
| W6 M5 — Analysis generate / preview / save | Complete and committed |
| W6 M6 — Grievance generate / edit / validate / save | Complete and committed |
| W6 M7 — Artifacts and History | Complete (implementation validated; commit pending) |
| W7 — RAG Evaluation and Output Quality | Planned — not started |
| W8 — Multi-Agent Authority Workflow | Planned — not started |
| W9 — Security and Governance | Planned — not started |
| W10 — LMOU and Arbitration Knowledge Expansion | Planned — not started |
| W11 — Production Packaging and Deployment | Planned — not started |

The former post-W5 sequence (W6 Security → W7 Steward UI → W8 Arbitration/LMOU →
W9 Deployment) is superseded. See [`docs/ROADMAP.md`](docs/ROADMAP.md).

## Product model

GrievanceHub is a backend-first grievance case workspace with a React steward
shell under active W6 construction. Each grievance matter is managed as a
persistent `GrievanceCase`. Conversation, Case Memory, evidence, reports,
grievances, artifacts, and workflow history remain attached to that case.

The application manages workflow automation. The steward controls when analysis
reports and grievances are created. There is no required Conversation → Analysis
→ Grievance sequence.

Authenticated stewards are planned to collaborate in a shared workspace without a
steward role hierarchy, unless that product decision is intentionally revised.
Source administration may still require a distinct privileged boundary separate
from ordinary steward case work.

## Implemented capabilities

- Persistent case create / open / reopen / workspace restore
- Continuous AI conversation via `POST /cases/{case_uuid}/interactions`
- Indexed-source retrieval for normal chat with citation grounding
- Case Memory projected from domain events
- Explicit Generate Analysis Report (temporary preview → Save / Save and Print)
- Explicit Generate Grievance (editable field-value draft → Save / Save and Print)
- Official grievance generation currently supports Step 1 and Step 2 only
  (`official_grievance_worksheet_step_1`,
  `official_standard_grievance_form_step_2`)
- Official Step 1 and Step 2 AcroForm PDF fill/export
- Artifacts library and Official Case Record for saved work (backend + React
  Artifact Library / history browsing on `/cases/:caseUuid/artifacts`)
- Case asset uploads
- Analysis report HTML/PDF export
- FastAPI steward verification shell at `/ui`
- SourceDocument processing lifecycle metadata and W5 Alembic migration
- Supervisor Manual corpus classification (`SUPERVISOR_MANUAL`) with EL-921, EL-801, and F-21 support
- Bounded retrieval-agent architecture (`RetrievalOrchestrator`, `ContractAgent`, `SupervisorManualAgent`)
- Interim API-key authentication on `/sources` routes (temporary W5 safety boundary)
- W6 M0 React/TypeScript frontend foundation under `frontend/` (AppShell, routing,
  TanStack Query, typed API client, health ConnectionStatus, design tokens)
- W6 M1 Saved Cases dashboard/list (`GET /cases/saved`), URL filters/search/
  pagination, open/reopen, and `/cases/:caseUuid` entry
- W6 M2 Create Case (`POST /cases/`), durable workspace restore
  (`GET /cases/{uuid}/workspace`), `CaseWorkspaceShell`, Case Rail, overview /
  Case Memory presentation, and known-facts editing (`PATCH /cases/{uuid}/facts`)
- W6 M3 case conversation (`GET /cases/{uuid}/messages`,
  `POST /cases/{uuid}/interactions`), retrieval-status UI, citation chips and
  research panel, disclosures / facts-needed; normal chat creates no analysis
  report, grievance, or artifact
- W6 M4 Evidence workspace (`/cases/:caseUuid/evidence`) with case asset list,
  multipart upload (`POST /cases/{uuid}/assets`), metadata detail, and
  conversation `upload_refs` attachment selection; uploaded evidence is
  case-context reference only and is not authority-corpus RAG
- W6 M5 Analysis workspace (`/cases/:caseUuid/analysis`) with explicit Generate
  Analysis (`POST /cases/{uuid}/reports/generate` → temporary client-held
  preview), Cancel (no persistence), Save / Save and Print
  (`POST /cases/{uuid}/reports/save-and-print` with `prepare_pdf` false/true and
  client `idempotency_key`), saved version list/detail
  (`GET /cases/{uuid}/versions[/{n}]`), and HTML/PDF export controls with
  official-versus-working-draft labeling; normal conversation still creates no
  analysis version or artifact
- W6 M6 Grievance workspace (`/cases/:caseUuid/grievance`) with Generate → Edit →
  Validate → Save / Save and Print for Step 1 and Step 2 only
  (`POST /cases/{uuid}/actions` `{ action: "generate_grievance" }` → temporary
  client-held draft; `POST /cases/{uuid}/grievances/save-and-print` with
  `prepare_pdf` false/true); limited list/detail/PDF for saved Step 1/2
  `grievance_form` artifacts
- W6 M7 Artifacts & History workspace (`/cases/:caseUuid/artifacts`) with
  case-scoped Artifact Library (`analysis_report` + `grievance_form`), read-only
  detail and PDF preview, Official Case Record (`GET /cases/saved/{uuid}/history`),
  broader timeline (`GET /cases/saved/{uuid}/timeline`), jump-to-context
  (`GET /cases/{uuid}/history/{event_id}/context`), and compatible artifact
  comparison (`POST /cases/{uuid}/artifacts/compare`). Browsing/compare/context
  create no artifacts. M8 workflow outcomes and Sources administration remain
  out of scope.

## Normal chat vs analysis

| Path | Behavior |
|------|----------|
| Normal chat | Retrieves indexed sources (including Supervisor Manual evidence via the orchestrator), answers conversationally, may return grounded citations, persists messages, may update Case Memory; creates no report version or artifact |
| Generate Analysis | Explicit steward action; structured RAG report pipeline; temporary read-only preview |
| Save / Save and Print | First persistence point for versioned artifacts and Official Case Record entries |

## Stack

Python 3, FastAPI, SQLAlchemy, Alembic, PostgreSQL 16 + pgvector, OpenAI
embeddings and chat, Jinja2 + WeasyPrint, pypdf AcroForm fill, pytest.
Frontend (W6): React, TypeScript, Vite, React Router, TanStack Query, Vitest.

## Security status

- Interim `/sources` API-key boundary exists (`GRIEVANCEHUB_API_KEY` /
  `GRIEVANCEHUB_ADMIN_API_KEY`)
- Final application identity does not exist
- Broader `/cases`, export, and UI authentication are not implemented
- The W6 browser must not receive source API secrets
- The system is not production secure

## Corpus status

- Existing W5 corpus supported (contract/CIM index artifacts; Supervisor Manual
  processing when synchronized locally)
- LMOU and arbitration expansion deferred until after W9 (Security and
  Governance)

## Deployment status

- Local development via Docker Compose for PostgreSQL is supported
- Production packaging and deployment are deferred until W11

## Implementation lineage

Historical commits use earlier internal labels such as `Phase 0`, `Phase 1.x`,
`Phase 2`, and `Phase 3`. The current public roadmap consolidates that work as:

| Milestone | Outcome |
|-----------|---------|
| W1 | Case interaction contracts and service boundaries |
| W2 | AI case interaction orchestration, persistent chat, retrieval, and analysis foundations |
| W3 | Case evidence, uploads, metadata, storage, and asset management |
| W4 | Workspace restoration, Case Memory, domain events, workflow FSM, Generate/Save artifacts, Official Case Record, and chat retrieval hardening |
| W5 | Knowledge Foundation: official forms, Supervisor Manuals, source lifecycle, retrieval agents, and interim source-route API-key boundary |
| W6 M0 | Frontend foundations: Vite/React/TS shell, routing, Query client, typed API client, health indicator |
| W6 M1 | Saved Cases dashboard/list, filters/search/pagination, open/reopen, workspace-entry route |
| W6 M2 | Create Case, durable workspace restore, CaseWorkspaceShell, Case Rail, facts editor |
| W6 M3 | Case conversation, message restore, interactions, retrieval status, citations |
| W6 M4 | Evidence uploads, asset list/detail, conversation upload_refs |
| W6 M5 | Analysis generate / temporary preview / Save / Save and Print / versions |
| W6 M6 | Grievance Generate → Edit → Validate → Save / Save and Print (Step 1/2) |
| W6 M7 | Artifact Library, Official Case Record, timeline, compare, jump-to-context |
| CrossCraft retirement | Obsolete SPBS/cross-craft surface removed |

The historical phase labels remain visible in Git history. They represent the
earlier implementation sequence and do not indicate missing work.

## Testing

```bash
python -m pytest tests/test_w5_source_lifecycle.py tests/test_official_grievance_pdf_export.py tests/test_retrieval_agents.py -q
python -m pytest tests/ -m "not integration" -q
cd frontend && npm run typecheck && npm run lint && npm run test:run && npm run build
```

## Roadmap (summary)

Canonical detail: [`docs/ROADMAP.md`](docs/ROADMAP.md).
W6 UI blueprint: [`docs/W6_UI_ARCHITECTURE.md`](docs/W6_UI_ARCHITECTURE.md).

| Phase | Status |
|-------|--------|
| W5 — Knowledge Foundation | Complete |
| W6 — Interactive Steward Workspace | In progress (M0–M7 complete) |
| W7 — RAG Evaluation and Output Quality | Planned |
| W8 — Multi-Agent Authority Workflow | Planned |
| W9 — Security and Governance | Planned |
| W10 — LMOU and Arbitration Knowledge Expansion | Planned |
| W11 — Production Packaging and Deployment | Planned |

W5 retrieval components are retrieval infrastructure. They are not completion of
W8 multi-agent orchestration. The interim `/sources` API-key boundary is not
completion of W9 application security. W6 M0–M7 cover shell foundations, Saved
Cases entry, Create Case, durable workspace restore, case conversation with
retrieval/citations, evidence uploads with `upload_refs`, Analysis
generate/preview/save, Grievance Generate → Edit → Validate → Save / Save and
Print for official Step 1 and Step 2 forms only, and Artifacts & History
browsing (library, Official Case Record, timeline, compare, jump-to-context).
Workflow outcomes (M8) and later screens remain later milestones. Case evidence
uploads are not indexed into the authority corpus.

## Related documentation

- [`docs/ROADMAP.md`](docs/ROADMAP.md)
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`docs/W6_UI_ARCHITECTURE.md`](docs/W6_UI_ARCHITECTURE.md)
- [`docs/saved_cases_ui_contract.md`](docs/saved_cases_ui_contract.md)
- [`docs/temp/W5_FINAL_COMPLETION_REPORT.md`](docs/temp/W5_FINAL_COMPLETION_REPORT.md)
- [`docs/temp/W6_M0_FRONTEND_FOUNDATIONS_REPORT.md`](docs/temp/W6_M0_FRONTEND_FOUNDATIONS_REPORT.md)
- [`docs/temp/W6_M1_SAVED_CASES_REPORT.md`](docs/temp/W6_M1_SAVED_CASES_REPORT.md)
- [`docs/temp/W6_M2_CREATE_WORKSPACE_REPORT.md`](docs/temp/W6_M2_CREATE_WORKSPACE_REPORT.md)
- [`docs/temp/W6_M3_CONVERSATION_RETRIEVAL_REPORT.md`](docs/temp/W6_M3_CONVERSATION_RETRIEVAL_REPORT.md)
- [`docs/temp/W6_M4_EVIDENCE_REPORT.md`](docs/temp/W6_M4_EVIDENCE_REPORT.md)
- [`docs/temp/W6_M5_ANALYSIS_REPORT.md`](docs/temp/W6_M5_ANALYSIS_REPORT.md)
- [`docs/temp/W6_M6_GRIEVANCE_REPORT.md`](docs/temp/W6_M6_GRIEVANCE_REPORT.md)
- [`docs/temp/W6_M7_ARTIFACTS_HISTORY_REPORT.md`](docs/temp/W6_M7_ARTIFACTS_HISTORY_REPORT.md)
- [`README.md`](README.md)
