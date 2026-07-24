# GrievanceHub W5 Retrieval Architecture Plan

**Status:** Temporary working plan for the Knowledge Foundation retrieval refactor  
**Workspace:** `C:\Users\tloll\Documents\GrievanceHub`  
**Active Git branch at planning:** `main`  
**Planning date:** 2026-07-23  
**Companion inspection:** `docs/temp/PROJECT_INSPECTION_W5.md`  
**Rule:** If inspection docs or prompt narratives conflict with current code, **current code wins**. Corrections are recorded in §1.1.

**This planning task makes no application code changes.** Only this document is created/replaced.

### Implementation divergence note (2026-07-23)

The completed implementation in `docs/temp/RETRIEVAL_AGENT_IMPLEMENTATION_REPORT.md` differs from this plan in the following material ways. Current code wins.

1. **Two retrieval agents, not three.** `ContractAgent` and `SupervisorManualAgent` are implemented under `RetrievalOrchestrator`. There is no separate `ArbitrationAgent` or `arbitration_agent.py`. `ARBITRATION` source types are retrieved by `ContractAgent` with evidence role `arbitral_persuasive_support`.
2. **ContractAgent is a bounded vector retriever, not a full extract of `search_all`.** Issue decomposition, multi-query expansion, empty-pool backfill, leave supplementation, and coverage-audit behavior remain in `KnowledgeRetrievalService.search_all`. The orchestrator is the new high-level path; `search_all` remains the compatibility facade for ask/report/chat.
3. **Supervisor Manual infrastructure now exists.** W5 completed three `SUPERVISOR_MANUAL` sources with 533 embeddings; `SupervisorManualAgent` is active, not an unavailable stub.
4. **Shared result contract is `RetrievalEvidence`, not a replacement of `relevance_utils.RetrievedChunk`.** Legacy callers continue to use `RetrievedChunk` via `search_all`; adapters bridge the agent path.
5. **Agent-specific candidate admission floor.** `RETRIEVAL_MIN_CANDIDATE_SIMILARITY = 0.45` admits mid-similarity neighbors for scoring; final acceptance still uses `MIN_COMBINED_RETRIEVAL_SCORE`. Existing `MIN_EMBEDDING_SIMILARITY` remains unchanged for the legacy provider path.

---

## Table of contents

