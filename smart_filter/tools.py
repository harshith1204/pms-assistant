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
        
    @tool
    async def mongo_query(self, query: str, show_all: bool = False) -> MongoQueryResult:
        """
        Execute mongo-query with the given parameters
        
        Args:
            query: Natural language query for MongoDB
            show_all: Whether to show all results or limit for performance
            
        Returns:
            MongoQueryResult with formatted work items
        """
        if not plan_and_execute_query:
            raise RuntimeError("mongo-query tool not available")
        
        result = await plan_and_execute_query(query)
            
        if result["success"]:
            response = f"🎯 INTELLIGENT QUERY RESULT:\n"
            response += f"Query: '{query}'\n\n"

            # Show parsed intent
            intent = result["intent"]
            response += f"📋 UNDERSTOOD INTENT:\n"
            if result.get("planner"):
                response += f"• Planner: {result['planner']}\n"
            response += f"• Primary Entity: {intent['primary_entity']}\n"
            if intent['target_entities']:
                response += f"• Related Entities: {', '.join(intent['target_entities'])}\n"
            if intent['filters']:
                response += f"• Filters: {intent['filters']}\n"
            if intent['aggregations']:
                response += f"• Aggregations: {', '.join(intent['aggregations'])}\n"
            response += "\n"

            # Show the generated pipeline (first few stages)
            pipeline = result.get("pipeline")
            pipeline_js = result.get("pipeline_js")
            if pipeline_js:
                response += f"🔧 GENERATED PIPELINE:\n"
                response += pipeline_js
                response += "\n"
            elif pipeline:
                response += f"🔧 GENERATED PIPELINE:\n"
                # Import the formatting function from planner
                try:
                    from .planner import _format_pipeline_for_display
                    formatted_pipeline = _format_pipeline_for_display(pipeline)
                    response += formatted_pipeline
                except ImportError:
                    # Fallback to JSON format if import fails
                    for i, stage in enumerate(pipeline):
                        stage_name = list(stage.keys())[0]
                        # Format the stage content nicely
                        stage_content = json.dumps(stage[stage_name], indent=2)
                        # Truncate very long content for readability but show complete structure
                        if len(stage_content) > 200:
                            stage_content = stage_content + "..."
                        response += f"• {stage_name}: {stage_content}\n"
                response += "\n"

            # Show results (compact preview)
            rows = result.get("result")
            try:
                # Attempt to parse stringified JSON results
                if isinstance(rows, str):
                    parsed = json.loads(rows)
                else:
                    parsed = rows
            except Exception:
                parsed = rows


            def format_llm_friendly(data, max_items=50, primary_entity: Optional[str] = None):
                """Format data in a more LLM-friendly way to avoid hallucinations."""
                def get_nested(d: Dict[str, Any], key: str) -> Any:
                    if key in d:
                        return d[key]
                    if "." in key:
                        cur: Any = d
                        for part in key.split("."):
                            if isinstance(cur, dict) and part in cur:
                                cur = cur[part]
                            else:
                                return None
                        return cur
                    return None

                def ensure_list_str(val: Any) -> List[str]:
                    if isinstance(val, list):
                        res: List[str] = []
                        for x in val:
                            if isinstance(x, str) and x.strip():
                                res.append(x)
                            elif isinstance(x, dict):
                                n = x.get("name") or x.get("title")
                                if isinstance(n, str) and n.strip():
                                    res.append(n)
                        return res
                    if isinstance(val, dict):
                        n = val.get("name") or val.get("title")
                        return [n] if isinstance(n, str) and n.strip() else []
                    if isinstance(val, str) and val.strip():
                        return [val]
                    return []

                def truncate_str(s: Any, limit: int = 120) -> str:
                    if not isinstance(s, str):
                        return str(s)
                    return s if len(s) <= limit else s[:limit] + "..."

                def render_line(entity: Dict[str, Any]) -> str:
                    e = (primary_entity or "").lower()
                    if e == "workitem":
                        bug = entity.get("displayBugNo") or entity.get("title") or "Item"
                        title = entity.get("title") or entity.get("name") or ""
                        state = entity.get("stateName") or get_nested(entity, "state.name")
                        project = entity.get("projectName") or get_nested(entity, "project.name")
                        assignees = ensure_list_str(entity.get("assignees") or entity.get("assignee"))
                        priority = entity.get("priority")
                        label = entity.get_nested(entity,"label.name")
                        # Build base line
                        base = f"• {bug}: {truncate_str(title, 80)} — state={state or 'N/A'}, priority={priority or 'N/A'}, assignee={(assignees[0] if assignees else 'N/A')}, project={project or 'N/A'}, label={label or 'N/A'}"
                        
                        # Add estimate if present
                        estimate = entity.get("estimate")
                        if estimate and isinstance(estimate, dict):
                            hr = estimate.get("hr", "0")
                            min_val = estimate.get("min", "0")
                            base += f", estimate={hr}h {min_val}m"
                        elif estimate:
                            base += f", estimate={estimate}"
                        
                        # Add work logs if present
                        work_logs = entity.get("workLogs")
                        if work_logs and isinstance(work_logs, list) and len(work_logs) > 0:
                            total_hours = sum(log.get("hours", 0) for log in work_logs if isinstance(log, dict))
                            total_mins = sum(log.get("minutes", 0) for log in work_logs if isinstance(log, dict))
                            total_hours += total_mins // 60
                            total_mins = total_mins % 60
                            base += f", logged={total_hours}h {total_mins}m ({len(work_logs)} logs)"
                            
                            descriptions = [
                                log.get("description", "").strip()
                                for log in work_logs
                                if isinstance(log, dict) and log.get("description")
                            ]
                            descriptions_text = "; ".join(descriptions) if descriptions else "No descriptions"

                            base += f", descriptions=[{descriptions_text}]"
                        return base
                    title = entity.get("title") or entity.get("name") or "Item"
                    return f"• {truncate_str(title, 80)}"
                if isinstance(data, list):
                    # Handle count-only results
                    if len(data) == 1 and isinstance(data[0], dict) and "total" in data[0]:
                        return f"📊 RESULTS:\nTotal: {data[0]['total']}"

                    # Handle grouped/aggregated results
                    if len(data) > 0 and isinstance(data[0], dict) and ("count" in data[0] or "totalMinutes" in data[0]):
                        response = "📊 RESULTS SUMMARY:\n"
                        # Prefer minutes total when available, else use count
                        has_minutes = any('totalMinutes' in item for item in data)
                        total_items = sum(item.get('count', 0) for item in data)
                        total_minutes = sum(item.get('totalMinutes', 0) for item in data) if has_minutes else None

                        # Determine what type of grouping this is
                        first_item = data[0]
                        group_keys = [k for k in first_item.keys() if k not in ['count', 'items', 'totalMinutes']]

                        if group_keys:
                            if has_minutes and total_minutes is not None:
                                response += f"Found {len(data)} groups grouped by {', '.join(group_keys)} (total {int(total_minutes)} min):\n\n"
                            else:
                                response += f"Found {total_items} items grouped by {', '.join(group_keys)}:\n\n"

                            # Sort by count (highest first) and show more groups
                            if has_minutes:
                                sorted_data = sorted(data, key=lambda x: x.get('totalMinutes', 0), reverse=True)
                            else:
                                sorted_data = sorted(data, key=lambda x: x.get('count', 0), reverse=True)

                            # Show all groups if max_items is None, otherwise limit
                            display_limit = len(sorted_data) if max_items is None else 25
                            for item in sorted_data[:display_limit]:
                                group_values = [f"{k}: {item[k]}" for k in group_keys if k in item]
                                group_label = ', '.join(group_values)
                                if has_minutes:
                                    mins = int(item.get('totalMinutes', 0) or 0)
                                    response += f"• {group_label}: {mins} min\n"
                                else:
                                    count = item.get('count', 0)
                                    response += f"• {group_label}: {count} items\n"

                            if max_items is not None and len(data) > 25:
                                if has_minutes:
                                    remaining = sum(int(item.get('totalMinutes', 0) or 0) for item in sorted_data[25:])
                                    response += f"• ... and {len(data) - 25} other categories: {remaining} min\n"
                                else:
                                    remaining = sum(item.get('count', 0) for item in sorted_data[25:])
                                    response += f"• ... and {len(data) - 25} other categories: {remaining} items\n"
                            elif max_items is None and len(data) > display_limit:
                                if has_minutes:
                                    remaining = sum(int(item.get('totalMinutes', 0) or 0) for item in sorted_data[display_limit:])
                                    response += f"• ... and {len(data) - display_limit} other categories: {remaining} min\n"
                                else:
                                    remaining = sum(item.get('count', 0) for item in sorted_data[display_limit:])
                                    response += f"• ... and {len(data) - display_limit} other categories: {remaining} items\n"
                        else:
                            if has_minutes and total_minutes is not None:
                                response += f"Found total {int(total_minutes)} min\n"
                            else:
                                response += f"Found {total_items} items\n"
                        print(response)
                        return response

                    # Handle list of documents - show summary instead of raw JSON
                    if max_items is not None and len(data) > max_items:
                        response = f"📊 RESULTS SUMMARY:\n"
                        response += f"Found {len(data)} items. Showing key details for last {max_items}:\n\n"
                        # Show sample items in a collection-aware way
                        for i, item in enumerate(data[-max_items:], len(data) - max_items + 1):
                            if isinstance(item, dict):
                                response += render_line(item) + "\n"
                        if len(data) > max_items:
                            response += f"• ... and {len(data) - max_items} items were omitted above\n"
                        return response
                    else:
                        # Show all items or small list - show in formatted way
                        response = "📊 RESULTS:\n"
                        for item in data:
                            if isinstance(item, dict):
                                response += render_line(item) + "\n"
                        return response

                # Single document or other data
                if isinstance(data, dict):
                    # Format single document in a readable way
                    response = "📊 RESULT:\n"
                    # Prefer a single-line summary first
                    if isinstance(data, dict):
                        response += render_line(data) + "\n\n"
                    # Then show key fields compactly (truncate long strings)
                    for key, value in data.items():
                        if isinstance(value, (str, int, float, bool)):
                            response += f"• {key}: {truncate_str(value, 140)}\n"
                        elif isinstance(value, dict):
                            # Show only shallow summary for dict
                            name_val = value.get('name') or value.get('title')
                            if name_val:
                                response += f"• {key}: {truncate_str(name_val, 120)}\n"
                            else:
                                child_keys = ", ".join(list(value.keys())[:5])
                                response += f"• {key}: {{ {child_keys} }}\n"
                        elif isinstance(value, list):
                            if len(value) <= 5:
                                response += f"• {key}: {truncate_str(str(value), 160)}\n"
                            else:
                                response += f"• {key}: [{len(value)} items]\n"
                    return response
                else:
                    # Fallback to JSON for other data types
                    return f"📊 RESULTS:\n{json.dumps(data, indent=2)}"

            # Apply strong filter/transform now that we know the primary entity

            # Format in LLM-friendly way
            max_items = None if show_all else 50
            # If members primary entity and no rows, proactively hint about filters
            try:
                if isinstance(result.get("intent"), dict) and result["intent"].get("primary_entity") == "members" and not filtered:
                    formatted_result += "\n(No members matched. Try filtering by name, role, type, or project.)"
            except Exception:
                pass
            response += formatted_result
            print(response)
            return response
        else:
            return f"❌ QUERY FAILED:\nQuery: '{query}'\nError: {result['error']}"
    
    @tool
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
