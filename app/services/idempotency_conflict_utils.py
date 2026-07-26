"""Shared helper for detecting expected idempotency-key unique conflicts.

Several services accept a caller-supplied ``idempotency_key`` and follow the
same pattern: check for an existing committed row, and if none is found,
insert a new one inside a nested transaction (SAVEPOINT) guarded by a unique
index on ``(case_uuid, idempotency_key)`` (see ``CaseDomainEvent``,
``CaseFormDraftRecord``, and ``CaseSavedArtifact`` in ``app.database.models``).

When two requests race with the same key, both may pass the initial
existence check before either commits. The database resolves the race: the
losing session's flush raises ``IntegrityError``. This module lets callers
recognize that *specific, expected* conflict by the violated index name and
fall back to the idempotent-read path, while any other integrity failure
(unrelated constraint, NOT NULL, foreign key, etc.) is left for the caller
to re-raise unchanged.
"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError

CASE_DOMAIN_EVENTS_IDEMPOTENCY_INDEX = "ix_case_domain_events_case_idempotency"
CASE_SAVED_ARTIFACTS_IDEMPOTENCY_INDEX = "ix_case_saved_artifacts_idempotency"
CASE_FORM_DRAFT_RECORDS_IDEMPOTENCY_INDEX = "ix_case_form_draft_records_idempotency"


def violated_constraint_name(exc: IntegrityError) -> str | None:
    """Best-effort extraction of the violated constraint/index name.

    Reads psycopg's libpq diagnostics (``orig.diag.constraint_name``), which
    is populated for unique-violation errors. Returns ``None`` when the
    underlying driver does not expose it, so callers degrade to treating the
    conflict as unrecognized (and re-raise) rather than guessing.
    """
    orig = getattr(exc, "orig", None)
    diag = getattr(orig, "diag", None)
    return getattr(diag, "constraint_name", None)


def is_idempotency_conflict(exc: IntegrityError, *expected_index_names: str) -> bool:
    """Return True only if ``exc`` is one of the named unique-index conflicts.

    Callers must re-raise ``exc`` when this returns False -- it means some
    other integrity rule was violated and must not be masked as a replay.
    """
    name = violated_constraint_name(exc)
    return name is not None and name in expected_index_names
