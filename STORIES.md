# Stories

Feature ideas that have come up but aren't built yet. Not commitments — a
running backlog so they surface again instead of getting lost in old
conversations.

## Automate voting-close-date enforcement

`voting_close_date` (computed in `app/dates.py`, shown on the admin
dashboard and the books list page) is purely informational today —
nothing in the app enforces it. Confirmed by reading the code: members can
approve or withdraw approvals before or after that date, nothing
auto-finalizes a month when it arrives, and there's no scheduled job or
cron in the app at all (plain FastAPI + Uvicorn).

Open question: should something actually happen when that date arrives?
Options, roughly in order of how much they'd require building:

1. **Leave it informational.** Status quo — the admin finalizes whenever
   convenient, including picking a book outside the app entirely (as
   happened for the August 2026 meeting, via "Skip this month" plus
   adding the pick as a historical book).
2. **Alert the admin** (email, via the already-integrated Resend) when a
   month's voting-close date arrives, prompting them to check the preview
   page and finalize manually. Needs a scheduler of some kind — the app
   has none yet, so this is a prerequisite for any of the automated
   options below.
3. **Auto-finalize** at the voting-close date. Removes the manual step
   entirely, but the club has already shown it sometimes picks books "the
   usual way" outside the app — full automation would need to account for
   that, or it'd fight the actual workflow.
4. **Block new approvals/withdrawals** after the close date without
   auto-finalizing — partial enforcement, gives the date some teeth
   without taking the finalize decision away from the admin.

Worth resolving before building anything: is "picked outside the app" a
one-off or a regular pattern for this club? That changes whether option 3
makes sense at all versus 2 or 4.
