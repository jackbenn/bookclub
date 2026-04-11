"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "book_clubs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("slug", sa.String(64), unique=True, nullable=False),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("allowed_emails", sa.Text, nullable=False, server_default="[]"),
        sa.Column("allowed_domains", sa.Text, nullable=False, server_default="[]"),
        sa.Column("decay_rate", sa.Float, nullable=False, server_default="0.85"),
        sa.Column("meeting_week", sa.Integer, nullable=False, server_default="3"),
        sa.Column("meeting_weekday", sa.Integer, nullable=False, server_default="1"),
        sa.Column("voting_close_days_before", sa.Integer, nullable=False, server_default="30"),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(256), nullable=False),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("club_id", sa.Integer, sa.ForeignKey("book_clubs.id"), nullable=False),
        sa.Column("last_active", sa.Date, nullable=True),
        sa.Column("is_admin", sa.Boolean, nullable=False, server_default="0"),
        sa.UniqueConstraint("email", "club_id"),
    )

    op.create_table(
        "books",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("club_id", sa.Integer, sa.ForeignKey("book_clubs.id"), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("author", sa.String(256), nullable=False),
        sa.Column("page_count", sa.Integer, nullable=True),
        sa.Column("goodreads_url", sa.String(512), nullable=True),
        sa.Column("nominated_by_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("nominated_at", sa.DateTime, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("selected_year", sa.Integer, nullable=True),
        sa.Column("selected_month", sa.Integer, nullable=True),
    )

    op.create_table(
        "approvals",
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("book_id", sa.Integer, sa.ForeignKey("books.id"), primary_key=True),
    )

    op.create_table(
        "monthly_results",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("club_id", sa.Integer, sa.ForeignKey("book_clubs.id"), nullable=False),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("month", sa.Integer, nullable=False),
        sa.Column("winning_book_id", sa.Integer, sa.ForeignKey("books.id"), nullable=False),
        sa.Column("runner_up_ids", sa.String(64), nullable=False, server_default=""),
        sa.Column("finalized_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("club_id", "year", "month"),
    )

    op.create_table(
        "monthly_settings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("club_id", sa.Integer, sa.ForeignKey("book_clubs.id"), nullable=False),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("month", sa.Integer, nullable=False),
        sa.Column("meeting_date", sa.Date, nullable=True),
        sa.Column("voting_close_date", sa.Date, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.UniqueConstraint("club_id", "year", "month"),
    )

    op.create_table(
        "user_loads",
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("club_id", sa.Integer, sa.ForeignKey("book_clubs.id"), primary_key=True),
        sa.Column("load_value", sa.Float, nullable=False, server_default="0.0"),
    )

    op.create_table(
        "magic_tokens",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(256), nullable=False, unique=True),
        sa.Column("otp_code", sa.String(8), nullable=False),
        sa.Column("expires_at", sa.DateTime, nullable=False),
        sa.Column("used_at", sa.DateTime, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("magic_tokens")
    op.drop_table("user_loads")
    op.drop_table("monthly_settings")
    op.drop_table("monthly_results")
    op.drop_table("approvals")
    op.drop_table("books")
    op.drop_table("users")
    op.drop_table("book_clubs")
