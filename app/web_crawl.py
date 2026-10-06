"""
Part 1 — Fetch and clean the ZAIO website pages.

This module is the *offline* half of the website knowledge source, same
role as the PDF-reading half of app/ingest.py plays for the handbook: run
once (and again whenever the site content changes), not on every API
request. Fetching (network) and cleaning (pure text transform) are kept as
separate functions on purpose -- clean_html() can be unit tested with a
plain HTML string and no network call (see tests/test_web_crawl.py), while
fetch_html() is only exercised by actually running `python -m app.ingest`.
"""
from __future__ import annotations

import time

import httpx
import lxml.html
import trafilatura
from lxml.etree import ParserError

from app import config


def fetch_html(url: str, timeout: float = 15.0) -> str:
    """Fetch one URL's raw HTML. Raises on a non-2xx response."""
    response = httpx.get(
        url,
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (handbook-rag-assistant coursework bot)"},
    )
    response.raise_for_status()
    return response.text


def clean_html(html: str) -> str:
    """
    Pull the real body content out of a raw HTML page -- nav, header,
    footer, ads, and boilerplate discarded -- using trafilatura, a library
    built specifically for this ("extract the article/body content, drop
    the chrome"), so there's far less bespoke tag-stripping logic to
    maintain than hand-rolled parsing.

    A pure function of a single string -> no network, no browser, which is
    what makes it fast and deterministic to unit test.

    <nav>/<header>/<footer> are dropped *before* extraction: on a page with
    no real body content, trafilatura falls back to returning whatever text
    it can find, which would be the nav links. (Its favor_precision mode
    avoids that too, but it also drops the FAQ accordions on pages like
    /tuition-financing -- exactly the content students ask about.)
    """
    try:
        doc = lxml.html.fromstring(html)
    except ParserError:
        return ""  # empty or unparseable document
    for element in doc.xpath("//nav | //header | //footer"):
        element.drop_tree()
    stripped = lxml.html.tostring(doc, encoding="unicode")

    cleaned = trafilatura.extract(stripped, include_comments=False, include_tables=False)
    return cleaned or ""


def fetch_and_clean(url: str, timeout: float = 15.0) -> str:
    """Fetch one URL, return its cleaned main-content text (no nav/footer)."""
    return clean_html(fetch_html(url, timeout=timeout))


def crawl_website(urls: list[str] | None = None) -> list[tuple[str, str]]:
    """
    Fetch every URL, one at a time with a polite delay between them -- this
    runs once offline, not on the request path, so there's no reason to
    hammer ZAIO's servers or parallelize it.

    Returns (url, text) pairs; a URL that fails to fetch, or yields nothing
    extractable, is skipped rather than included empty or aborting the
    whole crawl -- one dead link shouldn't block ingesting the other five
    pages.
    """
    urls = urls if urls is not None else config.TARGET_URLS
    pages: list[tuple[str, str]] = []
    for i, url in enumerate(urls):
        try:
            text = fetch_and_clean(url)
        except httpx.HTTPError as exc:
            print(f"  skipping {url}: {exc}")
            continue
        if text.strip():
            pages.append((url, text))
            print(f"  fetched {url} ({len(text)} chars)")
        else:
            print(f"  skipping {url}: no extractable content")
        if i < len(urls) - 1:
            time.sleep(config.CRAWL_DELAY_SECONDS)
    return pages


if __name__ == "__main__":
    for url, text in crawl_website():
        print(f"=== {url} ({len(text)} chars) ===")
        print(text[:300])
        print()
