# GrievanceHub Engineering Status

Last updated: 2026-07-18

Concise public engineering status for the current working tree. Detailed system
design lives in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Current status

| Item | State |
|------|--------|
| Branch | `phase-W3-case-asset-foundation` |
| Latest committed tip | `2e50b9e` — CrossCraft retirement |
| W1–W3 | Complete and committed |
| W4 | Implemented in working tree (Case Memory, domain events, workflow FSM, steward-controlled artifacts, workspace restore, `/ui` shell, normal-chat indexed retrieval) |
| W5 | Deferred — Local 300 Form 79-1 overlay PDF assembly |
| Production React UI | Deferred |
| Authentication / RBAC | Deferred |
| Cloud deployment | Deferred |

## Product model

GrievanceHub is a backend-first grievance case workspace. Each grievance matter
is managed as a persistent `GrievanceCase`. Conversation, Case Memory, evidence,
reports, grievances, artifacts, and workflow history remain attached to that case.

The application manages workflow automation. The steward controls when analysis
reports and grievances are created. There is no required Conversation → Analysis
→ Grievance sequence.

## Implemented capabilities

- Persistent case create / open / reopen / workspace restore
- Continuous AI conversation via `POST /cases/{case_uuid}/interactions`
- Indexed-source retrieval for normal chat with citation grounding
- Case Memory projected from domain events
- Explicit Generate Analysis Report (temporary preview → Save / Save and Print)
- Explicit Generate Grievance (editable field-value draft → Save / Save and Print)
- Artifacts library and Official Case Record for saved work
- Case asset uploads
- Analysis report HTML/PDF export
- FastAPI steward verification shell at `/ui`

## Normal chat vs analysis

| Path | Behavior |
|------|----------|
| Normal chat | Retrieves indexed sources, answers conversationally, may return grounded citations, persists messages, may update Case Memory; creates no report version or artifact |
| Generate Analysis | Explicit steward action; structured RAG report pipeline; temporary read-only preview |
| Save / Save and Print | First persistence point for versioned artifacts and Official Case Record entries |

## Stack

Python 3, FastAPI, SQLAlchemy, Alembic, PostgreSQL 16 + pgvector, OpenAI
embeddings and chat, Jinja2 + WeasyPrint, pytest.

## Indexed corpus (repository artifact)

The committed `app/sources/source_index.json` artifact currently includes
CONTRACT and CIM text chunks for local development. Live retrieval coverage
depends on the running database index.

## Recent milestones

| Phase | Outcome |
|-------|---------|
| Phase 0–1 | Retrieval relevance stabilization and structured GrievanceHub reports |
| Phase 2 | Persistent cases and versioned reports |
| Phase 3 | HTML/PDF export of saved analysis reports |
| W1–W3 | Workspace actions, AI chat foundation, case assets |
| W4 | Case Memory, workflow FSM, steward-controlled Generate/Save artifacts, chat indexed retrieval |
| CrossCraft retirement | Obsolete SPBS/cross-craft surface removed |

## Testing

```bash
python -m pytest tests/test_chat_source_retrieval.py tests/test_steward_artifact_workflow.py -q
python -m pytest tests/ -m "not integration" -q
```

## Next phase

W5 — complete Local 300 Form 79-1 overlay PDF assembly and filled-form
execution, then production UI, authentication/RBAC, and deployment hardening.

## Related documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`docs/saved_cases_ui_contract.md`](docs/saved_cases_ui_contract.md)
- [`README.md`](README.md)
