"""
Agentic router — a LangGraph-style state machine that decides *how* to answer.

Flow:  classify -> plan -> retrieve -> synthesize -> verify

The classifier uses cheap, deterministic heuristics (relationship verbs, summary intent,
entity co-occurrence) and selects one of four strategies:

  vector   : semantic document lookup            ("which documents mention X")
  graph    : relationship / connection questions ("relationship between A, B and C")
  hybrid   : both — graph narrows, vector proves ("which projects use both RAG and GraphRAG")
  summary  : broad synthesis                      ("summarise the architecture")

This is implemented as an explicit state machine (rather than importing LangGraph) so the
prototype has zero heavy dependencies, but the node/edge structure maps 1:1 onto a LangGraph
`StateGraph`. The design is documented in SYSTEM_DESIGN.md.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.graph.graphrag import GraphRAG
from app.graph.graph_store import GraphStore
from app.llm.provider import NO_INFO, get_llm_provider
from app.mcp.client import get_mcp_manager
from app.observability import get_logger, trace_event
from app.observability.logging import log
from app.retrieval.prompts import SYSTEM_PROMPT, build_user_prompt
from app.retrieval.rag import RAGRetriever
from app.retrieval.vector_store import VectorStore

logger = get_logger("router")

# Deterministic tool-intent triggers. When one matches AND MCP is available, the agent takes
# the "tool" route and calls the corresponding MCP tool. With a hosted LLM this is replaced by
# native function-calling for open-ended tool selection (see SYSTEM_DESIGN 'MCP tool use').
TOOL_TRIGGERS = {
    "current_datetime": ["current date", "current time", "what time", "today's date",
                         "what is the date", "time is it", "date today", "what day is"],
}

_REL_WORDS = ["relationship", "related", "connected", "connection", "between",
              "belongs", "depends", "link", "associated", "owns", "uses"]
_SUMMARY_WORDS = ["summarise", "summarize", "summary", "overview", "describe the",
                  "explain the architecture"]
_GRAPH_HINT = ["which projects", "which technologies", "which cloud", "which clients",
               "which requirements", "which services", "what risks", "connected to",
               "use both", "uses both"]


@dataclass
class AgentAnswer:
    answer: str
    sources: List[str]
    retrieval_strategy: str
    related_entities: List[str]
    route: str
    confidence: float
    llm_backend: str
    matched_entities: List[str] = field(default_factory=list)
    reasoning: str = ""

    def dict(self) -> Dict:
        return {
            "answer": self.answer,
            "sources": self.sources,
            "retrieval_strategy": self.retrieval_strategy,
            "related_entities": self.related_entities,
            "route": self.route,
            "confidence": round(self.confidence, 3),
            "llm_backend": self.llm_backend,
            "matched_entities": self.matched_entities,
            "reasoning": self.reasoning,
        }


class AgenticRouter:
    def __init__(self, vector_store: VectorStore, graph_store: GraphStore,
                 mcp_manager=None) -> None:
        self.rag = RAGRetriever(vector_store)
        self.graphrag = GraphRAG(graph_store)
        self.llm = get_llm_provider()
        # MCP tool broker (local stdio server by default; remote by config). Optional:
        # if the SDK/servers are unavailable the tool route degrades to vector search.
        self.mcp = mcp_manager if mcp_manager is not None else get_mcp_manager()

    def _match_tool(self, question: str) -> Optional[str]:
        q = question.lower()
        for tool, triggers in TOOL_TRIGGERS.items():
            if any(tr in q for tr in triggers):
                return tool
        return None

    # -- node 1: classify --------------------------------------------------
    def classify(self, question: str) -> str:
        q = question.lower()
        if self._match_tool(question) and self.mcp.available:
            return "tool"
        if any(w in q for w in _SUMMARY_WORDS):
            return "summary"
        rel = any(w in q for w in _REL_WORDS)
        graphy = any(h in q for h in _GRAPH_HINT)
        # entity anchors present in the graph?
        anchors = [k for k in self.graphrag.graph.match_entity(question)
                   if self.graphrag.graph.g.nodes[k].get("type") != "Document"]
        multi_anchor = len(set(self.graphrag.graph.g.nodes[k]["name"] for k in anchors)) >= 2

        if rel and multi_anchor:
            return "graph"
        if graphy and anchors:
            return "hybrid"
        if rel:
            return "graph"
        return "vector"

    # -- orchestration -----------------------------------------------------
    def answer(self, question: str, request_id: Optional[str] = None) -> AgentAnswer:
        route = self.classify(question)
        log(logger, "INFO", "route selected", request_id=request_id,
            route=route, question=question)

        # -- MCP tool route: agent invokes an external tool over MCP --
        if route == "tool":
            tool_name = self._match_tool(question)
            try:
                with trace_event("mcp_tool_call", request_id=request_id, tool=tool_name):
                    output = self.mcp.call_tool(tool_name, {})
                return AgentAnswer(
                    answer=output, sources=[f"mcp://mednova-knowledge/{tool_name}"],
                    retrieval_strategy="mcp_tool", related_entities=[], route="tool",
                    confidence=0.9, llm_backend=self.llm.backend,
                    matched_entities=[tool_name],
                    reasoning=f"Agent selected MCP tool '{tool_name}'.")
            except Exception as exc:  # tool failed -> fall back to normal retrieval
                log(logger, "WARNING", "mcp tool failed; falling back",
                    request_id=request_id, tool=tool_name, error=str(exc))
                route = "vector"

        graph_ctx = None
        rag_ctx = None
        strategy = route

        with trace_event("retrieve", request_id=request_id, route=route):
            if route in ("graph", "hybrid"):
                graph_ctx = self.graphrag.retrieve(question, hops=1)
            if route in ("vector", "hybrid", "summary"):
                top_k = 8 if route == "summary" else None
                rag_ctx = self.rag.retrieve(question, top_k=top_k)
            # graph route with no graph hits -> fall back to vector
            if route == "graph" and (graph_ctx is None or graph_ctx.is_empty()):
                rag_ctx = self.rag.retrieve(question)
                strategy = "graph_fallback_vector"

        vector_context = rag_ctx.context if rag_ctx else ""
        graph_context = graph_ctx.text if graph_ctx else ""
        context_blocks = []
        if graph_context:
            context_blocks.append(graph_context)
        if vector_context:
            context_blocks.append(vector_context)

        # sources + related entities
        sources: List[str] = []
        if graph_ctx:
            sources += graph_ctx.sources
        if rag_ctx:
            sources += rag_ctx.sources
        sources = list(dict.fromkeys(sources))  # dedupe, keep order
        related = graph_ctx.related_entities if graph_ctx else []
        matched = graph_ctx.matched if graph_ctx else []

        # confidence: from vector top score and/or graph match strength
        confidence = 0.0
        if rag_ctx:
            confidence = max(confidence, min(rag_ctx.top_score, 1.0))
        if graph_ctx and not graph_ctx.is_empty():
            confidence = max(confidence, 0.6 + 0.05 * min(len(graph_ctx.facts), 6))

        # -- node: verify (honesty gate) --
        if not context_blocks or confidence < 0.12:
            return AgentAnswer(
                answer=NO_INFO, sources=sources, retrieval_strategy=strategy,
                related_entities=related, route=route, confidence=confidence,
                llm_backend=self.llm.backend, matched_entities=matched,
                reasoning="Retrieval confidence below threshold; refused to guess.")

        # -- node: synthesize --
        strategy_label = {
            "vector": "vector", "graph": "graph", "hybrid": "vector_and_graph",
            "summary": "vector_summary", "graph_fallback_vector": "vector",
        }.get(strategy, strategy)

        with trace_event("synthesize", request_id=request_id, backend=self.llm.backend):
            user_prompt = build_user_prompt(question, vector_context, graph_context)
            llm_resp = self.llm.complete(SYSTEM_PROMPT, user_prompt,
                                         context_blocks=context_blocks)

        return AgentAnswer(
            answer=llm_resp.text,
            sources=sources,
            retrieval_strategy=strategy_label,
            related_entities=related,
            route=route,
            confidence=confidence,
            llm_backend=self.llm.backend,
            matched_entities=matched,
            reasoning=f"Classified as '{route}'; "
                      f"{'graph+vector' if route == 'hybrid' else route} retrieval.",
        )
