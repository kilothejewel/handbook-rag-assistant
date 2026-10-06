"""
Unit tests for the website content-cleaning logic (Part 1 / Part 4 of the
rubric).

`clean_html()` is a pure function of a raw HTML string -> no network call
-- which is what makes it fast and deterministic to test here. `fetch_html()`
and `crawl_website()` do real HTTP against zaio.io and are exercised by
actually running `python -m app.ingest`, not by a unit test.

Note: trafilatura's extraction is heuristic (it looks for article-shaped
content), so these fixtures use a realistic <article>/<main> structure
rather than a single bare sentence, to give it enough to recognize as real
content.
"""
from app.web_crawl import clean_html


def test_clean_html_strips_nav_and_footer_but_keeps_body_text():
    html = """
    <html>
      <head><title>Fullstack AI Engineer Bootcamp</title></head>
      <body>
        <nav><a href="/">Home</a><a href="/bootcamps">Bootcamps</a></nav>
        <header>Zaio - Leading Tech Bootcamp</header>
        <main>
          <article>
            <h1>Fullstack AI Engineer Bootcamp</h1>
            <p>The Fullstack AI Engineer bootcamp runs for seven months and
            combines full stack web development with modern AI engineering,
            so graduates can build and ship AI-powered applications.</p>
            <p>Classes are beginner friendly and require no prior coding
            experience before you start the programme.</p>
          </article>
        </main>
        <footer>&copy; 2026 Zaio Technology. +27 21 300 6808</footer>
      </body>
    </html>
    """

    cleaned = clean_html(html)

    assert "Fullstack AI Engineer" in cleaned
    assert "seven months" in cleaned
    assert "Home" not in cleaned
    assert "2026 Zaio Technology" not in cleaned


def test_clean_html_returns_empty_string_for_boilerplate_only_page():
    html = "<html><body><nav>Home</nav><header>Title</header><footer>Copy</footer></body></html>"

    cleaned = clean_html(html)

    assert cleaned == ""
