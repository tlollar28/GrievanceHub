# GrievanceHub Agent Instructions

Permanent guidance for AI agents and developers working on GrievanceHub.

## Product Purpose

GrievanceHub is a production-oriented union case-management and grievance
research platform for USPS/NPMHU stewards. It manages persistent grievance case
workspaces and produces structured **GrievanceHub Analysis Reports** from
steward questions, case facts, approved case context, and retrieved official
sources.

The repository is under active development and is not yet production-ready for
sensitive grievance data.

## Ownership and Publication

GrievanceHub is Tristan Lollar's project. The repository may be publicly visible
for portfolio review, professional evaluation, and educational demonstration.

- **No software license has been granted.** Do not call the project open source.
- **Never add a LICENSE file** without explicit user approval.
- Do not add clone, deployment, or contribution language that implies public
  reuse, redistribution, or permission to fork, modify, or deploy the code.
- Official USPS/NPMHU reference documents remain the property of their
  respective owners and must be distinguished from application code.
- Never commit employee information, real grievance data, uploads, generated
  forms, private union documents, secrets, credentials, or real `.env` files.
- Before significant work, read `AGENTS(2).md` (agent instructions),
`PROJECT_STATE.md`, `docs/ROADMAP.md`, `README.md`, and the relevant documents
under `docs/`.

## Permanent Product Principle

**The application manages the workflow. The steward manages the grievance.**

GrievanceHub is an AI-first case workspace, not a disposable chatbot.

- Case-specific chat persists conversation.
- Normal chat may retrieve indexed sources, return grounded citations, and
  update Case Memory.
- Normal chat does **not** create an analysis-report version, grievance artifact,
  or Official Case Record entry.
- Generate Analysis Report and Generate Grievance are explicit steward actions.
- Save / Save and Print are the first persistence points for versioned official
  artifacts.
- There is no required Conversation → Analysis → Grievance sequence.

Canonical chat route:

```http
POST /cases/{case_uuid}/interactions
```

## Engineering Roadmap

Historical commits use earlier internal labels such as `Phase 0`, `Phase 1.x`,
`Phase 2`, and `Phase 3`. Those labels remain part of Git history. The canonical
roadmap is [`docs/ROADMAP.md`](docs/ROADMAP.md). Concise status is in
[`PROJECT_STATE.md`](PROJECT_STATE.md).

### Completed and committed

1. **W1 — Case Interaction Contract**
2. **W2 — AI Case Interaction Orchestration**
3. **W3 — Case Evidence and Asset Management**
4. **W4 — Case Lifecycle, Memory, Workflow, and Artifacts**
5. **W5 — Knowledge Foundation**
   - Official Step 1 and Step 2 forms
   - Supervisor Manual corpus support
   - Source processing lifecycle
   - Bounded retrieval agents
   - Interim `/sources` API-key boundary

### Planned (authoritative post-W5 sequence)

6. **W6 — Interactive Steward Workspace** (next; not started)
7. **W7 — RAG Evaluation and Output Quality**
8. **W8 — Multi-Agent Authority Workflow**
9. **W9 — Security and Governance**
10. **W10 — LMOU and Arbitration Knowledge Expansion**
11. **W11 — Production Packaging and Deployment**

The former post-W5 sequence (W6 Security → W7 Steward UI → W8 Arbitration/LMOU →
W9 Deployment) is superseded. Do not describe W6 as Security Foundation. Do not
replace the W-series roadmap with older internal phase labels.

## Source Policy

### Current repository retrieval corpus

The committed local-development index currently includes:

- `CONTRACT` — National Agreement
- `CIM` — Contract Interpretation Manual

Live retrieval coverage depends on the configured running database index.

### Planned corpus expansion

- Supervisor Manual materials are part of the completed W5 knowledge foundation
  when synchronized and processed in the running environment
- W10: permission-aware LMOU and arbitration ingestion (after W9 security)

Do not ingest a new source class, protected document, arbitration decision,
settlement, handbook, private union document, or case file without explicit
approval and the required permission, security, and provenance controls.
Operational LMOU / arbitration expansion must wait until W9 is complete.

Never treat private grievance facts, employee data, or unauthorized documents as
publishable source material.

## Analysis Pipeline

```text
Question + case context
  → LegalIssueAnalyzer
  → KnowledgeRetrievalService
  → AuthorityRanker
  → EvidenceExtractor
  → ReportBuilder / NarrativeGenerator
  → CitationValidator
  → AnalysisService
```

