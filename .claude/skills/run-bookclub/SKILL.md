---
name: run-bookclub
description: Run, start, and drive the bookclub web app locally — launch it on a throwaway seeded database, log in without email, click through pages in headless Chromium, take desktop and phone-width screenshots, check for console errors and horizontal overflow, and run the tests. Use when asked to run bookclub, screenshot a page, or check a UI change works in the real app.
---

bookclub is a FastAPI + Jinja/HTMX/Tailwind app. To drive it, start
`.claude/skills/run-bookclub/launch.py`, which serves the app on a fresh
seeded SQLite DB with a test-only login route. Then drive it with
`.claude/skills/run-bookclub/driver.py` (Playwright, headless Chromium).

All paths below are relative to `bookclub/`. Verified on macOS (Python 3.12).

## Setup (once)

A dedicated venv holds the app's dependencies plus Playwright. The Chromium
download is about 95 MB and is cached in `~/Library/Caches/ms-playwright`.

```bash
python3 -m venv ~/.cache/bookclub-run/venv
~/.cache/bookclub-run/venv/bin/pip install -r requirements-dev.txt playwright
~/.cache/bookclub-run/venv/bin/python -m playwright install chromium
```

## Run (agent path)

Start the server in the background and poll until it answers:

```bash
P=~/.cache/bookclub-run/venv/bin/python
$P .claude/skills/run-bookclub/launch.py > ${TMPDIR:-/tmp}/bookclub-run.log 2>&1 &
for i in $(seq 60); do curl -sf -o /dev/null http://127.0.0.1:8765/ && echo up && break; sleep 0.5; done
```

Every start recreates the DB (`$TMPDIR/bookclub-run.db`) with this seed:

| | |
|---|---|
| Club | slug `test`, so pages are at `/test/books`, `/test/results`, `/test/admin`, … |
| Users | `1` Alice (admin), `2` Bob |
| Books | six active nominations, two with no page count; Alice approves *Beloved* and *A Wizard of Earthsea* |
| Results | one finalized month (Aug 2026, *Kindred*) and one historical pick (*Gilead*) |

Logging in: `GET /__login/{user_id}?next=/test/books` sets the session and
redirects. The driver does this for you.

**Smoke-check a page** (optional clicks, then screenshots at 1100px and 375px):

```bash
$P .claude/skills/run-bookclub/driver.py /test/books --click 'th:has-text("Length")' --click 'tr:has-text("Middlemarch") button'
$P .claude/skills/run-bookclub/driver.py /test/results --user 2
```

Output: the final URL and title. For each width, the screenshot path and
the elements that overflow the viewport horizontally (ignoring content
inside `.overflow-x-auto` boxes, which scroll on their own). Last, the
console and page errors. Screenshots go to `$TMPDIR/bookclub-shots/<path>-{desktop,phone}.png`.
**Open and look at them.**

**Custom flows**: import `open_page` and use the Playwright `Page`:

```bash
PYTHONPATH=.claude/skills/run-bookclub $P - <<'EOF'
from driver import open_page
with open_page("/test/books", user=2) as page:
    page.click('th:has-text("Author")')
    print(page.eval_on_selector_all("#books-table tbody tr td:nth-child(2)", "els => els.map(e => e.innerText)"))
EOF
```

**Stop:**

```bash
lsof -ti:8765 -sTCP:LISTEN | xargs kill
```

## Test

```bash
~/.cache/bookclub-run/venv/bin/python -m pytest -q
```

5 tests pass (`tests/test_voting.py`).

## Gotchas

- **Never point a local run at `/data/bookclub.db`.** That path is hard-coded
  in `app/database.py` and `alembic.ini` (it's the production volume in
  Docker). `launch.py` swaps `database.engine`/`SessionLocal` before
  importing the app. Don't run plain `uvicorn app.main:app` locally.
- **Login normally sends email** through Resend (magic link + OTP).
  `launch.py` blanks `RESEND_API_KEY` before `.env` loads (`load_dotenv`
  doesn't override variables that are already set) and you log in with
  `/__login/{id}` instead.
- **Don't drive the nominate-by-URL flow** (`/test/books/nominate` →
  scrape). It sends a live Goodreads request, and CLAUDE.md's Goodreads
  rules apply: one request at a time with real gaps, and stop on a WAF
  challenge. To add a book, POST the form to `/test/books/nominate/confirm`
  instead. It doesn't scrape:
  ```bash
  J=${TMPDIR:-/tmp}/bc-cj; curl -s -c $J -o /dev/null http://127.0.0.1:8765/__login/2
  curl -s -b $J -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:8765/test/books/nominate/confirm \
    -d title=Dune -d author="Frank Herbert" -d page_count=412   # -> 303
  ```
- **The seeded data mutates.** Approve/withdraw clicks persist until the
  next launch, so a second identical `--click` on a button undoes the
  first. Restart `launch.py` for a clean seed.
- **Alice is an admin**, so her nav bar has an extra Admin link. That
  matters for phone-width overflow checks: the nav already overflows 375px
  for everyone (≈395px wide for Bob, ≈465px for Alice), and that's an
  existing issue, not a regression.
- **macOS has no `timeout`**, so poll with the `for … seq` loop above
  rather than `timeout 30 bash -c 'until …'`.

## Troubleshooting

- **`Page.goto: net::ERR_CONNECTION_REFUSED at http://127.0.0.1:8765/__login/…`**:
  the server isn't up yet or has died. Run the poll loop, and check
  `$TMPDIR/bookclub-run.log`.
