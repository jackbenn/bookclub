from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_club, get_current_user
from app.models import Book, BookClub, BookStatus, MonthlyResult, User
from app.templates_env import templates

router = APIRouter(prefix="/{club_slug}/results", tags=["results"])


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

    # Enrich with runner-up book objects
    enriched = []
    for r in system_results:
        runner_ups = []
        if r.runner_up_ids:
            ids = [int(i) for i in r.runner_up_ids.split(",") if i]
            if ids:
                ru_result = await db.execute(select(Book).where(Book.id.in_(ids)))
                ru_books = {b.id: b for b in ru_result.scalars()}
                runner_ups = [ru_books[i] for i in ids if i in ru_books]
        enriched.append({"result": r, "runner_ups": runner_ups})

    # Historical books (pre-system): selected + historical status
    hist_result = await db.execute(
        select(Book).where(
            Book.club_id == club.id,
            Book.status.in_([BookStatus.selected, BookStatus.historical]),
            # Exclude books already covered by MonthlyResult
            Book.id.not_in([r["result"].winning_book_id for r in enriched]),
        ).order_by(
            Book.selected_year.desc().nullslast(),
            Book.selected_month.desc().nullslast(),
        )
    )
    historical = hist_result.scalars().all()

    return templates.TemplateResponse(
        "results/list.html",
        {
            "request": request,
            "club": club,
            "user": user,
            "system_results": enriched,
            "historical": historical,
        },
    )
