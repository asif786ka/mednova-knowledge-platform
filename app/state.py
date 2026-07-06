"""
Shared serving state: the in-memory stores and the agentic router used by the API.
Kept in one module so background jobs can hot-reload it after ingestion.
"""
from __future__ import annotations

from threading import Lock
from typing import Optional

from app.agents.router import AgenticRouter
from app.ingestion.pipeline import load_stores
from app.observability import get_logger

logger = get_logger("state")

_lock = Lock()
_router: Optional[AgenticRouter] = None
_vector_store = None
_graph_store = None


def reload_stores() -> None:
    global _router, _vector_store, _graph_store
    with _lock:
        _vector_store, _graph_store = load_stores()
        _router = AgenticRouter(_vector_store, _graph_store)
        logger.info("Serving stores reloaded (%d vectors, %d graph nodes)",
                    _vector_store.count(), _graph_store.g.number_of_nodes())


def get_router() -> AgenticRouter:
    global _router
    if _router is None:
        reload_stores()
    return _router  # type: ignore[return-value]


def get_vector_store():
    if _vector_store is None:
        reload_stores()
    return _vector_store


def get_graph_store():
    if _graph_store is None:
        reload_stores()
    return _graph_store
