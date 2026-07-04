# Phase 1.3 Implementation Report — Follow-Up Q&A Grounded in Saved Cases/Reports

**Prepared:** 2026-07-04  
**Branch:** `phase1-3-followup-qa` (created from `phase1-2-case-workspace-history`)  
**Status:** Implementation complete — **not committed** (awaiting user review)

---

## Summary

Phase 1.3 adds steward follow-up Q&A grounded in saved case report versions without automatic full report regeneration. The steward can ask questions after a report is saved; answers are built from the saved report, retrieval gaps, source audit, citations, uploads metadata, and prior follow-up thread. User and assistant messages persist under the same case history via `case_messages.message_metadata`.

Report regeneration remains explicit through `POST /cases/{uuid}/reports/regenerate` and legacy `POST /cases/{uuid}/messages`. No retrieval, ranker, narrative, or export pipeline changes were made.

---

## Endpoint approach implemented

**Dedicated follow-up endpoints (Option A from readiness report):**

| Method | Route | Behavior |
|--------|-------|----------|
| `POST` | `/cases/{case_uuid}/followups` | Steward follow-up question → grounded answer; persists user + assistant messages; **no** `generate_report_version()` |
| `GET` | `/cases/{case_uuid}/followups` | Lists follow-up thread messages with linked report version metadata |

**Unchanged:**

- `POST /cases/{uuid}/messages` — still triggers full report regeneration
- `POST /cases/{uuid}/reports/regenerate` — explicit regeneration path

---

## Files changed

| File | Change |
|------|--------|
| `app/schemas/follow_up_schema.py` | **New** — request/response/citation Pydantic models |
| `app/services/follow_up_chat_service.py` | **New** — grounding package builder, citation validation, mocked-testable LLM answer generation, orchestration |
| `app/services/case_service.py` | Added `CaseReportRequiredError`, `get_grounding_report_version()`, `list_follow_up_messages()`, `serialize_message()`, `add_follow_up_exchange()` |
| `app/api/routes/cases.py` | Registered `POST/GET /cases/{uuid}/followups`; added `FollowUpRequest` |
| `tests/test_follow_up_chat.py` | **New** — 14 unit tests (grounding, citations, remedy/LMOU disclosure, regen suggestion, persistence guard) |
| `tests/test_case_api.py` | Added 6 API route tests for follow-up endpoints |

**Not modified:** retrieval pipeline, ranker, narratives, export layer, Alembic migrations.

---

## Data flow

```
Steward follow-up question
  → POST /cases/{uuid}/followups
  → CaseService.get_case + get_grounding_report_version
  → FollowUpChatService.build_grounding_package
  → FollowUpChatService.generate_answer (gpt-4o-mini JSON; injectable for tests)
  → Citation validation against saved report excerpts
  → CaseService.add_follow_up_exchange (user + assistant CaseMessage rows)
  → FollowUpResponse JSON (no new CaseReportVersion)
```

### Grounding package sources

- Saved `report_data` / nested `GrievanceHubReport` sections
- Denormalized `report_summary`, `retrieval_gaps`, `source_coverage_audit`
- `ranked_authorities`, `issue_analysis`, `evidence_items`
- Case `known_facts`, upload metadata, prior follow-up thread
- Collected `saved_quotes` corpus for post-validation

### Message metadata (slice 1 — no migration)

**User message:** `intent=follow_up`, `linked_report_version_id`, `linked_report_version_number`

**Assistant message:** above plus `answer_type`, `citations`, `disclosures`, `facts_needed`, `requires_report_regen`, `suggested_actions`

---

## Test commands run and results

### Targeted follow-up + case API tests

```bash
venv\Scripts\python.exe -m pytest tests/test_follow_up_chat.py tests/test_case_api.py -v --tb=short
```

**Result:** **28 passed**, 0 failed

### Full non-integration suite

```bash
venv\Scripts\python.exe -m pytest tests/ -m "not integration" -q --tb=no
```

**Result:** **207 passed**, 1 deselected, 0 failed

### Coverage highlights

| Area | Tests |
|------|-------|
| Grounding package from saved version | `test_build_grounding_package_from_saved_version` |
| Missing evidence / report checklist | `test_missing_evidence_question_uses_report_checklist` |
| Saved quote citation | `test_authority_lookup_cites_saved_quote` |
| No hallucinated facts | `test_no_hallucinated_grievant_facts` |
| Remedy gap disclosure | `test_remedy_follow_up_discloses_no_explicit_authority` |
| LMOU unindexed disclosure | `test_lmou_not_indexed_disclosure` |
| Ungrounded quote rejection | `test_citation_validation_rejects_ungrounded_quote` |
| Separate CONTRACT/CIM citations | `test_separate_contract_and_cim_citations` |
| New facts → suggest regen, no auto-regen | `test_new_facts_suggests_regen_not_auto_regen` |
| Prior follow-ups in context | `test_prior_followups_included_in_context` |
| No report regeneration | `test_answer_follow_up_persists_without_report_regeneration`, `test_post_followup_persists_messages_no_new_report_version` |
| Missing case / report / version / empty question | API 404/400/422 tests |
| GET follow-up thread | `test_get_followups_returns_thread` |

All LLM-dependent tests use injected `llm_callable` mocks — no live OpenAI calls during CI-style runs.

---

## Intentionally deferred

| Item | Phase |
|------|-------|
| Change `POST /messages` default to chat-only | 1.3 slice 2 |
| `CaseMessage` column migration (`message_type`, `intent`, `citations`) | 1.3 slice 2 |
| Supplemental corpus retrieval in follow-up | 1.3 slice 2 / 1.6 |
| Step 1/2/3 grievance form generation | 1.5 |
| Proposed remedy drafting column | 1.4 |
| Frontend chat panel | 1.7 |
| Production auth / audit log | 1.7 |

---

## Final git status

Run after implementation (uncommitted):

```
On branch phase1-3-followup-qa
Changes not staged for commit:
	modified:   app/api/routes/cases.py
	modified:   app/services/case_service.py
	modified:   tests/test_case_api.py

Untracked files:
	app/schemas/follow_up_schema.py
	app/services/follow_up_chat_service.py
	tests/test_follow_up_chat.py
	data/reports/phase1_3_followup_qa_implementation_2026-07-04.md
```

---

## Confirmation

| Item | Status |
|------|--------|
| Git commit | **No** |
| Merge / push / upload / publish / deploy / sync | **No** |
| HTTP server started | **No** |
| Live follow-up Q&A against real grievance data | **No** |
| External transmission of grievance data | **No** |
| Retrieval/ranker behavior changed | **No** |

Ready for user review before commit.
