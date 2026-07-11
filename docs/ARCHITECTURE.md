# GrievanceHub Architecture

GrievanceHub is a production-grade, AI-powered union case management platform.

The system is designed as a deployable SaaS application using:

- Next.js, React, TypeScript, and Node.js for the frontend
- FastAPI and Python for the backend
- PostgreSQL with pgvector for relational data and semantic search
- LangChain, PyTorch, TensorFlow, and Hugging Face for AI/ML workflows
- Redis and Celery for background jobs
- Docker, Kubernetes, Terraform, and AWS for deployment
- GitHub Actions for CI/CD

## Core Purpose

GrievanceHub helps union representatives manage grievance cases, analyze uploaded evidence, search official sources, generate reports, and interact with an AI assistant grounded in authoritative labor documents.

## Permanent Architecture Rule

This project is not being built as a temporary prototype.

All major implementation decisions should support the long-term production version of GrievanceHub.

## Permanent Product Principle (AI-first workspace)

**The application manages the workflow. The steward manages the grievance.**

GrievanceHub is an AI-first grievance case workspace. Case-specific AI chat is
always present on active case-work pages. Submitting a chat interaction
automatically persists conversation, merges safe context, refreshes analysis,
and advances the current immutable report version. The steward must not be
required to click Save Context, Update Analysis, Reanalyze, or Start Chat.

- Canonical chat: `POST /cases/{case_uuid}/interactions`
- Explicit optional action: `POST /cases/{case_uuid}/actions` with `generate_grievance`
- Each case owns an isolated conversation; context must never bleed across cases
- Chat does not appear on print/export/login/settings/admin-only pages
