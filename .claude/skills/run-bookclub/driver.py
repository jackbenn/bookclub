"""Drive a running launch.py instance in headless Chromium.

CLI (smoke check of one page):

    python .claude/skills/run-bookclub/driver.py /test/books [--user 1] [--click 'th:has-text("Author")'] ...

Loads the page logged in as --user and applies each --click in order
(waiting for any HTMX request to settle). Then, at desktop (1100px) and
phone (375px) width, it saves a screenshot and prints the elements that
overflow the viewport horizontally. Last, it prints console/page errors.

Library (for flows the CLI can't express):

    from driver import open_page
    with open_page("/test/books") as page:   # Playwright sync Page
        page.click(...)
"""
import argparse
import os
from contextlib import contextmanager

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BOOKCLUB_URL", "http://127.0.0.1:8765")
OUT = os.environ.get("BOOKCLUB_SHOTS", os.path.join(os.environ.get("TMPDIR", "/tmp"), "bookclub-shots"))

OVERFLOW_JS = """() => {
  const vw = document.documentElement.clientWidth, out = [];
  for (const e of document.querySelectorAll('body *')) {
    const r = e.getBoundingClientRect();
    // Content inside an overflow-x-auto box scrolls there, not the page.
    if (r.right > vw + 1 && !e.closest('.overflow-x-auto'))
      out.push(`${e.tagName}.${String(e.className).slice(0, 50)} right=${Math.round(r.right)}`);
  }
  return {scrollWidth: document.documentElement.scrollWidth, viewport: vw, offenders: out.slice(0, 8)};
}"""


@contextmanager
def open_page(path, user=1, width=1100, errors=None):
    """Yield a Page logged in as `user` and showing `path`."""
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": 800})
        if errors is not None:
            page.on("console", lambda m: m.type == "error" and errors.append(m.text))
            page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"{BASE}/__login/{user}?next={path}")
        page.wait_for_load_state("networkidle")
        try:
            yield page
        finally:
            browser.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--user", type=int, default=1)
    ap.add_argument("--click", action="append", default=[], help="Playwright selector; repeatable")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    slug = a.path.strip("/").replace("/", "_") or "root"
    errors = []
    # One session: clicks that change data (approve/withdraw) run once, then
    # the same page is resized for the phone check.
    with open_page(a.path, a.user, 1100, errors) as page:
        for sel in a.click:
            page.click(sel)
            page.wait_for_load_state("networkidle")
        print(f"url {page.url} title={page.title()!r}")
        for label, width in [("desktop", 1100), ("phone", 375)]:
            page.set_viewport_size({"width": width, "height": 800})
            shot = os.path.join(OUT, f"{slug}-{label}.png")
            page.screenshot(path=shot, full_page=True)
            print(f"[{label}] screenshot {shot}")
            print(f"[{label}] overflow {page.evaluate(OVERFLOW_JS)}")
    print(f"errors {errors}")


if __name__ == "__main__":
    main()
