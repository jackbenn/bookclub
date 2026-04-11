"""Goodreads scraper. Returns partial results on failure; never raises."""

import re
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup


@dataclass
class BookData:
    title: str | None = None
    author: str | None = None
    page_count: int | None = None
    error: str | None = None


async def scrape_goodreads(url: str) -> BookData:
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (compatible; BookClubBot/1.0)"
                )
            }
            r = await client.get(url, headers=headers)
            r.raise_for_status()
    except Exception as e:
        return BookData(error=f"Could not fetch page: {e}")

    soup = BeautifulSoup(r.text, "html.parser")
    data = BookData()

    # Title
    title_tag = soup.find("h1", {"data-testid": "bookTitle"}) or soup.find("h1", class_="Text__title1")
    if title_tag:
        data.title = title_tag.get_text(strip=True)

    # Author
    author_tag = soup.find("span", {"data-testid": "name"}) or soup.find("a", class_="authorName")
    if author_tag:
        data.author = author_tag.get_text(strip=True)

    # Page count — look for "X pages" pattern
    pages_tag = soup.find("p", {"data-testid": "pagesFormat"})
    if pages_tag:
        m = re.search(r"(\d+)\s*pages", pages_tag.get_text())
        if m:
            data.page_count = int(m.group(1))

    if not any([data.title, data.author, data.page_count]):
        data.error = "Could not extract book data. Goodreads may have changed their layout."

    return data
