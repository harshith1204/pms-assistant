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

from registry import REL, ALLOWED_FIELDS, ALIASES, resolve_field_alias, validate_fields, build_lookup_stage
from constants import mongodb_tools, DATABASE_NAME

@dataclass
class QueryIntent:
    """Represents the parsed intent of a user query"""
    primary_entity: str  # Main collection/entity (e.g., "workItem", "project")
    target_entities: List[str]  # Related entities to include
    filters: Dict[str, Any]  # Filter conditions
    aggregations: List[str]  # Aggregation operations (count, group, etc.)
    group_by: List[str]  # Group-by tokens
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

        # Extract group-by tokens
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
        return "workItem"  # Default fallback prefers workItem for NL queries

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

        # Project name filters
        project_match = re.search(r'project\s+["\']([^"\']+)["\']', query)
        if project_match:
            filters['project_name'] = project_match.group(1)

        # Cycle name filters
        cycle_match = re.search(r'cycle\s+["\']([^"\']+)["\']', query)
        if cycle_match:
            filters['cycle_title'] = cycle_match.group(1)

        # Assignee name filters (e.g., "assigned to Aditya Sharma")
        assignee_match = re.search(r'assigned to\s+([a-zA-Z][\w .\-]+)', query)
        if assignee_match:
            filters['assignee_name'] = assignee_match.group(1).strip()

        # Module name filters (e.g., "CRM module", "API module")
        module_match = re.search(r'(\w+)\s+module', query)
        if module_match:
            filters['module_name'] = module_match.group(1)

        return filters

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

    def _extract_group_by(self, query: str) -> List[str]:
        """Extract group-by tokens from the query."""
        tokens: List[str] = []
        allowed = ["assignee", "project", "cycle", "status", "priority", "module"]
        for tok in allowed:
            if f"group by {tok}" in query or f"grouped by {tok}" in query or f"by {tok}" in query or f"per {tok}" in query:
                tokens.append(tok)
        # De-duplicate preserving order
        seen = set()
        ordered: List[str] = []
        for t in tokens:
            if t not in seen:
                seen.add(t)
                ordered.append(t)
        return ordered

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

        # Ensure lookups needed by secondary filters and group-by are included
        required_relations: Set[str] = set(intent.target_entities)
        if intent.filters:
            # If we will filter by joined fields, we must join those relations
            if 'project_name' in intent.filters and 'project' in REL.get(collection, {}):
                required_relations.add('project')
            if 'cycle_title' in intent.filters and 'cycle' in REL.get(collection, {}):
                required_relations.add('cycle')
            if 'assignee_name' in intent.filters and 'assignee' in REL.get(collection, {}):
                required_relations.add('assignee')
            if 'module_name' in intent.filters and 'module' in REL.get(collection, {}):
                required_relations.add('module')

        # Group-by implied relations
        for token in (intent.group_by or []):
            token_to_rel = {"project": "project", "cycle": "cycle", "assignee": "assignee", "module": "module"}
            rel = token_to_rel.get(token)
            if rel and rel in REL.get(collection, {}):
                required_relations.add(rel)

        # Add relationship lookups (supports multi-hop via dot syntax like project.states)
        for target_entity in sorted(required_relations):
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
                    # Always unwind when the relation is array-shaped
                    is_array_relation = bool(relationship.get("isArray") or relationship.get("many") or ("expr" in relationship and " in " in str(relationship.get("expr", "")).lower()))
                    if is_array_relation:
                        unwind_path = relationship.get("alias", relationship.get("target", hop))
                        pipeline.append({
                            "$unwind": {
                                "path": f"${unwind_path}",
                                "preserveNullAndEmptyArrays": True
                            }
                        })
                current_collection = relationship["target"]

        # Add secondary filters (on joined collections)
        if intent.filters:
            secondary_filters = self._extract_secondary_filters(intent.filters)
            if secondary_filters:
                pipeline.append({"$match": secondary_filters})

        # Add aggregations (skip count when details are requested)
        if intent.aggregations and not intent.wants_details:
            for agg in intent.aggregations:
                if agg == 'count':
                    pipeline.append({"$count": "total"})
                    return pipeline  # Count is terminal

        # Handle grouping pipelines
        if intent.group_by:
            # Map group tokens to document paths
            def map_group_field(token: str) -> str:
                mapping = {
                    "assignee": "members.name",  # via assignee -> members lookup
                    "project": "project.name",
                    "cycle": "cycle.title",
                    "module": "module.title",
                    "status": "status",
                    "priority": "priority",
                }
                return mapping.get(token, token)

            group_id: Dict[str, Any] = {}
            for tok in intent.group_by:
                field_path = map_group_field(tok)
                group_id[tok] = f"${field_path}"

            pipeline.append({
                "$group": {
                    "_id": group_id if len(group_id) > 1 else (list(group_id.values())[0] if group_id else None),
                    "count": {"$sum": 1}
                }
            })

            # Project flattened keys
            if len(group_id) > 1:
                project_spec: Dict[str, Any] = {tok: f"$_id.{tok}" for tok in group_id.keys()}
            else:
                # single key grouping; name it by token
                only_tok = intent.group_by[0]
                project_spec = {only_tok: "$_id"}
            project_spec["count"] = 1
            pipeline.append({"$project": project_spec})

            # Sorting for grouped results
            if intent.sort_order:
                sort_key = list(intent.sort_order.keys())[0]
                if sort_key in intent.group_by:
                    pipeline.append({"$sort": {sort_key: intent.sort_order[sort_key]}})
                else:
                    pipeline.append({"$sort": {"count": -1}})
            else:
                pipeline.append({"$sort": {"count": -1}})

            # Limit for grouped results
            if intent.limit:
                pipeline.append({"$limit": intent.limit})

            return pipeline

        # Add sorting (handle custom priority order), only for non-grouped
        added_priority_rank = False
        if intent.sort_order and not intent.group_by:
            # Determine if priority will be included in projections to avoid invisible-sort surprise
            will_project_priority = ('priority' in (intent.projections or []))
            if not will_project_priority and intent.wants_details and not intent.projections:
                # Check default projections for primary entity
                default_proj = self._get_default_projections(intent.primary_entity)
                will_project_priority = ('priority' in default_proj)

            if 'priority' in intent.sort_order and will_project_priority:
                added_priority_rank = True
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
            elif 'priority' not in intent.sort_order:
                pipeline.append({"$sort": intent.sort_order})

        # Determine projections for details
        effective_projections: List[str] = intent.projections
        if intent.wants_details and not effective_projections:
            effective_projections = self._get_default_projections(intent.primary_entity)

        # Add projections after sorting so computed fields can be hidden
        if effective_projections:
            projection = self._generate_projection(effective_projections, intent.target_entities, intent.primary_entity)
            # Ensure we exclude helper fields from output
            pipeline.append({"$project": projection})

        # Always unset helper if we added it
        if 'added_priority_rank' in locals() and added_priority_rank:
            pipeline.append({"$unset": "_priorityRank"})

        # Add limit (non-grouped)
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

        # Assignee name filter (applies to joined members via assignee relation)
        if 'assignee_name' in filters:
            # Prefer deterministic OR across known paths
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
        # Fallback to a minimal safe set if empty
        if not validated:
            minimal = ["title", "status", "priority", "createdTimeStamp"]
            validated = [f for f in minimal if f in allowed]
        return validated

