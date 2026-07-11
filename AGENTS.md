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

## Case Sessions and Follow-Up (Roadmap)

Each initial question creates a saved **GrievanceCase**. Follow-up questions retain original facts, report, sources, citations, and conversation context. Report versions are preserved (not silently overwritten).

Database models (Alembic migration `a1b2c3d4e5f6`):

- `GrievanceCase` — saved research session
- `CaseMessage` — conversation history
- `CaseReportVersion` — versioned structured report JSON

**Implemented:** case API routes (`/cases/*`), versioned report storage, HTML preview/download, PDF export.

**Not yet implemented:** follow-up chat service, grievance template storage, production authentication for export routes.

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
