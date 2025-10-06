from langchain_core.tools import tool
from typing import Optional, Dict, List, Any, Union
import mongo.constants
import os
import json
import re
# Qdrant and RAG dependencies
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
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
        except Exception as e:
            print(f"Failed to connect RAGTool components: {e}")
            raise
    
    # ... all other methods like search_content() and get_content_context() remain unchanged ...
    async def search_content(self, query: str, content_type: str = None, limit: int = 5, min_score: Optional[float] = None) -> List[Dict[str, Any]]:
        """Search for relevant content in Qdrant based on the query"""
        if not self.connected:
            await self.connect()

        try:
            # Generate embedding for the query
            query_embedding = self.embedding_model.encode(query).tolist()
            # h
            print("Query embedding generated")
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

            # Search in Qdrant
            search_results = self.qdrant_client.search(
                collection_name=mongo.constants.QDRANT_COLLECTION_NAME,
                query_vector=query_embedding,
                query_filter=search_filter,
                limit=limit,
                with_payload=True,
                score_threshold=min_score if min_score is not None else None
            )

            # Format results - include ALL metadata from payload
            results = []
            # print(f"total results",search_results)
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
                
                # Apply client-side cutoff in case backend threshold wasn't enforced
                if min_score is None or float(result_dict["score"]) >= float(min_score):
                    results.append(result_dict)

            return results

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