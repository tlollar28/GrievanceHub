# GrievanceHub

**A case-management and document-workflow application for union grievance work.**

GrievanceHub is a full-stack software engineering portfolio project built around a practical problem: keeping case conversations, evidence, research, and grievance documents connected to a single case record.

The application combines a React interface with a Python API, PostgreSQL persistence, and retrieval over indexed reference material. It supports structured case workflows rather than treating each interaction as an isolated chat.

## Application overview

- **Case workspaces** organize case information, conversation history, evidence, and workflow records.
- **Contextual conversations** retain the relationship between messages and the active case.
- **Case Memory** stores structured facts and case context alongside conversation records.
- **Reference research** uses indexed documents and source-linked retrieval.
- **Analysis reports** present generated analysis for review and can be saved as case artifacts.
- **Grievance documents** use Step 1 and Step 2 form templates.
- **Artifact history** keeps saved documents associated with their cases.

Analysis and grievance generation are explicit user actions; a conversation alone does not create an official case document.

## Technical overview

| Layer | Technologies |
| --- | --- |
| Interface | React, TypeScript, Vite, TanStack Query |
| API | Python, FastAPI, Pydantic |
| Persistence | PostgreSQL, SQLAlchemy, Alembic |
| Retrieval | pgvector, OpenAI embeddings |
| Documents | pypdf, Jinja2, WeasyPrint |
| Testing | pytest, Vitest, React Testing Library |

The frontend communicates with FastAPI endpoints. Domain services handle case operations, retrieval, and document generation. PostgreSQL holds structured case records and indexed reference data; uploaded files and generated documents are handled separately.

See [Architecture](docs/ARCHITECTURE.md) for a concise technical description of the implemented system.

## Repository layout

| Directory | Contents |
| --- | --- |
| `app/` | Backend API, services, models, schemas, and templates |
| `frontend/` | React application |
| `alembic/` | Database migrations |
| `tests/` | Backend automated tests |
| `docs/` | Public technical documentation |

## Portfolio and rights

This repository is publicly visible **solely for professional portfolio review**. It is not offered as an open-source project, a software distribution, or an invitation to run, reproduce, modify, redistribute, or deploy the application.

**Copyright © 2026 Tristan Lollar. All rights reserved.** See [LICENSE.md](LICENSE.md) for the rights notice and applicable limitations. Third-party components and reference materials remain subject to their respective rights.
