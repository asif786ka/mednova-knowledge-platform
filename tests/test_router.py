"""Tests for the agentic router: classification, grounding, and the honesty gate."""
from app.agents.router import AgenticRouter
from app.ingestion.pipeline import load_stores


def _router():
    vs, gs = load_stores()
    return AgenticRouter(vs, gs)


def test_relationship_question_routes_to_graph():
    r = _router()
    route = r.classify("What is the relationship between the knowledge platform, "
                       "Neo4j, and Astra DB?")
    assert route in ("graph", "hybrid")


def test_summary_question_routes_to_summary():
    r = _router()
    assert r.classify("Summarise the architecture of the knowledge platform.") == "summary"


def test_answer_is_source_backed():
    r = _router()
    ans = r.answer("Which projects use LangChain and Neo4j?")
    assert ans.sources, "answer must cite at least one source"
    assert ans.retrieval_strategy
    assert ans.confidence > 0


def test_out_of_domain_is_refused():
    r = _router()
    ans = r.answer("What is the capital of France?")
    assert "enough information" in ans.answer.lower()


def test_graph_relationship_answer_mentions_entities():
    r = _router()
    ans = r.answer("What is the relationship between the knowledge platform, "
                   "Neo4j, and Astra DB?")
    assert any("Neo4j" in e or "Astra" in e for e in ans.related_entities)
