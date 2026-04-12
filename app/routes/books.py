from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_club, get_current_user
from app.models import Approval, Book, BookClub, BookStatus, User
from app.scraper import scrape_goodreads
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

    # Which books has this user approved?
    approval_result = await db.execute(
        select(Approval.book_id).where(Approval.user_id == user.id)
    )
    approved_ids = {row for row in approval_result.scalars()}

    return templates.TemplateResponse(
        "books/list.html",
        {"request": request, "club": club, "user": user, "books": books, "approved_ids": approved_ids},
    )


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
    club_slug: str,
    goodreads_url: str = Form(...),
    club: BookClub = Depends(get_club),
    user: User = Depends(get_current_user),
):
    """Scrape the Goodreads URL and return a pre-filled confirm form."""
    data = await scrape_goodreads(goodreads_url.strip())
    return templates.TemplateResponse(
        "books/nominate_confirm.html",
        {
            "request": request,
            "club": club,
            "user": user,
            "goodreads_url": goodreads_url.strip(),
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
    club: BookClub = Depends(get_club),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    pages = int(page_count) if page_count.strip().isdigit() else None
    book = Book(
        club_id=club.id,
        title=title.strip(),
        author=author.strip(),
        page_count=pages,
        goodreads_url=goodreads_url.strip() or None,
        nominated_by_id=user.id,
        nominated_at=datetime.now(timezone.utc),
        status=BookStatus.active,
    )
    db.add(book)
    await db.flush()
    # Auto-approve for the nominator
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
