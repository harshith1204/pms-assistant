#!/usr/bin/env python3
"""
Intelligent Query Planner for PMS System
Handles natural language queries and generates optimal MongoDB aggregation pipelines
based on the relationship registry
"""

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional, Set
import os
from dataclasses import dataclass
import copy
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from mongo.registry import REL, ALLOWED_FIELDS, build_lookup_stage
from mongo.constants import mongodb_tools, DATABASE_NAME
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
 
from langchain_groq import ChatGroq
# Orchestration utilities
from orchestrator import Orchestrator, StepSpec, as_async

# OpenInference semantic conventions (optional)
try:
    from openinference.semconv.trace import SpanAttributes as OI
except Exception:  # Fallback when OpenInference isn't installed
    class _OI:
        INPUT_VALUE = "input.value"
        OUTPUT_VALUE = "output.value"
        TOOL_INPUT = "tool.input"
        TOOL_OUTPUT = "tool.output"
        ERROR_TYPE = "error.type"
        ERROR_MESSAGE = "error.message"

    OI = _OI()
from dotenv import load_dotenv
load_dotenv()
groq_api_key = os.getenv("GROQ_API_KEY")
if not groq_api_key:
    raise ValueError(
        "FATAL: GROQ_API_KEY environment variable not set.\n"
        "Please create a .env file and add your Groq API key to it."
    )

@dataclass
class QueryIntent:
    """Represents the parsed intent of a user query"""
    primary_entity: str  # Main collection/entity (e.g., "workItem", "project")
    target_entities: List[str]  # Related entities to include
    filters: Dict[str, Any]  # Filter conditions
    aggregations: List[str]  # Aggregation operations (count, group, etc.)
    group_by: List[str]  # Grouping keys (e.g., ["cycle"]) when 'group by' present
    projections: List[str]  # Fields to return
    sort_order: Optional[Dict[str, int]]  # Sort specification
    limit: Optional[int]  # Result limit
    skip: Optional[int]  # Result offset for pagination
    wants_details: bool  # Prefer detailed documents over counts
    wants_count: bool  # Whether the user asked for a count
    fetch_one: bool  # Whether the user wants a single specific item

@dataclass
class RelationshipPath:
    """Represents a traversal path through relationships"""
    start_collection: str
    end_collection: str
    path: List[str]  # List of relationship names
    cost: int  # Computational cost of this path
    filters: Dict[str, Any]  # Filters that can be applied at each step


