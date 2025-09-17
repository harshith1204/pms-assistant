#!/usr/bin/env python3
"""
Intelligent Query Planner for PMS System
Handles natural language queries and generates optimal MongoDB aggregation pipelines
based on the relationship registry
"""

import re
import json
from typing import Dict, List, Any, Optional, Set, Tuple
import os
from collections import defaultdict
from dataclasses import dataclass
import asyncio

from registry import REL, ALLOWED_FIELDS, ALIASES, resolve_field_alias, validate_fields, build_lookup_stage
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

class NaturalLanguageParser:
    """Parses natural language queries to extract intent"""

    def __init__(self):
        # Entity keywords mapped to collections
        self.entity_keywords = {
            'workItem': ['work item', 'task', 'bug', 'issue', 'story', 'ticket'],
            'project': ['project', 'initiative', 'program'],
            'cycle': ['cycle', 'sprint', 'iteration', 'phase'],
            'members': ['member', 'user', 'person', 'team member', 'developer'],
            'page': ['page', 'document', 'wiki', 'documentation'],
            'module': ['module', 'component', 'feature'],
            'projectState': ['state', 'status', 'workflow', 'stage']
        }

        # Action keywords
        self.action_keywords = {
            'find': ['find', 'get', 'show', 'list', 'display'],
            'count': ['count', 'how many', 'number of', 'total'],
            'filter': ['with', 'having', 'where', 'that have'],
            'group': ['grouped by', 'by', 'per'],
            'sort': ['sorted by', 'order by', 'ordered'],
            'aggregate': ['sum', 'average', 'total', 'summary']
        }

        # Work item status keywords (generic, not project/cycle)
        self.status_keywords = {
            'TODO': ['todo', 'to do', 'pending', 'open'],
            'COMPLETED': ['completed', 'done', 'finished', 'closed']
        }

        # Project status keywords aligned to PROJECT_STATUS enum
        self.project_status_keywords = {
            'NOT_STARTED': ['not started', 'new', 'not begun', 'yet to start'],
            'STARTED': ['started', 'has started', 'underway'],
            'COMPLETED': ['completed', 'finished', 'done'],
            'OVERDUE': ['overdue', 'late', 'past due']
        }

        # Cycle status keywords aligned to CYCLE_STATUS enum
        self.cycle_status_keywords = {
            'ACTIVE': ['active', 'in progress', 'ongoing', 'running'],
            'UPCOMING': ['upcoming', 'future', 'planned', 'next'],
            'COMPLETED': ['completed', 'finished', 'done']
        }

        # Page visibility keywords aligned to PageVisibility enum
        self.page_visibility_keywords = {
            'PUBLIC': ['public', 'visible to all'],
            'PRIVATE': ['private', 'restricted'],
            'ARCHIVED': ['archived', 'archive']
        }

    def parse_query(self, query: str) -> QueryIntent:
        """Parse natural language query into structured intent"""
        query_lower = query.lower().strip()

        # Extract primary entity
        primary_entity = self._extract_primary_entity(query_lower)

        # Extract target entities (related collections to include)
        target_entities = self._extract_target_entities(query_lower, primary_entity)

        # Extract filters
        filters = self._extract_filters(query_lower)

        # Extract aggregations
        aggregations = self._extract_aggregations(query_lower)

        # Extract grouping targets (e.g., grouped by cycle)
        group_by = self._extract_group_by(query_lower)

        # Extract projections
        projections = self._extract_projections(query_lower)

        # Extract sorting
        sort_order = self._extract_sorting(query_lower)

        # Extract limit
        limit = self._extract_limit(query_lower)

        # Determine intent for details vs count
        wants_count = ('count' in aggregations)
        wants_details = self._detect_detail_intent(query_lower, projections, wants_count)

        # If both are requested, prefer details per requirement
        if wants_details and wants_count:
            aggregations = [a for a in aggregations if a != 'count']
            wants_count = False

        return QueryIntent(
            primary_entity=primary_entity,
            target_entities=target_entities,
            filters=filters,
            aggregations=aggregations,
            group_by=group_by,
            projections=projections,
            sort_order=sort_order,
            limit=limit,
            wants_details=wants_details,
            wants_count=wants_count
        )

    def _extract_primary_entity(self, query: str) -> str:
        """Extract the primary entity from the query"""
        for collection, keywords in self.entity_keywords.items():
            for keyword in keywords:
                if keyword in query:
                    return collection
        return "project"  # Default fallback

    def _extract_target_entities(self, query: str, primary_entity: str) -> List[str]:
        """Extract related entities to include in the query"""
        target_entities = []

        # Look for relationship indicators
        relationship_indicators = {
            # generic
            'workItems': ['work items', 'tasks', 'bugs', 'issues'],
            'cycles': ['cycles', 'sprints', 'iterations'],
            'pages': ['pages', 'documentation', 'docs'],
            'modules': ['modules', 'components', 'features'],
            'states': ['states', 'status', 'workflow'],
            # workItem relations
            'assignee': ['assignee', 'assigned to', 'assigned', 'owner', 'owned by'],
            'project': ['project'],
            'cycle': ['cycle', 'sprint'],
            'module': ['module', 'component', 'feature'],
            'stateMaster': ['state', 'workflow']
        }

        for relation, keywords in relationship_indicators.items():
            for keyword in keywords:
                if keyword in query and relation in REL.get(primary_entity, {}):
                    target_entities.append(relation)
                    break

        return target_entities

    def _extract_filters(self, query: str) -> Dict[str, Any]:
        """Extract filter conditions from the query"""
        filters = {}

        # Status filters
        for status, keywords in self.status_keywords.items():
            for keyword in keywords:
                if keyword in query:
                    filters['status'] = status
                    break

        # Priority filters aligned to PRIORITY enum
        priority_keywords = {
            'URGENT': ['urgent', 'critical', 'asap', 'immediately'],
            'HIGH': ['high', 'important', 'severe'],
            'MEDIUM': ['medium', 'normal'],
            'LOW': ['low', 'minor', 'low priority'],
            'NONE': ['none', 'no priority', 'unprioritized']
        }
        for priority, keywords in priority_keywords.items():
            if any(keyword in query for keyword in keywords):
                filters['priority'] = priority
                break

        # Project status filters
        for status, keywords in self.project_status_keywords.items():
            if any(keyword in query for keyword in keywords):
                filters['project_status'] = status
                break

        # Cycle status filters
        for status, keywords in self.cycle_status_keywords.items():
            if any(keyword in query for keyword in keywords):
                filters['cycle_status'] = status
                break

        # Page visibility filters
        for visibility, keywords in self.page_visibility_keywords.items():
            if any(keyword in query for keyword in keywords):
                filters['page_visibility'] = visibility
                break

        # Project name filters - support multiple phrasings
        project_match1 = re.search(r'project\s+["\']([^"\']+)["\']', query)
        project_match2 = re.search(r'["\']([^"\']+)["\']\s+project', query)
        project_match3 = re.search(r'in\s+(?:the\s+)?([a-z0-9 _\-]+)\s+project', query)
        if project_match1:
            filters['project_name'] = project_match1.group(1).strip()
        elif project_match2:
            filters['project_name'] = project_match2.group(1).strip()
        elif project_match3:
            filters['project_name'] = project_match3.group(1).strip()

        # Cycle name filters
        cycle_match = re.search(r'cycle\s+["\']([^"\']+)["\']', query)
        if cycle_match:
            filters['cycle_title'] = cycle_match.group(1)

        # Assignee name filters (e.g., "assigned to Aditya Sharma")
        assignee_match = re.search(r'assigned to\s+([A-Za-z][\w .\-]+?)(?=(\s+(?:in|on|for|within|of|project|cycle|grouped|group|by)\b|[\.,]|$))', query)
        if assignee_match:
            filters['assignee_name'] = assignee_match.group(1).strip()

        # Module name filters (e.g., "CRM module", "API module")
        module_match = re.search(r'(\w+)\s+module', query)
        if module_match:
            filters['module_name'] = module_match.group(1)

        return filters

    def _extract_group_by(self, query: str) -> List[str]:
        """Extract grouping targets from phrases like 'grouped by cycle' or 'group by project, cycle'."""
        group_by: List[str] = []
        raw = None
        m = re.search(r'group(?:ed)? by\s+([a-zA-Z][a-zA-Z .,_\-]+)', query)
        if m:
            raw = m.group(1)
        elif 'group' in query:
            # Fallback: try ' by <term>' after a 'group' mention
            m2 = re.search(r' by\s+([a-zA-Z][a-zA-Z .,_\-]+)', query)
            if m2:
                raw = m2.group(1)
        if not raw:
            return group_by

        parts = re.split(r'(?:,| and | & )', raw)
        for p in parts:
            token = p.strip().lower()
            token = re.sub(r'[\.,;:!?].*$', '', token).strip()
            mapped = None
            if token.startswith('cycle'):
                mapped = 'cycle'
            elif token.startswith('project'):
                mapped = 'project'
            elif token.startswith('assignee') or token.startswith('owner'):
                mapped = 'assignee'
            elif token.startswith('status') or token.startswith('state'):
                mapped = 'status'
            elif token.startswith('priority'):
                mapped = 'priority'
            elif token.startswith('module'):
                mapped = 'module'
            if mapped and mapped not in group_by:
                group_by.append(mapped)
        return group_by

    def _extract_aggregations(self, query: str) -> List[str]:
        """Extract aggregation operations"""
        aggregations = []

        if any(word in query for word in ['count', 'how many', 'number of', 'total']):
            aggregations.append('count')

        if any(word in query for word in ['group', 'grouped by', 'by']):
            aggregations.append('group')

        if any(word in query for word in ['summary', 'overview', 'breakdown']):
            aggregations.append('summary')

        return aggregations

    def _extract_projections(self, query: str) -> List[str]:
        """Extract fields to project"""
        projections = []

        # Common field keywords
        field_keywords = {
            'title': ['title', 'name'],
            'status': ['status', 'state'],
            'priority': ['priority', 'importance'],
            'assignee': ['assignee', 'assigned to', 'owner'],
            'created': ['created', 'date', 'when'],
            'project': ['project', 'project name'],
            'cycle': ['cycle', 'sprint']
        }

        for field, keywords in field_keywords.items():
            for keyword in keywords:
                if keyword in query:
                    projections.append(field)
                    break

        return projections[:5] if projections else []  # Limit to 5 fields

    def _extract_sorting(self, query: str) -> Optional[Dict[str, int]]:
        """Extract sorting information"""
        if 'sort' in query or 'order' in query:
            if 'date' in query or 'created' in query:
                return {'createdTimeStamp': -1}
            elif 'priority' in query:
                return {'priority': -1}
            elif 'status' in query:
                return {'status': 1}
        return None

    def _extract_limit(self, query: str) -> Optional[int]:
        """Extract result limit"""
        limit_match = re.search(r'(?:show|list|get)\s+(\d+)', query)
        if limit_match:
            return int(limit_match.group(1))
        return 20  # Default limit

    def _detect_detail_intent(self, query: str, projections: List[str], wants_count: bool) -> bool:
        """Detect whether the user wants detailed records rather than just counts.

        Rules:
        - Explicit phrases like 'details', 'exact details' => True
        - If user specifies field-like words (projections extracted) => True
        - If the query is a numeric question ('how many', 'number of', 'count of') => False unless 'details' also present
        - Generic list verbs ('list', 'show', 'get', 'display') => True only when not explicitly a count question
        """
        if 'exact details' in query or 'details' in query:
            return True
        count_markers = any(kw in query for kw in ['how many', 'number of', 'count of'])
        if count_markers and not ('details' in query):
            return False
        if projections:
            return True
        list_markers = any(kw in query for kw in ['list', 'show', 'display', 'get', 'which', 'what are'])
        if list_markers and not wants_count:
            return True
        return False

