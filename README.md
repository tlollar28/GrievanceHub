# GrievanceHub

GrievanceHub is a backend-first, AI-assisted grievance case-management platform for USPS/NPMHU stewards. It is built around long-lived case workspaces rather than one-off chat sessions or disposable report jobs.

Each grievance matter is managed as a persistent **GrievanceCase**. Related conversation, Case Memory, evidence, reports, grievances, artifacts, and workflow history remain attached to that case.

This repository presents a portfolio-quality, production-oriented service architecture under active development. Production authentication, RBAC, a production frontend, and cloud deployment are not yet included.

Production case data, credentials, and private operational assets are not included in this portfolio repository.

## Current capabilities

| Capability | Status |
|------------|--------|
| Persistent case workspaces | Implemented |
| Continuous AI conversation with indexed-source retrieval | Implemented |
| Case Memory | Implemented |
| Domain events | Implemented |
| Workflow engine (finite-state) | Implemented |
| Analysis report preview, Save, and versioning | Implemented |
| Grievance field-value draft Generate / Save | Partially implemented |
| Artifacts and Official Case Record | Implemented |
| Case asset uploads | Implemented |
| Steward verification UI (`/ui`) | Implemented (FastAPI HTML shell) |
| Analysis report HTML/PDF export | Implemented |
| Official USPS Step 1 and Step 2 forms | Planned (W5) |
| USPS Supervisor Manual corpus | Planned (W5) |
| Authentication / RBAC | Planned (W6) |
| Production React UI | Planned (W7) |
| Arbitration and LMOU corpus | Planned (W8) |
| Cloud deployment | Planned (W9) |

## Steward workflow

```text
Dashboard
      ↓
New Case  or  Open Existing Case
      ↓
Persistent Case Workspace
      ↓
Continuous AI Conversation
      ↓
Upload Evidence at Any Time
      ↓
Steward independently chooses:
  • Generate Analysis Report
  • Generate Grievance
  • Continue Conversation
      ↓
Review
      ↓
Save  or  Save and Print
      ↓
Artifacts → Official Case Record
```

There is no required Conversation → Analysis → Grievance sequence. The steward controls when artifacts are created.

## Architecture at a glance

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

Technical detail: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Technology stack

| Layer | Technology |
|-------|------------|
| API | FastAPI, Uvicorn |
| Language | Python 3 |
| Database | PostgreSQL 16 + pgvector |
| ORM / migrations | SQLAlchemy, Alembic |
| LLM / embeddings | OpenAI |
| Report export | Jinja2 + WeasyPrint |
| Verification UI | FastAPI HTML shell (`/ui`) |
| Tests | pytest |

## Repository structure

```text
app/
  api/routes/     # cases, sources, exports, steward UI
  services/       # workspace, memory, workflow, retrieval, artifacts
  schemas/        # Pydantic contracts
  database/       # SQLAlchemy models and session
  templates/      # report templates
  sources/        # source manifest / index artifacts
alembic/          # migrations
tests/            # unit and API tests
docs/             # architecture and UI contracts
scripts/          # diagnostics and tooling
```

## Local development

```bash
docker compose up -d
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

- Health: `GET /health`
- Steward UI shell: `http://localhost:8000/ui`

## Testing

```bash
python -m pytest tests/ -v
python -m pytest tests/ -m "not integration" -q
```

## Current development status

W4 case-lifecycle work is complete in the working tree: Case Memory, domain events, workflow FSM, steward-controlled Generate/Save artifacts, workspace restoration, and the FastAPI verification shell. Continuous chat retrieves from the configured indexed labor-reference corpus and may return grounded citations; it does not create report versions or saved artifacts.

## Current limitations

- No production authentication or RBAC
- Steward UI is a FastAPI verification shell, not a production React application
- Official USPS Step 1 and Step 2 form generation is planned for W5
- USPS Supervisor Manual integration is planned for W5
- Arbitration decisions and LMOU integration are planned for W8
- Cloud deployment and operational infrastructure remain future work

## Development roadmap

### W5 — Official Forms and Supervisor Manual Integration

- Implement the official USPS Step 1 grievance form
- Implement the official USPS Step 2 grievance form
- Replace placeholder form templates
- Add approved USPS supervisor manuals to the retrieval corpus
- Improve retrieval and citation handling for the expanded corpus
- Add form-generation and retrieval regression tests

### W6 — Security Foundation

- Authentication
- Role-based access control
- Case-level authorization
- Secure upload validation
- Audit logging
- Encryption and secrets management
- Rate limiting
- Prompt-injection protections
- Security-focused tests

### W7 — Production Steward Interface

- Login and session flows
- Case dashboard
- Persistent case workspace
- Research and conversation interfaces
- Form editing and progression controls
- Citation viewing
- Responsive production UI

### W8 — Arbitration and LMOU Integration

- Protected arbitration-decision ingestion
- LMOU ingestion
- Metadata extraction and indexing
- Permission-aware retrieval
- Citation validation
- Retrieval and evaluation testing

### W9 — Production Deployment

- Managed PostgreSQL and pgvector
- Object storage for case assets
- Background workers for retrieval and PDF jobs
- Monitoring and structured logging
- Backup and recovery
- CI/CD hardening
- Performance and load testing

## Related documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — system design
- [`PROJECT_STATE.md`](PROJECT_STATE.md) — engineering status and phase history
- [`docs/saved_cases_ui_contract.md`](docs/saved_cases_ui_contract.md) — saved-cases UI/API contract
