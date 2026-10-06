# Backlog — bookclub

Prefix: BOOK · Next ID: 9 · Schema: v1

Ideas and next steps, one item per `##` section. Not commitments — a running
backlog so things surface again instead of getting lost in old conversations.

## [BOOK-1] Decide whether the voting-close date should be enforced

- **Status:** question
- **Priority:** P3
- **Size:** quick
- **Depends on:** none
- **Tags:** voting, dates, admin

`voting_close_date` (computed in `app/dates.py`, shown on the admin dashboard
and the books list page) is purely informational today — nothing in the app
enforces it. Confirmed by reading the code: members can approve or withdraw
approvals before or after that date, nothing auto-finalizes a month when it
arrives, and there is no scheduled job or cron in the app at all (plain
FastAPI + Uvicorn).

Options, roughly in order of how much they would require building:

1. **Leave it informational.** Status quo — the admin finalizes whenever
   convenient, including picking a book outside the app entirely (as happened
   for the August 2026 meeting, via "Skip this month" plus adding the pick as
   a historical book).
2. **Alert the admin** by email, via the already-integrated Resend, when a
   month's voting-close date arrives, prompting them to check the preview page
   and finalize manually. Needs a scheduler — see BOOK-2.
3. **Auto-finalize** at the voting-close date. Removes the manual step
   entirely, but the club has already shown it sometimes picks books "the usual
   way" outside the app — full automation would need to account for that, or it
   would fight the actual workflow.
4. **Block new approvals and withdrawals** after the close date without
   auto-finalizing. Partial enforcement: gives the date some teeth without
   taking the finalize decision away from the admin.

**Open question, to resolve before building anything:** is "picked outside the
app" a one-off or a regular pattern for this club? That decides whether option
3 makes sense at all, versus 2 or 4.

Resolving this closes the item and opens a new one for whichever option wins.
Option 1 closes it with no follow-on work.

## [BOOK-2] Add a scheduler for time-triggered jobs

- **Status:** idea
- **Priority:** P4
- **Size:** session
- **Depends on:** BOOK-1
- **Tags:** infra, dates

The app has no scheduler or cron of any kind — it is plain FastAPI + Uvicorn.
Anything that has to happen *when a date arrives*, rather than in response to a
request, needs one. This is the shared prerequisite for options 2, 3 and 4 of
BOOK-1; option 1 needs nothing here.

Still an idea rather than ready because the choice in BOOK-1 determines what
this has to support: a single daily check is enough to send an alert or block
approvals, while auto-finalizing wants something more careful about running
exactly once.

### Acceptance criteria
- [ ] A time-triggered job runs without an incoming HTTP request
- [ ] It survives a container restart, and a redeploy does not double-fire it
- [ ] Failures are visible rather than silent

## [BOOK-3] Widen the activity window for load decay to the last 60 days

- **Status:** done
- **Priority:** P3
- **Size:** quick
- **Depends on:** none
- **Tags:** voting
- **Commits:** 468b938

Lengthen how long a member can go without logging in and still have their
voting weight recover. Today it is one month; it should be two (60 days).

The mechanism is the load *decay* in `app/voting.py`: when a month is
finalized, `l_i *= decay_rate` is applied only to members whose `last_active`
falls in that same calendar month (the query around the `# Decay loads for
active members` comment). `last_active` is bumped to today on any
authenticated request in `app/dependencies.py`.

**Window:** within the last 60 days, counted back from the finalize date —
not calendar months. (Decided 2026-10-05.)

