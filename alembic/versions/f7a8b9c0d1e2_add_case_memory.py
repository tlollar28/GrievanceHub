"""Add first-class case_memories table.

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-07-17

Durable Case Memory is the permanent structured understanding of a case.
It is updated by meaningful interactions and restored before AI continuity.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, Sequence[str], None] = "e6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "case_memories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("case_uuid", sa.String(length=36), nullable=False),
        sa.Column("schema_version", sa.String(length=40), nullable=False),
        sa.Column("memory_json", sa.JSON(), nullable=False),
        sa.Column("reopen_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["grievance_cases.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id"),
        sa.UniqueConstraint("case_uuid"),
    )
    op.create_index("ix_case_memories_case_uuid", "case_memories", ["case_uuid"])
    op.create_index("ix_case_memories_case_id", "case_memories", ["case_id"])


def downgrade() -> None:
    op.drop_index("ix_case_memories_case_id", table_name="case_memories")
    op.drop_index("ix_case_memories_case_uuid", table_name="case_memories")
    op.drop_table("case_memories")
