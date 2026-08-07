from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from nameparser import HumanName
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_club, get_current_user
from app.models import Book, BookClub, BookStatus, MonthlyResult, User
from app.templates_env import templates

router = APIRouter(prefix="/{club_slug}/results", tags=["results"])


def _date_sort_key(year: int | None, month: int | None) -> int:
    """Undated entries sort as the oldest (0)."""
    return (year or 0) * 100 + (month or 0)


def _date_display(year: int | None, month: int | None) -> str:
    if year and month:
        return f"{year}-{month:02d}"
    if year:
        return str(year)
    return "—"


def _author_sort_key(author: str) -> str:
    """Surname-first sort key, e.g. 'Ursula K. Le Guin' -> 'le guin ursula k.'.

    Handles common suffixes (Jr., III) and name-piece prefixes (Le, Van, De)
    via nameparser. Not perfect — e.g. it assumes Western first/last order,
    so an author given surname-first (as is conventional for some Chinese
    names) will sort on the wrong piece — but good enough for a book list,
    and falls back to the raw string if it can't identify a last name.
    """
    name = HumanName(author)
    if not name.last:
        return author.strip().lower()
    return f"{name.last} {name.first} {name.middle}".strip().lower()


@router.get("", response_class=HTMLResponse)
async def results_page(
    request: Request,
    club: BookClub = Depends(get_club),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # System-tracked results
    system_result = await db.execute(
        select(MonthlyResult)
        .where(MonthlyResult.club_id == club.id)
        .options(selectinload(MonthlyResult.winning_book))
        .order_by(MonthlyResult.year.desc(), MonthlyResult.month.desc())
    )
    system_results = system_result.scalars().all()

    rows = []
    winning_book_ids = []
    for r in system_results:
        w = r.winning_book
        winning_book_ids.append(r.winning_book_id)
        runner_ups = []
        if r.runner_up_ids:
            ids = [int(i) for i in r.runner_up_ids.split(",") if i]
            if ids:
                ru_result = await db.execute(select(Book).where(Book.id.in_(ids)))
                ru_books = {b.id: b for b in ru_result.scalars()}
                runner_ups = [ru_books[i] for i in ids if i in ru_books]
        rows.append(
            {
                "date_sort": _date_sort_key(r.year, r.month),
                "date_display": _date_display(r.year, r.month),
                "title": w.title,
                "author": w.author,
                "author_sort": _author_sort_key(w.author),
                "author_goodreads_url": w.author_goodreads_url,
                "goodreads_url": w.goodreads_url,
                "runner_ups": runner_ups,
            }
        )

    # Historical books (pre-system): selected + historical status, not already covered above
    hist_result = await db.execute(
        select(Book).where(
            Book.club_id == club.id,
            Book.status.in_([BookStatus.selected, BookStatus.historical]),
            Book.id.not_in(winning_book_ids),
        )
    )
    for b in hist_result.scalars():
        rows.append(
            {
                "date_sort": _date_sort_key(b.selected_year, b.selected_month),
                "date_display": _date_display(b.selected_year, b.selected_month),
                "title": b.title,
                "author": b.author,
                "author_sort": _author_sort_key(b.author),
                "author_goodreads_url": b.author_goodreads_url,
                "goodreads_url": b.goodreads_url,
                "runner_ups": [],
            }
        )

    rows.sort(key=lambda row: -row["date_sort"])

    return templates.TemplateResponse(
        "results/list.html",
        {
            "request": request,
            "club": club,
            "user": user,
            "rows": rows,
        },
    )
