"""
Graph visualisation export.

Renders the knowledge graph to:
  - diagrams/knowledge_graph.png  (Graphviz, static)
  - diagrams/knowledge_graph.html (pyvis interactive, if installed)

Run: python -m app.graph.viz
"""
from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path

from app.config import BASE_DIR
from app.graph.graph_store import GraphStore

COLORS = {
    "Client": "#1f6fb2", "Project": "#2e8b57", "Technology": "#d9822b",
    "CloudProvider": "#7048a6", "Risk": "#c0392b", "Requirement": "#8a6d3b",
    "Document": "#5b6670", "Entity": "#888888",
}
OUT_DIR = BASE_DIR / "diagrams"


def _safe_id(key: str) -> str:
    return "n_" + re.sub(r"[^0-9a-zA-Z]+", "_", key)


def render_png(graph: GraphStore, out: Path | None = None) -> Path:
    from graphviz import Digraph

    out = out or (OUT_DIR / "knowledge_graph.png")
    g = Digraph("kg", format="png")
    g.attr(rankdir="LR", bgcolor="white", fontname="Helvetica", overlap="false")
    g.attr("node", style="filled,rounded", shape="box", fontname="Helvetica",
           fontsize="9", color="#333333")
    # skip Requirement nodes in the static view to reduce clutter
    for node in graph.find_nodes():
        if node["type"] == "Requirement":
            continue
        g.node(_safe_id(node["key"]), node["name"],
               fillcolor=COLORS.get(node["type"], "#dddddd"), fontcolor="white"
               if node["type"] in ("Client", "Project", "Risk", "CloudProvider") else "black")
    for src, dst, data in graph.g.edges(data=True):
        if graph.g.nodes[src].get("type") == "Requirement" or \
           graph.g.nodes[dst].get("type") == "Requirement":
            continue
        g.edge(_safe_id(src), _safe_id(dst), label=data.get("rel", ""),
               fontsize="7", color="#888888")

    tmp = Path(tempfile.mkdtemp(prefix="kg_"))
    g.render(tmp / "kg", cleanup=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(tmp / "kg.png", out)
    return out


def render_html(graph: GraphStore, out: Path | None = None) -> Path | None:
    out = out or (OUT_DIR / "knowledge_graph.html")
    try:
        from pyvis.network import Network
    except Exception:
        return None
    net = Network(height="720px", width="100%", directed=True, bgcolor="#ffffff",
                  cdn_resources="in_line")
    for node in graph.find_nodes():
        net.add_node(_safe_id(node["key"]), label=node["name"],
                     color=COLORS.get(node["type"], "#dddddd"),
                     title=f"{node['type']}: {node['name']}")
    for src, dst, data in graph.g.edges(data=True):
        net.add_edge(_safe_id(src), _safe_id(dst), label=data.get("rel", ""))
    out.parent.mkdir(parents=True, exist_ok=True)
    net.write_html(str(out))
    return out


if __name__ == "__main__":
    gs = GraphStore.load()
    png = render_png(gs)
    print("wrote", png)
    html = render_html(gs)
    print("wrote", html if html else "(pyvis not installed; skipped html)")
