"""
Part 2 — Retrieve information and generate an answer, across both sources.

This module is the *online* half of the pipeline: it runs on every /ask
request. It deliberately never imports FastAPI — keeping the RAG logic
independent of the web framework means it can be unit tested, reused from a
CLI, or swapped into a different API layer without changes.

Cross-source retrieval needs no special plumbing: both the handbook and the
website chunks live in one Chroma collection (see app/ingest.py), so
`collection.query()` already searches across both. The only places that
need to know there are two sources are the ones that turn a chunk back into
a human-facing citation or prompt context -- `_format_source()` and
`_build_prompt()` below.
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
    "provided excerpts from the student handbook or the ZAIO website. "
    "If the excerpts do not contain the answer, say exactly: "
    f'"{config.NOT_FOUND_MESSAGE}" '
    "Never use outside knowledge, never guess, and never mention that you "
    "were given excerpts — answer as if you simply know this material."
)


@dataclass
class RetrievedChunk:
    text: str
    source_type: str  # "handbook" or "website"
    distance: float  # cosine distance: 0.0 = identical, larger = less similar
    page: int | None = None  # set when source_type == "handbook"
    url: str | None = None   # set when source_type == "website"


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
    """Embed the question and return its top_k nearest chunks, regardless
    of which source (handbook or website) they came from."""
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
        retrieved.append(
            RetrievedChunk(
                text=text,
                source_type=meta["source_type"],
                distance=distance,
                page=meta.get("page"),
                url=meta.get("url"),
            )
        )
    return retrieved


def _format_source(chunks: list[RetrievedChunk]) -> str:
    """
    Turn the retrieved chunks into the single source string the API
    returns. Chunks are already ordered by relevance (lowest distance
    first), so `chunks[0]` is always the top-ranked match.

    Default design decision: if the top-ranked chunk is a website page, the
    source is just that page's URL -- several different URLs don't collapse
    into one clean string the way page numbers do, and the brief's own
    examples always show exactly one source per answer. If the top-ranked
    chunk is from the handbook, the source lists every handbook page among
    the *retrieved* chunks (ignoring any website chunks mixed into the same
    top-k) -- matching the single-source behavior this already had before
    the website was added, just prefixed to say which document it's from.
    """
    top = chunks[0]
    if top.source_type == "website":
        return top.url

    handbook_pages = sorted({c.page for c in chunks if c.source_type == "handbook"})
    if len(handbook_pages) == 1:
        return f"Student Handbook - Page {handbook_pages[0]}"
    return "Student Handbook - Pages " + ", ".join(str(p) for p in handbook_pages)


def _build_prompt(question: str, chunks: list[RetrievedChunk]) -> str:
    def _label(c: RetrievedChunk) -> str:
        return f"Student Handbook, Page {c.page}" if c.source_type == "handbook" else c.url

    context = "\n\n".join(f"[{_label(c)}]\n{c.text}" for c in chunks)
    return (
        f"Excerpts:\n{context}\n\n"
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

    # The distance check passed, but the model read the excerpts and still
    # found no answer (it's told to reply with NOT_FOUND_MESSAGE verbatim).
    # Citing the retrieved pages here would point the student at a source
    # that doesn't actually answer their question.
    if config.NOT_FOUND_MESSAGE.rstrip(".") in answer:
        return AskResult(
            answer=config.NOT_FOUND_MESSAGE,
            source="N/A",
            found=False,
            retrieved=chunks,
        )

    return AskResult(
        answer=answer,
        source=_format_source(chunks),
        found=True,
        retrieved=chunks,
    )
