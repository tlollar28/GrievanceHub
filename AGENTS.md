# GrievanceHub Agent Instructions

Permanent guidance for AI agents and developers working on GrievanceHub.

## Product Purpose

GrievanceHub is a production-grade union case management and grievance research platform for USPS/NPMHU stewards. The backend produces structured **GrievanceHub Analysis Reports** from steward questions, case facts, uploaded files, and retrieved official sources.

## Ownership and Publication

GrievanceHub is Tristan Lollar’s project. This repository may be publicly visible for portfolio review, professional evaluation, and educational demonstration.

- **No software license has been granted.** Do not call the project open source.
- **Never add a LICENSE file** (MIT, Apache-2.0, GPL, BSD, Creative Commons, or any other) without explicit user approval.
- Do not add clone/deploy/contributing instructions that imply public reuse, redistribution, or permission to fork, modify, or deploy the code.
- Public visibility does not grant reuse rights. See README **Copyright & Use Notice**.
- Official USPS/NPMHU contractual reference documents remain the property of their respective owners; distinguish them from Tristan’s application code.
- Preserve the public/private data boundary: never commit employee information, uploads, case assets, generated forms, arbitrations, settlements, private union documents, secrets, or real `.env` files.
- Before significant work, read current `AGENTS.md`, `PROJECT_STATE.md`, `README.md`, and relevant docs under `docs/`.

## Permanent Product Principle

**The application manages the workflow. The steward manages the grievance.**

GrievanceHub is an AI-first case workspace. Case-specific AI chat is always present on active case-work pages. Chat submission automatically persists conversation, refreshes analysis, and advances the current immutable report version. Stewards must not be required to click Save Context, Update Analysis, Reanalyze, or Start Chat. Canonical chat route: `POST /cases/{case_uuid}/interactions`. Generate Grievance remains an explicit optional action.

## Canonical Phase Names

Use these descriptive phase names in project status, roadmaps, and future prompts. **Do not reintroduce W-number shorthand** (W1, W2, W3, …) as primary phase names.

### Completed foundations

1. **Case Interaction Contract** — canonical interaction/action schemas and service boundaries
2. **AI Case Interaction Orchestration** — persistent case chat, AI response, automatic analysis refresh, immutable analysis versions
3. **Case Evidence and Asset Management** — first-class case assets, uploads, metadata, safe local storage, analysis-context references

### Next

4. **Case Lifecycle and Workspace Restoration** — automatic step-progression initialization; enriched reopen workspace

### Following

5. **Grievance Draft Generation** — explicit Generate Grievance; Step 2 Local 300 draft generation; snapshot/provenance

### Later

6. **Grievance Draft Persistence and Versioning**
7. **Grievance Revision Workflow**
8. **Grievance Review, Approval, and Export**
9. **Interaction API Consolidation**
10. **Client Integration Layer**
11. **Legacy API Retirement**

### Long-term feature tracks (descriptive names only)

- Authentication and Role-Based Access Control
- Steward Workspace User Interface
- Protected Source Corpus Expansion
- Case Evidence Retrieval and RAG
- Production Deployment and Infrastructure
- Controlled Agentic Workflow Orchestration
- Multi-Agent Case Analysis
- Graph-Enhanced Retrieval

## Approved Sources (Strict)

Use **only** these source types in retrieval and analysis:

- `CONTRACT` — National Agreement
- `CIM` — Contract Interpretation Manual
- `ELM` — Employee and Labor Relations Manual
- `LMOU` — Local Memorandum of Understanding

**Do not add** MRS, JCAM, Step 4 settlements, arbitration awards, union bylaws, or handbooks as searchable source types. CIM text may reference Step 4 grievances as citations within approved sources; do not ingest Step 4 as a separate source.

Public contractual source language (CONTRACT, CIM, ELM, blank Local 300 templates) is distinct from private case data. Never treat private grievance facts, employee data, or unauthorized private documents as publishable content.

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

## Case Workspace

GrievanceHub is an AI-powered living grievance case workspace — not a basic chatbot. Each steward question creates a saved **GrievanceCase**. Case-specific AI chat, facts, uploads/assets, report versions, timeline, and draft foundations stay attached to that case.

**Permanent product principle:** The application manages the workflow. The steward manages the grievance.

### Implemented (completed foundations)

- Case API routes (`/cases/*`), saved-case list/open/reopen, workspace payload, timeline
- Persistent case-specific AI conversation via canonical `POST /cases/{case_uuid}/interactions`
- Automatic analysis refresh after each interaction (new immutable `CaseReportVersion`; older versions retained)
- Follow-up chat service (`FollowUpChatService`) used by interactions and compatibility routes
- First-class Case Assets (`case_assets` + local `data/case_assets/`)
- Grievance template registry and Step 2 draft-builder foundation (Local 300 Form 79-1 only)
- Case step progression services/tables (initialization on case create deferred to Case Lifecycle and Workspace Restoration)
- HTML preview/download and PDF export of analysis reports

### Compatibility / non-steward UI surfaces

- `POST /messages`, `POST /followups`, `POST /reports/regenerate`, and `save_and_update_analysis` remain for API compatibility
- The steward-facing **Update Analysis** button is obsolete — analysis refreshes from chat interactions

### Not yet implemented / deferred

- Case Lifecycle and Workspace Restoration — enriched reopen workspace; step progression initialization on case creation
- Grievance Draft Generation — Generate Grievance execution (route/contract exists; execution deferred)
- Full draft persistence/edit/print of filled forms
- Steward Workspace User Interface (no React/Next frontend app in repo)
- Authentication and Role-Based Access Control (required before production use)
- Protected Source Corpus Expansion (LMOU, arbitration, and supervisor-manual ingestion)
- Controlled Agentic Workflow Orchestration / Multi-Agent Case Analysis / Graph-Enhanced Retrieval (long-term roadmap only)

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
7. Use canonical descriptive phase names only — do not reintroduce W-number shorthand.
8. Never add a LICENSE without explicit user approval; never imply open-source reuse permission.
9. Never commit secrets, real `.env` files, employee/case data, uploads, case assets, generated forms, or private union documents.

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
- [ ] Phase names remain descriptive (no W-number shorthand)
- [ ] No LICENSE added without explicit approval
