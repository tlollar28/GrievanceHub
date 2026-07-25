# W6 M6 — Grievance Generate, Edit, Validate, Save, and Print Report

1. **Date:** 2026-07-24
2. **Branch:** `main`
3. **Starting HEAD:** `44096141aa26118783012300e8712b731f47aae0`
4. **Verified M5 commit SHA:** `44096141aa26118783012300e8712b731f47aae0` — `feat(w6): implement analysis preview and saving`
5. **Pre-M6 Git status**
   - Branch `main` ahead of `origin/main` by 9 commits
   - Working tree clean of tracked M5 changes
   - Untracked only (deliberately excluded): prior M4/M5 smoke helpers and pytest temp logs under `docs/temp/`

6. **Grievance routes inspected**
   - `POST /cases/{case_uuid}/actions` with `{ "action": "generate_grievance" }`
   - `POST /cases/{case_uuid}/grievances/save-and-print`
   - `GET /cases/{case_uuid}/artifacts?artifact_type=grievance_form`
   - `GET /cases/{case_uuid}/artifacts/{artifact_uuid}`
   - `GET /cases/{case_uuid}/artifacts/{artifact_uuid}/pdf`
7. **Schemas inspected**
   - `WorkspaceActionRequest` / `WorkspaceActionResponse` / `GrievanceGenerationResult` in `app/schemas/case_workspace_action_schema.py`
   - `SaveAndPrintGrievanceRequest` / `SaveAndPrintResponse` / `CaseSavedArtifact*` in `app/schemas/case_saved_artifact_schema.py`
   - `ExactTemplateFieldMapping` / draft schemas in `app/schemas/grievance_form_draft_schema.py`
8. **OpenAPI paths verified**
   - Actions, grievances/save-and-print, artifacts list/detail/pdf present
   - Response shapes incomplete in places — **Pydantic / service serialization is source of truth**
9. **Template registry inspected**
   - `app/services/grievance_template_registry.py`
   - Official: `official_grievance_worksheet_step_1`, `official_standard_grievance_form_step_2`
   - Also registered (not exposed in M6 UI): `local_300_standard_grievance_form_79_1`
10. **Field mappings inspected**
    - `app/services/grievance_form_draft_builder.py` (`_OFFICIAL_STEP_1_FIELD_MAPPINGS`, `_OFFICIAL_STEP_2_FIELD_MAPPINGS`)
    - AcroForm fill in `app/services/grievance_pdf_export_service.py`
11. **Validation and never-invent services inspected**
    - Draft builder `_validate_draft_fields` / protected blank provenance
    - Save-and-print stores client-supplied validation fields; does not re-block incomplete drafts
12. **Existing backend tests inspected**
    - `tests/test_grievance_template_registry.py`
    - `tests/test_grievance_form_draft_builder.py`
    - `tests/test_official_grievance_pdf_export.py`
    - `tests/test_case_save_and_print_artifacts.py`
    - `tests/test_case_workspace_action_contract.py` / `test_case_workspace_action_api.py`
    - `tests/test_steward_artifact_workflow.py`
    - `tests/test_case_ai_first_chat_workspace.py` / `test_case_workspace_action_w2.py`

13. **Exact Generate contract**
    - `POST /cases/{uuid}/actions` body `{ "action": "generate_grievance" }`
    - Response: `WorkspaceActionResponse` with `grievance_generation`
    - Prerequisites may return `status: "prerequisites_not_met"` (HTTP 200) with messages
14. **Exact generation response**
    - `grievance_generation.template_id`, `step_type`, `draft_status`, `editable`, flat `field_values`, `official_artifact_created: false`, `draft_created: true`
15. **Exact Step 1 template contract**
    - `template_id = official_grievance_worksheet_step_1`
    - `step_type = step_1_initial` when case is on Step 1
16. **Exact Step 2 template contract**
    - `template_id = official_standard_grievance_form_step_2`
    - `step_type = step_2_appeal` when case is on Step 2
17. **Verification that only Step 1 and Step 2 are supported**
    - M6 UI accepts only those two template IDs
    - Unsupported / deferred templates show steward notice and do not render a substitute form
