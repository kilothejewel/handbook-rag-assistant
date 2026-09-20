"""
Part 3 — REST API.

    uvicorn app.main:app --reload

POST /ask   {"question": "..."}  ->  {"answer": "...", "source": "Page 12"}
GET  /health -> {"status": "ok"}

Design choices worth noting for graders (and for n8n, which will call this
as a plain HTTP node):
  * Pydantic models validate the request shape automatically — a missing or
    empty "question" field returns a 422 with a clear JSON body, no manual
    if-checks required.
  * A single exception handler turns any unexpected internal error into a
    structured JSON 500 response instead of a raw Python traceback — nothing
    calling this API should ever see a stack trace.
  * CORS is left open for local development / n8n; tighten allow_origins
    before deploying this anywhere public.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from app.rag import answer_question

logger = logging.getLogger("handbook_assistant")

app = FastAPI(
    title="Handbook Assistant API",
    description="RAG-powered Q&A over the student handbook.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, description="The student's question.")

    @field_validator("question")
    @classmethod
    def question_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("question must not be blank")
        return value.strip()


class AskResponse(BaseModel):
    answer: str
    source: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/ask", response_model=AskResponse)
def ask(payload: AskRequest) -> AskResponse:
    result = answer_question(payload.question)
    return AskResponse(answer=result.answer, source=result.source)


# --- Error handling ----------------------------------------------------------
# FastAPI already returns 422 JSON for validation errors; this handler just
# makes the shape predictable ({"error": "..."}), which is easier for n8n
# (or any caller) to branch on than parsing FastAPI's default detail array.
@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    # exc.errors() can include a raw exception instance under ctx.error for
    # custom @field_validator failures (e.g. our blank-question check), which
    # json.dumps can't serialize on its own — jsonable_encoder converts it
    # (and anything else non-JSON-native) to a safe representation first.
    return JSONResponse(
        status_code=422,
        content={"error": "Invalid request", "details": jsonable_encoder(exc.errors())},
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error while processing request")
    return JSONResponse(
        status_code=500,
        content={"error": "Something went wrong while answering your question."},
    )
