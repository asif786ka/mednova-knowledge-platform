"""
Central configuration, loaded from environment variables with safe local defaults.

Every external dependency (LLM provider, Redis, Neo4j, Astra DB, Langfuse) is OPTIONAL.
When its credentials are absent the platform transparently falls back to a local,
offline-capable implementation so it runs with zero setup.
"""
from __future__ import annotations

import os
from pathlib import Path

try:  # optional: load a .env file if python-dotenv is installed
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)


class Settings:
    # --- paths ---
    sample_docs_dir: Path = Path(os.getenv("SAMPLE_DOCS_DIR", BASE_DIR / "sample_docs"))
    vector_store_path: Path = DATA_DIR / "vector_store.pkl"
    graph_store_path: Path = DATA_DIR / "graph_store.json"

    # --- chunking ---
    chunk_size: int = int(os.getenv("CHUNK_SIZE", "700"))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "120"))

    # --- retrieval ---
    top_k: int = int(os.getenv("TOP_K", "5"))
    min_score: float = float(os.getenv("MIN_SCORE", "0.15"))

    # --- embeddings ---
    # If sentence-transformers is installed AND EMBED_MODEL is set, it is used.
    # Otherwise a deterministic hashing embedder keeps the system fully offline.
    embed_model: str = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    embed_dim: int = int(os.getenv("EMBED_DIM", "384"))
    force_hash_embeddings: bool = _bool("FORCE_HASH_EMBEDDINGS", False)

    # --- LLM provider (optional, via LiteLLM) ---
    llm_model: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY") or None
    # Any provider key LiteLLM understands enables the real LLM path.
    llm_enabled: bool = bool(
        os.getenv("OPENAI_API_KEY")
        or os.getenv("ANTHROPIC_API_KEY")
        or os.getenv("LITELLM_API_BASE")
        or os.getenv("OLLAMA_HOST")
    )

    # --- cache (Redis optional) ---
    redis_url: str | None = os.getenv("REDIS_URL") or None
    cache_ttl_seconds: int = int(os.getenv("CACHE_TTL_SECONDS", "3600"))

    # --- graph / vector backends (managed optional) ---
    neo4j_uri: str | None = os.getenv("NEO4J_URI") or None
    astra_db_id: str | None = os.getenv("ASTRA_DB_ID") or None

    # --- observability ---
    langfuse_public_key: str | None = os.getenv("LANGFUSE_PUBLIC_KEY") or None
    langfuse_secret_key: str | None = os.getenv("LANGFUSE_SECRET_KEY") or None
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    @property
    def langfuse_enabled(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)


settings = Settings()
