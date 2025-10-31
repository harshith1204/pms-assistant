"""
Smart Filter Agent - Combines RAG retrieval with MongoDB queries for intelligent work item filtering
"""

import json
import asyncio
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass
from datetime import datetime

from qdrant.retrieval import ChunkAwareRetriever
from mongo.constants import mongodb_tools, DATABASE_NAME
from mongo.registry import build_lookup_stage
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

# Orchestration utilities
from orchestrator import Orchestrator, StepSpec, as_async

import os
from dotenv import load_dotenv
load_dotenv()

groq_api_key = os.getenv("GROQ_API_KEY")
if not groq_api_key:
    raise ValueError("FATAL: GROQ_API_KEY environment variable not set.")


@dataclass
class SmartFilterResult:
    """Result from smart filtering operation"""
    work_items: List[Dict[str, Any]]
    total_count: int
    query: str
    rag_context: str
    mongo_query: Dict[str, Any]


class SmartFilterAgent:
    """Agent that combines RAG retrieval with MongoDB queries for intelligent work item filtering"""

    def __init__(self):
        self.llm = ChatGroq(
            model="openai/gpt-oss-120b",
            temperature=0.1,  # Slightly creative for query understanding
            max_tokens=1024,
            top_p=0.8,
        )

        # Initialize RAG components
        from qdrant.initializer import RAGTool
        self.rag_tool = RAGTool()
        self.retriever = ChunkAwareRetriever(
            qdrant_client=self.rag_tool.qdrant_client,
            embedding_model=self.rag_tool.embedding_model
        )

        # Initialize orchestrator for coordinated execution
        self.orchestrator = Orchestrator(tracer_name=__name__, max_parallel=3)

    def _extract_work_item_ids_from_rag(self, reconstructed_docs: List) -> Set[str]:
        """Extract work item IDs from RAG retrieval results"""
        work_item_ids = set()

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

        return work_item_ids

    def _build_mongo_query_from_rag(self, query: str, work_item_ids: Set[str], rag_context: str) -> Dict[str, Any]:
        """Build MongoDB aggregation query based on RAG context and extracted IDs"""

        # Use LLM to understand what filters to apply based on the natural language query
        filter_prompt = f"""
        Based on this natural language query: "{query}"

        And this RAG context from relevant documents:
        {rag_context[:2000]}  # Limit context to avoid token limits

        Extract filtering criteria for work items. Return a JSON object with these possible filters:
        - priority: array of priorities like ["HIGH", "MEDIUM", "LOW", "URGENT", "NONE"]
        - state: array of state names like ["Backlog", "In-Progress", "Completed"]
        - assignee: array of assignee names
        - label: array of label names
        - project: project name or identifier
        - module: module name
        - cycle: cycle name
        - startDate: date string in format "DD-MM-YYYY" or ISO
        - endDate: date string in format "DD-MM-YYYY" or ISO

        Only include filters that are clearly mentioned or strongly implied. Return empty object {{}} if no clear filters.

        Example response:
        {{"priority": ["HIGH", "URGENT"], "state": ["In-Progress"], "assignee": ["John Doe"]}}
        """

        try:
            response = self.llm.invoke([
                SystemMessage(content="You are a query parser that extracts filtering criteria from natural language. Return only valid JSON."),
                HumanMessage(content=filter_prompt)
            ])

            filter_criteria = json.loads(response.content.strip())
        except Exception as e:
            print(f"Error parsing filter criteria: {e}")
            filter_criteria = {}

        # Build MongoDB aggregation pipeline
        pipeline = []

        # Match stage - combine RAG-found IDs with user-specified filters
        match_conditions = {}

        # Add work item IDs from RAG if any were found
        if work_item_ids:
            # Try to match by displayBugNo first, then by ID
            match_conditions["$or"] = [
                {"displayBugNo": {"$in": list(work_item_ids)}},
                {"id": {"$in": list(work_item_ids)}}
            ]

        # Add filters from LLM parsing
        if filter_criteria.get("priority"):
            match_conditions["priority"] = {"$in": filter_criteria["priority"]}

        if filter_criteria.get("state"):
            match_conditions["state.name"] = {"$in": filter_criteria["state"]}

        if filter_criteria.get("assignee"):
            match_conditions["assignee.name"] = {"$in": filter_criteria["assignee"]}

        if filter_criteria.get("label"):
            match_conditions["label.name"] = {"$in": filter_criteria["label"]}

        if filter_criteria.get("project"):
            match_conditions["project.name"] = filter_criteria["project"]

        if filter_criteria.get("module"):
            match_conditions["modules.name"] = filter_criteria["module"]

        if filter_criteria.get("cycle"):
            match_conditions["cycle.name"] = filter_criteria["cycle"]

        # Date filters
        if filter_criteria.get("startDate"):
            try:
                # Try to parse various date formats
                start_date = self._parse_date(filter_criteria["startDate"])
                if start_date:
                    match_conditions["$or"] = match_conditions.get("$or", [])
                    match_conditions["$or"].append({"startDate": {"$gte": start_date}})
                    match_conditions["$or"].append({"createdOn": {"$gte": start_date}})
            except:
                pass

        if filter_criteria.get("endDate"):
            try:
                end_date = self._parse_date(filter_criteria["endDate"])
                if end_date:
                    match_conditions["$or"] = match_conditions.get("$or", [])
                    match_conditions["$or"].append({"endDate": {"$lte": end_date}})
                    match_conditions["$or"].append({"dueDate": {"$lte": end_date}})
            except:
                pass

        if match_conditions:
            pipeline.append({"$match": match_conditions})

        # Add necessary lookups for the response structure
        required_relations = {
            "workItem": ["project", "state", "assignee", "label", "modules", "cycle", "createdBy"]
        }

        for relation in required_relations.get("workItem", []):
            lookup_stage = build_lookup_stage("workItem", relation)
            if lookup_stage:
                pipeline.append(lookup_stage)

        # Project to match the required API response structure
        pipeline.append({
            "$project": {
                "id": 1,
                "displayBugNo": 1,
                "title": 1,
                "description": 1,
                "state": {
                    "id": "$state.id",
                    "name": "$state.name"
                },
                "priority": 1,
                "assignee": {
                    "$map": {
                        "input": "$assignee",
                        "as": "a",
                        "in": {
                            "id": "$$a.id",
                            "name": "$$a.name"
                        }
                    }
                },
                "label": {
                    "$map": {
                        "input": "$label",
                        "as": "l",
                        "in": {
                            "id": "$$l.id",
                            "name": "$$l.name",
                            "color": "$$l.color"
                        }
                    }
                },
                "modules": {
                    "id": "$modules.id",
                    "name": "$modules.name"
                },
                "cycle": {
                    "id": "$cycle.id",
                    "name": "$cycle.name",
                    "title": "$cycle.title"
                },
                "startDate": 1,
                "endDate": 1,
                "dueDate": 1,
                "createdOn": 1,
                "updatedOn": 1,
                "releaseDate": 1,
                "createdBy": {
                    "id": "$createdBy.id",
                    "name": "$createdBy.name"
                },
                "subWorkItem": 1,
                "attachment": 1
            }
        })

        # Limit results to prevent overwhelming responses
        pipeline.append({"$limit": 50})

        return {
            "database": DATABASE_NAME,
            "collection": "workItem",
            "pipeline": pipeline
        }

    def _parse_date(self, date_str: str) -> Optional[str]:
        """Parse various date formats into ISO string"""
        from datetime import datetime
        formats = [
            "%d-%m-%Y",  # DD-MM-YYYY
            "%Y-%m-%d",  # YYYY-MM-DD
            "%d/%m/%Y",  # DD/MM/YYYY
            "%Y/%m/%d",  # YYYY/MM/DD
            "%B %d, %Y", # Month DD, YYYY
            "%b %d, %Y", # Mon DD, YYYY
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.isoformat()
            except ValueError:
                continue
        return None

    async def smart_filter_work_items(self, query: str, limit: int = 50) -> SmartFilterResult:
        """
        Perform smart filtering of work items using RAG + MongoDB with orchestrated execution

        Args:
            query: Natural language query
            limit: Maximum number of work items to return

        Returns:
            SmartFilterResult with filtered work items and metadata
        """
        try:
            # Define orchestrated steps as closures to capture self and parameters
            async def _ensure_mongodb_connection(ctx: Dict[str, Any]) -> bool:
                """Ensure MongoDB connection is established"""
                await mongodb_tools.connect()
                return True

            async def _perform_rag_retrieval(ctx: Dict[str, Any]) -> List:
                """Perform RAG retrieval to find relevant work item documents"""
                query_text = ctx["query"]  # type: ignore[index]
                return await self.retriever.search_with_context(
                    query=query_text,
                    collection_name=self.rag_tool.collection_name,
                    content_type="work_item",  # Focus on work items
                    limit=20,  # Get more context for better filtering
                    chunks_per_doc=2,
                    include_adjacent=True,
                    min_score=0.3,
                    enable_keyword_fallback=True,
                    context_token_budget=4000  # Reasonable token budget
                )

            def _extract_work_item_ids(ctx: Dict[str, Any]) -> Set[str]:
                """Extract work item IDs from RAG results"""
                rag_results = ctx["rag_results"]  # type: ignore[index]
                return self._extract_work_item_ids_from_rag(rag_results)

            def _format_rag_context(ctx: Dict[str, Any]) -> str:
                """Format RAG results into context string for LLM"""
                rag_results = ctx["rag_results"]  # type: ignore[index]
                from qdrant.retrieval import format_reconstructed_results
                return format_reconstructed_results(rag_results, show_full_content=True)

            def _build_mongodb_query(ctx: Dict[str, Any]) -> Dict[str, Any]:
                """Build MongoDB aggregation query based on RAG context"""
                query_text = ctx["query"]  # type: ignore[index]
                work_item_ids = ctx["work_item_ids"]  # type: ignore[index]
                rag_context = ctx["rag_context"]  # type: ignore[index]
                return self._build_mongo_query_from_rag(query_text, work_item_ids, rag_context)

            async def _execute_mongodb_query(ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
                """Execute the MongoDB aggregation query"""
                mongo_query = ctx["mongo_query"]  # type: ignore[index]
                results = await mongodb_tools.execute_tool("aggregate", mongo_query)
                return results if results and isinstance(results, list) else []

            # Define the orchestrated steps with dependencies and error handling
            steps: List[StepSpec] = [
                StepSpec(
                    name="ensure_connection",
                    coroutine=as_async(_ensure_mongodb_connection),
                    requires=(),
                    provides="connection_established",
                    retries=2,
                    timeout_s=8.0,
                ),
                StepSpec(
                    name="rag_retrieval",
                    coroutine=as_async(_perform_rag_retrieval),
                    requires=("query",),
                    provides="rag_results",
                    timeout_s=25.0,
                    retries=1,
                ),
                StepSpec(
                    name="extract_work_item_ids",
                    coroutine=as_async(_extract_work_item_ids),
                    requires=("rag_results",),
                    provides="work_item_ids",
                    timeout_s=5.0,
                ),
                StepSpec(
                    name="format_rag_context",
                    coroutine=as_async(_format_rag_context),
                    requires=("rag_results",),
                    provides="rag_context",
                    timeout_s=5.0,
                ),
                StepSpec(
                    name="build_mongodb_query",
                    coroutine=as_async(_build_mongodb_query),
                    requires=("query", "work_item_ids", "rag_context"),
                    provides="mongo_query",
                    timeout_s=10.0,
                ),
                StepSpec(
                    name="execute_query",
                    coroutine=as_async(_execute_mongodb_query),
                    requires=("mongo_query", "connection_established"),
                    provides="work_items",
                    timeout_s=20.0,
                    retries=1,
                ),
            ]

            # Execute the orchestrated workflow
            ctx = await self.orchestrator.run(
                steps,
                initial_context={"query": query, "limit": limit},
                correlation_id=f"smart_filter_{hash(query) & 0xFFFFFFFF:x}",
            )

            # Extract results from the orchestrated context
            work_items = ctx.get("work_items", [])
            rag_context = ctx.get("rag_context", "")
            mongo_query = ctx.get("mongo_query", {})

            return SmartFilterResult(
                work_items=work_items,
                total_count=len(work_items),
                query=query,
                rag_context=rag_context,
                mongo_query=mongo_query
            )

        except Exception as e:
            print(f"Error in orchestrated smart filtering: {e}")
            import traceback
            traceback.print_exc()

            # Fallback: return empty results
            return SmartFilterResult(
                work_items=[],
                total_count=0,
                query=query,
                rag_context="",
                mongo_query={}
            )


# Global instance
smart_filter_agent = SmartFilterAgent()
