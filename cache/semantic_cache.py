import os
import json
import time
from typing import Any, Dict, List, Optional

try:
    import redis  # type: ignore
    _HAS_REDIS = True
except Exception:
    _HAS_REDIS = False


def _now() -> float:
    return time.time()


def _approx_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


class _InMemoryIndex:
    def __init__(self, max_items: int = 1000, ttl: int = 86400) -> None:
        self.max_items = max_items
        self.ttl = ttl
        # conversation_id -> dict[query] = (ts, response)
        self.store: Dict[str, Dict[str, Any]] = {}

    def _cleanup(self, conv_id: str) -> None:
        if conv_id not in self.store:
            self.store[conv_id] = {}
        cutoff = _now() - self.ttl
        keys_to_del = [q for q, rec in self.store[conv_id].items() if rec[0] < cutoff]
        for q in keys_to_del:
            self.store[conv_id].pop(q, None)
        # Trim to max_items by oldest
        if len(self.store[conv_id]) > self.max_items:
            items = sorted(self.store[conv_id].items(), key=lambda kv: kv[1][0])
            for q, _ in items[: max(0, len(items) - self.max_items)]:
                self.store[conv_id].pop(q, None)

    def get(self, conv_id: str, query: str) -> Optional[str]:
        self._cleanup(conv_id)
        rec = self.store.get(conv_id, {}).get(query)
        if rec:
            return rec[1]
        return None

    def set(self, conv_id: str, query: str, response: str) -> None:
        self._cleanup(conv_id)
        bucket = self.store.setdefault(conv_id, {})
        bucket[query] = (_now(), response)


class SemanticCache:
    def __init__(self) -> None:
        self.enabled = os.getenv("ENABLE_SEMANTIC_CACHE", "true").lower() == "true"
        self.ttl = int(os.getenv("SEM_CACHE_TTL_SEC", "86400"))
        self.max_items = int(os.getenv("SEM_CACHE_MAX_ITEMS", "1000"))

        self._redis = None
        if self.enabled and _HAS_REDIS and os.getenv("REDIS_URL"):
            try:
                self._redis = redis.Redis.from_url(os.getenv("REDIS_URL"), decode_responses=True)
            except Exception:
                self._redis = None
        if self._redis is None:
            self._mem = _InMemoryIndex(max_items=self.max_items, ttl=self.ttl)
        else:
            pass

    def _redis_key(self, conv_id: str) -> str:
        return f"semcache:{conv_id}"

    def get(self, query: str, conversation_id: Optional[str]) -> Optional[str]:
        if not self.enabled:
            return None
        conv_id = conversation_id or "_global_"
        if self._redis is None:
            return self._mem.get(conv_id, query)
        # Redis: exact match of (conv_id, query)
        try:
            key = self._redis_key(conv_id)
            raw = self._redis.hget(key, query)
            if not raw:
                return None
            rec = json.loads(raw)
            if (float(rec.get("ts", 0)) + self.ttl) < _now():
                # expired
                self._redis.hdel(key, query)
                return None
            return rec.get("response")
        except Exception:
            return None

    def set(self, query: str, response: str, conversation_id: Optional[str]) -> None:
        if not self.enabled:
            return
        if not response or len(response.strip()) == 0:
            return
        conv_id = conversation_id or "_global_"
        if self._redis is None:
            self._mem.set(conv_id, query, response)
            return
        try:
            rec = json.dumps({
                "ts": _now(),
                "response": response,
                "query": query,
            })
            key = self._redis_key(conv_id)
            self._redis.hset(key, query, rec)
            # no size trimming for hash; optional maintenance could be added
        except Exception:
            return
