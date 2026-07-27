"""Add justified case_id query indexes (W6 Batch 2 index hardening).

Revision ID: i0j1k2l3m4n5
Revises: h9c0d1e2f3a4
Create Date: 2026-07-26

Adds indexes on the five case_id foreign-key columns identified by the W6
audit (BE-4) that are not already covered -- directly or via a leading
composite -- by an existing index: case_messages, case_report_versions,
case_step_outcomes, case_timeline_events, and case_form_draft_records.

The other three BE-4 columns (case_steps.case_id, case_saved_artifacts.
case_id, case_assets.case_id) are already served by pre-existing composite
indexes whose leading column is case_id, so no new index is added for them
here; this migration only declares those pre-existing indexes' ORM metadata
in app/database/models.py (no DDL change).

This migration does not touch idempotency uniqueness: the unique indexes on
(case_uuid, idempotency_key) for case_domain_events, case_form_draft_records,
and case_saved_artifacts already exist from prior migrations
(g8b9c0d1e2f3, e6f7a8b9c0d1) and are unchanged here.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "i0j1k2l3m4n5"
down_revision: Union[str, Sequence[str], None] = "h9c0d1e2f3a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Serves CaseService's recent/paginated message reads
    # (WHERE case_id = ? ORDER BY created_at, id).
    op.create_index(
        "ix_case_messages_case_id_created_at",
        "case_messages",
        ["case_id", "created_at", "id"],
        unique=False,
    )
    # Serves saved_case_service's ROW_NUMBER() OVER (PARTITION BY case_id
    # ORDER BY version_number DESC, id DESC) dashboard window query.
    op.create_index(
        "ix_case_report_versions_case_id_version",
        "case_report_versions",
        ["case_id", "version_number", "id"],
        unique=False,
    )
    # Serves saved_case_service's per-case outcome reads and its
    # PARTITION BY case_id ORDER BY recorded_at DESC, id DESC window query.
    op.create_index(
        "ix_case_step_outcomes_case_id_recorded_at",
        "case_step_outcomes",
        ["case_id", "recorded_at", "id"],
        unique=False,
    )
    # Serves case_step_progression_persistence_service's per-case timeline
    # reads and saved_case_service's PARTITION BY case_id ORDER BY
    # event_timestamp DESC, id DESC window query.
    op.create_index(
        "ix_case_timeline_events_case_id_event_timestamp",
        "case_timeline_events",
        ["case_id", "event_timestamp", "id"],
        unique=False,
    )
    # Serves case_step_progression_persistence_service's per-case,
    # created_at-ordered draft reads.
    op.create_index(
        "ix_case_form_draft_records_case_id_created_at",
        "case_form_draft_records",
        ["case_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_case_form_draft_records_case_id_created_at",
        table_name="case_form_draft_records",
    )
    op.drop_index(
        "ix_case_timeline_events_case_id_event_timestamp",
        table_name="case_timeline_events",
    )
    op.drop_index(
        "ix_case_step_outcomes_case_id_recorded_at",
        table_name="case_step_outcomes",
    )
    op.drop_index(
        "ix_case_report_versions_case_id_version",
        table_name="case_report_versions",
    )
    op.drop_index(
        "ix_case_messages_case_id_created_at",
        table_name="case_messages",
    )
