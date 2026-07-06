"""
Build the architecture / system-design PDF for the MedNova AI Knowledge Platform.
Embeds the Graphviz-rendered diagrams and the design narrative.

Run:  python diagrams/build_pdf.py   ->  MedNova_Architecture_and_System_Design.pdf
"""
import tempfile
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak,
    HRFlowable,
)
from reportlab.lib.utils import ImageReader

ROOT = Path(__file__).resolve().parent.parent
DIAG = ROOT / "diagrams"
OUT = ROOT / "MedNova_Architecture_and_System_Design.pdf"

BLUE = colors.HexColor("#1f6fb2")
DARK = colors.HexColor("#22303c")
GREY = colors.HexColor("#5b6670")
LGREY = colors.HexColor("#eef1f4")

styles = getSampleStyleSheet()
styles.add(ParagraphStyle("H1", parent=styles["Heading1"], fontSize=17,
                          textColor=BLUE, spaceBefore=6, spaceAfter=8))
styles.add(ParagraphStyle("H2", parent=styles["Heading2"], fontSize=12.5,
                          textColor=DARK, spaceBefore=12, spaceAfter=4))
styles.add(ParagraphStyle("Body", parent=styles["BodyText"], fontSize=9.7,
                          leading=14, alignment=TA_LEFT, spaceAfter=6,
                          textColor=colors.HexColor("#1b1b1b")))
styles.add(ParagraphStyle("MnBullet", parent=styles["Body"], leftIndent=12,
                          bulletIndent=2, spaceAfter=2))
styles.add(ParagraphStyle("Small", parent=styles["Body"], fontSize=8.4,
                          textColor=GREY))
styles.add(ParagraphStyle("Cover", parent=styles["Title"], fontSize=26,
                          textColor=BLUE, leading=30))
styles.add(ParagraphStyle("CoverSub", parent=styles["Body"], fontSize=12,
                          textColor=GREY, leading=18))
styles.add(ParagraphStyle("MnCode", parent=styles["BodyText"], fontName="Courier",
                          fontSize=8, leading=10.5, backColor=LGREY,
                          borderPadding=6, textColor=DARK))


def P(t, s="Body"):
    return Paragraph(t, styles[s])


def B(t):
    return Paragraph(t, styles["MnBullet"], bulletText="•")


def scaled_image(path, max_w):
    ir = ImageReader(str(path))
    iw, ih = ir.getSize()
    w = max_w
    h = ih * (w / iw)
    return Image(str(path), width=w, height=h)


def infobox(rows):
    t = Table(rows, colWidths=[4.2 * cm, 12.3 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), LGREY),
        ("TEXTCOLOR", (0, 0), (0, -1), DARK),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.6),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.white),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def hr():
    return HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#c9d3dc"),
                      spaceBefore=4, spaceAfter=8)


