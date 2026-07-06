"""
Entity & relationship extraction (rule + dictionary based).

Design choice: for a small, controlled corpus a curated dictionary + light pattern matching
gives high-precision entities and clean relationships without the cost/latency/nondeterminism
of an LLM NER call. The interface returns (entities, relationships) so it can later be swapped
for an LLM extractor (documented in SYSTEM_DESIGN "Future improvements") with no downstream
changes. Each document is anchored to a primary Project + Client (from its metadata/name), and
technologies / cloud providers / risks found in that document are linked to that project.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# ---- canonical vocabularies ------------------------------------------------
TECHNOLOGIES: Dict[str, List[str]] = {
    "LangChain": ["langchain"],
    "LangGraph": ["langgraph"],
    "Neo4j": ["neo4j"],
    "Astra DB": ["astra db", "astradb", "astra"],
    "FastAPI": ["fastapi"],
    "Redis": ["redis"],
    "Kafka": ["kafka"],
    "PostgreSQL": ["postgresql", "postgres"],
    "Prometheus": ["prometheus"],
    "Grafana": ["grafana"],
    "Twilio": ["twilio"],
    "Whisper": ["whisper"],
    "Speech-to-Text": ["speech-to-text", "speech to text", "stt"],
    "Text-to-Speech": ["text-to-speech", "text to speech", "tts"],
    "RAG": ["rag", "retrieval-augmented generation", "retrieval augmented generation"],
    "GraphRAG": ["graphrag", "graph rag"],
    "Langfuse": ["langfuse"],
    "LiteLLM": ["litellm"],
    "Python": ["python"],
    "AI automation": ["ai automation"],
}

CLOUD_PROVIDERS: Dict[str, List[str]] = {
    "AWS": ["aws", "amazon web services", "ecs", "fargate", "lambda", "elasticache"],
    "Microsoft Azure": ["azure", "aks"],
    "Google Cloud Platform": ["gcp", "google cloud platform", "gke"],
}

PROJECTS: Dict[str, List[str]] = {
    "MedNova Knowledge Platform": ["mednova knowledge platform", "knowledge platform"],
    "Patient Assistant Platform": ["patient assistant platform", "patient assistant"],
    "Remote Care Platform": ["remote care platform", "remote care"],
    "Operational Insights Service": ["operational insights service", "operational insights"],
}

RISK_KEYWORDS = [
    "data-privacy risk", "data privacy risk", "hipaa", "privacy risk",
    "hallucination risk", "latency risk", "vendor lock-in risk",
    "speech-recognition-accuracy risk", "speech recognition accuracy risk",
    "scalability risk",
]
RISK_CANON = {
    "hipaa": "Data privacy / HIPAA risk",
    "data-privacy risk": "Data privacy / HIPAA risk",
    "data privacy risk": "Data privacy / HIPAA risk",
    "privacy risk": "Data privacy / HIPAA risk",
    "hallucination risk": "Model hallucination risk",
    "latency risk": "Latency risk",
    "vendor lock-in risk": "Vendor lock-in risk",
    "speech-recognition-accuracy risk": "Speech recognition accuracy risk",
    "speech recognition accuracy risk": "Speech recognition accuracy risk",
    "scalability risk": "Scalability risk",
}


@dataclass
class Entity:
    type: str   # Technology | CloudProvider | Project | Client | Risk | Requirement
    name: str


@dataclass
class Relationship:
    src_type: str
    src_name: str
    rel: str
    dst_type: str
    dst_name: str


def _find_terms(text_l: str, vocab: Dict[str, List[str]]) -> List[str]:
    found = []
    for canon, aliases in vocab.items():
        for a in aliases:
            if re.search(rf"(?<![a-z0-9]){re.escape(a)}(?![a-z0-9])", text_l):
                found.append(canon)
                break
    return found


def _meta(text: str, label: str) -> Optional[str]:
    m = re.search(rf"\*\*{label}:\*\*\s*(.+)", text)
    if m:
        return re.sub(r"\s*\(.*?\)\s*$", "", m.group(1)).strip()
    return None


def _primary_project(text: str, filename: str) -> Optional[str]:
    meta = _meta(text, "Project")
    if meta:
        for canon, aliases in PROJECTS.items():
            if meta.lower() in [a for a in aliases] or canon.lower() == meta.lower():
                return canon
        return meta
    text_l = text.lower()
    hits = _find_terms(text_l, PROJECTS)
    return hits[0] if hits else None


def extract(document_id: str, filename: str, text: str
            ) -> Tuple[List[Entity], List[Relationship]]:
    text_l = text.lower()
    entities: List[Entity] = []
    rels: List[Relationship] = []
    seen_ent = set()

    def add_entity(etype: str, name: str):
        key = (etype, name.lower())
        if key not in seen_ent:
            seen_ent.add(key)
            entities.append(Entity(etype, name))

    techs = _find_terms(text_l, TECHNOLOGIES)
    clouds = _find_terms(text_l, CLOUD_PROVIDERS)
    for t in techs:
        add_entity("Technology", t)
    for c in clouds:
        add_entity("CloudProvider", c)

    # risks
    risks = []
    for kw in RISK_KEYWORDS:
        if kw in text_l:
            canon = RISK_CANON[kw]
            if canon not in risks:
                risks.append(canon)
                add_entity("Risk", canon)

    # primary project + client
    project = _primary_project(text, filename)
    client = _meta(text, "Client")
    if project:
        add_entity("Project", project)
    if client:
        add_entity("Client", client)

    # requirements: lines that state a requirement
    for line in text.splitlines():
        ls = line.strip("-* ").strip()
        low = ls.lower()
        if not ls or len(ls) > 180:
            continue
        if re.search(r"\b(require[sd]?|must|required)\b", low) and len(ls) > 15:
            req_name = ls.rstrip(".")
            add_entity("Requirement", req_name)
            if project:
                rels.append(Relationship("Requirement", req_name, "BELONGS_TO",
                                         "Project", project))

    # relationships anchored to the primary project
    if project:
        rels.append(Relationship("Document", filename, "DESCRIBES", "Project", project))
        if client:
            rels.append(Relationship("Client", client, "OWNS", "Project", project))
        for t in techs:
            rels.append(Relationship("Project", project, "USES", "Technology", t))
        for c in clouds:
            rels.append(Relationship("Project", project, "DEPLOYED_ON",
                                     "CloudProvider", c))
        for r in risks:
            rels.append(Relationship("Project", project, "HAS_RISK", "Risk", r))

    # Document MENTIONS every entity (for provenance)
    for ent in list(entities):
        if ent.type in ("Technology", "CloudProvider", "Project", "Risk"):
            rels.append(Relationship("Document", filename, "MENTIONS",
                                     ent.type, ent.name))

    return entities, rels
