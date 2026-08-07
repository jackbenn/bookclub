"""
Backfill author_goodreads_url for existing books that already have a
goodreads_url but no author link yet (added before that field existed).
Re-scrapes each book's Goodreads page to pull the author link.

Run with: docker compose exec bookclub python3 scripts/backfill_author_links.py
Add --confirm to actually write changes (default is dry-run).
"""

import asyncio
import sys

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Book
from app.scraper import scrape_goodreads


async def main(confirm: bool):
    async with SessionLocal() as db:
        result = await db.execute(
            select(Book)
            .where(Book.goodreads_url.is_not(None), Book.author_goodreads_url.is_(None))
            .order_by(Book.id)
        )
        books = result.scalars().all()

        if not books:
            print("Nothing to backfill.")
        else:
            print(
                f"{'DRY RUN — ' if not confirm else ''}"
                f"{len(books)} book(s) have a Goodreads URL but no author link yet:\n"
            )

            updated = 0
            no_link_found = []
            for book in books:
                data = await scrape_goodreads(book.goodreads_url)
                if data.author_url:
                    print(f"  [{book.id}] {book.title} -> {data.author_url}")
                    if confirm:
                        book.author_goodreads_url = data.author_url
                    updated += 1
                else:
                    print(f"  [{book.id}] {book.title} -> no author link found ({data.error or 'unknown reason'})")
                    no_link_found.append(book)
                await asyncio.sleep(1)  # be polite to Goodreads between requests

            if confirm:
                await db.commit()
                print(f"\nUpdated {updated} book(s).")
            else:
                print(f"\nWould update {updated} book(s). Run with --confirm to write changes.")

            if no_link_found:
                print(f"\n{len(no_link_found)} book(s) had a Goodreads URL but no author link could be scraped:")
                for b in no_link_found:
                    print(f"  [{b.id}] {b.title} by {b.author} ({b.goodreads_url})")

        # Books with no Goodreads URL at all can't be backfilled automatically.
        no_url_result = await db.execute(
            select(Book).where(Book.goodreads_url.is_(None)).order_by(Book.id)
        )
        no_url_books = no_url_result.scalars().all()
        if no_url_books:
            print(
                f"\n{len(no_url_books)} book(s) have no Goodreads URL at all and can't be "
                "backfilled automatically — add an author link by hand via the admin "
                "edit-book page if you want one:"
            )
            for b in no_url_books:
                print(f"  [{b.id}] {b.title} by {b.author}")


if __name__ == "__main__":
    confirm = "--confirm" in sys.argv
    asyncio.run(main(confirm))
