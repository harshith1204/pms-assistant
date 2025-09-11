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
    projections: List[str]  # Fields to return
    sort_order: Optional[Dict[str, int]]  # Sort specification
    limit: Optional[int]  # Result limit

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

        # Status keywords
        self.status_keywords = {
            'TODO': ['todo', 'to do', 'pending', 'open'],
            'IN_PROGRESS': ['in progress', 'working', 'active', 'ongoing'],
            'COMPLETED': ['completed', 'done', 'finished', 'closed'],
            'UPCOMING': ['upcoming', 'future', 'planned', 'next']
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

        # Extract projections
        projections = self._extract_projections(query_lower)

        # Extract sorting
        sort_order = self._extract_sorting(query_lower)

        # Extract limit
        limit = self._extract_limit(query_lower)

        return QueryIntent(
            primary_entity=primary_entity,
            target_entities=target_entities,
            filters=filters,
            aggregations=aggregations,
            projections=projections,
            sort_order=sort_order,
            limit=limit
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

        # Priority filters
        priority_keywords = {
            'HIGH': ['high', 'urgent', 'critical'],
            'MEDIUM': ['medium', 'normal'],
            'LOW': ['low', 'minor']
        }
        for priority, keywords in priority_keywords.items():
            for keyword in keywords:
                if keyword in query:
                    filters['priority'] = priority
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

        # Ensure lookups needed by secondary filters are included
        required_relations: Set[str] = set(intent.target_entities)
        if intent.filters:
            # If we will filter by joined fields, we must join those relations
            if 'project_name' in intent.filters and 'project' in REL.get(collection, {}):
                required_relations.add('project')
            if 'cycle_title' in intent.filters and 'cycle' in REL.get(collection, {}):
                required_relations.add('cycle')
            if 'assignee_name' in intent.filters and 'assignee' in REL.get(collection, {}):
                required_relations.add('assignee')

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

        # Add aggregations
        if intent.aggregations:
            for agg in intent.aggregations:
                if agg == 'count':
                    pipeline.append({"$count": "total"})
                    return pipeline  # Count is terminal

        # Add projections
        if intent.projections:
            projection = self._generate_projection(intent.projections, intent.target_entities, intent.primary_entity)
            pipeline.append({"$project": projection})

        # Add sorting
        if intent.sort_order:
            pipeline.append({"$sort": intent.sort_order})

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
            if 'status' in filters:
                primary_filters['status'] = filters['status']

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
            secondary_filters['assignee.name'] = {'$regex': filters['assignee_name'], '$options': 'i'}

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

class QueryPlanner:
    """Main query planner that orchestrates the entire process"""

    def __init__(self):
        self.parser = NaturalLanguageParser()
        self.generator = PipelineGenerator()

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

# Global instance
query_planner = QueryPlanner()

async def plan_and_execute_query(query: str) -> Dict[str, Any]:
    """Convenience function to plan and execute queries"""
    return await query_planner.plan_and_execute(query)
