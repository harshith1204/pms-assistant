#!/usr/bin/env python3
"""
Intelligent Query Planner for PMS System
Handles natural language queries and generates optimal MongoDB aggregation pipelines
based on the relationship registry
"""

import json
import re
from typing import Dict, List, Any, Optional, Set
import os
from dataclasses import dataclass

from registry import REL, ALLOWED_FIELDS, build_lookup_stage
from constants import mongodb_tools, DATABASE_NAME
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage

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
    wants_details: bool  # Prefer detailed documents over counts
    wants_count: bool  # Whether the user asked for a count

@dataclass
class RelationshipPath:
    """Represents a traversal path through relationships"""
    start_collection: str
    end_collection: str
    path: List[str]  # List of relationship names
    cost: int  # Computational cost of this path
    filters: Dict[str, Any]  # Filters that can be applied at each step


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
        self.model_name = model_name or os.environ.get("QUERY_PLANNER_MODEL", "qwen3:0.6b-fp16")
        # Keep the model reasonably deterministic for planning
        self.llm = ChatOllama(
            model=self.model_name,
            temperature=0.1,
            num_ctx=4096,
            num_predict=768,
            top_p=0.9,
            top_k=40,
        )

        # Precompute compact schema context to keep prompts short
        self.entities: List[str] = list(REL.keys())
        self.entity_relations: Dict[str, List[str]] = {
            entity: list(REL.get(entity, {}).keys()) for entity in self.entities
        }
        self.allowed_fields: Dict[str, List[str]] = {
            entity: sorted(list(ALLOWED_FIELDS.get(entity, set()))) for entity in self.entities
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
        """Infer time-based sorting preferences from free-form query text.

        Recognizes phrases like 'recent', 'latest', 'newest' → createdTimeStamp desc (-1)
        and 'oldest', 'earliest' → createdTimeStamp asc (1). Also handles
        'ascending/descending' when mentioned alongside time/date/created keywords.
        """
        if not query_text:
            return None

        text = query_text.lower()

        # Direct recency/age cues
        if re.search(r"\b(recent|latest|newest|most\s+recent|newer\s+first)\b", text):
            return {"createdTimeStamp": -1}
        if re.search(r"\b(oldest|earliest|older\s+first)\b", text):
            return {"createdTimeStamp": 1}

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
            "- Cycles and modules belong to projects\n\n"

            "## VERY IMPORTANT\n"
            "## AVAILABLE FILTERS (use these exact keys):\n"
            "- state: Open|Completed|Backlog|Re-Raised|In-Progress|Verified\n"
            "- priority: URGENT|HIGH|MEDIUM|LOW|NONE\n"
            "- status: (varies by collection - use appropriate values)\n"
            "- project_status: NOT_STARTED|STARTED|COMPLETED|OVERDUE\n"
            "- cycle_status: ACTIVE|UPCOMING|COMPLETED\n"
            "- page_visibility: PUBLIC|PRIVATE|ARCHIVED\n"
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
            "- label: (work item labels)\n\n"

            "## TIME-BASED SORTING (CRITICAL)\n"
            "Infer sort_order from phrasing when the user implies recency or age.\n"
            "- 'recent', 'latest', 'newest', 'most recent' → {\"createdTimeStamp\": -1}\n"
            "- 'oldest', 'earliest', 'older first' → {\"createdTimeStamp\": 1}\n"
            "- If 'ascending/descending' is mentioned with created/time/date/timestamp, map to 1/-1 respectively on 'createdTimeStamp'.\n"
            "Only include sort_order when relevant; otherwise set it to null.\n\n"

            "## NAME EXTRACTION RULES - CRITICAL\n"
            "ALWAYS extract ONLY the core entity name, NEVER include descriptive phrases:\n"
            "- Query: 'work items within PMS project' → project_name: 'PMS' (NOT 'PMS project')\n"
            "- Query: 'tasks from test module' → module_name: 'test' (NOT 'test module')\n"
            "- Query: 'bugs assigned to alice' → assignee_name: 'alice' (NOT 'alice assigned')\n"
            "- Query: 'items in upcoming cycle' → cycle_name: 'upcoming' (NOT 'upcoming cycle')\n"
            "❌ WRONG: {'project_name': 'PMS project'} - this breaks regex matching!\n"
            "✅ CORRECT: {'project_name': 'PMS'} - this works with regex matching\n\n"

            "## COMMON QUERY PATTERNS\n"
            "- 'Show me X' → list/get details (aggregations: [])\n"
            "- 'How many X' → count (aggregations: ['count'])\n"
            "- 'Breakdown by X' → group results (aggregations: ['group'])\n"
            "- 'X assigned to Y' → filter by assignee name (Y = assignee_name)\n"
            "- 'X from/in/belonging to/associated with Y' → filter by project/cycle/module name (Y = project_name/cycle_name/module_name)\n"
            "- 'X in Y status' → filter by status/priority\n"
            "- 'Y project' → if asking about work items: workItem with project_name filter\n"
            "  → Context matters: 'details of Y project' vs 'work items associated with Y project'\n\n"
            
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
            '  "wants_details": true,\n'
            '  "wants_count": false\n'
            "}\n\n"

            "## EXAMPLES\n"
            "- 'show me tasks assigned to alice' → {\"primary_entity\": \"workItem\", \"filters\": {\"assignee_name\": \"alice\"}, \"aggregations\": []}\n"
            "- 'how many bugs are there' → {\"primary_entity\": \"workItem\", \"aggregations\": [\"count\"]}\n"
            "- 'count active projects' → {\"primary_entity\": \"project\", \"filters\": {\"project_status\": \"STARTED\"}, \"aggregations\": [\"count\"]}\n"
            "- 'group tasks by priority' → {\"primary_entity\": \"workItem\", \"aggregations\": [\"group\"], \"group_by\": [\"priority\"]}\n"
            "- 'show archived projects' → {\"primary_entity\": \"project\", \"filters\": {\"isArchived\": true}, \"aggregations\": []}\n"
            "- 'find favourite modules' → {\"primary_entity\": \"module\", \"filters\": {\"isFavourite\": true}, \"aggregations\": []}\n"
            "- 'show work items with bug label' → {\"primary_entity\": \"workItem\", \"filters\": {\"label\": \"bug\"}, \"aggregations\": []}\n"
            "- 'who created this project' → {\"primary_entity\": \"project\", \"filters\": {\"createdBy_name\": \"john\"}, \"aggregations\": []}\n\n"
            "- 'show recent tasks' → {\"primary_entity\": \"workItem\", \"aggregations\": [], \"sort_order\": {\"createdTimeStamp\": -1}}\n"
            "- 'list oldest projects' → {\"primary_entity\": \"project\", \"aggregations\": [], \"sort_order\": {\"createdTimeStamp\": 1}}\n"
            "- 'bugs in ascending created order' → {\"primary_entity\": \"workItem\", \"aggregations\": [], \"sort_order\": {\"createdTimeStamp\": 1}}\n\n"

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

        # Simplified filter processing - keep only valid filters
        raw_filters = data.get("filters") or {}
        filters: Dict[str, Any] = {}

        # Map legacy 'status' to 'state' for workItem if present
        if primary == "workItem" and "status" in raw_filters and "state" not in raw_filters:
            raw_filters["state"] = raw_filters.pop("status")

        # Keep only known filter keys and clean them
        known_filter_keys = {
            "state", "priority", "project_status", "cycle_status", "page_visibility",
            "status", "access", "isActive", "isArchived", "isDefault", "isFavourite",
            "type", "role", "visibility", "label",
            "project_name", "cycle_name", "assignee_name", "module_name", "member_role",
            "createdBy_name"
        }

        for k, v in raw_filters.items():
            if k in known_filter_keys and not self._is_placeholder(v):
                # Validate and normalize filter values
                if k == "state" and isinstance(v, str):
                    # Normalize state values
                    normalized_state = self._normalize_state_value(v.strip())
                    if normalized_state:
                        filters[k] = normalized_state
                elif k == "priority" and isinstance(v, str):
                    # Normalize priority values
                    normalized_priority = self._normalize_priority_value(v.strip())
                    if normalized_priority:
                        filters[k] = normalized_priority
                elif k in ["project_status", "cycle_status", "page_visibility"] and isinstance(v, str):
                    # Normalize status enum values
                    normalized_status = self._normalize_status_value(k, v.strip())
                    if normalized_status:
                        filters[k] = normalized_status
                elif k in ["isActive", "isArchived", "isDefault", "isFavourite"]:
                    # Handle boolean values
                    normalized_bool = self._normalize_boolean_value_from_any(v)
                    if normalized_bool is not None:
                        filters[k] = normalized_bool
                # Keep name-based filter values as provided by LLM
                elif k in ["project_name", "cycle_name", "module_name", "assignee_name", "createdBy_name"] and isinstance(v, str):
                    filters[k] = v.strip()
                else:
                    # For other valid filters, keep as-is
                    filters[k] = v


        # Aggregations
        allowed_aggs = {"count", "group", "summary"}
        aggregations = [a for a in (data.get("aggregations") or []) if a in allowed_aggs]

        # Group by tokens
        allowed_group = {"cycle", "project", "assignee", "state", "priority", "module"}
        group_by = [g for g in (data.get("group_by") or []) if g in allowed_group]

        # If user grouped by cross-entity tokens, force workItem as base (entity lock)
        cross_tokens = {"assignee", "project", "cycle", "module"}
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
            if norm_key in {"createdTimeStamp", "priority", "state", "status"} and norm_dir in (1, -1):
                sort_order = {norm_key: norm_dir}

        # Limit
        limit_val = data.get("limit")
        try:
            limit = int(limit_val) if limit_val is not None else 20
            if limit <= 0:
                limit = 20
            limit = min(limit, 100)
        except Exception:
            limit = 20

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

        # If no explicit sort provided and no grouping/count, infer time-based sort from phrasing
        if not sort_order and not group_by and not wants_count:
            inferred_sort = self._infer_sort_order_from_query(original_query or "")
            if inferred_sort:
                sort_order = inferred_sort

        return QueryIntent(
            primary_entity=primary,
            target_entities=target_entities,
            filters=filters,
            aggregations=aggregations,
            group_by=group_by,
            projections=projections,
            sort_order=sort_order,
            limit=limit,
            wants_details=wants_details,
            wants_count=wants_count,
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
            },
            'module': {
                'project': 'project',
                'assignee': 'assignee',
            },
            'page': {
                'project': 'project',  # key in REL is 'project', alias is 'projectDoc'
                'cycle': 'linkedCycle',
                'module': 'linkedModule',
            },
            'members': {
                'project': 'project',
            },
            'projectState': {
                'project': 'project',
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

        # Add secondary filters (on joined collections)
        if secondary_filters:
            pipeline.append({"$match": secondary_filters})

        # Add grouping if requested
        if intent.group_by:
            group_id_expr: Any
            id_fields: Dict[str, Any] = {}
            for token in intent.group_by:
                field_path = self._resolve_group_field(intent.primary_entity, token)
                if field_path:
                    id_fields[token] = f"${field_path}"
            if not id_fields:
                # Fallback: do nothing if we can't resolve
                pass
            else:
                group_id_expr = list(id_fields.values())[0] if len(id_fields) == 1 else id_fields
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
                # Sorting for grouped results: default to count desc, allow sorting by grouped keys
                if intent.sort_order:
                    sort_key, sort_dir = next(iter(intent.sort_order.items()))
                    if sort_key in intent.group_by:
                        # Sort by the grouped key inside _id
                        if len(id_fields) == 1:
                            pipeline.append({"$sort": {"_id": sort_dir}})
                        else:
                            pipeline.append({"$sort": {f"_id.{sort_key}": sort_dir}})
                    else:
                        pipeline.append({"$sort": {"count": -1}})
                else:
                    pipeline.append({"$sort": {"count": -1}})
                # Present a tidy shape
                project_shape: Dict[str, Any] = {"count": 1}
                if intent.wants_details:
                    project_shape["items"] = 1
                project_shape["group"] = "$_id"
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

        # Add limit (only for non-grouped queries; grouped handled above)
        if intent.limit and not intent.group_by:
            pipeline.append({"$limit": intent.limit})

        return pipeline

    def _extract_primary_filters(self, filters: Dict[str, Any], collection: str) -> Dict[str, Any]:
        """Extract filters that apply to the primary collection"""
        primary_filters = {}

        if collection == "workItem":
            if 'status' in filters:
                primary_filters['status'] = filters['status']
            if 'priority' in filters:
                primary_filters['priority'] = filters['priority']
            if 'state' in filters:
                # Map logical state filter to embedded field
                primary_filters['state.name'] = filters['state']

        elif collection == "project":
            if 'project_status' in filters:
                primary_filters['status'] = filters['project_status']

        elif collection == "cycle":
            if 'cycle_status' in filters:
                primary_filters['status'] = filters['cycle_status']

        elif collection == "page":
            if 'page_visibility' in filters:
                primary_filters['visibility'] = filters['page_visibility']

        return primary_filters

    def _extract_secondary_filters(self, filters: Dict[str, Any], collection: str) -> Dict[str, Any]:
        """Extract filters that apply to joined collections, guarded by available relations."""
        s: Dict[str, Any] = {}

        # Project name: allow both embedded project.name and joined alias projectDoc.name
        if 'project_name' in filters:
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
                "createdTimeStamp"
            ],
            "project": [
                "projectDisplayId", "name", "status", "isActive", "isArchived", "createdTimeStamp",
                "createdBy.name"
            ],
            "cycle": [
                "title", "status", "startDate", "endDate"
            ],
            "members": [
                "name", "email", "role", "joiningDate"
            ],
            "page": [
                "title", "visibility", "createdAt"
            ],
            "module": [
                "title", "description", "isFavourite", "createdTimeStamp"
            ],
            "projectState": [
                "name", "subStates.name", "subStates.order"
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
        """Map a grouping token to a concrete field path in the current pipeline."""
        mapping = {
            'workItem': {
                # Only relations that exist in REL for workItem
                'project': 'project.name',
                'assignee': 'assignee.name',
                'cycle': 'cycle.name',
                'module': 'modules.name',
                'state': 'state.name',
                'priority': 'priority',
            },
            'project': {
                'status': 'status',  # project status unchanged
            },
            'cycle': {
                'project': 'project.name',
                'status': 'status',  # cycle status unchanged
            },
            'page': {
                'project': 'projectDoc.name',
                'cycle': 'linkedCycleDocs.name',
                'module': 'linkedModuleDocs.name',
            },
        }
        entity_map = mapping.get(primary_entity, {})
        return entity_map.get(token)

class Planner:
    """Main query planner that orchestrates the entire process"""

    def __init__(self):
        self.generator = PipelineGenerator()
        self.llm_parser = LLMIntentParser()

    async def plan_and_execute(self, query: str) -> Dict[str, Any]:
        """Plan and execute a natural language query"""
        try:
            # Ensure MongoDB connection
            await mongodb_tools.connect()

            # Parse intent via LLM
            intent: Optional[QueryIntent] = await self.llm_parser.parse(query)
            if not intent:
                return {
                    "success": False,
                    "error": "Failed to parse query intent",
                    "query": query
                }

            # Generate the pipeline
            pipeline = self.generator.generate_pipeline(intent)

            # Execute the query
            result = await mongodb_tools.execute_tool("aggregate", {
                "database": DATABASE_NAME,
                "collection": intent.primary_entity,
                "pipeline": pipeline
            })

            return {
                "success": True,
                "intent": intent.__dict__,
                "pipeline": pipeline,
                "result": result,
                "planner": "llm"
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "query": query
            }

# Global instance
query_planner = Planner()

async def plan_and_execute_query(query: str) -> Dict[str, Any]:
    """Convenience function to plan and execute queries"""
    return await query_planner.plan_and_execute(query)
