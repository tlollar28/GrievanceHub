# GrievanceHub — System Architecture

GrievanceHub is organized around the **case** as its primary application record. Conversations, evidence, case context, generated reports, grievance forms, and workflow history are associated with a case rather than managed as unrelated documents.

## Component overview

```text
React / TypeScript interface
            |
            v
      FastAPI routes
            |
            v
     Domain services
       /         \
      v           v
PostgreSQL     File storage
+ pgvector     Evidence and
               generated documents
            |
            v
   Model and retrieval services
```

The diagram describes application responsibilities rather than a particular deployment environment.

## Interface and API

The React frontend contains case workspaces and dedicated views for conversation, evidence, analysis, grievance documents, saved artifacts, workflow, and research.

The frontend API layer is under `frontend/src/api/`; components and feature modules live under `frontend/src/`.

FastAPI endpoints are organized in `app/api/routes/`. Pydantic schemas in `app/schemas/` represent the request and response contracts. Domain behavior is implemented in `app/services/`.

## Data and persistence

SQLAlchemy models in `app/database/` represent case records and related entities. PostgreSQL holds structured case data, case messages, Case Memory records, workflow events, and references to saved artifacts.

Alembic manages schema changes. Indexed reference passages also reside in PostgreSQL; pgvector supports vector similarity search.

Evidence files and generated documents are maintained separately from the relational records that describe them.

## Research and analysis

The retrieval layer searches indexed reference material and retains source relationships for supporting passages. Model-backed services use retrieved material and case context to support case conversations and analysis report generation.

The application's case-management operations are distinct from its research and document-generation operations.

## Documents and case workflow

A case may contain evidence attachments, generated analysis reports, and Step 1 or Step 2 grievance forms. Document generation is initiated explicitly in the interface.

The backend uses PDF form templates for grievance documents and HTML/PDF rendering for analysis reports. Saved artifacts and their associated case history remain available through the application.

## Code organization

| Path | Responsibility |
| --- | --- |
| `app/main.py` | API application entry point |
| `app/api/routes/` | HTTP endpoints |
| `app/services/` | Case, retrieval, and document business logic |
| `app/database/` | Persistence models and sessions |
| `app/schemas/` | API data contracts |
| `app/templates/reports/` | Analysis report templates |
| `frontend/src/` | Interface, components, and API clients |
| `alembic/versions/` | Database schema migrations |
| `tests/` | Backend tests |

This document describes the architecture visible in the portfolio source code. It is not an installation or deployment guide.
