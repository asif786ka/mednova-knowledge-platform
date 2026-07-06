"""
Generate architecture and data-model diagrams for the MedNova AI Knowledge Platform.

Uses Graphviz (python `graphviz` package + system `dot`) to render:
  - diagrams/architecture_diagram.png
  - diagrams/database_diagram.png

Run:  python diagrams/gen_diagrams.py
"""
import shutil
import tempfile
from pathlib import Path
from graphviz import Digraph

OUT = Path(__file__).resolve().parent
# Render into a writable temp dir (mounted FS blocks Graphviz's cleanup of the
# intermediate .dot file), then copy the finished PNG back into diagrams/.
_TMP = Path(tempfile.mkdtemp(prefix="mednova_diag_"))


def _render(g, name):
    g.render(_TMP / name, cleanup=True)
    shutil.copyfile(_TMP / f"{name}.png", OUT / f"{name}.png")

# ----- palette ------------------------------------------------------------
BLUE = "#1f6fb2"
LBLUE = "#dceaf5"
GREEN = "#2e8b57"
LGREEN = "#dff1e6"
ORANGE = "#d9822b"
LORANGE = "#fbe9d6"
PURPLE = "#7048a6"
LPURPLE = "#ece3f6"
GREY = "#5b6670"
LGREY = "#eef1f4"
RED = "#c0392b"
LRED = "#fbe3e0"


def _node(g, name, label, fill, edge, shape="box"):
    g.node(name, label, shape=shape, style="filled,rounded",
           fillcolor=fill, color=edge, fontname="Helvetica",
           fontsize="10", penwidth="1.4")


def architecture():
    g = Digraph("architecture", format="png")
    g.attr(rankdir="TB", bgcolor="white", splines="spline",
           nodesep="0.35", ranksep="0.55", fontname="Helvetica")
    g.attr("edge", fontname="Helvetica", fontsize="8.5", color=GREY)

    # clients
    with g.subgraph(name="cluster_client") as c:
        c.attr(label="Clients", style="rounded,filled", fillcolor="#f7f9fb",
               color=GREY, fontname="Helvetica-Bold", fontsize="11")
        _node(c, "user", "Employee /\nWeb client\n(Swagger UI, curl, Postman)", LBLUE, BLUE)
        _node(c, "voice", "Voice client\n(transcript / audio)", LBLUE, BLUE)

    # api boundary
    with g.subgraph(name="cluster_api") as c:
        c.attr(label="FastAPI Backend  (Docker container)", style="rounded,filled",
               fillcolor="#f4f8fb", color=BLUE, fontname="Helvetica-Bold", fontsize="11")
        _node(c, "api", "API layer\n/health  /ingest\n/ask  /voice/ask\n(Pydantic validation,\nerror handling)", "#ffffff", BLUE)
        _node(c, "router", "Agentic Router\n(LangGraph-style state machine)\nclassify -> plan -> retrieve -> synthesize", LPURPLE, PURPLE)
        _node(c, "rag", "RAG pipeline\nvector retrieve + rerank", LGREEN, GREEN)
        _node(c, "graphrag", "GraphRAG pipeline\nentity match + neighbourhood\nexpansion", LGREEN, GREEN)
        _node(c, "summ", "Summarise route", LGREEN, GREEN)
        _node(c, "llmabs", "LLM provider layer\n(LiteLLM abstraction +\ndeterministic offline fallback)", LORANGE, ORANGE)
        _node(c, "ingest", "Ingestion worker\n(load -> chunk -> embed ->\nentity/rel extract)", LORANGE, ORANGE)
        _node(c, "cache", "Cache layer\nResponse + embedding cache\n(Redis | in-memory LRU)", LRED, RED)
        _node(c, "queue", "Background queue\n(FastAPI BackgroundTasks\n| Celery-ready)", LRED, RED)
        _node(c, "obs", "Observability\nStructured logs, latency,\ntracing (Langfuse hooks)", LGREY, GREY)
        _node(c, "mcp", "MCP client\n(transport-agnostic:\nstdio | HTTP | SSE)", LPURPLE, PURPLE)

    # data stores
    with g.subgraph(name="cluster_data") as c:
        c.attr(label="Data & Model Layer", style="rounded,filled", fillcolor="#fbfaf7",
               color=ORANGE, fontname="Helvetica-Bold", fontsize="11")
        _node(c, "vdb", "Vector store\nNumPy cosine index\n(Chroma / Astra DB-ready)", "#ffffff", GREEN, shape="cylinder")
        _node(c, "gdb", "Graph store\nNetworkX\n(Neo4j-ready)", "#ffffff", GREEN, shape="cylinder")
        _node(c, "emb", "Embedding model\nsentence-transformers\n(hash fallback)", "#ffffff", ORANGE)
        _node(c, "llm", "LLM provider\nOpenAI / Ollama / local\n(optional)", "#ffffff", ORANGE)
        _node(c, "redis", "Redis\n(cache + broker)", "#ffffff", RED, shape="cylinder")

    # MCP tool servers
    with g.subgraph(name="cluster_mcp") as c:
        c.attr(label="MCP Tool Servers", style="rounded,filled", fillcolor="#f6f2fb",
               color=PURPLE, fontname="Helvetica-Bold", fontsize="11")
        _node(c, "mcp_local", "Local MCP server\n(stdio subprocess)\nsearch_documents,\ngraph_neighbors,\nlist_projects", "#ffffff", PURPLE)
        _node(c, "mcp_remote", "Remote MCP server\n(HTTP / SSE)\n3rd-party tools\n(optional, by config)", "#ffffff", PURPLE)

    # edges
    g.edge("user", "api")
    g.edge("voice", "api", label="STT")
    g.edge("api", "router", label="/ask")
    g.edge("api", "ingest", label="/ingest\n(async)")
    g.edge("api", "cache", label="lookup", style="dashed")
    g.edge("api", "queue", style="dashed")
    g.edge("router", "rag")
    g.edge("router", "graphrag")
    g.edge("router", "summ")
    g.edge("rag", "vdb", label="top-k")
    g.edge("graphrag", "gdb", label="cypher-like\ntraversal")
    g.edge("rag", "llmabs")
    g.edge("graphrag", "llmabs")
    g.edge("summ", "llmabs")
    g.edge("llmabs", "llm", style="dashed", label="if key set")
    g.edge("ingest", "emb")
    g.edge("ingest", "vdb")
    g.edge("ingest", "gdb")
    g.edge("rag", "emb", label="query embed")
    g.edge("cache", "redis", style="dashed")
    g.edge("queue", "redis", style="dashed")
    g.edge("router", "obs", style="dotted", constraint="false")
    g.edge("ingest", "queue", style="dashed", constraint="false")
    g.edge("router", "mcp", label="tool route")
    g.edge("mcp", "mcp_local", label="stdio")
    g.edge("mcp", "mcp_remote", label="HTTP/SSE", style="dashed")

    _render(g, "architecture_diagram")
    print("wrote architecture_diagram.png")


