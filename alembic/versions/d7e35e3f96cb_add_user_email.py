"""add user email

Revision ID: d7e35e3f96cb
Revises: 781affe3eee7
Create Date: 2026-07-25 16:44:19.468201

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd7e35e3f96cb'
down_revision: Union[str, Sequence[str], None] = '781affe3eee7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column("email", sa.String(length=320), nullable=True)
        )
        batch_op.create_unique_constraint("uq_users_email", ["email"])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("uq_users_email", type_="unique")
        batch_op.drop_column("email")
