# Handbook Assistant

A retrieval-augmented generation (RAG) API that answers student questions
using only the content of the student handbook, and says so plainly when an
answer isn't in there.

Built for the Zaio Full-Stack AI Engineer Bootcamp handbook-RAG practical:
loads the handbook PDF, chunks and embeds it into a Chroma vector store,
retrieves relevant passages per question, and generates a grounded answer
via Groq — refusing rather than guessing when the handbook doesn't cover
the question. See [`test_results/test_log.md`](test_results/test_log.md)
for real Q&A test runs and a documented retrieval limitation.

## How it works

```
Ingestion (run once)
  handbook.pdf -> extract text per page -> chunk (tagged with page #)
                -> embed -> store in Chroma

Query (runs per request)
  question -> embed -> search top-k -> grounded prompt -> LLM -> {answer, source}
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # then add your GROQ_API_KEY
```

Place the handbook PDF at `data/handbook.pdf` (or set `HANDBOOK_PATH` in `.env`).

## Run

```bash
# 1. Build the vector store (only needed once, or after the PDF changes)
python -m app.ingest

# 2. Start the API
uvicorn app.main:app --reload
```

## Use

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "How much are the total fees for the bootcamp?"}'
```

```json
{"answer": "The total fees for the bootcamp are R 38,950.", "source": "Pages 16, 17, 19, 24"}
```

A question the handbook doesn't cover (e.g. "What is the attendance
requirement?") returns a fixed not-found message with `"source": "N/A"`
instead of a guess — see `app/config.py`'s `NOT_FOUND_MESSAGE` and the
guardrail in `app/rag.py::answer_question`.

Interactive API docs: http://localhost:8000/docs

## Test

```bash
pytest
```

## Project layout

```
app/
  config.py   configuration (paths, model names, thresholds)
  ingest.py   Part 1 — PDF -> chunks -> embeddings -> Chroma
  rag.py      Part 2 — retrieval + generation
  main.py     Part 3 — FastAPI app
tests/        Part 4 — unit tests
test_results/ Part 4 — logged Q&A test runs
```

## n8n integration (Part 5)

The API is a plain HTTP JSON endpoint, so it's ready to call from n8n's
HTTP Request node with no extra setup:

- **Request:** `POST http://localhost:8000/ask`, body `{"question": "..."}` (JSON)
- **Response:** `{"answer": "...", "source": "..."}` on success
- **Errors:** always JSON, never a raw stack trace — `{"error": "Invalid request", "details": [...]}` (422) for a missing/blank question, `{"error": "..."}` (500) for an internal failure
- CORS is open (`allow_origins=["*"]`) for local development; tighten this before deploying anywhere public

n8n workflow wiring itself is out of scope for this practical and will be
done in the next one.

## Known limitations

See [`test_results/test_log.md`](test_results/test_log.md) for the full
test run and one documented false-negative: a specific phrasing of a
grade-breakdown question was incorrectly refused because the retrieved
chunk lacked its section heading for context, even though the same
information answered correctly when the question was reworded.
