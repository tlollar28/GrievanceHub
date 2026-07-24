"""Add W5 source processing provenance metadata.

Revision ID: h9c0d1e2f3a4
Revises: g8b9c0d1e2f3
Create Date: 2026-07-23

Adds SourceDocument lifecycle fields (status, timestamps, SHA, strategy)
and SourceChunk.chunk_metadata so ingestion is auditable and retryable.
Existing source_documents rows receive processing_status='pending'.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h9c0d1e2f3a4"
down_revision: Union[str, Sequence[str], None] = "g8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "source_documents",
        sa.Column("version", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "source_documents",
        sa.Column("document_metadata", sa.JSON(), nullable=True),
    )
    op.add_column(
        "source_documents",
        sa.Column("processing_strategy", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "source_documents",
        sa.Column(
            "processing_status",
            sa.String(length=40),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "source_documents",
        sa.Column("processed_sha256", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "source_documents",
        sa.Column("processed_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "source_documents",
        sa.Column("processing_error", sa.Text(), nullable=True),
    )
    op.create_index(
        op.f("ix_source_documents_processing_status"),
        "source_documents",
        ["processing_status"],
        unique=False,
    )

    op.add_column(
        "source_chunks",
        sa.Column("chunk_metadata", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("source_chunks", "chunk_metadata")

    op.drop_index(
        op.f("ix_source_documents_processing_status"),
        table_name="source_documents",
    )
    op.drop_column("source_documents", "processing_error")
    op.drop_column("source_documents", "processed_at")
    op.drop_column("source_documents", "processed_sha256")
    op.drop_column("source_documents", "processing_status")
    op.drop_column("source_documents", "processing_strategy")
    op.drop_column("source_documents", "document_metadata")
    op.drop_column("source_documents", "version")
