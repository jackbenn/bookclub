from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_club, get_current_user
from app.models import BookClub, User
from app.templates_env import templates

router = APIRouter(prefix="/{club_slug}/members", tags=["members"])


@router.get("", response_class=HTMLResponse)
async def members_page(
    request: Request,
    club: BookClub = Depends(get_club),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).where(User.club_id == club.id).order_by(User.display_name)
    )
    member_list = result.scalars().all()
    return templates.TemplateResponse(
        "members.html",
        {"request": request, "club": club, "user": user, "members": member_list},
    )
