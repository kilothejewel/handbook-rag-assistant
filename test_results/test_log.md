# Test Results — Handbook RAG Assistant

Ran against the live `/ask` endpoint on 2026-09-20, using the real
`data/handbook.pdf` (Zaio Full-Stack AI Engineer Bootcamp Handbook 2026),
after ingestion produced 60 chunks from 26 pages.

Config at time of testing: `TOP_K=6`, `MAX_RELEVANT_DISTANCE=0.75`,
`LLM_MODEL_NAME=openai/gpt-oss-20b` (via Groq).

| # | Question | Source (pages) | Answer |
|---|---|---|---|
| 1 | What are the hardware requirements for the bootcamp? | 1, 4, 5 | Lists OS (Windows/PowerShell or Mac/Terminal), dual-core i5/AMD 3000+/M1 processor, 4–8GB RAM, 256GB SSD, and minimum internet speeds (10 Mbps down / 3 Mbps up). |
| 2 | When does the bootcamp start and how long does it run for? | 7, 8, 11, 20 | Starts 15 January 2026, runs for 7 months. |
| 3 | What times are the live classes held? | 7, 11, 20 | Tuesdays 9–11am and Thursdays 6–8pm for the first 12 weeks, then Tuesdays 9–11am only. All sessions recorded. |
| 4 | How much are the total fees for the bootcamp? | 16, 17, 19, 24 | R38,950. |
| 5 | What payment options are available for paying the fees? | 16, 17 | Upfront payment via Zaio bank details, or financing through Capitec/Manati. |
| 6 | How is the final grade broken down for this bootcamp? | N/A | **Not found** (see Known Limitation below — the handbook does cover this on the "Grade Breakdown" page). |
| 7 | Which communication channel is used after orientation day? | 9, 18 | Discord. |
| 8 | How do I get access to my daily schedule/calendar? | 8, 9, 10 | Register on zaio.io, add your email to the JAN26-FS/FSAI-BC sheet by 16 Jan 2026 4pm, then use the "My Schedule" button once it appears. |
| 9 | What salary can I expect from the paid internship placement? | 24, 25 | R4,000/month for a 12-month paid internship. |
| 10 | What is the attendance requirement? | N/A | **Correctly returned "not found"** — this question (taken directly from the assignment brief's own example) is not answerable from this handbook, and the system did not hallucinate an answer. |

**8/10 correctly answered from the handbook. 1/10 correctly refused
(genuine not-found, #10). 1/10 incorrectly refused (#6, a false negative).**

## Known limitation: question #6

"How is the final grade broken down?" was wrongly refused, even though the
handbook has a full "Grade Breakdown" section (Final Project 35%,
Assignments 25%, Coding Challenges 25%, MCQs 15%). Investigation showed:

- The correct chunk *was* being retrieved among the top-6 results.
- But the system prompt instructs the model to answer only when the
  excerpts clearly support it, and the retrieved chunk — a bulleted list
  fragment without its section heading nearby — didn't read as obviously
  about "the final grade" to the model, so it declined rather than guess.
- Rephrasing the same question ("How is my final grade calculated?", "What
  is the grade breakdown?") retrieved the same content and answered
  correctly both times.

This is a retrieval-chunking edge case, not a crash or a hallucination —
the system fails safe (refuses) rather than fails unsafe (makes something
up), which is the right failure mode for a handbook assistant. A future
improvement would be prepending each chunk with its page's section heading
before embedding, so fragments carry their own context.

## Tuning changes made during this test pass

- `LLM_MODEL_NAME`: `llama-3.1-8b-instant` → `openai/gpt-oss-20b` (Groq
  deprecated the former on 2026-08-16).
- `TOP_K`: `4` → `6` (4 was clipping multi-item bulleted answers, e.g. only
  returning 2 of 4 grading components on some phrasings).
- `MAX_RELEVANT_DISTANCE`: `0.60` → `0.75` (0.60 was rejecting some
  genuinely relevant chunks).
