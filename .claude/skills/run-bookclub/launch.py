"""Run bookclub locally on a throwaway, seeded SQLite DB, for agents to drive.

    python .claude/skills/run-bookclub/launch.py [--db PATH] [--port 8765]

Run from the bookclub directory. It never touches /data/bookclub.db (the
production path hard-coded in app/database.py), never sends email, and adds
a test-only login route:

    GET /__login/{user_id}?next=/test/books   -> sets the session, redirects

Seed: club slug "test"; user 1 Alice (admin), user 2 Bob; six active books
(two with no page count; Alice approves two); one finalized month and one
historical pick so the Results page has rows. The DB is recreated on every
start.
"""
import argparse
import asyncio
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.getcwd())
# load_dotenv() doesn't override variables that are already set, so this
# keeps a real RESEND_API_KEY in .env from being used to send mail.
os.environ["RESEND_API_KEY"] = ""

parser = argparse.ArgumentParser()
parser.add_argument("--db", default=os.path.join(os.environ.get("TMPDIR", "/tmp"), "bookclub-run.db"))
parser.add_argument("--port", type=int, default=8765)
args = parser.parse_args()

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.database as database

# get_db() looks up SessionLocal at call time, so swapping it here is enough.
database.engine = create_async_engine(f"sqlite+aiosqlite:///{args.db}")
database.SessionLocal = async_sessionmaker(database.engine, expire_on_commit=False)

from fastapi import Request
from fastapi.responses import RedirectResponse

from app.main import app
from app.models import Approval, Base, Book, BookClub, BookStatus, MonthlyResult, User


@app.get("/__login/{user_id}")
async def _test_login(user_id: int, request: Request, next: str = "/test/books"):
    request.session["user_id"] = user_id
    return RedirectResponse(next, status_code=303)

# Must precede the catch-all /{club_slug}/ routes.
app.router.routes.insert(0, app.router.routes.pop())

BOOKS = [
    ("The Dispossessed", "Ursula K. Le Guin", 387),
    ("Beloved", "Toni Morrison", None),
    ("Middlemarch", "George Eliot", 880),
    ("A Wizard of Earthsea", "Ursula K. Le Guin", 183),
    ("The Remains of the Day", "Kazuo Ishiguro", 258),
    ("Piranesi", "Susanna Clarke", None),
]


async def seed():
    if os.path.exists(args.db):
        os.remove(args.db)
    async with database.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with database.SessionLocal() as db:
        club = BookClub(slug="test", display_name="Test Club", allowed_emails="[]",
                        allowed_domains="[]", description="A seeded club for local testing.")
        db.add(club)
        await db.flush()
        alice = User(email="alice@example.com", display_name="Alice", club_id=club.id, is_admin=True)
        bob = User(email="bob@example.com", display_name="Bob", club_id=club.id)
        db.add_all([alice, bob])
        await db.flush()
        start = datetime(2026, 9, 1)
        for i, (title, author, pages) in enumerate(BOOKS):
            book = Book(club_id=club.id, title=title, author=author, page_count=pages,
                        nominated_by_id=alice.id, nominated_at=start + timedelta(days=i),
                        status=BookStatus.active,
                        goodreads_url=f"https://example.com/book/{i}" if i % 2 else None)
            db.add(book)
            await db.flush()
            if i in (1, 3):
                db.add(Approval(user_id=alice.id, book_id=book.id))
        winner = Book(club_id=club.id, title="Kindred", author="Octavia E. Butler", page_count=264,
                      status=BookStatus.selected, selected_year=2026, selected_month=8)
        old = Book(club_id=club.id, title="Gilead", author="Marilynne Robinson",
                   status=BookStatus.historical, selected_year=2025, selected_month=11)
        db.add_all([winner, old])
        await db.flush()
        db.add(MonthlyResult(club_id=club.id, year=2026, month=8, winning_book_id=winner.id))
        await db.commit()


asyncio.run(seed())

import uvicorn

print(f"bookclub: DB {args.db}; log in at http://127.0.0.1:{args.port}/__login/1", flush=True)
uvicorn.run(app, host="127.0.0.1", port=args.port)
