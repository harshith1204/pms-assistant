#!/usr/bin/env python3
"""
Intelligent Query Planner for PMS System
Handles natural language queries and generates optimal MongoDB aggregation pipelines
based on the relationship registry
"""

import json
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

class NaturalLanguageParser:
    def parse(self, query: str) -> "QueryIntent":
        """Minimal heuristic fallback when LLM intent parsing fails.

        Defaults to listing workItems, attempts to detect simple group-by and count prompts.
        """
        ql = (query or "").lower()
        # Detect group-by tokens in simple phrasing
        group_tokens: List[str] = []
        for token in ["assignee", "project", "cycle", "status", "priority", "module"]:
            if f"group by {token}" in ql or f"grouped by {token}" in ql:
                group_tokens.append(token)

        # Detect count requests
        wants_count = ("count" in ql) or ("how many" in ql)
        aggregations: List[str] = ["group"] if group_tokens else (["count"] if wants_count else [])

        return QueryIntent(
            primary_entity="workItem",
            target_entities=[],
            filters={},
            aggregations=aggregations,
            group_by=group_tokens,
            projections=[],
            sort_order=None,
            limit=20,
            # For grouped results, default to no details unless explicitly asked; here we assume details for list
            wants_details=(not aggregations) or (aggregations == ["group"]),
            wants_count=(aggregations == ["count"]),
        )

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
            reasoning=False,
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
            return self._sanitize_intent(data, query)
        except Exception:
            return None

    def _sanitize_intent(self, data: Dict[str, Any], original_query: str = "") -> QueryIntent:
        # Primary entity (prefer workItem; flip to workItem if cross-entity grouping is requested)
        requested_primary = (data.get("primary_entity") or "").strip()
        primary = requested_primary if requested_primary in self.entities else "workItem"

        # Allowed relations for primary
        allowed_rels = set(self.entity_relations.get(primary, []))
        target_entities: List[str] = []
        for rel in (data.get("target_entities") or []):
            if isinstance(rel, str) and rel.split(".")[0] in allowed_rels:
                target_entities.append(rel)

        # Filters: keep only known keys and drop placeholders
        raw_filters = data.get("filters") or {}
        known_filter_keys = {
            "status", "priority", "project_status", "cycle_status", "page_visibility",
            "project_name", "cycle_title", "assignee_name", "module_name"
        }
        filters: Dict[str, Any] = {}
        for k, v in raw_filters.items():
            if k in known_filter_keys and isinstance(v, (str, int)) and not self._is_placeholder(v):
                # keep exact enums only for enum fields
                if k in {"status", "project_status", "cycle_status", "page_visibility"} and isinstance(v, str):
                    if "?" in v or not v.isupper():
                        continue
                filters[k] = v

        # Aggregations
        allowed_aggs = {"count", "group", "summary"}
        aggregations = [a for a in (data.get("aggregations") or []) if a in allowed_aggs]

        # Group by tokens
        allowed_group = {"cycle", "project", "assignee", "status", "priority", "module"}
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

        # Details vs count (mutually exclusive) + heuristic for "how many"
        oq = (original_query or "").lower()
        wants_details_raw = data.get("wants_details")
        wants_count_raw = data.get("wants_count")
        wants_details = bool(wants_details_raw) if wants_details_raw is not None else False
        wants_count = bool(wants_count_raw) if wants_count_raw is not None else False
        wants_count = wants_count or ("how many" in oq)

        # If group_by present, details default to False unless explicitly requested
        if group_by and wants_details_raw is None:
            wants_details = False

        # Never have both; count wins if user explicitly asked
        if wants_details and wants_count:
            wants_details = False
        if wants_count and not group_by:
            aggregations = ["count"]

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
        pipeline: List[Dict[str, Any]] = []

        # Start with the primary collection
        collection = intent.primary_entity

        # Build sanitized filters once
        primary_filters = self._extract_primary_filters(intent.filters, collection) if intent.filters else {}
        secondary_filters = self._extract_secondary_filters(intent.filters) if intent.filters else {}

        # COUNT-ONLY: no group_by, no details → do not add lookups
        if (("count" in intent.aggregations) or intent.wants_count) and not intent.group_by and not intent.wants_details:
            if primary_filters:
                return [{"$match": primary_filters}, {"$count": "total"}]
            if not secondary_filters:
                return [{"$count": "total"}]
            # fall through only if secondary filters exist (rare for "how many …")

        # Add filters for the primary collection
        if primary_filters:
            pipeline.append({"$match": primary_filters})

        # Ensure lookups needed by secondary filters or grouping are included
        required_relations: Set[str] = set()
        # Filters → relations
        if intent.filters:
            if 'project_name' in intent.filters and 'project' in REL.get(collection, {}):
                required_relations.add('project')
            if 'cycle_title' in intent.filters and 'cycle' in REL.get(collection, {}):
                required_relations.add('cycle')
            if 'assignee_name' in intent.filters and 'assignee' in REL.get(collection, {}):
                required_relations.add('assignee')
            if 'module_name' in intent.filters and 'module' in REL.get(collection, {}):
                required_relations.add('module')

        # Group-by → relations
        for token in (intent.group_by or []):
            if token in REL.get(collection, {}):
                required_relations.add(token)
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
                    # If array relation, unwind the alias used in $lookup
                    is_many = bool(relationship.get("isArray") or relationship.get("many", False))
                    if is_many:
                        unwind_path = relationship.get("as") or relationship.get("alias") or relationship.get("target")
                        pipeline.append({
                            "$unwind": {"path": f"${unwind_path}", "preserveNullAndEmptyArrays": True}
                        })
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
            else:
                pipeline.append({"$sort": intent.sort_order})

        # Add projections after sorting so computed fields can be hidden
        if effective_projections and not intent.group_by:
            projection = self._generate_projection(effective_projections, intent.target_entities, intent.primary_entity)
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
        s: Dict[str, Any] = {}

        # Project name: allow both embedded project.name and joined alias projectDoc.name
        if 'project_name' in filters:
            s['$or'] = [
                {'project.name': {'$regex': filters['project_name'], '$options': 'i'}},
                {'projectDoc.name': {'$regex': filters['project_name'], '$options': 'i'}},
            ]

        # Assignee name via joined alias 'assignees'
        if 'assignee_name' in filters:
            s['assignees.name'] = {'$regex': filters['assignee_name'], '$options': 'i'}

        # Cycle title filter (applies to joined cycle)
        if 'cycle_title' in filters:
            s['cycle.title'] = {'$regex': filters['cycle_title'], '$options': 'i'}

        # Module name filter (applies to joined module)
        if 'module_name' in filters:
            s['module.title'] = {'$regex': filters['module_name'], '$options': 'i'}

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

        # After computing validated, if it's empty, fall back to a minimal safe set
        if not validated:
            minimal = ["title", "status", "priority", "createdTimeStamp"]
            validated = [f for f in minimal if f in allowed]
        return validated

    def _resolve_group_field(self, primary_entity: str, token: str) -> Optional[str]:
        """Map a grouping token to a concrete field path in the current pipeline."""
        mapping = {
            'workItem': {
                'cycle': 'cycle.title',
                'project': 'project.name',
                'assignee': 'assignees.name',  # joined alias for assignee relation (REL alias)
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
        self.generator = PipelineGenerator()
        self.llm_parser = LLMIntentParser()
        self.rule_parser = NaturalLanguageParser()

    async def plan_and_execute(self, query: str) -> Dict[str, Any]:
        """Plan and execute a natural language query"""
        try:
            # Ensure MongoDB connection
            await mongodb_tools.connect()

            # Parse intent via LLM (single source of truth)
            intent_source = "llm"
            intent: Optional[QueryIntent] = await self.llm_parser.parse(query)
            if not intent:
                # Fallback to rule-based parser
                intent = self.rule_parser.parse(query)
                intent_source = "rules"

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
