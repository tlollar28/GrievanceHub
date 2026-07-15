# GrievanceHub

AI-powered grievance case analysis and workflow platform for USPS/NPMHU stewards, built from prior union-steward and USPS operations experience.

**Product principle:** The application manages the workflow. The steward manages the grievance.

GrievanceHub is a living case workspace — not a basic chatbot. Case-specific AI chat, cumulative facts/evidence, grounded analysis reports, and versioned history stay attached to each saved case.

> **Status:** Active development. Not production-ready for sensitive grievance data. Authentication/RBAC are not implemented.

## Current capabilities

Implemented backend capabilities:

- FastAPI REST API
- PostgreSQL, SQLAlchemy, and Alembic
- pgvector embeddings and grounded RAG analysis
- Structured GrievanceHub Analysis Reports with citations
- Immutable report versions
- Persistent case-specific AI conversations
- Automatic analysis refresh after each interaction
- Saved cases with open/reopen workflow
- Case timeline / history
- First-class Case Assets (uploaded documents)
- Step 2 grievance draft-builder foundation (Local 300 Form 79-1)
- HTML and PDF analysis-report export
- Broad automated pytest coverage

## Architecture (brief)

| Layer | Role |
|-------|------|
| API | FastAPI routes for cases, sources, exports |
| Services | Case workspace orchestration, RAG pipeline, drafts/assets |
| Data | PostgreSQL + pgvector |
| RAG | Issue analysis → retrieval → authority ranking → grounded report |
| Case workspace | Conversations, facts, versions, timeline, reopen |
| Case assets | Case-owned uploaded documents (local storage) |
| Templates / drafts | Registry + Step 2 draft builder foundation |

Canonical chat route:

```http
POST /cases/{case_uuid}/interactions
```

See `docs/ARCHITECTURE.md` and `AGENTS.md` for details.

## Current workflow

```text
Create / Open Case
  → Chat with case-specific AI
  → Add context / evidence
  → Analysis automatically refreshes and versions
  → Continue interacting
  → Generate Grievance later when available (W5)
```

Stewards are not required to click Save Context, Update Analysis, Reanalyze, or Start Chat.

## Technology stack

- Python 3.x, FastAPI, Uvicorn
- SQLAlchemy, Alembic
- PostgreSQL 16 + pgvector (Docker Compose)
- OpenAI embeddings and chat models
- Jinja2 + WeasyPrint (HTML/PDF export)
- pytest

## Development status

| Area | Status |
|------|--------|
| W1–W3 AI-first workspace + Case Assets | Implemented |
| Generate Grievance execution | Planned **W5** |
| Full draft persistence / edit / print | Planned |
| React / Next steward UI | Planned (not in repo) |
| Auth / RBAC | Required before production use |
| LMOU / arbitration / supervisor-manual ingestion | Planned |
| Agentic / multi-agent architecture | Future roadmap |

Template note: only **Step 2 Local 300 Form 79-1** is currently buildable. Step 1 and Step 3 templates are not yet available. Step progression services/tables exist; initialization on case creation is deferred to **W4**.

## Local setup

### Prerequisites

- Docker / Docker Compose
- Python virtual environment
- OpenAI API key (local `.env`)

### Database

```bash
docker compose up -d
```

This starts PostgreSQL 16 with pgvector using local development credentials from `docker-compose.yml`.

### Environment

```bash
cp .env.example .env
# Edit .env and set OPENAI_API_KEY=...
```

### Migrations and API

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

Windows example with project venv:

```bash
venv\Scripts\python.exe -m alembic upgrade head
venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

### PDF export on Windows

WeasyPrint requires MSYS2 Pango (`mingw-w64-x86_64-pango`). See comments in `requirements.txt`.

## Testing

```bash
pytest tests/ -v
```

Non-integration suite:

```bash
pytest tests/ -m "not integration" -v
```

Optional live regression (calls the analysis pipeline; requires DB + OpenAI):

```bash
set RUN_REGRESSION=1
pytest tests/test_regression_harness.py::test_regression_live_pipeline_smoke -v -s
```

Do not commit runtime outputs under `data/reports/`, `data/case_assets/`, `uploads/`, or generated filled forms.

## Project roadmap

1. **W4** — enriched reopen workspace; step progression init on case create
2. **W5** — Generate Grievance execution
3. Draft persistence / edit / print
4. Auth / RBAC
5. Steward UI (React/Next)
6. Expanded source corpus (LMOU and controlled additions)
7. Controlled future agentic workflows

## Documentation

| Doc | Purpose |
|-----|---------|
| `AGENTS.md` | Permanent product and agent rules |
| `PROJECT_STATE.md` | Phase history and verification record |
| `docs/ARCHITECTURE.md` | Current architecture |
| `docs/saved_cases_ui_contract.md` | Deferred saved-cases UI contract |

## Safety notice

This repository is under active development and is **not** currently production-ready for sensitive grievance data. Do not deploy without authentication, access control, and a reviewed data-handling posture.
