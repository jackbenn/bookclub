import json
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dates import compute_meeting_date, compute_voting_close
from app.dependencies import get_admin_user, get_club
from app.models import Book, BookClub, BookStatus, MonthlyResult, MonthlySettings, User
from app.scraper import scrape_goodreads
from app.templates_env import templates
from app.voting import finalize_month

router = APIRouter(prefix="/{club_slug}/admin", tags=["admin"])


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
