"""Add official saved artifacts and draft field persistence.

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-07-17

Supports Save and Print for analysis reports and grievance forms:
immutable official artifacts, populated field values on drafts, PDF refs.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e6f7a8b9c0d1"
down_revision: Union[str, Sequence[str], None] = "d5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "case_form_draft_records",
        sa.Column("template_version", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "case_form_draft_records",
        sa.Column("field_values", sa.JSON(), nullable=True),
    )
    op.add_column(
        "case_form_draft_records",
        sa.Column("content_snapshot", sa.JSON(), nullable=True),
    )
    op.add_column(
        "case_form_draft_records",
        sa.Column("is_official", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "case_form_draft_records",
        sa.Column("saved_by", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "case_form_draft_records",
        sa.Column("printed_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "case_form_draft_records",
        sa.Column("pdf_asset_uuid", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "case_form_draft_records",
        sa.Column("idempotency_key", sa.String(length=120), nullable=True),
    )
    op.create_index(
        "ix_case_form_draft_records_idempotency",
        "case_form_draft_records",
        ["case_uuid", "idempotency_key"],
        unique=True,
    )

    op.create_table(
        "case_saved_artifacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("artifact_uuid", sa.String(length=36), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("case_uuid", sa.String(length=36), nullable=False),
        sa.Column("artifact_type", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("version_label", sa.String(length=255), nullable=False),
        sa.Column("grievance_step", sa.String(length=50), nullable=True),
        sa.Column("template_id", sa.String(length=150), nullable=True),
        sa.Column("template_version", sa.String(length=80), nullable=True),
        sa.Column("content_json", sa.JSON(), nullable=False),
        sa.Column("key_summary_json", sa.JSON(), nullable=True),
        sa.Column("source_report_version_id", sa.Integer(), nullable=True),
        sa.Column("source_report_version_number", sa.Integer(), nullable=True),
        sa.Column("source_draft_record_uuid", sa.String(length=36), nullable=True),
        sa.Column("pdf_asset_uuid", sa.String(length=36), nullable=True),
        sa.Column("pdf_status", sa.String(length=50), nullable=False),
        sa.Column("printed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_latest_official", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("saved_by", sa.String(length=255), nullable=True),
        sa.Column("saved_at", sa.DateTime(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="official"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["grievance_cases.id"]),
        sa.ForeignKeyConstraint(
            ["source_report_version_id"], ["case_report_versions.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("artifact_uuid"),
    )
    op.create_index(
        op.f("ix_case_saved_artifacts_artifact_uuid"),
        "case_saved_artifacts",
        ["artifact_uuid"],
        unique=True,
    )
    op.create_index(
        op.f("ix_case_saved_artifacts_case_uuid"),
        "case_saved_artifacts",
        ["case_uuid"],
        unique=False,
    )
    op.create_index(
        "ix_case_saved_artifacts_case_type",
        "case_saved_artifacts",
        ["case_id", "artifact_type"],
        unique=False,
    )
    op.create_index(
        "ix_case_saved_artifacts_idempotency",
        "case_saved_artifacts",
        ["case_uuid", "idempotency_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_case_saved_artifacts_idempotency", table_name="case_saved_artifacts"
    )
    op.drop_index(
        "ix_case_saved_artifacts_case_type", table_name="case_saved_artifacts"
    )
    op.drop_index(
        op.f("ix_case_saved_artifacts_case_uuid"), table_name="case_saved_artifacts"
    )
    op.drop_index(
        op.f("ix_case_saved_artifacts_artifact_uuid"),
        table_name="case_saved_artifacts",
    )
    op.drop_table("case_saved_artifacts")

    op.drop_index(
        "ix_case_form_draft_records_idempotency",
        table_name="case_form_draft_records",
    )
    op.drop_column("case_form_draft_records", "idempotency_key")
    op.drop_column("case_form_draft_records", "pdf_asset_uuid")
    op.drop_column("case_form_draft_records", "printed_at")
    op.drop_column("case_form_draft_records", "saved_by")
    op.drop_column("case_form_draft_records", "is_official")
    op.drop_column("case_form_draft_records", "content_snapshot")
    op.drop_column("case_form_draft_records", "field_values")
    op.drop_column("case_form_draft_records", "template_version")
