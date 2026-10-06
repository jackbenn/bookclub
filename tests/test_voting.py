import asyncio
from datetime import date, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Approval, Base, Book, BookClub, User, UserLoad
from app.voting import ACTIVITY_WINDOW_DAYS, finalize_month


async def _finalize_with_members(last_active_by_name: dict[str, date | None]) -> dict[str, float]:
    """
    Set up a club where each named member starts with load 1.0 and approves
    nothing, finalize the current month, and return each member's new load.
    Since none of them approved the winner, any change is decay alone.
    """
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as db:
        club = BookClub(slug="test", display_name="Test", decay_rate=0.5)
        db.add(club)
        await db.flush()

        users = {}
        for name, last_active in last_active_by_name.items():
            user = User(email=f"{name}@example.com", display_name=name, club_id=club.id,
                        last_active=last_active)
            db.add(user)
            await db.flush()
            db.add(UserLoad(user_id=user.id, club_id=club.id, load_value=1.0))
            users[name] = user

        # finalize_month needs at least one approved book
        book = Book(club_id=club.id, title="Book", author="Author")
        voter = User(email="voter@example.com", display_name="voter", club_id=club.id)
        db.add_all([book, voter])
        await db.flush()
        db.add(Approval(user_id=voter.id, book_id=book.id))
        await db.commit()

        today = date.today()
        await finalize_month(club, today.year, today.month, db)
        await db.commit()

        result = await db.execute(select(UserLoad))
        loads = {row.user_id: row.load_value for row in result.scalars()}

    await engine.dispose()
    return {name: loads[user.id] for name, user in users.items()}


@pytest.mark.parametrize(
    ("days_ago", "decayed"),
    [
        (0, True),
        (35, True),  # previous calendar month: inactive under the old rule
        (ACTIVITY_WINDOW_DAYS, True),
        (ACTIVITY_WINDOW_DAYS + 1, False),
        (None, False),  # never logged in
    ],
)
def test_decay_applies_within_activity_window(days_ago, decayed):
    last_active = None if days_ago is None else date.today() - timedelta(days=days_ago)
    loads = asyncio.run(_finalize_with_members({"member": last_active}))
    assert loads["member"] == (0.5 if decayed else 1.0)
