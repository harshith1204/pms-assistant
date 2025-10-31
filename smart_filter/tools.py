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
from orchestrator import Orchestrator, StepSpec, as_async
from .planner import plan_and_execute_query
# Import the existing tools
try:
    from tools import mongo_query, rag_search
except ImportError:
    # Fallback for testing
    mongo_query = None
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
    
    async def execute_mongo_query(self, query: str, show_all: bool = False) -> MongoQueryResult:
        """
        Execute mongo-query with the given parameters
        
        Args:
            query: Natural language query for MongoDB
            show_all: Whether to show all results or limit for performance
            
        Returns:
            MongoQueryResult with formatted work items
        """
        if not mongo_query:
            raise RuntimeError("mongo_query tool not available")
        
        try:
            result = await plan_and_execute_query(query)
            # Execute the mongo-query tool
            
            # Parse the result to extract work items
            work_items = []
            total_count = 0
            
            # Try to parse the result string as JSON first
            try:
                parsed_result = json.loads(result)
                
                # Handle different possible result formats
                if isinstance(parsed_result, list):
                    # Direct list of work items
                    work_items = parsed_result
                    total_count = len(parsed_result)
                elif isinstance(parsed_result, dict):
                    # Dictionary format - look for common keys
                    if 'data' in parsed_result:
                        work_items = parsed_result['data']
                    elif 'work_items' in parsed_result:
                        work_items = parsed_result['work_items']
                    elif 'results' in parsed_result:
                        work_items = parsed_result['results']
                    else:
                        # Try to find any list in the result
                        for value in parsed_result.values():
                            if isinstance(value, list):
                                work_items = value
                                break
                    
                    total_count = len(work_items)
                    
                    # Try to get total count from metadata
                    if 'total' in parsed_result:
                        total_count = parsed_result['total']
                    elif 'total_count' in parsed_result:
                        total_count = parsed_result['total_count']
                        
            except json.JSONDecodeError:
                # Result is a string - parse it manually
                lines = result.split('\n')
                in_results_section = False
                
                for line in lines:
                    line = line.strip()
                    if line.startswith('📊 RESULTS:') or line.startswith('📊 RESULT:'):
                        in_results_section = True
                        continue
                    
                    if line.startswith('🎯 INTELLIGENT QUERY RESULT:'):
                        # Extract query info
                        continue
                    
                    if line.startswith('📋 UNDERSTOOD INTENT:') or line.startswith('🔧 GENERATED PIPELINE:'):
                        in_results_section = False
                        continue
                    
                    if in_results_section and line.startswith('• '):
                        # This is a work item - parse it
                        try:
                            # Extract JSON from the line if present
                            if '{' in line and '}' in line:
                                json_part = line[line.find('{'):line.rfind('}') + 1]
                                item = json.loads(json_part)
                                work_items.append(item)
                        except Exception:
                            # Skip parsing errors
                            pass
                    elif line.startswith('Found') and 'item(s)' in line:
                        # Extract count from "Found X items" message
                        try:
                            count_part = line.split('item(s)')[0].split('Found ')[1]
                            total_count = int(count_part.strip())
                        except Exception:
                            pass
            
            return MongoQueryResult(
                work_items=work_items,
                total_count=total_count,
                query=query,
                raw_result=result
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
                    
                    # Extract work item IDs from reconstructed docs
                    for doc in reconstructed_docs:
                        # Extract work item IDs from content using regex patterns
                        import re
                        
                        # Look for patterns like "HELLO-123", work item numbers, or IDs
                        patterns = [
                            r'([A-Z]+-\d+)',  # HELLO-123 format
                            r'work.?item.?(\w+)',  # work item mentions
                            r'task.?(\w+)',  # task mentions
                            r'issue.?(\w+)',  # issue mentions
                        ]
                        
                        content = doc.full_content.lower()
                        for pattern in patterns:
                            matches = re.findall(pattern, content, re.IGNORECASE)
                            for match in matches:
                                if isinstance(match, tuple):
                                    match = match[0]
                                # Clean the match
                                clean_match = re.sub(r'[^\w-]', '', str(match))
                                if clean_match and len(clean_match) > 2:
                                    work_item_ids.add(clean_match)
                        
                        # Also check metadata for direct work item references
                        if doc.metadata.get('work_item_id'):
                            work_item_ids.add(doc.metadata['work_item_id'])
                        if doc.metadata.get('display_bug_no'):
                            work_item_ids.add(doc.metadata['display_bug_no'])
                            
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
    
        
        # # Project to match the required API response structure
        # pipeline.append({
        #     "$project": {
        #         "id": 1,
        #         "displayBugNo": 1,
        #         "title": 1,
        #         "description": 1,
        #         "state": {
        #             "id": "$state.id",
        #             "name": "$state.name"
        #         },
        #         "priority": 1,
        #         "assignee": {
        #             "$map": {
        #                 "input": "$assignee",
        #                 "as": "a",
        #                 "in": {
        #                     "id": "$$a.id",
        #                     "name": "$$a.name"
        #                 }
        #             }
        #         },
        #         "label": {
        #             "$map": {
        #                 "input": "$label",
        #                 "as": "l",
        #                 "in": {
        #                     "id": "$$l.id",
        #                     "name": "$$l.name",
        #                     "color": "$$l.color"
        #                 }
        #             }
        #         },
        #         "modules": {
        #             "id": "$modules.id",
        #             "name": "$modules.name"
        #         },
        #         "cycle": {
        #             "id": "$cycle.id",
        #             "name": "$cycle.name",
        #             "title": "$cycle.title"
        #         },
        #         "startDate": 1,
        #         "endDate": 1,
        #         "dueDate": 1,
        #         "createdOn": 1,
        #         "updatedOn": 1,
        #         "releaseDate": 1,
        #         "createdBy": {
        #             "id": "$createdBy.id",
        #             "name": "$$createdBy.name"
        #         },
        #         "subWorkItem": 1,
        #         "attachment": 1
        #     }
        # })
        
        # # Limit results to prevent overwhelming responses
        # pipeline.append({"$limit": 50})
        
        # return {
        #     "database": DATABASE_NAME,
        #     "collection": "workItem",
        #     "pipeline": pipeline
        # }


# Global instance
smart_filter_tools = SmartFilterTools()
