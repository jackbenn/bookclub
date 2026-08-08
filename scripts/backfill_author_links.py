"""
Backfill author_goodreads_url for existing books that already have a
goodreads_url but no author link yet (added before that field existed).
Re-scrapes each book's Goodreads page to pull the author link.

Requests are spaced out with a randomized delay to avoid tripping
Goodreads' (AWS WAF) bot detection. That's a best-effort mitigation, not
a guarantee — WAF Bot Control can flag traffic on more than just rate.
If it challenges a request, no HTTP client can solve that challenge, so
this script stops immediately rather than burning through the rest of
the list logging the same block as if it were 90 separate parsing
failures. If that happens, wait a while before trying again — there's
no reliable way to know how long the block lasts.

Run with: docker compose exec bookclub python3 scripts/backfill_author_links.py
Add --confirm to actually write changes (default is dry-run).
"""

import asyncio
import random
import sys

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Book
from app.scraper import scrape_goodreads

MIN_DELAY_SECONDS = 4
MAX_DELAY_SECONDS = 9


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
            blocked_at = None
            for i, book in enumerate(books):
                data = await scrape_goodreads(book.goodreads_url)
                if data.blocked:
                    blocked_at = i
                    print(
                        f"\nGoodreads challenged this request (bot protection) after "
                        f"{i} of {len(books)} book(s). Stopping here — retrying "
                        f"immediately won't help. Wait a while before running this again."
                    )
                    break
                if data.author_url:
                    print(f"  [{book.id}] {book.title} -> {data.author_url}")
                    if confirm:
                        book.author_goodreads_url = data.author_url
                    updated += 1
                else:
                    print(f"  [{book.id}] {book.title} -> no author link found ({data.error or 'unknown reason'})")
                    no_link_found.append(book)
                await asyncio.sleep(random.uniform(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS))

            if confirm:
                await db.commit()
                print(f"\nUpdated {updated} book(s).")
            else:
                print(f"\nWould update {updated} book(s). Run with --confirm to write changes.")

            if no_link_found:
                print(f"\n{len(no_link_found)} book(s) had a Goodreads URL but no author link could be scraped:")
                for b in no_link_found:
                    print(f"  [{b.id}] {b.title} by {b.author} ({b.goodreads_url})")

            if blocked_at is not None:
                remaining = books[blocked_at:]
                print(f"\n{len(remaining)} book(s) were never attempted because of the block above:")
                for b in remaining:
                    print(f"  [{b.id}] {b.title}")

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
