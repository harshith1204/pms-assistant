"""
Smart Filter Tools - Integration tools for the smart-filter agent

This module provides tool wrappers that integrate with the existing tools
in tools.py to enable the smart-filter agent to use mongo-query and RAG
functionality while maintaining its orchestration pattern.
"""

import json
import asyncio
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass
from langchain_core.tools import tool
from .planner import plan_and_execute_query
# Import the existing tools
try:
    from tools import  rag_search
except ImportError:
    # Fallback for testing
    rag_search = None

# Import necessary modules for RAG and MongoDB operations
try:
    from qdrant.retrieval import ChunkAwareRetriever
    from qdrant.initializer import RAGTool
    from mongo.constants import mongodb_tools, DATABASE_NAME, QDRANT_COLLECTION_NAME
except ImportError:
    ChunkAwareRetriever = None
    RAGTool = None
    mongodb_tools = None
    DATABASE_NAME = "ProjectManagement"
    QDRANT_COLLECTION_NAME = "pms_collection"
    build_lookup_stage = None
    REL = None


@dataclass
class MongoQueryResult:
    """Result from mongo-query tool execution"""
    work_items: List[Dict[str, Any]]
    total_count: int
    query: str
    raw_result: Any


@dataclass
class RAGSearchResult:
    """Result from RAG search tool execution"""
    work_items: List[Dict[str, Any]]
    total_count: int
    query: str
    reconstructed_docs: List[Any] = None  # Optional reconstructed docs from RAG search
    work_item_ids: Set[str] = None  # Optional set of work item IDs found
    rag_context: str = ""  # Optional RAG context string