def _serialize_pipeline_for_json(pipeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert datetime objects in pipeline to JSON-serializable format using MongoDB ISODate format"""
    if not pipeline:
        return pipeline

    def _convert_value(value: Any) -> Any:
        if isinstance(value, datetime):
            # Use MongoDB ISODate format: new ISODate("2025-09-27T01:22:58Z")
            iso_string = value.strftime('%Y-%m-%dT%H:%M:%S.%fZ') if value.microsecond else value.strftime('%Y-%m-%dT%H:%M:%SZ')
            return {"$isodate": iso_string}  # Use a special marker that can be converted to JavaScript
        elif isinstance(value, dict):
            return {k: _convert_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [_convert_value(item) for item in value]
        else:
            return value

    return [_convert_value(stage) for stage in pipeline]

def _format_pipeline_for_display(pipeline: List[Dict[str, Any]]) -> str:
    """Format pipeline as JavaScript code for display in MongoDB shell format"""
    if not pipeline:
        return "[]"

    def _format_value(value: Any) -> str:
        if isinstance(value, dict):
            if "$isodate" in value:
                return f'new ISODate("{value["$isodate"]}")'
            else:
                items = []
                for k, v in value.items():
                    formatted_value = _format_value(v)
                    # Don't quote string values that are not meant to be strings
                    if isinstance(v, str) and v in ("true", "false", "null"):
                        items.append(f'"{k}": {formatted_value}')
                    else:
                        items.append(f'"{k}": {formatted_value}')
                return "{" + ", ".join(items) + "}"
        elif isinstance(value, list):
            items = [_format_value(item) for item in value]
            return "[" + ", ".join(items) + "]"
        elif isinstance(value, str):
            return f'"{value}"'
        else:
            return str(value)

    def _format_stage(stage: Dict[str, Any]) -> str:
        stage_name = list(stage.keys())[0]
        stage_value = stage[stage_name]
        stage_content = _format_value(stage_value)
        return f'  {stage_name}: {stage_content}'

    formatted_stages = []
    for i, stage in enumerate(pipeline):
        formatted_stages.append(_format_stage(stage))
        if i < len(pipeline) - 1:
            formatted_stages.append("")

    return "[\n" + ",\n".join(formatted_stages) + "\n]"

class LLMIntentParser:
    """LLM-backed intent parser that produces a structured plan compatible with QueryIntent.

    The LLM proposes:
    - primary_entity
    - target_entities (relations to join)
    - filters (normalized keys: status, priority, project_status, cycle_status, page_visibility,
      project_name, cycle_name, assignee_name, module_name)
    - aggregations: ["count"|"group"|"summary"]
    - group_by tokens: ["cycle","project","assignee","status","priority","module"]
    - projections (subset of allow-listed fields for the primary entity)
    - sort_order (field -> 1|-1), supported keys: createdTimeStamp, priority, status
    - limit (int)
    - wants_details, wants_count

    Safety: we filter LLM output against REL and ALLOWED_FIELDS before use.
    """

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or os.environ.get("QUERY_PLANNER_MODEL", "openai/gpt-oss-120b")
        # Keep the model reasonably deterministic for planning
        self.llm = ChatGroq(
            model=self.model_name,
            temperature=0,
            max_tokens=1024,
            top_p=0.8,
        )

        # Precompute compact schema context to keep prompts short
        self.entities: List[str] = list(REL.keys())
        self.entity_relations: Dict[str, List[str]] = {
            entity: list(REL.get(entity, {}).keys()) for entity in self.entities
        }
        self.allowed_fields: Dict[str, List[str]] = {
            entity: sorted(list(ALLOWED_FIELDS.get(entity, set()))) for entity in self.entities
        }
        # Map common synonyms to canonical entity names to reduce LLM mistakes
        self.entity_synonyms = {
            "member": "members",
            "members": "members",
            "team": "members",
            "teammate": "members",
            "teammates": "members",
            "assignee": "members",
            "assignees": "members",
            "user": "members",
            "users": "members",
            "staff": "members",
            "personnel": "members",
            "task": "workItem",
            "tasks": "workItem",
            "bug": "workItem",
            "bugs": "workItem",
            "issue": "workItem",
            "issues": "workItem",
            "tickets": "workItem",
            "ticket": "workItem",
            # timeline synonyms
            "timeline": "timeline",
            "timelines": "timeline",
            "history": "timeline",
            "activity": "timeline",
            "activities": "timeline",
            "change": "timeline",
            "changes": "timeline",
            "event": "timeline",
            "events": "timeline",
            "log": "timeline",
            "logs": "timeline",
            "audit": "timeline",
            "audits": "timeline",
        }

    def _is_placeholder(self, v) -> bool:
        if v is None:
            return True
        if not isinstance(v, str):
            return False
        s = v.strip().lower()
        return (
            s == "" or
            "?" in s or
            s.startswith("string") or
            s in {"none?", "todo?", "n/a", "<none>", "<unknown>"}
        )


    def _normalize_state_value(self, value: str) -> Optional[str]:
        """Normalize state values to match database enum"""
        state_map = {
            "open": "Open",
            "completed": "Completed",
            "backlog": "Backlog",
            "re-raised": "Re-Raised",
            "re raised": "Re-Raised",
            "reraised": "Re-Raised",
            "reopened": "Re-Raised",
            "re-opened": "Re-Raised",
            "re opened": "Re-Raised",
            "in-progress": "In-Progress",
            "in progress": "In-Progress",
            "wip": "In-Progress",
            "verified": "Verified"
        }
        return state_map.get(value.lower())

    def _normalize_priority_value(self, value: str) -> Optional[str]:
        """Normalize priority values to match database enum"""
        priority_map = {
            "urgent": "URGENT",
            "high": "HIGH",
            "medium": "MEDIUM",
            "low": "LOW",
            "none": "NONE"
        }
        return priority_map.get(value.lower())

    def _normalize_status_value(self, filter_key: str, value: str) -> Optional[str]:
        """Normalize status values based on filter type"""
        if filter_key == "project_status":
            status_map = {
                "not_started": "NOT_STARTED",
                "not started": "NOT_STARTED",
                "started": "STARTED",
                "completed": "COMPLETED",
                "overdue": "OVERDUE"
            }
        elif filter_key == "cycle_status":
            status_map = {
                "active": "ACTIVE",
                "upcoming": "UPCOMING",
                "completed": "COMPLETED"
            }
        elif filter_key == "page_visibility":
            status_map = {
                "public": "PUBLIC",
                "private": "PRIVATE",
                "archived": "ARCHIVED"
            }
        else:
            return None

        return status_map.get(value.lower())

    def _normalize_boolean_value(self, value: str) -> Optional[bool]:
        """Normalize string booleans to actual booleans"""
        if value.lower() in ["true", "1", "yes", "on"]:
            return True
        elif value.lower() in ["false", "0", "no", "off"]:
            return False
        return None

    def _normalize_boolean_value_from_any(self, value) -> Optional[bool]:
        """Normalize any type of value to boolean"""
        if isinstance(value, bool):
            return value
        elif isinstance(value, str):
            return self._normalize_boolean_value(value)
        return None

    def _infer_sort_order_from_query(self, query_text: str) -> Optional[Dict[str, int]]:
        """Infer sorting preferences from free-form query text.

        Recognizes phrases like:
        - 'recent', 'latest', 'newest' → createdTimeStamp desc (-1)
        - 'oldest', 'earliest' → createdTimeStamp asc (1)
        - 'top N priority' → priority desc (-1)
        - 'highest priority' → priority desc (-1)
        - 'top N' with time context → createdTimeStamp desc (-1)
        """
        if not query_text:
            return None

        text = query_text.lower()

        # Priority-based sorting cues (highest priority first)
        if re.search(r'\b(?:top|highest|most|high)\s+\d*\s*priority\b', text):
            return {"priority": -1}
        if re.search(r'\bpriority\s+(?:top|highest|desc|descending)\b', text):
            return {"priority": -1}
        if re.search(r'\b(?:lowest|low)\s+priority\b', text):
            return {"priority": 1}
            
        # Direct recency/age cues
        if re.search(r"\b(recent|latest|newest|most\s+recent|newer\s+first)\b", text):
            return {"createdTimeStamp": -1}
        if re.search(r"\b(oldest|earliest|older\s+first)\b", text):
            return {"createdTimeStamp": 1}
            
        # "Top N" without explicit field → assume recent (most common use case)
        if re.search(r'\btop\s+\d+\b', text) and not re.search(r'\bpriority\b', text):
            return {"createdTimeStamp": -1}

        # Asc/Desc cues when paired with time/date/created terms
        mentions_time = re.search(r"\b(time|date|created|creation|timestamp|recent)\b", text) is not None
        if mentions_time:
            if re.search(r"\b(desc|descending|new\s*->\s*old|new\s+to\s+old)\b", text):
                return {"createdTimeStamp": -1}
            if re.search(r"\b(asc|ascending|old\s*->\s*new|old\s+to\s+new)\b", text):
                return {"createdTimeStamp": 1}

        return None


    async def parse(self, query: str) -> Optional[QueryIntent]:
        """Use the LLM to produce a structured intent. Returns None on failure."""
        system = (
            "You are an expert MongoDB query planner for a Project Management System.\n"
            "Your task is to convert natural language queries into structured JSON intent objects.\n\n"

            "## DOMAIN CONTEXT\n"
            "This is a project management system with these main entities:\n"
            f"- {', '.join(self.entities)}\n\n"
            "Users ask questions in many different ways. Be flexible with their wording.\n"
            "Focus on understanding their intent, not exact keywords.\n\n"

            "## KEY RELATIONSHIPS\n"
            "- Work items belong to projects, cycles, and modules\n"
            "- Work items are assigned to team members\n"
            "- Projects contain cycles and modules\n"
            "- Cycles and modules belong to projects\n"
            "- Timeline events reference a project (and optionally a work item) and include: type, fieldChanged, message, commentText, oldValue/newValue, user.name (actor), timestamp\n\n"

            "## VERY IMPORTANT\n"
            "## AVAILABLE FILTERS (use these exact keys):\n"
            "- state: Open|Completed|Backlog|Re-Raised|In-Progress|Verified (for workItem)\n"
            "- priority: URGENT|HIGH|MEDIUM|LOW|NONE (for workItem)\n"
            "- status: (varies by collection - use appropriate values)\n"
            "- project_status: NOT_STARTED|STARTED|COMPLETED|OVERDUE (for project)\n"
            "- cycle_status: ACTIVE|UPCOMING|COMPLETED (for cycle)\n"
            "- page_visibility: PUBLIC|PRIVATE|ARCHIVED (for page)\n"
            "- access: (project access levels)\n"
            "- isActive: true|false (for projects)\n"
            "- isArchived: true|false (for projects)\n"
            "- isDefault: true|false (for cycles)\n"
            "- isFavourite: true|false (for various entities)\n"
            "- type: (member types)\n"
            "- role: (member roles)\n"
            "- visibility: PUBLIC|PRIVATE|ARCHIVED (for pages)\n"
            "- project_name, cycle_name, assignee_name, module_name\n"
            "- createdBy_name: (creator names)\n"
            "- label: (work item labels)\n"
            "- (timeline) type, fieldChanged, actor_name (user.name), work_item_title (workItemTitle), timestamp_from/timestamp_to/timestamp_within\n\n"

            "## TIMELINE DATE WINDOW (MANDATORY)\n"
            "When primary_entity = 'timeline' and the query mentions a relative period (e.g., 'today', 'yesterday', 'this week', 'last week', 'this month', 'last month'), you MUST set filters.timestamp_within accordingly.\n"
            "Examples: 'time logged today' → filters.timestamp_within = 'today'; 'recent changes last week' → 'last_week'.\n\n"

            "## TIME-BASED SORTING (CRITICAL)\n"
            "Infer sort_order from phrasing when the user implies recency or age.\n"
            "- 'recent', 'latest', 'newest', 'most recent' → {\"createdTimeStamp\": -1}\n"
            "- 'oldest', 'earliest', 'older first' → {\"createdTimeStamp\": 1}\n"
            "- If 'ascending/descending' is mentioned with created/time/date/timestamp, map to 1/-1 respectively on 'createdTimeStamp'.\n"
            "Only include sort_order when relevant; otherwise set it to null.\n\n"

            "## LIMIT EXTRACTION (CRITICAL)\n"
            "Extract the result limit intelligently from the user's query:\n"
            "- 'top N' / 'first N' / 'N items' → limit: N (e.g., 'top 5' → limit: 5)\n"
            "- 'all' / 'every' / 'list all' → limit: 1000 (high limit to get all results)\n"
            "- 'a few' / 'some' → limit: 5\n"
            "- 'several' → limit: 10\n"
            "- 'one' / 'single' / 'find X' (singular) → limit: 1, fetch_one: true\n"
            "- No specific mention → limit: 20 (reasonable default)\n"
            "- For count/aggregation queries → limit: null (no limit needed)\n"
            "IMPORTANT: When 'top N' is used, also infer appropriate sorting:\n"
            "  - 'top N' with priority context → sort_order: {\"priority\": -1}\n"
            "  - 'top N' with date/recent context → sort_order: {\"createdTimeStamp\": -1}\n\n"

            "## NAME EXTRACTION RULES - CRITICAL\n"
            "ALWAYS extract ONLY the core entity name, NEVER include descriptive phrases:\n"
            "- Query: 'work items within PMS project' → project_name: 'PMS' (NOT 'PMS project')\n"
            "- Query: 'tasks from test module' → module_name: 'test' (NOT 'test module')\n"
            "- Query: 'bugs assigned to alice' → assignee_name: 'alice' (NOT 'alice assigned')\n"
            "- Query: 'items in upcoming cycle' → cycle_name: 'upcoming' (NOT 'upcoming cycle')\n"
            "❌ WRONG: {'project_name': 'PMS project'} - this breaks regex matching!\n"
            "✅ CORRECT: {'project_name': 'PMS'} - this works with regex matching\n\n"

            "## COMPOUND FILTER PARSING\n"
            "When users write queries like 'cycles where state.active = true':\n"
            "- 'state.active = true' should map to cycle_status: 'ACTIVE' for cycle entities\n"
            "- 'state.open = true' should map to state: 'Open' for workItem entities\n"
            "- 'status.completed = true' should map to project_status: 'COMPLETED' for project entities\n"
            "- Parse 'entity.field = value' patterns and map to appropriate filter keys\n\n"

            "## COMMON QUERY PATTERNS\n"
            "- 'Show me X' → list/get details (aggregations: [])\n"
            "- 'How many X' → count (aggregations: ['count'])\n"
            "- 'Breakdown by X' → group results (aggregations: ['group'])\n"
            "- 'X assigned to Y' → filter by assignee name (Y = assignee_name)\n"
            "- 'X from/in/belonging to/associated with Y' → filter by project/cycle/module name (Y = project_name/cycle_name/module_name)\n"
            "- 'X in Y status' → filter by status/priority\n"
            "- 'work items with title containing Z' → filter by title field (Z = search term)\n"
            "- 'work items with label Z' → filter by label field (Z = exact label value)\n"
            "- 'find items containing X in title' → {\"primary_entity\": \"workItem\", \"filters\": {\"title\": \"X\"}, \"aggregations\": []}\n"
            "- 'search for Y in descriptions' → {\"primary_entity\": \"workItem\", \"filters\": {\"description\": \"Y\"}, \"aggregations\": []}\n"
            "- 'IMPORTANT: For \"containing\" queries, extract ONLY the search term (e.g., \"component\"), not the full phrase'\n"
            "- 'Y project' → if asking about work items: workItem with project_name filter\n"
            "  → Context matters: 'details of Y project' vs 'work items associated with Y project'\n"
            "- 'cycles that are active/currently active' → cycle with cycle_status: 'ACTIVE'\n"
            "- 'active cycles' → cycle with cycle_status: 'ACTIVE'\n"
            "- 'what is the email address for X' → members with name filter and email projection\n"
            "- 'member X' → members entity with name filter\n"
            "- 'project member X' → members entity with name filter\n"
            "- 'work items updated in the last 30 days' → {\"primary_entity\": \"workItem\", \"filters\": {\"updatedTimeStamp_from\": \"now-30d\"}}\n"
            "- 'tasks created since last week' → {\"primary_entity\": \"workItem\", \"filters\": {\"createdTimeStamp_from\": \"last_week\"}}\n"
            "- 'issues modified after 2024-01-01' → {\"primary_entity\": \"workItem\", \"filters\": {\"updatedTimeStamp_from\": \"2024-01-01\"}}\n"
            "- 'workItem.last_date >= current_date - 30 days' → {\"primary_entity\": \"workItem\", \"filters\": {\"updatedTimeStamp_from\": \"now-30d\"}}\n\n"
            
            "## OUTPUT FORMAT\n"
            "CRITICAL: Output ONLY the JSON object, nothing else.\n"
            "CRITICAL: The response must be parseable by json.loads().\n\n"
            "EXACT JSON structure:\n"
            "{\n"
            f'  "primary_entity": "",\n'  # Use a valid default
            '  "target_entities": [],\n'
            '  "filters": {},\n'
            '  "aggregations": [],\n'
            '  "group_by": [],\n'
            '  "projections": [],\n'
            '  "sort_order": null,\n'
            '  "limit": 20,\n'
            '  "skip": 0,\n'
            '  "wants_details": true,\n'
            '  "wants_count": false,\n'
            '  "fetch_one": false\n'
            "}\n\n"

            "## EXAMPLES\n"
            "- 'show me tasks assigned to alice' → {\"primary_entity\": \"workItem\", \"filters\": {\"assignee_name\": \"alice\"}, \"aggregations\": []}\n"
            "- 'how many bugs are there' → {\"primary_entity\": \"workItem\", \"aggregations\": [\"count\"]}\n"
            "- 'count active projects' → {\"primary_entity\": \"project\", \"filters\": {\"project_status\": \"STARTED\"}, \"aggregations\": [\"count\"]}\n"
            "- 'group tasks by priority' → {\"primary_entity\": \"workItem\", \"aggregations\": [\"group\"], \"group_by\": [\"priority\"]}\n"
            "- 'show archived projects' → {\"primary_entity\": \"project\", \"filters\": {\"isArchived\": true}, \"aggregations\": []}\n"
            "- 'find favourite modules' → {\"primary_entity\": \"module\", \"filters\": {\"isFavourite\": true}, \"aggregations\": []}\n"
            "- 'show work items with bug label' → {\"primary_entity\": \"workItem\", \"filters\": {\"label\": \"bug\"}, \"aggregations\": []}\n"
            "- 'find work items with title containing component' → {\"primary_entity\": \"workItem\", \"filters\": {\"title\": \"component\"}, \"aggregations\": []}\n"
            "- 'who created this project' → {\"primary_entity\": \"project\", \"filters\": {\"createdBy_name\": \"john\"}, \"aggregations\": []}\n"
            "- 'find active cycles' → {\"primary_entity\": \"cycle\", \"filters\": {\"cycle_status\": \"ACTIVE\"}, \"aggregations\": []}\n"
            "- 'list cycles where state.active = true' → {\"primary_entity\": \"cycle\", \"filters\": {\"cycle_status\": \"ACTIVE\"}, \"aggregations\": []}\n"
            "- 'list all cycles that currently active' → {\"primary_entity\": \"cycle\", \"filters\": {\"cycle_status\": \"ACTIVE\"}, \"aggregations\": []}\n"
            "- 'show upcoming cycles' → {\"primary_entity\": \"cycle\", \"filters\": {\"cycle_status\": \"UPCOMING\"}, \"aggregations\": []}\n"
            "- 'count completed cycles' → {\"primary_entity\": \"cycle\", \"filters\": {\"cycle_status\": \"COMPLETED\"}, \"aggregations\": [\"count\"]}\n"
            "- 'what is the email address for the project member Vikas' → {\"primary_entity\": \"members\", \"filters\": {\"name\": \"Vikas\"}, \"projections\": [\"email\"], \"aggregations\": []}\n"
            "- 'what is the role of Vikas in Simpo Builder project' → {\"primary_entity\": \"members\", \"target_entities\": [\"project\"], \"filters\": {\"name\": \"Vikas\", \"business_name\": \"Simpo.ai\"}, \"aggregations\": []}\n"
            "- 'show members in Simpo project' → {\"primary_entity\": \"members\", \"target_entities\": [\"project\"], \"filters\": {\"project_name\": \"Simpo\"}, \"aggregations\": []}\n\n"
            "- 'show recent tasks' → {\"primary_entity\": \"workItem\", \"aggregations\": [], \"sort_order\": {\"createdTimeStamp\": -1}}\n"
            "- 'list oldest projects' → {\"primary_entity\": \"project\", \"aggregations\": [], \"sort_order\": {\"createdTimeStamp\": 1}}\n"
            "- 'bugs in ascending created order' → {\"primary_entity\": \"workItem\", \"aggregations\": [], \"sort_order\": {\"createdTimeStamp\": 1}}\n"
            "- 'work items updated in the last 30 days' → {\"primary_entity\": \"workItem\", \"filters\": {\"updatedTimeStamp_from\": \"now-30d\"}, \"aggregations\": []}\n"
            "- 'tasks created since yesterday' → {\"primary_entity\": \"workItem\", \"filters\": {\"createdTimeStamp_from\": \"yesterday\"}, \"aggregations\": []}\n"
            "- 'issues from the last week' → {\"primary_entity\": \"workItem\", \"filters\": {\"updatedTimeStamp_from\": \"last_week\"}, \"aggregations\": []}\n"
            "- 'workItem.last_date >= current_date - 30 days' → {\"primary_entity\": \"workItem\", \"filters\": {\"updatedTimeStamp_from\": \"now-30d\"}, \"aggregations\": []}\n"
            "- 'top 5 priority work items' → {\"primary_entity\": \"workItem\", \"aggregations\": [], \"sort_order\": {\"priority\": -1}, \"limit\": 5}\n"
            "- 'first 10 projects' → {\"primary_entity\": \"project\", \"aggregations\": [], \"limit\": 10}\n"
            "- 'all active cycles' → {\"primary_entity\": \"cycle\", \"filters\": {\"cycle_status\": \"ACTIVE\"}, \"aggregations\": [], \"limit\": 1000}\n"
            "- 'show me a few bugs' → {\"primary_entity\": \"workItem\", \"filters\": {\"label\": \"bug\"}, \"aggregations\": [], \"limit\": 5}\n"
            "- 'find one project named X' → {\"primary_entity\": \"project\", \"filters\": {\"name\": \"X\"}, \"aggregations\": [], \"limit\": 1, \"fetch_one\": true}\n"
            "- 'recent changes for Simpo Tech' → {\"primary_entity\": \"timeline\", \"filters\": {\"project_name\": \"Simpo Tech\", \"timestamp_within\": \"last_week\"}}\n"
            "- 'who changed state to Done' → {\"primary_entity\": \"timeline\", \"filters\": {\"fieldChanged\": \"State\", \"newValue\": \"Done\"}}\n"
            "- 'time logged today' → {\"primary_entity\": \"timeline\", \"filters\": {\"type\": \"TIME_LOGGED\", \"timestamp_within\": \"today\"}}\n\n"

            "Always output valid JSON. No explanations, no thinking, just the JSON object."
        )

        user = f"Convert to JSON: {query}"

        try:
            ai = await self.llm.ainvoke([SystemMessage(content=system), HumanMessage(content=user)])
            content = ai.content.strip()
            print(f"DEBUG: LLM response: {content}")
            import re
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
            content = re.sub(r'<think>.*', '', content, flags=re.DOTALL)  # Handle incomplete tags

            # Some models wrap JSON in code fences; strip if present
            if content.startswith("```"):
                content = content.strip("`\n").split("\n", 1)[-1]
                if content.startswith("json\n"):
                    content = content[5:]

            # Try to find JSON in the response (look for { to } pattern)
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                content = json_match.group(0)

            # Ensure we have valid JSON
            if not content or content.isspace():
                return None

            data = json.loads(content)
        except Exception as e:
            print(f"DEBUG: LLM parsing exception: {e}")
            return None

        try:
            # Normalize primary entity synonyms before sanitization
            if isinstance(data, dict):
                pe = (data.get("primary_entity") or "").strip()
                if pe:
                    data["primary_entity"] = self.entity_synonyms.get(pe.lower(), pe)
            return await self._sanitize_intent(data, query)
        except Exception:
            return None

    async def _sanitize_intent(self, data: Dict[str, Any], original_query: str = "") -> QueryIntent:
        # Primary entity - trust the LLM's choice unless it's completely invalid
        requested_primary = (data.get("primary_entity") or "").strip()
        primary = requested_primary if requested_primary in self.entities else "workItem"

        # Allowed relations for primary
        allowed_rels = set(self.entity_relations.get(primary, []))
        target_entities: List[str] = []
        for rel in (data.get("target_entities") or []):
            if isinstance(rel, str) and rel.split(".")[0] in allowed_rels:
                target_entities.append(rel)

        # Simplified filter processing - keep valid filters, expanded to cover all collections
        raw_filters = data.get("filters") or {}
        filters: Dict[str, Any] = {}

        # Map legacy 'status' to 'state' for workItem if present
        if primary == "workItem" and "status" in raw_filters and "state" not in raw_filters:
            raw_filters["state"] = raw_filters.pop("status")

        # Allow plain 'status' for project/cycle as their canonical status
        if primary in ("project", "cycle") and "status" in raw_filters:
            if primary == "project" and "project_status" not in raw_filters:
                raw_filters["project_status"] = raw_filters["status"]
            if primary == "cycle" and "cycle_status" not in raw_filters:
                raw_filters["cycle_status"] = raw_filters["status"]

        # Normalize date filter key synonyms BEFORE validation so they are preserved
        # Examples the LLM might emit: createdAt_from, created_from, date_to, updated_since, etc.
        def _normalize_date_filter_keys(primary_entity: str, rf: Dict[str, Any]) -> Dict[str, Any]:
            normalized: Dict[str, Any] = {}
            # Determine canonical created/updated fields per entity
            if primary_entity == "page":
                created_field = "createdAt"
                updated_field = "updatedAt"
            elif primary_entity == "members":
                # members commonly use joiningDate
                created_field = "joiningDate"
                updated_field = None
            else:
                # workItem/project/cycle/module use createdTimeStamp/updatedTimeStamp
                created_field = "createdTimeStamp"
                updated_field = "updatedTimeStamp"

            # Supported suffixes indicating range/window semantics
            suffixes = ("_from", "_to", "_within", "_duration")
            # Bases that imply created vs updated
            created_bases = {"created", "createdat", "created_time", "creation", "date", "timestamp"}
            updated_bases = {"updated", "updatedat", "last_date", "modified", "updated_time"}

            for key, val in rf.items():
                k = str(key)
                lk = k.lower()
                matched_suffix = next((s for s in suffixes if lk.endswith(s)), None)
                if matched_suffix:
                    base = lk[: -len(matched_suffix)]
                    if base in created_bases and created_field:
                        normalized[f"{created_field}{matched_suffix}"] = val
                        continue
                    if base in updated_bases and updated_field:
                        normalized[f"{updated_field}{matched_suffix}"] = val
                        continue
                # Also normalize plain created/updated without suffix if value looks like a window
                if lk in created_bases and created_field:
                    normalized[f"{created_field}_from"] = val
                    continue
                if lk in updated_bases and updated_field:
                    normalized[f"{updated_field}_from"] = val
                    continue
                # Keep as-is when not a recognized synonym
                normalized[k] = val

            return normalized

        raw_filters = _normalize_date_filter_keys(primary, raw_filters)

        # Build dynamic known keys from allow-listed fields and common tokens
        allowed_primary_fields = set(self.allowed_fields.get(primary, []))
        # Recognize date-like fields for range filters
        date_like_fields = {f for f in allowed_primary_fields if any(t in f.lower() for t in ["date", "timestamp", "createdat", "updatedat"]) }

        # Base normalized keys across collections
        known_filter_keys = {
            # normalized enums/booleans
            "state", "priority", "project_status", "cycle_status", "page_visibility",
            "status", "access", "isActive", "isArchived", "isDefault", "isFavourite",
            "visibility", "locked",
            # name/title/id style queries
            "label", "title", "name", "displayBugNo", "projectDisplayId", "email",
            # entity name filters (secondary lookups)
            "project_name", "cycle_name", "assignee_name", "module_name", "member_role",
            # actor/name filters
            "createdBy_name", "lead_name", "leadMail", "business_name",
            # timeline specific actor/task tokens
            "actor_name", "work_item_title",
            "defaultAssignee_name", "defaultAsignee_name", "staff_name",
            # members specific
            "role", "type", "joiningDate", "joiningDate_from", "joiningDate_to",
        }

        # Also accept any allow-listed primary fields directly
        known_filter_keys |= allowed_primary_fields
        # Add dynamic range keys for each date-like field
        for f in date_like_fields:
            known_filter_keys.add(f + "_from")
            known_filter_keys.add(f + "_to")
            # Also preserve relative window keys so timeline's timestamp_within is not dropped
            known_filter_keys.add(f + "_within")
            known_filter_keys.add(f + "_duration")

        for k, v in raw_filters.items():
            if k not in known_filter_keys or self._is_placeholder(v):
                continue
            # Normalize values where appropriate
            if k == "state" and isinstance(v, str):
                normalized_state = self._normalize_state_value(v.strip())
                if normalized_state:
                    filters[k] = normalized_state
            elif k == "priority" and isinstance(v, str):
                normalized_priority = self._normalize_priority_value(v.strip())
                if normalized_priority:
                    filters[k] = normalized_priority
            elif k in ["project_status", "cycle_status", "page_visibility"] and isinstance(v, str):
                normalized_status = self._normalize_status_value(k, v.strip())
                if normalized_status:
                    filters[k] = normalized_status
            elif k in ["isActive", "isArchived", "isDefault", "isFavourite", "locked"]:
                normalized_bool = self._normalize_boolean_value_from_any(v)
                if normalized_bool is not None:
                    filters[k] = normalized_bool
            elif k in ["project_name", "cycle_name", "module_name", "assignee_name", "createdBy_name", "lead_name", "business_name"] and isinstance(v, str):
                filters[k] = v.strip()
            elif isinstance(v, str) and k in {"title", "name", "displayBugNo", "projectDisplayId", "email"}:
                filters[k] = v.strip()
            else:
                # Keep other valid filters (including direct field filters and date range tokens)
                filters[k] = v

        
        # Heuristic enrichments from original query text (generalized)
        oq_text = (original_query or "").lower()

        # 1) Infer grouping from phrasing: "by X", "group by X", "breakdown by X", "per X"
        inferred_group_by: List[str] = []
        def _maybe_add_group(token: str):
            if token in {"project", "priority", "assignee", "cycle", "module", "state", "status", "business"}:
                if token not in inferred_group_by:
                    inferred_group_by.append(token)

        # Common phrasings
        if re.search(r"\b(group\s+by|breakdown\s+by|distribution\s+by|by|per)\s+priority\b", oq_text):
            _maybe_add_group("priority")
        if re.search(r"\b(group\s+by|breakdown\s+by|distribution\s+by|by|per)\s+project\b", oq_text):
            _maybe_add_group("project")
        if re.search(r"\b(group\s+by|breakdown\s+by|distribution\s+by|by|per)\s+assignee\b", oq_text):
            _maybe_add_group("assignee")
        if re.search(r"\b(group\s+by|breakdown\s+by|distribution\s+by|by|per)\s+cycle\b", oq_text):
            _maybe_add_group("cycle")
        if re.search(r"\b(group\s+by|breakdown\s+by|distribution\s+by|by|per)\s+module\b", oq_text):
            _maybe_add_group("module")
        if re.search(r"\b(group\s+by|breakdown\s+by|distribution\s+by|by|per)\s+(state|status)\b", oq_text):
            _maybe_add_group("state")
        if re.search(r"\b(group\s+by|breakdown\s+by|distribution\s+by|by|per)\s+business\b", oq_text):
            _maybe_add_group("business")

        # Merge with LLM-provided group_by if any
        if inferred_group_by:
            existing_group_by = [g for g in (data.get("group_by") or [])]
            # keep order: inferred first, then any unique extras
            merged = inferred_group_by + [g for g in existing_group_by if g not in inferred_group_by]
            data["group_by"] = merged

            # If grouping by priority explicitly, drop conflicting exact priority filters to avoid collapsing buckets
            if "priority" in merged and "by priority" in oq_text and "priority" in filters:
                filters.pop("priority", None)

        # 2) Overdue semantics for work items: dueDate < now and not in done-like states
        if primary == "workItem" and re.search(r"\boverdue\b|\bpast\s+due\b|\blate\b", oq_text):
            # Only add if user didn't already specify a dueDate bound
            if "dueDate_to" not in filters:
                filters["dueDate_to"] = "now"
            # Exclude commonly done/closed states if user didn't explicitly filter state
            if "state" not in filters and "state_not" not in filters:
                filters["state_not"] = ["Completed", "Verified"]


        # Aggregations
        allowed_aggs = {"count", "group", "summary"}
        aggregations = [a for a in (data.get("aggregations") or []) if a in allowed_aggs]

        # Group by tokens
        # Extended to support status/visibility/business and date buckets
        allowed_group = {
            "cycle", "project", "assignee", "state", "priority", "module",
            "status", "visibility", "business",
            "created_day", "created_week", "created_month",
            "updated_day", "updated_week", "updated_month",
        }
        group_by = [g for g in (data.get("group_by") or []) if g in allowed_group]

        # If user grouped by cross-entity tokens, force workItem as base (entity lock)
        cross_tokens = {"assignee", "project", "cycle", "module", "business"}
        if any(g in cross_tokens for g in group_by):
            primary = "workItem"

        # Aggregations & group_by coherence
        if group_by and "group" not in aggregations:
            aggregations.insert(0, "group")
        if not group_by:
            # drop stray 'group'
            aggregations = [a for a in aggregations if a != "group"]

        # Projections limited to allow-listed fields for primary
        allowed_projection_set = set(self.allowed_fields.get(primary, []))
        projections = [p for p in (data.get("projections") or []) if p in allowed_projection_set][:10]

        # Sort order
        sort_order = None
        so = data.get("sort_order") or {}
        if isinstance(so, dict) and so:
            key, val = next(iter(so.items()))
            # Accept synonyms and normalize
            if primary == "page":
                key_map = {
                    "created": "createdAt",
                    "createdAt": "createdAt",
                    "created_time": "createdAt",
                    "time": "createdAt",
                    "date": "createdAt",
                    "timestamp": "updatedAt",
                }
            elif primary == "timeline":
                key_map = {
                    "created": "timestamp",
                    "createdAt": "timestamp",
                    "created_time": "timestamp",
                    "time": "timestamp",
                    "date": "timestamp",
                    "timestamp": "timestamp",
                }
            else:
                key_map = {
                    "created": "createdTimeStamp",
                    "createdAt": "createdTimeStamp",
                    "created_time": "createdTimeStamp",
                    "time": "createdTimeStamp",
                    "date": "createdTimeStamp",
                    "timestamp": "createdTimeStamp",
                }
            norm_key = key_map.get(key, key)

            def _norm_dir(v: Any) -> Optional[int]:
                if v in (1, -1):
                    return int(v)
                if isinstance(v, str):
                    s = v.strip().lower()
                    if s in {"asc", "ascending", "old->new", "old to new", "old_to_new"}:
                        return 1
                    if s in {"desc", "descending", "new->old", "new to old", "new_to_old"}:
                        return -1
                return None

            norm_dir = _norm_dir(val)
            if norm_key in {"createdTimeStamp", "createdAt", "updatedAt", "timestamp", "priority", "state", "status"} and norm_dir in (1, -1):
                sort_order = {norm_key: norm_dir}

        # Limit - intelligent handling based on query type
        limit_val = data.get("limit")
        try:
            # For count/aggregation-only queries, no limit needed unless specifically requested
            if aggregations and not wants_details and limit_val is None:
                limit = None
            elif limit_val is None or limit_val == 20:
                # Use default limit when LLM doesn't provide a specific limit
                limit = 20
            else:
                limit = int(limit_val)
                if limit <= 0:
                    limit = 20
                # Cap at 1000 to prevent runaway queries (instead of 100)
                limit = min(limit, 1000)
        except Exception:
            # Last resort fallback: use default limit
            limit = 20

        # Skip (offset)
        skip_val = data.get("skip")
        try:
            skip = int(skip_val) if skip_val is not None else 0
            if skip < 0:
                skip = 0
        except Exception:
            skip = 0

        # Details vs count (mutually exclusive) + heuristic for "how many"
        oq = (original_query or "").lower()
        wants_details_raw = data.get("wants_details")
        wants_count_raw = data.get("wants_count")
        wants_details = bool(wants_details_raw) if wants_details_raw is not None else False
        wants_count = bool(wants_count_raw) if wants_count_raw is not None else False
        wants_count = wants_count or ("how many" in oq)

        # Simplified count query handling
        if wants_count:
            # For count queries, keep it simple
            aggregations = ["count"]
            wants_details = False
            group_by = []
            target_entities = []
            projections = []
            sort_order = None
        else:
            # For non-count queries, ensure consistency
            if group_by and wants_details_raw is None:
                wants_details = False

        # Heuristic: timeline TIME_LOGGED queries that mention per-task breakdown should group by work item
        # This enables questions like "amount of time logged by <user> per task for today"
        if primary == "timeline":
            tval = str(filters.get("type", "")).lower()
            mentions_time = any(k in oq for k in ["time logged", "amount of time", "time spent", "logged time"]) or ("time_logged" in tval)
            mentions_per_task = any(k in oq for k in ["per task", "by task", "per work item", "by work item", "per ticket", "by ticket", "breakdown"])
            if mentions_time and (mentions_per_task or ("time_logged" in tval and not group_by)):
                if "group" not in aggregations:
                    aggregations = ["group"] + [a for a in aggregations if a != "group"]
                if not group_by:
                    group_by = ["work_item_title"]
                # Grouped summaries don't need wants_details by default
                wants_details = False

            # Infer missing time window for timeline when the query includes relative periods
            has_time_window = any(k in filters for k in [
                "timestamp_from", "timestamp_to", "timestamp_within", "timestamp_duration"
            ])
            if not has_time_window:
                if re.search(r"\btoday\b", oq):
                    filters["timestamp_within"] = "today"
                elif re.search(r"\byesterday\b", oq):
                    filters["timestamp_within"] = "yesterday"
                elif re.search(r"\bthis\s+week\b", oq):
                    filters["timestamp_within"] = "this_week"
                elif re.search(r"\blast\s+week\b", oq):
                    filters["timestamp_within"] = "last_week"
                elif re.search(r"\bthis\s+month\b", oq):
                    filters["timestamp_within"] = "this_month"
                elif re.search(r"\blast\s+month\b", oq):
                    filters["timestamp_within"] = "last_month"

        # If no explicit sort provided and no grouping/count, infer time-based sort from phrasing
        if not sort_order and not group_by and not wants_count:
            inferred_sort = self._infer_sort_order_from_query(original_query or "")
            if inferred_sort:
                # If timeline → map createdTimeStamp to timestamp
                if primary == "timeline" and "createdTimeStamp" in inferred_sort:
                    dirv = inferred_sort.get("createdTimeStamp", -1)
                    sort_order = {"timestamp": dirv}
                elif primary == "page" and "createdTimeStamp" in inferred_sort:
                    dirv = inferred_sort.get("createdTimeStamp", -1)
                    sort_order = {"createdAt": dirv}
                else:
                    sort_order = inferred_sort

        # Fetch one heuristic
        fetch_one = bool(data.get("fetch_one", False)) or (limit == 1)

        return QueryIntent(
            primary_entity=primary,
            target_entities=target_entities,
            filters=filters,
            aggregations=aggregations,
            group_by=group_by,
            projections=projections,
            sort_order=sort_order,
            limit=limit,
            skip=skip,
            wants_details=wants_details,
            wants_count=wants_count,
            fetch_one=fetch_one,
        )

    async def _disambiguate_name_entity(self, proposed: Dict[str, str]) -> Optional[str]:
        """Use DB counts across collections to decide which name filter is most plausible.

        Preference order on ties: assignee -> project -> cycle -> module.
        Returns the chosen filter key or None if inconclusive.
        """
        # Build candidate lookups: mapping filter key -> (collection, field)
        candidates = {
            "assignee_name": ("members", "name"),
            "project_name": ("project", "name"),
            "cycle_name": ("cycle", "name"),
            "module_name": ("module", "name"),
        }
        counts: Dict[str, int] = {}
        for key, (collection, field) in candidates.items():
            if key not in proposed:
                continue
            value = proposed[key]
            try:
                cnt = await self._aggregate_count(collection, {field: {"$regex": value, "$options": "i"}})
            except Exception:
                cnt = 0
            counts[key] = cnt

        if not counts:
            return None

        # Pick the key with the highest positive count
        positive = {k: v for k, v in counts.items() if v and v > 0}
        if not positive:
            # No evidence; prefer assignee if proposed
            if "assignee_name" in proposed:
                return "assignee_name"
            return None

        # Sort keys by count desc then by preference order
        preference = {"assignee_name": 0, "project_name": 1, "cycle_name": 2, "module_name": 3}
        chosen = sorted(positive.items(), key=lambda kv: (-kv[1], preference.get(kv[0], 99)))[0][0]
        return chosen

    async def _aggregate_count(self, collection: str, match_filter: Dict[str, Any]) -> int:
        """Run a count via aggregation to avoid needing a dedicated count tool."""
        try:
            result = await mongodb_tools.execute_tool("aggregate", {
                "database": DATABASE_NAME,
                "collection": collection,
                "pipeline": [{"$match": match_filter}, {"$count": "total"}]
            })
            if isinstance(result, list) and result and isinstance(result[0], dict) and "total" in result[0]:
                return int(result[0]["total"])  # type: ignore
        except Exception:
            pass
        return 0

class PipelineGenerator:
    """Generates MongoDB aggregation pipelines based on query intent and relationships"""

    def __init__(self):
        self.relationship_cache = {}  # Cache for computed relationship paths

    def _add_comprehensive_lookups(self, pipeline: List[Dict[str, Any]], collection: str, intent: QueryIntent, required_relations: Set[str]):
        """Add strategic lookups only for relationships that provide clear query benefits"""
        # Only add strategic relationships that are likely to improve query performance
        # without adding unnecessary complexity for simple queries

        strategic_relations = {
            'workItem': {
                # Only add project if we're doing multi-hop queries or need business context
                'project': self._needs_multi_hop_context(intent, ['business', 'cycle', 'module']),
            },
            'project': {
                # Only add business if we're grouping by or filtering by business
                'business': 'business' in (intent.group_by or []) or 'business_name' in (intent.filters or {}),
            },
            'cycle': {
                # Only add project if we're doing complex analysis
                'project': len(intent.group_by or []) > 1 or intent.wants_details,
            },
            'module': {
                # Only add project if we're doing complex analysis
                'project': len(intent.group_by or []) > 1 or intent.wants_details,
            },
            'members': {
                # Only add project if we're doing complex analysis
                'project': len(intent.group_by or []) > 1 or intent.wants_details,
            },
            'page': {
                # Only add project if we're doing complex analysis
                'project': len(intent.group_by or []) > 1 or intent.wants_details,
            }
        }

        # Get the strategic relations for this collection
        relations_to_add = strategic_relations.get(collection, {})

        # Only add relations that are actually beneficial for this specific query
        for relation_name, should_add in relations_to_add.items():
            if should_add and relation_name in REL.get(collection, {}):
                # Only add if this relationship isn't already required but would be beneficial
                if relation_name not in required_relations:
                    required_relations.add(relation_name)

    def _needs_multi_hop_context(self, intent: QueryIntent, context_fields: List[str]) -> bool:
        """Check if the query needs multi-hop context for the given fields"""
        # Check if any context fields are referenced in group_by or filters
        for field in context_fields:
            if field in (intent.group_by or []) or f'{field}_name' in (intent.filters or {}):
                return True
        return False

    def _should_use_strategic_joins(self, intent: QueryIntent, required_relations: Set[str]) -> bool:
        """Automatically determine if strategic joins would benefit this query"""
        # Use strategic joins if:
        # 1. Query has multiple group_by fields (complex analysis)
        # 2. Query needs multi-hop context (business, cycle, module context)
        # 3. Query filters by fields that require joins
        # 4. Query requests details (indicating complex data needs)

        # Check for multi-hop context needs
        needs_multi_hop = (
            self._needs_multi_hop_context(intent, ['business', 'cycle', 'module']) or
            'business' in (intent.group_by or []) or
            'business_name' in (intent.filters or {})
        )

        # Check for complex grouping
        has_complex_grouping = len(intent.group_by or []) > 1

        # Check for detail requests
        wants_details = intent.wants_details

        # Check if already has required relations (don't need strategic joins if relations already identified)
        has_basic_relations = len(required_relations) > 0

        # Use strategic joins if any of these conditions are met
        return needs_multi_hop or has_complex_grouping or (wants_details and has_basic_relations)

    def generate_pipeline(self, intent: QueryIntent) -> List[Dict[str, Any]]:
        """Generate MongoDB aggregation pipeline for the given intent"""
        pipeline: List[Dict[str, Any]] = []

        # Start with the primary collection
        collection = intent.primary_entity

        # Build sanitized filters once
        primary_filters = self._extract_primary_filters(intent.filters, collection) if intent.filters else {}
        secondary_filters = self._extract_secondary_filters(intent.filters, collection) if intent.filters else {}

        # COUNT-ONLY: no group_by, no details → do not add lookups
        if (("count" in intent.aggregations) or intent.wants_count) and not intent.group_by and not intent.wants_details:
            # Combine all filters for optimal count query
            all_filters = {}
            if primary_filters:
                all_filters.update(primary_filters)
            if secondary_filters:
                all_filters.update(secondary_filters)

            if all_filters:
                return [{"$match": all_filters}, {"$count": "total"}]
            else:
                return [{"$count": "total"}]

        # Add filters for the primary collection
        if primary_filters:
            pipeline.append({"$match": primary_filters})

        # Ensure lookups needed by secondary filters or grouping are included
        required_relations: Set[str] = set()

        # Determine relation tokens per primary collection
        relation_alias_by_token = {
            'workItem': {
                # All are embedded on workItem; no lookup needed for filters/grouping
                'project': None,
                'assignee': None,
                'module': None,
                'cycle': None,
                # For business grouping we may need a project join to ensure business name
                'business': 'project',
            },
            'project': {
                'cycle': 'cycles',
                'module': 'modules',
                'assignee': 'members',
                'page': 'pages',
                'project': None,
            },
            'cycle': {
                'project': 'project',
                'business': 'project',
            },
            'module': {
                'project': 'project',
                'assignee': 'assignee',
                'business': 'project',
            },
            'page': {
                'project': 'project',  # key in REL is 'project', alias is 'projectDoc'
                'cycle': 'linkedCycle',
                'module': 'linkedModule',
                'business': 'project',
                'linkedMembers': 'linkedMembers',
            },
            'members': {
                'project': 'project',
                'business': 'project',
            },
            'projectState': {
                'project': 'project',
                'business': 'project',
            },
            'timeline': {
                'project': 'project',
                'workItem': 'workItem',
            },
        }.get(collection, {})

        # Include explicit target entities requested by the intent (supports multi-hop like "project.cycles")
        for rel in (intent.target_entities or []):
            if not isinstance(rel, str) or not rel:
                continue
            first_hop = rel.split(".")[0]
            if first_hop in REL.get(collection, {}):
                required_relations.add(rel)

        # Filters → relations (map filter tokens to relation alias for this primary)
        if intent.filters:
            # For workItem, project/assignee/cycle/modules are embedded; no lookups needed for name filters
            if collection != 'workItem':
                if 'project_name' in intent.filters and relation_alias_by_token.get('project') in REL.get(collection, {}):
                    required_relations.add(relation_alias_by_token['project'])
                if 'cycle_name' in intent.filters and relation_alias_by_token.get('cycle') in REL.get(collection, {}):
                    required_relations.add(relation_alias_by_token['cycle'])
                if 'assignee_name' in intent.filters and relation_alias_by_token.get('assignee') in REL.get(collection, {}):
                    required_relations.add(relation_alias_by_token['assignee'])
                if 'module_name' in intent.filters and relation_alias_by_token.get('module') in REL.get(collection, {}):
                    required_relations.add(relation_alias_by_token['module'])
                # Business name may require project hop for collections without embedded business
                if 'business_name' in intent.filters:
                    # If primary lacks direct business relation, but has project relation, join project
                    if relation_alias_by_token.get('project') in REL.get(collection, {}):
                        required_relations.add(relation_alias_by_token['project'])
                # Page linked members filter requires linkedMembers join
                if collection == 'page' and 'LinkedMembers_0_name' in intent.filters and relation_alias_by_token.get('linkedMembers') in REL.get(collection, {}):
                    required_relations.add(relation_alias_by_token['linkedMembers'])
            if 'member_role' in intent.filters:
                # Require member join depending on collection
                if collection == 'workItem' and 'assignee' in REL.get(collection, {}):
                    required_relations.add('assignee')
                if collection == 'project' and 'members' in REL.get('project', {}):
                    required_relations.add('members')
                if collection == 'module' and 'assignee' in REL.get('module', {}):
                    required_relations.add('assignee')

            # Multi-hop fallbacks for cycle/module via project when direct relations are absent
            if 'cycle_name' in intent.filters and ('cycle' not in REL.get(collection, {}) and 'cycles' not in REL.get(collection, {}) and 'linkedCycle' not in REL.get(collection, {})):
                if 'project' in REL.get(collection, {}) and 'cycles' in REL.get('project', {}):
                    required_relations.add('project')
                    required_relations.add('project.cycles')
            if 'module_name' in intent.filters and ('module' not in REL.get(collection, {}) and 'modules' not in REL.get(collection, {}) and 'linkedModule' not in REL.get(collection, {})):
                if 'project' in REL.get(collection, {}) and 'modules' in REL.get('project', {}):
                    required_relations.add('project')
                    required_relations.add('project.modules')

        # Group-by → relations
        for token in (intent.group_by or []):
            # Map grouping token to relation alias for this primary
            rel_alias = relation_alias_by_token.get(token)
            if rel_alias and rel_alias in REL.get(collection, {}):
                required_relations.add(rel_alias)
            # Multi-hop fallback for grouping keys that require project hop (e.g., cycle/module on workItem)
            if token == 'cycle' and ('cycle' not in REL.get(collection, {}) and 'cycles' not in REL.get(collection, {})):
                if 'project' in REL.get(collection, {}) and 'cycles' in REL.get('project', {}):
                    required_relations.add('project')
                    required_relations.add('project.cycles')
            if token == 'module' and ('module' not in REL.get(collection, {}) and 'modules' not in REL.get(collection, {})):
                if 'project' in REL.get(collection, {}) and 'modules' in REL.get('project', {}):
                    required_relations.add('project')
                    required_relations.add('project.modules')

        # Automatically add strategic lookups when they provide clear benefits for this query
        # Complex joins are now fully automatic based on query requirements
        if self._should_use_strategic_joins(intent, required_relations):
            self._add_comprehensive_lookups(pipeline, collection, intent, required_relations)

        # Add relationship lookups (supports multi-hop via dot syntax like project.states)
        for target_entity in sorted(required_relations):
            # Allow multi-hop relation names like "project.cycles"
            hops = target_entity.split(".")
            current_collection = collection
            local_prefix = None
            for hop in hops:
                if hop not in REL.get(current_collection, {}):
                    break
                relationship = REL[current_collection][hop]

                # SAFETY: avoid writing a lookup into an existing scalar field name
                needs_alias_fix = (
                    relationship.get("target") == "project"
                    and current_collection in {"cycle", "module", "page", "members", "projectState"}
                )
                if needs_alias_fix:
                    # Force a safe alias to prevent clobbering embedded project field
                    relationship = {**relationship, "as": "projectDoc"}
                lookup = build_lookup_stage(relationship["target"], relationship, current_collection, local_field_prefix=local_prefix)
                if lookup:
                    pipeline.append(lookup)
                    # If array relation, unwind the alias used in $lookup
                    is_many = bool(relationship.get("isArray") or relationship.get("many", False))
                    alias_name = relationship.get("as") or relationship.get("alias") or relationship.get("target")
                    if is_many:
                        pipeline.append({
                            "$unwind": {"path": f"${alias_name}", "preserveNullAndEmptyArrays": True}
                        })
                    # Set local prefix to the alias for chaining next hop
                    local_prefix = alias_name
                current_collection = relationship["target"]

        # Add secondary filters (on joined collections) BEFORE normalizing fields
        if secondary_filters:
            pipeline.append({"$match": secondary_filters})

        # Normalize project fields to scalars for safe filtering/printing
        if intent.primary_entity in {"cycle", "module", "page", "members", "projectState"}:
            pipeline.append({
                "$addFields": {
                    "projectId": {"$ifNull": ["$project._id", {"$first": "$projectDoc._id"}]},
                    "projectName": {"$ifNull": ["$project.name", {"$first": "$projectDoc.name"}]},
                    "projectBusinessName": {"$ifNull": ["$project.business.name", {"$first": "$projectDoc.business.name"}]}
                }
            })

        # Add grouping if requested
        if intent.group_by:
            # Pre-group unwind for embedded arrays that are used as grouping keys
            # For workItem, assignee is an array subdocument; unwind to get per-assignee buckets
            if intent.primary_entity == 'workItem' and 'assignee' in intent.group_by:
                pipeline.append({
                    "$unwind": {"path": "$assignee", "preserveNullAndEmptyArrays": True}
                })
            group_id_expr: Any
            id_fields: Dict[str, Any] = {}
            for token in intent.group_by:
                resolved = self._resolve_group_field(intent.primary_entity, token)
                if resolved:
                    # Accept either a field path (str) or a full expression (dict)
                    if isinstance(resolved, str):
                        id_fields[token] = f"${resolved}"
                    else:
                        id_fields[token] = resolved
            if not id_fields:
                # Fallback: do nothing if we can't resolve
                pass
            else:
                group_id_expr = list(id_fields.values())[0] if len(id_fields) == 1 else id_fields

                # Special handling: for timeline TIME_LOGGED breakdowns, sum parsed minutes from newValue
                is_timeline_time_logged = (
                    intent.primary_entity == 'timeline' and (
                        isinstance(intent.filters.get('type'), str) and 'time_logged' in str(intent.filters.get('type')).lower()
                    )
                )
                if is_timeline_time_logged:
                    # Compute parsed minutes from strings like "1 hr 30 min", "45 min", "2 hr"
                    pipeline.append({
                        "$addFields": {
                            "_parsedMinutes": {
                                "$let": {
                                    "vars": {
                                        "h": {"$regexFind": {"input": "$newValue", "regex": "([0-9]+)\\s*(?:h|hr|hrs|hour|hours)"}},
                                        "m": {"$regexFind": {"input": "$newValue", "regex": "([0-9]+)\\s*(?:m|min|mins|minute|minutes)"}}
                                    },
                                    "in": {
                                        "$add": [
                                            {"$multiply": [
                                                {"$toInt": {"$ifNull": [{"$arrayElemAt": ["$$h.captures", 0]}, 0]}}, 60
                                            ]},
                                            {"$toInt": {"$ifNull": [{"$arrayElemAt": ["$$m.captures", 0]}, 0]}}
                                        ]
                                    }
                                }
                            }
                        }
                    })
                    group_stage: Dict[str, Any] = {
                        "$group": {
                            "_id": group_id_expr,
                            "totalMinutes": {"$sum": "$__parsedMinutes__"}  # placeholder to be replaced
                        }
                    }
                    # Replace placeholder key with the actual parsed minutes field name
                    group_stage["$group"]["totalMinutes"] = {"$sum": "$_parsedMinutes"}
                else:
                    group_stage: Dict[str, Any] = {
                        "$group": {
                            "_id": group_id_expr,
                            "count": {"$sum": 1},
                        }
                    }
                if intent.wants_details:
                    group_stage["$group"]["items"] = {
                        "$push": {
                            "_id": "$_id",
                            "displayBugNo": "$displayBugNo",
                            "title": "$title",
                            "priority": "$priority",
                        }
                    }
                pipeline.append(group_stage)
                # Sorting for grouped results: default to metric desc (count or totalMinutes), allow sorting by grouped keys
                if intent.sort_order:
                    sort_key, sort_dir = next(iter(intent.sort_order.items()))
                    if sort_key in intent.group_by:
                        # Sort by the grouped key inside _id
                        if len(id_fields) == 1:
                            pipeline.append({"$sort": {"_id": sort_dir}})
                        else:
                            pipeline.append({"$sort": {f"_id.{sort_key}": sort_dir}})
                    else:
                        # Default to the primary metric
                        if intent.primary_entity == 'timeline' and ('work_item_title' in (intent.group_by or [])) and is_timeline_time_logged:
                            pipeline.append({"$sort": {"totalMinutes": -1}})
                        else:
                            pipeline.append({"$sort": {"count": -1}})
                else:
                    if intent.primary_entity == 'timeline' and ('work_item_title' in (intent.group_by or [])) and is_timeline_time_logged:
                        pipeline.append({"$sort": {"totalMinutes": -1}})
                    else:
                        pipeline.append({"$sort": {"count": -1}})
                # Present a tidy shape
                project_shape: Dict[str, Any] = {"count": 1}
                if intent.wants_details:
                    project_shape["items"] = 1
                project_shape["group"] = "$_id"
                # Expose totalMinutes when computed
                if intent.primary_entity == 'timeline' and ('work_item_title' in (intent.group_by or [])) and is_timeline_time_logged:
                    project_shape["totalMinutes"] = 1
                pipeline.append({"$project": project_shape})
                # Respect limit on grouped results
                if intent.limit:
                    pipeline.append({"$limit": intent.limit})

        # Add aggregations like count (skip count when details are requested)
        if intent.aggregations and not intent.wants_details and not intent.group_by:
            for agg in intent.aggregations:
                if agg == 'count':
                    pipeline.append({"$count": "total"})
                    return pipeline  # Count is terminal

        # Determine projections for details (skip when grouping since we reshape after $group)
        effective_projections: List[str] = intent.projections
        if intent.wants_details and not intent.group_by and not effective_projections:
            effective_projections = self._get_default_projections(intent.primary_entity)

        # Add sorting (handle custom priority order) — skip if already grouped
        added_priority_rank = False
        if intent.sort_order and not intent.group_by:
            if 'priority' in intent.sort_order:
                # Only compute rank if priority is part of projections to avoid surprising invisible sorts
                if (effective_projections and 'priority' in effective_projections) or (not effective_projections):
                    added_priority_rank = True
                    pipeline.append({
                        "$addFields": {
                            "_priorityRank": {
                                "$switch": {
                                    "branches": [
                                        {"case": {"$eq": ["$priority", "URGENT"]}, "then": 5},
                                        {"case": {"$eq": ["$priority", "HIGH"]}, "then": 4},
                                        {"case": {"$eq": ["$priority", "MEDIUM"]}, "then": 3},
                                        {"case": {"$eq": ["$priority", "LOW"]}, "then": 2},
                                        {"case": {"$eq": ["$priority", "NONE"]}, "then": 1}
                                    ],
                                    "default": 0
                                }
                            }
                        }
                    })
                    # Use computed rank for sorting direction provided
                    direction = intent.sort_order.get('priority', -1)
                    pipeline.append({"$sort": {"_priorityRank": direction}})
                else:
                    pipeline.append({"$sort": intent.sort_order})
            elif 'state' in intent.sort_order and collection == 'workItem':
                # Sort by state via embedded state.name.
                pipeline.append({"$sort": {"state.name": intent.sort_order.get('state', 1)}})
            else:
                pipeline.append({"$sort": intent.sort_order})

        # Compute projected aliases for joined relations so projections include them when needed
        projected_aliases: Set[str] = set()
        if required_relations:
            for rel_path in sorted(required_relations):
                hops = rel_path.split(".")
                current_collection = collection
                for hop in hops:
                    if hop not in REL.get(current_collection, {}):
                        break
                    relationship = REL[current_collection][hop]
                    alias_name = relationship.get("as") or relationship.get("alias") or relationship.get("target")
                    if alias_name:
                        projected_aliases.add(alias_name)
                    current_collection = relationship["target"]

        # Add projections after sorting so computed fields can be hidden
        if effective_projections and not intent.group_by:
            projection = self._generate_projection(effective_projections, sorted(list(projected_aliases)), intent.primary_entity)
            # Ensure we exclude helper fields from output
            pipeline.append({"$project": projection})
        # Always remove priority rank helper if it was added
        if added_priority_rank:
            pipeline.append({"$unset": "_priorityRank"})

        # Add pagination: skip then limit (only for non-grouped queries; grouped handled above)
        if not intent.group_by:
            # Apply skip before limit
            try:
                if intent.skip and int(intent.skip) > 0:
                    pipeline.append({"$skip": int(intent.skip)})
            except Exception:
                pass
            effective_limit = 1 if intent.fetch_one else (intent.limit or None)
            if effective_limit:
                pipeline.append({"$limit": int(effective_limit)})

        return pipeline

    def _extract_primary_filters(self, filters: Dict[str, Any], collection: str) -> Dict[str, Any]:
        """Extract filters that apply to the primary collection"""
        primary_filters = {}

        # Handle direct _id filters first using $expr with $toObjectId for safety
        def _is_hex24(s: str) -> bool:
            try:
                return isinstance(s, str) and len(s) == 24 and all(c in '0123456789abcdefABCDEF' for c in s)
            except Exception:
                return False

        if "_id" in filters:
            val = filters.get("_id")
            if isinstance(val, str) and _is_hex24(val):
                primary_filters["$expr"] = {"$eq": ["$_id", {"$toObjectId": val}]}
            elif isinstance(val, list):
                ids = [v for v in val if isinstance(v, str) and _is_hex24(v)]
                if ids:
                    primary_filters["$expr"] = {
                        "$in": [
                            "$_id",
                            {"$map": {"input": ids, "as": "id", "in": {"$toObjectId": "$$id"}}}
                        ]
                    }

        def _apply_date_range(target: Dict[str, Any], field: str, f: Dict[str, Any]):
            # Resolve field aliases first
            from mongo.registry import resolve_field_alias
            resolved_field = resolve_field_alias(collection, field)

            # Support additional keys:
            # - {field}_within / {field}_duration: relative window like "last_7_days", "7d", {"last": {"days": 7}}
            # - allow {field}_from / {field}_to values like "now-7d" or ISO timestamps

            def _parse_relative_window(spec: Any) -> Optional[Dict[str, datetime]]:
                now = datetime.now(timezone.utc)
                start: Optional[datetime] = None
                end: datetime = now

                def _start_of_week(dt: datetime) -> datetime:
                    dow = dt.weekday()  # Monday=0
                    sod = datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)
                    return sod - timedelta(days=dow)

                def _start_of_month(dt: datetime) -> datetime:
                    return datetime(dt.year, dt.month, 1, tzinfo=timezone.utc)

                def _end_of_month(dt: datetime) -> datetime:
                    if dt.month == 12:
                        next_month = datetime(dt.year + 1, 1, 1, tzinfo=timezone.utc)
                    else:
                        next_month = datetime(dt.year, dt.month + 1, 1, tzinfo=timezone.utc)
                    return next_month - timedelta(microseconds=1)

                if isinstance(spec, dict) and spec.get("last"):
                    last_obj = spec.get("last") or {}
                    days = float(last_obj.get("days", 0) or 0)
                    hours = float(last_obj.get("hours", 0) or 0)
                    delta = timedelta(days=days, hours=hours)
                    if delta.total_seconds() > 0:
                        start = now - delta
                        return {"from": start, "to": end}
                    return None

                if not isinstance(spec, str):
                    return None

                s = spec.strip().lower().replace("-", "_")
                if s == "today":
                    sod = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
                    return {"from": sod, "to": end}
                if s == "yesterday":
                    sod_today = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
                    sod_y = sod_today - timedelta(days=1)
                    eod_y = sod_today - timedelta(microseconds=1)
                    return {"from": sod_y, "to": eod_y}
                if s == "this_week":
                    return {"from": _start_of_week(now), "to": end}
                if s == "last_week":
                    sow_this = _start_of_week(now)
                    sow_last = sow_this - timedelta(days=7)
                    eow_last = sow_this - timedelta(microseconds=1)
                    return {"from": sow_last, "to": eow_last}
                if s == "this_month":
                    return {"from": _start_of_month(now), "to": end}
                if s == "last_month":
                    som_this = _start_of_month(now)
                    if som_this.month == 1:
                        som_last = datetime(som_this.year - 1, 12, 1, tzinfo=timezone.utc)
                    else:
                        som_last = datetime(som_this.year, som_this.month - 1, 1, tzinfo=timezone.utc)
                    eom_last = _end_of_month(som_last)
                    return {"from": som_last, "to": eom_last}

                m = re.search(r"(last|past)?\s*([0-9]+)\s*(day|days|d|week|weeks|w|month|months|mo|hour|hours|h|year|years|y)", s)
                if m:
                    n = int(m.group(2))
                    unit = m.group(3)
                    if unit in {"day", "days", "d"}:
                        start = now - timedelta(days=n)
                    elif unit in {"week", "weeks", "w"}:
                        start = now - timedelta(weeks=n)
                    elif unit in {"month", "months", "mo"}:
                        start = now - timedelta(days=30 * n)
                    elif unit in {"hour", "hours", "h"}:
                        start = now - timedelta(hours=n)
                    elif unit in {"year", "years", "y"}:
                        start = now - timedelta(days=365 * n)
                    if start:
                        return {"from": start, "to": end}

                m2 = re.fullmatch(r"([0-9]+)\s*(d|h)", s)
                if m2:
                    n = int(m2.group(1))
                    unit = m2.group(2)
                    if unit == "d":
                        start = now - timedelta(days=n)
                    elif unit == "h":
                        start = now - timedelta(hours=n)
                    if start:
                        return {"from": start, "to": end}
                return None

            def _normalize_bound(val: Any) -> Any:
                if isinstance(val, (int, float)):
                    try:
                        if float(val) > 1e11:
                            return datetime.fromtimestamp(float(val) / 1000.0, tz=timezone.utc)
                        return datetime.fromtimestamp(float(val), tz=timezone.utc)
                    except Exception:
                        return val
                if isinstance(val, str):
                    s = val.strip().lower()
                    if s == "now":
                        return datetime.now(timezone.utc)
                    m = re.fullmatch(r"now\s*[-+]\s*([0-9]+)\s*(d|day|days|h|hour|hours)", s)
                    if m:
                        n = int(m.group(1))
                        unit = m.group(2)
                        if unit in {"d", "day", "days"}:
                            return datetime.now(timezone.utc) - timedelta(days=n)
                        if unit in {"h", "hour", "hours"}:
                            return datetime.now(timezone.utc) - timedelta(hours=n)
                    try:
                        return datetime.fromisoformat(val)
                    except Exception:
                        return val
                return val

            # Look for date range keys using the original field name
            within = f.get(f"{field}_within") or f.get(f"{field}_duration")
            gte_key = f.get(f"{field}_from")
            lte_key = f.get(f"{field}_to")

            if within is not None:
                rng = _parse_relative_window(within)
                if rng:
                    gte_key = gte_key or rng.get("from")
                    lte_key = lte_key or rng.get("to")

            if gte_key is None and lte_key is None:
                return
            range_expr: Dict[str, Any] = {}
            if gte_key is not None:
                range_expr["$gte"] = _normalize_bound(gte_key)
            if lte_key is not None:
                range_expr["$lte"] = _normalize_bound(lte_key)
            if range_expr:
                target[resolved_field] = range_expr

        if collection == "workItem":
            if 'status' in filters:
                primary_filters['status'] = filters['status']
            if 'priority' in filters:
                primary_filters['priority'] = filters['priority']
            if 'state' in filters:
                # Map logical state filter to embedded field
                primary_filters['state.name'] = filters['state']
            # Exclude states (array) support, mapped to state.name not-in
            if 'state_not' in filters and isinstance(filters['state_not'], list) and filters['state_not']:
                primary_filters['state.name'] = primary_filters.get('state.name') or {}
                # If previously set to a scalar via 'state', turn into $nin with preservation
                if isinstance(primary_filters['state.name'], str):
                    primary_filters['state.name'] = {"$in": [primary_filters['state.name']]}
                # Merge not-in
                primary_filters['state.name']["$nin"] = filters['state_not']
            if 'label' in filters and isinstance(filters['label'], str):
                primary_filters['label'] = {'$regex': filters['label'], '$options': 'i'}
            if 'createdBy_name' in filters and isinstance(filters['createdBy_name'], str):
                primary_filters['createdBy.name'] = {'$regex': filters['createdBy_name'], '$options': 'i'}
            if 'title' in filters and isinstance(filters['title'], str):
                primary_filters['title'] = {'$regex': filters['title'], '$options': 'i'}
            if 'displayBugNo' in filters and isinstance(filters['displayBugNo'], str):
                primary_filters['displayBugNo'] = {'$regex': f"^{filters['displayBugNo']}", '$options': 'i'}
            _apply_date_range(primary_filters, 'createdTimeStamp', filters)
            _apply_date_range(primary_filters, 'updatedTimeStamp', filters)
            # Support dueDate ranges uniformly
            _apply_date_range(primary_filters, 'dueDate', filters)

        elif collection == "project":
            if 'project_status' in filters:
                primary_filters['status'] = filters['project_status']
            if 'status' in filters and 'status' not in primary_filters:
                primary_filters['status'] = filters['status']
            if 'isActive' in filters:
                primary_filters['isActive'] = bool(filters['isActive'])
            if 'isArchived' in filters:
                primary_filters['isArchived'] = bool(filters['isArchived'])
            if 'access' in filters:
                primary_filters['access'] = filters['access']
            if 'isFavourite' in filters:
                # Some schemas use 'favourite' on projects
                primary_filters['favourite'] = bool(filters['isFavourite'])
            if 'createdBy_name' in filters and isinstance(filters['createdBy_name'], str):
                primary_filters['createdBy.name'] = {'$regex': filters['createdBy_name'], '$options': 'i'}
            if 'lead_name' in filters and isinstance(filters['lead_name'], str):
                primary_filters['lead.name'] = {'$regex': filters['lead_name'], '$options': 'i'}
            if 'leadMail' in filters and isinstance(filters['leadMail'], str):
                primary_filters['leadMail'] = {'$regex': f"^{filters['leadMail']}", '$options': 'i'}
            if 'projectDisplayId' in filters and isinstance(filters['projectDisplayId'], str):
                primary_filters['projectDisplayId'] = {'$regex': f"^{filters['projectDisplayId']}", '$options': 'i'}
            if 'name' in filters and isinstance(filters['name'], str):
                primary_filters['name'] = {'$regex': filters['name'], '$options': 'i'}
            if 'business_name' in filters and isinstance(filters['business_name'], str):
                primary_filters['business.name'] = {'$regex': filters['business_name'], '$options': 'i'}
            # default assignee (object): allow name filtering
            if 'defaultAssignee_name' in filters and isinstance(filters['defaultAssignee_name'], str):
                primary_filters['defaultAsignee.name'] = {'$regex': filters['defaultAssignee_name'], '$options': 'i'}
            if 'defaultAsignee_name' in filters and isinstance(filters['defaultAsignee_name'], str):
                primary_filters['defaultAsignee.name'] = {'$regex': filters['defaultAsignee_name'], '$options': 'i'}
            _apply_date_range(primary_filters, 'createdTimeStamp', filters)
            _apply_date_range(primary_filters, 'updatedTimeStamp', filters)

        elif collection == "cycle":
            if 'cycle_status' in filters:
                primary_filters['status'] = filters['cycle_status']
            if 'status' in filters and 'status' not in primary_filters:
                primary_filters['status'] = filters['status']
            if 'isDefault' in filters:
                primary_filters['isDefault'] = bool(filters['isDefault'])
            if 'isFavourite' in filters:
                primary_filters['isFavourite'] = bool(filters['isFavourite'])
            if 'title' in filters and isinstance(filters['title'], str):
                primary_filters['title'] = {'$regex': filters['title'], '$options': 'i'}
            _apply_date_range(primary_filters, 'startDate', filters)
            _apply_date_range(primary_filters, 'endDate', filters)
            _apply_date_range(primary_filters, 'createdTimeStamp', filters)
            _apply_date_range(primary_filters, 'updatedTimeStamp', filters)

            # Optional duration-based filtering in days: duration_days_from/to
            dur_from = filters.get('duration_days_from')
            dur_to = filters.get('duration_days_to')
            if dur_from is not None or dur_to is not None:
                dur_bounds: List[Dict[str, Any]] = []
                dur_expr = {
                    "$divide": [
                        {"$subtract": [
                            {"$ifNull": ["$endDate", "$$NOW"]},
                            "$startDate"
                        ]},
                        86400000
                    ]
                }
                try:
                    if dur_from is not None:
                        dur_from_val = float(dur_from)
                        dur_bounds.append({"$gte": [dur_expr, dur_from_val]})
                except Exception:
                    pass
                try:
                    if dur_to is not None:
                        dur_to_val = float(dur_to)
                        dur_bounds.append({"$lte": [dur_expr, dur_to_val]})
                except Exception:
                    pass
                if dur_bounds:
                    expr = {"$and": dur_bounds} if len(dur_bounds) > 1 else dur_bounds[0]
                    if "$expr" in primary_filters:
                        existing = primary_filters["$expr"]
                        primary_filters["$expr"] = {"$and": [existing, expr]}
                    else:
                        primary_filters["$expr"] = expr

        elif collection == "page":
            if 'page_visibility' in filters:
                primary_filters['visibility'] = filters['page_visibility']
            if 'visibility' in filters:
                primary_filters['visibility'] = filters['visibility']
            if 'isFavourite' in filters:
                primary_filters['isFavourite'] = bool(filters['isFavourite'])
            if 'createdBy_name' in filters and isinstance(filters['createdBy_name'], str):
                primary_filters['createdBy.name'] = {'$regex': filters['createdBy_name'], '$options': 'i'}
            if 'locked' in filters:
                primary_filters['locked'] = bool(filters['locked'])
            if 'title' in filters and isinstance(filters['title'], str):
                primary_filters['title'] = {'$regex': filters['title'], '$options': 'i'}
            _apply_date_range(primary_filters, 'createdAt', filters)
            _apply_date_range(primary_filters, 'updatedAt', filters)

        elif collection == "module":
            if 'isFavourite' in filters:
                primary_filters['isFavourite'] = bool(filters['isFavourite'])
            if 'title' in filters and isinstance(filters['title'], str):
                primary_filters['title'] = {'$regex': filters['title'], '$options': 'i'}
            if 'name' in filters and isinstance(filters['name'], str):
                primary_filters['name'] = {'$regex': filters['name'], '$options': 'i'}
            if 'business_name' in filters and isinstance(filters['business_name'], str):
                primary_filters['business.name'] = {'$regex': filters['business_name'], '$options': 'i'}
            if 'lead_name' in filters and isinstance(filters['lead_name'], str):
                primary_filters['lead.name'] = {'$regex': filters['lead_name'], '$options': 'i'}
            if 'assignee_name' in filters and isinstance(filters['assignee_name'], str):
                # module.assignee can be array of member subdocs
                primary_filters['assignee.name'] = {'$regex': filters['assignee_name'], '$options': 'i'}
            _apply_date_range(primary_filters, 'createdTimeStamp', filters)

        elif collection == "members":
            if 'role' in filters and isinstance(filters['role'], str):
                primary_filters['role'] = {'$regex': f"^{filters['role']}$", '$options': 'i'}
            if 'type' in filters and isinstance(filters['type'], str):
                primary_filters['type'] = {'$regex': f"^{filters['type']}$", '$options': 'i'}
            if 'name' in filters and isinstance(filters['name'], str):
                primary_filters['name'] = {'$regex': filters['name'], '$options': 'i'}
            if 'email' in filters and isinstance(filters['email'], str):
                primary_filters['email'] = {'$regex': f"^{filters['email']}", '$options': 'i'}
            if 'project_name' in filters and isinstance(filters['project_name'], str):
                primary_filters['project.name'] = {'$regex': filters['project_name'], '$options': 'i'}
            if 'staff_name' in filters and isinstance(filters['staff_name'], str):
                primary_filters['staff.name'] = {'$regex': filters['staff_name'], '$options': 'i'}
            _apply_date_range(primary_filters, 'joiningDate', filters)

        elif collection == "projectState":
            if 'name' in filters and isinstance(filters['name'], str):
                primary_filters['name'] = {'$regex': filters['name'], '$options': 'i'}
            if 'sub_state_name' in filters and isinstance(filters['sub_state_name'], str):
                primary_filters['subStates.name'] = {'$regex': filters['sub_state_name'], '$options': 'i'}

        elif collection == "timeline":
            # timeline supports type/status-like filtering via 'type'
            if 'status' in filters and isinstance(filters['status'], str):
                primary_filters['type'] = {'$regex': f"^{filters['status']}$", '$options': 'i'}
            if 'type' in filters and isinstance(filters['type'], str):
                primary_filters['type'] = {'$regex': filters['type'], '$options': 'i'}
            if 'fieldChanged' in filters and isinstance(filters['fieldChanged'], str):
                primary_filters['fieldChanged'] = {'$regex': filters['fieldChanged'], '$options': 'i'}
            if 'message' in filters and isinstance(filters['message'], str):
                primary_filters['message'] = {'$regex': filters['message'], '$options': 'i'}
            if 'commentText' in filters and isinstance(filters['commentText'], str):
                primary_filters['commentText'] = {'$regex': filters['commentText'], '$options': 'i'}
            if 'oldValue' in filters and isinstance(filters['oldValue'], str):
                primary_filters['oldValue'] = {'$regex': filters['oldValue'], '$options': 'i'}
            if 'newValue' in filters and isinstance(filters['newValue'], str):
                primary_filters['newValue'] = {'$regex': filters['newValue'], '$options': 'i'}
            if 'actor_name' in filters and isinstance(filters['actor_name'], str):
                primary_filters['user.name'] = {'$regex': filters['actor_name'], '$options': 'i'}
            if 'work_item_title' in filters and isinstance(filters['work_item_title'], str):
                primary_filters['workItemTitle'] = {'$regex': filters['work_item_title'], '$options': 'i'}
            if 'project_name' in filters and isinstance(filters['project_name'], str):
                primary_filters['project.name'] = {'$regex': filters['project_name'], '$options': 'i'}
            if 'business_name' in filters and isinstance(filters['business_name'], str):
                primary_filters['business.name'] = {'$regex': filters['business_name'], '$options': 'i'}
            # date range on 'timestamp'
            _apply_date_range(primary_filters, 'timestamp', filters)

        return primary_filters

    def _extract_secondary_filters(self, filters: Dict[str, Any], collection: str) -> Dict[str, Any]:
        """Extract filters that apply to joined collections, guarded by available relations."""
        s: Dict[str, Any] = {}

        # Project name: allow both embedded project.name and joined alias projectDoc.name
        if 'project_name' in filters and collection == 'project':
            s['$or'] = [
                {'name': {'$regex': filters['project_name'], '$options': 'i'}},
                {'projectDoc.name': {'$regex': filters['project_name'], '$options': 'i'}},
                {'projectName': {'$regex': filters['project_name'], '$options': 'i'}},
            ]
        elif 'project_name' in filters:
            # For non-project collections, match on the joined project document
            s['$or'] = [
                {'project.name': {'$regex': filters['project_name'], '$options': 'i'}},
                {'projectDoc.name': {'$regex': filters['project_name'], '$options': 'i'}},
            ]

        # Assignee name via joined alias 'assignees' (only if relation exists)
        if 'assignee_name' in filters and 'assignee' in REL.get(collection, {}):
            # Prefer embedded assignee names when present; joined alias may be 'assignees'
            s['$or'] = s.get('$or', []) + [
                {'assignee.name': {'$regex': filters['assignee_name'], '$options': 'i'}},
                {'assignees.name': {'$regex': filters['assignee_name'], '$options': 'i'}},
            ]
        # Member role filter when relation exists
        if 'member_role' in filters:
            # For workItem: embedded assignee or joined members
            if collection == 'workItem' and 'assignee' in REL.get(collection, {}):
                s['$or'] = s.get('$or', []) + [
                    {'assignee.role': {'$regex': f"^{filters['member_role']}$", '$options': 'i'}},
                    {'assignees.role': {'$regex': f"^{filters['member_role']}$", '$options': 'i'}},
                ]
            # For project: through members join
            if collection == 'project' and 'members' in REL.get('project', {}):
                s['members.role'] = {'$regex': f"^{filters['member_role']}$", '$options': 'i'}
            # For module: embedded assignee or joined members
            if collection == 'module' and 'assignee' in REL.get('module', {}):
                s['$or'] = s.get('$or', []) + [
                    {'assignee.role': {'$regex': f"^{filters['member_role']}$", '$options': 'i'}},
                    {'assignees.role': {'$regex': f"^{filters['member_role']}$", '$options': 'i'}},
                ]

        # Cycle name filter: prefer embedded cycle.name; support joined aliases
        if 'cycle_name' in filters:
            if collection == 'workItem':
                s['cycle.name'] = {'$regex': filters['cycle_name'], '$options': 'i'}
            elif 'cycle' in REL.get(collection, {}):
                s['cycle.name'] = {'$regex': filters['cycle_name'], '$options': 'i'}
            elif 'cycles' in REL.get(collection, {}):
                s['cycles.name'] = {'$regex': filters['cycle_name'], '$options': 'i'}
            elif collection == 'page' and 'linkedCycle' in REL.get('page', {}):
                s['linkedCycleDocs.name'] = {'$regex': filters['cycle_name'], '$options': 'i'}

        # Module name filter: prefer embedded modules.name; support joined aliases
        if 'module_name' in filters:
            if collection == 'workItem':
                s['modules.name'] = {'$regex': filters['module_name'], '$options': 'i'}
            elif 'module' in REL.get(collection, {}):
                s['module.name'] = {'$regex': filters['module_name'], '$options': 'i'}
            elif 'modules' in REL.get(collection, {}):
                s['modules.name'] = {'$regex': filters['module_name'], '$options': 'i'}
            elif collection == 'page' and 'linkedModule' in REL.get('page', {}):
                s['linkedModuleDocs.name'] = {'$regex': filters['module_name'], '$options': 'i'}

        # Business name via embedded or joined path
        if 'business_name' in filters:
            # Directly embedded business on these collections
            if collection in ('project', 'page'):
                s['$or'] = s.get('$or', []) + [
                    {'business.name': {'$regex': filters['business_name'], '$options': 'i'}},
                    {'projectDoc.business.name': {'$regex': filters['business_name'], '$options': 'i'}},
                    {'projectBusinessName': {'$regex': filters['business_name'], '$options': 'i'}},
                ]
            # For cycle/module: prefer project join to reach project.business.name
            if collection in ('cycle', 'module'):
                s['$or'] = s.get('$or', []) + [
                    {'project.business.name': {'$regex': filters['business_name'], '$options': 'i'}},
                    {'projectDoc.business.name': {'$regex': filters['business_name'], '$options': 'i'}},
                    {'projectBusinessName': {'$regex': filters['business_name'], '$options': 'i'}},
                ]
            # For members: through joined project
            if collection == 'members' and 'project' in REL.get('members', {}):
                s['$or'] = s.get('$or', []) + [
                    {'project.business.name': {'$regex': filters['business_name'], '$options': 'i'}},
                    {'projectDoc.business.name': {'$regex': filters['business_name'], '$options': 'i'}},
                    {'projectBusinessName': {'$regex': filters['business_name'], '$options': 'i'}},
                ]

        # Page linked members: support name filter via joined alias when available
        if collection == 'page' and 'LinkedMembers_0_name' in filters:
            # Interpret as any linked member name regex
            s['linkedMembersDocs.name'] = {'$regex': filters['LinkedMembers_0_name'], '$options': 'i'}

        return s

    def _generate_lookup_stage(self, from_collection: str, target_entity: str, filters: Dict[str, Any]) -> Dict[str, Any]:
        # Deprecated in favor of build_lookup_stage imported from registry
        if from_collection not in REL or target_entity not in REL[from_collection]:
            return {}
        relationship = REL[from_collection][target_entity]
        return build_lookup_stage(relationship["target"], relationship, from_collection)

    def _generate_projection(self, projections: List[str], target_entities: List[str], primary_entity: str) -> Dict[str, Any]:
        """Generate projection object"""
        projection = {"_id": 1}  # Always include ID

        # Add requested projections
        for field in projections:
            if field in ALLOWED_FIELDS.get(primary_entity, {}):
                projection[field] = 1

        # Add target entity fields
        for entity in target_entities:
            if entity in REL.get(primary_entity, {}):
                projection[entity] = 1

        return projection

    def _get_default_projections(self, primary_entity: str) -> List[str]:
        """Return sensible default fields for detail queries per collection.
        Only returns fields that are allow-listed for the given collection.
        """
        defaults_map: Dict[str, List[str]] = {
            "workItem": [
                "displayBugNo", "title", "priority",
                "state.name", "assignee",
                "project.name", "cycle.name", "modules.name",
                "createdTimeStamp",
                # Estimation and logging fields to enable time tracking summaries
                "estimateSystem", "estimate.hr", "estimate.min",
                "workLogs.hours", "workLogs.minutes", "workLogs.description", "workLogs.loggedAt",
            ],
            "project": [
                "projectDisplayId", "name", "status", "isActive", "isArchived", "createdTimeStamp",
                "createdBy.name", "lead.name", "leadMail", "defaultAsignee.name"
            ],
            "cycle": [
                "title", "status", "startDate", "endDate", "projectName", "projectId"
            ],
            "members": [
                "name", "email", "role", "joiningDate", "projectName", "projectId"
            ],
            "page": [
                "title", "visibility", "createdAt", "projectName", "projectId"
            ],
            "module": [
                "title", "description", "isFavourite", "createdTimeStamp", "projectName", "projectId"
            ],
            "projectState": [
                "name", "subStates.name", "subStates.order"
            ],
            "timeline": [
                "type", "fieldChanged", "message", "commentText",
                "oldValue", "newValue", "timestamp",
                "workItemTitle", "project.name", "business.name", "user.name"
            ],
        }

        candidates = defaults_map.get(primary_entity, ["_id"])  # fallback _id

        # Validate against allow-listed fields for safety
        allowed = ALLOWED_FIELDS.get(primary_entity, set())
        validated: List[str] = []
        for field in candidates:
            # Keep only fields that are explicitly allow-listed for primary entity
            if field in allowed:
                validated.append(field)

        # After computing validated, if it's empty, fall back to a minimal safe set
        if not validated:
            minimal = ["title", "priority", "createdTimeStamp"]
            validated = [f for f in minimal if f in allowed]
        return validated

    def _resolve_group_field(self, primary_entity: str, token: str) -> Optional[str]:
        """Map a grouping token to a concrete field path or Mongo expression.

        Returns either a string field path (relative to current doc) or a dict representing
        a MongoDB aggregation expression (e.g., for date bucketing).
        """
        # Date bucket helper
        def date_field_for(entity: str, which: str) -> Optional[str]:
            # which: 'created' | 'updated'
            if entity == 'page':
                return 'createdAt' if which == 'created' else 'updatedAt'
            if entity == 'timeline':
                # timeline stores a single 'timestamp' field for event time
                return 'timestamp'
            # Default to *TimeStamp for other entities
            return 'createdTimeStamp' if which == 'created' else 'updatedTimeStamp'

        def bucket_expr(entity: str, which: str, unit: str):
            field = date_field_for(entity, which)
            if not field:
                return None
            # Prefer $dateTrunc for week/month; for day we can also truncate
            if unit in {'week', 'month', 'day'}:
                return {"$dateTrunc": {"date": f"${field}", "unit": unit}}
            return None

        # Base mappings
        mapping: Dict[str, Dict[str, Any]] = {
            'workItem': {
                'project': 'project.name',
                'assignee': 'assignee.name',
                'cycle': 'cycle.name',
                'module': 'modules.name',
                'state': 'state.name',
                'status': 'state.name',  # accept 'status' as synonym for state
                'priority': 'priority',
                'business': 'projectDoc.business.name',  # ensure join if needed
                'created_day': bucket_expr('workItem', 'created', 'day'),
                'created_week': bucket_expr('workItem', 'created', 'week'),
                'created_month': bucket_expr('workItem', 'created', 'month'),
                'updated_day': bucket_expr('workItem', 'updated', 'day'),
                'updated_week': bucket_expr('workItem', 'updated', 'week'),
                'updated_month': bucket_expr('workItem', 'updated', 'month'),
            },
            'project': {
                'status': 'status',
                'business': 'business.name',
                'created_day': bucket_expr('project', 'created', 'day'),
                'created_week': bucket_expr('project', 'created', 'week'),
                'created_month': bucket_expr('project', 'created', 'month'),
                'updated_day': bucket_expr('project', 'updated', 'day'),
                'updated_week': bucket_expr('project', 'updated', 'week'),
                'updated_month': bucket_expr('project', 'updated', 'month'),
            },
            'cycle': {
                'project': 'project.name',
                'status': 'status',
                'created_day': bucket_expr('cycle', 'created', 'day'),
                'created_week': bucket_expr('cycle', 'created', 'week'),
                'created_month': bucket_expr('cycle', 'created', 'month'),
                'updated_day': bucket_expr('cycle', 'updated', 'day'),
                'updated_week': bucket_expr('cycle', 'updated', 'week'),
                'updated_month': bucket_expr('cycle', 'updated', 'month'),
            },
            'page': {
                'project': 'projectDoc.name',
                'cycle': 'linkedCycleDocs.name',
                'module': 'linkedModuleDocs.name',
                'visibility': 'visibility',
                'business': 'projectDoc.business.name',
                'created_day': bucket_expr('page', 'created', 'day'),
                'created_week': bucket_expr('page', 'created', 'week'),
                'created_month': bucket_expr('page', 'created', 'month'),
                'updated_day': bucket_expr('page', 'updated', 'day'),
                'updated_week': bucket_expr('page', 'updated', 'week'),
                'updated_month': bucket_expr('page', 'updated', 'month'),
            },
            'module': {
                'project': 'project.name',
                'business': 'project.business.name',
                'created_day': bucket_expr('module', 'created', 'day'),
                'created_week': bucket_expr('module', 'created', 'week'),
                'created_month': bucket_expr('module', 'created', 'month'),
            },
            'members': {
                'project': 'project.name',
                'business': 'project.business.name',
                'created_day': bucket_expr('members', 'created', 'day'),
                'created_week': bucket_expr('members', 'created', 'week'),
                'created_month': bucket_expr('members', 'created', 'month'),
            },
            'projectState': {
                'project': 'project.name',
                'business': 'project.business.name',
            },
            'timeline': {
                'project': 'project.name',
                'status': 'type',
                'assignee': 'user.name',
                'created_day': bucket_expr('timeline', 'created', 'day'),
                'created_week': bucket_expr('timeline', 'created', 'week'),
                'created_month': bucket_expr('timeline', 'created', 'month'),
                'updated_day': bucket_expr('timeline', 'updated', 'day'),
                'updated_week': bucket_expr('timeline', 'updated', 'week'),
                'updated_month': bucket_expr('timeline', 'updated', 'month'),
            },
        }
        entity_map = mapping.get(primary_entity, {})
        val = entity_map.get(token)
        # Some bucket_expr entries may be None if field not applicable
        return val if val is not None else None

class Planner:
    """Main query planner that orchestrates the entire process"""

    def __init__(self):
        self.generator = PipelineGenerator()
        self.llm_parser = LLMIntentParser()
        self.orchestrator = Orchestrator(tracer_name=__name__, max_parallel=5)

    async def plan_and_execute(self, query: str) -> Dict[str, Any]:
        """Plan and execute a natural language query using the Orchestrator."""
        try:
            # Define step coroutines as closures to capture self
            async def _ensure_connection(ctx: Dict[str, Any]) -> bool:
                await mongodb_tools.connect()
                return True

            async def _parse_intent(ctx: Dict[str, Any]) -> Optional[QueryIntent]:
                return await self.llm_parser.parse(ctx["query"])  # type: ignore[index]

            def _parse_validator(result: Any, _ctx: Dict[str, Any]) -> bool:
                return result is not None

            def _generate_pipeline(ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
                return self.generator.generate_pipeline(ctx["intent"])  # type: ignore[index]

            async def _execute(ctx: Dict[str, Any]) -> Any:
                intent: QueryIntent = ctx["intent"]  # type: ignore[assignment]
                args = {
                    "database": DATABASE_NAME,
                    "collection": intent.primary_entity,
                    "pipeline": ctx["pipeline"],
                }
                return await mongodb_tools.execute_tool("aggregate", args)

            steps: List[StepSpec] = [
                StepSpec(
                    name="ensure_connection",
                    coroutine=as_async(_ensure_connection),
                    requires=(),
                    provides="connected",
                    retries=2,
                    timeout_s=8.0,
                ),
                StepSpec(
                    name="parse_intent",
                    coroutine=as_async(_parse_intent),
                    requires=("query",),
                    provides="intent",
                    timeout_s=15.0,
                    retries=1,
                    validator=_parse_validator,
                ),
                StepSpec(
                    name="generate_pipeline",
                    coroutine=as_async(_generate_pipeline),
                    requires=("intent",),
                    provides="pipeline",
                    timeout_s=5.0,
                ),
                StepSpec(
                    name="execute_query",
                    coroutine=as_async(_execute),
                    requires=("intent", "pipeline"),
                    provides="result",
                    timeout_s=20.0,
                    retries=1,
                ),
            ]

            ctx = await self.orchestrator.run(
                steps,
                initial_context={"query": query},
                correlation_id=f"planner_{hash(query) & 0xFFFFFFFF:x}",
            )

            intent: QueryIntent = ctx["intent"]  # type: ignore[assignment]
            pipeline: List[Dict[str, Any]] = ctx["pipeline"]  # type: ignore[assignment]
            result = ctx.get("result")

            return {
                "success": True,
                "intent": intent.__dict__,
                "pipeline": _serialize_pipeline_for_json(pipeline),
                "pipeline_js": _format_pipeline_for_display(pipeline),
                "result": result,
                "planner": "llm",
            }
        except Exception as e:
            pass
            return {
                "success": False,
                "error": str(e),
                "query": query,
            }

# Global instance
query_planner = Planner()

async def plan_and_execute_query(query: str) -> Dict[str, Any]:
    """Convenience function to plan and execute queries"""
    return await query_planner.plan_and_execute(query)
