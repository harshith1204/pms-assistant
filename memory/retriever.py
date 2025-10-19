from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import asyncio

from qdrant_client.models import Filter, FieldCondition, MatchValue, Prefetch, NearestQuery, FusionQuery, Fusion


class ConversationMemoryRetriever:
    """Retrieves semantically relevant prior messages for a conversation.

    Uses the existing Qdrant client and SentenceTransformer embedding model
    initialized by RAGTool. No reranker, no token budget. Keeps a small top-k.
    """

    def __init__(self) -> None:
        from qdrant.initializer import RAGTool
        from mongo import constants as const

        self._rag_tool_cls = RAGTool
        self._collection = getattr(const, "MEMORY_QDRANT_COLLECTION_NAME", "conversation_memory")
        self._rag = None

    async def _ensure_ready(self) -> None:
        if self._rag is None:
            await self._rag_tool_cls.initialize()
            self._rag = self._rag_tool_cls.get_instance()

    async def retrieve(self, *, conversation_id: str, query: str, top_k: int = 10, roles: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        await self._ensure_ready()
        client = self._rag.qdrant_client
        model = self._rag.embedding_model

        query_vec = await asyncio.get_running_loop().run_in_executor(None, model.encode, query)

        must: List[Any] = [FieldCondition(key="conversation_id", match=MatchValue(value=conversation_id))]
        if roles:
            must.append(FieldCondition(key="role", match=MatchValue(any=roles)))  # type: ignore[arg-type]
        q_filter = Filter(must=must)

        prefetch = [
            Prefetch(query=NearestQuery(nearest=query_vec), using="dense", limit=max(50, top_k * 5), filter=q_filter)
        ]
        fusion = FusionQuery(fusion=Fusion.RRF)

        resp = client.query_points(collection_name=self._collection, prefetch=prefetch, query=fusion, limit=top_k)
        points = getattr(resp, "points", []) or []
        results: List[Dict[str, Any]] = []
        for p in points:
            payload = p.payload or {}
            results.append({
                "id": p.id,
                "score": p.score,
                **payload
            })
        return results


def compress_for_prompt(snippets: List[Dict[str, Any]]) -> str:
    """Very simple compression to short bullets; preserve roles and timestamps.
    Avoids any extra LLM pass, per user request (no reranker/token-budget).
    """
    lines: List[str] = []
    for s in snippets:
        role = s.get("role", "msg")
        ts = s.get("ts")
        text = (s.get("text") or "").strip()
        if not text:
            continue
        # Keep first ~220 chars for readability
        if len(text) > 220:
            text = text[:220] + "..."
        prefix = {
            "user": "U",
            "assistant": "A",
            "tool": "T",
            "action": "Act",
        }.get(role, "M")
        lines.append(f"- [{prefix}] {text}")
    if not lines:
        return ""
    return "\n".join(lines)