class QueryPlanner:
    """Main query planner that orchestrates the entire process"""

    def __init__(self):
        self.parser = NaturalLanguageParser()
        self.entities: Set[str] = set(REL.keys())
        # Simple fallback parser if primary parsing fails (keeps system usable)
        self.rule_parser = self._build_rule_fallback()
        self.generator = PipelineGenerator()

    async def plan_and_execute(self, query: str) -> Dict[str, Any]:
        """Plan and execute a natural language query"""
        try:
            # Ensure MongoDB connection
            await mongodb_tools.connect()

            # Parse the query with fallback and sanitize
            intent = self._parse_with_fallback(query)

            # Sanitize and enforce deterministic behaviors
            intent = self._sanitize_intent(intent, query)

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
                "result": result
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "query": query
            }

    def _sanitize_intent(self, intent: QueryIntent, query: str) -> QueryIntent:
        """Apply deterministic fixes: primary entity, group enforcement, details vs count."""
        ql = query.lower()

        # Primary entity preference and lock to workItem for cross-entity grouping
        requested_primary = (intent.primary_entity or "").strip()
        primary = requested_primary if requested_primary in self.entities else "workItem"

        cross_tokens = {"assignee", "project", "cycle", "module"}
        if any(g in cross_tokens for g in (intent.group_by or [])):
            primary = "workItem"

        # Ensure grouping when group_by present
        if intent.group_by and "group" not in intent.aggregations:
            intent.aggregations = ["group"] + intent.aggregations

        # Count vs details: do not mix; count wins if asked; default details=false for groups unless explicit
        wants_details = bool(intent.wants_details)
        wants_count = bool(intent.wants_count)

        explicit_details = ("details" in ql) or ("exact details" in ql)
        if intent.group_by and not explicit_details:
            wants_details = False
        if wants_details and wants_count:
            wants_details = False

        # Apply changes back to intent
        intent.primary_entity = primary
        intent.wants_details = wants_details
        intent.wants_count = wants_count
        return intent

    def _build_rule_fallback(self):
        class _RuleFallback:
            def parse(self_inner, query_str: str) -> QueryIntent:
                ql = query_str.lower()
                group_by: List[str] = []
                for token in ["assignee", "project", "cycle", "status", "priority", "module"]:
                    if f"group by {token}" in ql:
                        group_by.append(token)
                aggregations = ["group"] if group_by else (["count"] if ("count" in ql or "how many" in ql) else [])
                return QueryIntent(
                    primary_entity="workItem",
                    target_entities=[],
                    filters={},
                    aggregations=aggregations,
                    group_by=group_by,
                    projections=[],
                    sort_order=None,
                    limit=20,
                    wants_details=(not aggregations) or (aggregations == ["group"]),
                    wants_count=(aggregations == ["count"]),
                )

        return _RuleFallback()

    def _parse_with_fallback(self, query: str) -> QueryIntent:
        try:
            intent = self.parser.parse_query(query)
        except Exception:
            intent = None
        if not intent or not getattr(intent, 'primary_entity', None):
            intent = self.rule_parser.parse(query)
        return intent

# Global instance
query_planner = QueryPlanner()

async def plan_and_execute_query(query: str) -> Dict[str, Any]:
    """Convenience function to plan and execute queries"""
    return await query_planner.plan_and_execute(query)
