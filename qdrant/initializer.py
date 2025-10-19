from langchain_core.tools import tool
from typing import Optional, Dict, List, Any, Union
import mongo.constants
import os
import json
import re
# Qdrant and RAG dependencies
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Filter, FieldCondition, MatchValue, Prefetch, NearestQuery, FusionQuery, Fusion, SparseVector
)
from sentence_transformers import SentenceTransformer
print(f"DEBUG: Imported QdrantClient, value is: {QdrantClient}")

class RAGTool:
    """
    RAG tool as a Singleton, designed for eager initialization at server startup.
    """
    _instance = None  # Class variable to hold the single instance

    @classmethod
    async def initialize(cls):
        """
        Creates and connects the single instance.
        This should be called once at server startup.
        """
        if cls._instance is None:
            print("Initializing RAGTool for the first time...")
            # Create the instance and connect it
            instance = cls.__new__(cls)
            instance.qdrant_client = None
            instance.embedding_model = None
            instance.connected = False
            
            await instance.connect()
            cls._instance = instance
            print("RAGTool successfully initialized and connected.")
        else:
            print("RAGTool is already initialized.")

    @classmethod
    def get_instance(cls):
        """
        Synchronously gets the single, pre-connected instance of the RAGTool.
        Raises an exception if initialize() has not been called.
        """
        if cls._instance is None:
            raise RuntimeError(
                "RAGTool has not been initialized. "
                "Please call await RAGTool.initialize() at server startup."
            )
        return cls._instance

    async def connect(self):
        # This method's internal logic remains the same
        if self.connected:
            return
        try:
            self.qdrant_client = QdrantClient(url=mongo.constants.QDRANT_URL, api_key=mongo.constants.QDRANT_API_KEY)
            try:
                self.embedding_model = SentenceTransformer(mongo.constants.EMBEDDING_MODEL)
            except Exception as e:
                print(f"⚠️ Failed to load embedding model '{mongo.constants.EMBEDDING_MODEL}': {e}\nFalling back to 'sentence-transformers/all-MiniLM-L6-v2'")
                self.embedding_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
            self.connected = True
            print(f"Successfully connected to Qdrant at {mongo.constants.QDRANT_URL}")
            # Lightweight verification that sparse vectors are configured and present
            try:
                col = self.qdrant_client.get_collection(mongo.constants.QDRANT_COLLECTION_NAME)
                # If call succeeds, we assume sparse config exists as we create it during indexing
                print(f"ℹ️ Collection loaded: {getattr(col, 'name', mongo.constants.QDRANT_COLLECTION_NAME)}")
            except Exception as e:
                print(f"⚠️ Could not verify collection config: {e}")
        except Exception as e:
            print(f"Failed to connect RAGTool components: {e}")
            raise
    
    async def ensure_memory_collection(self, collection_name: str) -> None:
        """Ensure a Qdrant collection exists for conversation memory.

        Uses the same embedding model to determine vector size and creates
        a simple cosine dense vector space.
        """
        if not self.connected:
            await self.connect()
        client = self.qdrant_client
        model = self.embedding_model
        try:
            client.get_collection(collection_name)
            return
        except Exception:
            pass
        try:
            # Determine embedding size
            dim = None
            try:
                dim = int(getattr(model, "get_sentence_embedding_dimension", lambda: None)())
            except Exception:
                dim = None
            if not dim:
                v = model.encode("dimension_probe")
                dim = len(v.tolist() if hasattr(v, "tolist") else v)
            client.create_collection(
                collection_name=collection_name,
                vectors_config={"dense": VectorParams(size=int(dim), distance=Distance.COSINE)},
            )
        except Exception as e:
            print(f"⚠️ Failed to ensure memory collection '{collection_name}': {e}")
            raise

    # ... all other methods like search_content() and get_content_context() remain unchanged ...
    async def search_content(self, query: str, content_type: str = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Search for relevant content in Qdrant with dense+SPLADE hybrid fusion."""
        if not self.connected:
            await self.connect()

        try:
            # Generate embedding for the query
            query_embedding = self.embedding_model.encode(query).tolist()
            # Build filter if content_type is specified
            from mongo.constants import BUSINESS_UUID
            must_conditions = []
            if content_type:
                must_conditions.append(
                    FieldCondition(
                        key="content_type",
                        match=MatchValue(value=content_type)
                    )
                )
            if BUSINESS_UUID:
                must_conditions.append(
                    FieldCondition(
                        key="business_id",
                        match=MatchValue(value=BUSINESS_UUID)
                    )
                )
            search_filter = Filter(must=must_conditions) if must_conditions else None

            # Hybrid fusion: dense + SPLADE sparse (fallback to keyword over full_text)
            # Increase initial candidate pool to improve recall with smaller chunks
            initial_limit = max(limit * 10, 50)
            prefetch_list = [
                Prefetch(
                    query=NearestQuery(nearest=query_embedding),
                    using="dense",
                    limit=initial_limit,
                    # Apply a modest threshold to dense to drop very weak hits
                    score_threshold=0.4,
                    filter=search_filter,
                )
            ]

            sparse_added = False
            try:
                from qdrant.encoder import get_splade_encoder
                from qdrant.retrieval import extract_keywords
                splade = get_splade_encoder()
                splade_vec = splade.encode_text(query)
                if splade_vec.get("indices"):
                    prefetch_list.append(
                        Prefetch(
                            query=NearestQuery(
                                nearest=SparseVector(indices=splade_vec["indices"], values=splade_vec["values"]),
                            ),
                            using="sparse",
                            # Give sparse more candidates; do not threshold (scale differs)
                            limit=max(initial_limit, int(initial_limit * 2.0)),
                            score_threshold=None,
                            filter=search_filter,
                        )
                    )
                    sparse_added = True
            except Exception:
                pass

            ENABLE_KEYWORD_FALLBACK = False
            if ENABLE_KEYWORD_FALLBACK and not sparse_added:
                from qdrant.retrieval import extract_keywords
                keyword_query = extract_keywords(query)
                prefetch_list.append(
                    Prefetch(
                        query=NearestQuery(nearest=keyword_query),
                        using="full_text",
                        limit=initial_limit,
                        filter=search_filter,
                    )
                )

            fusion = FusionQuery(fusion=Fusion.RRF)
            response = self.qdrant_client.query_points(
                collection_name=mongo.constants.QDRANT_COLLECTION_NAME,
                prefetch=prefetch_list,
                query=fusion,
                limit=initial_limit,
            )
            search_results = response.points if response else []

            # Format results - include ALL metadata from payload
            results = []
            for result in search_results:
                payload = result.payload or {}
                # Prefer 'content'; fallback to 'full_text' or 'title' so content is never empty
                content_text = payload.get("content") or payload.get("full_text") or payload.get("title", "")

                # Create a result dict with all payload fields
                result_dict = {
                    "id": result.id,
                    "score": result.score,
                    "title": payload.get("title", "Untitled"),
                    "content": content_text,
                    "content_type": payload.get("content_type", "unknown"),
                    "mongo_id": payload.get("mongo_id"),
                }
                
                # Add all other metadata fields from payload
                for key, value in payload.items():
                    if key not in result_dict and key not in ["full_text"]:  # Skip duplicates and internal fields
                        result_dict[key] = value
                
                results.append(result_dict)

            # Keep top-N by score
            results.sort(key=lambda x: x.get("score", 0), reverse=True)
            return results[:limit]

        except Exception as e:
            print(f"Error searching Qdrant: {e}")
            return []

    async def get_content_context(self, query: str, content_types: List[str] = None) -> str:
        """Get relevant context for answering questions about page and work item content"""
        if not content_types:
            content_types = ["page", "work_item", "project", "cycle", "module"]

        all_results = []
        for content_type in content_types:
            results = await self.search_content(query, content_type=content_type, limit=3)
            all_results.extend(results)

        # Sort by relevance score
        all_results.sort(key=lambda x: x["score"], reverse=True)

        # Format context
        context_parts = []
        # print(all_results)
        for i, result in enumerate(all_results[:5], 1):  # Limit to top 5 results
            chunk_info = ""
            if result.get("chunk_index") is not None and result.get("chunk_count"):
                chunk_info = f" (chunk {int(result['chunk_index'])+1}/{int(result['chunk_count'])})"
            context_parts.append(
                f"[{i}] {result['content_type'].upper()}: {result['title']}{chunk_info}\n"
                f"Content: {result['content'][:500]}{'...' if len(result['content']) > 500 else ''}\n"
                f"Relevance Score: {result['score']:.3f}\n"
            )

        return "\n".join(context_parts) if context_parts else "No relevant content found." 