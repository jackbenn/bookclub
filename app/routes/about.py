from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from app.dependencies import get_club, get_current_user
from app.models import BookClub, User
from app.templates_env import templates

router = APIRouter(prefix="/{club_slug}/about", tags=["about"])


@router.get("", response_class=HTMLResponse)
async def about_page(
    request: Request,
    club: BookClub = Depends(get_club),
    user: User = Depends(get_current_user),
):
    return templates.TemplateResponse(
        "about.html",
        {"request": request, "club": club, "user": user},
    )
