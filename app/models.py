from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class BookStatus(str, enum.Enum):
    active = "active"
    selected = "selected"
    historical = "historical"


class BookClub(Base):
    __tablename__ = "book_clubs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    # JSON-encoded lists, e.g. '["alice@example.com"]' and '["example.com"]'
    allowed_emails: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    allowed_domains: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    decay_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.85)
    # "3rd Tuesday" = meeting_week=3, meeting_weekday=1 (Mon=0 … Sun=6)
    meeting_week: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    meeting_weekday: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    voting_close_days_before: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    accent_color: Mapped[str] = mapped_column(String(32), nullable=False, default="amber")

    users: Mapped[list[User]] = relationship("User", back_populates="club")
    books: Mapped[list[Book]] = relationship("Book", back_populates="club")
    monthly_results: Mapped[list[MonthlyResult]] = relationship("MonthlyResult", back_populates="club")
    monthly_settings: Mapped[list[MonthlySettings]] = relationship("MonthlySettings", back_populates="club")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(256), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    club_id: Mapped[int] = mapped_column(ForeignKey("book_clubs.id"), nullable=False)
    last_active: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (UniqueConstraint("email", "club_id"),)

    club: Mapped[BookClub] = relationship("BookClub", back_populates="users")
    approvals: Mapped[list[Approval]] = relationship("Approval", back_populates="user")
    load: Mapped[UserLoad | None] = relationship("UserLoad", back_populates="user", uselist=False)
    magic_tokens: Mapped[list[MagicToken]] = relationship("MagicToken", back_populates="user")


class Book(Base):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    club_id: Mapped[int] = mapped_column(ForeignKey("book_clubs.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    author: Mapped[str] = mapped_column(String(256), nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    goodreads_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Null for historical imports
    nominated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    nominated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[BookStatus] = mapped_column(Enum(BookStatus), nullable=False, default=BookStatus.active)
    # Independently nullable: historical books may have year-only or no date
    selected_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    selected_month: Mapped[int | None] = mapped_column(Integer, nullable=True)

    club: Mapped[BookClub] = relationship("BookClub", back_populates="books")
    nominated_by: Mapped[User | None] = relationship("User")
    approvals: Mapped[list[Approval]] = relationship("Approval", back_populates="book")


class Approval(Base):
    __tablename__ = "approvals"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), primary_key=True)

    user: Mapped[User] = relationship("User", back_populates="approvals")
    book: Mapped[Book] = relationship("Book", back_populates="approvals")


class MonthlyResult(Base):
    __tablename__ = "monthly_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    club_id: Mapped[int] = mapped_column(ForeignKey("book_clubs.id"), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    winning_book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), nullable=False)
    # Comma-separated book IDs for 2nd and 3rd place, e.g. "42,17"
    runner_up_ids: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    finalized_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())

    __table_args__ = (UniqueConstraint("club_id", "year", "month"),)

    club: Mapped[BookClub] = relationship("BookClub", back_populates="monthly_results")
    winning_book: Mapped[Book] = relationship("Book", foreign_keys=[winning_book_id])


class MonthlySettings(Base):
    """Overrides for a specific month: date changes and skips."""

    __tablename__ = "monthly_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    club_id: Mapped[int] = mapped_column(ForeignKey("book_clubs.id"), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    # Null = month is skipped
    meeting_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Null = use club default calculation
    voting_close_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (UniqueConstraint("club_id", "year", "month"),)

    club: Mapped[BookClub] = relationship("BookClub", back_populates="monthly_settings")


class UserLoad(Base):
    __tablename__ = "user_loads"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    club_id: Mapped[int] = mapped_column(ForeignKey("book_clubs.id"), primary_key=True)
    load_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    user: Mapped[User] = relationship("User", back_populates="load")


class MagicToken(Base):
    __tablename__ = "magic_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(256), nullable=False, unique=True)
    otp_code: Mapped[str] = mapped_column(String(8), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped[User] = relationship("User", back_populates="magic_tokens")
