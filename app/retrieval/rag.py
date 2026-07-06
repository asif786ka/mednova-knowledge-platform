"""
RAG retrieval: embed the query, cosine top-k over the vector store, light lexical rerank,
and assemble a context string plus deduplicated source filenames.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

from app.config import settings
from app.retrieval.embeddings import get_embedder
from app.retrieval.vector_store import SearchHit, VectorStore


@dataclass
class RetrievedContext:
    context: str
    sources: List[str]
    hits: List[SearchHit]
    top_score: float


def _keywords(text: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2}


def _rerank(question: str, hits: List[SearchHit]) -> List[SearchHit]:
    """Blend semantic score with lexical overlap to sharpen ordering on keyword queries."""
    q = _keywords(question)
    if not q:
        return hits
    rescored = []
    for h in hits:
        lex = len(q & _keywords(h.record.text)) / (len(q) or 1)
        blended = 0.75 * h.score + 0.25 * lex
        rescored.append(SearchHit(h.record, blended))
    rescored.sort(key=lambda x: -x.score)
    return rescored


class RAGRetriever:
    def __init__(self, vector_store: VectorStore) -> None:
        self.vector_store = vector_store
        self.embedder = get_embedder()

    def retrieve(self, question: str, top_k: int | None = None,
                 min_score: float | None = None) -> RetrievedContext:
        top_k = top_k or settings.top_k
        min_score = settings.min_score if min_score is None else min_score
        qvec = self.embedder.embed_one(question)
        hits = self.vector_store.search(qvec, top_k=max(top_k * 2, top_k), min_score=0.0)
        hits = _rerank(question, hits)[:top_k]
        hits = [h for h in hits if h.score >= min_score] or hits[:1]

        blocks, sources = [], []
        for h in hits:
            section = h.record.metadata.get("section", "")
            header = f"[{h.record.source}" + (f" — {section}]" if section else "]")
            blocks.append(f"{header}\n{h.record.text}")
            if h.record.source not in sources:
                sources.append(h.record.source)
        top_score = hits[0].score if hits else 0.0
        return RetrievedContext(
            context="\n\n".join(blocks),
            sources=sources,
            hits=hits,
            top_score=top_score,
        )
