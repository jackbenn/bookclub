import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.auth_utils import consume_magic_token, consume_otp, issue_magic_token
from app.models import Base, BookClub, MagicToken, User


async def _issue(expired: bool = False) -> tuple[async_sessionmaker, int, str, str]:
    """
    Set up a club with one user, issue a login token for them, and return
    (sessionmaker, club_id, signed_token, otp). Reading the token back in a
    fresh session matters: SQLite returns its timestamps naive.
    """
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as db:
        club = BookClub(slug="test", display_name="Test")
        db.add(club)
        await db.flush()
        user = User(email="a@example.com", display_name="A", club_id=club.id)
        db.add(user)
        await db.flush()
        token, otp = await issue_magic_token(user, db)
        if expired:
            past = datetime.now(timezone.utc) - timedelta(minutes=1)
            await db.execute(update(MagicToken).values(expires_at=past))
            await db.commit()
    return Session, club.id, token, otp


def test_otp_logs_in():
    async def run():
        Session, club_id, _, otp = await _issue()
        async with Session() as db:
            return await consume_otp("a@example.com", club_id, otp, db)

    assert asyncio.run(run()).email == "a@example.com"


def test_magic_link_logs_in():
    async def run():
        Session, _, token, _ = await _issue()
        async with Session() as db:
            return await consume_magic_token(token, db)

    assert asyncio.run(run()).email == "a@example.com"


def test_expired_otp_is_rejected():
    async def run():
        Session, club_id, _, otp = await _issue(expired=True)
        async with Session() as db:
            return await consume_otp("a@example.com", club_id, otp, db)

    assert asyncio.run(run()) is None
