"""
Remove duplicate books within each club, keeping the earliest-nominated copy.
Duplicates are matched first by canonical Goodreads URL, then by lowercase title.
All linked approvals are deleted before the book rows.

Run with: docker compose exec bookclub python3 scripts/dedup_books.py
Add --confirm to actually delete (default is dry-run).
"""

import asyncio
import sys

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Approval, Book
from app.scraper import canonicalize_goodreads_url


async def find_duplicates(db):
    result = await db.execute(select(Book).order_by(Book.id))
    books = result.scalars().all()

    # Group by (club_id, canonical_url) then (club_id, lower_title)
    seen: dict[tuple, Book] = {}   # key -> book to keep
    dupes: list[Book] = []

    for book in books:
        url_key = None
        if book.goodreads_url:
            canonical = canonicalize_goodreads_url(book.goodreads_url)
            if canonical:
                url_key = (book.club_id, "url", canonical)

        title_key = (book.club_id, "title", book.title.strip().lower())

        matched_key = None
        if url_key and url_key in seen:
            matched_key = url_key
        elif title_key in seen:
            matched_key = title_key

        if matched_key:
            dupes.append(book)
        else:
            # Register under both keys so either can match future dupes
            if url_key:
                seen[url_key] = book
            seen[title_key] = book

    return dupes


async def main(confirm: bool):
    async with SessionLocal() as db:
        dupes = await find_duplicates(db)

        if not dupes:
            print("No duplicates found.")
            return

        print(f"{'DRY RUN — ' if not confirm else ''}Found {len(dupes)} duplicate book(s) to remove:\n")
        for book in dupes:
            print(f"  [{book.id}] {book.title} by {book.author}  (status={book.status.value}, url={book.goodreads_url})")

        if not confirm:
            print("\nRun with --confirm to delete these rows.")
            return

        print("\nDeleting...")
        for book in dupes:
            # Delete linked approvals first
            approval_result = await db.execute(
                select(Approval).where(Approval.book_id == book.id)
            )
            approvals = approval_result.scalars().all()
            for approval in approvals:
                await db.delete(approval)
            await db.delete(book)
            print(f"  Deleted [{book.id}] {book.title} and {len(approvals)} approval(s)")

        await db.commit()
        print("\nDone.")


if __name__ == "__main__":
    confirm = "--confirm" in sys.argv
    asyncio.run(main(confirm))
