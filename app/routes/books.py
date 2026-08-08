from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dates import find_next_actionable_month
from app.dependencies import get_club, get_current_user
from app.models import Approval, Book, BookClub, BookStatus, User
from app.scraper import canonicalize_author_url, canonicalize_goodreads_url, scrape_goodreads
from sqlalchemy import func
from app.templates_env import templates

router = APIRouter(prefix="/{club_slug}/books", tags=["books"])


@router.get("", response_class=HTMLResponse)
async def book_list(
    request: Request,
    club: BookClub = Depends(get_club),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Book).where(Book.club_id == club.id, Book.status == BookStatus.active)
        .order_by(Book.nominated_at)
    )
    books = result.scalars().all()

    approval_result = await db.execute(
        select(Approval.book_id).where(Approval.user_id == user.id)
    )
    approved_ids = {row for row in approval_result.scalars()}

    _year, _month, meeting_date, voting_close = await find_next_actionable_month(club, db)

    return templates.TemplateResponse(
        "books/list.html",
        {
            "request": request,
            "club": club,
            "user": user,
            "books": books,
            "approved_ids": approved_ids,
            "meeting_date": meeting_date,
            "voting_close": voting_close,
        },
    )


async def _find_duplicate(club_id: int, goodreads_url: str | None, title: str, db: AsyncSession) -> Book | None:
    """Return an existing book if one matches by canonical URL or title."""
    canonical = canonicalize_goodreads_url(goodreads_url) if goodreads_url else None
    if canonical:
        result = await db.execute(
            select(Book).where(Book.club_id == club_id, Book.goodreads_url == canonical)
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing
    result = await db.execute(
        select(Book).where(
            Book.club_id == club_id,
            func.lower(Book.title) == title.strip().lower(),
        )
    )
    return result.scalar_one_or_none()


def _duplicate_message(book: Book) -> str:
    if book.status == BookStatus.active:
        return f'"{book.title}" is already nominated.'
    elif book.status == BookStatus.selected:
        return f'"{book.title}" was already selected as a past winner.'
    else:
        return f'"{book.title}" is already in the club\'s history.'


@router.get("/nominate", response_class=HTMLResponse)
async def nominate_page(
    request: Request,
    club: BookClub = Depends(get_club),
    user: User = Depends(get_current_user),
):
    return templates.TemplateResponse("books/nominate.html", {"request": request, "club": club, "user": user})


@router.post("/nominate/scrape", response_class=HTMLResponse)
async def nominate_scrape(
    request: Request,
    goodreads_url: str = Form(...),
    club: BookClub = Depends(get_club),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    canonical = canonicalize_goodreads_url(goodreads_url.strip())
    duplicate = await _find_duplicate(club.id, canonical, "", db) if canonical else None

    # Check by URL only at scrape step (title not known yet)
    if duplicate:
        return templates.TemplateResponse(
            "books/nominate.html",
            {"request": request, "club": club, "user": user, "error": _duplicate_message(duplicate)},
            status_code=400,
        )

    data = await scrape_goodreads(canonical or goodreads_url.strip())
    return templates.TemplateResponse(
        "books/nominate_confirm.html",
        {
            "request": request,
            "club": club,
            "user": user,
            "goodreads_url": canonical or goodreads_url.strip(),
            "book": data,
        },
    )


@router.post("/nominate/confirm")
async def nominate_confirm(
    request: Request,
    club_slug: str,
    title: str = Form(...),
    author: str = Form(...),
    page_count: str = Form(""),
    goodreads_url: str = Form(""),
    author_goodreads_url: str = Form(""),
    club: BookClub = Depends(get_club),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    canonical = canonicalize_goodreads_url(goodreads_url) if goodreads_url else None
    duplicate = await _find_duplicate(club.id, canonical, title, db)
    if duplicate:
        return templates.TemplateResponse(
            "books/nominate_confirm.html",
            {
                "request": request,
                "club": club,
                "user": user,
                "goodreads_url": canonical or goodreads_url,
                "book": type("B", (), {
                    "title": title, "author": author, "page_count": page_count,
                    "author_url": author_goodreads_url, "error": None, "blocked": False,
                })(),
                "error": _duplicate_message(duplicate),
            },
            status_code=400,
        )

    pages = int(page_count) if str(page_count).strip().isdigit() else None
    book = Book(
        club_id=club.id,
        title=title.strip(),
        author=author.strip(),
        page_count=pages,
        goodreads_url=canonical or None,
        author_goodreads_url=canonicalize_author_url(author_goodreads_url) if author_goodreads_url else None,
        nominated_by_id=user.id,
        nominated_at=datetime.now(timezone.utc),
        status=BookStatus.active,
    )
    db.add(book)
    await db.flush()
    db.add(Approval(user_id=user.id, book_id=book.id))
    await db.commit()
    return RedirectResponse(url=f"/{club_slug}/books", status_code=303)


@router.post("/{book_id}/approve", response_class=HTMLResponse)
async def approve_book(
    request: Request,
    book_id: int,
    club: BookClub = Depends(get_club),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    book = await _get_active_book(book_id, club.id, db)
    existing = await db.execute(
        select(Approval).where(Approval.user_id == user.id, Approval.book_id == book_id)
    )
    if existing.scalar_one_or_none() is None:
        db.add(Approval(user_id=user.id, book_id=book_id))
        await db.commit()
    # Return updated button fragment for HTMX
    return templates.TemplateResponse(
        "books/_approval_button.html",
        {"request": request, "club": club, "book": book, "approved": True},
    )


@router.post("/{book_id}/withdraw", response_class=HTMLResponse)
async def withdraw_approval(
    request: Request,
    book_id: int,
    club: BookClub = Depends(get_club),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    book = await _get_active_book(book_id, club.id, db)
    existing = await db.execute(
        select(Approval).where(Approval.user_id == user.id, Approval.book_id == book_id)
    )
    row = existing.scalar_one_or_none()
    if row is not None:
        await db.delete(row)
        await db.commit()
    return templates.TemplateResponse(
        "books/_approval_button.html",
        {"request": request, "club": club, "book": book, "approved": False},
    )


async def _get_active_book(book_id: int, club_id: int, db: AsyncSession) -> Book:
    result = await db.execute(
        select(Book).where(Book.id == book_id, Book.club_id == club_id, Book.status == BookStatus.active)
    )
    book = result.scalar_one_or_none()
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")
    return book