class SmartFilterTools:
    """Tools for smart-filter agent to call mongo-query and RAG functionality"""

    _instance = None  # Class variable to hold the single instance

    def __new__(cls):
        """Ensure only one instance exists"""
        if cls._instance is None:
            cls._instance = super(SmartFilterTools, cls).__new__(cls)
            # Initialize instance variables
            cls._instance.rag_tool = None
            cls._instance.retriever = None
            cls._instance.rag_available = False
        return cls._instance

    def __init__(self):
        # Skip initialization if already done (singleton pattern)
        if hasattr(self, '_initialized'):
            return
        self._initialized = True

        # Lazy initialization - RAG will be initialized when first used
        # This avoids sync/async issues in __init__
        pass
    
    async def ensure_mongodb_connection(self) -> bool:
        """Ensure MongoDB connection is established"""
        if not mongodb_tools:
            return False

        try:
            await mongodb_tools.connect()
            return True
        except Exception:
            return False

    @classmethod
    async def initialize(cls):
        """
        Pre-initialize RAG components at server startup.
        This should be called once at server startup, similar to RAGTool.initialize()
        """
        instance = cls()
        if instance.rag_available and instance.retriever:
            return  # Already initialized

        await instance.ensure_rag_initialized()

    async def ensure_rag_initialized(self) -> bool:
        """Ensure RAG components are initialized"""
        if self.rag_available and self.retriever:
            return True

        if not RAGTool:
            print("⚠️ RAGTool not available (import failed)")
            return False

        try:
            # Set environment variable to avoid OpenMP threading issues
            import os
            os.environ['OMP_NUM_THREADS'] = '1'
            os.environ['TOKENIZERS_PARALLELISM'] = 'false'

            # Check if RAGTool is already initialized
            try:
                existing_instance = RAGTool.get_instance()
                if existing_instance and existing_instance.connected:
                    self.rag_tool = existing_instance
                    # Only log on first initialization
                    if not self.rag_available:
                        print("ℹ️ RAGTool already initialized, reusing instance")
                else:
                    print("ℹ️ Initializing RAGTool...")
                    await RAGTool.initialize()
                    self.rag_tool = RAGTool.get_instance()
            except RuntimeError:
                # Not initialized yet, initialize it
                print("ℹ️ Initializing RAGTool...")
                await RAGTool.initialize()
                self.rag_tool = RAGTool.get_instance()

            if self.rag_tool and self.rag_tool.connected:
                self.retriever = ChunkAwareRetriever(
                    qdrant_client=self.rag_tool.qdrant_client,
                    embedding_model=self.rag_tool.embedding_model
                )
                self.rag_available = True
                # Only log on first initialization
                if not hasattr(self, '_logged_init'):
                    print("✅ RAG components initialized successfully")
                    self._logged_init = True
                return True
            else:
                print("⚠️ RAGTool initialized but not connected")
                return False
        except Exception as e:
            print(f"❌ RAG initialization failed: {e}")
            # Don't set rag_available to False here, let it retry
            return False

    async def fetch_work_items_by_ids(self, work_item_ids: Set[str]) -> List[Dict[str, Any]]:
        """
        Fetch complete work item documents by their IDs from MongoDB

        Args:
            work_item_ids: Set of work item IDs (can be displayBugNo or _id)

        Returns:
            List of complete work item documents
        """
        if not work_item_ids:
            return []

        # Ensure MongoDB connection
        if not await self.ensure_mongodb_connection():
            raise RuntimeError("MongoDB connection failed")

        try:
            # Convert IDs to list for MongoDB query
            id_list = list(work_item_ids)

            # Build aggregation pipeline to fetch work items by IDs
            # We need to handle both displayBugNo and _id lookups
            pipeline = [
                {
                    "$match": {
                        "$or": [
                            {"displayBugNo": {"$in": id_list}},
                            {"_id": {"$in": id_list}}
                        ]
                    }
                }
            ]

            # Execute the query
            results = await mongodb_tools.aggregate(
                database=DATABASE_NAME,
                collection="workItem",
                pipeline=pipeline
            )

            return results if results else []

        except Exception as e:
            print(f"Warning: Failed to fetch work items by IDs: {e}")
            return []
    
    async def execute_mongo_query(
        self,
        query: str,
        show_all: bool = False,
        limit: Optional[int] = None,
    ) -> MongoQueryResult:
        """
        Execute mongo-query with the given parameters

        Args:
            query: Natural language query for MongoDB
            show_all: Whether to show all results or limit for performance

        Returns:
            MongoQueryResult with formatted work items
        """
        # Note: mongo_query is no longer used - we use plan_and_execute_query from planner

        try:
            result_payload = await plan_and_execute_query(query)

            if not isinstance(result_payload, dict):
                raise RuntimeError("Planner returned unexpected response type")

            if not result_payload.get("success"):
                raise RuntimeError(result_payload.get("error", "Unknown planner error"))

            raw_rows = result_payload.get("result") or []

            work_items: List[Dict[str, Any]] = []
            total_count: int = 0

            if isinstance(raw_rows, list):
                for item in raw_rows:
                    if isinstance(item, dict):
                        work_items.append(item)
                    elif isinstance(item, str):
                        try:
                            parsed_item = json.loads(item)
                            if isinstance(parsed_item, dict):
                                work_items.append(parsed_item)
                        except Exception:
                            continue

                # Attempt to extract total/count metadata when present
                if raw_rows and isinstance(raw_rows[0], dict) and "total" in raw_rows[0]:
                    try:
                        total_count = int(raw_rows[0]["total"])
                    except Exception:
                        total_count = len(work_items)
                else:
                    total_count = len(work_items)

            elif isinstance(raw_rows, dict):
                # Count-only shape
                if "total" in raw_rows:
                    try:
                        total_count = int(raw_rows["total"])
                    except Exception:
                        total_count = 0
                # When single document returned
                if raw_rows:
                    work_items.append(raw_rows)

            # Honor explicit limit when provided (unless show_all requested)
            if not show_all and limit is not None and limit > 0:
                work_items = work_items[:limit]

            if total_count == 0:
                total_count = len(work_items)

            return MongoQueryResult(
                work_items=work_items,
                total_count=total_count,
                query=query,
                raw_result=result_payload,
            )

        except Exception as e:
            raise RuntimeError(f"Mongo query execution failed: {str(e)}")
    
    async def execute_rag_search(
        self,
        query: str,
        content_type: str = "work_item",  # Keep focused on work items for smart filtering
        limit: int = 20,
        use_chunk_aware: bool = True
    ) -> RAGSearchResult:
        """
        Execute RAG search to find work items by directly using retriever, then fetch complete documents.
        Optimized to avoid returning chunk content to save tokens.

        Args:
            query: Search query
            content_type: Content type to search (default: work_item)
            limit: Maximum results to retrieve
            use_chunk_aware: Whether to use chunk-aware retrieval

        Returns:
            RAGSearchResult with complete work item documents
        """
        try:
            work_item_ids = set()
            reconstructed_docs = None

            # Try optimized path first: use ChunkAwareRetriever directly
            rag_initialized = await self.ensure_rag_initialized()
            if rag_initialized and self.retriever and use_chunk_aware:
                try:
                    # Get reconstructed docs directly without formatting content for agent
                    reconstructed_docs = await self.retriever.search_with_context(
                        query=query,
                        collection_name=QDRANT_COLLECTION_NAME,
                        content_type=content_type,
                        limit=limit,
                        chunks_per_doc=3,
                        include_adjacent=True,
                        min_score=0.1,  # Lower threshold for better recall
                        min_keyword_overlap=0.0,  # Remove keyword overlap requirement
                        context_token_budget=4000
                    )

                    # Extract work item IDs directly from reconstructed docs
                    for doc in reconstructed_docs:
                        if doc.mongo_id:
                            work_item_ids.add(str(doc.mongo_id))

                        # Collect metadata-sourced identifiers
                        if doc.metadata:
                            for key in ["mongo_id", "work_item_id", "workItemId", "displayBugNo", "display_bug_no"]:
                                value = doc.metadata.get(key)
                                if isinstance(value, str) and value.strip():
                                    work_item_ids.add(value.strip())
                                elif isinstance(value, list):
                                    for item in value:
                                        if isinstance(item, str) and item.strip():
                                            work_item_ids.add(item.strip())

                        # Regex-based fallback from reconstructed content
                        try:
                            import re
                            content_lower = doc.full_content.lower()
                            patterns = [
                                r'([A-Z]+-\d+)',  # BUG-123 style identifiers
                                r'displaybugno[:\s]+([\w-]+)',
                                r'bug[:\s]+([\w-]+)',
                            ]
                            for pattern in patterns:
                                for match in re.findall(pattern, content_lower, re.IGNORECASE):
                                    if isinstance(match, tuple):
                                        match = match[0]
                                    cleaned = re.sub(r'[^\w-]', '', match)
                                    if cleaned:
                                        work_item_ids.add(cleaned)
                        except Exception:
                            pass

                except Exception as e:
                    print(f"⚠️ Direct RAG search failed: {e}")

            # Fallback: use rag_search tool if optimized path failed or no IDs found
            if not work_item_ids and rag_search:
                try:
                    result = await rag_search.ainvoke({
                        "query": query,
                        "content_type": content_type,
                        "limit": limit,
                        "show_content": False,  # Don't return content to save tokens
                        "use_chunk_aware": use_chunk_aware
                    })

                    # Parse minimal result to extract work item IDs
                    lines = result.split('\n')
                    for line in lines:
                        line = line.strip()

                        # Look for work item patterns in the minimal content
                        if content_type == "work_item" and 'displayBugNo:' in line:
                            try:
                                bug_match = line.split('displayBugNo: ')[1]
                                if bug_match:
                                    bug_number = bug_match.split()[0].rstrip(',')
                                    if bug_number and len(bug_number) > 2:
                                        work_item_ids.add(bug_number)
                            except Exception:
                                pass

                        # Look for ID patterns
                        if 'mongo_id:' in line or 'id:' in line:
                            try:
                                id_part = line.split(':')[1].strip()
                                if id_part and len(id_part) > 2:
                                    work_item_ids.add(id_part)
                            except Exception:
                                pass

                except Exception as e:
                    print(f"Warning: Fallback RAG search failed: {e}")

            # Fetch complete work item documents by IDs
            work_items = []
            if work_item_ids:
                work_items = await self.fetch_work_items_by_ids(work_item_ids)
                # Limit results to the requested limit
                work_items = work_items[:limit]

            return RAGSearchResult(
                work_items=work_items,
                total_count=len(work_items),
                query=query,
                reconstructed_docs=reconstructed_docs,
                work_item_ids=work_item_ids,
                rag_context=""
            )

        except Exception as e:
            raise RuntimeError(f"RAG search execution failed: {str(e)}")



# Global instance
smart_filter_tools = SmartFilterTools()
