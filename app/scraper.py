"""Goodreads scraper. Returns partial results on failure; never raises."""

import re
from dataclasses import dataclass


def canonicalize_goodreads_url(url: str) -> str | None:
    """Strip slug after the numeric ID: /book/show/123456.Title -> /book/show/123456"""
    if not url:
        return None
    url = url.strip()
    m = re.search(r"goodreads\.com/book/show/(\d+)", url)
    if m:
        return f"https://www.goodreads.com/book/show/{m.group(1)}"
    return url


def canonicalize_author_url(url: str) -> str | None:
    """Strip slug after the numeric ID: /author/show/123456.Name -> /author/show/123456"""
    if not url:
        return None
    url = url.strip()
    m = re.search(r"goodreads\.com/author/show/(\d+)", url)
    if m:
        return f"https://www.goodreads.com/author/show/{m.group(1)}"
    return url

import httpx
from bs4 import BeautifulSoup


@dataclass
class BookData:
    title: str | None = None
    author: str | None = None
    author_url: str | None = None
    page_count: int | None = None
    error: str | None = None
    blocked: bool = False  # True if Goodreads' bot protection challenged the request


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

    # AWS WAF Bot Control challenges suspicious traffic with a 202 and an
    # empty body instead of serving the page. A plain HTTP client can't
    # solve the challenge, so this is a distinct condition from a parsing
    # failure — retrying immediately won't help.
    if r.headers.get("x-amzn-waf-action") == "challenge" or (r.status_code == 202 and not r.text):
        return BookData(blocked=True, error="Blocked by Goodreads' bot protection — wait before retrying.")

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
        # The name is usually wrapped in (or, in the legacy layout, itself is)
        # a link to the author's Goodreads page.
        author_link = author_tag if author_tag.name == "a" else author_tag.find_parent("a")
        if author_link and author_link.get("href"):
            data.author_url = canonicalize_author_url(author_link["href"])

    # Page count — look for "X pages" pattern
    pages_tag = soup.find("p", {"data-testid": "pagesFormat"})
    if pages_tag:
        m = re.search(r"(\d+)\s*pages", pages_tag.get_text())
        if m:
            data.page_count = int(m.group(1))

    if not any([data.title, data.author, data.page_count]):
        data.error = "Could not extract book data. Goodreads may have changed their layout."

    return data
