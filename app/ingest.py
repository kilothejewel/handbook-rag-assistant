"""
Part 1 — Process the handbook.

This module is the *offline* half of the RAG pipeline. It is meant to be run
once (and again any time the handbook PDF changes), not on every API request:

    python -m app.ingest

Pipeline: PDF -> per-page text -> overlapping chunks (tagged with their page
number) -> embeddings -> persisted Chroma collection.

Keeping page numbers attached to every chunk from the very first step is
what makes the API's `"source": "Page 12"` field possible later — extract
the whole PDF as one blob first and that information is gone for good.
"""
from __future__ import annotations

from dataclasses import dataclass

import chromadb
from chromadb.config import Settings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

from app import config


@dataclass
class Chunk:
    """One retrievable unit of the handbook."""
    id: str
    text: str
    page: int  # 1-indexed page number, for citations


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
    Split each page's text independently so a chunk never straddles a page
    boundary — that would make citing a single source page ambiguous.

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
                Chunk(id=f"page{page_number}-chunk{i}", text=piece, page=page_number)
            )
    return chunks


def build_vector_store(chunks: list[Chunk]) -> None:
    """Embed every chunk and persist it, with metadata, into Chroma."""
    if not chunks:
        raise ValueError(
            "No chunks to store — is the PDF path correct and does it contain "
            "extractable text (not just scanned images)?"
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

    collection.add(
        ids=[c.id for c in chunks],
        documents=[c.text for c in chunks],
        embeddings=embeddings.tolist(),
        metadatas=[{"page": c.page} for c in chunks],
    )
    print(f"Stored {len(chunks)} chunks from {len(set(c.page for c in chunks))} pages "
          f"in '{config.CHROMA_COLLECTION_NAME}' at {config.CHROMA_PERSIST_DIR}")


def run() -> None:
    print(f"Reading {config.HANDBOOK_PATH} ...")
    pages = extract_pages(config.HANDBOOK_PATH)
    print(f"Extracted text from {len(pages)} pages.")

    chunks = chunk_pages(pages)
    print(f"Split into {len(chunks)} chunks "
          f"(chunk_size={config.CHUNK_SIZE}, overlap={config.CHUNK_OVERLAP}).")

    build_vector_store(chunks)


if __name__ == "__main__":
    run()
