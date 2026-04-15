from fastapi import FastAPI, Request, Depends
from starlette.middleware.sessions import SessionMiddleware

from app.config import SECRET_KEY
from app.templates_env import templates
from app.dependencies import get_club, get_current_user
from app.models import BookClub, User
from app.routes import auth, books, voting, results, admin, members, site

app = FastAPI(title="Book Club")

app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=60 * 60 * 24 * 30)

# Site-level routes (/, /how-it-works, /new-club) must be registered first
# so they aren't shadowed by the /{club_slug}/ route below.
app.include_router(site.router)

app.include_router(auth.router)
app.include_router(books.router)
app.include_router(voting.router)
app.include_router(results.router)
app.include_router(admin.router)
app.include_router(members.router)


@app.get("/{club_slug}/")
async def club_home(
    request: Request,
    club: BookClub = Depends(get_club),
    user: User = Depends(get_current_user),
):
    return templates.TemplateResponse("home.html", {"request": request, "club": club, "user": user})
