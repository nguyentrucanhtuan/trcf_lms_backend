"""add lesson video_type

Revision ID: 847a12306f19
Revises: d03ea09c1d75
Create Date: 2026-06-10 19:45:54.672443

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '847a12306f19'
down_revision: Union[str, Sequence[str], None] = 'd03ea09c1d75'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Existing rows get 'auto' (detect provider from URL) via server_default.
    op.add_column(
        "lesson",
        sa.Column(
            "video_type",
            sa.String(length=20),
            nullable=False,
            server_default="auto",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("lesson") as batch_op:
        batch_op.drop_column("video_type")
