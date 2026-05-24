import json
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dates import compute_meeting_date, compute_voting_close
from app.dependencies import get_admin_user, get_club
from app.models import Book, BookClub, BookStatus, MonthlyResult, MonthlySettings, User
from app.scraper import scrape_goodreads
from app.templates_env import templates
from app.voting import finalize_month

router = APIRouter(prefix="/{club_slug}/admin", tags=["admin"])


@router.post("/settings")
async def settings_save(
    request: Request,
    club_slug: str,
    display_name: str = Form(...),
    description: str = Form(""),
    allowed_emails_text: str = Form(""),
    allowed_domains_text: str = Form(""),
    accent_color: str = Form("amber"),
    decay_rate: float = Form(...),
    meeting_week: int = Form(...),
    meeting_weekday: int = Form(...),
    voting_close_days_before: int = Form(...),
    club: BookClub = Depends(get_club),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    emails = [e.strip().lower() for e in allowed_emails_text.splitlines() if e.strip()]
    domains = [d.strip().lower() for d in allowed_domains_text.splitlines() if d.strip()]
    club.display_name = display_name.strip()
    club.description = description.strip() or None
    club.allowed_emails = json.dumps(emails)
    club.allowed_domains = json.dumps(domains)
    club.accent_color = accent_color
    club.decay_rate = max(0.0, min(1.0, decay_rate))
    club.meeting_week = max(1, min(5, meeting_week))
    club.meeting_weekday = max(0, min(6, meeting_weekday))
    club.voting_close_days_before = max(0, voting_close_days_before)
    await db.commit()
    return RedirectResponse(url=f"/{club_slug}/admin", status_code=303)


@router.get("", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    club: BookClub = Depends(get_club),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    today = date.today()
    year, month = today.year, today.month

    # Current month settings/override
    settings_result = await db.execute(
        select(MonthlySettings).where(
            MonthlySettings.club_id == club.id,
            MonthlySettings.year == year,
            MonthlySettings.month == month,
        )
    )
    settings = settings_result.scalar_one_or_none()
    meeting_date = compute_meeting_date(club, year, month, settings)
    voting_close = compute_voting_close(club, meeting_date, settings)

    # Already finalized this month?
    result_row = await db.execute(
        select(MonthlyResult).where(
            MonthlyResult.club_id == club.id,
            MonthlyResult.year == year,
            MonthlyResult.month == month,
        )
    )
    already_finalized = result_row.scalar_one_or_none() is not None

    members_result = await db.execute(select(User).where(User.club_id == club.id).order_by(User.display_name))
    members = members_result.scalars().all()

    allowed_emails = json.loads(club.allowed_emails)
    allowed_domains = json.loads(club.allowed_domains)

    return templates.TemplateResponse(
        "admin/dashboard.html",
        {
            "request": request,
            "club": club,
            "admin": admin,
            "year": year,
            "month": month,
            "meeting_date": meeting_date,
            "voting_close": voting_close,
            "already_finalized": already_finalized,
            "is_skipped": settings is not None and settings.meeting_date is None,
            "members": members,
            "allowed_emails_text": "\n".join(allowed_emails),
            "allowed_domains_text": "\n".join(allowed_domains),
            "accent_colors": [
                ("amber", "Amber"),
                ("orange", "Orange"),
                ("rose", "Rose"),
                ("violet", "Violet"),
                ("indigo", "Indigo"),
                ("sky", "Sky"),
                ("teal", "Teal"),
                ("emerald", "Emerald"),
                ("stone", "Stone"),
            ],
        },
    )


@router.post("/finalize")
async def finalize(
    request: Request,
    club_slug: str,
    year: int = Form(...),
    month: int = Form(...),
    club: BookClub = Depends(get_club),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await finalize_month(club, year, month, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return RedirectResponse(url=f"/{club_slug}/results", status_code=303)


@router.post("/skip-month")
async def skip_month(
    request: Request,
    club_slug: str,
    year: int = Form(...),
    month: int = Form(...),
    notes: str = Form(""),
    club: BookClub = Depends(get_club),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(
        select(MonthlySettings).where(
            MonthlySettings.club_id == club.id,
            MonthlySettings.year == year,
            MonthlySettings.month == month,
        )
    )
    row = existing.scalar_one_or_none()
    if row is None:
        row = MonthlySettings(club_id=club.id, year=year, month=month)
        db.add(row)
    row.meeting_date = None  # None = skipped
    row.notes = notes.strip() or None
    await db.commit()
    return RedirectResponse(url=f"/{club_slug}/admin", status_code=303)


@router.post("/set-meeting-date")
async def set_meeting_date(
    request: Request,
    club_slug: str,
    year: int = Form(...),
    month: int = Form(...),
    meeting_date: str = Form(...),
    notes: str = Form(""),
    club: BookClub = Depends(get_club),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        parsed = date.fromisoformat(meeting_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")
    existing = await db.execute(
        select(MonthlySettings).where(
            MonthlySettings.club_id == club.id,
            MonthlySettings.year == year,
            MonthlySettings.month == month,
        )
    )
    row = existing.scalar_one_or_none()
    if row is None:
        row = MonthlySettings(club_id=club.id, year=year, month=month)
        db.add(row)
    row.meeting_date = parsed
    row.notes = notes.strip() or None
    await db.commit()
    return RedirectResponse(url=f"/{club_slug}/admin", status_code=303)


# ── Book management ──────────────────────────────────────────────────────────

@router.get("/books", response_class=HTMLResponse)
async def manage_books(
    request: Request,
    club: BookClub = Depends(get_club),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    # Load all books with nominator and approval count
    books_result = await db.execute(
        select(Book).where(Book.club_id == club.id).order_by(Book.status, Book.nominated_at.nullslast(), Book.title)
    )
    books = books_result.scalars().all()

    # Approval counts
    counts_result = await db.execute(
        select(Approval.book_id, func.count(Approval.user_id).label("n"))
        .where(Approval.book_id.in_([b.id for b in books]))
        .group_by(Approval.book_id)
    )
    approval_counts = {row.book_id: row.n for row in counts_result}

    # Nominator names
    nominator_ids = {b.nominated_by_id for b in books if b.nominated_by_id}
    nominators = {}
    if nominator_ids:
        nom_result = await db.execute(select(User).where(User.id.in_(nominator_ids)))
        nominators = {u.id: u for u in nom_result.scalars()}

    book_data = [
        {
            "book": b,
            "approval_count": approval_counts.get(b.id, 0),
            "nominated_by": nominators.get(b.nominated_by_id),
        }
        for b in books
    ]

    return templates.TemplateResponse(
        "admin/books.html",
        {"request": request, "club": club, "admin": admin, "book_data": book_data},
    )


@router.post("/books/{book_id}/delete")
async def delete_book(
    club_slug: str,
    book_id: int,
    club: BookClub = Depends(get_club),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Book).where(Book.id == book_id, Book.club_id == club.id))
    book = result.scalar_one_or_none()
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")
    # Delete approvals first
    approvals = await db.execute(select(Approval).where(Approval.book_id == book_id))
    for a in approvals.scalars():
        await db.delete(a)
    await db.delete(book)
    await db.commit()
    return RedirectResponse(url=f"/{club_slug}/admin/books", status_code=303)


@router.get("/books/{book_id}/edit", response_class=HTMLResponse)
async def edit_book_page(
    request: Request,
    book_id: int,
    club: BookClub = Depends(get_club),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Book).where(Book.id == book_id, Book.club_id == club.id))
    book = result.scalar_one_or_none()
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")
    return templates.TemplateResponse(
        "admin/edit_book.html", {"request": request, "club": club, "admin": admin, "book": book}
    )


@router.post("/books/{book_id}/edit")
async def edit_book_save(
    club_slug: str,
    book_id: int,
    title: str = Form(...),
    author: str = Form(...),
    page_count: str = Form(""),
    goodreads_url: str = Form(""),
    selected_year: str = Form(""),
    selected_month: str = Form(""),
    club: BookClub = Depends(get_club),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    from app.scraper import canonicalize_goodreads_url
    result = await db.execute(select(Book).where(Book.id == book_id, Book.club_id == club.id))
    book = result.scalar_one_or_none()
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")
    book.title = title.strip()
    book.author = author.strip()
    book.page_count = int(page_count) if page_count.strip().isdigit() else None
    book.goodreads_url = canonicalize_goodreads_url(goodreads_url.strip()) or None
    book.selected_year = int(selected_year) if selected_year.strip().isdigit() else None
    raw_month = int(selected_month) if selected_month.strip().isdigit() else None
    book.selected_month = raw_month if raw_month and 1 <= raw_month <= 12 else None
    await db.commit()
    return RedirectResponse(url=f"/{club_slug}/admin/books", status_code=303)


# ── Historical book entry ────────────────────────────────────────────────────

@router.get("/add-historical", response_class=HTMLResponse)
async def add_historical_page(
    request: Request,
    club: BookClub = Depends(get_club),
    admin: User = Depends(get_admin_user),
):
    return templates.TemplateResponse(
        "admin/add_historical.html", {"request": request, "club": club, "admin": admin}
    )


@router.post("/add-historical/scrape", response_class=HTMLResponse)
async def add_historical_scrape(
    request: Request,
    goodreads_url: str = Form(...),
    club: BookClub = Depends(get_club),
    admin: User = Depends(get_admin_user),
):
    data = await scrape_goodreads(goodreads_url.strip())
    return templates.TemplateResponse(
        "admin/add_historical_confirm.html",
        {"request": request, "club": club, "admin": admin, "goodreads_url": goodreads_url.strip(), "book": data},
    )


@router.post("/add-historical/confirm")
async def add_historical_confirm(
    request: Request,
    club_slug: str,
    title: str = Form(...),
    author: str = Form(...),
    page_count: str = Form(""),
    goodreads_url: str = Form(""),
    selected_year: str = Form(""),
    selected_month: str = Form(""),
    club: BookClub = Depends(get_club),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    pages = int(page_count) if page_count.strip().isdigit() else None
    year = int(selected_year) if selected_year.strip().isdigit() else None
    month = int(selected_month) if selected_month.strip().isdigit() else None
    if month is not None and not (1 <= month <= 12):
        month = None

    book = Book(
        club_id=club.id,
        title=title.strip(),
        author=author.strip(),
        page_count=pages,
        goodreads_url=goodreads_url.strip() or None,
        nominated_by_id=None,
        nominated_at=None,
        status=BookStatus.historical,
        selected_year=year,
        selected_month=month,
    )
    db.add(book)
    await db.commit()
    return RedirectResponse(url=f"/{club_slug}/results", status_code=303)


# ── Member management ────────────────────────────────────────────────────────

@router.post("/members/{user_id}/toggle-admin")
async def toggle_admin(
    request: Request,
    club_slug: str,
    user_id: int,
    club: BookClub = Depends(get_club),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot change your own admin status")
    result = await db.execute(select(User).where(User.id == user_id, User.club_id == club.id))
    target = result.scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=404, detail="Member not found")
    target.is_admin = not target.is_admin
    await db.commit()
    return RedirectResponse(url=f"/{club_slug}/admin", status_code=303)


@router.post("/members/{user_id}/remove")
async def remove_member(
    request: Request,
    club_slug: str,
    user_id: int,
    club: BookClub = Depends(get_club),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot remove yourself")
    result = await db.execute(select(User).where(User.id == user_id, User.club_id == club.id))
    target = result.scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=404, detail="Member not found")
    await db.delete(target)
    await db.commit()
    return RedirectResponse(url=f"/{club_slug}/admin", status_code=303)
