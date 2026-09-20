"""
Central configuration for the handbook assistant.

Everything that might change between environments (paths, model names, the
LLM API key) lives here so the rest of the codebase never hardcodes it.
Values are read from environment variables, with sensible defaults for
local development. Copy .env.example to .env and fill in your own values.
"""
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()  # reads a local .env file if present; does nothing in prod
# where real secrets/config come from (env vars set by the host) either way.

BASE_DIR = Path(__file__).resolve().parent.parent

# --- Source document -------------------------------------------------------
HANDBOOK_PATH = Path(os.getenv("HANDBOOK_PATH", BASE_DIR / "data" / "handbook.pdf"))

# --- Chunking ---------------------------------------------------------------
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))       # characters, not tokens
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "75"))  # ~15% overlap

# --- Embeddings --------------------------------------------------------------
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")

# --- Vector store -------------------------------------------------------------
CHROMA_PERSIST_DIR = str(BASE_DIR / "chroma_db")
CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "handbook")

# --- Retrieval ----------------------------------------------------------------
TOP_K = int(os.getenv("TOP_K", "4"))
# Chroma's default "l2" space doesn't map cleanly to a 0-1 similarity, so the
# collection is created with cosine distance (see ingest.py). With cosine
# distance, 0.0 = identical, 2.0 = opposite. This threshold is a starting
# point — tune it during Sprint 4 testing against real handbook questions.
MAX_RELEVANT_DISTANCE = float(os.getenv("MAX_RELEVANT_DISTANCE", "0.60"))

# --- Generation (Groq, OpenAI-compatible API) ---------------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
# llama-3.1-8b-instant was deprecated by Groq on 2026-08-16; openai/gpt-oss-20b
# is its recommended replacement (see https://console.groq.com/docs/deprecations).
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "openai/gpt-oss-20b")

NOT_FOUND_MESSAGE = (
    "I couldn't find anything about that in the student handbook. "
    "Please check with your faculty administrator or student services."
)
