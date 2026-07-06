"""
End-to-end demo: ingest the sample docs, then run the 12 assessment questions through the
agent and print routed, source-backed answers. Produces demo evidence for the README.

Usage:  python scripts/demo.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.ingestion.pipeline import IngestionPipeline, load_stores  # noqa: E402
from app.agents.router import AgenticRouter  # noqa: E402

QUESTIONS = [
    "Which MedNova projects use AI automation?",
    "Which documents mention cloud deployment?",
    "What risks are mentioned across the project documents?",
    "Which technologies are connected to the patient assistant platform?",
    "Which projects use LangChain?",
    "Which services are related to patient engagement?",
    "What is the relationship between the knowledge platform, Neo4j, and Astra DB?",
    "Which requirements mention voice-based AI?",
    "Which cloud providers are mentioned in the documents?",
    "Summarise the architecture of the MedNova AI knowledge platform.",
    "Which projects use both RAG and GraphRAG?",
    "What are the main implementation challenges mentioned in the documents?",
]


def main():
    print("Ingesting sample documents...")
    res = IngestionPipeline().ingest_folder()
    print(f"  {res.documents_processed} docs, {res.chunks_created} chunks, "
          f"{res.entities_extracted} entities, {res.relationships_created} relationships\n")

    vs, gs = load_stores()
    router = AgenticRouter(vs, gs)

    for i, q in enumerate(QUESTIONS, 1):
        a = router.answer(q)
        print(f"[{i:>2}] Q: {q}")
        print(f"     route={a.route}  strategy={a.retrieval_strategy}  "
              f"confidence={a.confidence:.2f}")
        print(f"     A: {a.answer.strip()[:320]}")
        print(f"     sources: {', '.join(a.sources) or '-'}")
        if a.related_entities:
            print(f"     related: {', '.join(a.related_entities[:8])}")
        print()


if __name__ == "__main__":
    main()