Normal chat shares retrieval infrastructure but does not run the complete
report-construction pipeline.

### Relevance and grounding controls

| Stage | Primary module | Control |
|-------|----------------|---------|
| Retrieval | `app/services/knowledge_retrieval_service.py` | Similarity, boilerplate exclusion, and combined scoring |
| Ranking | `app/services/authority_ranker.py` | Relevance and authority controls |
| Report construction | `app/services/report_builder.py` | Structured issue and authority assembly |
| Citations | `app/services/citation_validator.py` | Quote grounding against retrieved source text |

Do not bypass retrieval relevance, provenance, or citation-grounding controls.

## GrievanceHub Analysis Report

Completed reports should include the supported portions of:

1. GrievanceHub Analysis Report title
2. Generated date and user/case information
3. Research-draft disclaimer
4. Your Question
5. Quick Assessment
6. Key Contract Violations / Key Contract Issues
7. Recommended Remedy
8. Detailed Analysis
9. Matching Grievance Templates
10. Source citations
11. Limitations / missing facts

Brand reports as **GrievanceHub** only.

Structured schema: `app/schemas/report_schema.py`.

## Current Case Workspace

### Implemented through W5

- Case create, open, reopen, and workspace restoration
- Persistent case-specific AI conversation
- Indexed-source retrieval for normal chat
- Case Memory and Case Overview
- Domain events and workflow FSM
- Saved-case dashboard and reopen API
- Case assets and uploads
- Explicit Generate Analysis preview
- Explicit Generate Grievance field-value draft
- Save / Save and Print artifact persistence
- Artifact library and Official Case Record
- Analysis-report HTML/PDF export
- FastAPI steward verification shell at `/ui`
- Official USPS Step 1 and Step 2 AcroForm fill/export
- Supervisor Manual corpus support and source lifecycle metadata
- Bounded retrieval-agent architecture
- Interim `/sources` API-key authentication

### Compatibility surfaces

Compatibility routes such as `/messages`, `/followups`, and report-regeneration
routes may remain for existing API clients. The canonical steward chat path is
`POST /cases/{case_uuid}/interactions`.

### Not yet implemented

- Interactive steward workspace (W6)
- Formal RAG evaluation and quality gates (W7)
- Multi-agent authority workflow product system (W8)
- Application identity and governance (W9)
- Permission-aware arbitration and LMOU corpus expansion (W10)
- Production packaging and deployment (W11)

### Form status

Official Step 1 and Step 2 AcroForm fill/export is implemented as part of W5.
Do not represent the wider application as production-ready for sensitive
operational data.

## Development Rules

1. Never hard-code a specific grievance type in production logic.
2. Never hard-code example answers or pre-written conclusions.
3. Preserve retrieval relevance, provenance, and citation-grounding controls.
4. Preserve management-limiting authorities in their intended report sections.
5. Update tests when behavior changes.
6. Update `PROJECT_STATE.md`, `docs/ROADMAP.md`, `README.md`, and architecture
   documentation after significant milestone changes.
7. Use the W1–W11 roadmap in `docs/ROADMAP.md` consistently; treat older phase
   names and the superseded post-W5 sequence as historical only.
8. Never add a LICENSE without explicit user approval.
9. Never commit secrets, real `.env` files, employee/case data, uploads, case
   assets, generated forms, or private union documents.
10. Prefer small, reviewable edits and run focused tests before the full suite.

## Commands

```bash
# Database
docker compose up -d

# Migrations
alembic upgrade head

# API
uvicorn app.main:app --reload

# Focused tests
python -m pytest <relevant test files> -q

# Full non-integration suite
python -m pytest tests/ -m "not integration" -q
```

## Change Checklist

- [ ] Focused tests pass
- [ ] Full non-integration suite passes when appropriate
- [ ] No unauthorized source types or private documents were added
- [ ] Citation and provenance controls remain intact
- [ ] Report branding remains GrievanceHub
- [ ] `PROJECT_STATE.md`, `docs/ROADMAP.md`, `README.md`, and architecture docs are current
- [ ] W1–W11 roadmap terminology is consistent with `docs/ROADMAP.md`
- [ ] No LICENSE was added without explicit approval
- [ ] No secrets or private case data were committed
