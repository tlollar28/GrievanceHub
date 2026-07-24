# GrievanceHub Engineering Status

Last updated: 2026-07-23

Concise public engineering status for the current working tree. Detailed system
design lives in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Current status

| Item | State |
|------|--------|
| Current branch | `main` |
| W1 — Case Interaction Contract | Complete and committed |
| W2 — AI Case Interaction Orchestration | Complete and committed |
| W3 — Case Evidence and Asset Management | Complete and committed |
| W4 — Case Lifecycle, Memory, Workflow, and Artifacts | Complete and committed |
| W5 — Knowledge Foundation | Complete and committed |
| W6 — Security Foundation | Next — not started |
| W7 — Production Steward Interface | Planned |
| W8 — Arbitration and LMOU Integration | Planned |
| W9 — Production Deployment | Planned |

## Product model

GrievanceHub is a backend-first grievance case workspace. Each grievance matter
is managed as a persistent `GrievanceCase`. Conversation, Case Memory, evidence,
reports, grievances, artifacts, and workflow history remain attached to that case.

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
- Official Step 1 and Step 2 AcroForm PDF fill/export
- Artifacts library and Official Case Record for saved work
- Case asset uploads
- Analysis report HTML/PDF export
- FastAPI steward verification shell at `/ui`
- SourceDocument processing lifecycle metadata and W5 Alembic migration
- Supervisor Manual corpus classification (`SUPERVISOR_MANUAL`) with EL-921, EL-801, and F-21 support
- Bounded retrieval-agent architecture (`RetrievalOrchestrator`, `ContractAgent`, `SupervisorManualAgent`)
- Interim API-key authentication on `/sources` routes (temporary W5 safety boundary)

## Normal chat vs analysis

| Path | Behavior |
|------|----------|
| Normal chat | Retrieves indexed sources (including Supervisor Manual evidence via the orchestrator), answers conversationally, may return grounded citations, persists messages, may update Case Memory; creates no report version or artifact |
| Generate Analysis | Explicit steward action; structured RAG report pipeline; temporary read-only preview |
| Save / Save and Print | First persistence point for versioned artifacts and Official Case Record entries |

## Stack

Python 3, FastAPI, SQLAlchemy, Alembic, PostgreSQL 16 + pgvector, OpenAI
embeddings and chat, Jinja2 + WeasyPrint, pypdf AcroForm fill, pytest.

## Indexed corpus (repository artifact)

The committed `app/sources/source_index.json` artifact currently includes
CONTRACT and CIM text chunks for local development. Live retrieval coverage
depends on the running database index, including Supervisor Manual embeddings
when those sources have been synchronized and processed locally.

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
| CrossCraft retirement | Obsolete SPBS/cross-craft surface removed |

The historical phase labels remain visible in Git history. They represent the
earlier implementation sequence and do not indicate missing work.

## Testing

```bash
python -m pytest tests/test_w5_source_lifecycle.py tests/test_official_grievance_pdf_export.py tests/test_retrieval_agents.py -q
python -m pytest tests/ -m "not integration" -q
```

## Roadmap

### W5 — Knowledge Foundation (complete)

Delivered:

- Official USPS Step 1 and Step 2 fillable AcroForm PDF integration
- Source processing lifecycle metadata and Alembic migration
- Supervisor Manual registration/sync/processing support (EL-921, EL-801, F-21)
- Bounded retrieval-agent architecture with fail-closed authorization adapters
- Interim `/sources` API-key authentication (temporary; not W6 identity)

W5 retrieval components are retrieval infrastructure. They are not completion of a
future multi-agent product system.

### W6 — Security Foundation (next)

Not started. Planned work includes application identity, RBAC or equivalent
policy, case-level authorization, secure upload validation, audit logging,
encryption and secrets management, production rate limiting, broader
prompt-injection defenses, and security-focused tests.

The interim `GRIEVANCEHUB_API_KEY` / `GRIEVANCEHUB_ADMIN_API_KEY` boundary added
in W5 protects source/retrieval routes only. It must be replaced or integrated
into the W6 identity design and must not be described as completing W6.

### W7 — Production Steward Interface

Build the production dashboard, persistent case workspace, research and
conversation interfaces, form editing, progression controls, citation viewing,
and responsive UI.

### W8 — Arbitration and LMOU Integration

Add protected arbitration decisions and LMOUs with metadata extraction,
indexing, permission-aware retrieval, citation validation, and evaluation tests.
Additional LMOU and historical arbitration expansion remains deferred to this
phase.

### W9 — Production Deployment

Add managed PostgreSQL and pgvector, object storage, background workers,
monitoring, backup and recovery, CI/CD hardening, and performance testing.

## Related documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`docs/saved_cases_ui_contract.md`](docs/saved_cases_ui_contract.md)
- [`docs/temp/W5_FINAL_COMPLETION_REPORT.md`](docs/temp/W5_FINAL_COMPLETION_REPORT.md)
- [`README.md`](README.md)
