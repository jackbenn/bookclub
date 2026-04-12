from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth_utils import (
    clear_session,
    consume_magic_token,
    consume_otp,
    is_email_allowed,
    issue_magic_token,
    send_magic_email,
    set_session,
)
from app.database import get_db
from app.dependencies import get_club
from app.models import BookClub, User
from app.templates_env import templates

router = APIRouter(prefix="/{club_slug}/auth", tags=["auth"])


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, club: BookClub = Depends(get_club)):
    return templates.TemplateResponse("auth/login.html", {"request": request, "club": club})


@router.post("/login")
async def login_submit(
    request: Request,
    club_slug: str,
    email: str = Form(...),
    display_name: str = Form(...),
    club: BookClub = Depends(get_club),
    db: AsyncSession = Depends(get_db),
):
    email = email.strip().lower()
    if not is_email_allowed(email, club):
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "club": club, "error": "That email isn't on the member list."},
            status_code=400,
        )
    # Find or create user
    result = await db.execute(
        select(User).where(User.email == email, User.club_id == club.id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        user = User(email=email, display_name=display_name.strip(), club_id=club.id)
        db.add(user)
        await db.flush()  # get user.id

    token, otp = await issue_magic_token(user, db)
    await send_magic_email(email, user.display_name, club_slug, token, otp)

    return RedirectResponse(
        url=f"/{club_slug}/auth/verify-prompt?email={email}", status_code=303
    )


@router.get("/verify-prompt", response_class=HTMLResponse)
async def verify_prompt(request: Request, email: str, club: BookClub = Depends(get_club)):
    return templates.TemplateResponse(
        "auth/verify.html", {"request": request, "club": club, "email": email}
    )


@router.get("/verify")
async def verify_link(
    request: Request,
    club_slug: str,
    token: str,
    club: BookClub = Depends(get_club),
    db: AsyncSession = Depends(get_db),
):
    user = await consume_magic_token(token, db)
    if user is None or user.club_id != club.id:
        return templates.TemplateResponse(
            "auth/verify.html",
            {"request": request, "club": club, "email": "", "error": "Link is invalid or expired."},
        )
    set_session(request, user.id)
    return RedirectResponse(url=f"/{club_slug}/books", status_code=303)


@router.post("/verify")
async def verify_otp(
    request: Request,
    club_slug: str,
    email: str = Form(...),
    otp: str = Form(...),
    club: BookClub = Depends(get_club),
    db: AsyncSession = Depends(get_db),
):
    user = await consume_otp(email.strip().lower(), club.id, otp.strip(), db)
    if user is None:
        return templates.TemplateResponse(
            "auth/verify.html",
            {"request": request, "club": club, "email": email, "error": "Invalid or expired code."},
            status_code=400,
        )
    set_session(request, user.id)
    return RedirectResponse(url=f"/{club_slug}/books", status_code=303)


@router.get("/logout")
async def logout(request: Request, club_slug: str):
    clear_session(request)
    return RedirectResponse(url=f"/{club_slug}/auth/login", status_code=303)
