"""
Unit tests for the answer pipeline's guardrails in app/rag.py.

`retrieve()` and `generate_answer()` are monkeypatched, so these never load
the embedding model, open Chroma, or call the LLM -- they only check what
`answer_question()` does with the results.
"""
from app import config, rag
from app.rag import RetrievedChunk


def _handbook_chunk(page: int, distance: float) -> RetrievedChunk:
    return RetrievedChunk(text="...", source_type="handbook", distance=distance, page=page)


def test_answer_question_cites_source_when_model_answers(monkeypatch):
    monkeypatch.setattr(rag, "retrieve", lambda q: [_handbook_chunk(11, 0.3)])
    monkeypatch.setattr(rag, "generate_answer", lambda q, c: "Live classes run on Thursdays.")

    result = rag.answer_question("When are live classes?")

    assert result.found is True
    assert result.source == "Student Handbook - Page 11"


def test_answer_question_skips_llm_when_nothing_is_close_enough(monkeypatch):
    far = config.MAX_RELEVANT_DISTANCE + 0.1
    monkeypatch.setattr(rag, "retrieve", lambda q: [_handbook_chunk(5, far)])

    def _fail(q, c):
        raise AssertionError("LLM should not be called")

    monkeypatch.setattr(rag, "generate_answer", _fail)

    result = rag.answer_question("What is the capital of France?")

    assert result.found is False
    assert result.source == "N/A"


def test_answer_question_drops_citation_when_model_refuses(monkeypatch):
    # Retrieval passed the distance check, but the excerpts didn't actually
    # contain the answer, so the model replied with the not-found message.
    monkeypatch.setattr(rag, "retrieve", lambda q: [_handbook_chunk(5, 0.6)])
    monkeypatch.setattr(rag, "generate_answer", lambda q, c: config.NOT_FOUND_MESSAGE)

    result = rag.answer_question("What is the minimum attendance requirement?")

    assert result.found is False
    assert result.source == "N/A"
    assert result.answer == config.NOT_FOUND_MESSAGE
