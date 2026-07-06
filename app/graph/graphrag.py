"""
GraphRAG retrieval.

Matches entities mentioned in the question against knowledge-graph nodes, expands their
neighbourhood (1–2 hops), and renders the relationships as natural-language "facts" that the
LLM (or extractive fallback) can ground on. Also returns the related entity names and the
source documents that mention those entities — so graph answers are still source-backed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from app.graph.graph_store import GraphStore

REL_PHRASE = {
    "OWNS": "owns",
    "USES": "uses",
    "DEPLOYED_ON": "is deployed on",
    "HAS_RISK": "has risk",
    "BELONGS_TO": "belongs to",
    "MENTIONS": "mentions",
    "DESCRIBES": "describes",
}


@dataclass
class GraphContext:
    facts: List[str] = field(default_factory=list)
    related_entities: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    matched: List[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(f"- {f}" for f in self.facts)

    def is_empty(self) -> bool:
        return not self.facts


class GraphRAG:
    def __init__(self, graph_store: GraphStore) -> None:
        self.graph = graph_store

    def retrieve(self, question: str, hops: int = 1, max_facts: int = 40) -> GraphContext:
        matched_keys = self.graph.match_entity(question)
        # keep the most specific matches, skip generic Document nodes as anchors
        anchors = [k for k in matched_keys
                   if self.graph.g.nodes[k].get("type") != "Document"][:6]
        ctx = GraphContext(matched=[self.graph.g.nodes[k]["name"] for k in anchors])
        if not anchors:
            return ctx

        related = set()
        docs = set()
        facts = []
        seen_fact = set()

        sub = self.graph.subgraph_around(anchors, hops=hops)
        for src, dst, data in sub.edges(data=True):
            sname = sub.nodes[src]["name"]
            dname = sub.nodes[dst]["name"]
            stype = sub.nodes[src]["type"]
            dtype = sub.nodes[dst]["type"]
            rel = data.get("rel", "")
            phrase = REL_PHRASE.get(rel, rel.lower())
            fact = f"{stype} '{sname}' {phrase} {dtype} '{dname}'."
            if fact not in seen_fact:
                seen_fact.add(fact)
                facts.append(fact)
            if stype == "Document":
                docs.add(sname)
            if dtype == "Document":
                docs.add(dname)
            for nm, ty in ((sname, stype), (dname, dtype)):
                if ty not in ("Document", "Requirement"):
                    related.add(nm)

        # provenance: documents that MENTION any anchor entity
        for k in anchors:
            for rel, nb_key, nb in self.graph.neighbors(k, rel="MENTIONS", direction="in"):
                if nb.get("type") == "Document":
                    docs.add(nb["name"])

        ctx.facts = facts[:max_facts]
        ctx.related_entities = sorted(related)
        ctx.sources = sorted(docs)
        return ctx
