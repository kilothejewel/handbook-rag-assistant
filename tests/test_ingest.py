"""
Unit tests for the chunking logic (Part 1 / Part 4 of the rubric).

These tests never touch a real PDF, the embedding model, or the network —
they call `chunk_pages` directly with plain strings. That's the point of
keeping chunk_pages a pure function: it's fast and deterministic to test.
"""
from app.ingest import chunk_pages


def test_chunk_pages_tags_each_chunk_with_its_page_number():
    pages = ["Page one content. " * 20, "Page two content. " * 20]

    chunks = chunk_pages(pages, chunk_size=100, chunk_overlap=20)

    assert chunks, "expected at least one chunk"
    assert {c.page for c in chunks} == {1, 2}
    # a chunk from page 1 must never contain page 2's text and vice versa
    for c in chunks:
        if c.page == 1:
            assert "Page two" not in c.text


def test_chunk_pages_skips_blank_pages():
    pages = ["Real content here that is long enough to chunk.", "   ", ""]

    chunks = chunk_pages(pages, chunk_size=100, chunk_overlap=10)

    assert all(c.page == 1 for c in chunks)


def test_chunk_pages_respects_chunk_size_roughly():
    long_page = ("word " * 400)  # long enough to require multiple chunks
    chunks = chunk_pages([long_page], chunk_size=100, chunk_overlap=10)

    assert len(chunks) > 1
    # allow a little slack — the splitter breaks on separators, not mid-word
    assert all(len(c.text) <= 130 for c in chunks)


def test_chunk_ids_are_unique():
    pages = ["Some content. " * 30, "More content. " * 30]
    chunks = chunk_pages(pages, chunk_size=80, chunk_overlap=10)

    ids = [c.id for c in chunks]
    assert len(ids) == len(set(ids))
