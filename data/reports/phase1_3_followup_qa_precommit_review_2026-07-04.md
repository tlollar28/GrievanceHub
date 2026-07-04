# Phase 1.3 Pre-Commit Review — Follow-Up Q&A Grounded in Saved Cases/Reports

**Prepared:** 2026-07-04  
**Reviewer:** AI agent (read-only review; no code modified)  
**Branch reviewed:** `phase1-3-followup-qa`  
**Base:** `phase1-2-case-workspace-history` (Phase 1.2A committed)

---

## Current branch

`phase1-3-followup-qa`

---

## Current git status

```
 M app/api/routes/cases.py
 M app/services/case_service.py
 M tests/test_case_api.py
?? app/schemas/follow_up_schema.py
?? app/services/follow_up_chat_service.py
?? tests/test_follow_up_chat.py
?? data/reports/phase1_3_followup_qa_implementation_2026-07-04.md
?? data/reports/phase1_3_followup_qa_precommit_review_2026-07-04.md
```

**Diff stat (implementation code only):** 3 files changed, +263 / −1 lines; 3 new source/test files.

No `.env`, credentials, cache artifacts, or unrelated generated files appear in the change set.

---

## Files reviewed

### Planning / handoff (read)

| File | Purpose |
|------|---------|
| `AGENTS.md` | Product rules, approved sources, pipeline boundaries |
| `PROJECT_STATE.md` | Prior phase state (not yet updated for 1.3) |
| `data/reports/phase1_3_followup_qa_readiness_2026-07-04.md` | Phase 1.3 scope and endpoint recommendation |
| `data/reports/phase1_3_followup_qa_implementation_2026-07-04.md` | Implementation summary |
| `data/reports/phase1_2_case_workspace_followup_forms_plan_2026-07-04.md` | Broader roadmap constraints |
| `data/reports/phase1_2a_case_workspace_history_implementation_2026-07-04.md` | Phase 1.2A foundation |

### Implementation (code review)

| File | Role |
|------|------|
| `app/schemas/follow_up_schema.py` | Request/response/citation models |
| `app/services/follow_up_chat_service.py` | Grounding, LLM answer, citation validation, orchestration |
| `app/services/case_service.py` | Follow-up persistence helpers |
| `app/api/routes/cases.py` | `POST/GET /followups` routes |
| `tests/test_follow_up_chat.py` | 14 unit tests (mocked LLM) |
| `tests/test_case_api.py` | 6 new follow-up API tests (+ existing case tests) |

---

## Summary of endpoint approach

**Implemented as recommended (Option A):**

| Method | Route | Behavior |
|--------|-------|----------|
| `POST` | `/cases/{case_uuid}/followups` | Follow-up Q&A; persists user + assistant messages |
| `GET` | `/cases/{case_uuid}/followups` | Lists follow-up thread + linked report version |

**Explicit regeneration unchanged:**

- `POST /cases/{case_uuid}/reports/regenerate` → `CaseService.generate_report_version()`
- `POST /cases/{case_uuid}/messages` → still appends message **and** regenerates report (legacy)

---

## Verification checklist (25 items)

