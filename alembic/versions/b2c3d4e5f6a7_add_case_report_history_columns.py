"""Add report history columns to case_report_versions.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "case_report_versions",
        sa.Column("retrieval_gaps", sa.JSON(), nullable=True),
    )
    op.add_column(
        "case_report_versions",
        sa.Column("source_coverage_audit", sa.JSON(), nullable=True),
    )
    op.add_column(
        "case_report_versions",
        sa.Column("report_summary", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("case_report_versions", "report_summary")
    op.drop_column("case_report_versions", "source_coverage_audit")
    op.drop_column("case_report_versions", "retrieval_gaps")
