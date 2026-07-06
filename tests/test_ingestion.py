"""Unit tests for ingestion, chunking, and entity/relationship extraction."""
from app.ingestion.chunker import chunk_document
from app.ingestion.extractor import extract
from app.ingestion.pipeline import IngestionPipeline


def test_chunking_overlap_and_sections():
    text = "# Title\n\n" + ("Sentence about LangChain. " * 60)
    chunks = chunk_document("doc1", "doc1.md", text, chunk_size=200, overlap=40)
    assert len(chunks) >= 2
    assert all(c.source == "doc1.md" for c in chunks)
    assert chunks[0].section == "Title"


def test_extractor_finds_tech_and_relationships():
    text = ("**Client:** St. Aldwyn Hospital\n**Project:** Patient Assistant Platform\n"
            "The platform uses Speech-to-Text and LangChain and is deployed on Microsoft Azure. "
            "It requires voice-based AI. There is a hallucination risk.")
    entities, rels = extract("d", "patient_assistant_project_brief.md", text)
    etypes = {(e.type, e.name) for e in entities}
    assert ("Technology", "Speech-to-Text") in etypes
    assert ("Technology", "LangChain") in etypes
    assert ("CloudProvider", "Microsoft Azure") in etypes
    assert ("Project", "Patient Assistant Platform") in etypes
    rel_tuples = {(r.src_type, r.rel, r.dst_type) for r in rels}
    assert ("Project", "USES", "Technology") in rel_tuples
    assert ("Project", "DEPLOYED_ON", "CloudProvider") in rel_tuples
    assert ("Client", "OWNS", "Project") in rel_tuples


def test_full_pipeline_populates_stores():
    p = IngestionPipeline()
    res = p.ingest_folder()
    assert res.documents_processed >= 6
    assert res.chunks_created > 0
    assert res.entities_extracted > 10
    assert res.relationships_created > 10
    stats = p.graph_store.stats()
    assert stats["nodes_Project"] >= 3
    assert stats["nodes_Technology"] >= 5
