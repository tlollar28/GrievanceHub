# GrievanceHub

AI-powered grievance case analysis and workflow platform for USPS/NPMHU stewards, built from prior union-steward and USPS operations experience.

**Product principle:** The application manages the workflow. The steward manages the grievance.

GrievanceHub is a living case workspace — not a basic chatbot. Case-specific AI chat, cumulative facts/evidence, grounded analysis reports, and versioned history stay attached to each saved case.

> **Status:** Active development. Not production-ready for sensitive grievance data. Authentication/RBAC are not implemented. Do not use real grievance/employee data yet.

No license has been selected for this repository.

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

- Git
- Docker / Docker Compose
- Python 3.x
- An OpenAI API key for local analysis/chat (kept only in your private `.env`)

### 1. Clone

```bash
git clone <repository-url>
cd GrievanceHub
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv
```

Windows (PowerShell / cmd):

```bash
venv\Scripts\activate
```

macOS / Linux:

```bash
source venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 4. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set a local `OPENAI_API_KEY=...` placeholder replacement. Never commit `.env`.

### 5. Start PostgreSQL + pgvector

```bash
docker compose up -d
```

This starts PostgreSQL 16 with pgvector using local development credentials from `docker-compose.yml`.

### 6. Run migrations

```bash
alembic upgrade head
```

Windows example with the project venv:

```bash
venv\Scripts\python.exe -m alembic upgrade head
```

### 7. Official source files (local only)

Official CONTRACT / CIM / ELM PDFs and zips are **not** committed (gitignored). The repository tracks:

- `app/sources/manifest.json` — relative `local_path` entries and download metadata
- `app/sources/source_index.json` — committed text-chunk index used by retrieval
- `app/sources/source_registry.json`

Blank Local 300 grievance templates under `app/assets/grievance_templates/` **are** tracked.

To download official binaries into the expected local paths:

```bash
python scripts/download_sources.py
```

Do not commit downloaded PDFs/zips, uploads, case assets, generated filled forms, or private reports.

### 8. Start the API

```bash
uvicorn app.main:app --reload
```

Windows example:

```bash
venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

### PDF export on Windows

WeasyPrint requires MSYS2 Pango (`mingw-w64-x86_64-pango`). See comments in `requirements.txt`.

## Testing

Non-integration suite (default for local verification; does not require live OpenAI for most tests):

```bash
pytest tests/ -m "not integration" -v
```

Full suite:

```bash
pytest tests/ -v
```

Optional live regression (calls the analysis pipeline; requires DB + OpenAI):

```bash
set RUN_REGRESSION=1
pytest tests/test_regression_harness.py::test_regression_live_pipeline_smoke -v -s
```

Do not commit runtime outputs under `data/reports/`, `data/case_assets/`, `uploads/`, or generated filled forms. Do not commit private grievance or employee data.

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