def build():
    story = []
    W = A4[0] - 4 * cm

    # ---- cover ----
    story += [Spacer(1, 3.2 * cm)]
    story.append(P("MedNova Solutions", "CoverSub"))
    story.append(P("Agentic AI Knowledge Platform", "Cover"))
    story.append(Spacer(1, 0.3 * cm))
    story.append(P("Architecture &amp; System Design", "H2"))
    story.append(Spacer(1, 0.5 * cm))
    story.append(P("A prototype internal knowledge assistant combining Retrieval-Augmented "
                   "Generation (RAG), a knowledge graph (GraphRAG), and an agentic router "
                   "behind a FastAPI backend. Designed to run fully self-contained with zero "
                   "API keys, and to scale to managed cloud services (OpenAI, Neo4j, Astra DB, "
                   "Redis) by configuration alone.", "Body"))
    story.append(Spacer(1, 0.6 * cm))
    story.append(infobox([
        ["Prepared for", "AI/ML Engineer Take-Home Assessment — AWTG"],
        ["Author", "Asif"],
        ["Deliverable", "8.3 Architecture Diagram + 8.4 Data Model + SYSTEM_DESIGN"],
        ["Runtime posture", "Self-contained / offline-first, key-optional (LiteLLM)"],
    ]))
    story.append(PageBreak())

    # ---- 1. context ----
    story.append(P("1. Problem &amp; Design Goals", "H1"))
    story.append(hr())
    story.append(P("MedNova Solutions is a healthcare-technology company whose internal knowledge "
                   "is scattered across project briefs, architecture notes, meeting summaries, "
                   "risk assessments and requirements. Employees waste time searching manually and "
                   "re-asking the same questions. The platform lets an employee ask a natural-language "
                   "question and receive a <b>reliable, source-backed answer</b> — not a generic chatbot "
                   "reply, but one grounded in the company's own documents and the relationships between "
                   "projects, technologies, risks and requirements.", "Body"))
    story.append(P("Design goals that shaped every decision below:", "Body"))
    story.append(B("<b>Grounded &amp; honest.</b> Every answer cites source documents and the system "
                   "explicitly says when the documents do not contain the answer."))
    story.append(B("<b>Runs anywhere in minutes.</b> Zero mandatory API keys or cloud accounts; "
                   "local embeddings, an in-process vector index and an in-memory graph mean a "
                   "reviewer can clone and run immediately."))
    story.append(B("<b>Swap-by-config to production.</b> Each layer hides behind an interface so "
                   "OpenAI, Neo4j, Astra DB and Redis can replace the local defaults without code "
                   "changes."))
    story.append(B("<b>Relationships are first-class.</b> A knowledge graph answers connection "
                   "questions (\"what is the relationship between the platform, Neo4j and Astra DB?\") "
                   "that pure vector search handles poorly."))

    # ---- 2. architecture diagram ----
    story.append(P("2. System Architecture", "H1"))
    story.append(hr())
    story.append(P("A request enters the FastAPI backend, which validates it and checks the cache. "
                   "On a miss, the <b>agentic router</b> classifies the question and dispatches it to "
                   "the RAG pipeline, the GraphRAG pipeline, a summarisation route, or a combination. "
                   "Retrieved context is passed to the LLM provider layer, which uses a real LLM when a "
                   "key is configured and otherwise falls back to a deterministic, extractive answerer "
                   "that composes a grounded answer straight from the retrieved chunks. Ingestion runs "
                   "as a background task so large uploads never block the API.", "Body"))
    story.append(Spacer(1, 0.2 * cm))
    story.append(scaled_image(DIAG / "architecture_diagram.png", W))
    story.append(P("Figure 1 — End-to-end architecture. Dashed edges are optional / config-gated "
                   "(Redis, managed LLM). Cylinders are data stores.", "Small"))
    story.append(PageBreak())

    # ---- 3. components ----
    story.append(P("3. Component Responsibilities", "H1"))
    story.append(hr())
    comp = [
        ["API layer", "FastAPI. Endpoints /health, /ingest, /ask, /voice/ask. Pydantic request/"
                       "response models, input validation, structured error handling, per-request id."],
        ["Agentic router", "LangGraph-style state machine: classify -> plan -> retrieve -> "
                            "synthesize -> verify. Rule + heuristic classifier selects vector, "
                            "graph, hybrid or summary route; falls back to hybrid when uncertain."],
        ["RAG pipeline", "Embeds the query, runs cosine top-k over the vector store, applies a light "
                         "lexical rerank, and builds a grounded, citation-carrying prompt."],
        ["GraphRAG pipeline", "Matches entities in the question, expands their neighbourhood in the "
                              "graph (1–2 hops), and returns connected projects / tech / risks plus the "
                              "supporting documents. Combined with vector hits for hybrid questions."],
        ["LLM provider layer", "LiteLLM-style abstraction. One interface, many providers (OpenAI, "
                               "Ollama, local). Deterministic extractive fallback guarantees offline "
                               "operation and reduces hallucination."],
        ["Ingestion worker", "Loads .md/.txt/.pdf/.docx, chunks with overlap, embeds, and extracts "
                             "entities + relationships into the graph. Runs via the background queue."],
        ["Vector store", "NumPy cosine index persisted to disk. Interface mirrors Chroma / Astra DB "
                         "so it can be swapped with no caller changes."],
        ["Graph store", "NetworkX multi-digraph persisted to JSON; Cypher-like helpers. Neo4j-ready "
                        "via the same GraphStore interface."],
        ["Cache layer", "Response + embedding cache. Redis when REDIS_URL is set, otherwise an "
                        "in-memory TTL-LRU. Keyed by sha256(question)."],
        ["Queue / background", "FastAPI BackgroundTasks for async ingestion; Celery-ready design "
                              "documented for horizontal scaling."],
        ["Observability", "Structured JSON logs, per-request latency, route + retrieval traces, "
                          "optional Langfuse tracing when keys are present."],
        ["MCP client", "Transport-agnostic Model Context Protocol client. Talks to a local "
                       "stdio tool server today and remote HTTP/SSE servers by config only. "
                       "Lets the agent invoke external tools; degrades gracefully if absent."],
    ]
    t = Table([[Paragraph(f"<b>{a}</b>", styles["Small"]), Paragraph(b, styles["Small"])]
               for a, b in comp], colWidths=[3.4 * cm, 13.1 * cm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, LGREY]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#d5dde4")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t)

    # ---- 4. agentic flow ----
    story.append(P("4. Agentic Workflow &amp; Routing", "H1"))
    story.append(hr())
    story.append(P("The router is the heart of the \"agentic\" behaviour: it decides <i>how</i> to "
                   "answer rather than blindly running one pipeline. Classification uses cheap "
                   "heuristics first (relationship verbs, entity co-occurrence, summary intent) and can "
                   "escalate to an LLM classifier when a key is available.", "Body"))
    story.append(infobox([
        ["Vector route", "Fact-lookup / \"which documents mention X\" — semantic top-k retrieval."],
        ["Graph route", "Relationship questions — \"relationship between A, B and C\", \"what is "
                        "connected to the patient assistant\"."],
        ["Hybrid route", "\"Which projects use both RAG and GraphRAG\" — graph narrows candidates, "
                         "vector supplies evidence sentences."],
        ["Summary route", "\"Summarise the architecture\" — broad multi-chunk retrieval + summarise "
                          "prompt."],
        ["Voice route", "/voice/ask — transcript (or STT) -> same router -> optional TTS."],
        ["Tool route", "Invokes an external tool over MCP (e.g. live data). Local stdio "
                       "server now; remote HTTP/SSE servers by config."],
    ]))
    story.append(P("Every route ends in a <b>verify</b> step: if retrieval confidence is below "
                   "threshold, the system returns an explicit \"not enough information in the "
                   "documents\" answer instead of guessing.", "Body"))
    story.append(P("<b>External tools via MCP.</b> The agent can also call tools through a "
                   "transport-agnostic <b>Model Context Protocol</b> client. A local MCP server "
                   "(spawned over stdio) exposes the platform's own retrieval as standard tools "
                   "(<i>search_documents, graph_neighbors, list_projects</i>) plus generic tools; "
                   "switching to a <b>remote</b> MCP server is a pure config change "
                   "(stdio → HTTP/SSE), so third-party or shared tool servers plug in without "
                   "code changes. If the MCP layer is unavailable the tool route degrades to "
                   "vector search.", "Body"))
    story.append(PageBreak())

    # ---- 5. data model ----
    story.append(P("5. Data &amp; Knowledge Model", "H1"))
    story.append(hr())
    story.append(P("Two complementary stores. The <b>vector store</b> holds chunk embeddings for "
                   "semantic recall. The <b>knowledge graph</b> holds typed entities and relationships "
                   "for reasoning over connections. Both are linked back to the source document so every "
                   "answer is traceable.", "Body"))
    story.append(Spacer(1, 0.2 * cm))
    story.append(scaled_image(DIAG / "database_diagram.png", W))
    story.append(P("Figure 2 — Data model. Left: knowledge-graph node/relationship types. Right: "
                   "vector-store, document, cache and trace records.", "Small"))
    story.append(Spacer(1, 0.3 * cm))
    story.append(P("Graph schema (Cypher-style):", "H2"))
    story.append(Paragraph(
        "(:Client)-[:OWNS]-&gt;(:Project)<br/>"
        "(:Project)-[:USES]-&gt;(:Technology)<br/>"
        "(:Project)-[:DEPLOYED_ON]-&gt;(:CloudProvider)<br/>"
        "(:Project)-[:HAS_RISK]-&gt;(:Risk)<br/>"
        "(:Requirement)-[:BELONGS_TO]-&gt;(:Project)<br/>"
        "(:Document)-[:MENTIONS]-&gt;(:Entity)&nbsp;&nbsp;&nbsp;(:Document)-[:DESCRIBES]-&gt;(:Project)",
        styles["MnCode"]))

    # ---- 6. cross-cutting ----
    story.append(P("6. Caching, Queues, Observability &amp; Scale", "H1"))
    story.append(hr())
    story.append(P("<b>Caching.</b> Two layers. (1) A response cache keyed on the normalised question "
                   "hash returns identical answers instantly and cuts LLM cost. (2) An embedding cache "
                   "avoids re-embedding repeated text during ingestion and query. Backend is Redis in "
                   "production and an in-memory TTL-LRU locally — same interface. A note on <b>KV / "
                   "prompt cache</b>: for a hosted LLM we additionally benefit from provider-side prompt "
                   "caching by keeping the system prompt and retrieved context prefix-stable.", "Body"))
    story.append(P("<b>Queues / background processing.</b> Ingestion is I/O- and compute-heavy, so "
                   "/ingest enqueues work and returns immediately with a job summary. Locally this uses "
                   "FastAPI BackgroundTasks; the same producer interface targets Celery + Redis/RabbitMQ "
                   "for multi-worker scale-out.", "Body"))
    story.append(P("<b>Observability.</b> Every request carries an id and emits structured JSON logs "
                   "with route, latency_ms, retrieved chunk ids and (when using a hosted LLM) token "
                   "usage. Langfuse tracing hooks activate automatically when LANGFUSE keys are present, "
                   "giving per-step traces of the agentic flow.", "Body"))
    story.append(P("<b>Scalability path.</b> The API is stateless, so it scales horizontally behind a "
                   "load balancer. Vector store -> Astra DB / Chroma server; graph -> Neo4j Aura; cache "
                   "+ broker -> managed Redis; ingestion workers -> Celery pool. The provider abstraction "
                   "lets us route cheap models for classification and stronger models for synthesis "
                   "(LLM routing).", "Body"))

    # ---- 7. decisions & limits ----
    story.append(P("7. Key Decisions, Assumptions &amp; Limitations", "H1"))
    story.append(hr())
    story.append(P("<b>Decisions.</b> Offline-first defaults (NumPy vector index, NetworkX graph, "
                   "extractive fallback) were chosen so the prototype is trivially runnable and "
                   "reproducible for grading, while every layer is interface-bound for a clean upgrade "
                   "to managed services. LiteLLM gives provider independence and avoids lock-in.", "Body"))
    story.append(P("<b>Assumptions.</b> Small corpus (single-digit to low-hundreds of documents); "
                   "single-tenant internal use; documents are non-sensitive fictional samples; English "
                   "content.", "Body"))
    story.append(P("<b>Limitations.</b> Entity extraction is rule/heuristic-based (dictionary + "
                   "patterns) rather than a fine-tuned NER model, so recall on novel entity names is "
                   "limited. The NumPy index is in-process and not sharded — fine for the prototype, "
                   "replaced by Astra/Chroma at scale. The extractive fallback answers are grounded but "
                   "less fluent than a hosted LLM.", "Body"))
    story.append(P("<b>Future improvements.</b> LLM-based NER + relation extraction, hybrid BM25+vector "
                   "retrieval with cross-encoder reranking, an evaluation harness with RAGAS-style "
                   "metrics wired into CI, streaming responses, a web UI, and full voice (Whisper STT + "
                   "TTS).", "Body"))
    story.append(Spacer(1, 0.3 * cm))
    story.append(hr())
    story.append(P("Companion documents: README.md (setup &amp; usage), SYSTEM_DESIGN.md (extended "
                   "narrative), diagrams/ (source PNGs), and the running Swagger UI at /docs.", "Small"))

    doc = SimpleDocTemplate(str(OUT), pagesize=A4,
                            leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                            title="MedNova AI Knowledge Platform — Architecture & System Design",
                            author="Asif")

    def footer(canvas, d):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#c9d3dc"))
        canvas.line(2 * cm, 1.4 * cm, A4[0] - 2 * cm, 1.4 * cm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(GREY)
        canvas.drawString(2 * cm, 1.0 * cm, "MedNova AI Knowledge Platform — Architecture & System Design")
        canvas.drawRightString(A4[0] - 2 * cm, 1.0 * cm, f"Page {d.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=lambda c, d: None, onLaterPages=footer)
    print("wrote", OUT)


if __name__ == "__main__":
    build()