| # | Requirement | Result | Evidence |
|---|-------------|--------|----------|
| 1 | Scope limited to follow-up Q&A | **Pass** | New service/routes only; no retrieval/ranker/export edits |
| 2 | Dedicated follow-up endpoints | **Pass** | `cases.py` lines 201–241 |
| 3 | Normal follow-up does not create new report version | **Pass** | `add_follow_up_exchange()` writes `CaseMessage` rows only |
| 4 | Normal follow-up does not call `generate_report_version()` | **Pass** | `answer_follow_up()` has no regen call; tests assert `mock_regen.assert_not_called()` |
| 5 | `/reports/regenerate` remains explicit regen path | **Pass** | Route unchanged at lines 139–158 |
| 6 | Answers grounded in saved case/report context | **Pass** | `build_grounding_package()` loads saved version + case fields |
| 7 | Uses latest saved report version by default | **Pass** | `get_grounding_report_version(case, None)` → `max(version_number)` |
| 8 | Citations / source metadata preserved in response | **Pass (minor gap)** | Top-level `citations[]` with `document_type`, quote, `grounded`; assistant `message_metadata.citations`. Report `source_references` block not copied explicitly into grounding JSON (authorities + gaps cover most use cases) |
| 9 | Source gaps not hidden | **Pass** | `retrieval_gaps`, `source_coverage_audit`, `disclosures[]`, `unindexed_sources_disclosed` in grounding and response |
| 10 | LLM behavior mocked in tests | **Pass** | All service tests pass `llm_callable=fake_llm`; API tests patch `answer_follow_up` |
| 11 | No live OpenAI calls in tests | **Pass** | No test invokes `FollowUpChatService.call_llm` or real `OpenAI` client |
| 12 | Missing case → correct error | **Pass** | API 404; `CaseNotFoundError` |
| 13 | Missing saved report → clear error | **Pass** | `CaseReportRequiredError` → HTTP 400; empty `report_versions` tested at service level |
| 14 | Empty question validation | **Pass** | `min_length=1` → HTTP 422 (`test_post_followup_422_when_empty_question`) |
| 15 | Follow-up history listable | **Pass** | `GET /followups` + `list_follow_up_thread()` |
| 16 | User + assistant messages persisted correctly | **Pass** | `add_follow_up_exchange()` with `intent=follow_up`, linked version, citations/disclosures on assistant row (persistence verified via unit mock; no live DB integration test) |
| 17 | No Step 1/2/3 form generation | **Pass** | No form services/routes added |
| 18 | No arbitration ingestion | **Pass** | None |
| 19 | No LMOU ingestion | **Pass** | Disclosure only when steward asks about LMOU |
| 20 | No supervisor-manual ingestion | **Pass** | None |
| 21 | No production auth/security layer | **Pass** | No auth middleware or audit tables added |
| 22 | No sensitive logging | **Pass** | No `print`, `logger`, or logging calls in follow-up service |
| 23 | No accidental commit files | **Pass** | Six implementation files + two local reports only |
| 24 | Implementation report accurate | **Pass** | Endpoints, files, test counts, and results match code review and re-run tests below |
| 25 | Tests believable and sufficient for Phase 1.3 slice 1 | **Pass (with notes)** | Covers readiness acceptance cases; gaps noted in Risks |

---

## Whether follow-up Q&A avoids report regeneration

**Yes.** The follow-up path:

1. Loads case + saved `CaseReportVersion`
2. Builds grounding package from saved JSON/columns
3. Generates answer (LLM when not mocked)
4. Persists two `CaseMessage` rows via `add_follow_up_exchange()`

It never inserts a `CaseReportVersion` row and never calls `CaseService.generate_report_version()`.

When new facts are detected, the service sets `requires_report_regen: true` and suggests `regenerate_report` — it does **not** auto-regenerate.

---

## Whether saved report/case grounding is used

**Yes.** `build_grounding_package()` assembles:

- Case: `initial_question`, `known_facts`, uploads from message metadata, prior follow-up thread
- Report version: `report_data` sections, `report_summary`, `retrieval_gaps`, `source_coverage_audit`, `ranked_authorities`, `issue_analysis`, `evidence_items`
- Post-validation corpus: `saved_quotes` from authority sections, supporting evidence, and ranked authorities

Default version resolution uses the **latest** saved version; optional `report_version` request field pins a specific version.

**Note:** Pre–Phase 1.2A rows with `NULL` denormalized columns still work via fallbacks to nested `report_data` / limitations JSON, consistent with readiness guidance.

---

## Whether citations/source metadata are preserved

**Yes, in the follow-up response layer:**

- API response includes `citations[]` (`document_type`, `document_name`, `article_or_section`, `page`, `quote`, `grounded`)
- Assistant message metadata stores the same citation list plus `disclosures`, `facts_needed`
- Post-processing validates quotes against saved excerpts; ungrounded quotes get `grounded: false` and a disclosure

**Minor gap:** The report’s aggregated `source_references` object is not copied as its own grounding field. Authority sections and gap metadata largely subsume it for slice 1.

---

## Whether LLM behavior is mocked in tests

**Yes.**

