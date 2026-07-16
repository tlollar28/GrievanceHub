# GrievanceHub

AI-powered grievance case analysis and workflow platform for USPS/NPMHU stewards.

> **Development status:** This repository represents an active portfolio and product-development project. GrievanceHub is not currently production-ready. Authentication, authorization, security hardening, and additional safeguards are still under development. Sensitive grievance or employee information must not be used with the application at this stage.

## Copyright & Use Notice

© 2026 Tristan Lollar. All Rights Reserved.

This repository is made publicly available for portfolio, educational, and professional evaluation purposes only.

No license has been granted for this source code.

Except where required by law, no permission is granted to copy, modify, distribute, sublicense, deploy, create derivative works from, or commercially use any portion of this repository without prior written permission from the copyright holder.

Official USPS and NPMHU contractual source documents included or referenced within this project remain the property of their respective owners and are used as publicly available reference materials for grievance analysis.

## Product Vision

**The application manages the workflow. The steward manages the grievance.**

GrievanceHub is a persistent case workspace, not a basic chatbot. Conversations, evidence, grounded analysis, and versioned history stay attached to each saved case. The application handles persistence, analysis refresh, and workflow structure; the steward remains responsible for judgment and filing decisions.

## Why GrievanceHub?

Traditional grievance work often relies on manual document review, fragmented notes, repetitive drafting, and maintaining context across multiple grievance steps.

GrievanceHub centralizes case evidence, grounded AI analysis, versioned reports, persistent case interaction, and structured grievance workflows into a single workspace. The project is informed by prior USPS operations and union steward experience.

## Current Backend Capabilities

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

Canonical case chat route:

```http
POST /cases/{case_uuid}/interactions
```

Stewards are not required to click Save Context, Update Analysis, Reanalyze, or Start Chat. Generate Grievance remains an explicit optional action; execution is planned for Grievance Draft Generation.

## Architecture

| Layer | Role |
|-------|------|
| API | FastAPI routes for cases, sources, and exports |
| Services | Case workspace orchestration, RAG pipeline, drafts, and assets |
| Data | PostgreSQL + pgvector |
| RAG | Issue analysis → retrieval → authority ranking → grounded report |
| Case workspace | Conversations, facts, versions, timeline, and reopen |
| Case assets | Case-owned uploaded documents (local storage) |
| Templates / drafts | Registry + Step 2 draft builder foundation |

```text
Create / Open Case
        ↓
Persistent Case Interaction
        ↓
Grounded RAG Analysis
        ↓
Immutable Analysis Versions
        ↓
Generate Grievance (planned)
```

See `docs/ARCHITECTURE.md` and `AGENTS.md` for details.

## Development Environment

This project is developed and verified in a reproducible engineering environment using:

- **Python** with **FastAPI**, **Uvicorn**, and **Pydantic**
- **SQLAlchemy** and **Alembic** for ORM and migrations
- **PostgreSQL 16** with **pgvector** via **Docker Compose**
- **OpenAI API** for embeddings and chat-backed analysis
- **pytest** for automated tests
- **Swagger / OpenAPI** (FastAPI interactive docs) for API inspection
- **Jinja2** and **WeasyPrint** for HTML/PDF analysis-report export

Maintainer workflow (technical evidence of the environment; not an invitation to reuse or redistribute this project):

- Start local database services with Docker Compose
- Apply schema migrations with Alembic (`alembic upgrade head`)
- Run the API with Uvicorn (`uvicorn app.main:app`)
- Verify behavior with pytest

Environment variables are documented in `.env.example` (placeholders only). A real `.env` with secrets is never committed. Official CONTRACT / CIM / ELM binaries are not committed; the repository tracks source manifests and a committed text-chunk index. Blank Local 300 templates under `app/assets/grievance_templates/` are tracked.

On Windows, WeasyPrint PDF export requires MSYS2 Pango (`mingw-w64-x86_64-pango`); see comments in `requirements.txt`.

## Development Status

| Area | Status |
|------|--------|
| Case Interaction Contract | Complete |
| AI Case Interaction Orchestration | Complete |
| Case Evidence and Asset Management | Complete |
| Case Lifecycle and Workspace Restoration | Next |
| Grievance Draft Generation | Following |
| Grievance draft persistence / revision / export | Later |
| Steward Workspace User Interface (React / Next) | Planned (not in repo) |
| Authentication and Role-Based Access Control | Required before production use |
| Protected Source Corpus Expansion | Planned |
| Controlled Agentic Workflow Orchestration | Long-term roadmap only |

Template note: only **Step 2 Local 300 Form 79-1** is currently buildable. Step 1 and Step 3 templates are not yet available. Step progression services and tables exist; initialization on case creation is part of Case Lifecycle and Workspace Restoration.

## Project Roadmap

### Next

- **Case Lifecycle and Workspace Restoration** — automatic step-progression initialization; enriched reopen workspace with full conversation, analysis, assets, timeline, step state, outcomes, drafts, and available actions

### Following

- **Grievance Draft Generation** — explicit Generate Grievance action; current analysis and case-state assembly; Step 2 Local 300 draft generation; snapshot/provenance integration

### Later

- **Grievance Draft Persistence and Versioning**
- **Grievance Revision Workflow**
- **Grievance Review, Approval, and Export** (printable grievance PDF/DOCX; distinct from analysis-report export)
- **Interaction API Consolidation** and **Legacy API Retirement**
- **Client Integration Layer**
- **Authentication and Role-Based Access Control**
- **Steward Workspace User Interface**
- **Protected Source Corpus Expansion**
- **Case Evidence Retrieval and RAG**
- **Production Deployment and Infrastructure**

### Long-term

- **Controlled Agentic Workflow Orchestration**
- **Multi-Agent Case Analysis**
- **Graph-Enhanced Retrieval**

These long-term tracks are roadmap language only and are **not** implemented.

## Documentation

| Doc | Purpose |
|-----|---------|
| `AGENTS.md` | Permanent product and agent rules |
| `PROJECT_STATE.md` | Phase history and verification record |
| `docs/ARCHITECTURE.md` | Current architecture |
| `docs/saved_cases_ui_contract.md` | Deferred saved-cases UI contract |

## Safety Notice

This repository is under active development and is **not** currently production-ready for sensitive grievance data. Do not use real grievance or employee information until authentication, authorization, and related safeguards are in place.