The member-facing explanation describes the current rule ("If you show up and
participate each month…") in `app/templates/site/how_it_works.html`, and
`app/templates/about.html` and `app/templates/admin/preview.html` mention
recovery too — check them for wording that would become wrong.

### Acceptance criteria
- [x] A member whose `last_active` is within 60 days of the finalize date gets decay applied
- [x] A member last active more than 60 days before it does not
- [x] Docstring at the top of `app/voting.py` and the member-facing help text describe the new window
- [x] Tests cover both edges

### Notes
- 2026-10-05: implemented. The repo has no test suite, so both edges (60 days
  active, 61 inactive) were checked with a throwaway script against an
  in-memory SQLite DB under Python 3.11. The tests criterion stays open.
- 2026-10-05: added `tests/test_voting.py` (the project's first pytest test),
  covering 0, 35, 60 and 61 days and never-active. Closed.

## [BOOK-4] Turn the Books tab into a sortable table

- **Status:** idea
- **Priority:** P3
- **Size:** session
- **Depends on:** none
- **Tags:** ui, books

Turn the Books tab into a sortable table, similar to the Results tab. The
columns should be Title, Author, Length, and Approval.

The Results tab (`app/templates/results/list.html`) already does this with
`th[data-sort]` headers, `data-*` sort keys on each row, and a small inline
script; Author sorts by surname via `author_sort`. The Books tab
(`app/templates/books/list.html`) is currently a card list showing title,
author (linked to Goodreads when known), page count, and the HTMX approval
button from `books/_approval_button.html`.

Things to decide while building:
- "Approval" is presumably the current member's own approve/withdraw button,
  sorted approved-first — vote totals are private until the month's winner is
  announced, so it can't be a count.
- After clicking the approval button, the HTMX swap updates the cell; the
  row's sort key needs updating too, or the sort will be stale until reload.
- Books with no page count should sort last on Length.
- Check it is usable at phone width.

### Acceptance criteria
- [ ] Books tab renders as a table with Title, Author, Length, Approval columns
- [ ] Each column sorts ascending/descending on header click, with an indicator, matching Results
- [ ] Author sorts by surname
- [ ] Approving or withdrawing from the table still works and the row sorts correctly afterward

## [BOOK-5] Let members leave notes on or discuss books

- **Status:** idea
- **Priority:** P4
- **Size:** multi
- **Depends on:** none
- **Tags:** books, ui

Some sort of way for users to leave notes on books or discuss them. That one
will take some refinement.

Open questions to refine before this can be specified:
- Private notes (for yourself), shared comments, or both?
- On nominated books only (pitching/discussing candidates), on past picks
  (post-meeting discussion), or both?
- Flat comments or threaded replies? Editing and deleting?
- Any notification (email) when someone comments, or just visible on the page?
- Does an admin need to be able to remove comments?

## [BOOK-6] Expand the test suite

- **Status:** idea
- **Priority:** P3
- **Size:** multi
- **Depends on:** none
- **Tags:** test

The project had no tests until BOOK-3 added `tests/test_voting.py`, which
covers only the decay activity window. The harness is minimal: `pytest.ini`
(sets `pythonpath = .`), `requirements-dev.txt` (adds pytest), and tests that
build an in-memory `sqlite+aiosqlite://` database and drive async code with
`asyncio.run` rather than a pytest-asyncio plugin. Run with
`pip install -r requirements-dev.txt && pytest`, on Python 3.11 like the
Dockerfile.

Candidate areas, roughly by risk:
- `app/voting.py` beyond decay: Phragmén scoring and load updates, each
  tiebreaker in order, runners-up, error when nothing has approvals,
  `preview_current_standings` agreeing with `finalize_month`
- `app/auth_utils.py`: magic link and OTP — valid, expired, already used
  (security-sensitive; see commit a4aaae0)
- `app/dates.py`: meeting date and voting-close date, including month and
  year boundaries
- Route-level tests via FastAPI's test client: approval toggle, nomination,
  admin-only routes rejecting non-admins
- `app/scraper.py` parsing against saved HTML fixtures, **never** live
  Goodreads (see CLAUDE.md), including the WAF-challenge `blocked=True` path

Worth deciding along the way: a shared fixture (`tests/conftest.py`) for the
DB setup now duplicated inside `test_voting.py`, and whether to run tests in CI.

## [BOOK-7] Protect club creation

- **Status:** idea
- **Priority:** unknown
- **Size:** unknown
- **Depends on:** none
- **Tags:** security, admin

Anyone can create a club. `POST /new-club` (`app/routes/site.py`) needs no
login, has no rate limit or CAPTCHA, and doesn't verify the admin email before
the club exists. Every new club then appears on the public home page at
bookclub.bennetto.com. On 2026-10-06 production listed a club "frkzuumlsr"
with description "sfwqikguzpixmoujitzlvhjuwiiwpn" — probably a club member
who works in QA testing the form, but a bot could do the same at volume.

Options to weigh (not mutually exclusive):
- Require the admin email to be confirmed (magic link) before the club is
  created or before it is listed
- Stop listing clubs on the home page, or list only ones that opt in
- Require a site-level invite code or approval to create a club
- Rate-limit `POST /new-club` per IP
- An admin way to delete junk clubs, which today means editing the DB by hand

## [BOOK-8] Split the About page into a club part and a general how-it-works part

- **Status:** idea
- **Priority:** unknown
- **Size:** session
- **Depends on:** none
- **Tags:** ui, docs

Split the about page into a club-specific part and a general part explaining
how it works.

Today the club About page (`app/templates/about.html`, served at
`/{club_slug}/about` by `app/routes/about.py`) mixes both. Its "What this is"
section uses `club.description`. Then "The goal of the election system",
"How the vote actually works", "Secrecy and timing" and "Tiebreakers" are
general explanation that's the same for every club.

There is already a site-wide `/how-it-works` page
(`app/templates/site/how_it_works.html`) covering much the same ground in
different words: the problem with simple voting, the balance of debt,
inactive members, tiebreakers, after the pick. The two have drifted apart:
BOOK-3 had to update the 60-day wording in both. Part of this item is
deciding whether the general part *is* that page (with the club About
linking to it), or a shared include rendered in both places, so the
explanation lives once.

Club-specific content worth putting in the club part: the description,
meeting schedule (`meeting_week`/`meeting_weekday`), voting-close timing,
and links to that club's results page.

