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
    work_item_ids: Set[str]
    rag_context: str
    reconstructed_docs: List[Any]
    query: str


class SmartFilterTools:
    """Tools for smart-filter agent to call mongo-query and RAG functionality"""
    
    def __init__(self):
        # Initialize RAG components if available
        self.rag_tool = None
        self.retriever = None
        self.rag_available = False
        
        if RAGTool:
            try:
                # Try to initialize RAGTool with error handling
                self.rag_tool = RAGTool.get_instance()
                # Only initialize retriever if RAG tool is available
                if self.rag_tool:
                    self.retriever = ChunkAwareRetriever(
                        qdrant_client=self.rag_tool.qdrant_client,
                        embedding_model=self.rag_tool.embedding_model
                    )
                    self.rag_available = True
            except Exception as e:
                print(f"Warning: RAG initialization failed: {e}")
                # RAG initialization failed - tools will be unavailable
                self.rag_tool = None
                self.retriever = None
                self.rag_available = False
    
    async def ensure_mongodb_connection(self) -> bool:
        """Ensure MongoDB connection is established"""
        if not mongodb_tools:
            return False
        
        try:
            await mongodb_tools.connect()
            return True
        except Exception:
            return False
    
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
        content_type: str = "work_item", 
        limit: int = 20,
        use_chunk_aware: bool = True
    ) -> RAGSearchResult:
        """
        Execute RAG search to find work items and descriptions
        
        Args:
            query: Search query
            content_type: Content type to search (default: work_item)
            limit: Maximum results to retrieve
            use_chunk_aware: Whether to use chunk-aware retrieval
            
        Returns:
            RAGSearchResult with extracted work item IDs and context
        """
        if not rag_search:
            raise RuntimeError("rag_search tool not available")
        
        try:
            # Execute the rag_search tool using ainvoke method for async invocation
            result = await rag_search.ainvoke({
                "query": query,
                "content_type": content_type,
                "limit": limit,
                "show_content": True,
                "use_chunk_aware": use_chunk_aware
            })
            
            # Extract work item IDs and context from the result
            work_item_ids = set()
            reconstructed_docs = []
            rag_context = ""
            
            # Parse the result to extract work item IDs
            lines = result.split('\n')
            content_start = False  # Initialize content_start flag
            
            for line in lines:
                line = line.strip()
                
                # Look for work item patterns in the content
                if content_type == "work_item" and 'displayBugNo:' in line:
                    # Extract bug number from lines like "• BUG-123: title..."
                    try:
                        bug_match = line.split('displayBugNo: ')[1]
                        if bug_match:
                            # Clean up the bug number
                            bug_number = bug_match.split()[0].rstrip(',')
                            if bug_number and len(bug_number) > 2:
                                work_item_ids.add(bug_number)
                    except Exception:
                        pass
                
                # Look for ID patterns in content
                if 'mongo_id:' in line or 'id:' in line:
                    try:
                        id_part = line.split(':')[1].strip()
                        if id_part and len(id_part) > 2:
                            work_item_ids.add(id_part)
                    except Exception:
                        pass
                
                # Collect the full context for the agent
                if '=== CONTENT START ===' in line:
                    content_start = True
                    continue
                elif '=== CONTENT END ===' in line:
                    content_start = False
                    continue
                
                if content_start:
                    rag_context += line + '\n'
            
            # If we have a retriever available, we can also search directly
            if self.retriever:
                try:
                    reconstructed_docs = await self.retriever.search_with_context(
                        query=query,
                        collection_name=QDRANT_COLLECTION_NAME,
                        content_type=content_type,
                        limit=limit,
                        chunks_per_doc=3,
                        include_adjacent=True,
                        min_score=0.5,
                        context_token_budget=4000
                    )

                    # Extract identifiers and keep reconstructed docs for downstream usage
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

                    reconstructed_docs = reconstructed_docs or []

                except Exception as e:
                    print(f"Warning: Direct RAG search failed: {e}")
            
            return RAGSearchResult(
                work_item_ids=work_item_ids,
                rag_context=rag_context,
                reconstructed_docs=reconstructed_docs,
                query=query
            )
            
        except Exception as e:
            raise RuntimeError(f"RAG search execution failed: {str(e)}")



# Global instance
smart_filter_tools = SmartFilterTools()
