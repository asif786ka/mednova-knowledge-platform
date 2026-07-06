"""
MedNova Agentic AI Knowledge Platform — FastAPI backend.

Endpoints:
  GET  /health      system + dependency status
  POST /ingest      ingest documents (sync or async via background queue)
  POST /ask         ask a question -> source-backed, routed answer
  POST /voice/ask   voice route: transcript in -> answer + speech text out
  GET  /jobs/{id}   ingestion job status (async ingestion)
  GET  /graph/stats knowledge-graph statistics
"""
from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import state
from app.api.models import (
    AskRequest, AskResponse, HealthResponse, IngestRequest, IngestResponse,
    VoiceAskRequest, VoiceAskResponse,
)
from app.cache import get_cache
from app.config import settings
from app.llm.provider import get_llm_provider
from app.observability import Timer, get_logger, new_request_id
from app.observability.logging import log
from app.queue import get_job_store, run_ingestion_job
from app.retrieval.embeddings import get_embedder

logger = get_logger("api")


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Load persisted stores if present; ingest samples on first run if empty.
    state.reload_stores()
    if state.get_vector_store().count() == 0:
        log(logger, "INFO", "empty index at startup; ingesting sample_docs")
        try:
            from app.ingestion.pipeline import IngestionPipeline

            IngestionPipeline().ingest_folder()
            state.reload_stores()
        except Exception as exc:  # pragma: no cover
            log(logger, "WARNING", "startup ingest failed", error=str(exc))
    yield


app = FastAPI(
    title="MedNova Agentic AI Knowledge Platform",
    version="0.1.0",
    description="Internal knowledge assistant: RAG + GraphRAG + agentic routing over "
                "MedNova documents. Source-backed answers with an honesty gate.",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])


@app.middleware("http")
async def request_context(request: Request, call_next):
    rid = new_request_id()
    request.state.request_id = rid
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:  # pragma: no cover
        log(logger, "ERROR", "unhandled error", request_id=rid,
            path=request.url.path, error=str(exc))
        return JSONResponse(status_code=500,
                            content={"detail": "internal error", "request_id": rid})
    ms = round((time.perf_counter() - start) * 1000, 1)
    response.headers["X-Request-ID"] = rid
    response.headers["X-Response-Time-ms"] = str(ms)
    log(logger, "INFO", "request", request_id=rid, method=request.method,
        path=request.url.path, status=response.status_code, latency_ms=ms)
    return response


# --------------------------------------------------------------------------- #
@app.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    vs = state.get_vector_store()
    gs = state.get_graph_store()
    llm = get_llm_provider()
    cache = get_cache()
    embedder = get_embedder()
    return HealthResponse(
        status="ok",
        vector_db="connected" if vs is not None else "unavailable",
        graph_db="connected" if gs is not None else "unavailable",
        llm_provider=llm.backend + (" (available)" if llm.uses_real_llm
                                    else " (deterministic fallback)"),
        cache=cache.backend,
        embeddings=embedder.backend,
        documents_indexed=vs.count() if vs else 0,
        graph_nodes=gs.g.number_of_nodes() if gs else 0,
    )


@app.post("/ingest", response_model=IngestResponse, tags=["ingestion"])
def ingest(req: IngestRequest, background: BackgroundTasks) -> IngestResponse:
    if req.async_mode:
        job_id = uuid.uuid4().hex[:12]
        get_job_store().create(job_id)
        background.add_task(run_ingestion_job, job_id, req.folder, req.reset)
        log(logger, "INFO", "ingestion queued", job_id=job_id)
        return IngestResponse(status="queued", documents_processed=0, chunks_created=0,
                              entities_extracted=0, relationships_created=0, job_id=job_id)
    try:
        from app.ingestion.pipeline import IngestionPipeline

        result = IngestionPipeline().ingest_folder(req.folder, reset=req.reset)
        state.reload_stores()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"ingestion failed: {exc}")
    return IngestResponse(**result.dict())


@app.get("/jobs/{job_id}", tags=["ingestion"])
def job_status(job_id: str):
    job = get_job_store().get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return job.dict()


@app.post("/ask", response_model=AskResponse, tags=["qa"])
def ask(req: AskRequest, request: Request) -> AskResponse:
    rid = getattr(request.state, "request_id", new_request_id())
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="question must not be empty")

    cache = get_cache()
    cached = cache.get(question)
    with Timer() as t:
        if cached:
            payload = dict(cached)
            payload["cached"] = True
            payload["latency_ms"] = t.ms
            log(logger, "INFO", "cache hit", request_id=rid, question=question)
            return AskResponse(**payload)
        answer = state.get_router().answer(question, request_id=rid)
    payload = answer.dict()
    payload["cached"] = False
    payload["latency_ms"] = t.ms
    # store the cacheable subset (exclude volatile fields)
    cache.set(question, {k: v for k, v in payload.items()
                         if k not in ("cached", "latency_ms")})
    log(logger, "INFO", "answered", request_id=rid, route=answer.route,
        strategy=answer.retrieval_strategy, confidence=round(answer.confidence, 3),
        sources=answer.sources, latency_ms=t.ms)
    return AskResponse(**payload)


@app.post("/voice/ask", response_model=VoiceAskResponse, tags=["voice"])
def voice_ask(req: VoiceAskRequest, request: Request) -> VoiceAskResponse:
    """
    Voice route. Accepts a transcript (client-side or server-side STT). Returns the same
    routed answer plus `speech_text` ready for a text-to-speech engine. Audio-file upload and
    Whisper STT / TTS synthesis are designed and documented; the transcript path keeps the
    prototype dependency-free (see SYSTEM_DESIGN 'Voice AI').
    """
    rid = getattr(request.state, "request_id", new_request_id())
    transcript = (req.transcript or "").strip()
    if not transcript:
        raise HTTPException(status_code=422,
                            detail="Provide 'transcript'. (Audio STT is optional; see docs.)")
    if len(transcript) < 3:
        raise HTTPException(status_code=422, detail="transcript too short")

    with Timer() as t:
        answer = state.get_router().answer(transcript, request_id=rid)
    payload = answer.dict()
    payload.update(cached=False, latency_ms=t.ms, transcript=transcript,
                   speech_text=answer.answer)
    log(logger, "INFO", "voice answered", request_id=rid, route=answer.route,
        latency_ms=t.ms)
    return VoiceAskResponse(**payload)


@app.get("/graph/stats", tags=["graph"])
def graph_stats():
    return state.get_graph_store().stats() if state.get_graph_store() else {}


@app.get("/", tags=["system"])
def root():
    return {"name": "MedNova Agentic AI Knowledge Platform",
            "docs": "/docs", "health": "/health"}
