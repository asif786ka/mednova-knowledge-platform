import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest

# Tests must be deterministic, fast, and free: force the offline extractive provider
# so the suite never calls a paid LLM API even if OPENAI_API_KEY is set in the env/.env.
from app.config import settings

settings.llm_enabled = False
from app.llm.provider import get_llm_provider  # noqa: E402

get_llm_provider.cache_clear()

from app.ingestion.pipeline import IngestionPipeline, load_stores  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _ingest_once():
    """Ensure the index is built once before the test session."""
    vs, _ = load_stores()
    if vs.count() == 0:
        IngestionPipeline().ingest_folder()
    yield
