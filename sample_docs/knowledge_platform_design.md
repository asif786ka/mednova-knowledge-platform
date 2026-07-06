# MedNova Knowledge Platform — Design Document

**Client:** MedNova Solutions (internal)
**Project:** MedNova Knowledge Platform
**Status:** Active prototype

## Overview
The MedNova Knowledge Platform is an internal agentic AI knowledge assistant. It lets
employees ask natural-language questions and receive reliable, source-backed answers drawn
from MedNova's project documents, architecture notes, and risk assessments.

## Technology Stack
The Knowledge Platform uses **LangChain** for orchestration and **LangGraph** to implement
the agentic routing workflow. It uses **Neo4j** for graph-based relationship retrieval and
**Astra DB** as the managed vector database for semantic search. The backend is built with
**FastAPI**. **Redis** provides response caching and acts as the background-task broker.
**LiteLLM** abstracts the LLM provider and **Langfuse** provides tracing and observability.

The platform combines **RAG** (Retrieval-Augmented Generation) with **GraphRAG** so that it
can answer both document-lookup questions and relationship questions.

## Deployment
The Knowledge Platform is deployed on **AWS** (ECS + managed Redis + Astra DB).

## Requirements
- All answers must be source-backed and cite the originating document.
- The system must clearly state when there is not enough information.
- Sub-second cached response latency is required for repeated questions.
