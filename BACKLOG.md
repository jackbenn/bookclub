# Backlog — bookclub

Prefix: BOOK · Next ID: 6 · Schema: v1

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

- **Status:** idea
- **Priority:** P3
- **Size:** quick
- **Depends on:** none
- **Tags:** voting

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
- [ ] A member whose `last_active` is within 60 days of the finalize date gets decay applied
- [ ] A member last active more than 60 days before it does not
- [ ] Docstring at the top of `app/voting.py` and the member-facing help text describe the new window
- [ ] Tests cover both edges

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
