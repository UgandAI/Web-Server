"""add ingestion runs

Revision ID: d8e2f5a1c3b9
Revises: b1f4c9d2e6a7
Create Date: 2026-08-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d8e2f5a1c3b9"
down_revision: Union[str, Sequence[str], None] = "b1f4c9d2e6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("source_directory", sa.String(length=1024), nullable=False),
        sa.Column("files_scanned", sa.Integer(), nullable=False),
        sa.Column("documents_created", sa.Integer(), nullable=False),
        sa.Column("documents_skipped", sa.Integer(), nullable=False),
        sa.Column("chunks_created", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("ingestion_runs")
