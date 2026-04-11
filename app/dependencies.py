"""FastAPI dependencies for auth and club resolution."""

from datetime import date

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth_utils import get_session_user_id
from app.database import get_db
from app.models import BookClub, User


async def get_club(club_slug: str, db: AsyncSession = Depends(get_db)) -> BookClub:
    result = await db.execute(select(BookClub).where(BookClub.slug == club_slug))
    club = result.scalar_one_or_none()
    if club is None:
        raise HTTPException(status_code=404, detail="Book club not found")
    return club


async def get_current_user(
    request: Request,
    club: BookClub = Depends(get_club),
    db: AsyncSession = Depends(get_db),
) -> User:
    user_id = get_session_user_id(request)
    if user_id is None:
        raise HTTPException(status_code=302, headers={"Location": f"/{club.slug}/auth/login"})
    result = await db.execute(
        select(User).where(User.id == user_id, User.club_id == club.id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=302, headers={"Location": f"/{club.slug}/auth/login"})
    # Update last_active
    today = date.today()
    if user.last_active != today:
        user.last_active = today
        await db.commit()
    return user


async def get_admin_user(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
