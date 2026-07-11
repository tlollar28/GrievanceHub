"""Add case_assets table for Phase W3 Case Asset foundation.

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-07-10

First-class case-owned artifacts: uploaded documents (executable in W3) plus
placeholder categories for generated reports, grievances, exports, and future
attachments.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, Sequence[str], None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "case_assets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("asset_uuid", sa.String(length=36), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("case_uuid", sa.String(length=36), nullable=False),
        sa.Column("asset_category", sa.String(length=50), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("stored_filename", sa.String(length=255), nullable=True),
        sa.Column("stored_path", sa.Text(), nullable=True),
        sa.Column("mime_type", sa.String(length=150), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("sha256", sa.String(length=128), nullable=True),
        sa.Column("uploaded_by", sa.String(length=255), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("parent_asset_uuid", sa.String(length=36), nullable=True),
        sa.Column("report_version_id", sa.Integer(), nullable=True),
        sa.Column("report_version_number", sa.Integer(), nullable=True),
        sa.Column("draft_record_uuid", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="active"),
        sa.Column("asset_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["grievance_cases.id"]),
        sa.ForeignKeyConstraint(["report_version_id"], ["case_report_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_uuid"),
    )
    op.create_index(op.f("ix_case_assets_id"), "case_assets", ["id"], unique=False)
    op.create_index(
        op.f("ix_case_assets_asset_uuid"), "case_assets", ["asset_uuid"], unique=True
    )
    op.create_index(
        op.f("ix_case_assets_case_uuid"), "case_assets", ["case_uuid"], unique=False
    )
    op.create_index(
        op.f("ix_case_assets_asset_category"),
        "case_assets",
        ["asset_category"],
        unique=False,
    )
    op.create_index(
        "ix_case_assets_case_id_category",
        "case_assets",
        ["case_id", "asset_category"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_case_assets_case_id_category", table_name="case_assets")
    op.drop_index(op.f("ix_case_assets_asset_category"), table_name="case_assets")
    op.drop_index(op.f("ix_case_assets_case_uuid"), table_name="case_assets")
    op.drop_index(op.f("ix_case_assets_asset_uuid"), table_name="case_assets")
    op.drop_index(op.f("ix_case_assets_id"), table_name="case_assets")
    op.drop_table("case_assets")
