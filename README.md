# MedNova — Agentic AI Knowledge Platform

An internal AI knowledge assistant for the (fictional) healthcare-technology company
**MedNova Solutions**. Employees ask natural-language questions and get **reliable,
source-backed answers** grounded in MedNova's own documents — combining **RAG**, a
**knowledge graph (GraphRAG)**, and an **agentic router**, served by **FastAPI**.

> **Runs with zero API keys.** Out of the box it uses local embeddings, an in-process vector
> index, an in-memory graph, and a deterministic grounded answerer — so a reviewer can clone
> and run it in minutes. Every layer upgrades to a managed service (OpenAI, Neo4j, Astra DB,
> Redis, Langfuse) by setting an environment variable. No code changes.

---

## Table of contents
1. [Project overview](#project-overview)
2. [Business problem](#business-problem)
3. [Features implemented](#features-implemented)
4. [Technologies used](#technologies-used)
5. [Quick start](#quick-start)
6. [Environment variables](#environment-variables)
7. [How to run](#how-to-run)
8. [Ingesting documents](#ingesting-documents)
9. [Asking questions (API)](#asking-questions-api)
10. [How it works](#how-it-works) — RAG, GraphRAG, agentic workflow, caching, queue, observability
11. [Testing & evaluation](#testing--evaluation)
12. [Known limitations](#known-limitations)
13. [Future improvements](#future-improvements)

---

## Project overview
MedNova's internal knowledge is scattered across project briefs, architecture notes, meeting
summaries, risk assessments and requirements. This platform lets an employee ask a question in
plain English and receive a concise, cited answer. It is **not a generic chatbot** — it
retrieves from the company's documents, reasons over the relationships between projects,
technologies, risks and requirements, and refuses to answer when the documents don't support
one.

Full design write-up: **[`SYSTEM_DESIGN.md`](SYSTEM_DESIGN.md)** and the
**[architecture PDF](MedNova_Architecture_and_System_Design.pdf)**.

## Business problem
Employees waste time searching documents and re-asking the same questions. The platform:
reduces manual search time, improves access to internal knowledge, surfaces relationships
between projects/tools/risks/requirements, speeds up onboarding, and provides a foundation for
future AI assistants and voice interfaces.

## Features implemented
- **Document ingestion pipeline** — load (`.md/.txt/.pdf/.docx`) → structure-aware chunking →
  embeddings → vector store → entity/relationship extraction → knowledge graph.
- **RAG** — semantic top-k retrieval with lexical rerank and source-cited, grounded answers.
- **GraphRAG / knowledge graph** — NetworkX graph of Clients, Projects, Technologies, Cloud
  Providers, Risks, Requirements, Documents; used for relationship questions and to enrich
  answers.
- **Agentic router** — a LangGraph-style state machine (classify → plan → retrieve →
  synthesize → verify) that picks vector / graph / hybrid / summary routes.
- **LLM provider abstraction** — LiteLLM (OpenAI/Anthropic/Ollama/…) with an automatic
  **deterministic extractive fallback** so it always answers, offline, without hallucinating.
- **FastAPI backend** — `/health`, `/ingest`, `/ask`, `/voice/ask`, `/jobs/{id}`,
  `/graph/stats`, with Pydantic validation, error handling, and request ids.
- **Caching** — response cache (Redis or in-memory TTL-LRU) keyed on the question hash.
- **Queue / background processing** — async ingestion via FastAPI BackgroundTasks
  (Celery-ready).
- **Observability** — structured JSON logs, per-request latency, tracing spans, optional
  Langfuse.
- **Voice endpoint** — `/voice/ask` (transcript in → answer + TTS-ready text out).
- **Bonus** — Docker + docker-compose, graph visualisation (PNG + interactive HTML),
  pytest suite, and an evaluation harness.

## Technologies used
Python 3.11 · FastAPI · Pydantic · NumPy · NetworkX · LiteLLM (optional) ·
sentence-transformers (optional) · Redis (optional) · Langfuse (optional) · Graphviz / pyvis ·
pytest · Docker / docker-compose.

**Paid APIs:** none required. If you set `OPENAI_API_KEY` (or another provider key) the LLM
synthesis path uses that provider and will incur that provider's cost; otherwise everything is
free and local.

---

## Quick start

```bash
# 1. install
pip install -r requirements.txt

# 2. run the API (auto-ingests sample_docs on first start)
uvicorn app.main:app --reload

# 3. open the interactive docs
open http://localhost:8000/docs
```

Or with Docker (includes Redis):

```bash
docker compose up --build
# API at http://localhost:8000 , Swagger at /docs
```

## Environment variables
Everything is optional — see [`.env.example`](.env.example) for the full list. Highlights:

| Variable | Effect |
|---|---|
| _(none set)_ | Fully offline: hashing embedder, NumPy vector store, NetworkX graph, extractive answerer, in-memory cache |
| `OPENAI_API_KEY` (+ `LLM_MODEL`) | Enables real LLM synthesis via LiteLLM |
| `EMBED_MODEL` | Use a sentence-transformers model instead of the hashing embedder |
| `REDIS_URL` | Use Redis for the response cache / queue broker |
| `NEO4J_URI`, `ASTRA_DB_ID` | Reserved for the managed graph / vector backends (design-ready) |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | Enable Langfuse tracing |

## How to run

```bash
uvicorn app.main:app --reload          # dev server with auto-reload
python scripts/demo.py                 # ingest + run the 12 assessment questions
python scripts/run_evals.py            # evaluation harness (route/source/keyword/honesty)
python -m app.graph.viz                # export knowledge-graph PNG + interactive HTML
pytest -q                              # unit + integration tests
```

## Ingesting documents
Drop files into `sample_docs/` (or any folder) and ingest:

```bash
# via API (synchronous)
curl -X POST localhost:8000/ingest -H 'Content-Type: application/json' -d '{}'

# via API (asynchronous background job)
curl -X POST localhost:8000/ingest -H 'Content-Type: application/json' \
     -d '{"async": true, "folder": "sample_docs"}'
# -> {"status":"queued","job_id":"ab12cd34ef56", ...}
curl localhost:8000/jobs/ab12cd34ef56
```

Example synchronous response:

```json
{"status":"success","documents_processed":9,"chunks_created":18,
 "entities_extracted":47,"relationships_created":154,"skipped":[]}
```

## Asking questions (API)

**Request**
```bash
curl -X POST localhost:8000/ask -H 'Content-Type: application/json' \
     -d '{"question":"Which projects use LangChain and Neo4j?"}'
```

**Response**
```json
{
  "answer": "Project 'MedNova Knowledge Platform' uses Technology 'LangChain'. Project 'MedNova Knowledge Platform' uses Technology 'Neo4j'. ...",
  "sources": ["knowledge_platform_design.md", "technical_architecture_notes.md", "meeting_summary_2026_06.md"],
  "retrieval_strategy": "vector_and_graph",
  "related_entities": ["LangChain", "MedNova Knowledge Platform", "Neo4j"],
  "route": "hybrid",
  "confidence": 0.9,
  "llm_backend": "extractive-fallback",
  "matched_entities": ["LangChain", "Neo4j"],
  "cached": false,
  "latency_ms": 3.5
}
```

**Voice**
```bash
curl -X POST localhost:8000/voice/ask -H 'Content-Type: application/json' \
     -d '{"transcript":"Which requirements mention voice-based AI?"}'
# returns the same answer plus `speech_text` for a text-to-speech engine
```

More runnable examples and live responses are in **[`demo/`](demo/)**
(`api_examples.json`, `demo_output.txt`, `eval_report.txt`).

---

## How it works

### RAG implementation
`/ingest` loads each document, splits it with a **structure-aware recursive chunker** (markdown
headings → paragraphs → sentences, with overlap), embeds each chunk, and stores it in the
vector store with its source filename and section. At query time (`app/retrieval/rag.py`) the
question is embedded, the store returns cosine top-k, and a **lightweight lexical rerank**
blends semantic score with keyword overlap to sharpen keyword-heavy queries. The retrieved
chunks — each tagged `[source — section]` — become the grounding context. **Embeddings**:
sentence-transformers when available, otherwise a deterministic character-n-gram **hashing
embedder** so the system needs no model download.

### GraphRAG / knowledge graph implementation
During ingestion (`app/ingestion/extractor.py`) a dictionary + pattern extractor pulls typed
entities (Technology, CloudProvider, Project, Client, Risk, Requirement) and links them to each
document's **primary project**, producing a NetworkX graph:

```
(:Client)-[:OWNS]->(:Project)      (:Project)-[:USES]->(:Technology)
(:Project)-[:DEPLOYED_ON]->(:CloudProvider)   (:Project)-[:HAS_RISK]->(:Risk)
(:Requirement)-[:BELONGS_TO]->(:Project)      (:Document)-[:MENTIONS]->(:Entity)
```

For relationship questions (`app/graph/graphrag.py`) the platform matches entities in the
question, expands their 1-hop neighbourhood, and renders the edges as natural-language facts
(“Project X uses Technology Y”) that ground the answer — **still source-backed**, because it
also returns the documents that mention those entities. This answers questions pure vector
search handles poorly, e.g. *“What is the relationship between the knowledge platform, Neo4j and
Astra DB?”*. Visualise it with `python -m app.graph.viz` →
[`diagrams/knowledge_graph.png`](diagrams/knowledge_graph.png).

### Agentic workflow
`app/agents/router.py` is a LangGraph-style state machine:
**classify → plan → retrieve → synthesize → verify**. The classifier uses cheap heuristics
(relationship verbs, summary intent, multi-entity co-occurrence) to choose a route:

| Route | When | Retrieval |
|---|---|---|
| `vector` | fact lookup / “which documents mention X” | semantic top-k |
| `graph` | relationship / connection questions | graph neighbourhood |
| `hybrid` | “which projects use both A and B” | graph narrows + vector proves |
| `summary` | “summarise the architecture” | broad multi-chunk + summarise |

The **verify** node is an honesty gate: if retrieval confidence is too low, it returns an
explicit *“not enough information”* instead of guessing. A `graph` route with no graph hits
gracefully falls back to `vector`.

### Caching strategy
`app/cache/` provides a response cache keyed on `sha256(normalised question)`. A repeated
question returns instantly and **skips the LLM entirely** (biggest cost/latency win). Backend
is **Redis** when `REDIS_URL` is set (shared across replicas, TTL-based) and an in-memory
**TTL-LRU** otherwise — identical interface. The design also covers provider-side **prompt/KV
cache** by keeping the system prompt + context prefix stable (see `SYSTEM_DESIGN.md`).

### Queue / background processing
`/ingest` with `{"async": true}` enqueues the ingestion job and returns a `job_id` immediately;
progress is polled at `/jobs/{id}`. Locally this uses **FastAPI BackgroundTasks** with an
in-process `JobStore` (`app/queue/`). The producer boundary maps directly onto a **Celery**
task with Redis/RabbitMQ for multi-worker scale-out.

### Observability
`app/observability/` emits **structured JSON logs** with a request id, route, `latency_ms`,
retrieved chunk ids and cache hits; `trace_event` spans wrap retrieve/synthesize steps and
activate **Langfuse** tracing automatically when keys are present. Every HTTP response carries
`X-Request-ID` and `X-Response-Time-ms`. Sample logs: `demo/structured_logs_sample.jsonl`.

---

## Testing & evaluation
- **Unit + integration tests** (`pytest -q`) — ingestion, extraction, router classification,
  the honesty gate, and all API endpoints. **15 tests, all passing.**
- **Evaluation harness** (`python scripts/run_evals.py`) — runs the 12 assessment questions
  plus an out-of-domain refusal case, scoring **route accuracy, source recall, keyword recall
  and honesty**. Current result: **13/13 (100%)**. Report: `demo/eval_report.txt`.

## Known limitations
- Entity/relationship extraction is **rule/dictionary-based**, so recall on entity names
  outside the vocabulary is limited (high precision, bounded recall).
- The NumPy vector index is **in-process** and not sharded — perfect for the prototype,
  replaced by Astra DB / Chroma at scale.
- The offline **extractive answerer** is grounded but less fluent than a hosted LLM; set an LLM
  key for polished prose.
- Neo4j / Astra DB integrations are **design-ready** (interfaces + config) but the default runs
  on the local NetworkX / NumPy stores.

## Future improvements
LLM-based NER + relation extraction; hybrid BM25 + vector retrieval with cross-encoder
reranking; streaming responses; a web UI; full voice (Whisper STT + TTS); RAGAS-style metrics
wired into CI; and swapping the local stores for Neo4j Aura + Astra DB in production.

---

### Project structure
```
awtg_home_task/
├── app/
│   ├── main.py                 # FastAPI app + endpoints
│   ├── config.py               # env-driven settings (all deps optional)
│   ├── state.py                # shared serving state (hot-reloadable)
│   ├── api/models.py           # Pydantic schemas
│   ├── ingestion/              # loaders, chunker, extractor, pipeline
│   ├── retrieval/              # embeddings, vector_store, rag, prompts
│   ├── graph/                  # graph_store, graphrag, viz
│   ├── agents/router.py        # agentic router (state machine)
│   ├── llm/provider.py         # LiteLLM abstraction + extractive fallback
│   ├── cache/                  # Redis / in-memory response cache
│   ├── queue/                  # background job store + worker
│   └── observability/          # structured logging + tracing
├── sample_docs/                # 9 fictional MedNova documents
├── diagrams/                   # architecture, data-model & knowledge-graph diagrams (+ generators)
├── demo/                       # demo evidence: API examples, eval report, logs, OpenAPI
├── eval/eval_dataset.json      # evaluation set
├── scripts/                    # demo.py, run_evals.py
├── tests/                      # pytest suite
├── MedNova_Architecture_and_System_Design.pdf
├── SYSTEM_DESIGN.md
├── Dockerfile · docker-compose.yml · requirements.txt · .env.example
```
