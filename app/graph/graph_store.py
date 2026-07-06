"""
Knowledge graph store backed by NetworkX, persisted to JSON.

Node types:   Client, Project, Technology, CloudProvider, Risk, Requirement, Document, Entity
Edge types:   OWNS, USES, DEPLOYED_ON, HAS_RISK, BELONGS_TO, MENTIONS, DESCRIBES

The interface (upsert_node / upsert_edge / neighbors / find_nodes / subgraph) is intentionally
small and Cypher-like so it can be re-implemented against Neo4j without touching callers.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import networkx as nx

from app.config import settings
from app.observability import get_logger

logger = get_logger("graph_store")

NODE_TYPES = ["Client", "Project", "Technology", "CloudProvider",
              "Risk", "Requirement", "Document", "Entity"]


def node_key(node_type: str, name: str) -> str:
    return f"{node_type}::{name.strip().lower()}"


class GraphStore:
    def __init__(self) -> None:
        self.g = nx.MultiDiGraph()

    # -- write -------------------------------------------------------------
    def upsert_node(self, node_type: str, name: str, **props: Any) -> str:
        key = node_key(node_type, name)
        if self.g.has_node(key):
            self.g.nodes[key].setdefault("props", {}).update(props)
        else:
            self.g.add_node(key, type=node_type, name=name.strip(), props=dict(props))
        return key

    def upsert_edge(self, src: str, rel: str, dst: str, **props: Any) -> None:
        # avoid duplicate identical edges
        if self.g.has_edge(src, dst):
            for _, data in self.g.get_edge_data(src, dst).items():
                if data.get("rel") == rel:
                    data.setdefault("props", {}).update(props)
                    return
        self.g.add_edge(src, dst, rel=rel, props=dict(props))

    def clear(self) -> None:
        self.g = nx.MultiDiGraph()

    # -- read --------------------------------------------------------------
    def has_node(self, node_type: str, name: str) -> bool:
        return self.g.has_node(node_key(node_type, name))

    def get_node(self, key: str) -> Optional[dict]:
        return self.g.nodes[key] if self.g.has_node(key) else None

    def find_nodes(self, node_type: Optional[str] = None) -> List[dict]:
        out = []
        for key, data in self.g.nodes(data=True):
            if node_type is None or data.get("type") == node_type:
                out.append({"key": key, **data})
        return out

    def neighbors(self, key: str, rel: Optional[str] = None,
                  direction: str = "both") -> List[Tuple[str, str, dict]]:
        """Return (rel, neighbor_key, neighbor_data) triples for a node."""
        if not self.g.has_node(key):
            return []
        out: List[Tuple[str, str, dict]] = []
        if direction in ("out", "both"):
            for _, dst, data in self.g.out_edges(key, data=True):
                if rel is None or data.get("rel") == rel:
                    out.append((data["rel"], dst, self.g.nodes[dst]))
        if direction in ("in", "both"):
            for src, _, data in self.g.in_edges(key, data=True):
                if rel is None or data.get("rel") == rel:
                    out.append((data["rel"], src, self.g.nodes[src]))
        return out

    def match_entity(self, text: str) -> List[str]:
        """Fuzzy-match a mention against node names; returns node keys."""
        text_l = text.lower()
        matches = []
        for key, data in self.g.nodes(data=True):
            name = data.get("name", "").lower()
            if not name:
                continue
            if name in text_l or text_l in name:
                matches.append((key, len(name)))
        # prefer longer (more specific) name matches
        matches.sort(key=lambda x: -x[1])
        return [k for k, _ in matches]

    def subgraph_around(self, keys: List[str], hops: int = 1) -> nx.MultiDiGraph:
        nodes = set(keys)
        frontier = set(keys)
        for _ in range(hops):
            nxt = set()
            for k in frontier:
                if not self.g.has_node(k):
                    continue
                for _, dst in self.g.out_edges(k):
                    nxt.add(dst)
                for src, _ in self.g.in_edges(k):
                    nxt.add(src)
            nodes |= nxt
            frontier = nxt
        return self.g.subgraph(nodes).copy()

    def stats(self) -> Dict[str, int]:
        by_type: Dict[str, int] = {}
        for _, data in self.g.nodes(data=True):
            by_type[data.get("type", "?")] = by_type.get(data.get("type", "?"), 0) + 1
        return {
            "nodes": self.g.number_of_nodes(),
            "edges": self.g.number_of_edges(),
            **{f"nodes_{k}": v for k, v in by_type.items()},
        }

    # -- persistence -------------------------------------------------------
    def persist(self, path: Optional[Path] = None) -> None:
        path = Path(path or settings.graph_store_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = nx.node_link_data(self.g, edges="links")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        logger.info("Persisted graph: %d nodes / %d edges -> %s",
                    self.g.number_of_nodes(), self.g.number_of_edges(), path)

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "GraphStore":
        path = Path(path or settings.graph_store_path)
        store = cls()
        if not path.exists():
            return store
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        store.g = nx.node_link_graph(data, multigraph=True, directed=True, edges="links")
        logger.info("Loaded graph: %d nodes / %d edges",
                    store.g.number_of_nodes(), store.g.number_of_edges())
        return store


@lru_cache(maxsize=1)
def get_graph_store() -> GraphStore:
    return GraphStore.load()
