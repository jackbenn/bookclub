import asyncio
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.dates
from app.dates import find_next_meeting
from app.models import Base, Book, BookClub, BookStatus, MonthlySettings

# Default schedule is the third Tuesday: 2026-10-20, 2026-11-17, 2026-12-15.


def _next_meeting(today: date, books=(), skipped=(), monkeypatch=None):
    """Run find_next_meeting on a fresh club as of `today`.

    books: (title, status, year, month) picks; skipped: (year, month) skipped in the app.
    Returns (meeting_date, title or None).
    """
    class FakeDate(date):
        @classmethod
        def today(cls):
            return today

    monkeypatch.setattr(app.dates, "date", FakeDate)

    async def run():
        engine = create_async_engine("sqlite+aiosqlite://")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        Session = async_sessionmaker(engine, expire_on_commit=False)
        async with Session() as db:
            club = BookClub(slug="c", display_name="C", allowed_emails="[]", allowed_domains="[]")
            db.add(club)
            await db.flush()
            for title, status, year, month in books:
                db.add(Book(club_id=club.id, title=title, author="X", status=status,
                            selected_year=year, selected_month=month))
            for year, month in skipped:
                db.add(MonthlySettings(club_id=club.id, year=year, month=month, meeting_date=None))
            await db.commit()
            meeting, book = await find_next_meeting(club, db)
        await engine.dispose()
        return meeting, book.title if book else None

    return asyncio.run(run())


def test_no_pick_yet(monkeypatch):
    assert _next_meeting(date(2026, 10, 6), monkeypatch=monkeypatch) == (date(2026, 10, 20), None)


def test_meeting_day_itself_counts(monkeypatch):
    assert _next_meeting(date(2026, 10, 20), monkeypatch=monkeypatch) == (date(2026, 10, 20), None)


def test_after_this_months_meeting_moves_to_next_month(monkeypatch):
    books = [("Kindred", BookStatus.selected, 2026, 10)]
    assert _next_meeting(date(2026, 10, 21), books, monkeypatch=monkeypatch) == (date(2026, 11, 17), None)


def test_finalized_pick_is_returned(monkeypatch):
    books = [("Kindred", BookStatus.selected, 2026, 10), ("Old", BookStatus.selected, 2026, 9)]
    assert _next_meeting(date(2026, 10, 6), books, monkeypatch=monkeypatch) == (date(2026, 10, 20), "Kindred")


def test_skipped_month_is_passed_over(monkeypatch):
    assert _next_meeting(date(2026, 10, 6), skipped=[(2026, 10)], monkeypatch=monkeypatch) == (date(2026, 11, 17), None)


def test_skipped_month_with_outside_pick_still_counts(monkeypatch):
    books = [("Gilead", BookStatus.historical, 2026, 10)]
    got = _next_meeting(date(2026, 10, 6), books, skipped=[(2026, 10)], monkeypatch=monkeypatch)
    assert got == (date(2026, 10, 20), "Gilead")
