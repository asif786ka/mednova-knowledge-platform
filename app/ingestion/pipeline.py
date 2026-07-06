"""
Ingestion pipeline: load -> chunk -> embed -> store vectors -> extract entities/relationships
-> populate graph -> persist. Returns a summary matching the /ingest response contract.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional

from app.config import settings
from app.graph import GraphStore, get_graph_store
from app.ingestion.chunker import chunk_document
from app.ingestion.extractor import extract
from app.ingestion.loaders import LoadedDocument, load_file, load_folder
from app.observability import get_logger, trace_event
from app.observability.logging import log
from app.retrieval import get_embedder
from app.retrieval.vector_store import VectorRecord, VectorStore

logger = get_logger("ingestion")


@dataclass
class IngestResult:
    status: str
    documents_processed: int
    chunks_created: int
    entities_extracted: int
    relationships_created: int
    skipped: List[str]

    def dict(self):
        return asdict(self)


class IngestionPipeline:
    def __init__(self, vector_store: Optional[VectorStore] = None,
                 graph_store: Optional[GraphStore] = None) -> None:
        self.embedder = get_embedder()
        self.vector_store = vector_store or VectorStore(self.embedder.dim)
        self.graph_store = graph_store or GraphStore()

    def _ingest_documents(self, docs: List[LoadedDocument]) -> IngestResult:
        all_records: List[VectorRecord] = []
        all_texts: List[str] = []
        entity_keys = set()
        rel_count = 0
        chunks_total = 0

        for doc in docs:
            chunks = chunk_document(doc.document_id, doc.filename, doc.text)
            chunks_total += len(chunks)
            for ch in chunks:
                all_records.append(VectorRecord(
                    chunk_id=ch.chunk_id,
                    document_id=ch.document_id,
                    source=ch.source,
                    text=ch.text,
                    metadata={"section": ch.section, "doc_type": doc.doc_type,
                              "char_start": ch.char_start, "char_end": ch.char_end},
                ))
                all_texts.append(ch.text)

            # graph population
            entities, rels = extract(doc.document_id, doc.filename, doc.text)
            self.graph_store.upsert_node("Document", doc.filename, doc_type=doc.doc_type)
            for ent in entities:
                self.graph_store.upsert_node(ent.type, ent.name)
                entity_keys.add((ent.type, ent.name.lower()))
            for r in rels:
                src = self.graph_store.upsert_node(r.src_type, r.src_name)
                dst = self.graph_store.upsert_node(r.dst_type, r.dst_name)
                self.graph_store.upsert_edge(src, r.rel, dst)
                rel_count += 1

        if all_records:
            embeddings = self.embedder.embed(all_texts)
            self.vector_store.add(all_records, embeddings)

        return IngestResult(
            status="success",
            documents_processed=len(docs),
            chunks_created=chunks_total,
            entities_extracted=len(entity_keys),
            relationships_created=rel_count,
            skipped=[],
        )

    def ingest_folder(self, folder: Optional[Path] = None,
                      reset: bool = True) -> IngestResult:
        folder = Path(folder or settings.sample_docs_dir)
        with trace_event("ingest_folder", folder=str(folder)):
            if reset:
                self.vector_store.clear()
                self.graph_store.clear()
            skipped: List[str] = []
            docs: List[LoadedDocument] = []
            for path in sorted(folder.rglob("*")):
                if not path.is_file():
                    continue
                try:
                    docs.append(load_file(path))
                except Exception as exc:
                    log(logger, "WARNING", "skipped file", file=path.name, error=str(exc))
                    skipped.append(path.name)
            result = self._ingest_documents(docs)
            result.skipped = skipped
            self._persist()
            log(logger, "INFO", "ingestion complete", **result.dict())
            return result

    def _persist(self) -> None:
        self.vector_store.persist()
        self.graph_store.persist()


def load_stores() -> tuple[VectorStore, GraphStore]:
    """Load persisted stores for serving (used by the API at startup)."""
    embedder = get_embedder()
    vs = VectorStore.load(dim=embedder.dim)
    gs = GraphStore.load()
    return vs, gs
