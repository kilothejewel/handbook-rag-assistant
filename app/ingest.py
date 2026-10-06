"""
Part 1 — Process the handbook and the ZAIO website into one knowledge base.

This module is the *offline* half of the RAG pipeline. It is meant to be run
once (and again any time the handbook PDF or the crawled site content
changes), not on every API request:

    python -m app.ingest

Pipeline: PDF -> per-page text -> overlapping chunks (tagged with their page
number)                                                  \
                                                            -> embeddings -> one persisted Chroma collection
Website  -> crawl + clean six ZAIO pages -> overlapping chunks (tagged      /
            with their URL)

Every chunk carries its own `source_type` ("handbook" or "website") plus
either a page number or a URL, never both -- that's what lets `app/rag.py`
turn a retrieved chunk straight into "Student Handbook - Page 12" or a real
URL later, instead of losing provenance the moment two sources share one
collection.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import chromadb
from chromadb.config import Settings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

from app import config
from app.web_crawl import crawl_website


@dataclass
class Chunk:
    """One retrievable unit, from either the handbook or the website."""
    id: str
    text: str
    source_type: str        # "handbook" or "website"
    page: int | None = None  # 1-indexed handbook page number; None for website chunks
    url: str | None = None   # source URL; None for handbook chunks


def extract_pages(pdf_path) -> list[str]:
    """Return a list of page texts, index 0 == page 1."""
    reader = PdfReader(str(pdf_path))
    pages = []
    for page in reader.pages:
        text = page.extract_text() or ""
        pages.append(text)
    return pages


def chunk_pages(
    pages: list[str],
    chunk_size: int = config.CHUNK_SIZE,
    chunk_overlap: int = config.CHUNK_OVERLAP,
) -> list[Chunk]:
    """
    Split each handbook page's text independently so a chunk never straddles
    a page boundary — that would make citing a single source page ambiguous.

    A pure function of (pages, chunk_size, chunk_overlap) with no file or
    network I/O, which is exactly what makes it easy to unit test.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks: list[Chunk] = []
    for page_number, page_text in enumerate(pages, start=1):
        cleaned = page_text.strip()
        if not cleaned:
            continue  # skip blank pages (cover pages, section dividers, ...)
        for i, piece in enumerate(splitter.split_text(cleaned)):
            chunks.append(
                Chunk(
                    id=f"page{page_number}-chunk{i}",
                    text=piece,
                    source_type="handbook",
                    page=page_number,
                )
            )
    return chunks


def _slugify(url: str) -> str:
    """Turn a URL into a short, readable, filesystem/ID-safe token."""
    slug = re.sub(r"^https?://", "", url)
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", slug).strip("-").lower()
    return slug or "page"


def chunk_website_pages(
    pages: list[tuple[str, str]],
    chunk_size: int = config.CHUNK_SIZE,
    chunk_overlap: int = config.CHUNK_OVERLAP,
) -> list[Chunk]:
    """
    Split each crawled page's cleaned text independently. Reuses the exact
    same splitter config as `chunk_pages()` so chunking behavior is
    identical across sources -- no second chunking strategy to maintain.

    `pages` is a list of (url, cleaned_text) pairs, as returned by
    `app.web_crawl.crawl_website()`.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks: list[Chunk] = []
    for url, page_text in pages:
        cleaned = page_text.strip()
        if not cleaned:
            continue  # a page that crawled but cleaned down to nothing
        slug = _slugify(url)
        for i, piece in enumerate(splitter.split_text(cleaned)):
            chunks.append(
                Chunk(
                    id=f"web-{slug}-chunk{i}",
                    text=piece,
                    source_type="website",
                    url=url,
                )
            )
    return chunks


def build_vector_store(chunks: list[Chunk]) -> None:
    """Embed every chunk (handbook and website together) and persist them,
    with metadata, into one Chroma collection."""
    if not chunks:
        raise ValueError(
            "No chunks to store — is the handbook PDF path correct (and does "
            "it contain extractable text, not just scanned images), and did "
            "the website crawl return any pages?"
        )

    model = SentenceTransformer(config.EMBEDDING_MODEL_NAME)
    embeddings = model.encode([c.text for c in chunks], show_progress_bar=True)

    client = chromadb.PersistentClient(
        path=config.CHROMA_PERSIST_DIR,
        settings=Settings(anonymized_telemetry=False),
    )

    # Drop any previous run so re-ingesting never leaves stale chunks behind.
    try:
        client.delete_collection(config.CHROMA_COLLECTION_NAME)
    except Exception:
        pass

    collection = client.create_collection(
        name=config.CHROMA_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    # Metadata only carries the field that's actually meaningful for a given
    # chunk's source_type -- Chroma doesn't require every item's metadata
    # dict to share the same keys, and storing a page=None/url=None pair on
    # every chunk would just be noise app/rag.py has to filter back out.
    metadatas = []
    for c in chunks:
        meta: dict = {"source_type": c.source_type}
        if c.page is not None:
            meta["page"] = c.page
        if c.url is not None:
            meta["url"] = c.url
        metadatas.append(meta)

    collection.add(
        ids=[c.id for c in chunks],
        documents=[c.text for c in chunks],
        embeddings=embeddings.tolist(),
        metadatas=metadatas,
    )

    handbook_chunks = [c for c in chunks if c.source_type == "handbook"]
    website_chunks = [c for c in chunks if c.source_type == "website"]
    print(
        f"Stored {len(chunks)} chunks total in '{config.CHROMA_COLLECTION_NAME}' "
        f"at {config.CHROMA_PERSIST_DIR}: "
        f"{len(handbook_chunks)} from {len({c.page for c in handbook_chunks})} handbook pages, "
        f"{len(website_chunks)} from {len({c.url for c in website_chunks})} website pages."
    )


def run() -> None:
    print(f"Reading {config.HANDBOOK_PATH} ...")
    pages = extract_pages(config.HANDBOOK_PATH)
    print(f"Extracted text from {len(pages)} pages.")

    handbook_chunks = chunk_pages(pages)
    print(
        f"Split handbook into {len(handbook_chunks)} chunks "
        f"(chunk_size={config.CHUNK_SIZE}, overlap={config.CHUNK_OVERLAP})."
    )

    print(f"Crawling {len(config.TARGET_URLS)} ZAIO website pages ...")
    website_pages = crawl_website()
    print(f"Fetched and cleaned {len(website_pages)}/{len(config.TARGET_URLS)} website pages.")

    website_chunks = chunk_website_pages(website_pages)
    print(f"Split website content into {len(website_chunks)} chunks.")

    build_vector_store(handbook_chunks + website_chunks)


if __name__ == "__main__":
    run()
