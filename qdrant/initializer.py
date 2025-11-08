from langchain_core.tools import tool
from typing import Optional, Dict, List, Any, Union
import mongo.constants
import os
import json
import re
import uuid
import logging
from bson import ObjectId, Binary
# Qdrant and RAG dependencies
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Filter,
    FieldCondition,
    MatchValue,
    MatchAny,
    Prefetch,
    NearestQuery,
    FusionQuery,
    Fusion,
    SparseVector,
)
from embedding.service_client import EmbeddingServiceClient, EmbeddingServiceError

# Configure logging
logger = logging.getLogger(__name__)

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
            # Create the instance and connect it
            instance = cls.__new__(cls)
            instance.qdrant_client = None
            instance.embedding_client = None
            instance.connected = False

            await instance.connect()
            cls._instance = instance

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
            self.qdrant_client = QdrantClient(
                url=mongo.constants.QDRANT_URL,
                api_key=mongo.constants.QDRANT_API_KEY,
            )
            self.embedding_client = EmbeddingServiceClient(os.getenv("EMBEDDING_SERVICE_URL"))
            try:
                dimension = self.embedding_client.get_dimension()
            except EmbeddingServiceError as exc:
                raise RuntimeError(f"Failed to initialize embedding service: {exc}") from exc
            self.connected = True
            # Lightweight verification that sparse vectors are configured and present
            try:
                col = self.qdrant_client.get_collection(mongo.constants.QDRANT_COLLECTION_NAME)
                # If call succeeds, we assume sparse config exists as we create it during indexing
            except Exception as e:
                logger.error(f"Could not verify collection config: {e}")
        except Exception as e:
            logger.error(f"Failed to connect RAGTool components: {e}")
            raise
    
    # ... all other methods like search_content() and get_content_context() remain unchanged ...
    async def search_content(self, query: str, content_type: str = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Search for relevant content in Qdrant with dense+SPLADE hybrid fusion."""
        if not self.connected:
            await self.connect()

        try:
            # Generate embedding for the query
            query_vectors = self.embedding_client.encode([query])
            if not query_vectors:
                return []
            query_embedding = query_vectors[0]
            # Build filter if content_type is specified
            from mongo.constants import BUSINESS_UUID, MEMBER_UUID
            must_conditions = []
            if content_type:
                must_conditions.append(
                    FieldCondition(
                        key="content_type",
                        match=MatchValue(value=content_type)
                    )
                )

            # Business-level scoping
            business_uuid = BUSINESS_UUID()
            if business_uuid:
                must_conditions.append(
                    FieldCondition(
                        key="business_id",
                        match=MatchValue(value=business_uuid)
                    )
                )

            # Member-level project RBAC scoping
            member_uuid = MEMBER_UUID()
            if member_uuid:
                try:
                    # Get list of project IDs this member has access to
                    member_projects = await self._get_member_projects(member_uuid, business_uuid)
                    if member_projects:
                        # Only apply member filtering for content types that belong to projects
                        project_content_types = {"page", "work_item", "cycle", "module"}
                        if content_type is None or content_type in project_content_types:
                            # Filter by accessible project IDs
                            must_conditions.append(FieldCondition(key="project_id", match=MatchAny(any=member_projects)))
                        elif content_type == "project":
                            # For project searches, only show projects the member has access to
                            must_conditions.append(FieldCondition(key="mongo_id", match=MatchAny(any=member_projects)))
                except Exception as e:
                    # Error getting member projects - log and skip member filter
                    logger.error(f"Error getting member projects for '{member_uuid}': {e}")
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
            logger.error(f"Error searching Qdrant: {e}")
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

    def _normalize_mongo_id(self, mongo_id) -> str:
        """Convert Mongo _id (ObjectId or Binary UUID) into a safe string like Qdrant expects."""
        if isinstance(mongo_id, ObjectId):
            return str(mongo_id)
        elif isinstance(mongo_id, Binary) and mongo_id.subtype == 3:
            return str(uuid.UUID(bytes=mongo_id))
        return str(mongo_id)

    async def _get_member_projects(self, member_uuid: str, business_uuid: str) -> List[str]:
        """
        Get list of project IDs that the member has access to.

        Args:
            member_uuid: The member's UUID
            business_uuid: The business UUID for additional scoping

        Returns:
            List of project IDs the member can access
        """
        try:
            # Import here to avoid circular imports
            from mongo.client import direct_mongo_client
            from mongo.constants import uuid_str_to_mongo_binary

            # Query MongoDB to get projects the member is associated with
            pipeline = [
                {
                    "$match": {
                        "staff._id": uuid_str_to_mongo_binary(member_uuid)
                    }
                },
                {
                    "$project": {
                        "project_id": "$project._id"
                    }
                }
            ]

            # Add business scoping if available
            if business_uuid:
                pipeline[0]["$match"]["project.business._id"] = uuid_str_to_mongo_binary(business_uuid)

            results = await direct_mongo_client.aggregate("ProjectManagement", "members", pipeline)

            # Extract project IDs and convert back to string format using same normalization as Qdrant
            project_ids = []
            for result in results:
                if result.get("project_id"):
                    project_ids.append(self._normalize_mongo_id(result["project_id"]))

            return project_ids

        except Exception as e:
            logger.error(f"Error querying member projects: {e}")
            return [] 