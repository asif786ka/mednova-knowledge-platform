"""Pydantic request/response schemas for the API (input validation + OpenAPI docs)."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    vector_db: str
    graph_db: str
    llm_provider: str
    cache: str
    embeddings: str
    documents_indexed: int
    graph_nodes: int


class IngestRequest(BaseModel):
    folder: Optional[str] = Field(
        default=None, description="Folder to ingest. Defaults to the sample_docs directory.")
    reset: bool = Field(default=True, description="Clear existing index before ingesting.")
    async_mode: bool = Field(
        default=False, alias="async",
        description="Run ingestion in the background and return a job id immediately.")

    model_config = {"populate_by_name": True}


class IngestResponse(BaseModel):
    status: str
    documents_processed: int
    chunks_created: int
    entities_extracted: int
    relationships_created: int
    skipped: List[str] = []
    job_id: Optional[str] = None


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500,
                          description="Natural-language question about MedNova documents.")


class AskResponse(BaseModel):
    answer: str
    sources: List[str]
    retrieval_strategy: str
    related_entities: List[str] = []
    route: str
    confidence: float
    llm_backend: str
    matched_entities: List[str] = []
    cached: bool = False
    latency_ms: float


class VoiceAskRequest(BaseModel):
    transcript: Optional[str] = Field(
        default=None, description="Transcribed question text (from client-side STT).")
    # Audio bytes would be accepted via multipart on a real deployment; the transcript
    # path keeps the prototype dependency-free. See SYSTEM_DESIGN 'Voice'.


class VoiceAskResponse(AskResponse):
    transcript: str
    speech_text: str  # text intended for text-to-speech synthesis
