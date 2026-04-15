"""add accent_color to book_clubs

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-13

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("book_clubs", sa.Column("accent_color", sa.String(32), nullable=False, server_default="amber"))


def downgrade() -> None:
    op.drop_column("book_clubs", "accent_color")
