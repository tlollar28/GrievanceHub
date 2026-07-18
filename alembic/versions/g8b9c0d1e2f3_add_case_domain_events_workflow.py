"""Add case_domain_events and Case Memory workflow_state column.

Revision ID: g8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-07-17

Internal domain events drive modular Case Memory updates synchronously.
workflow_state mirrors the explicit grievance workflow FSM for restore.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "g8b9c0d1e2f3"
down_revision: Union[str, Sequence[str], None] = "f7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "case_memories",
        sa.Column("workflow_state", sa.String(length=80), nullable=True),
    )
    op.create_index(
        "ix_case_memories_workflow_state",
        "case_memories",
        ["workflow_state"],
    )

    op.create_table(
        "case_domain_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("case_uuid", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("actor_id", sa.String(length=255), nullable=True),
        sa.Column("grievance_step", sa.String(length=50), nullable=True),
        sa.Column("source_type", sa.String(length=80), nullable=True),
        sa.Column("source_uuid", sa.String(length=36), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=160), nullable=True),
        sa.Column(
            "schema_version",
            sa.String(length=40),
            nullable=False,
            server_default="case_domain_event_v1",
        ),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.Column(
            "processing_status",
            sa.String(length=40),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("steward_timeline_event_uuid", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["grievance_cases.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id"),
    )
    op.create_index(
        "ix_case_domain_events_case_uuid", "case_domain_events", ["case_uuid"]
    )
    op.create_index("ix_case_domain_events_case_id", "case_domain_events", ["case_id"])
    op.create_index(
        "ix_case_domain_events_event_type", "case_domain_events", ["event_type"]
    )
    op.create_index(
        "ix_case_domain_events_occurred_at", "case_domain_events", ["occurred_at"]
    )
    op.create_index(
        "ix_case_domain_events_case_idempotency",
        "case_domain_events",
        ["case_uuid", "idempotency_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_case_domain_events_case_idempotency", table_name="case_domain_events"
    )
    op.drop_index("ix_case_domain_events_occurred_at", table_name="case_domain_events")
    op.drop_index("ix_case_domain_events_event_type", table_name="case_domain_events")
    op.drop_index("ix_case_domain_events_case_id", table_name="case_domain_events")
    op.drop_index("ix_case_domain_events_case_uuid", table_name="case_domain_events")
    op.drop_table("case_domain_events")
    op.drop_index("ix_case_memories_workflow_state", table_name="case_memories")
    op.drop_column("case_memories", "workflow_state")
