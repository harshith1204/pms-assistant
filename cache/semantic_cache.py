import os
import json
import time
from typing import Any, Dict, List, Optional, Tuple

try:
    import redis  # type: ignore
    _HAS_REDIS = True
except Exception:
    _HAS_REDIS = False

try:
    from sentence_transformers import SentenceTransformer  # type: ignore
    import numpy as np  # type: ignore
    _HAS_ST = True
except Exception:
    _HAS_ST = False


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
        # conversation_id -> list[ (ts, vec, response, query) ]
        self.store: Dict[str, List[Tuple[float, Any, str, str]]] = {}
        self._embedder = None

    def _get_embedder(self):
        if not _HAS_ST:
            return None
        if self._embedder is None:
            model_name = os.getenv("SEM_CACHE_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
            try:
                self._embedder = SentenceTransformer(model_name)
            except Exception:
                self._embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        return self._embedder

    def _cleanup(self, conv_id: str) -> None:
        items = self.store.get(conv_id, [])
        if not items:
            return
        cutoff = _now() - self.ttl
        items = [x for x in items if x[0] >= cutoff]
        if len(items) > self.max_items:
            items = items[-self.max_items:]
        self.store[conv_id] = items

    def get(self, conv_id: str, query: str, min_score: float) -> Optional[str]:
        emb = self._get_embedder()
        if emb is None:
            return None
        self._cleanup(conv_id)
        items = self.store.get(conv_id, [])
        if not items:
            return None
        qvec = emb.encode([query])[0]
        import numpy as np  # type: ignore
        best: Tuple[float, Optional[str]] = (0.0, None)
        for ts, vec, response, q in items:
            denom = (np.linalg.norm(vec) * np.linalg.norm(qvec))
            if denom <= 0:
                continue
            score = float(np.dot(vec, qvec) / denom)
            if score > best[0]:
                best = (score, response)
        if best[0] >= min_score:
            return best[1]
        return None

    def set(self, conv_id: str, query: str, response: str) -> None:
        emb = self._get_embedder()
        if emb is None:
            return
        vec = emb.encode([query])[0]
        items = self.store.setdefault(conv_id, [])
        items.append(( _now(), vec, response, query ))
        self._cleanup(conv_id)


class SemanticCache:
    def __init__(self) -> None:
        self.enabled = os.getenv("ENABLE_SEMANTIC_CACHE", "true").lower() == "true"
        self.min_score = float(os.getenv("SEM_CACHE_MIN_SCORE", "0.92"))
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
            # embedder for redis path (scan-based)
            self._embedder = None
            if _HAS_ST:
                try:
                    model_name = os.getenv("SEM_CACHE_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
                    self._embedder = SentenceTransformer(model_name)
                except Exception:
                    self._embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

    def _redis_key(self, conv_id: str) -> str:
        return f"semcache:{conv_id}"

    def get(self, query: str, conversation_id: Optional[str]) -> Optional[str]:
        if not self.enabled:
            return None
        conv_id = conversation_id or "_global_"
        if self._redis is None:
            return self._mem.get(conv_id, query, self.min_score)
        # Redis scan-based fallback: iterate list and compute cosine
        try:
            key = self._redis_key(conv_id)
            items = self._redis.lrange(key, 0, -1) or []
            if not items or self._embedder is None:
                return None
            import numpy as np  # type: ignore
            qvec = self._embedder.encode([query])[0]
            best_score = 0.0
            best_resp: Optional[str] = None
            cutoff = _now() - self.ttl
            # Filter expired and compute best sim
            kept: List[str] = []
            for raw in items:
                try:
                    rec = json.loads(raw)
                except Exception:
                    continue
                ts = float(rec.get("ts", 0))
                if ts < cutoff:
                    continue
                vec = np.array(rec.get("vec", []), dtype=float)
                denom = (np.linalg.norm(vec) * np.linalg.norm(qvec))
                if denom <= 0:
                    kept.append(raw)
                    continue
                score = float(np.dot(vec, qvec) / denom)
                if score > best_score:
                    best_score = score
                    best_resp = rec.get("response")
                kept.append(raw)
            # Trim list if too large
            if len(kept) > self.max_items:
                kept = kept[-self.max_items:]
            if kept != items:
                pipeline = self._redis.pipeline()
                pipeline.delete(key)
                if kept:
                    pipeline.rpush(key, *kept)
                pipeline.execute()
            if best_score >= self.min_score:
                return best_resp
            return None
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
            if self._embedder is None:
                return
            vec = self._embedder.encode([query])[0]
            rec = json.dumps({
                "ts": _now(),
                "vec": list(map(float, vec)),
                "response": response,
                "query": query,
            })
            key = self._redis_key(conv_id)
            self._redis.rpush(key, rec)
            # Trim to max_items
            length = self._redis.llen(key)
            if length and length > self.max_items:
                # Keep newest tail
                self._redis.ltrim(key, -self.max_items, -1)
        except Exception:
            return
