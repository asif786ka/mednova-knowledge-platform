"""Integration tests for the FastAPI endpoints."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["vector_db"] == "connected"
    assert body["graph_db"] == "connected"
    assert body["documents_indexed"] > 0


def test_ask_returns_sources():
    r = client.post("/ask", json={"question": "Which projects use LangChain and Neo4j?"})
    assert r.status_code == 200
    body = r.json()
    assert body["sources"]
    assert body["retrieval_strategy"]
    assert "latency_ms" in body


def test_ask_cache_hit():
    q = {"question": "Which cloud providers are mentioned in the documents?"}
    first = client.post("/ask", json=q).json()
    second = client.post("/ask", json=q).json()
    assert first["cached"] is False
    assert second["cached"] is True


def test_ask_validation_error():
    assert client.post("/ask", json={"question": "a"}).status_code == 422
    assert client.post("/ask", json={}).status_code == 422


def test_voice_ask():
    r = client.post("/voice/ask",
                    json={"transcript": "Which requirements mention voice-based AI?"})
    assert r.status_code == 200
    body = r.json()
    assert body["transcript"]
    assert body["speech_text"]


def test_voice_ask_requires_transcript():
    assert client.post("/voice/ask", json={}).status_code == 422


def test_graph_stats():
    r = client.get("/graph/stats")
    assert r.status_code == 200
    assert r.json()["nodes"] > 0
