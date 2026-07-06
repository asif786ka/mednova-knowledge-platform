# Meeting Summary — Platform Sync (June 2026)

## Attendees
Engineering, Product, Clinical Safety.

## Decisions
- The MedNova Knowledge Platform will use both RAG and GraphRAG. Projects that use both RAG and
  GraphRAG: currently only the Knowledge Platform.
- Neo4j and Astra DB confirmed as the graph and vector stores for the Knowledge Platform.
- LangChain + LangGraph confirmed for orchestration; Langfuse for tracing.

## Action items
- Address the main implementation challenges: entity-extraction accuracy, hallucination control,
  and LLM latency/cost under load.
- Confirm voice-based AI requirements with St. Aldwyn Hospital for the Patient Assistant Platform.

## Which projects use AI automation
It was noted that all four projects use AI automation: the Knowledge Platform (agentic retrieval),
the Patient Assistant Platform (query triage), the Remote Care Platform (anomaly detection), and
the Operational Insights Service (demand forecasting).
