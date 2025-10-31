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
from mongo.registry import build_lookup_stage, REL
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from .tools import smart_filter_tools
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

DEFAULT_SYSTEM_PROMPT = (
"You are an intelligent query-routing agent that decides which tool to use for each user query.\n"
"Your job is to select exactly one of the following tools for every request:\n"

"Tools:\n"

"build_mongo_query – Use this when the query involves structured, filterable data.\n"
"Examples include queries that specify attributes such as priority, state, assignee, project, module, date, cycle, or label,\n"
"or that request lists, counts, metrics, or tabular data.\n"
"Examples:\n"

"“Show all high-priority bugs assigned to John.”\n"

"“List completed tasks from last week.”\n"

"rag_search – Use this when the query is open-ended, descriptive, or conceptual, requiring semantic understanding, summaries, reasoning, or explanations.\n"
"Examples:\n"

"“Summarize recent login crash reports.”\n"

"“What’s blocking the Alpha release?”\n"

"Routing Rules:\n"

"Always choose exactly one tool. Never choose both.\n"

"Prefer build_mongo_query whenever structured filters or data attributes are explicitly mentioned.\n"

"Use rag_search for vague, narrative, or reasoning-based requests.\n"

"Output only the tool call in the correct format — never provide a direct answer.\n"

"Goal:\n"
"Determine the user’s intent precisely and route the query deterministically to the appropriate tool."
)

class SmartFilterAgent:
    """Agent that combines RAG retrieval with MongoDB queries for intelligent work item filtering"""

    def __init__(self, max_steps: int = 2, system_prompt: Optional[str] = DEFAULT_SYSTEM_PROMPT):
        self.llm = ChatGroq(
            model="openai/gpt-oss-120b",
            temperature=0.1,  # Slightly creative for query understanding
            max_tokens=1024,
            top_p=0.8,
        )
        self.connected = False
        self.max_steps = max_steps
        self.system_prompt = system_prompt
        from qdrant.initializer import RAGTool
        from mongo.constants import QDRANT_COLLECTION_NAME
        self.rag_tool = RAGTool.get_instance()
        self.collection_name = QDRANT_COLLECTION_NAME
        self.retriever = ChunkAwareRetriever(
            qdrant_client=self.rag_tool.qdrant_client,
            embedding_model=self.rag_tool.embedding_model
        )
        # Initialize RAG components
        

        
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
        #             "name": "$createdBy.name"
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

    
            
# Global instance - initialized lazily during startup
smart_filter_agent = None
