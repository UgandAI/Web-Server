"""merge chat histories and add conversation titles

Revision ID: e9f4a6b2c1d0
Revises: d8e2f5a1c3b9, b8a1c2d3e4f5
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "e9f4a6b2c1d0"
down_revision: Union[str, Sequence[str], None] = ("d8e2f5a1c3b9", "b8a1c2d3e4f5")
branch_labels = None
depends_on = None

def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "messages" in tables and "conversation_messages" not in tables:
        op.rename_table("messages", "conversation_messages")
    elif "messages" in tables and "conversation_messages" in tables:
        op.execute(sa.text(
            "INSERT INTO conversation_messages (conversation_id, role, content, created_at) "
            "SELECT conversation_id, role, content, created_at FROM messages"
        ))
        op.drop_table("messages")
    with op.batch_alter_table("conversations") as batch_op:
        batch_op.add_column(sa.Column("title", sa.String(length=120), nullable=False,
                                      server_default="New conversation"))

def downgrade() -> None:
    with op.batch_alter_table("conversations") as batch_op:
        batch_op.drop_column("title")
    op.rename_table("conversation_messages", "messages")
