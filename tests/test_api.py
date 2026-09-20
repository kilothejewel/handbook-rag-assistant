"""
Unit tests for the FastAPI layer (Part 3 / Part 5 of the rubric).

The RAG pipeline (`answer_question`) is monkeypatched out here on purpose:
these tests check that the API validates input, shapes responses correctly,
and handles errors gracefully — not that the LLM gives a good answer (that's
what the Sprint 4 test-questions log is for). Mocking the slow/external
dependency is what keeps a unit test suite fast enough to run on every commit.
"""
from fastapi.testclient import TestClient

from app import main
from app.rag import AskResult

# raise_server_exceptions=False: without it, TestClient re-raises an
# exception that reached the app's own generic Exception handler instead of
# letting us assert on the 500 response that handler returns — we're testing
# that our handler produces a clean JSON error, not that the exception
# doesn't happen.
client = TestClient(main.app, raise_server_exceptions=False)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ask_returns_answer_and_source(monkeypatch):
    monkeypatch.setattr(
        main,
        "answer_question",
        lambda question: AskResult(
            answer="Attendance must be at least 80%.",
            source="Page 12",
            found=True,
        ),
    )

    response = client.post("/ask", json={"question": "What is the attendance requirement?"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Attendance must be at least 80%."
    assert body["source"] == "Page 12"


def test_ask_returns_not_found_message_when_out_of_scope(monkeypatch):
    monkeypatch.setattr(
        main,
        "answer_question",
        lambda question: AskResult(answer="I couldn't find that.", source="N/A", found=False),
    )

    response = client.post("/ask", json={"question": "What's the wifi password?"})

    assert response.status_code == 200
    assert response.json()["source"] == "N/A"


def test_ask_rejects_missing_question_field():
    response = client.post("/ask", json={})

    assert response.status_code == 422
    assert "error" in response.json()


def test_ask_rejects_blank_question():
    response = client.post("/ask", json={"question": "   "})

    assert response.status_code == 422


def test_ask_handles_internal_errors_gracefully(monkeypatch):
    def boom(question):
        raise RuntimeError("vector store unavailable")

    monkeypatch.setattr(main, "answer_question", boom)

    response = client.post("/ask", json={"question": "What is the attendance requirement?"})

    assert response.status_code == 500
    assert response.json() == {"error": "Something went wrong while answering your question."}
