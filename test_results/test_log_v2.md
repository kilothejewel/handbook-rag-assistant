# Test Results v2 — Cross-Source (Handbook + ZAIO Website)

Ran against the live `/ask` endpoint on <!-- fill in date -->, after
`python -m app.ingest` rebuilt `chroma_db` with both the handbook PDF and
the six crawled `TARGET_URLS` pages (see `app/config.py`).

Config at time of testing: `TOP_K=6`, `MAX_RELEVANT_DISTANCE=0.75`,
`LLM_MODEL_NAME=openai/gpt-oss-20b` (via Groq).

How to fill this in: run each question through `http://localhost:8000/docs`
→ `POST /ask` → "Try it out", paste the real `answer` and `source` fields
back from the response into the row below.

## Handbook-only

| # | Question | Answer | Source |
|---|---|---|---|
| 1 | How much are the total fees for the bootcamp? | The total fees for the bootcamp are **R 38,950**. | Student Handbook - Pages 16, 17, 24 |
| 2 | When does the bootcamp start and how long does it run for? | The bootcamp starts on **15 January 2026** and runs for **7 months**. | Student Handbook - Pages 7, 8, 11 |
| 3 | What are the hardware requirements for the bootcamp? | OS: current Windows w/ PowerShell or Mac w/ Terminal. Processor: dual-core i5 / AMD 3000+ / Apple M1 or greater. RAM: 4-8GB. Storage: 256GB SSD recommended. Internet: min 10 Mbps down / 3 Mbps up. | Student Handbook - Pages 1, 4, 5, 19 |
| 4 | What payment options are available for paying the fees? | Upfront payment (R38,950 via Zaio bank details); financing through Capitec or Manati; or pay-as-you-learn instalments (deposit + 50% in month 1 + 50% halfway through). See limitation below. | Student Handbook - Pages 16, 17 |
| 5 | What salary can I expect from the paid internship placement? | A paid internship placement offers a monthly salary of **R4,000**. | Student Handbook - Pages 3, 24, 25 |

## Website-only

| # | Question | Answer | Source |
|---|---|---|---|
| 6 | Can I finance 100% of my tuition? | Yes -- eligible learners can finance up to 100% of bootcamp tuition through partner Manati, starting with zero upfront cost and repaying in instalments. | https://www.zaio.io/tuition-financing |
| 7 | What bootcamp programs does Zaio offer? | I could not find that information in the available knowledge base. | N/A -- unexpected refusal, see limitation note below |
| 8 | Who is Zaio / what does the company do? | Zaio is a South African tech company founded to democratise access to opportunity. Builds training programmes (software dev, data science, web dev, digital marketing) with flexible live/recorded classes, plus post-course job-hunting support, interview prep, and an alumni network. | https://www.zaio.io/aboutus |
| 9 | How does the Full-Stack AI Engineer bootcamp compare to Zaio's other courses? | One of 5 fully-online bootcamps, most popular, highest monthly tuition (R4,178/mo, R42,850 upfront vs. R3,213/mo Cloud & DevOps, R1,950/mo Web Dev). Focuses on AI-specific tools (Cursor, Claude, OpenAI, LangChain, N8N) and agentic full-stack apps vs. other courses' domain focus. | https://www.zaio.io/fullstack-ai-engineer-bootcamp |
| 10 | Is there a part-time option for the bootcamp? | I could not find that information in the available knowledge base. | N/A -- plausibly a genuine gap (part-time vs. full-time may not be addressed on the crawled pages), not confirmed as a retrieval failure |

## Could come from either source

| # | Question | Answer | Source |
|---|---|---|---|
| 11 | How long is the Full-Stack AI Engineer bootcamp? | The Full-Stack AI Engineer bootcamp lasts **7 months**. | Student Handbook - Pages 1, 5 |
| 12 | What is the registration deadline? | Friday, 16 January 2026, 4pm. | Student Handbook - Pages 7, 8, 10, 17 |

## Unanswerable (should refuse)

| # | Question | Answer | Source |
|---|---|---|---|
| 13 | What is the attendance requirement? | I could not find that information in the available knowledge base. | N/A |
| 14 | Does Zaio offer a money-back guarantee if I don't get a job afterward? | I could not find that information in the available knowledge base. | N/A |
| 15 | What programming language is covered in the first week of the course? | I could not find that information in the available knowledge base. | N/A |

## Summary

**10/15 correctly answered** (5 handbook, 3 website, 2 either-source), with
sources resolving correctly across both the handbook (page numbers) and
the website (URLs) -- confirms cross-source retrieval and citation
formatting both work.

**3/15 correctly refused** (questions 13, 14, 15) -- genuine not-found
cases, exact refusal wording returned each time, no hallucination.

**1/15 phrasing-sensitive false negative** (question 7) -- same failure
mode as the v1 grade-breakdown limitation: the retrieved chunk existed but
didn't surface for the first wording tried; a rephrase answered correctly.
Not a crash, not a hallucination -- the system fails safe.

**1/15 ambiguous** (question 10) -- refused, plausibly a genuine content
gap on the crawled pages rather than a retrieval failure; not confirmed
either way under time constraints.

Two additional findings worth mentioning in the walkthrough video, neither
a system bug:
- Question 4's answer pulled in detail from a website chunk while citing
  only the handbook, and referenced "the handbook and website" directly in
  its answer text -- see the limitation note below.
- Question 9 surfaced a real pricing discrepancy between the handbook
  (R38,950) and the website (R42,850) for the same bootcamp.

## Known limitations carried over from v1

See `test_results/test_log.md` for the documented false-negative on grade
breakdown questions (chunk lacks its section heading for context) -- still
a known limitation unless re-tested here.

## Note found in this test pass (question 9) -- source discrepancy, not a bug

The website (`/fullstack-ai-engineer-bootcamp`) quotes upfront tuition at
**R42,850**, while the handbook (question 1) says **R38,950**. This is a
real discrepancy between the two source documents themselves, not a
retrieval or generation error -- worth noting since the answer a student
gets could depend on which source the system happens to cite.

## New limitation found in this test pass (question 7)

"What bootcamp programs does Zaio offer?" was wrongly refused (N/A), but
rephrasing to "What courses can I study at Zaio?" answered successfully:
"Zaio offers bootcamps, including the **Full Stack AI Engineer Bootcamp**."
(source: https://www.zaio.io). Same failure mode as the v1 grade-breakdown
limitation -- phrasing-sensitive retrieval, not a missing or broken page.

Also worth a follow-up (not blocking): the successful answer names only one
bootcamp, while `/bootcamps` is meant to list all six programs per the
original crawl plan. Worth spot-checking whether `/bootcamps` content made
it into the vector store with enough detail, or whether the homepage chunk
is simply outranking it for this phrasing.

## New limitation found in this test pass (question 4)

"What payment options are available for paying the fees?" answered with a
"pay-as-you-learn instalments" option that is not in the handbook-only
test log from v1, and the answer's own wording ("the handbook and website
list...") indicates the model was given excerpts from both sources for
this question. However, `source` resolved to the handbook pages only,
since `_format_source()` cites only the single most relevant chunk's
source. Two issues: (1) the system prompt explicitly instructs the model
never to reveal that it was given excerpts, and it did so here; (2) the
cited source doesn't fully reflect where all of the answer's content came
from when top-k chunks mix sources. Neither is a crash or a hallucination
-- the fee amounts and options stated are accurate -- but both are worth
naming as a known limitation of the current single-source citation design.
