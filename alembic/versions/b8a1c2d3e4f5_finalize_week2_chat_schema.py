"""finalize Week 2 chat schema

Revision ID: b8a1c2d3e4f5
Revises: 9c3f1d2a4b5e
"""
from typing import Sequence, Union
from alembic import op

revision: str = "b8a1c2d3e4f5"
down_revision: Union[str, Sequence[str], None] = "9c3f1d2a4b5e"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.rename_table("conversation_messages", "messages")
    with op.batch_alter_table("conversations") as batch_op:
        batch_op.drop_constraint("uq_conversations_user_id", type_="unique")

def downgrade() -> None:
    with op.batch_alter_table("conversations") as batch_op:
        batch_op.create_unique_constraint("uq_conversations_user_id", ["user_id"])
    op.rename_table("messages", "conversation_messages")
