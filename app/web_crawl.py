from __future__ import annotations
import time
import hhtpx
import trafilature 
from app import config

def fetch_and_clean(url: str, timeout: float = 15.0) -> str:
    """Fetch one URL, return its cleaned main-content text (no nav/footer)."""
    response = httpx.get(
        url, timeout=timeout, follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (handbook-rag-assistant coursework bot)"},
    )
    response.raise_for_status()
    cleaned = trafilatura.extract(response.text, include_comments=False, include_tables=False)
    return cleaned or ""


def crawl_website(urls: list[str] = None) -> list[tuple[str, str]]:
    """Fetch every URL, one at a time with a delay. Returns (url, text) pairs;
    a URL that fails or yields nothing extractable is skipped, not included empty."""
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