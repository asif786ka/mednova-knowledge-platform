# Technical Architecture Notes — MedNova Knowledge Platform

## Retrieval design
The MedNova Knowledge Platform uses both RAG and GraphRAG. Vector search runs over document
chunks stored in Astra DB. Graph search runs over a Neo4j knowledge graph that models the
relationships between clients, projects, technologies, cloud providers, risks, and requirements.

The relationship between the Knowledge Platform, Neo4j, and Astra DB is as follows: Neo4j stores
the knowledge graph (entities and relationships) while Astra DB stores the vector embeddings of
document chunks. The agentic router queries Neo4j for relationship questions and Astra DB for
semantic-similarity questions, and combines both for hybrid questions.

## Orchestration
LangGraph defines the agent state machine: classify → plan → retrieve → synthesize → verify.
LangChain provides the retriever and prompt tooling. LiteLLM routes requests to the configured
LLM provider so open-source and closed-source models can be swapped freely.

## Observability
Langfuse traces every step of the agentic workflow. Structured logs capture latency and the
retrieved chunk ids for each request.

## Implementation challenges
The main implementation challenges are: keeping entity extraction accurate without a fine-tuned
NER model, avoiding hallucination when documents are sparse, and controlling LLM latency and cost
under load. Caching and prompt-stable context are used to mitigate cost.
