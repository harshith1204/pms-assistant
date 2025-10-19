from __future__ import annotations

from typing import Any, Dict, Optional
import asyncio
import time
import uuid

from qdrant_client.models import Distance, VectorParams


class ConversationMemoryIndexer:
    """Indexes conversation messages and tool outputs into Qdrant.

    Reuses the existing Qdrant client and SentenceTransformer embedding model
    initialized by RAGTool. Creates a dedicated collection for conversation
    memory if it doesn't already exist.
    """

    def __init__(self) -> None:
        # Lazy import to avoid circulars and heavy init at import-time
        from qdrant.initializer import RAGTool
        from mongo import constants as const

        self._rag_tool_cls = RAGTool
        self._collection = getattr(
            const, "MEMORY_QDRANT_COLLECTION_NAME", "conversation_memory"
        )
        self._rag: Optional[Any] = None

    async def _ensure_ready(self) -> None:
        if self._rag is None:
            try:
                await self._rag_tool_cls.initialize()
            except TypeError:
                # In case initialize is not awaited somewhere; keep robust
                await asyncio.get_running_loop().run_in_executor(None, self._rag_tool_cls.initialize)  # type: ignore[arg-type]
            self._rag = self._rag_tool_cls.get_instance()
            # Ensure memory collection exists with proper vector size
            try:
                await self._rag.ensure_memory_collection(self._collection)
            except AttributeError:
                # Older initializer without helper; create via client directly
                client = self._rag.qdrant_client
                model = self._rag.embedding_model
                try:
                    dim = int(getattr(model, "get_sentence_embedding_dimension", lambda: len(model.encode("dim").tolist()))())  # type: ignore[misc]
                except Exception:
                    dim = len(model.encode("sample").tolist())
                try:
                    client.get_collection(self._collection)
                except Exception:
                    client.create_collection(
                        collection_name=self._collection,
                        vectors_config={
                            "dense": VectorParams(size=dim, distance=Distance.COSINE)
                        },
                    )

    async def upsert_message(self, *, conversation_id: str, role: str, text: str, metadata: Optional[Dict[str, Any]] = None, message_id: Optional[str] = None) -> None:
        """Embed and upsert a message into the memory collection.

        - role: 'user' | 'assistant' | 'tool' | 'action'
        - metadata: arbitrary payload (tool name, step index, etc.)
        """
        if not text or not text.strip():
            return
        await self._ensure_ready()

        assert self._rag is not None  # for type checkers
        client = self._rag.qdrant_client
        model = self._rag.embedding_model

        # Compute embedding and prepare payload
        vector = await asyncio.get_running_loop().run_in_executor(None, model.encode, text)
        payload: Dict[str, Any] = {
            "conversation_id": conversation_id,
            "role": role,
            "text": text,
            "ts": int(time.time()),
        }
        if metadata:
            payload.update({k: v for k, v in metadata.items() if v is not None})

        point_id = message_id or str(uuid.uuid4())

        # Qdrant client is synchronous; offload to thread to avoid blocking loop
        def _upsert():
            client.upsert(
                collection_name=self._collection,
                points=[
                    {
                        "id": point_id,
                        "vector": {"dense": vector.tolist() if hasattr(vector, "tolist") else vector},
                        "payload": payload,
                    }
                ],
            )

        await asyncio.to_thread(_upsert)


# Singleton accessor
_singleton: Optional[ConversationMemoryIndexer] = None


def get_memory_indexer() -> ConversationMemoryIndexer:
    global _singleton
    if _singleton is None:
        _singleton = ConversationMemoryIndexer()
    return _singleton

