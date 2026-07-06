"""
Response cache with a pluggable backend.

Backend selection is automatic:
  - Redis  when REDIS_URL is set and reachable (shared across replicas, TTL-based).
  - In-memory TTL-LRU otherwise (per-process, zero setup).

Keyed on sha256 of the normalised question, so identical questions return instantly and skip
the LLM entirely — the biggest single cost/latency win for a repeated-question workload. The
interface (get / set / stats / backend) is identical for both backends.
"""
from __future__ import annotations

import hashlib
import json
import time
from collections import OrderedDict
from functools import lru_cache
from typing import Any, Dict, Optional

from app.config import settings
from app.observability import get_logger

logger = get_logger("cache")


def cache_key(question: str) -> str:
    norm = " ".join(question.lower().split())
    return "mednova:ans:" + hashlib.sha256(norm.encode()).hexdigest()


class _MemoryTTLLRU:
    def __init__(self, maxsize: int = 512) -> None:
        self._store: "OrderedDict[str, tuple[float, Any]]" = OrderedDict()
        self.maxsize = maxsize

    def get(self, key: str) -> Optional[Any]:
        item = self._store.get(key)
        if not item:
            return None
        expires, value = item
        if expires and expires < time.time():
            self._store.pop(key, None)
            return None
        self._store.move_to_end(key)
        return value

    def set(self, key: str, value: Any, ttl: int) -> None:
        self._store[key] = (time.time() + ttl if ttl else 0, value)
        self._store.move_to_end(key)
        while len(self._store) > self.maxsize:
            self._store.popitem(last=False)

    def __len__(self) -> int:
        return len(self._store)


class ResponseCache:
    def __init__(self) -> None:
        self.backend = "in-memory-lru"
        self._redis = None
        self._mem = _MemoryTTLLRU()
        self.hits = 0
        self.misses = 0
        if settings.redis_url:
            self._try_redis()

    def _try_redis(self) -> None:
        try:
            import redis

            client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
            client.ping()
            self._redis = client
            self.backend = "redis"
            logger.info("Cache backend: redis")
        except Exception as exc:
            logger.info("Redis unavailable (%s); in-memory cache", exc)
            self._redis = None
            self.backend = "in-memory-lru"

    def get(self, question: str) -> Optional[Dict[str, Any]]:
        key = cache_key(question)
        try:
            if self._redis is not None:
                raw = self._redis.get(key)
                value = json.loads(raw) if raw else None
            else:
                value = self._mem.get(key)
        except Exception:
            value = None
        if value is not None:
            self.hits += 1
        else:
            self.misses += 1
        return value

    def set(self, question: str, value: Dict[str, Any],
            ttl: Optional[int] = None) -> None:
        key = cache_key(question)
        ttl = settings.cache_ttl_seconds if ttl is None else ttl
        try:
            if self._redis is not None:
                self._redis.set(key, json.dumps(value), ex=ttl)
            else:
                self._mem.set(key, value, ttl)
        except Exception as exc:  # pragma: no cover
            logger.warning("cache set failed: %s", exc)

    def stats(self) -> Dict[str, Any]:
        size = self._redis.dbsize() if self._redis is not None else len(self._mem)
        return {"backend": self.backend, "hits": self.hits,
                "misses": self.misses, "size": size}

    def connected(self) -> bool:
        return True  # always usable (falls back to memory)


@lru_cache(maxsize=1)
def get_cache() -> ResponseCache:
    return ResponseCache()
