"""
LLM provider abstraction.

One interface, three tiers of backend, chosen automatically:
  1. LiteLLM  -> any hosted/open model (OpenAI, Anthropic, Ollama, ...) when a key is set.
  2. (LiteLLM also covers local Ollama via OLLAMA_HOST.)
  3. Deterministic extractive fallback -> composes a grounded, source-cited answer directly
     from the retrieved context. No network, no key, no hallucination. This guarantees the
     platform always returns a useful, honest answer.

The abstraction (complete / available / backend) means the rest of the app never imports a
provider SDK directly — swapping models is a config change (LLM_MODEL + provider key).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import List, Optional

from app.config import settings
from app.observability import get_logger

logger = get_logger("llm")

NO_INFO = ("I don't have enough information in the provided MedNova documents to answer "
           "that confidently.")


@dataclass
class LLMResponse:
    text: str
    backend: str
    tokens: Optional[int] = None


class LLMProvider:
    def __init__(self) -> None:
        self.backend = "extractive-fallback"
        self._litellm = None
        if settings.llm_enabled:
            self._try_litellm()

    def _try_litellm(self) -> None:
        try:
            import litellm  # noqa
            self._litellm = litellm
            self.backend = f"litellm:{settings.llm_model}"
            logger.info("LLM provider: %s", self.backend)
        except Exception as exc:  # pragma: no cover
            logger.info("litellm unavailable (%s); extractive fallback", exc)
            self._litellm = None
            self.backend = "extractive-fallback"

    @property
    def available(self) -> bool:
        return True  # always available: fallback guarantees a response

    @property
    def uses_real_llm(self) -> bool:
        return self._litellm is not None

    # -- generation --------------------------------------------------------
    def complete(self, system: str, user: str,
                 context_blocks: Optional[List[str]] = None,
                 temperature: float = 0.1) -> LLMResponse:
        if self._litellm is not None:  # pragma: no cover - needs a key
            try:
                resp = self._litellm.completion(
                    model=settings.llm_model,
                    messages=[{"role": "system", "content": system},
                              {"role": "user", "content": user}],
                    temperature=temperature,
                )
                text = resp["choices"][0]["message"]["content"]
                tokens = resp.get("usage", {}).get("total_tokens")
                return LLMResponse(text=text.strip(), backend=self.backend, tokens=tokens)
            except Exception as exc:
                logger.warning("LLM call failed (%s); extractive fallback", exc)
        return self._extractive(user, context_blocks or [])

    # -- deterministic grounded fallback -----------------------------------
    def _extractive(self, user: str, context_blocks: List[str]) -> LLMResponse:
        """
        Build an answer from retrieved context only. Selects the sentences most relevant to
        the question by keyword overlap and stitches them into a short, grounded summary. If
        nothing overlaps, returns the explicit "not enough information" message.
        """
        question = _last_question(user)
        q_terms = _keywords(question)
        sentences: List[str] = []
        for block in context_blocks:
            for sent in re.split(r"(?<=[.!?\n])\s+", _clean_block(block)):
                sent = _clean_sentence(sent)
                if len(sent) < 15:
                    continue
                overlap = len(q_terms & _keywords(sent))
                if overlap:
                    sentences.append((overlap, sent))  # type: ignore[arg-type]
        if not sentences:
            return LLMResponse(text=NO_INFO, backend=self.backend, tokens=None)
        sentences.sort(key=lambda x: -x[0])  # type: ignore[index]
        picked, seen = [], set()
        for _, sent in sentences:  # type: ignore[misc]
            norm = sent.lower()
            if norm in seen:
                continue
            seen.add(norm)
            picked.append(sent)
            if len(picked) >= 4:
                break
        answer = " ".join(picked)
        return LLMResponse(text=answer, backend=self.backend, tokens=None)


def _clean_block(block: str) -> str:
    """Drop source-header lines and markdown headings so they don't leak into answers."""
    keep = []
    for line in block.splitlines():
        s = line.strip()
        if not s or s.startswith("[") or s.startswith("#") or s.startswith("==="):
            continue
        keep.append(s)
    return " ".join(keep)


def _clean_sentence(sent: str) -> str:
    sent = sent.strip().lstrip("-*• ").strip()
    sent = sent.replace("**", "").replace("`", "")
    sent = re.sub(r"#{1,6}\s*", "", sent)          # strip markdown heading markers anywhere
    return re.sub(r"\s+", " ", sent).strip()


_STOP = set("the a an of to and or in on for with is are was were be been which what who "
            "how why when where does do use uses used mention mentions mentioned across "
            "project projects document documents mednova that this these those it its as by "
            "from at".split())


def _keywords(text: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower())
            if w not in _STOP and len(w) > 2}


def _last_question(user: str) -> str:
    m = re.search(r"Question:\s*(.+)", user)
    return m.group(1) if m else user


@lru_cache(maxsize=1)
def get_llm_provider() -> LLMProvider:
    return LLMProvider()