- `tests/test_follow_up_chat.py`: every `generate_answer` / `answer_follow_up` test supplies `llm_callable=...`
- `tests/test_case_api.py`: follow-up routes patch `FollowUpChatService.answer_follow_up` or `list_follow_up_thread`

No test reaches `FollowUpChatService.call_llm()` or the OpenAI SDK.

---

## Whether any live OpenAI call occurred during review

**No.** Review consisted of static code inspection and local pytest runs with mocked/injected LLM behavior only.

**Production note:** When a steward calls `POST /followups` without test mocks, `call_llm()` will use `gpt-4o-mini` and send the grounding JSON prompt — same external-API pattern as the existing analysis pipeline. That is expected for runtime, not exercised in this review.

---

## Whether any HTTP server was started

**No.** FastAPI `TestClient` runs in-process only.

---

## Whether anything was pushed, uploaded, deployed, synced, or exposed

**No.** Local read-only review and pytest only. No git push, merge, deploy, or network listener.

---

## Test results (re-run during review)

### Targeted

```bash
venv\Scripts\python.exe -m pytest tests/test_follow_up_chat.py tests/test_case_api.py -v --tb=short
```

**Result:** **28 passed**, 0 failed, 1 warning (Starlette/httpx deprecation)

### Non-integration suite

```bash
venv\Scripts\python.exe -m pytest tests/ -m "not integration" -q --tb=no
```

**Result:** **207 passed**, 1 deselected, 0 failed, 2 warnings

Matches the implementation report claims.

---

## Risks and concerns

| Severity | Concern | Notes |
|----------|---------|-------|
| Low | `POST /messages` still regenerates | Documented; UI must use `/followups`. Deferred to slice 2 per plan |
| Low | `follow_up_schema.py` partially unused | Routes define inline `FollowUpRequest`; schema models not wired to FastAPI response_model | 
| Low | No DB integration test for `add_follow_up_exchange` | Persistence logic is straightforward; covered by mock + metadata shape review |
| Low | No API test for invalid pinned `report_version` (404) | Service raises `ReportVersionNotFoundError`; route maps to 404 — not explicitly API-tested |
| Low | `list_follow_up_messages` includes assistant rows with `answer_type` even if `intent` missing | Unlikely to matter until other assistant message types exist |
| Low | `PROJECT_STATE.md` / `AGENTS.md` checklist not updated | AGENTS.md recommends updating project state after significant work — doc-only follow-up |
| Medium (runtime) | Live follow-up sends full grounding JSON to OpenAI | Consistent with existing pipeline; steward should treat as sensitive channel until Phase 1.7 local-LLM option |
| Medium (runtime) | Heuristic `NEW_FACT_SIGNALS` for regen suggestion | Simple string rules; may false-positive/negative — acceptable for slice 1 |

**No blocking defects found** for Phase 1.3 slice 1 scope.

---

## Required fixes before commit

**None blocking.**

Optional (can be same commit or immediate follow-up):

1. Update `PROJECT_STATE.md` with Phase 1.3 summary (per `AGENTS.md` checklist).
2. Import `FollowUpRequest` from `app/schemas/follow_up_schema.py` in routes to avoid duplicate model definitions (cosmetic).
3. Add API test for `POST /followups` with invalid `report_version` → 404 (nice-to-have).
4. Include both implementation and pre-commit review reports in the commit.

---

## Final recommendation

### **Commit — approved for Phase 1.3 slice 1**

The implementation matches the readiness report’s recommended endpoint approach, stays within scope, avoids automatic report regeneration on normal follow-up Q&A, grounds answers in saved case/report data, preserves citations and gap disclosures, and passes all targeted and non-integration tests with mocked LLM behavior.

Proceed with commit on `phase1-3-followup-qa` when the steward approves. Consider including `PROJECT_STATE.md` update and the two `data/reports/phase1_3_*` artifacts in the commit.

---

## Confirmation

| Item | Status |
|------|--------|
| Implementation code modified during review | **No** |
| Git commit | **No** |
| Merge / push / upload / publish / deploy / sync | **No** |
| HTTP server started | **No** |
| Live OpenAI calls | **No** |
| External grievance data transmission | **No** |
