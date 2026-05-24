"""add password_changed_at and token_version to user

Revision ID: d03ea09c1d75
Revises: 1f1873b73dd4
Create Date: 2026-05-24 22:48:24.027423

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'd03ea09c1d75'
down_revision: Union[str, Sequence[str], None] = '1f1873b73dd4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("user") as batch_op:
        batch_op.add_column(sa.Column("password_changed_at", sa.DateTime(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "token_version",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_column("token_version")
        batch_op.drop_column("password_changed_at")
