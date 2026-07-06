"""
Embedding layer.

Primary: sentence-transformers (all-MiniLM-L6-v2) when installed and downloadable.
Fallback: a deterministic hashing embedder (character n-gram feature hashing) that needs
no model download and keeps the whole system runnable fully offline. Both produce L2-
normalised vectors so cosine similarity == dot product.
"""
from __future__ import annotations

import hashlib
import re
from functools import lru_cache
from typing import List

import numpy as np

from app.config import settings
from app.observability import get_logger

logger = get_logger("embeddings")
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _normalise(v: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(v, axis=-1, keepdims=True)
    norm[norm == 0] = 1.0
    return v / norm


class Embedder:
    """Unified embedding interface with a backend name for /health reporting."""

    def __init__(self) -> None:
        self.dim = settings.embed_dim
        self.backend = "hash"
        self._model = None
        if not settings.force_hash_embeddings:
            self._try_load_sentence_transformers()

    def _try_load_sentence_transformers(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(settings.embed_model)
            self.dim = self._model.get_sentence_embedding_dimension()
            self.backend = f"sentence-transformers:{settings.embed_model.split('/')[-1]}"
            logger.info("Loaded embedding model %s", settings.embed_model)
        except Exception as exc:  # offline / not installed -> fallback
            logger.info("sentence-transformers unavailable (%s); using hash embedder", exc)
            self._model = None
            self.backend = "hash"
            self.dim = settings.embed_dim

    # -- hashing fallback --------------------------------------------------
    def _hash_embed_one(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim, dtype=np.float32)
        tokens = _TOKEN_RE.findall(text.lower())
        if not tokens:
            return vec
        # unigrams + bigrams -> feature hashing with signed buckets
        grams = tokens + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:])]
        for g in grams:
            h = int(hashlib.md5(g.encode()).hexdigest(), 16)
            idx = h % self.dim
            sign = 1.0 if (h >> 1) % 2 == 0 else -1.0
            vec[idx] += sign
        return vec

    # -- public API --------------------------------------------------------
    def embed(self, texts: List[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        if self._model is not None:
            vecs = self._model.encode(texts, normalize_embeddings=True,
                                      show_progress_bar=False)
            return np.asarray(vecs, dtype=np.float32)
        vecs = np.vstack([self._hash_embed_one(t) for t in texts])
        return _normalise(vecs).astype(np.float32)

    def embed_one(self, text: str) -> np.ndarray:
        return self.embed([text])[0]


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    return Embedder()
