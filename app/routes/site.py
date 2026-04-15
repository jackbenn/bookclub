import json
import re

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import BookClub, User
from app.templates_env import templates

router = APIRouter(tags=["site"])

_SLUG_RE = re.compile(r"^[a-z0-9-]+$")


@router.get("/", response_class=HTMLResponse)
async def site_home(request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(BookClub).order_by(BookClub.display_name))
    clubs = result.scalars().all()
    return templates.TemplateResponse("site/home.html", {"request": request, "clubs": clubs})


@router.get("/how-it-works", response_class=HTMLResponse)
async def how_it_works(request: Request):
    return templates.TemplateResponse("site/how_it_works.html", {"request": request})


@router.get("/new-club", response_class=HTMLResponse)
async def new_club_page(request: Request):
    return templates.TemplateResponse("site/new_club.html", {"request": request, "form": {}, "error": None})


@router.post("/new-club", response_class=HTMLResponse)
async def new_club_submit(
    request: Request,
    display_name: str = Form(...),
    slug: str = Form(...),
    description: str = Form(""),
    allowed_domains_text: str = Form(""),
    allowed_emails_text: str = Form(""),
    admin_email: str = Form(...),
    admin_name: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    form = {
        "display_name": display_name,
        "slug": slug,
        "description": description,
        "allowed_domains_text": allowed_domains_text,
        "allowed_emails_text": allowed_emails_text,
        "admin_email": admin_email,
        "admin_name": admin_name,
    }

    slug = slug.strip().lower()
    if not _SLUG_RE.match(slug):
        return templates.TemplateResponse(
            "site/new_club.html",
            {"request": request, "form": form, "error": "Slug must contain only lowercase letters, numbers, and hyphens."},
            status_code=400,
        )

    existing = await db.execute(select(BookClub).where(BookClub.slug == slug))
    if existing.scalar_one_or_none():
        return templates.TemplateResponse(
            "site/new_club.html",
            {"request": request, "form": form, "error": f'A club with slug "{slug}" already exists.'},
            status_code=400,
        )

    emails = [e.strip().lower() for e in allowed_emails_text.splitlines() if e.strip()]
    domains = [d.strip().lower() for d in allowed_domains_text.splitlines() if d.strip()]

    club = BookClub(
        slug=slug,
        display_name=display_name.strip(),
        description=description.strip() or None,
        allowed_emails=json.dumps(emails),
        allowed_domains=json.dumps(domains),
    )
    db.add(club)
    await db.flush()

    admin = User(
        email=admin_email.strip().lower(),
        display_name=admin_name.strip(),
        club_id=club.id,
        is_admin=True,
    )
    db.add(admin)
    await db.commit()

    return RedirectResponse(url=f"/{slug}/auth/login", status_code=303)
