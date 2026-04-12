from fastapi import FastAPI, Request
from starlette.middleware.sessions import SessionMiddleware

from app.config import SECRET_KEY
from app.templates_env import templates
from app.routes import auth, books, voting, results, admin

app = FastAPI(title="Book Club")

app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=60 * 60 * 24 * 30)

app.include_router(auth.router)
app.include_router(books.router)
app.include_router(voting.router)
app.include_router(results.router)
app.include_router(admin.router)


@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
