# GrievanceHub

GrievanceHub is a FastAPI backend for USPS/NPMHU steward grievance case work. Each matter is modeled as a persistent `GrievanceCase`. Conversation, Case Memory, evidence, analysis reports, grievance drafts, artifacts, and workflow state remain attached to that case across open, close, and reopen.

The service is designed for steward-controlled workflows. Continuous chat can retrieve indexed labor references and return grounded citations. Analysis reports and grievance forms are created only through explicit actions—there is no required Conversation → Analysis → Grievance sequence.

This repository does not include production credentials, private case data, or operational infrastructure.

## Core capabilities

- Persistent case create, open, reopen, and workspace restoration
- Continuous case chat with indexed-source retrieval and citation grounding
- Case Memory projected from domain events
- Finite-state workflow tracking
- Explicit analysis-report generation (temporary preview → Save / Save and Print)
- Explicit grievance draft generation with official Step 1 and Step 2 AcroForm PDF fill
- Artifacts library and Official Case Record for saved work
- Case asset uploads
- Analysis report HTML and PDF export
- Indexed labor-reference corpus management, including contract sources and Supervisor Manual materials
- Bounded, domain-aware retrieval over embedded source chunks
- FastAPI verification shell at `/ui`

## High-level architecture

```text
HTTP client / verification UI
        │
        ▼
   FastAPI routers
   (/cases, /sources, exports, /ui)
        │
        ▼
   Service layer
   (workspace, memory, workflow, retrieval, forms, artifacts)
        │
        ├─► PostgreSQL 16 + pgvector
        └─► Local filesystem storage
            (case assets, generated reports/forms)
```

Chat and analysis share retrieval infrastructure. Chat does not run the full analysis-report pipeline. Detailed design is documented in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Technology stack

| Layer | Technology |
|-------|------------|
| API | FastAPI, Uvicorn |
| Language | Python 3 |
| Database | PostgreSQL 16 + pgvector |
| ORM / migrations | SQLAlchemy, Alembic |
| Embeddings / LLM | OpenAI |
| PDF forms | pypdf (AcroForm fill) |
| Report export | Jinja2, WeasyPrint |
| Verification UI | FastAPI HTML shell (`/ui`) |
| Tests | pytest |

## Repository structure

```text
app/
  api/            # Route modules and interim source-route auth
  assets/         # Official grievance form templates
  database/       # SQLAlchemy models and session
  schemas/        # Pydantic request/response contracts
  services/       # Business logic (cases, retrieval, forms, artifacts)
  sources/        # Source manifest / index artifacts
  templates/      # Report templates
  static/         # Static assets for reports / UI shell
alembic/          # Database migrations
docs/             # Architecture and API/UI contracts
scripts/          # Local diagnostics and tooling
tests/            # Unit and API tests
docker-compose.yml
requirements.txt
.env.example
```

Runtime directories such as `data/`, `uploads/`, and local virtual environments are not part of the committed product surface.

## Local development setup

Requirements: Python 3, Docker (for PostgreSQL + pgvector), and an OpenAI API key for embeddings and LLM-backed paths.

```bash
python -m venv venv
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate

pip install -r requirements.txt
docker compose up -d
cp .env.example .env
```

Edit `.env` with local values before starting the application.

## Configuration

Configuration is loaded from environment variables (see [`.env.example`](.env.example)):

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | Embeddings and LLM-backed analysis / chat |
| `DATABASE_URL` | SQLAlchemy PostgreSQL URL |
| `GRIEVANCEHUB_API_KEY` | Read access to `/sources` routes |
| `GRIEVANCEHUB_ADMIN_API_KEY` | Source administration (upload, sync, process, and related mutations) |
| `WEASYPRINT_DLL_DIRECTORIES` | Optional Windows helper when WeasyPrint cannot locate Pango DLLs |

`/sources` routes accept `Authorization: Bearer <key>` or `X-API-Key: <key>`. A local `.env` file is gitignored.

## Database migrations

With PostgreSQL running and `DATABASE_URL` configured:

```bash
alembic upgrade head
```

Alembic revisions live under `alembic/versions/`. The application expects PostgreSQL with the `vector` extension available for embedding storage.

## Running the application

```bash
uvicorn app.main:app --reload
```

Useful endpoints:

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check |
| `http://localhost:8000/docs` | Interactive OpenAPI (Swagger UI) |
| `http://localhost:8000/redoc` | ReDoc OpenAPI view |
| `http://localhost:8000/ui` | Steward verification shell |

## Running tests

```bash
python -m pytest tests/ -q
python -m pytest tests/ -m "not integration" -q
```

Most tests run without live external network calls. Opt-in live regression coverage is gated behind environment flags where present in the suite.

## API documentation

- Interactive OpenAPI UI: `/docs` when the application is running
- ReDoc: `/redoc`
- Case / saved-case UI contract notes: [`docs/saved_cases_ui_contract.md`](docs/saved_cases_ui_contract.md)
- System design: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

Primary route groups:

- `/cases` — case workspace, interactions, reports, grievances, artifacts, assets, and report export
- `/sources` — corpus listing, search, ask/report helpers, sync/process (API-key protected)
- `/ui` — verification shell

## Security posture and production readiness

Current posture:

- `/sources` routes require an interim server-configured API key (read vs administrative).
- Broader application authentication is not implemented for `/cases`, exports, or the verification UI.
- There is no multi-user identity system, session model, or role-based access control in the application layer.
- Retrieved source text is treated as untrusted evidence for downstream LLM prompts.
- Query length, retrieval fan-out, and embedding retries are bounded in application code.
- Process-wide request throttling is not provided by the application.

This codebase is suitable for local development and controlled internal evaluation. It is not production-hardened for public internet exposure.

## Documentation

| Document | Contents |
|----------|----------|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System design and subsystem behavior |
| [`docs/saved_cases_ui_contract.md`](docs/saved_cases_ui_contract.md) | Saved-case API/UI contract notes |
| [`PROJECT_STATE.md`](PROJECT_STATE.md) | Current engineering status tracking |
| [`.env.example`](.env.example) | Environment variable template |
