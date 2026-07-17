# GrievanceHub

GrievanceHub is an internal AI-assisted grievance management platform for authorized union stewards. It supports grievance research, case management, document analysis, official grievance workflows, and AI-assisted case preparation.

This repository exists for educational and portfolio purposes. It includes only public-safe source code, documentation, tests, and approved sample assets. It is not intended for public production deployment by third parties.

## Notice

Confidential materials are intentionally excluded, including:

- grievance case data and employee information
- arbitration decisions, settlements, and LMOUs
- uploaded evidence and generated grievance forms
- local databases, API secrets, and production configuration

Only public-safe code, documentation, tests, and approved sample assets belong here.

## Product principle

**The application manages the workflow. The steward manages the grievance.**

Case-specific AI chat persists conversation, refreshes analysis, and advances immutable report versions automatically. Structured GrievanceHub Analysis Reports are grounded in approved official sources (CONTRACT, CIM, ELM, and LMOU when ingested).

## Stack

- FastAPI / Python
- PostgreSQL 16 + pgvector
- OpenAI embeddings and chat
- SQLAlchemy / Alembic
- Jinja2 HTML + WeasyPrint PDF export
- pytest

## Local development

```bash
docker compose up -d
cp .env.example .env   # set OPENAI_API_KEY and DATABASE_URL
alembic upgrade head
uvicorn app.main:app --reload
python -m pytest tests/ -v
```

See `AGENTS.md` for product rules and `PROJECT_STATE.md` for implementation status.
