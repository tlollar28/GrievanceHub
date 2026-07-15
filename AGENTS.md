# GrievanceHub Agent Instructions

Permanent guidance for AI agents and developers working on GrievanceHub.

## Product Purpose

GrievanceHub is a production-grade union case management and grievance research platform for USPS/NPMHU stewards. The backend produces structured **GrievanceHub Analysis Reports** from steward questions, case facts, uploaded files, and retrieved official sources.

## Permanent Product Principle

**The application manages the workflow. The steward manages the grievance.**

GrievanceHub is an AI-first case workspace. Case-specific AI chat is always present on active case-work pages. Chat submission automatically persists conversation, refreshes analysis, and advances the current immutable report version. Stewards must not be required to click Save Context, Update Analysis, Reanalyze, or Start Chat. Canonical chat route: `POST /cases/{case_uuid}/interactions`. Generate Grievance remains an explicit optional action.

## Approved Sources (Strict)

Use **only** these source types in retrieval and analysis:

- `CONTRACT` — National Agreement
- `CIM` — Contract Interpretation Manual
- `ELM` — Employee and Labor Relations Manual
- `LMOU` — Local Memorandum of Understanding

**Do not add** MRS, JCAM, Step 4 settlements, arbitration awards, union bylaws, or handbooks as searchable source types. CIM text may reference Step 4 grievances as citations within approved sources; do not ingest Step 4 as a separate source.

## Analysis Pipeline

```
Question (+ case context)
  → LegalIssueAnalyzer          (neutral issue decomposition)
  → KnowledgeRetrievalService   (embedding search + relevance scoring)
  → AuthorityRanker             (LLM classification + post-filters)
  → EvidenceExtractor           (grounded quotes)
  → ReportBuilder               (structured GrievanceHub report)
  → CitationValidator           (quote grounding check)
  → AnalysisService             (API response)
```

### Relevance Gates (Do Not Bypass)

| Stage | File | Gate |
|-------|------|------|
| Retrieval | `app/services/knowledge_retrieval_service.py` | Min embedding similarity, boilerplate exclusion, combined score |
| Ranking | `app/services/authority_ranker.py` | Min relevance score, distinctive keyword overlap, quote grounding |
| Key issues | `app/services/report_builder.py` | Min key-authority relevance score |
| Citations | `app/services/citation_validator.py` | Quotes must exist in source excerpts |

Configuration: `app/retrieval_config.py`

## GrievanceHub Analysis Report (Required Sections)

Every completed report must dynamically include these sections when supported by facts and authorities. Headings stay consistent; content is generated from the user's question, facts, uploads, and retrieved sources.

1. GrievanceHub Analysis Report title
2. Generated date and user/case information
3. Research-draft disclaimer
4. Your Question
5. Quick Assessment
6. Key Contract Violations / Key Contract Issues
7. Recommended Remedy
8. Detailed Analysis (Grievance Framework, Evidence to Gather, Strategic Tips)
9. Matching Grievance Templates
10. Source citations (document names, pages, sections, direct quotes)
11. Limitations / missing facts

Brand as **GrievanceHub only** — never CREA.

Structured schema: `app/schemas/report_schema.py`

## Case Workspace (Implemented through W3)

GrievanceHub is an AI-powered living grievance case workspace — not a basic chatbot. Each steward question creates a saved **GrievanceCase**. Case-specific AI chat, facts, uploads/assets, report versions, timeline, and draft foundations stay attached to that case.

**Permanent product principle:** The application manages the workflow. The steward manages the grievance.

### Implemented (W1–W3 committed)

- Case API routes (`/cases/*`), saved-case list/open/reopen, workspace payload, timeline
- Persistent case-specific AI conversation via canonical `POST /cases/{case_uuid}/interactions`
- Automatic analysis refresh after each interaction (new immutable `CaseReportVersion`; older versions retained)
- Follow-up chat service (`FollowUpChatService`) used by interactions and compatibility routes
- First-class Case Assets (`case_assets` + local `data/case_assets/`)
- Grievance template registry and Step 2 draft-builder foundation (Local 300 Form 79-1 only)
- Case step progression services/tables (initialization on case create deferred to W4)
- HTML preview/download and PDF export of analysis reports

### Compatibility / non-steward UI surfaces

- `POST /messages`, `POST /followups`, `POST /reports/regenerate`, and `save_and_update_analysis` remain for API compatibility
- The steward-facing **Update Analysis** button is obsolete — analysis refreshes from chat interactions

### Not yet implemented / deferred

- W4 — enriched reopen workspace; step progression initialization on case creation
- W5 — Generate Grievance execution (route/contract exists; execution deferred)
- Full draft persistence/edit/print of filled forms
- React/Next steward UI (no frontend app in repo)
- Production authentication / RBAC (required before production use)
- LMOU, arbitration, and supervisor-manual ingestion
- Agentic / multi-agent / graph-RAG workflows (future roadmap only)

### Template availability

- Step 2 Local 300 Form 79-1 — only currently buildable form template
- Step 1 — not available (`unconfirmed_pending_steward_confirmation`)
- Step 3 — deferred (`deferred_separate_form_required`)

## Development Rules

1. **Never hard-code** a specific grievance type (Article 10, leave, discipline, etc.) in production logic.
2. **Never hard-code** example answers or pre-written conclusions.
3. Use issue-aware keyword scoring (`app/services/relevance_utils.py`), not topic-only matching.
4. Preserve `management_limiting` authorities in their dedicated report section.
5. Update tests when changing relevance behavior.
6. Update `PROJECT_STATE.md` after significant work.

## Commands

```bash
# Database
docker compose up -d

# Migrations
alembic upgrade head

# API
uvicorn app.main:app --reload

# Tests
pytest tests/ -v
```

## Change Checklist

- [ ] Relevance tests pass (`pytest tests/ -v`)
- [ ] No new disallowed source types
- [ ] Report branding remains GrievanceHub
- [ ] `PROJECT_STATE.md` updated
