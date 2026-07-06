"""
Vector store: an in-process NumPy cosine index persisted to disk.

The public interface (add / search / persist / load / count) mirrors what a Chroma or
Astra DB collection exposes, so the RAG pipeline is agnostic to the backend. To move to a
managed vector DB, implement the same methods against Astra DB / Chroma and swap the factory.
"""
from __future__ import annotations

import pickle
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from app.config import settings
from app.observability import get_logger

logger = get_logger("vector_store")


@dataclass
class VectorRecord:
    chunk_id: str
    document_id: str
    source: str          # filename
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchHit:
    record: VectorRecord
    score: float


class VectorStore:
    def __init__(self, dim: int) -> None:
        self.dim = dim
        self._matrix: Optional[np.ndarray] = None   # (N, dim) normalised
        self._records: List[VectorRecord] = []

    # -- write -------------------------------------------------------------
    def add(self, records: List[VectorRecord], embeddings: np.ndarray) -> None:
        if not records:
            return
        embeddings = np.asarray(embeddings, dtype=np.float32)
        if self._matrix is None:
            self._matrix = embeddings
        else:
            self._matrix = np.vstack([self._matrix, embeddings])
        self._records.extend(records)

    def clear(self) -> None:
        self._matrix = None
        self._records = []

    # -- read --------------------------------------------------------------
    def count(self) -> int:
        return len(self._records)

    def search(self, query_vec: np.ndarray, top_k: int = 5,
               min_score: float = 0.0) -> List[SearchHit]:
        if self._matrix is None or len(self._records) == 0:
            return []
        q = np.asarray(query_vec, dtype=np.float32).reshape(-1)
        # matrix is normalised and q from the embedder is normalised -> dot = cosine
        scores = self._matrix @ q
        k = min(top_k, len(self._records))
        idx = np.argpartition(-scores, k - 1)[:k]
        idx = idx[np.argsort(-scores[idx])]
        hits = [SearchHit(self._records[i], float(scores[i])) for i in idx
                if float(scores[i]) >= min_score]
        return hits

    # -- persistence -------------------------------------------------------
    def persist(self, path: Optional[Path] = None) -> None:
        path = Path(path or settings.vector_store_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "dim": self.dim,
            "matrix": self._matrix,
            "records": [asdict(r) for r in self._records],
        }
        with open(path, "wb") as fh:
            pickle.dump(payload, fh)
        logger.info("Persisted vector store: %d records -> %s", self.count(), path)

    @classmethod
    def load(cls, path: Optional[Path] = None, dim: Optional[int] = None) -> "VectorStore":
        path = Path(path or settings.vector_store_path)
        store = cls(dim or settings.embed_dim)
        if not path.exists():
            return store
        with open(path, "rb") as fh:
            payload = pickle.load(fh)
        store.dim = payload["dim"]
        store._matrix = payload["matrix"]
        store._records = [VectorRecord(**r) for r in payload["records"]]
        logger.info("Loaded vector store: %d records", store.count())
        return store