def datamodel():
    g = Digraph("datamodel", format="png")
    g.attr(rankdir="LR", bgcolor="white", splines="spline",
           nodesep="0.4", ranksep="0.7", fontname="Helvetica")
    g.attr("edge", fontname="Helvetica", fontsize="9", color=GREY, fontcolor=BLUE)

    # graph nodes (knowledge graph)
    _node(g, "Client", "Client", LBLUE, BLUE)
    _node(g, "Project", "Project", LGREEN, GREEN)
    _node(g, "Technology", "Technology", LORANGE, ORANGE)
    _node(g, "CloudProvider", "CloudProvider", LORANGE, ORANGE)
    _node(g, "Risk", "Risk", LRED, RED)
    _node(g, "Requirement", "Requirement", LPURPLE, PURPLE)
    _node(g, "Document", "Document", LGREY, GREY)
    _node(g, "Entity", "Entity", LGREY, GREY)

    g.edge("Client", "Project", label="OWNS")
    g.edge("Project", "Technology", label="USES")
    g.edge("Project", "CloudProvider", label="DEPLOYED_ON")
    g.edge("Project", "Risk", label="HAS_RISK")
    g.edge("Requirement", "Project", label="BELONGS_TO")
    g.edge("Document", "Entity", label="MENTIONS")
    g.edge("Document", "Project", label="DESCRIBES")

    # vector-store record (as a record node)
    g.node("chunk",
           "{Vector store record|chunk_id|document_id|source (filename)|text|embedding[384]|char_start / char_end|section}",
           shape="record", style="filled", fillcolor="#ffffff", color=GREEN,
           fontname="Helvetica", fontsize="9")
    g.node("doc",
           "{Document metadata|document_id|filename|doc_type|title|ingested_at|n_chunks}",
           shape="record", style="filled", fillcolor="#ffffff", color=BLUE,
           fontname="Helvetica", fontsize="9")
    g.node("cacherec",
           "{Cached response (Redis/LRU)|key = sha256(question)|answer|sources[]|strategy|ttl}",
           shape="record", style="filled", fillcolor="#ffffff", color=RED,
           fontname="Helvetica", fontsize="9")
    g.node("trace",
           "{Trace / log record|request_id|route|latency_ms|retrieved_chunk_ids|token_usage|timestamp}",
           shape="record", style="filled", fillcolor="#ffffff", color=GREY,
           fontname="Helvetica", fontsize="9")

    g.edge("doc", "chunk", label="1..N split")
    g.edge("chunk", "Entity", label="embeds text\nmentioning", style="dashed")
    g.edge("doc", "Document", label="=", style="dotted")

    _render(g, "database_diagram")
    print("wrote database_diagram.png")


if __name__ == "__main__":
    architecture()
    datamodel()