1. [Current-state summary](#1-current-state-summary)
2. [W5 changes already completed](#2-w5-changes-already-completed)
3. [Goals](#3-goals)
4. [Non-goals](#4-non-goals)
5. [Exact three-agent architecture](#5-exact-three-agent-architecture)
6. [Source-to-agent mapping](#6-source-to-agent-mapping)
7. [Authority and evidence-role rules](#7-authority-and-evidence-role-rules)
8. [Responsibilities of each planned module](#8-responsibilities-of-each-planned-module)
9. [Proposed data models](#9-proposed-data-models)
10. [Proposed public method signatures](#10-proposed-public-method-signatures)
11. [SQLAlchemy session-safety strategy](#11-sqlalchemy-session-safety-strategy)
12. [Read-only security boundaries](#12-read-only-security-boundaries)
13. [KnowledgeRetrievalService compatibility strategy](#13-knowledgeretrievalservice-compatibility-strategy)
14. [Incremental migration stages](#14-incremental-migration-stages)
15. [File-by-file implementation checklist](#15-file-by-file-implementation-checklist)
16. [Existing files that must remain unchanged](#16-existing-files-that-must-remain-unchanged)
17. [Tests mapped to each migration stage](#17-tests-mapped-to-each-migration-stage)
18. [New tests required](#18-new-tests-required)
19. [Risk analysis](#19-risk-analysis)
20. [Rollback strategy for each stage](#20-rollback-strategy-for-each-stage)
21. [Recommended first implementation file](#21-recommended-first-implementation-file)
22. [Explicit exclusions](#22-explicit-exclusions)

---

## 1. Current-state summary

### 1.0 Runtime retrieval today

Indexed retrieval is DB + pgvector based. Query-time filesystem access is not used.

| Layer | Current role |
|--------|----------------|
| `SourceSyncService` / `SourceService` / upload | Set `SourceDocument.local_path` (+ hash) |
| `SourceProcessingService` | PDF → chunks → `text-embedding-3-small` → `SourceChunk.embedding` |
| Providers (`CONTRACT`, `ELM`, `CIM`, `LMOU`) | Cosine-distance search returning `(SourceChunk, distance)` |
| `LegalIssueAnalyzer` | Pre-retrieval issue decomposition + query expansion |
| `KnowledgeRetrievalService.search_all` | Full retrieval engine: issues → providers → score → gate → fallback → backfill → coverage audit → leave supplement → merge |
| `relevance_utils` | Shared `RetrievedChunk`, scoring, gates, backfill builders, merge, leave-direction logic |
| `AnalysisService` | Post-retrieval ask/report; enriches gaps/audit; does **not** call `search_all` |
| `source_manager` | Offline registry/download; **not** imported by KRS |

**Working providers (only):** `ContractProvider`, `CIMProvider`, `ELMProvider`, `LMOUProvider` registered on `KnowledgeRetrievalService.providers`.

**Public facade signature (must be preserved):**

```python
KnowledgeRetrievalService.search_all(
    db: Session,
    query: str,
    limit_per_source: int = 8,
    known_facts: list[str] | None = None,
)
```

**Exact public return keys (must be preserved):**

`query`, `known_facts`, `issue_analysis`, `decomposed_issues`, `expanded_queries`, `issue_keywords`, `keywords`, `article_mentions`, `limit_per_source`, `results_by_source`, `all_chunks`, `retrieved_chunks`, `issue_pools`, `merge_metadata`, `retrieval_gaps`, `indexed_source_types`, `source_coverage_audit`

**Critical type splits:**

- KRS `retrieval_gaps` = **list**
- Report-level `retrieval_gaps` = enriched **dict**
- KRS `source_coverage_audit` = raw list (`disposition`, …)
- Report-level audit = summarized (`final_disposition`, …)

Full behavioral detail is in `docs/temp/PROJECT_INSPECTION_W5.md`.

### 1.1 Corrections vs inspection / prompt narratives (code wins)

Inspection and the planning prompt describe some W5 ingestion/sync features that are **not present** in the current workspace application code. Recorded corrections:

| Claim | Current code reality |
|-------|----------------------|
| `SourceProcessingService` updates processing status, processed timestamp, processed SHA256, processing strategy, rolls back on failure, preserves rich chunk metadata beyond text/page/index/embedding | **Not present.** Current `process_source` deletes existing chunks, embeds paragraphs, inserts `SourceChunk(source_document_id, chunk_index, page_number, text, embedding)`, commits, returns `{message, source_id, pages, chunks_created}`. On exception it returns `{error, type}` and does **not** explicitly `rollback()`. |
| `SourceDocument` stores processing status / processed fields | **Not present** on `SourceDocument`. `processing_status` / `processed_at` exist on **`CaseDomainEvent`**, not source documents. |
| `source_manager` writes optional `version` into the offline manifest it manages | Current `update_source` writes name, source_type, official_page, download_url, final_url, local_path, sha256, content_type under key `source["id"]`. It does **not** write a `version` field. Canonical ID is preserved as the **manifest key** (`source["id"]`). |
| Committed `app/sources/manifest.json` already contains `version` | **True** for the checked-in app/sources manifest (ELM/CONTRACT/CIM entries). That file is parallel to `source_manager`'s `DATA_DIR/sources/manifest.json` writer. Do not restore an older format that drops `version` from `app/sources/manifest.json`. |
| `SourceSyncService` supports Supervisor Manual folder and resets processing status to pending on document change | **Not present.** Current `folder_map` keys: `CONTRACT`, `ELM`, `CIM`, `LMOU`, `ARBITRATION`, `STEP4`, `MOU`. No Supervisor Manual key. Sync sets `local_path`/`sha256` and commits; no processing-status reset. |
| Supervisor Manual source type string | Confirmed in tests/fixtures as **`SUPERVISOR_MANUAL`** (`tests/test_case_lifecycle_workspace_restoration.py`). Not yet in sync `folder_map` or providers. |
| Arbitration source type string | Confirmed as **`ARBITRATION`** in sync `folder_map` and tests. No arbitration provider yet. |
| Working retrieval already covers Supervisor Manual / Arbitration | **False.** Only CONTRACT/CIM/ELM/LMOU providers exist. Optional agents must be unavailable until indexed chunks + read-only search exist. |

**Implication for migration:** Do not assume SourceDocument processing-status fields or Supervisor Manual sync folders already exist when designing retrieval agents. Agent availability must check indexed embeddings / registered search capability, not invent infrastructure.

**Note on sync folders `STEP4` and `MOU`:** These strings exist today in `SourceSyncService.folder_map` for file sync only. They are **explicitly excluded** from the three-agent retrieval architecture (see §22). Do not create agents, enums, or retrieval plans for them.

---

## 2. W5 changes already completed

Preserve what exists in the current workspace. Do not undo.

### 2.A Ingestion (`SourceProcessingService`) — as currently implemented

Current responsibilities that must remain:

- Read a source PDF from `SourceDocument.local_path`
- Split into paragraph / max-char chunks (`split_text`, `MAX_CHARS=6000`)
- Create embeddings with `text-embedding-3-small`
- Store `SourceChunk` rows
- Replace prior chunks for the document on re-process (delete-then-insert)
- Return success/error payload to API callers

**Planned-but-not-yet-in-code ingestion enhancements** (status/timestamp/SHA/strategy/rollback) must **not** be invented by the retrieval refactor. If those land later in ingestion, retrieval stays read-only and does not own them.

### 2.B Official-source registry (`source_manager`)

Current behavior to preserve:

- Registry-driven download/update flow
- Manifest keyed by canonical source id (`source["id"]`)
- Manifest fields written by `update_source` as listed in §1.1
- Do not restore an older manifest format that drops identity or (for `app/sources/manifest.json`) existing `version` fields

### 2.C Sync (`SourceSyncService`)

Current behavior to preserve:

- Local folder preference then download_url fallback
- SHA256 calculation
- Existing folder_map entries including `ARBITRATION` (and, for sync only, `STEP4`/`MOU` which remain non-retrieval)

### 2.D Retrieval engine (`KnowledgeRetrievalService` + `relevance_utils`)

Already supports and **must be preserved behaviorally**:

- CONTRACT, CIM, ELM, LMOU
- Issue decomposition (`LegalIssueAnalyzer` + `collect_decomposed_issues`)
- Query expansion
- Embedding retrieval via providers
- Scoring (`score_chunk_for_issue` / `_score_chunk_match`)
- Retrieval gates (`passes_retrieval_gate`, actor/action direction)
- Global fallback
- Empty-pool backfill
- Missing-source-type backfill
- Source-coverage auditing (raw dispositions)
- Leave-revocation CONTRACT supplementation
- Per-issue pools
- Merge and deduplication (`merge_issue_retrieval_pools`)
- Retrieval metadata attachment on returned chunks
- Backward-compatible public return data

**Goal of this refactor:** reorganize into orchestrator + agents **without replacing** this retrieval algorithm.

---

## 3. Goals

1. Introduce exactly **three** retrieval agents under `RetrievalOrchestrator`:
   - `ContractAgent`
   - `SupervisorManualAgent`
   - `ArbitrationAgent`
2. Keep `KnowledgeRetrievalService` as the backward-compatible public facade.
3. Extract/delegate current KRS pipeline into `ContractAgent` with behavioral parity.
4. Model optional agents as explicitly unavailable until infrastructure exists; never fabricate evidence or fake “searched” audits.
5. Keep a single shared scoring/gate/backfill/merge implementation in `relevance_utils` (no per-agent copies).
6. Enforce read-only retrieval boundaries (no DB writes, no ingest/sync/download).
7. Design interfaces compatible with future parallel agent execution while using safe sequential Session use now.
8. Migrate incrementally with rollback points and parity tests.
9. Preserve exact `search_all` return keys and helper-method compatibility via forwarding during initial migration.

---

## 4. Non-goals

1. No new final-reasoning / legal-conclusion agents in this refactor.
2. No changes to `retrieval_config` thresholds, scoring weights, embedding model/dimensions.
3. No rewriting of `relevance_utils` algorithms.
4. No big-bang rewrite of `search_all` behavior.
5. No unsafe concurrent sharing of one SQLAlchemy `Session`.
6. No fabricated Supervisor Manual or Arbitration passages.
7. No Step 4 retrieval agent or National MOU retrieval agent (see §22).
8. No separate Contract / CIM / ELM / LMOU agents.
9. No moving ELM under SupervisorManualAgent.
10. No application code changes during **this planning task**.
11. No git branches, worktrees, commits, pushes, merges, or resets unless explicitly instructed later.
12. No replacing `relevance_utils.RetrievedChunk` without an explicit compatibility adapter design.

---

## 5. Exact three-agent architecture

```text
RetrievalOrchestrator
├── ContractAgent
├── SupervisorManualAgent
└── ArbitrationAgent
```

**Target package:**

```text
app/services/retrieval/
├── __init__.py
├── models.py
├── base_agent.py
├── contract_agent.py
├── supervisor_manual_agent.py
├── arbitration_agent.py
└── orchestrator.py
```

**Exactly three retrieval agents. Do not add any other retrieval agent.**

Future reasoning flow (retrieval portion only implemented now):

```text
Steward facts
    ↓
Issue analysis
    ↓
RetrievalOrchestrator
    ├── ContractAgent
    ├── SupervisorManualAgent
    └── ArbitrationAgent
    ↓
Evidence validation and authority resolution   ← out of scope for this refactor
    ↓
Final grievance/legal analysis                 ← out of scope
    ↓
Case strategy and response generation          ← out of scope
```

Agents retrieve and organize evidence. They do **not** independently conclude sustain/deny.

---

## 6. Source-to-agent mapping

| Source type string (current code) | Agent | Retrieval status now |
|-----------------------------------|-------|----------------------|
| `CONTRACT` | **ContractAgent** | Active (provider exists) |
| `CIM` | **ContractAgent** | Active |
| `ELM` | **ContractAgent** | Active — **not** SupervisorManualAgent |
| `LMOU` | **ContractAgent** | Active |
| `SUPERVISOR_MANUAL` | **SupervisorManualAgent** | Unavailable until indexed + search impl |
| `ARBITRATION` | **ArbitrationAgent** | Unavailable until indexed + search impl |
| `STEP4` | *(none — excluded)* | Sync folder only; not a retrieval agent |
| `MOU` | *(none — excluded)* | Sync folder only; not a retrieval agent |

**Contract-domain ownership (single agent):**

- National Agreement / `CONTRACT` — governing CBA
- `CIM` — interpretation of the National Agreement; not a competing separate authority domain
- `ELM` — USPS employment/labor rules used in grievance analysis; stays in ContractAgent
- `LMOU` — local contractual provisions; stays in ContractAgent

---

## 7. Authority and evidence-role rules

### 7.1 ContractAgent evidence role

- Returns contractual / interpretive / related rule evidence and findings organized by issue.
- Answers: what rights/obligations apply; controlling National Agreement language; CIM explanation; related ELM; applicable LMOU.
- Does **not** independently produce final sustain/deny conclusions.

Proposed evidence-role labels (metadata only; do not change scoring semantics):

- `contract_controlling` — National Agreement language
- `contract_interpretation` — CIM explaining/applying NA language
- `employment_labor_rule` — ELM provisions
- `local_contract_provision` — LMOU

### 7.2 SupervisorManualAgent evidence role

- Owns only Supervisor Manuals and directly related supervisory guidance supported by the project.
- Separate from ELM.
- Does **not** create contractual rights.
- Compares steward facts against expected supervisory conduct, procedure, investigation, management responsibility.
- Must **not** present Supervisor Manual language as controlling National Agreement language.

Proposed evidence-role label:

- `supervisory_guidance` (non-controlling; conduct/procedure comparison)

### 7.3 ArbitrationAgent evidence role

- Owns only arbitration decisions.
- Persuasive support only.
- May strengthen/weaken arguments, provide analogy, similar facts, arbitral reasoning.
- Must **not** create rights, override National Agreement / controlling contract language, be treated as automatic binding precedent, or independently determine sustain.

Proposed evidence-role labels:

- `arbitral_persuasive_support`
- `arbitral_persuasive_contrary`
- `arbitral_analogous_reasoning`

Metadata should record persuasive role explicitly.

### 7.4 Cross-domain final analysis (future, not this refactor)

Final analysis layer will eventually weigh contract violation, supervisory procedure compliance, arbitral persuasiveness, case strength, remedy. **Do not implement** that layer here.

---

## 8. Responsibilities of each planned module

### 8.1 `app/services/retrieval/__init__.py`

- Export stable public types/symbols for the package as needed.
- Avoid importing heavy side effects.
- May re-export orchestrator / request models for convenience once stable.

### 8.2 `app/services/retrieval/models.py`

- Strongly typed request/context, agent identity/domain, execution status, agent output, orchestration output, evidence-role metadata.
- Adapters to/from existing `RetrievedChunk` and KRS dict shapes.
- No retrieval algorithms.

### 8.3 `app/services/retrieval/base_agent.py`

- Abstract read-only `BaseRetrievalAgent`.
- Standardize: name, domain, supported source types, availability check, timing/logging hooks, error isolation, `retrieve` entry point.
- **No** source-specific search logic.

### 8.4 `app/services/retrieval/contract_agent.py`

- Own CONTRACT/CIM/ELM/LMOU.
- Host or delegate the current KRS pipeline without behavior change.
- Produce agent output sufficient for KRS facade to rebuild exact public return.

### 8.5 `app/services/retrieval/supervisor_manual_agent.py`

- Interface-complete; retrieve only when `SUPERVISOR_MANUAL` is indexed and a read-only search path exists.
- Otherwise return explicit status: `unavailable` / `unregistered` / `not_indexed`.
- No fake evidence; no fake “searched” audit implying a run.

### 8.6 `app/services/retrieval/arbitration_agent.py`

- Same pattern for `ARBITRATION`.
- Attach persuasive-role metadata when real retrieval exists.

### 8.7 `app/services/retrieval/orchestrator.py`

- Coordinate exactly the three agents.
- Accept standardized request/context.
- Determine which agents are available.
- Execute applicable agents (sequential with one Session initially).
- Collect outputs; preserve source type, domain, matched issue IDs.
- Deduplicate evidence; preserve deterministic ordering.
- Record agent execution status; tolerate optional-agent failure.
- Return standardized orchestration result for KRS mapping.
- **Must not** contain source-specific retrieval algorithms.

### 8.8 `KnowledgeRetrievalService` (facade — later stage)

- Remains import path for the app.
- Builds retrieval request; calls orchestrator; maps to exact `search_all` return.
- Forwards helpers used by tests/scripts.
- Keeps `providers` list compatible where callers/tests depend on ordering.

### 8.9 Unchanged shared engines (not moved into agents as copies)

- `relevance_utils.py` — scoring, gates, merge, backfill builders, leave logic
- `retrieval_config.py` — thresholds/weights
- `embedding_service.py` — query embeddings
- Existing providers under `app/services/providers/` — ContractAgent uses them initially

---

## 9. Proposed data models

Location: `app/services/retrieval/models.py`

Prefer dataclasses or TypedDicts consistent with the codebase. Do **not** replace `relevance_utils.RetrievedChunk` in Stage 1; wrap/adapt.

### 9.1 Enums / literals

```python
AgentDomain = Literal["contract", "supervisor_manual", "arbitration"]

AgentName = Literal[
    "ContractAgent",
    "SupervisorManualAgent",
    "ArbitrationAgent",
]

AgentExecutionStatus = Literal[
    "completed",
    "unavailable",
    "unregistered",
    "not_indexed",
    "skipped",
    "error",
]

EvidenceRole = Literal[
    "contract_controlling",
    "contract_interpretation",
    "employment_labor_rule",
    "local_contract_provision",
    "supervisory_guidance",
    "arbitral_persuasive_support",
    "arbitral_persuasive_contrary",
    "arbitral_analogous_reasoning",
]
```

Do **not** add Step4 / NationalMOU domains or agent names.

### 9.2 `RetrievalRequest`

```python
@dataclass(frozen=True)
class RetrievalRequest:
    query: str
    limit_per_source: int = 8
    known_facts: tuple[str, ...] = ()
    # Optional precomputed analysis if facade already ran analyzer (future);
    # initial ContractAgent path may still call LegalIssueAnalyzer internally
    # to preserve exact current behavior.
```

### 9.3 `RetrievalContext`

Runtime context passed into agents (not frozen if it carries session):

```python
@dataclass
class RetrievalContext:
    db: Session  # read-only usage contract; see §11–§12
    request: RetrievalRequest
    indexed_source_types: frozenset[str]
    # Optional shared analysis fields when orchestrator lifts analyzer later
    issue_analysis: dict | None = None
    decomposed_issues: list[dict] | None = None
    expanded_queries: list[str] | None = None
    issue_keywords: list[str] | None = None
    dispute_frame: dict | None = None
```

### 9.4 `AgentIdentity`

```python
@dataclass(frozen=True)
class AgentIdentity:
    name: AgentName
    domain: AgentDomain
    supported_source_types: frozenset[str]
```

### 9.5 `AgentRunRecord`

```python
@dataclass
class AgentRunRecord:
    identity: AgentIdentity
    status: AgentExecutionStatus
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: float | None = None
    error_type: str | None = None
    error_message: str | None = None
    detail: str | None = None  # e.g. "no SUPERVISOR_MANUAL embeddings"
```

### 9.6 `AgentRetrievalOutput`

```python
@dataclass
class AgentRetrievalOutput:
    identity: AgentIdentity
    run: AgentRunRecord
    # ContractAgent populates KRS-compatible structures for facade mapping:
    issue_analysis: dict | None = None
    decomposed_issues: list[dict] | None = None
    expanded_queries: list[str] | None = None
    issue_keywords: list[str] | None = None
    keywords: list[str] | None = None
    article_mentions: list[str] | None = None
    retrieved_chunks: list[RetrievedChunk] = field(default_factory=list)
    issue_pools: dict[str, list[RetrievedChunk]] = field(default_factory=dict)
    merge_metadata: dict | None = None
    retrieval_gaps: list[dict] = field(default_factory=list)  # KRS list shape
    indexed_source_types_considered: list[str] = field(default_factory=list)
    source_coverage_audit: list[dict] = field(default_factory=list)  # raw
    results_by_source: dict[str, list[dict]] = field(default_factory=dict)
    evidence_roles_by_chunk_key: dict[tuple, EvidenceRole] = field(default_factory=dict)
```

For unavailable optional agents: empty evidence lists + non-`completed` status; **no** fabricated audit rows claiming a search ran.

### 9.7 `OrchestrationResult`

```python
@dataclass
class OrchestrationResult:
    request: RetrievalRequest
    agent_outputs: list[AgentRetrievalOutput]
    agent_runs: list[AgentRunRecord]
    # Aggregated views for facade (initially dominated by ContractAgent):
    primary_contract_output: AgentRetrievalOutput | None
    combined_retrieved_chunks: list[RetrievedChunk]
    combined_issue_pools: dict[str, list[RetrievedChunk]]
    combined_merge_metadata: dict
    combined_retrieval_gaps: list[dict]
    combined_source_coverage_audit: list[dict]
    combined_indexed_source_types: list[str]
    combined_results_by_source: dict[str, list[dict]]
```

### 9.8 Compatibility adapter notes

- Keep using `relevance_utils.RetrievedChunk` inside agent outputs.
- Chunk identity remains `(source_document_id, page_number, chunk_index)`.
- Facade maps `OrchestrationResult` → exact `search_all` dict keys.
- Until Supervisor/Arbitration contribute chunks, combined views == ContractAgent views (parity).

---

## 10. Proposed public method signatures

### 10.1 Facade (unchanged public API)

```python
class KnowledgeRetrievalService:
    providers = [...]  # preserve ordering CONTRACT, ELM, CIM, LMOU

    @staticmethod
    def search_all(
        db: Session,
        query: str,
        limit_per_source: int = 8,
        known_facts: list[str] | None = None,
    ) -> dict: ...

    # Compatibility forwarders (initial migration preference):
    @staticmethod
    def _get_indexed_source_types(db: Session) -> set[str]: ...
    @staticmethod
    def extract_keywords(query: str) -> list[str]: ...
    @staticmethod
    def extract_article_mentions(query: str) -> list[str]: ...
    @staticmethod
    def _chunk_key(chunk) -> tuple: ...
    @staticmethod
    def _score_chunk_match(...) -> float: ...
    @staticmethod
    def _retrieve_queries_into_pool(...) -> dict: ...
    @staticmethod
    def _append_passing_chunks_to_pool(...) -> None: ...
    @staticmethod
    def _backfill_empty_issue_pools(...) -> None: ...
    @staticmethod
    def _backfill_missing_source_types(...) -> list[dict]: ...
    @staticmethod
    def _supplement_contract_leave_commitment_pool(...) -> None: ...
    @staticmethod
    def _pool_has_contract_leave_commitment(...) -> bool: ...
```

Forwarders may delegate to `ContractAgent` / shared helpers once extracted; signatures and behavior must match.

### 10.2 Base agent

```python
class BaseRetrievalAgent(ABC):
    identity: AgentIdentity

    def is_available(self, context: RetrievalContext) -> AgentExecutionStatus:
        """Return completed-eligible status or unavailable/unregistered/not_indexed."""

    def retrieve(self, context: RetrievalContext) -> AgentRetrievalOutput:
        """Read-only retrieval entry; isolates errors into AgentRunRecord."""
```

### 10.3 ContractAgent

```python
class ContractAgent(BaseRetrievalAgent):
    identity = AgentIdentity(
        name="ContractAgent",
        domain="contract",
        supported_source_types=frozenset({"CONTRACT", "CIM", "ELM", "LMOU"}),
    )

    def retrieve(self, context: RetrievalContext) -> AgentRetrievalOutput:
        """Behavioral parity with current KnowledgeRetrievalService.search_all core."""
```

### 10.4 SupervisorManualAgent / ArbitrationAgent

```python
class SupervisorManualAgent(BaseRetrievalAgent):
    identity = AgentIdentity(
        name="SupervisorManualAgent",
        domain="supervisor_manual",
        supported_source_types=frozenset({"SUPERVISOR_MANUAL"}),
    )

class ArbitrationAgent(BaseRetrievalAgent):
    identity = AgentIdentity(
        name="ArbitrationAgent",
        domain="arbitration",
        supported_source_types=frozenset({"ARBITRATION"}),
    )
```

Initial `retrieve`: if not available → status + empty evidence (no fake audits).

### 10.5 Orchestrator

```python
class RetrievalOrchestrator:
    def __init__(self, agents: list[BaseRetrievalAgent] | None = None): ...

    def retrieve(self, context: RetrievalContext) -> OrchestrationResult:
        """
        Sequential execution with the provided Session (safe default).
        Interfaces allow future parallelism only with session-per-worker.
        """
```

### 10.6 Provider contract (unchanged)

```python
def search(self, db: Session, query_embedding, limit=5) -> list[tuple]:
    """(SourceChunk, cosine_distance) ascending distance."""
```

---

## 11. SQLAlchemy session-safety strategy

1. Current system uses a **synchronous SQLAlchemy `Session`** per request.
2. **Do not** run multiple agents concurrently on the same Session.
3. Initial orchestrator execution: **strictly sequential** on `context.db`.
4. Design `RetrievalOrchestrator.retrieve` and agent interfaces so future parallelism can pass **separate sessions per worker** when/if the codebase provides a safe factory.
5. Document on orchestrator and base agent: “Session is not thread-safe; sequential use required unless caller supplies isolated sessions.”
6. Agents must not call `db.commit()`, `db.rollback()`, or mutate ORM state that implies persistence (in-memory `chunk.retrieval_metadata` assignment is allowed as today).
7. Tests must assert no commits/writes during retrieval (see §18).

---

## 12. Read-only security boundaries

### Retrieval agents may

- Query `SourceDocument` / `SourceChunk`
- Perform embedding searches via providers / equivalent read-only search
- Score evidence via shared `relevance_utils`
- Attach in-memory retrieval metadata
- Call `EmbeddingService.create_embedding` for query vectors (read-path embedding of the question — not writing chunk embeddings)

### Retrieval agents must not

- Modify `SourceDocument` rows
- Create/delete `SourceChunk` rows
- Process PDFs
- Download sources
- Synchronize files
- Update manifests
- Write embeddings to DB
- Commit database transactions

### Layer separation (least privilege)

| Layer | Owner modules | Privilege |
|-------|---------------|-----------|
| Discovery/download | `source_manager`, download scripts | Write files/manifests |
| Synchronization | `SourceSyncService`, `SourceService` | Update document paths/hashes |
| Processing/embedding | `SourceProcessingService` | Write chunks/embeddings |
| Retrieval | `app/services/retrieval/*`, KRS facade | Read-only DB + in-memory metadata |
| Evidence validation / ranking | `AnalysisService`, `AuthorityRanker`, etc. | Post-retrieval (unchanged here) |
| Legal reasoning / response | analysis/narrative/case services | Out of retrieval scope |

Explicit interfaces only between layers; no sneaking ingest into agents.

---

## 13. KnowledgeRetrievalService compatibility strategy

### 13.1 Facade role

1. Accept existing `search_all` parameters.
2. Build `RetrievalRequest` / `RetrievalContext` (compute `indexed_source_types` via existing helper).
3. Call `RetrievalOrchestrator.retrieve`.
4. Map `OrchestrationResult` → exact public dict keys and types.
5. Ensure `all_chunks` objects receive `retrieval_metadata` as today.
6. Preserve `results_by_source` keys/order from provider list (CONTRACT, ELM, CIM, LMOU).
7. Preserve list-shaped `retrieval_gaps` and raw `source_coverage_audit`.

### 13.2 Helper forwarding

Prefer keeping KRS static methods as thin forwarders to extracted ContractAgent/shared functions until all callers/tests migrate.

Known dependents:

- Unit tests: `_score_chunk_match`, `_append_passing_chunks_to_pool`, `_backfill_empty_issue_pools`, etc.
- Chat: `_get_indexed_source_types`
- Scripts: full `search_all` keys including `issue_pools`, `retrieved_chunks`, `merge_metadata`

### 13.3 Parity gate

Do not remove inline KRS behavior until ContractAgent parity tests pass for the same DB/query/known_facts/config.

### 13.4 Optional agents and public output

Until Supervisor/Arbitration are indexed:

- Orchestrator still “coordinates” three agents, but optional ones return unavailable.
- Public `search_all` output remains ContractAgent-equivalent (current behavior).
- Do not add empty audit rows for unavailable agents that imply they searched.

### 13.5 `results_by_source` future extension

When optional agents become active, extend `results_by_source` carefully:

- Existing CONTRACT/ELM/CIM/LMOU keys must remain.
- New keys (`SUPERVISOR_MANUAL`, `ARBITRATION`) only when real retrieval occurs and callers are ready.
- Initial migration: do not change key set until parity suite green and a deliberate compatibility decision is made.

---

## 14. Incremental migration stages

### Stage 1 — Shared models

**Create:** `app/services/retrieval/__init__.py`, `app/services/retrieval/models.py`  
**Behavior change:** none  
**Rollback:** delete package files

### Stage 2 — Base agent

**Create:** `app/services/retrieval/base_agent.py`  
**Behavior change:** none  
**Rollback:** delete file; models remain harmless

### Stage 3 — ContractAgent

**Create:** `app/services/retrieval/contract_agent.py`  
**Action:** extract/delegate current KRS pipeline without algorithm change  
**Preserve:** LegalIssueAnalyzer, expanded queries, per-issue retrieval, scoring, gates, global fallback, empty-pool backfill, missing-source-type backfill, leave supplement, merge, gaps, indexed types, coverage audit, public data for facade  
**KRS:** may still contain original code; ContractAgent can initially wrap/call shared extracted functions or duplicate-call path behind a flag — prefer extract-once used by both until facade cutover  
**Rollback:** stop calling ContractAgent; keep KRS original path

### Stage 4 — Orchestrator

**Create:** `app/services/retrieval/orchestrator.py`  
**Initially:** run ContractAgent as active implementation; register Supervisor/Arbitration only when valid/available (or register stubs that always return unavailable)  
**Rollback:** facade continues calling KRS internals / ContractAgent directly

### Stage 5 — SupervisorManualAgent

**Create:** `app/services/retrieval/supervisor_manual_agent.py`  
**If infra incomplete:** unavailable statuses only  
**Do not** fabricate retrieval  
**Rollback:** unregister agent / force unavailable

### Stage 6 — ArbitrationAgent

**Create:** `app/services/retrieval/arbitration_agent.py`  
Same rules as Stage 5 for `ARBITRATION`

### Stage 7 — KRS compatibility facade

**Refactor:** `app/services/knowledge_retrieval_service.py`  
Wire: request → orchestrator → map exact return  
Keep forwarders  
**Remove** duplicated engine body only after equivalence tests pass  
**Rollback:** restore previous KRS body from git on `main` (no force ops unless instructed)

**Order note:** Stages 5–6 may land as unavailable stubs before Stage 7, or after ContractAgent parity — either is fine if orchestrator tolerates unavailable agents. Preferred: stubs in place before facade cutover so orchestrator always sees three agents.

---

## 15. File-by-file implementation checklist

### New files

| File | Stage | Checklist |
|------|-------|-----------|
| `app/services/retrieval/__init__.py` | 1 | Package init; minimal exports |
| `app/services/retrieval/models.py` | 1 | Request/context/identity/status/outputs/orchestration models; evidence roles; no Step4/MOU |
| `app/services/retrieval/base_agent.py` | 2 | Abstract interface; availability; timing; error isolation; read-only docs |
| `app/services/retrieval/contract_agent.py` | 3 | Owns four source types; delegates current pipeline; parity |
| `app/services/retrieval/orchestrator.py` | 4 | Sequential coordination; status collection; dedupe/order hooks; session safety docs |
| `app/services/retrieval/supervisor_manual_agent.py` | 5 | Interface + unavailable until ready; evidence-role metadata when active |
| `app/services/retrieval/arbitration_agent.py` | 6 | Interface + unavailable until ready; persuasive-role metadata when active |

### Modified later (not in planning task)

| File | Stage | Checklist |
|------|-------|-----------|
| `app/services/knowledge_retrieval_service.py` | 3–7 | Extract helpers → ContractAgent; then facade to orchestrator; keep public API + forwarders |
| Tests under `tests/` | 1–7 | Existing green + new architecture tests |

### Explicitly not modified for retrieval algorithm

See §16.

### Future infra (out of retrieval algorithm scope; blockers for optional agents)

When enabling SupervisorManualAgent / ArbitrationAgent for real retrieval (separate work):

- Confirm source_type strings: `SUPERVISOR_MANUAL`, `ARBITRATION`
- Sync folders / seed documents / process embeddings
- Read-only provider or equivalent search
- Do **not** add Step4/National MOU retrieval

---

## 16. Existing files that must remain unchanged

**Unchanged in algorithm/behavior during this refactor** (may be imported, not rewritten):

| File | Why |
|------|-----|
| `app/services/relevance_utils.py` | Single shared scoring/gate/backfill/merge/leave implementation |
| `app/retrieval_config.py` | Thresholds and weights |
| `app/services/embedding_service.py` | `text-embedding-3-small` / 1536-d consistency |
| `app/services/providers/*.py` | Cosine-distance contract; used by ContractAgent |
| `app/services/legal_issue_analyzer.py` | Issue decomposition / expansion semantics |
| `app/services/analysis_service.py` | Post-retrieval; list-vs-dict gap/audit contracts |
| `app/services/source_processing_service.py` | Ingestion writes stay outside retrieval |
| `app/services/source_sync_service.py` | Sync writes stay outside retrieval |
| `app/services/source_manager.py` | Offline download/manifest outside retrieval |
| `app/database/models.py` | Schema not altered by retrieval package introduction |

**Preserve without behavior change (facade may thin later):**

- Public `search_all` contract and helper method availability via forwarding

**Do not copy into each agent:**

- `RetrievedChunk`, `build_issue_type_backfill_queries`, `build_queries_for_issue`, `build_source_type_backfill_queries`, `collect_decomposed_issues`, `extract_issue_keywords`, `extract_issue_keywords_for_issue`, `is_boilerplate_chunk`, `merge_issue_retrieval_pools`, `passes_retrieval_gate`, leave-direction helpers, `score_chunk_for_issue`, actor/action direction logic

**Do not change:**

- Embedding model/dimensions
- Provider cosine-distance contract
- SourceChunk identity key
- Source-coverage audit dispositions
- Merge caps / issue decomposition / query expansion / fallback queries / retrieval metadata semantics

---

## 17. Tests mapped to each migration stage

From `docs/temp/PROJECT_INSPECTION_W5.md` and current test inventory.

### Stage 1–2 (models / base — no behavior change)

- Smoke import tests for new package (new)
- Existing suite should remain fully green with no production path changes

### Stage 3 (ContractAgent extraction)

Must remain green:

| Test file | Focus |
|-----------|--------|
| `tests/test_knowledge_retrieval_scoring.py` | `_score_chunk_match` / combine score |
| `tests/test_relevance_utils.py` | overlap, boilerplate, combine, quote verify |
| `tests/test_relevance_phase0.py` | gates, merge metadata, `_append_passing_chunks_to_pool`, `_backfill_empty_issue_pools` |
| `tests/test_phase1_1_retrieval_stability.py` | direction/gates, backfill helpers, stability |
| `tests/test_phase1_1_source_coverage.py` | source-type backfill queries; audit summarization |
| `tests/test_retrieval_gaps.py` | AnalysisService gap enrichment from KRS list |
| `tests/test_phase0_1_iteration_a.py` | KRS-shaped gaps into `_build_retrieval_gaps` |

### Stage 4–7 (orchestrator + facade)

| Test file | Focus |
|-----------|--------|
| `tests/test_chat_source_retrieval.py` | mocks `search_all` keys `all_chunks`, `indexed_source_types` |
| `tests/test_case_service.py` | report preview audit persistence; KRS list gaps in mocks |
| `tests/test_case_api.py` | export must not call retrieval |
| `tests/test_report_export_presentation.py` | coverage caveat formatting |
| `tests/test_authority_ranker_filters.py` | post-retrieval ranking |
| `tests/test_narrative_generator.py` | narrative consumers |
| `tests/test_follow_up_chat.py` | chat continuity / retrieval status |
| `tests/test_regression_harness.py` | live report path when enabled |

### Diagnostics (practical, not always CI)

- `scripts/diagnose_regression.py`
- `scripts/phase1_1_verification.py`
- `scripts/phase1_1_source_coverage_diagnostic.py`

Expect same keys: `issue_pools`, `retrieved_chunks`, `merge_metadata`, `retrieval_gaps`, `source_coverage_audit`, etc.

### Leave-direction / coverage / stability

Covered primarily by `test_relevance_phase0.py`, `test_phase1_1_retrieval_stability.py`, `test_phase1_1_source_coverage.py`, and leave helpers in `relevance_utils` tests.

---

## 18. New tests required

| New test theme | Requirement |
|----------------|-------------|
| BaseRetrievalAgent error isolation | Agent exception → `status=error`, other agents still run |
| Agent availability | Unavailable/unregistered/not_indexed without raising |
| Agent source-type ownership | ContractAgent only four types; Supervisor only `SUPERVISOR_MANUAL`; Arbitration only `ARBITRATION` |
| ContractAgent parity | Same DB/query/known_facts/config → KRS-compatible outputs closely enough that existing tests/scripts/report generation continue working |
| Orchestrator deduplication | Cross-agent duplicate chunk keys merged correctly when optional agents active; no double-count when only ContractAgent |
| Orchestrator deterministic ordering | Stable ordering for equal scores / agent run order |
| Optional-agent failure isolation | Supervisor/Arbitration error does not empty ContractAgent results |
| No DB writes during retrieval | No `SourceChunk` insert/delete; no `SourceDocument` field persistence; no commit |
| No unsafe concurrent Session use | Sequential execution asserted; document/guard against shared-session parallel |
| Exact `search_all` return-key compatibility | Key set and critical types (list gaps, raw audit) |
| Supervisor Manual evidence-role metadata | When active, role is `supervisory_guidance` and not presented as controlling contract |
| Arbitration persuasive-role metadata | When active, persuasive labels present; not controlling |

**Most important migration test:** ContractAgent behavioral parity with current `KnowledgeRetrievalService` retrieval output.

---

## 19. Risk analysis

| Risk | Impact | Mitigation |
|------|--------|------------|
| Behavioral drift during extract | Report/chat regressions | Parity tests; keep dual path until green; forwarders |
| Copying scoring into agents | Divergent gates/scores | Forbid copies; import `relevance_utils` only |
| Unsafe parallel Session use | Subtle DB corruption / errors | Sequential default; explicit session-per-worker only later |
| Fake optional-agent audits | Misleading coverage | Unavailable statuses; no fabricated searched rows |
| Changing return key types | Caller/test breakage | Freeze key set; list-vs-dict documentation |
| Accidental inclusion of Step4/MOU | Architecture violation | Explicit exclusions; code review checklist |
| Moving ELM to Supervisor agent | Wrong authority model | Mapping table + ownership tests |
| Replacing RetrievedChunk early | Wide breakage | Adapter-only until deliberate migration |
| Ingest fields assumed present | Failed designs | §1.1 corrections; availability based on embeddings |
| Big-bang facade cutover | Hard rollback | Stage gates; keep old body until parity |

---

## 20. Rollback strategy for each stage

| Stage | Rollback |
|-------|----------|
| 1 Models | Delete `app/services/retrieval/` new files; no runtime dependency yet |
| 2 Base agent | Delete `base_agent.py`; models unused |
| 3 ContractAgent | Keep KRS original implementation as sole path; delete or stop importing ContractAgent |
| 4 Orchestrator | Facade/KRS call ContractAgent or original KRS directly |
| 5 SupervisorManualAgent | Force unavailable / unregister; no public output change |
| 6 ArbitrationAgent | Same as Stage 5 |
| 7 KRS facade | Restore previous `knowledge_retrieval_service.py` from git history on `main`; keep retrieval package inert or unused |

General rules:

- Work only on `main` when implementing (per project instruction at implementation time).
- Do not force-push, reset, or create branches/worktrees unless explicitly instructed.
- Prefer feature flags / dual-path switches inside KRS over irreversible deletes until parity passes.

---

## 21. Recommended first implementation file

**`app/services/retrieval/models.py`**

(with `app/services/retrieval/__init__.py` created in the same Stage 1 change)

**Rationale:**

- Zero retrieval behavior change
- Establishes typed contracts for all later stages
- Encodes three-agent domains and evidence roles without touching KRS
- Safe rollback
- Unblocks `base_agent.py` cleanly

---

## 22. Explicit exclusions

This architecture plan and all subsequent retrieval implementation must exclude:

- **No Step 4 source** (as a retrieval architecture source)
- **No Step 4 agent**
- **No National MOU source** (as a retrieval architecture source)
- **No National MOU agent**
- **No separate CIM agent**
- **No separate ELM agent**
- **No separate LMOU agent**
- **ELM does not belong to SupervisorManualAgent**
- **Supervisor Manuals do not establish contractual rights**
- **Arbitration is persuasive, not controlling**
- **No application code changes during this planning task**
- **No branches or worktrees** for this planning task

Additional clarifications:

- Sync folder keys `STEP4` and `MOU` may continue to exist for file sync only; they are not retrieval agents or planned retrieval sources in this architecture.
- Do not add placeholders, enums, future-work sections, comments, or models that introduce Step 4 or National MOU retrieval agents.

---

## Appendix A — Intended steward → retrieval → analysis flow

```text
Steward facts
    ↓
Issue analysis (LegalIssueAnalyzer — preserved)
    ↓
RetrievalOrchestrator
    ├── ContractAgent      (CONTRACT, CIM, ELM, LMOU)  [active first]
    ├── SupervisorManualAgent (SUPERVISOR_MANUAL)      [unavailable until indexed]
    └── ArbitrationAgent     (ARBITRATION)             [unavailable until indexed]
    ↓
Evidence validation and authority resolution   (future / existing post-retrieval)
    ↓
Final grievance/legal analysis                 (future; not this refactor)
    ↓
Case strategy and response generation          (existing case/chat/report paths)
```

---

## Appendix B — Public `search_all` return contract (freeze)

```python
{
  "query": str,
  "known_facts": list,
  "issue_analysis": dict,
  "decomposed_issues": list[dict],
  "expanded_queries": list[str],
  "issue_keywords": list[str],
  "keywords": list[str],
  "article_mentions": list[str],
  "limit_per_source": int,
  "results_by_source": dict[str, list[dict]],
  "all_chunks": list[SourceChunk],          # retrieval_metadata attached
  "retrieved_chunks": list[RetrievedChunk],
  "issue_pools": dict[str, list[RetrievedChunk]],
  "merge_metadata": {"per_issue_counts": dict, "total_merged": int},
  "retrieval_gaps": list[dict],             # NOT report dict
  "indexed_source_types": list[str],
  "source_coverage_audit": list[dict],      # raw dispositions
}
```

---

## Appendix C — Availability policy for optional agents

An optional agent must return one of:

- `unregistered` — not wired into orchestrator
- `unavailable` — wired but search implementation missing
- `not_indexed` — type known but no embedded chunks
- `skipped` — deliberately not run for this request
- `error` — exception isolated
- `completed` — real retrieval ran

**Never:**

- Generate fake evidence
- Report unsupported sources as searched
- Return fabricated empty audit records implying an unavailable provider ran

Valid ContractAgent results must still be returned when optional agents are not completed.

---

## Appendix D — End of plan

This document is the temporary working architecture plan for the W5 retrieval refactor.  
Planning produced **no application code changes**.  
Next implementation step: Stage 1 — create `app/services/retrieval/models.py` (and `__init__.py`) on `main` when explicitly instructed.
