# GrievanceHub Architecture

GrievanceHub is an AI-powered living grievance case workspace for USPS/NPMHU
stewards. The application manages workflow automation; the steward manages the
grievance.

This document describes the **current implemented architecture** (through
Phase W3). Planned frontend, auth, and agentic systems are roadmap items only.

## Permanent Product Principle

**The application manages the workflow. The steward manages the grievance.**

- Canonical case chat: `POST /cases/{case_uuid}/interactions`
- Chat submission persists conversation, refreshes analysis, and advances the
  immutable report version automatically
- Stewards must not be required to click Save Context, Update Analysis,
  Reanalyze, or Start Chat
- Generate Grievance remains an explicit optional action
  (`POST /cases/{case_uuid}/actions`, execution planned for W5)

## Current Stack (Implemented)

| Layer | Technology |
|-------|------------|
| API | FastAPI (Python), Uvicorn |
| ORM / migrations | SQLAlchemy, Alembic |
| Database | PostgreSQL 16 + pgvector (Docker Compose) |
| Embeddings / LLM | OpenAI (`text-embedding-3-small`, `gpt-4o-mini`) |
| Report export | Jinja2 HTML + WeasyPrint PDF |
| Tests | pytest |

**Not present in the current repository:** React/Next.js frontend, LangChain,
PyTorch/TensorFlow/Hugging Face ML stacks, Redis/Celery workers, Kubernetes/
Terraform production deploy configs with content, or GitHub Actions CI workflows.

Empty `frontend/`, `backend/`, and scaffold `infra/` directories may exist as
placeholders only.

## High-Level Shape

```text
Steward / API client
  → FastAPI routes (/cases, /sources, export routes, legacy upload helpers)
    → Case workspace orchestration (interactions, actions, assets, saved cases)
      → Analysis pipeline (RAG + structured report)
      → PostgreSQL + pgvector
      → Local case asset / generated-form storage (gitignored)
```

## API Layer

Primary routers (registered in `app/main.py`):

| Area | Module | Role |
|------|--------|------|
| Cases | `app/api/routes/cases.py` | Create/list cases, workspace, interactions, actions, assets, saved reopen, follow-ups, versions |
| Sources | `app/api/routes/sources.py` | Source ingest/search/report helpers |
| Exports | `app/api/routes/exports.py` | HTML/PDF analysis-report export |

Canonical steward chat:

```http
POST /cases/{case_uuid}/interactions
```

Other important surfaces:

- `GET /cases/{case_uuid}/workspace` — workspace aggregate (messages, versions, assets)
- `GET/POST /cases/saved...` — saved-case list, open, reopen, timeline
- `GET/POST /cases/{case_uuid}/assets` — Case Assets
- `POST /cases/{case_uuid}/actions` — Generate Grievance (W5) + compatibility actions
- Export preview/download HTML/PDF under `/cases/{case_uuid}/export/...`

## Services / Orchestration

| Concern | Primary modules |
|---------|-----------------|
| Case lifecycle | `case_service.py`, `saved_case_service.py` |
| AI-first chat + analysis refresh | `case_workspace_action_service.py`, `follow_up_chat_service.py` |
| Case assets | `case_asset_service.py` |
| Step progression | `case_step_progression_service.py`, `case_step_progression_persistence_service.py` |
| Template / draft foundation | `grievance_template_registry.py`, `grievance_form_draft_builder.py` |
| Analysis pipeline | `analysis_service.py` + retrieval/ranking/report builders |
| Export | `report_export_service.py`, `app/services/report_export/` |

## Analysis (RAG) Pipeline

```text
Question (+ case context)
  → LegalIssueAnalyzer
  → KnowledgeRetrievalService (embeddings + relevance gates)
  → AuthorityRanker (LLM classification + post-filters)
  → EvidenceExtractor (grounded quotes)
  → ReportBuilder / NarrativeGenerator
  → CitationValidator
  → AnalysisService response + CaseReportVersion persistence
```

Approved searchable source types only: `CONTRACT`, `CIM`, `ELM`, `LMOU`.

**Current corpus status:** CONTRACT and CIM are actively used in the indexed
artifact/`source_index` path. LMOU is approved but not ingested. Arbitration
awards, settlements, and supervisor manuals are **not** implemented as source
types.

Relevance gates live in `app/retrieval_config.py` and must not be bypassed.

## Case Workspace Model

Core persistence (Alembic migrations through `d5e6f7a8b9c0`):

- `GrievanceCase` — saved research/case session
- `CaseMessage` — conversation history
- `CaseReportVersion` — immutable structured report JSON
- `CaseStep` / `CaseStepOutcome` / `CaseTimelineEventRecord` / `CaseFormDraftRecord`
- `CaseAsset` — first-class case-owned artifacts

Workflow (current):

```text
Create / Open Case
  → Chat with case-specific AI (/interactions)
  → Add context / evidence (facts, assets, upload refs)
  → Analysis automatically refreshes and versions
  → Continue interacting
  → Generate Grievance later when W5 execution is available
```

## Case Assets

Categories reserved in schema; W3 executable category is `uploaded_document`.

Local storage: `data/case_assets/{case_uuid}/` (gitignored). Cloud storage and
case-file RAG ingestion are not implemented.

## Template / Draft Foundations

- Blank templates under `app/assets/grievance_templates/`
- Only **Step 2 Local 300 Form 79-1** is currently buildable
- Step 1 template unavailable; Step 3 deferred
- Draft builder produces structured draft models; filled-form export/print is
  not complete
- Step progression tables/services exist; **initialization on case create is
  deferred to W4**

## Security / Auth (Current Reality)

- Development/local routes use an auth stub for exports
- Production authentication and RBAC are **not implemented**
- Sensitive grievance data is expected inside an authorized steward/admin app;
  public anonymous access must not be allowed in production
- Runtime outputs (`data/reports/`, `data/case_assets/`, generated forms,
  uploads) are gitignored and must not be committed

## Roadmap (Not Current Features)

- W4 — enriched reopen workspace; progression init on case create
- W5 — Generate Grievance execution
- Draft persistence / edit / print
- Auth / RBAC
- React/Next steward UI
- Expanded source corpus (LMOU, controlled future sources)
- Controlled future agentic / multi-agent workflows (not current architecture)

## Related Docs

- `AGENTS.md` — permanent agent/product rules
- `PROJECT_STATE.md` — phase history and verification record
- `docs/saved_cases_ui_contract.md` — deferred UI contract for saved cases
- `README.md` — employer-facing project overview
