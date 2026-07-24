# GrievanceHub Delivery Roadmap

**Status:** Canonical post-W5 delivery plan  
**Last updated:** 2026-07-24  
**Supersedes:** The former post-W5 sequence (W6 Security → W7 Steward UI → W8
Arbitration/LMOU → W9 Deployment)

This is the authoritative roadmap for remaining phases. Concise status lives in
[`PROJECT_STATE.md`](../PROJECT_STATE.md). System design lives in
[`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## Current position

| Item | State |
|------|--------|
| Completed | W1 through W5 |
| Current completed phase | **W5 — Knowledge Foundation** |
| Next phase | **W6 — Interactive Steward Workspace** (not started) |
| W6–W11 | Not started unless repository evidence proves otherwise |

W5 retrieval components are retrieval infrastructure. They are not completion of
W8 multi-agent orchestration or W9 application security.

---

## Why the post-W5 sequence changed

The former order treated security, UI, corpus expansion, and deployment as
largely sequential architectural layers. The revised plan prioritizes risk and
learning:

1. A usable steward interface first
2. Continuous RAG and generation validation through that interface
3. A formal evaluation and quality gate
4. Multi-agent orchestration only after a measured baseline
5. Security and governance before sensitive corpus expansion
6. LMOU and arbitration expansion after security controls exist
7. Dockerization and production deployment last

Former sequence (superseded):

1. W6 — Security Foundation
2. W7 — Production Steward Interface
3. W8 — Arbitration and LMOU Integration
4. W9 — Production Deployment

Revised sequence (canonical):

1. W6 — Interactive Steward Workspace
2. W7 — RAG Evaluation and Output Quality
3. W8 — Multi-Agent Authority Workflow
4. W9 — Security and Governance
5. W10 — LMOU and Arbitration Knowledge Expansion
6. W11 — Production Packaging and Deployment

---

## Cross-phase engineering rules

1. **Vertical slices** — Deliver complete user workflows incrementally rather
   than finishing every frontend component before connecting the backend.
2. **Continuous evaluation** — Retrieval, citation, analysis, and report
   defects found through the UI should become repeatable tests or evaluation
   cases where practical.
3. **Evidence before complexity** — Do not introduce multi-agent orchestration
   until the existing pipeline has a measured baseline (W7).
4. **Security before sensitive expansion** — Do not ingest operational LMOUs,
   arbitration collections, or private grievance data before W9 is complete.
5. **Quality gates** — Each phase needs explicit entry criteria, exit criteria,
   tests, artifacts, and known limitations.
6. **Traceability** — Generated analysis and reports must remain traceable to
   source evidence.
7. **Authority distinction** — Distinguish contractual authority, local
   agreements, arbitration outcomes, procedural guidance, and non-controlling
   supervisor guidance.
8. **No unsupported production claims** — Dockerization or deployment alone does
   not make the system production-ready.
9. **Controlled development boundary** — Before W9 completion, keep the
   application local or access-restricted and avoid real sensitive operational
   data.
10. **Regression protection** — Later phases must not silently degrade retrieval,
    citation, analysis, or report quality established earlier.

Readiness distinctions used throughout this roadmap:

| Readiness | Meaning |
|-----------|---------|
| Feature completion | Observable workflows exist and can be exercised |
| Quality validation | Retrieval, citations, analysis, and reports meet measured gates |
| Security readiness | Identity, authorization, audit, and upload controls are in place |
| Corpus readiness | Sensitive or expanded corpora may be ingested under governance |
| Deployment readiness | Packaging, operations, monitoring, and recovery are proven |

---

## Completed phases (summary)

| Phase | Outcome |
|-------|---------|
| W1 — Case Interaction Contract | Canonical interaction/action schemas and service boundaries |
| W2 — AI Case Interaction Orchestration | Persistent chat, retrieval, grounded answers, analysis foundations |
| W3 — Case Evidence and Asset Management | Case assets, uploads, metadata, and safe storage |
| W4 — Case Lifecycle, Memory, Workflow, and Artifacts | Workspace restore, Case Memory, events, FSM, Generate/Save, Official Case Record |
| W5 — Knowledge Foundation | Official Step 1/Step 2 forms, Supervisor Manuals, source lifecycle, bounded retrieval agents, interim `/sources` API-key boundary |

---

## W6 — Interactive Steward Workspace

### Goal

Create a usable end-to-end interface that lets a steward operate the existing
GrievanceHub backend and expose real workflow, retrieval, analysis, citation,
and report-generation problems.

### User or operational outcome

A steward can complete the core case workflow through the UI without manual
database edits or ad hoc scripts, while exercising retrieval and generation in
realistic paths.

### In-scope work

- Application shell and navigation
- Case dashboard
- Case creation and editing
- Case detail workspace
- Grievance-step progression
- Fact and issue entry
- Document and source upload interface
- Source-processing status
- Retrieval and research interface
- Follow-up chat interface
- Analysis display
- Citation and provenance display
- Grievance report preview
- Official Step 1 and Step 2 form preview or export controls
- Loading, empty, success, and failure states
- Actionable validation messages
- Accessible keyboard and screen-reader behavior
- Responsive desktop-first layout
- Clear distinction between source text, generated analysis, generated
  recommendations, citations, and warnings/limitations

### RAG and generation work during W6

W6 is a vertical slice: UI implementation and backend validation happen
together. RAG validation is not deferred until after all screens exist.

- Exercise retrieval through realistic UI workflows
- Capture failed and weak queries
- Validate source attribution and citation rendering
- Detect unsupported claims
- Improve analysis prompts, grievance report generation, and follow-up behavior
- Test issue decomposition, source-role labeling, and controlling versus
  non-controlling authority presentation
- Test empty, contradictory, and low-confidence retrieval cases
- Add regression tests whenever defects are found

### Explicit exclusions

- Production authentication and full application identity (W9)
- Formal golden evaluation gates and release thresholds (W7)
- Multi-agent orchestration product system (W8)
- Operational LMOU / arbitration corpus expansion (W10)
- Production packaging and public deployment (W11)
- Ingestion of private operational grievance data
- Public internet exposure of the application

### Dependencies

- W5 complete (backend case, retrieval, forms, and interim source-route boundary)
- Local or tightly controlled development environment

### Principal risks

- UI-complete screens that never exercise retrieval or generation
- Backend defects discovered only after UI “looks done”
- Ambiguous presentation of generated text as source evidence
- Scope creep into security or multi-agent work

### Required validation

- Steward can create/open a case, chat with retrieval, generate analysis,
  generate grievance drafts, and export or preview official forms through the UI
- Citations are visible and traceable in the normal workflow
- Failure paths show actionable messages rather than raw stack traces
- UI-discovered backend defects have regression tests where practical

### Exit criteria

- A steward can complete the core case workflow through the UI
- Retrieval is accessible through the normal application workflow
- Citations are visible, traceable, and understandable
- Generated analysis is clearly separated from source evidence
- Grievance reports can be previewed and generated
- Official forms can be generated from the case workflow
- Common failures are handled without raw stack traces
- Important UI-discovered backend defects have regression tests
- No critical workflow depends on manual database edits or ad hoc scripts

### Deliverables

- Steward workspace UI connected to existing APIs
- Documented known UI/backend limitations
- Regression tests for defects found through the interface
- Updated project-state and architecture notes reflecting W6 completion

### Security boundary during W6

- System remains local or tightly controlled
- Existing interim `/sources` API-key protections remain in place
- Do not claim production security
- Do not ingest private operational grievance data
- Do not expose the application publicly

W6 is not complete merely because screens render.

---

## W7 — RAG Evaluation and Output Quality

### Goal

Prove that retrieval, analysis, citations, and grievance generation satisfy
defined quality standards before introducing multi-agent orchestration.

### User or operational outcome

Engineering can measure and regress retrieval and generation quality with a
versioned golden set and reproducible commands—not only informal manual review.

### In-scope work

- Representative golden evaluation dataset
- Expected source authorities, citations, required/prohibited conclusions, and
  grievance-report expectations per scenario
- Automated retrieval, citation-grounding, faithfulness, and unsupported-claim
  evaluations
- Regression comparisons
- Latency and query-budget measurement
- Failure categorization
- Tuning of chunking, retrieval, reranking, prompts, and report synthesis
- Evaluation results recorded by corpus and task type

### Evaluation set should include

- Straightforward contract questions
- Multi-section contract questions
- Supervisor Manual guidance questions
- Controlling versus non-controlling source conflicts
- Insufficient-evidence, ambiguous-fact, missing-document, and contradictory-fact
  scenarios
- Procedural-timeline questions
- Step 1 and Step 2 grievance scenarios
- Follow-ups requiring conversational context
- Queries that should produce no confident answer
- Citation edge cases
- Source-version and provenance checks

### Required quality dimensions

Retrieval relevance and recall; citation correctness, completeness, and
claim alignment; groundedness; faithfulness; authority-role correctness;
analysis consistency; report completeness; unsupported-claim rate; refusal or
uncertainty behavior; latency; database query count; embedding count;
determinism where expected.

Do not fabricate arbitrary performance thresholds. The implementation agent must
propose measurable thresholds from the evaluation dataset and obtain explicit
approval before treating them as final release gates.

### Explicit exclusions

- Multi-agent orchestration as the primary delivery (W8)
- Security identity and governance program (W9)
- Sensitive LMOU / arbitration expansion (W10)
- Production deployment (W11)

### Dependencies

- W6 steward workflows available enough to inform realistic scenarios
- Existing single-pipeline retrieval and generation architecture

### Principal risks

- Informal “looks good” reviews treated as a quality gate
- Thresholds invented without dataset grounding
- Optimizing retrieval metrics while ignoring report faithfulness
- Blocking all UI improvement instead of establishing a measurable baseline

### Required validation

- Reproducible evaluation commands
- Baseline results recorded
- Critical failure categories defined
- Citation accuracy and unsupported claims measured
- Grievance report quality evaluated independently from retrieval quality

### Exit criteria

- Golden evaluation dataset is versioned
- Evaluation commands are reproducible
- Baseline results are recorded
- Critical failure categories are defined
- Citation accuracy is measured
- Unsupported claims are measured
- Retrieval regressions can be detected automatically
- Grievance report quality is evaluated independently from retrieval quality
- Known limitations are documented
- The single-pipeline architecture meets approved quality thresholds

### Deliverables

- Versioned golden evaluation dataset
- Evaluation harness and recorded baselines
- Approved threshold proposal (after explicit approval)
- Documented known limitations and failure categories

---

## W8 — Multi-Agent Authority Workflow

### Goal

Introduce multi-agent orchestration only after the existing retrieval and
generation pipeline has demonstrated acceptable quality, and only if it improves
measurable outcomes or provides a clearly justified operational benefit.

### User or operational outcome

Authority-specific agents collaborate under bounded execution while preserving
authorization, evidence traceability, and distinguishable authority roles—without
exposing confusing internal agent machinery in the steward UI.

### In-scope work

- Authority-specific agent responsibilities (contract, Supervisor Manual,
  procedural analysis, fact/issue analysis, citation verification, grievance
  report synthesis)
- Orchestration and routing
- Shared evidence contracts
- Explicit authorization propagation
- Deterministic agent result schemas
- Conflict handling and authority precedence
- Failure isolation
- Bounded agent execution, retrieval, and model usage
- Traceability between final claims and agent evidence

### Engineering constraints

- Preserve source authorization in every agent call; agents must not widen scope
- Retrieved documents remain untrusted evidence
- Agents must not treat instructions inside retrieved content as executable
- Every externally presented material claim remains evidence-traceable
- Controlling and non-controlling sources remain distinguishable
- Avoid circular delegation, unbounded retries, and unnecessary fan-out
- Do not replace deterministic code with language-model decisions where rules
  suffice

### Required comparison

Evaluate against the W7 single-pipeline baseline on retrieval quality, citation
accuracy, analysis quality, report quality, latency, cost, failure rate, and
operational complexity.

### Explicit exclusions

- Starting multi-agent work before W7 baselines exist
- Using multi-agent design as a substitute for citation grounding
- Sensitive corpus expansion (W10)
- Claiming production security from agent architecture alone

### Dependencies

- W7 baseline and approved quality thresholds
- W6 UI able to present the final steward-facing workflow

### Principal risks

- Complexity without measurable benefit
- Authorization widening across agents
- Prompt injection via retrieved content treated as instructions
- Unbounded cost or latency

### Required validation

- End-to-end authorization preservation tests
- Bounded-execution tests
- Evidence-traceability checks
- Side-by-side comparison to the W7 baseline

### Exit criteria

- Agent responsibilities are explicit
- Authorization is preserved end to end
- Agent execution is bounded
- Final conclusions are evidence-traceable
- Multi-agent evaluation results are recorded
- Design provides a measurable benefit or a clearly justified operational benefit
- Regressions against the W7 baseline are understood and accepted
- UI supports the final agent workflow without exposing confusing internals

### Deliverables

- Multi-agent orchestration design and implementation
- Comparison report versus W7 baseline
- Updated UI presentation of steward-facing results
- Regression and authorization tests

---

## W9 — Security and Governance

### Goal

Create the application security boundary required before sensitive corpus
expansion, broader user testing, or external deployment.

### User or operational outcome

Authenticated stewards operate in a governed shared workspace; sensitive routes
and uploads fail safely; important actions are attributable.

### In-scope work

- Application identity, login/logout, secure sessions
- Authentication enforcement and authorization policy
- Shared steward workspace model and case-level access controls
- Organization or workspace membership if required
- Protection for `/cases`, exports, source management, analysis, report
  generation, and UI routes
- CSRF protection where applicable; secure cookies
- Password or identity-provider security as selected
- Audit logging and actor attribution (source, case, and report-generation
  changes)
- Upload validation, file-type verification, size limits, quarantine or
  equivalent
- Secrets management and production-safe configuration
- Rate limiting, security headers, error sanitization
- Sensitive-data logging review
- Dependency and container scanning preparation
- Backup and recovery security requirements
- Threat model, abuse-case testing, security regression tests

### Governance model

Use the current shared authenticated steward workspace direction unless the
repository contains a newer approved decision. Do not reintroduce an unapproved
steward hierarchy or RBAC model merely because an older roadmap mentioned RBAC.
Source administration may still require a distinct privileged boundary.

### Explicit exclusions

- Treating the interim `/sources` API-key boundary as completed application
  security
- Ingesting operational LMOUs, arbitration collections, or private grievance
  data before exit criteria are met
- Production public deployment (W11)

### Dependencies

- Stable application surface from W6–W8 sufficient to protect real routes
- Decision on identity mechanism (password vs IdP) recorded before
  implementation freeze

### Principal risks

- Security theater (auth on some routes only)
- Premature sensitive-corpus ingestion
- Reintroducing unapproved role hierarchies
- Logging secrets or private case content

### Required validation

- Explicit authentication decision for every application route
- Explicit authorization decision for sensitive operations
- Case and source access tests
- Upload failure-path tests
- Audit-event coverage for important actions
- Threat model review and security regression tests

### Exit criteria

- All application routes have an explicit authentication decision
- Sensitive operations have an explicit authorization decision
- Case access is tested
- Source access is tested
- Audit events are recorded for important actions
- Uploads fail safely
- Secrets are not stored in source control
- Security tests exist
- Threat model is documented
- No known critical or high-severity security defects remain open before corpus
  expansion

### Deliverables

- Identity and session implementation
- Authorization and audit logging
- Threat model document
- Security test suite
- Secrets and configuration guidance suitable for later deployment

---

## W10 — LMOU and Arbitration Knowledge Expansion

### Goal

Expand the knowledge corpus after the application security boundary and quality
evaluation infrastructure are established.

### User or operational outcome

Stewards can retrieve and cite Local Memoranda of Understanding and historical
arbitration materials with correct jurisdiction, date, supersession, and
authority-role behavior.

### In-scope work

- Local Memoranda of Understanding
- Historical arbitration decisions
- Additional approved postal manuals or guidance
- Corpus, jurisdiction/locality, effective-date, supersession, decision,
  arbitrator (where appropriate), and citation metadata
- Source versioning and lifecycle
- Corpus-specific chunking and retrieval tests
- Authority-role rules and conflict/precedence handling
- Retention and deletion procedures
- Sensitive-data review
- Duplicate and near-duplicate detection

### LMOU requirements

- Preserve installation or jurisdiction scope
- Prevent application outside authorized scope
- Track effective dates and superseded versions
- Distinguish local agreement language from national agreement language

### Arbitration requirements

- Preserve case and decision provenance
- Separate holdings from factual summaries
- Preserve award dates and cited contract provisions
- Avoid treating outcomes as universally controlling
- Represent precedential weight accurately
- Support filters by craft, issue, jurisdiction, date, and authority type

### Explicit exclusions

- Starting this phase before W9 security exit criteria
- Treating arbitration as universally controlling authority
- Silent degradation of W7/W8 quality baselines

### Dependencies

- W9 security and governance complete
- W7 evaluation infrastructure available for corpus-specific golden sets
- W8 multi-agent behavior (if adopted) compatible with new authority roles

### Principal risks

- Scope leakage of LMOUs across jurisdictions
- Misrepresenting arbitration weight
- Sensitive data in corpus without review
- Quality regressions on existing corpora

### Required validation

- Corpus admission criteria documented and enforced
- Security review complete before ingestion
- LMOU scope filtering tests
- Arbitration citation and authority-role tests
- Corpus-specific golden evaluations
- Baseline comparison against W7/W8 results

### Exit criteria

- Corpus admission criteria are documented
- Security review is complete
- Metadata requirements are enforced
- Corpus-specific golden evaluations exist
- LMOU scope filtering is tested
- Arbitration citation and authority-role behavior are tested
- New corpora do not degrade existing W7 and W8 quality baselines
- Ingestion is reproducible and auditable

### Deliverables

- Ingestion procedures and metadata schema
- Indexed LMOU and arbitration corpora under governance
- Corpus-specific evaluations and regression records
- Retention/deletion and sensitive-data review artifacts

---

## W11 — Production Packaging and Deployment

### Goal

Package, deploy, operate, monitor, and recover the complete system in a
production-like environment.

### User or operational outcome

The system can be deployed reproducibly with health/readiness checks, managed
secrets, monitoring, tested backups, and documented rollback—without equating
Dockerization alone with production readiness.

### In-scope work

- Dockerfiles and multi-stage builds
- Docker Compose for supported local or staging operation
- Production image configuration
- PostgreSQL and pgvector deployment with persistent storage
- Migration execution strategy
- Application startup, health, and readiness checks
- Background-job strategy if required
- Reverse proxy or ingress and TLS termination
- Environment-specific configuration and managed secrets
- Logging, metrics, tracing where justified, error monitoring
- Backup automation, restore testing, disaster-recovery procedure
- CI/CD, image scanning, dependency scanning
- Database migration safeguards and rollback procedure
- Deployment runbook and operational documentation

### Explicit exclusions

- Treating containerization alone as production readiness
- Skipping backup restore testing
- Baking secrets into images
- Claiming production readiness before application behavior, quality, and
  security have been validated in earlier phases

### Dependencies

- W6 feature workflows validated
- W7 quality gates approved
- W8 multi-agent outcomes accepted (if multi-agent is retained)
- W9 security controls complete
- W10 corpus expansion complete or explicitly deferred with documented risk

### Principal risks

- “Dockerized therefore production-ready” claims
- Untested restores and rollbacks
- Secrets in images or source control
- Monitoring that misses retrieval or generation failures

### Required validation

- Reproducible image builds
- Non-root containers where practical
- Health and readiness checks
- Safe migrations and persistent data across restarts
- Tested backup restoration
- Production-like smoke tests
- Documented and tested rollback steps

### Exit criteria

- Images build reproducibly
- Containers run as non-root where practical
- Secrets are injected rather than baked into images
- Health and readiness checks work
- Migrations run safely
- Persistent data survives restarts
- Backup restoration has been tested
- Deployment is reproducible
- Monitoring surfaces application and retrieval failures
- Security configuration is preserved in deployment
- Production-like smoke tests pass
- Rollback steps are documented and tested

### Deliverables

- Production packaging artifacts
- Deployment and recovery runbooks
- Monitoring and alerting configuration
- CI/CD pipeline with scanning
- Smoke-test and rollback evidence

---

## Related documentation

- [`PROJECT_STATE.md`](../PROJECT_STATE.md) — concise current snapshot
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — system design
- [`saved_cases_ui_contract.md`](saved_cases_ui_contract.md) — saved-case UI/API contract
- [`README.md`](../README.md) — public-facing repository entry point
