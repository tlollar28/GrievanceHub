# GrievanceHub Engineering Status

Last updated: 2026-07-18

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
| W5 | Planned — Official Forms and Supervisor Manual Integration |
| W6 | Planned — Security Foundation |
| W7 | Planned — Production Steward Interface |
| W8 | Planned — Arbitration and LMOU Integration |
| W9 | Planned — Production Deployment |

## Product model

GrievanceHub is a backend-first grievance case workspace. Each grievance matter
is managed as a persistent `GrievanceCase`. Conversation, Case Memory, evidence,
reports, grievances, artifacts, and workflow history remain attached to that case.

The application manages workflow automation. The steward controls when analysis
reports and grievances are created. There is no required Conversation → Analysis
→ Grievance sequence.

## Implemented capabilities

- Persistent case create / open / reopen / workspace restore
- Continuous AI conversation via `POST /cases/{case_uuid}/interactions`
- Indexed-source retrieval for normal chat with citation grounding
- Case Memory projected from domain events
- Explicit Generate Analysis Report (temporary preview → Save / Save and Print)
- Explicit Generate Grievance (editable field-value draft → Save / Save and Print)
- Artifacts library and Official Case Record for saved work
- Case asset uploads
- Analysis report HTML/PDF export
- FastAPI steward verification shell at `/ui`

## Normal chat vs analysis

| Path | Behavior |
|------|----------|
| Normal chat | Retrieves indexed sources, answers conversationally, may return grounded citations, persists messages, may update Case Memory; creates no report version or artifact |
| Generate Analysis | Explicit steward action; structured RAG report pipeline; temporary read-only preview |
| Save / Save and Print | First persistence point for versioned artifacts and Official Case Record entries |

## Stack

Python 3, FastAPI, SQLAlchemy, Alembic, PostgreSQL 16 + pgvector, OpenAI
embeddings and chat, Jinja2 + WeasyPrint, pytest.

## Indexed corpus (repository artifact)

The committed `app/sources/source_index.json` artifact currently includes
CONTRACT and CIM text chunks for local development. Live retrieval coverage
depends on the running database index.

## Implementation lineage

Historical commits use earlier internal labels such as `Phase 0`, `Phase 1.x`,
`Phase 2`, and `Phase 3`. The current public roadmap consolidates that work as:

| Milestone | Outcome |
|-----------|---------|
| W1 | Case interaction contracts and service boundaries |
| W2 | AI case interaction orchestration, persistent chat, retrieval, and analysis foundations |
| W3 | Case evidence, uploads, metadata, storage, and asset management |
| W4 | Workspace restoration, Case Memory, domain events, workflow FSM, Generate/Save artifacts, Official Case Record, and chat retrieval hardening |
| CrossCraft retirement | Obsolete SPBS/cross-craft surface removed |

The historical phase labels remain visible in Git history. They represent the
earlier implementation sequence and do not indicate missing work.

## Testing

```bash
python -m pytest tests/test_chat_source_retrieval.py tests/test_steward_artifact_workflow.py -q
python -m pytest tests/ -m "not integration" -q
```

## Roadmap

### W5 — Official Forms and Supervisor Manual Integration

Implement the official USPS Step 1 and Step 2 forms, replace placeholder
templates, add approved USPS supervisor manuals to the retrieval corpus, improve
retrieval and citation handling, and add regression tests.

### W6 — Security Foundation

Implement authentication, RBAC, case-level authorization, secure upload
validation, audit logging, encryption and secrets management, rate limiting,
prompt-injection protections, and security-focused tests.

### W7 — Production Steward Interface

Build the production dashboard, persistent case workspace, research and
conversation interfaces, form editing, progression controls, citation viewing,
and responsive UI.

### W8 — Arbitration and LMOU Integration

Add protected arbitration decisions and LMOUs with metadata extraction,
indexing, permission-aware retrieval, citation validation, and evaluation tests.

### W9 — Production Deployment

Add managed PostgreSQL and pgvector, object storage, background workers,
monitoring, backup and recovery, CI/CD hardening, and performance testing.

## Related documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`docs/saved_cases_ui_contract.md`](docs/saved_cases_ui_contract.md)
- [`README.md`](README.md)
