"""
Background/queue processing.

Ingestion is I/O- and compute-heavy (loading, chunking, embedding, extraction), so /ingest
enqueues the work and returns a job id immediately instead of blocking the request. Locally
this runs on FastAPI BackgroundTasks with an in-process JobStore tracking status. The same
producer boundary (`run_ingestion_job`) maps directly onto a Celery task for multi-worker
scale-out with Redis/RabbitMQ as the broker (documented in SYSTEM_DESIGN.md).
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field, asdict
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

from app.observability import get_logger
from app.observability.logging import log

logger = get_logger("queue")


@dataclass
class Job:
    job_id: str
    status: str = "queued"           # queued | running | completed | failed
    created_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None
    result: Optional[dict] = None
    error: Optional[str] = None

    def dict(self) -> dict:
        d = asdict(self)
        d["duration_ms"] = (round((self.finished_at - self.created_at) * 1000, 1)
                            if self.finished_at else None)
        return d


class JobStore:
    def __init__(self) -> None:
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self, job_id: str) -> Job:
        with self._lock:
            job = Job(job_id=job_id)
            self._jobs[job_id] = job
            return job

    def update(self, job_id: str, **fields) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            for k, v in fields.items():
                setattr(job, k, v)

    def get(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def all(self) -> Dict[str, dict]:
        return {k: v.dict() for k, v in self._jobs.items()}


@lru_cache(maxsize=1)
def get_job_store() -> JobStore:
    return JobStore()


def run_ingestion_job(job_id: str, folder: Optional[str] = None,
                      reset: bool = True) -> None:
    """
    Worker entrypoint. In local mode this is scheduled via BackgroundTasks; in a Celery
    deployment this body becomes the task function (`@celery.task`). It re-imports the
    pipeline lazily so the worker process stays lightweight until a job arrives.
    """
    from app.ingestion.pipeline import IngestionPipeline

    store = get_job_store()
    store.update(job_id, status="running")
    log(logger, "INFO", "ingestion job started", job_id=job_id)
    try:
        pipeline = IngestionPipeline()
        result = pipeline.ingest_folder(Path(folder) if folder else None, reset=reset)
        store.update(job_id, status="completed", finished_at=time.time(),
                     result=result.dict())
        # refresh the served stores so new content is queryable immediately
        _refresh_serving_stores()
        log(logger, "INFO", "ingestion job completed", job_id=job_id, **result.dict())
    except Exception as exc:  # pragma: no cover
        store.update(job_id, status="failed", finished_at=time.time(), error=str(exc))
        log(logger, "ERROR", "ingestion job failed", job_id=job_id, error=str(exc))


def _refresh_serving_stores() -> None:
    """Hot-reload the API's in-memory stores after a successful ingest."""
    try:
        from app import state

        state.reload_stores()
    except Exception:
        pass
