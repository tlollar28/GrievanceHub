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
| Local 300 Form 79-1 PDF overlay | Deferred (next phase) |
| Production React UI | Deferred |
| Authentication / RBAC | Deferred |
| Cloud deployment | Deferred |

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
- Grievance Generate/Save uses editable field-value drafts; full Local 300 Form 79-1 overlay PDF assembly is deferred
- Broader corpus expansion and cloud deployment remain future work

## Next phase

**W5** — complete Local 300 Form 79-1 overlay PDF assembly and filled-form execution, followed by production UI, authentication/RBAC, and deployment hardening.

## Related documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — system design
- [`PROJECT_STATE.md`](PROJECT_STATE.md) — engineering status and phase history
- [`docs/saved_cases_ui_contract.md`](docs/saved_cases_ui_contract.md) — saved-cases UI/API contract
