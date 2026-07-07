"""Add case step timeline and draft history persistence tables.

Revision ID: c4d5e6f7a8b9
Revises: b2c3d4e5f6a7
Create Date: 2026-07-06

Phase 1.4D — persist case steps, outcomes, timeline events, and form draft records.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "case_steps",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("case_uuid", sa.String(length=36), nullable=False),
        sa.Column("step_type", sa.String(length=50), nullable=False),
        sa.Column("step_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("is_closed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("was_reopened", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("appealed_from_prior_step", sa.String(length=50), nullable=True),
        sa.Column("prior_step_id", sa.Integer(), nullable=True),
        sa.Column("prior_step_outcome_uuid", sa.String(length=36), nullable=True),
        sa.Column("report_version_id", sa.Integer(), nullable=True),
        sa.Column("report_version_number", sa.Integer(), nullable=True),
        sa.Column("follow_up_message_ids", sa.JSON(), nullable=True),
        sa.Column("template_id", sa.String(length=150), nullable=True),
        sa.Column("template_available", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("template_availability", sa.String(length=80), nullable=True),
        sa.Column("step_metadata", sa.JSON(), nullable=True),
        sa.Column("opened_at", sa.DateTime(), nullable=False),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("reopened_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["grievance_cases.id"]),
        sa.ForeignKeyConstraint(["prior_step_id"], ["case_steps.id"]),
        sa.ForeignKeyConstraint(["report_version_id"], ["case_report_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_case_steps_id"), "case_steps", ["id"], unique=False)
    op.create_index(op.f("ix_case_steps_case_uuid"), "case_steps", ["case_uuid"], unique=False)
    op.create_index(
        "ix_case_steps_case_id_step_type",
        "case_steps",
        ["case_id", "step_type"],
        unique=False,
    )

    op.create_table(
        "case_step_outcomes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("outcome_uuid", sa.String(length=36), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("case_uuid", sa.String(length=36), nullable=False),
        sa.Column("case_step_id", sa.Integer(), nullable=False),
        sa.Column("step_type", sa.String(length=50), nullable=False),
        sa.Column("outcome_type", sa.String(length=50), nullable=False),
        sa.Column("decision_summary", sa.Text(), nullable=True),
        sa.Column("decision_date", sa.String(length=50), nullable=True),
        sa.Column("decision_maker_name", sa.String(length=255), nullable=True),
        sa.Column("decision_maker_title", sa.String(length=255), nullable=True),
        sa.Column("decision_document_refs", sa.JSON(), nullable=True),
        sa.Column("steward_notes", sa.Text(), nullable=True),
        sa.Column("close_step", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("close_case", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("appeal_to_next_step", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("next_step_type", sa.String(length=50), nullable=True),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["grievance_cases.id"]),
        sa.ForeignKeyConstraint(["case_step_id"], ["case_steps.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("outcome_uuid"),
    )
    op.create_index(op.f("ix_case_step_outcomes_id"), "case_step_outcomes", ["id"], unique=False)
    op.create_index(
        op.f("ix_case_step_outcomes_outcome_uuid"),
        "case_step_outcomes",
        ["outcome_uuid"],
        unique=True,
    )
    op.create_index(
        op.f("ix_case_step_outcomes_case_uuid"),
        "case_step_outcomes",
        ["case_uuid"],
        unique=False,
    )

    op.create_table(
        "case_form_draft_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("draft_uuid", sa.String(length=36), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("case_uuid", sa.String(length=36), nullable=False),
        sa.Column("case_step_id", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.String(length=150), nullable=False),
        sa.Column("report_version_id", sa.Integer(), nullable=True),
        sa.Column("report_version_number", sa.Integer(), nullable=True),
        sa.Column("follow_up_message_ids", sa.JSON(), nullable=True),
        sa.Column("draft_version", sa.Integer(), nullable=False),
        sa.Column("draft_status", sa.String(length=50), nullable=False),
        sa.Column("validation_status", sa.String(length=50), nullable=True),
        sa.Column("missing_required_field_ids", sa.JSON(), nullable=True),
        sa.Column("steward_override_field_ids", sa.JSON(), nullable=True),
        sa.Column("approval_status", sa.String(length=50), nullable=True),
        sa.Column("export_status", sa.String(length=50), nullable=True),
        sa.Column("export_attempted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("exported_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["grievance_cases.id"]),
        sa.ForeignKeyConstraint(["case_step_id"], ["case_steps.id"]),
        sa.ForeignKeyConstraint(["report_version_id"], ["case_report_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("draft_uuid"),
    )
    op.create_index(
        op.f("ix_case_form_draft_records_id"),
        "case_form_draft_records",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_case_form_draft_records_draft_uuid"),
        "case_form_draft_records",
        ["draft_uuid"],
        unique=True,
    )
    op.create_index(
        op.f("ix_case_form_draft_records_case_uuid"),
        "case_form_draft_records",
        ["case_uuid"],
        unique=False,
    )

    op.create_table(
        "case_timeline_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_uuid", sa.String(length=36), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("case_uuid", sa.String(length=36), nullable=False),
        sa.Column("case_step_id", sa.Integer(), nullable=True),
        sa.Column("step_type", sa.String(length=50), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("event_timestamp", sa.DateTime(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("report_version_id", sa.Integer(), nullable=True),
        sa.Column("report_version_number", sa.Integer(), nullable=True),
        sa.Column("follow_up_message_ids", sa.JSON(), nullable=True),
        sa.Column("draft_record_id", sa.Integer(), nullable=True),
        sa.Column("draft_record_uuid", sa.String(length=36), nullable=True),
        sa.Column("upload_refs", sa.JSON(), nullable=True),
        sa.Column("outcome_uuid", sa.String(length=36), nullable=True),
        sa.Column("prior_step_type", sa.String(length=50), nullable=True),
        sa.Column("next_step_type", sa.String(length=50), nullable=True),
        sa.Column("export_ref", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["grievance_cases.id"]),
        sa.ForeignKeyConstraint(["case_step_id"], ["case_steps.id"]),
        sa.ForeignKeyConstraint(["draft_record_id"], ["case_form_draft_records.id"]),
        sa.ForeignKeyConstraint(["report_version_id"], ["case_report_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_uuid"),
    )
    op.create_index(
        op.f("ix_case_timeline_events_id"),
        "case_timeline_events",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_case_timeline_events_event_uuid"),
        "case_timeline_events",
        ["event_uuid"],
        unique=True,
    )
    op.create_index(
        op.f("ix_case_timeline_events_case_uuid"),
        "case_timeline_events",
        ["case_uuid"],
        unique=False,
    )
    op.create_index(
        op.f("ix_case_timeline_events_event_timestamp"),
        "case_timeline_events",
        ["event_timestamp"],
        unique=False,
    )
    op.create_index(
        "ix_case_timeline_events_case_uuid_event_timestamp",
        "case_timeline_events",
        ["case_uuid", "event_timestamp"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_case_timeline_events_case_uuid_event_timestamp",
        table_name="case_timeline_events",
    )
    op.drop_index(
        op.f("ix_case_timeline_events_event_timestamp"),
        table_name="case_timeline_events",
    )
    op.drop_index(
        op.f("ix_case_timeline_events_case_uuid"),
        table_name="case_timeline_events",
    )
    op.drop_index(
        op.f("ix_case_timeline_events_event_uuid"),
        table_name="case_timeline_events",
    )
    op.drop_index(op.f("ix_case_timeline_events_id"), table_name="case_timeline_events")
    op.drop_table("case_timeline_events")

    op.drop_index(
        op.f("ix_case_form_draft_records_case_uuid"),
        table_name="case_form_draft_records",
    )
    op.drop_index(
        op.f("ix_case_form_draft_records_draft_uuid"),
        table_name="case_form_draft_records",
    )
    op.drop_index(
        op.f("ix_case_form_draft_records_id"),
        table_name="case_form_draft_records",
    )
    op.drop_table("case_form_draft_records")

    op.drop_index(
        op.f("ix_case_step_outcomes_case_uuid"),
        table_name="case_step_outcomes",
    )
    op.drop_index(
        op.f("ix_case_step_outcomes_outcome_uuid"),
        table_name="case_step_outcomes",
    )
    op.drop_index(op.f("ix_case_step_outcomes_id"), table_name="case_step_outcomes")
    op.drop_table("case_step_outcomes")

    op.drop_index("ix_case_steps_case_id_step_type", table_name="case_steps")
    op.drop_index(op.f("ix_case_steps_case_uuid"), table_name="case_steps")
    op.drop_index(op.f("ix_case_steps_id"), table_name="case_steps")
    op.drop_table("case_steps")