18. **Exact draft field shape**
    - Flat `dict[str, string-like]` in `field_values` (empty string for blanks)
19. **Required-field behavior**
    - Client early feedback from mirrored mappings; backend save does not reject incomplete drafts
20. **Protected and never-invent behavior**
    - Protected blanks remain blank on Generate; UI warns; steward must supply facts
21. **Steward override behavior**
    - Client tracks edited field IDs → `steward_override_field_ids` on Save
22. **Exact Save-and-Print contract**
    - Single endpoint `POST .../grievances/save-and-print`
    - Body includes `template_id`, `field_values`, `steward_override_field_ids`, `missing_required_field_ids`, `validation_status`, `draft_status`, `idempotency_key`, `prepare_pdf`
23. **Exact idempotency behavior**
    - Matching `case_uuid` + `idempotency_key` → `status=idempotent_replay`, no new artifact
24. **Exact PDF-success behavior**
    - `status=saved`, `pdf_status=ready`, `print_ready=true`, export via artifact PDF path
25. **Exact PDF-failure behavior**
    - Artifact persists; `status=saved_pdf_failed`; UI shows saved-with-warning
26. **Exact artifact and PDF retrieval behavior**
    - List/filter `artifact_type=grievance_form`; detail JSON; PDF bytes `application/pdf`
27. **Verification Generate creates no artifact**
    - Live DB after Generate: `grievance_artifacts=0`, no grievance-related events
28. **Verification Cancel creates no artifact, PDF, or event**
    - Cancel is client-only discard; no Save request; DB unchanged
29. **Verification Conversation creates no grievance**
    - Live interaction: `grievance_draft_created=false`; artifact count unchanged
30. **Verification Analysis creates no grievance**
    - Live `reports/generate`: artifact count unchanged
31. **Architecture corrections and removed later-step assumptions**
    - Docs updated: official grievance generation ends at Step 2
    - Removed steward-UI Step 3 placeholder / later-form generation assumptions from W6 UI architecture
    - No backend redesign; no speculative backend changes
    - No narrow backend fix required for M6

32. **Files created**
    - `frontend/src/api/types/grievances.ts`
    - `frontend/src/api/grievances.ts`
    - `frontend/src/features/grievance/templateFields.ts`
    - `frontend/src/features/grievance/draftValidation.ts`
    - `frontend/src/features/cases/useGenerateGrievanceMutation.ts`
    - `frontend/src/features/cases/useSaveGrievanceMutation.ts`
    - `frontend/src/features/cases/useGrievanceArtifactsQuery.ts`
    - `frontend/src/features/cases/useGrievanceArtifactQuery.ts`
    - `frontend/src/components/grievance/*` (panel, draft editor, validation, save actions, artifact list/detail, PDF actions, CSS)
    - `frontend/src/routes/CaseGrievancePage.tsx`
    - `frontend/src/test/grievance.test.tsx`
    - `docs/temp/W6_M6_GRIEVANCE_REPORT.md`
33. **Files modified**
    - `frontend/src/app/routes.tsx`
    - `frontend/src/components/workspace/WorkspaceSectionNav.tsx`
    - `frontend/src/features/cases/savedCaseActions.ts` (`grievanceKeys`)
    - `frontend/src/test/savedCasesFixtures.ts`
    - `PROJECT_STATE.md`, `README.md`, `docs/ARCHITECTURE.md`, `docs/W6_UI_ARCHITECTURE.md`
