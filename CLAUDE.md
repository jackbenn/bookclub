# bookclub

A book club management app (FastAPI + SQLite/SQLAlchemy + Jinja2/HTMX/Tailwind). See `README.md` for the one-line pitch; architecture and schema are best read directly from the code (`app/models.py`, `app/routes/`, `app/voting.py`).

## External service etiquette: Goodreads

This app scrapes Goodreads (`app/scraper.py`) for book/author metadata — live during nomination, and in bulk via one-off scripts like `scripts/backfill_author_links.py`. Goodreads sits behind AWS WAF Bot Control, which *challenges* traffic it judges automated rather than just rate-limiting it: a `202` response with an empty body and an `x-amzn-waf-action: challenge` header. No plain HTTP client (this app's scraper, `httpx`, `curl`, etc.) can solve that challenge — retrying immediately does nothing, and it briefly blocked the whole server's outbound IP, including live nomination scraping.

Rules for **any** request to goodreads.com from this project — app code, scripts, or ad hoc debugging (including one-off Bash/`httpx` calls made while investigating something, not just code you commit):

- **Never send more than one Goodreads request in quick succession without a real delay.** Bulk/backfill code must use a randomized multi-second delay between requests — see `scripts/backfill_author_links.py` for the current pattern (4–9s jittered).
- **Never loop several test/diagnostic requests back-to-back when debugging.** A ~90-request burst at 1/sec is exactly what tripped the block last time. Space out manual checks the same way you'd space out scripted ones.
- **Treat a WAF challenge as a hard stop, not a retry signal.** `scrape_goodreads()` returns `BookData(blocked=True, ...)` for this case — check it explicitly and abort/report rather than looping through remaining work as if each failure were an independent parsing error.
- If a block is suspected, wait before sending more requests. There's no reliable way to query how long it lasts; continuing to probe only prolongs it.
