"""add citations

Revision ID: b1f4c9d2e6a7
Revises: c4a62f1d8b90
Create Date: 2026-08-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b1f4c9d2e6a7"
down_revision: Union[str, Sequence[str], None] = "c4a62f1d8b90"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "citations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("chunk_id", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["message_id"], ["conversation_messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chunk_id"], ["chunks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_citations_message_id"), "citations", ["message_id"], unique=False)
    op.create_index(op.f("ix_citations_chunk_id"), "citations", ["chunk_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_citations_chunk_id"), table_name="citations")
    op.drop_index(op.f("ix_citations_message_id"), table_name="citations")
    op.drop_table("citations")
