"""
MedNova Knowledge — local MCP server (Model Context Protocol).

Exposes the platform's retrieval capabilities as standard MCP *tools* so any MCP client
(this app's agent, Claude Desktop, Cursor, etc.) can call them. Built with FastMCP.

Transport is selected by argument so the SAME server code runs locally over stdio or
remotely over streamable HTTP — this is what makes the deployment "transport-agnostic":

    python mcp_servers/knowledge_server.py                 # stdio (local, default)
    python mcp_servers/knowledge_server.py streamable-http # remote-style HTTP server
    python mcp_servers/knowledge_server.py sse             # SSE server

Tools:
    search_documents(query, k)   -> semantic document search (RAG retrieval)
    graph_neighbors(entity)      -> knowledge-graph relationships for an entity
    list_projects()              -> all projects known to the graph
    current_datetime()           -> server time (a simple non-KB tool, to show tool variety)
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# MCP stdio transport owns stdout for JSON-RPC; force all app logging to stderr BEFORE any
# app import so log lines can never corrupt the protocol stream.
os.environ["LOG_STREAM"] = "stderr"

# ensure the app package is importable when spawned as a subprocess
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mcp.server.fastmcp import FastMCP  # noqa: E402

from app.graph.graphrag import GraphRAG  # noqa: E402
from app.ingestion.pipeline import load_stores  # noqa: E402
from app.retrieval.rag import RAGRetriever  # noqa: E402

mcp = FastMCP("mednova-knowledge")

# stores are loaded once per server process
_VS, _GS = load_stores()
_RAG = RAGRetriever(_VS)
_GRAPHRAG = GraphRAG(_GS)


@mcp.tool()
def search_documents(query: str, k: int = 5) -> str:
    """Semantic search over MedNova documents. Returns the top matching chunks with their
    source filenames. Use for fact-lookup questions like 'which documents mention cloud
    deployment'."""
    ctx = _RAG.retrieve(query, top_k=k)
    if not ctx.hits:
        return "No matching documents found."
    lines = [f"Sources: {', '.join(ctx.sources)}", ""]
    for h in ctx.hits:
        lines.append(f"[{h.record.source}] (score={h.score:.2f})")
        lines.append(h.record.text[:400])
        lines.append("")
    return "\n".join(lines).strip()


@mcp.tool()
def graph_neighbors(entity: str) -> str:
    """Return knowledge-graph relationships connected to an entity (project, technology,
    cloud provider, risk, etc.). Use for relationship questions like 'what is connected to
    the patient assistant platform'."""
    ctx = _GRAPHRAG.retrieve(entity, hops=1)
    if ctx.is_empty():
        return f"No graph relationships found for '{entity}'."
    facts = "\n".join(f"- {f}" for f in ctx.facts)
    related = ", ".join(ctx.related_entities)
    return f"Matched: {', '.join(ctx.matched)}\nRelated entities: {related}\n\nFacts:\n{facts}"


@mcp.tool()
def list_projects() -> str:
    """List all MedNova projects present in the knowledge graph."""
    projects = [n["name"] for n in _GS.find_nodes("Project")]
    return "\n".join(f"- {p}" for p in sorted(projects)) or "No projects found."


@mcp.tool()
def current_datetime() -> str:
    """Return the current UTC date and time (ISO 8601). A generic tool independent of the
    knowledge base, demonstrating mixed tool types via MCP."""
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    transport = sys.argv[1] if len(sys.argv) > 1 else "stdio"
    # FastMCP accepts: "stdio", "streamable-http", "sse"
    mcp.run(transport=transport)
