"""add author_goodreads_url to books

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-06

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("books", sa.Column("author_goodreads_url", sa.String(512), nullable=True))


def downgrade() -> None:
    op.drop_column("books", "author_goodreads_url")
