"""Revision ID: a1b2c3d4e5f6
Revises: 2d6d4a6b4613
Create Date: 2026-06-30

Add grievance case, message, and report version tables.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "2d6d4a6b4613"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "grievance_cases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_uuid", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("user_name", sa.String(length=255), nullable=True),
        sa.Column("local_number", sa.String(length=100), nullable=True),
        sa.Column("initial_question", sa.Text(), nullable=False),
        sa.Column("known_facts", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_grievance_cases_id"),
        "grievance_cases",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_grievance_cases_case_uuid"),
        "grievance_cases",
        ["case_uuid"],
        unique=True,
    )

    op.create_table(
        "case_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("message_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["grievance_cases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_case_messages_id"),
        "case_messages",
        ["id"],
        unique=False,
    )

    op.create_table(
        "case_report_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("trigger_message_id", sa.Integer(), nullable=True),
        sa.Column("report_data", sa.JSON(), nullable=False),
        sa.Column("ranked_authorities", sa.JSON(), nullable=True),
        sa.Column("issue_analysis", sa.JSON(), nullable=True),
        sa.Column("evidence_items", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["grievance_cases.id"]),
        sa.ForeignKeyConstraint(["trigger_message_id"], ["case_messages.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_case_report_versions_id"),
        "case_report_versions",
        ["id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_case_report_versions_id"), table_name="case_report_versions")
    op.drop_table("case_report_versions")
    op.drop_index(op.f("ix_case_messages_id"), table_name="case_messages")
    op.drop_table("case_messages")
    op.drop_index(op.f("ix_grievance_cases_case_uuid"), table_name="grievance_cases")
    op.drop_index(op.f("ix_grievance_cases_id"), table_name="grievance_cases")
    op.drop_table("grievance_cases")