class LLMIntentParser:
    """LLM-backed intent parser that produces a structured plan compatible with QueryIntent.

    The LLM proposes:
    - primary_entity
    - target_entities (relations to join)
    - filters (normalized keys: status, priority, project_status, cycle_status, page_visibility,
      project_name, cycle_title, assignee_name, module_name)
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

    async def parse(self, query: str) -> Optional[QueryIntent]:
        """Use the LLM to produce a structured intent. Returns None on failure."""
        system = (
            "You are an expert MongoDB query planner for a Project Management System. "
            "Given a natural-language question, output a STRICT JSON object describing the intent. "
            "Use only the provided entity names, relations, and allow-listed fields. "
            "Do not generate raw pipelines; produce a plan that a downstream generator will realize.\n\n"
            "Collections (entities): " + ", ".join(self.entities) + "\n" +
            "Relations per entity (use only these as target_entities):\n" +
            "\n".join(f"- {e}: {', '.join(self.entity_relations.get(e, []))}" for e in self.entities) + "\n\n" +
            "Allow-listed fields per entity (projections must be subset of primary's list):\n" +
            "\n".join(f"- {e}: {', '.join(self.allowed_fields.get(e, []))}" for e in self.entities) + "\n\n" +
            "Normalize keys as follows: status, priority, project_status, cycle_status, page_visibility, "
            "project_name, cycle_title, assignee_name, module_name. Use uppercase enum values if obvious.\n"
            "Aggregations allowed: count, group, summary. Group-by tokens allowed: cycle, project, assignee, status, priority, module.\n"
            "sort_order keys allowed: createdTimeStamp, priority, status.\n"
            "Always include ALL top-level keys in the JSON output with appropriate empty values if unknown."
        )

        schema = {
            "primary_entity": "string; one of " + ", ".join(self.entities),
            "target_entities": "string[]; relations to join for primary, from the allowed list above",
            "filters": {
                "status": "TODO|COMPLETED?",
                "priority": "URGENT|HIGH|MEDIUM|LOW|NONE?",
                "project_status": "NOT_STARTED|STARTED|COMPLETED|OVERDUE?",
                "cycle_status": "ACTIVE|UPCOMING|COMPLETED?",
                "page_visibility": "PUBLIC|PRIVATE|ARCHIVED?",
                "project_name": "string? (free text, used as case-insensitive regex)",
                "cycle_title": "string?",
                "assignee_name": "string?",
                "module_name": "string?"
            },
            "aggregations": "string[]; subset of [count, group, summary]",
            "group_by": "string[]; subset of [cycle, project, assignee, status, priority, module]",
            "projections": "string[]; subset of allow-listed fields for primary_entity",
            "sort_order": "object?; single key among allowed sort keys mapping to 1 or -1",
            "limit": "integer <= 100; default 20",
            "wants_details": "boolean",
            "wants_count": "boolean"
        }

        user = (
            "TASK: Convert the user's request into a strict JSON intent object.\n"
            "Rules:\n"
            "- Only use allowed entities, relations, and fields.\n"
            "- If both details and count are implied, set wants_details true and wants_count false.\n"
            "- Keep target_entities minimal but sufficient to support filters and group_by.\n"
            "- Do NOT include any explanations or prose. Output JSON ONLY.\n\n"
            f"Schema (for reference, keys only): {json.dumps(schema)}\n\n"
            f"User Query: {query}"
        )

        try:
            ai = await self.llm.ainvoke([SystemMessage(content=system), HumanMessage(content=user)])
            content = ai.content.strip()
            # Some models wrap JSON in code fences; strip if present
            if content.startswith("```"):
                content = content.strip("`\n").split("\n", 1)[-1]
                if content.startswith("json\n"):
                    content = content[5:]
            data = json.loads(content)
        except Exception:
            return None

        try:
            return self._sanitize_intent(data)
        except Exception:
            return None

    def _sanitize_intent(self, data: Dict[str, Any]) -> QueryIntent:
        # Primary entity
        primary = data.get("primary_entity") or "project"
        if primary not in self.entities:
            primary = "project"

        # Allowed relations for primary
        allowed_rels = set(self.entity_relations.get(primary, []))
        target_entities: List[str] = []
        for rel in (data.get("target_entities") or []):
            if isinstance(rel, str) and rel.split(".")[0] in allowed_rels:
                target_entities.append(rel)

        # Filters: pick only known keys
        raw_filters = data.get("filters") or {}
        known_filter_keys = {
            "status", "priority", "project_status", "cycle_status", "page_visibility",
            "project_name", "cycle_title", "assignee_name", "module_name"
        }
        filters = {k: v for k, v in raw_filters.items() if k in known_filter_keys and isinstance(v, (str, int))}

        # Aggregations
        allowed_aggs = {"count", "group", "summary"}
        aggregations = [a for a in (data.get("aggregations") or []) if a in allowed_aggs]

        # Group by tokens
        allowed_group = {"cycle", "project", "assignee", "status", "priority", "module"}
        group_by = [g for g in (data.get("group_by") or []) if g in allowed_group]

        # Projections limited to allow-listed fields for primary
        allowed_projection_set = set(self.allowed_fields.get(primary, []))
        projections = [p for p in (data.get("projections") or []) if p in allowed_projection_set][:10]

        # Sort order
        sort_order = None
        so = data.get("sort_order") or {}
        if isinstance(so, dict) and so:
            key, val = next(iter(so.items()))
            if key in {"createdTimeStamp", "priority", "status"} and val in (1, -1):
                sort_order = {key: val}

        # Limit
        limit_val = data.get("limit")
        try:
            limit = int(limit_val) if limit_val is not None else 20
            if limit <= 0:
                limit = 20
            limit = min(limit, 100)
        except Exception:
            limit = 20

        # Detail vs count flags
        wants_details = bool(data.get("wants_details", False))
        wants_count = bool(data.get("wants_count", False))
        if wants_details and wants_count:
            wants_count = False
            if "count" in aggregations:
                aggregations = [a for a in aggregations if a != "count"]

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

class PipelineGenerator:
    """Generates MongoDB aggregation pipelines based on query intent and relationships"""

    def __init__(self):
        self.relationship_cache = {}  # Cache for computed relationship paths

    def generate_pipeline(self, intent: QueryIntent) -> List[Dict[str, Any]]:
        """Generate MongoDB aggregation pipeline for the given intent"""
        pipeline = []

        # Start with the primary collection
        collection = intent.primary_entity

        # Add filters for the primary collection
        if intent.filters:
            primary_filters = self._extract_primary_filters(intent.filters, collection)
            if primary_filters:
                pipeline.append({"$match": primary_filters})

        # Ensure lookups needed by secondary filters or grouping are included
        required_relations: Set[str] = set(intent.target_entities)
        if intent.filters:
            # If we will filter by joined fields, we must join those relations
            if 'project_name' in intent.filters and 'project' in REL.get(collection, {}):
                required_relations.add('project')
            if 'cycle_title' in intent.filters and 'cycle' in REL.get(collection, {}):
                required_relations.add('cycle')
            if 'assignee_name' in intent.filters and 'assignee' in REL.get(collection, {}):
                required_relations.add('assignee')

        # Include relations used by grouping keys
        if intent.group_by:
            if 'cycle' in intent.group_by and 'cycle' in REL.get(collection, {}):
                required_relations.add('cycle')
            if 'project' in intent.group_by and 'project' in REL.get(collection, {}):
                required_relations.add('project')
            if 'assignee' in intent.group_by and 'assignee' in REL.get(collection, {}):
                required_relations.add('assignee')
            if 'module' in intent.group_by and 'module' in REL.get(collection, {}):
                required_relations.add('module')

        # Add relationship lookups (supports multi-hop via dot syntax like project.states)
        for target_entity in required_relations:
            # Allow multi-hop relation names like "project.stateMaster" from queries
            hops = target_entity.split(".")
            current_collection = collection
            for hop in hops:
                if hop not in REL.get(current_collection, {}):
                    break
                relationship = REL[current_collection][hop]
                lookup = build_lookup_stage(relationship["target"], relationship, current_collection)
                if lookup:
                    pipeline.append(lookup)
                    if "join" in relationship or "expr" in relationship:
                        pipeline.append({
                            "$unwind": {
                                "path": f"${relationship['target']}",
                                "preserveNullAndEmptyArrays": True
                            }
                        })
                current_collection = relationship["target"]

        # Add secondary filters (on joined collections)
        if intent.filters:
            secondary_filters = self._extract_secondary_filters(intent.filters)
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
                # Sort by count desc for readability
                pipeline.append({"$sort": {"count": -1}})
                # Present a tidy shape
                project_shape: Dict[str, Any] = {"count": 1}
                if intent.wants_details:
                    project_shape["items"] = 1
                project_shape["group"] = "$_id"
                pipeline.append({"$project": project_shape})

        # Add aggregations like count (skip count when details are requested)
        if intent.aggregations and not intent.wants_details and not intent.group_by:
            for agg in intent.aggregations:
                if agg == 'count':
                    pipeline.append({"$count": "total"})
                    return pipeline  # Count is terminal

        # Add sorting (handle custom priority order) — skip if already grouped
        if intent.sort_order and not intent.group_by:
            if 'priority' in intent.sort_order:
                # Map PRIORITY enum to rank for sorting: URGENT > HIGH > MEDIUM > LOW > NONE
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

        # Determine projections for details (skip when grouping since we reshape after $group)
        effective_projections: List[str] = intent.projections
        if intent.wants_details and not intent.group_by and not effective_projections:
            effective_projections = self._get_default_projections(intent.primary_entity)

        # Add projections after sorting so computed fields can be hidden
        if effective_projections and not intent.group_by:
            projection = self._generate_projection(effective_projections, intent.target_entities, intent.primary_entity)
            # Ensure we exclude helper fields from output
            pipeline.append({"$project": projection})
            pipeline.append({"$unset": "_priorityRank"})

        # Add limit
        if intent.limit:
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

    def _extract_secondary_filters(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Extract filters that apply to joined collections"""
        secondary_filters = {}

        # Project name filter (applies to joined project)
        if 'project_name' in filters:
            secondary_filters['project.name'] = {'$regex': filters['project_name'], '$options': 'i'}

        # Cycle title filter (applies to joined cycle)
        if 'cycle_title' in filters:
            secondary_filters['cycle.title'] = {'$regex': filters['cycle_title'], '$options': 'i'}

        # Assignee name filter: support both raw embedded and joined members
        if 'assignee_name' in filters:
            secondary_filters['$or'] = [
                {'assignee.name': {'$regex': filters['assignee_name'], '$options': 'i'}},
                {'members.name': {'$regex': filters['assignee_name'], '$options': 'i'}},
            ]

        # Module name filter (applies to joined module)
        if 'module_name' in filters:
            secondary_filters['module.title'] = {'$regex': filters['module_name'], '$options': 'i'}

        return secondary_filters

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
                "displayBugNo", "title", "status", "priority",
                "state.name", "stateMaster.name", "assignee",
                "project.name", "createdTimeStamp"
            ],
            "project": [
                "projectDisplayId", "name", "status", "isActive", "isArchived", "createdTimeStamp"
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
        # If none survived validation, just return _id (already always projected)
        return validated

    def _resolve_group_field(self, primary_entity: str, token: str) -> Optional[str]:
        """Map a grouping token to a concrete field path in the current pipeline."""
        mapping = {
            'workItem': {
                'cycle': 'cycle.title',
                'project': 'project.name',
                'assignee': 'members.name',  # joined alias for assignee relation
                'status': 'status',
                'priority': 'priority',
                'module': 'module.title',
            },
            'project': {
                'status': 'status',
            },
            'cycle': {
                'project': 'project.name',
                'status': 'status',
            },
        }
        entity_map = mapping.get(primary_entity, {})
        return entity_map.get(token)

class QueryPlanner:
    """Main query planner that orchestrates the entire process"""

    def __init__(self):
        self.parser = NaturalLanguageParser()
        self.generator = PipelineGenerator()
        self.llm_parser = LLMIntentParser()

    async def plan_and_execute(self, query: str) -> Dict[str, Any]:
        """Plan and execute a natural language query"""
        try:
            # Ensure MongoDB connection
            await mongodb_tools.connect()

            # Try LLM-backed parsing first; fall back to heuristic if it fails
            intent_source = "llm"
            intent: Optional[QueryIntent] = await self.llm_parser.parse(query)
            if not intent:
                intent = self.parser.parse_query(query)
                intent_source = "heuristic"

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
                "planner": intent_source
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "query": query
            }

# Global instance
query_planner = QueryPlanner()

async def plan_and_execute_query(query: str) -> Dict[str, Any]:
    """Convenience function to plan and execute queries"""
    return await query_planner.plan_and_execute(query)
