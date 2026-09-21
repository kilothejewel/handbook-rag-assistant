"""
Part 2 — Retrieve information and generate an answer.

This module is the *online* half of the pipeline: it runs on every /ask
request. It deliberately never imports FastAPI — keeping the RAG logic
independent of the web framework means it can be unit tested, reused from a
CLI, or swapped into a different API layer without changes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

import chromadb
from chromadb.config import Settings
from openai import OpenAI
from sentence_transformers import SentenceTransformer

from app import config

SYSTEM_PROMPT = (
    "You are an assistant that answers student questions using ONLY the "
    "provided excerpts from the student handbook. "
    "If the excerpts do not contain the answer, say exactly: "
    f'"{config.NOT_FOUND_MESSAGE}" '
    "Never use outside knowledge, never guess, and never mention that you "
    "were given excerpts — answer as if you simply know the handbook."
)


@dataclass
class RetrievedChunk:
    text: str
    page: int
    distance: float  # cosine distance: 0.0 = identical, larger = less similar


@dataclass
class AskResult:
    answer: str
    source: str
    found: bool
    retrieved: list[RetrievedChunk] = field(default_factory=list)


@lru_cache(maxsize=1)
def _get_embedding_model() -> SentenceTransformer:
    # Loaded once per process and reused — this is the slow-to-load object.
    return SentenceTransformer(config.EMBEDDING_MODEL_NAME)


@lru_cache(maxsize=1)
def _get_collection():
    client = chromadb.PersistentClient(
        path=config.CHROMA_PERSIST_DIR,
        settings=Settings(anonymized_telemetry=False),
    )
    return client.get_collection(config.CHROMA_COLLECTION_NAME)


@lru_cache(maxsize=1)
def _get_llm_client() -> OpenAI:
    # Groq exposes an OpenAI-compatible API, so the official `openai` SDK
    # works unchanged — only base_url and api_key differ. Swapping to a
    # different provider later means changing this function alone.
    return OpenAI(api_key=config.GROQ_API_KEY, base_url=config.GROQ_BASE_URL)


def retrieve(question: str, top_k: int = config.TOP_K) -> list[RetrievedChunk]:
    """Embed the question and return its top_k nearest handbook chunks."""
    model = _get_embedding_model()
    query_embedding = model.encode([question]).tolist()

    collection = _get_collection()
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    retrieved = []
    for text, meta, distance in zip(
        results["documents"][0], results["metadatas"][0], results["distances"][0]
    ):
        retrieved.append(RetrievedChunk(text=text, page=meta["page"], distance=distance))
    return retrieved


def _format_source(chunks: list[RetrievedChunk]) -> str:
    pages = sorted({c.page for c in chunks})
    if len(pages) == 1:
        return f"Page {pages[0]}"
    return "Pages " + ", ".join(str(p) for p in pages)


def _build_prompt(question: str, chunks: list[RetrievedChunk]) -> str:
    context = "\n\n".join(f"[Page {c.page}]\n{c.text}" for c in chunks)
    return (
        f"Handbook excerpts:\n{context}\n\n"
        f"Student question: {question}\n\n"
        "Answer the question using only the excerpts above."
    )


def generate_answer(question: str, chunks: list[RetrievedChunk]) -> str:
    client = _get_llm_client()
    response = client.chat.completions.create(
        model=config.LLM_MODEL_NAME,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_prompt(question, chunks)},
        ],
        temperature=0.0,  # deterministic, factual answers — not creative writing
    )
    return response.choices[0].message.content.strip()


def answer_question(question: str) -> AskResult:
    """
    The full online pipeline: retrieve -> guardrail -> generate.

    The guardrail matters as much as the retrieval itself: if nothing
    retrieved is actually close enough to the question, we return the
    "not found" message directly and skip the LLM call entirely, rather
    than trusting the model to refuse on its own.
    """
    chunks = retrieve(question)

    if not chunks or chunks[0].distance > config.MAX_RELEVANT_DISTANCE:
        return AskResult(
            answer=config.NOT_FOUND_MESSAGE,
            source="N/A",
            found=False,
            retrieved=chunks,
        )

    answer = generate_answer(question, chunks)
    return AskResult(
        answer=answer,
        source=_format_source(chunks),
        found=True,
        retrieved=chunks,
    )