34. **Dependencies changed:** none
35. **Routing implementation:** `/cases/:caseUuid/grievance` under `CaseWorkspaceShell`; nav adds Grievance
36. **Generate implementation:** explicit button; exact `{action:"generate_grievance"}`; no auto-generate; pending disables duplicates
37. **Temporary draft implementation:** local React state in `GrievancePanel`; banner; case-scoped; not in Query cache as official artifact
38. **Field-editing implementation:** verified template fields with labels/required/protected; dirty/override tracking
39. **Validation implementation:** `DraftValidationSummary` client early feedback; backend authoritative on save
40. **Never-invent implementation:** protected blanks stay blank; steward warnings
41. **Steward-override implementation:** edited IDs sent as `steward_override_field_ids`
42. **Cancel behavior:** confirmation when dirty; no Save; no artifact/PDF/event
43. **Save behavior:** `prepare_pdf: false`; clears draft on success; invalidates grievance + workspace queries
44. **Save-and-Print behavior:** `prepare_pdf: true`; same endpoint; PDF ready or saved-with-warning
45. **Step 1 official form behavior:** Generate → Save / Save and Print → official worksheet PDF
46. **Step 2 official form behavior:** after Step 1 denial+appeal outcome → Generate Step 2 template → Save and Print PDF
47. **Saved grievance restoration:** list/detail restore after refresh; temporary draft does not
48. **Query and state ownership:** TanStack Query for saved artifacts; ephemeral local draft; mutations `retry: false`
49. **Case isolation:** caseUuid effect clears draft; abort in-flight generate; no cross-case leakage
50. **Accessibility:** labels, required/protected announcements, validation summary, alertdialog cancel, aria-busy, role alert/status, PDF iframe titles, focus first invalid

51. **Tests added**
    - `frontend/src/test/grievance.test.tsx` (22 tests covering generate/edit/validate/cancel/save/PDF/isolation/no side effects)
52. **Exact commands run**
    - Frontend: `npm run typecheck`, `npm run lint`, `npm run test:run`, `npm run build`, `npm audit`
    - Backend focused pytest suite (grievance/action/save-and-print/chat invariants)
    - Live: uvicorn `:8000`, vite `:5173`, `docs/temp/_m6_live_smoke.py`
53. **Frontend validation**
    - typecheck exit 0
    - lint exit 0
    - test:run — 10 files, 99 tests, 0 failures
    - build exit 0
54. **Backend validation**
    - 123 passed (focused grievance-related suite)
55. **Direct FastAPI health:** `200` `{status:healthy, service:GrievanceHub}`
56. **Vite proxy result:** `200` healthy via `http://127.0.0.1:5173/api/health`
57. **Live Step 1 Generate result:** `official_grievance_worksheet_step_1`, artifacts=0
58. **Live Step 1 Cancel result:** client discard; artifacts remain 0 (no Save)
59. **Live Step 1 Save result:** `status=saved`, first official artifact created
60. **Live Step 1 Save-and-Print result:** `status=saved`, `pdf_status=ready`, `print_ready=true`
61. **Live Step 1 PDF result:** `application/pdf`, 691373 bytes
62. **Live Step 2 Generate result:** `official_standard_grievance_form_step_2` / `step_2_appeal`
63. **Live Step 2 Save-and-Print result:** `status=saved`, template Step 2, `pdf_status=ready`
64. **Live Step 2 PDF result:** `application/pdf`, 157075 bytes
65. **Refresh restoration result:** saved grievance list restores; temporary draft does not (unit + live contract)
66. **Verification no unsupported grievance form was exposed:** UI gates on supported IDs only
67. **Verification no general Artifact Library was implemented:** grievance-scoped list only; no compare/sources admin
68. **npm audit result:** React Router GHSA-qwww-vcr4-c8h2 (high); force-fix not applied; known W6 advisory classification retained
69. **React Router advisory status:** present; not introduced by M6; no unstable RSC APIs added
70. **Documentation updates:** PROJECT_STATE, README, ARCHITECTURE, W6_UI_ARCHITECTURE
71. **Files deliberately excluded**
    - `docs/temp/_m6_live_smoke.py`, `_m6_live_case_uuid.txt`, `_m6_live_step2_case_uuid.txt`
    - Prior M4/M5 smoke helpers and pytest logs
    - `frontend/dist/`, `node_modules/`, runtime PDFs/uploads
72. **Known non-blocking limitations**
    - OpenAPI grievance/report response shapes remain incomplete vs Pydantic
    - Save does not server-block incomplete required fields (client warns; backend stores as provided)
    - React Router advisory remains until W9/security packaging decision
    - Full Artifact Library / compare / Official Case Record browser remain M7
73. **M7 handoff items**
    - General Artifact Library UI
    - Artifact comparison
    - Broader Official Case Record browsing
    - History jump-to-context presentation beyond M6-limited grievance list
74. **Final verdict:** **PASS**
