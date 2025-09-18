#!/usr/bin/env python3
"""
Intelligent Query Planner for PMS System
Handles natural language queries and generates optimal MongoDB aggregation pipelines
based on the relationship registry
"""

import re
import json
from typing import Dict, List, Any, Optional, Set, Tuple
from collections import defaultdict
from dataclasses import dataclass
import asyncio
from langchain_groq import ChatGroq
from dotenv import load_dotenv
load_dotenv()
import os
# from agent import llm
from registry import REL, ALLOWED_FIELDS, ALIASES, resolve_field_alias, validate_fields, build_lookup_stage
from constants import mongodb_tools, DATABASE_NAME
groq_api_key = os.getenv("GROQ_API_KEY")
if not groq_api_key:
    raise ValueError(
        "FATAL: GROQ_API_KEY environment variable not set.\n"
        "Please create a .env file and add your Groq API key to it."
    )
llm = ChatGroq(
            api_key=groq_api_key,
            model="llama-3.1-8b-instant",
            streaming=False,
            temperature= 0.3
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


class LLMNaturalLanguageParser:
    """Parses natural language queries using an LLM instead of rules."""


    def __init__(self, llm_client):
        self.llm = llm_client # An LLM API client (e.g., OpenAI, Anthropic, etc.)


    def parse_query(self, query: str) -> QueryIntent:
        """Ask the LLM to parse the query into structured intent."""
        
        prompt = f"""
        Your task is to convert the user query into a JSON object that follows the schema below.  
        Return only the raw JSON object — no explanations, no comments, no markdown.

        JSON Schema:
        {{
            "primary_entity": "workItem | project | cycle | members | page | module | projectState",
            "target_entities": ["related entities like project, cycle, module, assignee"],
            "filters": {{"field": "value"}},
            "aggregations": ["count | group | summary"],
            "group_by": ["cycle | project | status | priority | module | assignee"],
            "projections": ["title | status | priority | assignee | project | cycle | created"],
            "sort_order": {{"field": 1, "field": -1}},
            "limit": 20,
            "wants_details": true|false,
            "wants_count": true|false
        }}
        
        Inference Rules:  
        - If the query requests listing, showing, fetching, or details → set `wants_details: true` and `wants_count: false`.  
        - If the query requests counts, totals, or summaries → set `wants_count: true` and `wants_details: false`.  
        - Only one of `wants_details` or `wants_count` may be true at a time.  
        - If unspecified, default to `wants_details: true` and `wants_count: false`.  
        - Always match the schema structure, leaving non-specified fields empty, null, or default.  
        - Output must always be valid JSON only.

        User query: "{query}"
        """

        response = self.llm.invoke(prompt) # assumes llm returns a text string
        
        if not hasattr(response, "content"):
            raise ValueError(f"Unexpected LLM response format. Expected an object with a 'content' attribute, but got: {type(response)}")
        
        response_text = response.content
        response_text = response_text.strip()
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[len("json"):].strip()

        try:
            parsed = json.loads(response_text)
        except json.JSONDecodeError:
            raise ValueError(f"LLM returned invalid JSON: {response_text}")

        return QueryIntent(**parsed)

# class NaturalLanguageParser:
#     """Parses natural language queries to extract intent"""

#     def __init__(self):
#         # Entity keywords mapped to collections
#         self.entity_keywords = {
#             'workItem': ['work item', 'task', 'bug', 'issue', 'story', 'ticket'],
#             'project': ['project', 'initiative', 'program'],
#             'cycle': ['cycle', 'sprint', 'iteration', 'phase'],
#             'members': ['member', 'user', 'person', 'team member', 'developer'],
#             'page': ['page', 'document', 'wiki', 'documentation'],
#             'module': ['module', 'component', 'feature'],
#             'projectState': ['state', 'status', 'workflow', 'stage']
#         }

#         # Action keywords
#         self.action_keywords = {
#             'find': ['find', 'get', 'show', 'list', 'display'],
#             'count': ['count', 'how many', 'number of', 'total'],
#             'filter': ['with', 'having', 'where', 'that have'],
#             'group': ['grouped by', 'by', 'per'],
#             'sort': ['sorted by', 'order by', 'ordered'],
#             'aggregate': ['sum', 'average', 'total', 'summary']
#         }

#         # Work item status keywords (generic, not project/cycle)
#         self.status_keywords = {
#             'TODO': ['todo', 'to do', 'pending', 'open'],
#             'COMPLETED': ['completed', 'done', 'finished', 'closed']
#         }

#         # Project status keywords aligned to PROJECT_STATUS enum
#         self.project_status_keywords = {
#             'NOT_STARTED': ['not started', 'new', 'not begun', 'yet to start'],
#             'STARTED': ['started', 'has started', 'underway'],
#             'COMPLETED': ['completed', 'finished', 'done'],
#             'OVERDUE': ['overdue', 'late', 'past due']
#         }

#         # Cycle status keywords aligned to CYCLE_STATUS enum
#         self.cycle_status_keywords = {
#             'ACTIVE': ['active', 'in progress', 'ongoing', 'running'],
#             'UPCOMING': ['upcoming', 'future', 'planned', 'next'],
#             'COMPLETED': ['completed', 'finished', 'done']
#         }

#         # Page visibility keywords aligned to PageVisibility enum
#         self.page_visibility_keywords = {
#             'PUBLIC': ['public', 'visible to all'],
#             'PRIVATE': ['private', 'restricted'],
#             'ARCHIVED': ['archived', 'archive']
#         }

#     def parse_query(self, query: str) -> QueryIntent:
#         """Parse natural language query into structured intent"""
#         query_lower = query.lower().strip()

#         # Extract primary entity
#         primary_entity = self._extract_primary_entity(query_lower)

#         # Extract target entities (related collections to include)
#         target_entities = self._extract_target_entities(query_lower, primary_entity)

#         # Extract filters
#         filters = self._extract_filters(query_lower)

#         # Extract aggregations
#         aggregations = self._extract_aggregations(query_lower)

#         # Extract grouping targets (e.g., grouped by cycle)
#         group_by = self._extract_group_by(query_lower)

#         # Extract projections
#         projections = self._extract_projections(query_lower)

#         # Extract sorting
#         sort_order = self._extract_sorting(query_lower)

#         # Extract limit
#         limit = self._extract_limit(query_lower)

#         # Determine intent for details vs count
#         wants_count = ('count' in aggregations)
#         wants_details = self._detect_detail_intent(query_lower, projections, wants_count)

#         # If both are requested, prefer details per requirement
#         if wants_details and wants_count:
#             aggregations = [a for a in aggregations if a != 'count']
#             wants_count = False

#         return QueryIntent(
#             primary_entity=primary_entity,
#             target_entities=target_entities,
#             filters=filters,
#             aggregations=aggregations,
#             group_by=group_by,
#             projections=projections,
#             sort_order=sort_order,
#             limit=limit,
#             wants_details=wants_details,
#             wants_count=wants_count
#         )

#     def _extract_primary_entity(self, query: str) -> str:
#         """Extract the primary entity from the query"""
#         for collection, keywords in self.entity_keywords.items():
#             for keyword in keywords:
#                 if keyword in query:
#                     return collection
#         return "project"  # Default fallback

#     def _extract_target_entities(self, query: str, primary_entity: str) -> List[str]:
#         """Extract related entities to include in the query"""
#         target_entities = []

#         # Look for relationship indicators
#         relationship_indicators = {
#             # generic
#             'workItems': ['work items', 'tasks', 'bugs', 'issues'],
#             'cycles': ['cycles', 'sprints', 'iterations'],
#             'pages': ['pages', 'documentation', 'docs'],
#             'modules': ['modules', 'components', 'features'],
#             'states': ['states', 'status', 'workflow'],
#             # workItem relations
#             'assignee': ['assignee', 'assigned to', 'assigned', 'owner', 'owned by'],
#             'project': ['project'],
#             'cycle': ['cycle', 'sprint'],
#             'module': ['module', 'component', 'feature'],
#             'stateMaster': ['state', 'workflow']
#         }

#         for relation, keywords in relationship_indicators.items():
#             for keyword in keywords:
#                 if keyword in query and relation in REL.get(primary_entity, {}):
#                     target_entities.append(relation)
#                     break

#         return target_entities

#     def _extract_filters(self, query: str) -> Dict[str, Any]:
#         """Extract filter conditions from the query"""
#         filters = {}

#         # Status filters
#         for status, keywords in self.status_keywords.items():
#             for keyword in keywords:
#                 if keyword in query:
#                     filters['status'] = status
#                     break

#         # Priority filters aligned to PRIORITY enum
#         priority_keywords = {
#             'URGENT': ['urgent', 'critical', 'asap', 'immediately'],
#             'HIGH': ['high', 'important', 'severe'],
#             'MEDIUM': ['medium', 'normal'],
#             'LOW': ['low', 'minor', 'low priority'],
#             'NONE': ['none', 'no priority', 'unprioritized']
#         }
#         for priority, keywords in priority_keywords.items():
#             if any(keyword in query for keyword in keywords):
#                 filters['priority'] = priority
#                 break

#         # Project status filters
#         for status, keywords in self.project_status_keywords.items():
#             if any(keyword in query for keyword in keywords):
#                 filters['project_status'] = status
#                 break

#         # Cycle status filters
#         for status, keywords in self.cycle_status_keywords.items():
#             if any(keyword in query for keyword in keywords):
#                 filters['cycle_status'] = status
#                 break

#         # Page visibility filters
#         for visibility, keywords in self.page_visibility_keywords.items():
#             if any(keyword in query for keyword in keywords):
#                 filters['page_visibility'] = visibility
#                 break

#         # Project name filters - support multiple phrasings
#         project_match1 = re.search(r'project\s+["\']([^"\']+)["\']', query)
#         project_match2 = re.search(r'["\']([^"\']+)["\']\s+project', query)
#         project_match3 = re.search(r'in\s+(?:the\s+)?([a-z0-9 _\-]+)\s+project', query)
#         if project_match1:
#             filters['project_name'] = project_match1.group(1).strip()
#         elif project_match2:
#             filters['project_name'] = project_match2.group(1).strip()
#         elif project_match3:
#             filters['project_name'] = project_match3.group(1).strip()

#         # Cycle name filters
#         cycle_match = re.search(r'cycle\s+["\']([^"\']+)["\']', query)
#         if cycle_match:
#             filters['cycle_title'] = cycle_match.group(1)

#         # Assignee name filters (e.g., "assigned to Aditya Sharma")
#         assignee_match = re.search(r'assigned to\s+([A-Za-z][\w .\-]+?)(?=(\s+(?:in|on|for|within|of|project|cycle|grouped|group|by)\b|[\.,]|$))', query)
#         if assignee_match:
#             filters['assignee_name'] = assignee_match.group(1).strip()

#         # Module name filters (e.g., "CRM module", "API module")
#         module_match = re.search(r'(\w+)\s+module', query)
#         if module_match:
#             filters['module_name'] = module_match.group(1)

#         return filters

#     def _extract_group_by(self, query: str) -> List[str]:
#         """Extract grouping targets from phrases like 'grouped by cycle' or 'group by project, cycle'."""
#         group_by: List[str] = []
#         raw = None
#         m = re.search(r'group(?:ed)? by\s+([a-zA-Z][a-zA-Z .,_\-]+)', query)
#         if m:
#             raw = m.group(1)
#         elif 'group' in query:
#             # Fallback: try ' by <term>' after a 'group' mention
#             m2 = re.search(r' by\s+([a-zA-Z][a-zA-Z .,_\-]+)', query)
#             if m2:
#                 raw = m2.group(1)
#         if not raw:
#             return group_by

#         parts = re.split(r'(?:,| and | & )', raw)
#         for p in parts:
#             token = p.strip().lower()
#             token = re.sub(r'[\.,;:!?].*$', '', token).strip()
#             mapped = None
#             if token.startswith('cycle'):
#                 mapped = 'cycle'
#             elif token.startswith('project'):
#                 mapped = 'project'
#             elif token.startswith('assignee') or token.startswith('owner'):
#                 mapped = 'assignee'
#             elif token.startswith('status') or token.startswith('state'):
#                 mapped = 'status'
#             elif token.startswith('priority'):
#                 mapped = 'priority'
#             elif token.startswith('module'):
#                 mapped = 'module'
#             if mapped and mapped not in group_by:
#                 group_by.append(mapped)
#         return group_by

#     def _extract_aggregations(self, query: str) -> List[str]:
#         """Extract aggregation operations"""
#         aggregations = []

#         if any(word in query for word in ['count', 'how many', 'number of', 'total']):
#             aggregations.append('count')

#         if any(word in query for word in ['group', 'grouped by', 'by']):
#             aggregations.append('group')

#         if any(word in query for word in ['summary', 'overview', 'breakdown']):
#             aggregations.append('summary')

#         return aggregations

#     def _extract_projections(self, query: str) -> List[str]:
#         """Extract fields to project"""
#         projections = []

#         # Common field keywords
#         field_keywords = {
#             'title': ['title', 'name'],
#             'status': ['status', 'state'],
#             'priority': ['priority', 'importance'],
#             'assignee': ['assignee', 'assigned to', 'owner'],
#             'created': ['created', 'date', 'when'],
#             'project': ['project', 'project name'],
#             'cycle': ['cycle', 'sprint']
#         }

#         for field, keywords in field_keywords.items():
#             for keyword in keywords:
#                 if keyword in query:
#                     projections.append(field)
#                     break

#         return projections[:5] if projections else []  # Limit to 5 fields

#     def _extract_sorting(self, query: str) -> Optional[Dict[str, int]]:
#         """Extract sorting information"""
#         if 'sort' in query or 'order' in query:
#             if 'date' in query or 'created' in query:
#                 return {'createdTimeStamp': -1}
#             elif 'priority' in query:
#                 return {'priority': -1}
#             elif 'status' in query:
#                 return {'status': 1}
#         return None

#     def _extract_limit(self, query: str) -> Optional[int]:
#         """Extract result limit"""
#         limit_match = re.search(r'(?:show|list|get)\s+(\d+)', query)
#         if limit_match:
#             return int(limit_match.group(1))
#         return 20  # Default limit

#     def _detect_detail_intent(self, query: str, projections: List[str], wants_count: bool) -> bool:
#         """Detect whether the user wants detailed records rather than just counts.

#         Rules:
#         - Explicit phrases like 'details', 'exact details' => True
#         - If user specifies field-like words (projections extracted) => True
#         - If the query is a numeric question ('how many', 'number of', 'count of') => False unless 'details' also present
#         - Generic list verbs ('list', 'show', 'get', 'display') => True only when not explicitly a count question
#         """
#         if 'exact details' in query or 'details' in query:
#             return True
#         count_markers = any(kw in query for kw in ['how many', 'number of', 'count of'])
#         if count_markers and not ('details' in query):
#             return False
#         if projections:
#             return True
#         list_markers = any(kw in query for kw in ['list', 'show', 'display', 'get', 'which', 'what are'])
#         if list_markers and not wants_count:
#             return True
#         return False


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


class LLMResponseFormatter:
    """Formats a clean query result into a string suitable for an LLM."""

    def __init__(self):
        """Initializes the formatter with a map for pretty field names."""
        # This map is crucial for user-friendly output.
        self.field_name_map = {
            # Project Fields
            "projectDisplayId": "Project ID",
            "name": "Name",
            "business.name": "Business",
            "lead.name": "Lead",
            "status": "Status",
            "access": "Access",
            "createdTimeStamp": "Created Date",
            "description": "Description",
            "leadMail": "Lead Email",
            "displayBugNo": "Bug ID",
            "title": "Title",
            "priority": "Priority",
            "assignee_name": "Assignee",
        }

    def _get_nested_value(self, doc: Dict, key: str) -> Any:
        """Safely retrieves a value from a nested dictionary using dot notation."""
        keys = key.split('.')
        value = doc
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return None
        return value

    def _format_value(self, value: Any) -> str:
        """Helper function to format individual values."""
        if value is None:
            return "N/A"
        # Handle MongoDB date objects
        if isinstance(value, dict) and '$date' in value:
            try:
                return value['$date'].split('T')[0]  # Return YYYY-MM-DD
            except:
                return str(value) # Fallback
        # Handle nested objects by extracting their 'name' if available
        if isinstance(value, dict) and 'name' in value:
            return str(value['name'])
        return str(value)

    def _format_as_detailed_list(self, result: List[Dict], entity: str) -> str:
        """Formats the result as a detailed, human-readable list (card view)."""
        output_lines = [f"Here are the details for the {entity}(s) you requested:"]
        for i, doc in enumerate(result):
            output_lines.append(f"\n--- **Record {i+1}** ---")
            for key, value in doc.items():
                if key.startswith('_'): continue # Skip internal fields like _id, _class
                
                display_key = self.field_name_map.get(key, key.replace('_', ' ').title())
                formatted_value = self._format_value(value)
                output_lines.append(f"**{display_key}:** {formatted_value}")
        return "\n".join(output_lines)

    def _format_as_table(self, result: List[Dict]) -> str:
        """Formats a list of results into a Markdown table for a summary view."""
        if not result: return "No records to display."

        # Define columns based on the most relevant fields for the entity
        # This should be adapted based on the entity type (project, bug, etc.)
        headers_to_check = ["projectDisplayId", "name", "business.name", "lead.name", "status", "createdTimeStamp"]
        doc_keys = result[0].keys()
        
        # Select headers that are actually present in the result
        headers = [h for h in headers_to_check if h.split('.')[0] in doc_keys]
        if not headers: # Fallback if no standard headers match
            headers = list(doc_keys)[:5] # Limit to first 5 keys

        pretty_headers = [self.field_name_map.get(h, h.title()) for h in headers]

        # Create Header and Separator
        header_line = "| " + " | ".join(pretty_headers) + " |"
        separator_line = "| " + " | ".join([":---"] * len(pretty_headers)) + " |"

        # Create Rows
        rows = []
        for doc in result:
            row_data = [self._format_value(self._get_nested_value(doc, h)) for h in headers]
            rows.append("| " + " | ".join(row_data) + " |")
            
        count = len(result)
        summary = f"Found {count} record(s). Here is a summary:"
        return "\n".join([summary, header_line, separator_line] + rows)

    def format_results(self, result: List[Dict[str, Any]], intent: Any) -> str:
        """
        Takes the clean query result and returns a polished, human-readable string.
        """
        if not result:
            return "No records found matching your query."

        # 1. Handle Count Intent
        if intent.wants_count:
            # Assumes count query returns a doc like {'total': 53}
            if isinstance(result[0], dict) and "total" in result[0]:
                count = result[0]["total"]
            else:
                count = len(result)
            return f"Found a total of {count} {intent.primary_entity}(s) matching the criteria."

        # 2. Handle Detailed View Intent
        if intent.wants_details:
            return self._format_as_detailed_list(result, intent.primary_entity)

        # 3. Default to Summary Table for multiple results
        if len(result) > 1:
            return self._format_as_table(result)
        
        # 4. Default to Detailed View for a single result
        if len(result) == 1:
            return self._format_as_detailed_list(result, intent.primary_entity)
            
        # This fallback should ideally never be reached
        return "Could not determine the best way to format the results."

class QueryPlanner:
    """Main query planner that orchestrates the entire process"""

    def __init__(self):
        self.parser = LLMNaturalLanguageParser(llm)
        self.generator = PipelineGenerator()
        self.formatter = LLMResponseFormatter()

    async def plan_and_execute(self, query: str) -> Dict[str, Any]:
        """Plan and execute a natural language query"""
        try:
            # Ensure MongoDB connection
            await mongodb_tools.connect()

            # Parse the query
            intent = self.parser.parse_query(query)

            # Generate the pipeline
            pipeline = self.generator.generate_pipeline(intent)

            # Execute the query
            db_result = await mongodb_tools.execute_tool("aggregate", {
                "database": DATABASE_NAME,
                "collection": intent.primary_entity,
                "pipeline": pipeline
            })
            parsed_result = db_result
            if isinstance(db_result, str):
                try:
                    parsed_result = json.loads(db_result)
                except json.JSONDecodeError:
                    return {
                        "success": True, "intent": intent.__dict__, "pipeline": pipeline,
                        "result": db_result
                    }
            elif isinstance(db_result, list) and db_result:
                if isinstance(db_result[0], str):
                    temp_list = []
                    for item_str in db_result:
                        try:
                            temp_list.append(json.loads(item_str))
                        except (json.JSONDecodeError, TypeError):
                            continue
                    parsed_result = temp_list
            # --- END: ROBUST parsing logic ---

            # Format the clean data into a string for the final response
            formatted_response = self.formatter.format_results(parsed_result, intent)

            # The tool expects the final, formatted string in a key named 'result'.
            return {
                "success": True,
                "intent": intent.__dict__,
                "pipeline": pipeline,
                "result": formatted_response,
                "debug_raw_data": db_result
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "query": query
            }
        #     return {
        #         "success": True,
        #         "intent": intent.__dict__,
        #         "pipeline": pipeline,
        #         "result": result
        #     }

        # except Exception as e:
        #     return {
        #         "success": False,
        #         "error": str(e),
        #         "query": query
        #     }

# Global instance
query_planner = QueryPlanner()

async def plan_and_execute_query(query: str) -> Dict[str, Any]:
    """Convenience function to plan and execute queries"""
    return await query_planner.plan_and_execute(query)
