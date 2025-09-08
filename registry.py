#!/usr/bin/env python3
"""
PMS Registry — single source of truth for:
- collections and primary keys
- cross-collection edges (how to join)
- field aliases and allowed fields (safety)
- utilities to resolve aliases, validate fields, and build $lookup stages
"""

from __future__ import annotations
from typing import Dict, List, Any, Iterable

# ---------- Core entity metadata ----------

ENTITIES: Dict[str, Dict[str, Any]] = {
    "project": {
        "collection": "ProjectManagement.project",
        "pk": "_id",
        "aliases": {
            "projectId": "_id",
            "projectKey": "projectDisplayId",
            "projectName": "name",
            "businessId": "business._id",
            "createdAt": "createdTimeStamp",
            "updatedAt": "updatedTimeStamp",
            "status": "status",
        },
        "allowed_fields": [
            "_id","projectDisplayId","name","status","isActive","isArchived",
            "business._id","business.name","icon","imageUrl","access","favourite",
            "createdTimeStamp","updatedTimeStamp"
        ],
        "edges": {
            # Direct relationships
            "workItems":   {"to": "workItem", "local": "_id", "foreign": "project._id", "many": True},
            "cycles":      {"to": "cycle",    "local": "_id", "foreign": "project._id", "many": True},
            "modules":     {"to": "module",   "local": "_id", "foreign": "project._id", "many": True},
            "pages":       {"to": "page",     "local": "_id", "foreign": "project._id", "many": True},
            "members":     {"to": "members",  "local": "_id", "foreign": "project._id", "many": True},
            "projectState":{"to": "projectState", "local": "_id", "foreign": "projectId", "many": False},

            # Indirect relationships through workItems
            "workItemAssignees": {"to": "members", "via": "workItems", "path": "workItems.assignee._id", "foreign": "staff._id", "many": True},
            "workItemCreators":  {"to": "members", "via": "workItems", "path": "workItems.createdBy._id", "foreign": "staff._id", "many": True},

            # Indirect relationships through pages
            "pageCreators": {"to": "members", "via": "pages", "path": "pages.createdBy._id", "foreign": "staff._id", "many": True},

            # Business unit relationships
            "businessProjects": {"to": "project", "local": "business._id", "foreign": "business._id", "many": True, "self": True},
        },
        "query_patterns": {
            "team_workload": {"entities": ["members", "workItems"], "join_type": "lookup_workload"},
            "project_health": {"entities": ["workItems", "cycles"], "metrics": ["completion_rate", "velocity"]},
            "resource_allocation": {"entities": ["members", "workItems", "modules"], "group_by": "assignee"},
        },
    },

    "cycle": {
        "collection": "ProjectManagement.cycle",
        "pk": "_id",
        "aliases": {
            "cycleTitle":"title",
            "cycleStatus":"status",
            "start":"startDate",
            "end":"endDate",
            "createdAt":"createdTimeStamp",
            "updatedAt":"updatedTimeStamp",
        },
        "allowed_fields": [
            "_id","title","description","status","isDefault","startDate","endDate",
            "project._id","project.name","business._id","createdTimeStamp","updatedTimeStamp"
        ],
        "edges": {
            # Direct relationships
            "project": {"to": "project", "local": "project._id", "foreign": "_id", "many": False},

            # Work items in this cycle (if cycleId field exists)
            "workItems": {"to": "workItem", "local": "_id", "foreign": "cycleId", "many": True, "optional": True},

            # Pages linked to this cycle
            "linkedPages": {"to": "page", "via": "page", "path": "linkedCycle", "foreign": "_id", "many": True, "array_lookup": True},
        },
        "query_patterns": {
            "cycle_progress": {"entities": ["workItems"], "metrics": ["completion_rate", "burndown"]},
            "cycle_capacity": {"entities": ["members", "workItems"], "metrics": ["workload_distribution"]},
        },
    },

    "module": {
        "collection": "ProjectManagement.module",
        "pk": "_id",
        "aliases": {
            "moduleTitle":"title",
            "favourite":"isFavourite",
            "createdAt":"createdTimeStamp",
        },
        "allowed_fields": [
            "_id","title","description","isFavourite","assignee",
            "project._id","project.name","business._id","createdTimeStamp"
        ],
        "edges": {
            # Direct relationships
            "project": {"to": "project", "local": "project._id", "foreign": "_id", "many": False},

            # Work items in this module (if moduleId field exists)
            "workItems": {"to": "workItem", "local": "_id", "foreign": "moduleId", "many": True, "optional": True},

            # Pages linked to this module
            "linkedPages": {"to": "page", "via": "page", "path": "linkedModule", "foreign": "_id", "many": True, "array_lookup": True},

            # Module assignees (if assignee array exists)
            "assignees": {"to": "members", "via": "assignee", "foreign": "staff._id", "many": True, "array_lookup": True},
        },
        "query_patterns": {
            "module_progress": {"entities": ["workItems"], "metrics": ["completion_rate", "team_distribution"]},
            "module_capacity": {"entities": ["members", "workItems"], "metrics": ["workload_by_module"]},
        },
    },

    "members": {
        "collection": "ProjectManagement.members",
        "pk": "_id",
        "aliases": {
            "memberEmail":"email",
            "memberRole":"role",
            "joined":"joiningDate",
        },
        "allowed_fields": [
            "_id","name","email","role","type","joiningDate","memberId",
            "staff._id","staff.name","project._id","project.name"
        ],
        "edges": {
            # Direct relationships
            "project": {"to": "project", "local": "project._id", "foreign": "_id", "many": False},

            # Work items assigned to this member
            "assignedWorkItems": {"to": "workItem", "via": "workItem", "path": "assignee._id", "foreign": "staff._id", "many": True, "array_lookup": True},

            # Work items created by this member
            "createdWorkItems": {"to": "workItem", "local": "staff._id", "foreign": "createdBy._id", "many": True},

            # Pages created by this member
            "createdPages": {"to": "page", "local": "staff._id", "foreign": "createdBy._id", "many": True},

            # Modules assigned to this member
            "assignedModules": {"to": "module", "via": "module", "path": "assignee", "foreign": "staff._id", "many": True, "array_lookup": True},
        },
        "query_patterns": {
            "member_workload": {"entities": ["workItems", "pages"], "metrics": ["task_count", "productivity_score"]},
            "member_contribution": {"entities": ["workItems", "pages", "modules"], "metrics": ["creation_rate", "completion_rate"]},
        },
    },

    "page": {
        "collection": "ProjectManagement.page",
        "pk": "_id",
        "aliases": {
            "pageTitle":"title",
            "visibility":"visibility",
            "createdAt":"createdAt",
            "updatedAt":"updatedAt",
        },
        "allowed_fields": [
            "_id","title","visibility","linkedCycle","linkedModule","createdBy._id",
            "createdBy.name","createdAt","updatedAt","project._id","project.name",
            "business._id","business.name"
        ],
        "edges": {
            # Direct relationships
            "project": {"to": "project", "local": "project._id", "foreign": "_id", "many": False},
            "creator": {"to": "members", "local": "createdBy._id", "foreign": "staff._id", "many": False},

            # Linked entities (array fields)
            "linkedCycles": {"to": "cycle", "via": "cycle", "path": "linkedCycle", "foreign": "_id", "many": True, "array_lookup": True},
            "linkedModules": {"to": "module", "via": "module", "path": "linkedModule", "foreign": "_id", "many": True, "array_lookup": True},
        },
        "query_patterns": {
            "page_network": {"entities": ["cycles", "modules"], "metrics": ["link_density", "cross_references"]},
            "content_distribution": {"entities": ["members"], "metrics": ["creation_patterns", "collaboration_network"]},
        },
    },

    "projectState": {
        "collection": "ProjectManagement.projectState",
        "pk": "_id",
        "aliases": {
            "stateName":"name",
            "subStates":"subStates",
        },
        "allowed_fields": ["_id","name","subStates","projectId"],
        "edges": {
            # Direct relationships
            "project": {"to": "project", "local": "projectId", "foreign": "_id", "many": False},

            # Work items using these states
            "workItems": {"to": "workItem", "via": "workItem", "path": "state._id", "foreign": "_id", "many": True},
            "workItemsByStateMaster": {"to": "workItem", "via": "workItem", "path": "stateMaster._id", "foreign": "_id", "many": True},
        },
        "query_patterns": {
            "workflow_analysis": {"entities": ["workItems"], "metrics": ["state_distribution", "transition_rates"]},
            "process_efficiency": {"entities": ["workItems"], "metrics": ["cycle_time", "bottlenecks"]},
        },
    },

    "workItem": {
        "collection": "ProjectManagement.workItem",
        "pk": "_id",
        "aliases": {
            "ticket":"displayBugNo",
            "state":"state.name",
            "stateGroup":"stateMaster.name",
            "created":"createdTimeStamp",
            "updated":"updatedTimeStamp",
            "assignees":"assignee",
        },
        "allowed_fields": [
            "_id","displayBugNo","title","description","priority","status",
            "state.name","stateMaster.name","createdTimeStamp","updatedTimeStamp",
            "createdBy._id","createdBy.name","assignee","label",
            "project._id","project.name","business._id","business.name"
        ],
        "edges": {
            # Direct relationships
            "project": {"to": "project", "local": "project._id", "foreign": "_id", "many": False},
            "creator": {"to": "members", "local": "createdBy._id", "foreign": "staff._id", "many": False},
            "currentState": {"to": "projectState", "local": "state._id", "foreign": "_id", "many": False},
            "stateMaster": {"to": "projectState", "local": "stateMaster._id", "foreign": "_id", "many": False},

            # Optional traversals (may not exist in all data)
            "cycle":  {"to": "cycle", "local": "cycleId", "foreign": "_id", "many": False, "optional": True},
            "module": {"to": "module", "local": "moduleId", "foreign": "_id", "many": False, "optional": True},

            # Assignee relationships (array field)
            "assignedMembers": {"to": "members", "via": "assignee", "path": "assignee._id", "foreign": "staff._id", "many": True, "array_lookup": True},
        },
        "query_patterns": {
            "work_distribution": {"entities": ["members", "cycles", "modules"], "metrics": ["assignment_patterns", "workload_balance"]},
            "progress_tracking": {"entities": ["projectState"], "metrics": ["completion_velocity", "bottleneck_analysis"]},
            "team_collaboration": {"entities": ["members"], "metrics": ["cross_assignment", "knowledge_sharing"]},
        },
    },
}

# ---------- Flattened helpers ----------

ALIASES: Dict[str, str] = {}
ALLOWED_FIELDS: Dict[str, List[str]] = {}
for entity, meta in ENTITIES.items():
    for k, v in meta.get("aliases", {}).items():
        ALIASES[f"{entity}.{k}"] = f"{entity}.{v}"
        ALIASES[k] = v  # allow bare alias too
    ALLOWED_FIELDS[entity] = meta.get("allowed_fields", [])

def resolve_field_alias(entity: str, field: str) -> str:
    """
    Resolve user-facing alias to canonical field path for an entity.
    Accepts bare fields or fully-qualified 'entity.field' strings.
    """
    if "." in field:
        prefix, rest = field.split(".", 1)
        if prefix in ENTITIES:
            # already qualified; try alias map
            return ALIASES.get(field, field)
        # unqualified 'project.name' style but prefix isn't entity key
        # fall back to bare alias
    mapped = ALIASES.get(field)
    if mapped:
        return mapped
    return field

def validate_fields(entity: str, fields: Iterable[str]) -> List[str]:
    """
    Keep only whitelisted fields for projections/sorts to prevent accidental leakage.
    """
    allowed = set(ALLOWED_FIELDS.get(entity, []))
    result: List[str] = []
    for f in fields:
        f2 = resolve_field_alias(entity, f)
        if f2 in allowed:
            result.append(f2)
    return result

# ---------- $lookup builder ----------

def build_lookup_stage(source_entity: str, edge_name: str) -> Dict[str, Any]:
    """
    Build a robust $lookup stage to traverse a defined edge.
    Uses 'let' + $expr eq to match embedded references.
    """
    src = ENTITIES[source_entity]
    edge = src["edges"][edge_name]
    tgt = ENTITIES[edge["to"]]

    # Handle different edge types
    if "via" in edge and "path" in edge:
        # Complex lookup through another collection
        return build_complex_lookup_stage(source_entity, edge_name)
    elif "array_lookup" in edge and edge["array_lookup"]:
        # Array field lookup (e.g., assignee arrays, linkedCycle arrays)
        return build_array_lookup_stage(source_entity, edge_name)
    else:
        # Simple direct lookup
        return build_simple_lookup_stage(source_entity, edge_name)

def build_simple_lookup_stage(source_entity: str, edge_name: str) -> Dict[str, Any]:
    """Build a simple $lookup stage for direct field matching."""
    src = ENTITIES[source_entity]
    edge = src["edges"][edge_name]
    tgt = ENTITIES[edge["to"]]

    local_field = edge["local"]
    foreign_field = edge["foreign"]
    let_var = f"local_{edge_name}_key"

    local_expr = f"${local_field}"
    foreign_expr = f"${foreign_field}"

    return {
        "$lookup": {
            "from": tgt["collection"],
            "let": { let_var: local_expr },
            "pipeline": [
                { "$match": { "$expr": { "$eq": [ foreign_expr, f"$${let_var}" ] } } }
            ],
            "as": edge_name
        }
    }

def build_array_lookup_stage(source_entity: str, edge_name: str) -> Dict[str, Any]:
    """Build a $lookup stage for array field matching (e.g., assignee._id in array)."""
    src = ENTITIES[source_entity]
    edge = src["edges"][edge_name]
    tgt = ENTITIES[edge["to"]]

    local_field = edge["local"] if "local" in edge else edge["path"]
    foreign_field = edge["foreign"]
    let_var = f"local_{edge_name}_key"

    local_expr = f"${local_field}"
    foreign_expr = f"${foreign_field}"

    return {
        "$lookup": {
            "from": tgt["collection"],
            "let": { let_var: local_expr },
            "pipeline": [
                { "$match": { "$expr": { "$in": [ foreign_expr, f"$${let_var}" ] } } }
            ],
            "as": edge_name
        }
    }

def build_complex_lookup_stage(source_entity: str, edge_name: str) -> Dict[str, Any]:
    """Build a complex $lookup stage that goes through another collection."""
    src = ENTITIES[source_entity]
    edge = src["edges"][edge_name]

    # For complex lookups, we need to first lookup the intermediate collection
    # then lookup the final target collection
    via_entity = edge["via"]
    path_expr = edge["path"]
    foreign_field = edge["foreign"]

    let_var = f"local_{edge_name}_key"

    return {
        "$lookup": {
            "from": ENTITIES[via_entity]["collection"],
            "let": { let_var: f"${edge.get('local', '_id')}" },
            "pipeline": [
                # First match the relationship
                { "$match": { "$expr": { "$eq": [ f"${path_expr}", f"$${let_var}" ] } } },
                # Then lookup the target entity
                {
                    "$lookup": {
                        "from": ENTITIES[edge["to"]]["collection"],
                        "let": { "target_id": f"${foreign_field}" },
                        "pipeline": [
                            { "$match": { "$expr": { "$eq": [ "$_id", "$$target_id" ] } } }
                        ],
                        "as": f"{edge_name}_target"
                    }
                },
                # Unwind and replace root
                { "$unwind": f"${edge_name}_target" },
                { "$replaceRoot": { "newRoot": f"${edge_name}_target" } }
            ],
            "as": edge_name
        }
    }

def entity_collection(entity: str) -> str:
    return ENTITIES[entity]["collection"]

# ---------- Advanced Query Pattern Builders ----------

def build_multi_entity_pipeline(root_entity: str, target_entities: List[str], filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """
    Build a pipeline that joins multiple entities from a root entity.
    Useful for complex inter-related queries.
    """
    pipeline = []
    filters = filters or {}

    # Start with root entity filters
    root_filters = {k: v for k, v in filters.items() if not any(k.startswith(f"{entity}.") for entity in target_entities)}
    if root_filters:
        pipeline.append({"$match": root_filters})

    # Add lookups for each target entity
    for target_entity in target_entities:
        if target_entity in ENTITIES[root_entity]["edges"]:
            lookup_stage = build_lookup_stage(root_entity, target_entity)
            pipeline.append(lookup_stage)

            # Handle unwinding based on relationship type
            edge = ENTITIES[root_entity]["edges"][target_entity]
            if not edge.get("many", True):
                pipeline.append({"$unwind": {"path": f"${target_entity}", "preserveNullAndEmptyArrays": True}})

    # Apply cross-entity filters
    cross_filters = []
    for key, value in filters.items():
        for target_entity in target_entities:
            if key.startswith(f"{target_entity}."):
                field_path = key.replace(f"{target_entity}.", "")
                cross_filters.append({f"{target_entity}.{field_path}": value})

    if cross_filters:
        combined_filter = {"$and": cross_filters} if len(cross_filters) > 1 else cross_filters[0]
        pipeline.append({"$match": combined_filter})

    return pipeline

def get_query_pattern_suggestions(entity: str, intent_description: str) -> List[str]:
    """
    Suggest query patterns based on entity and intent description.
    Helps LLM choose appropriate pipeline building strategies.
    """
    suggestions = []
    patterns = ENTITIES.get(entity, {}).get("query_patterns", {})

    intent_lower = intent_description.lower()

    for pattern_name, pattern_info in patterns.items():
        entities = pattern_info.get("entities", [])
        metrics = pattern_info.get("metrics", [])

        # Check if intent matches pattern characteristics
        if any(metric in intent_lower for metric in metrics):
            suggestions.append(f"Use {pattern_name} pattern: joins {', '.join(entities)} for {', '.join(metrics)}")
        elif any(entity in intent_lower for entity in entities):
            suggestions.append(f"Consider {pattern_name} pattern for cross-entity analysis")

    return suggestions

def analyze_relationship_complexity(root_entity: str, target_entities: List[str]) -> Dict[str, Any]:
    """
    Analyze the complexity of relationships between entities to help optimize pipeline building.
    """
    analysis = {
        "direct_relationships": [],
        "indirect_relationships": [],
        "array_relationships": [],
        "complexity_score": 0,
        "recommended_strategy": "simple_lookup"
    }

    root_edges = ENTITIES.get(root_entity, {}).get("edges", {})

    for target in target_entities:
        if target in root_edges:
            edge = root_edges[target]

            if "via" in edge:
                analysis["indirect_relationships"].append(target)
                analysis["complexity_score"] += 3
            elif edge.get("array_lookup"):
                analysis["array_relationships"].append(target)
                analysis["complexity_score"] += 2
            else:
                analysis["direct_relationships"].append(target)
                analysis["complexity_score"] += 1

    # Determine strategy based on complexity
    if analysis["complexity_score"] >= 5:
        analysis["recommended_strategy"] = "multi_stage_aggregation"
    elif analysis["indirect_relationships"]:
        analysis["recommended_strategy"] = "nested_lookup"
    elif analysis["array_relationships"]:
        analysis["recommended_strategy"] = "array_lookup"

    return analysis

# ---------- Backward compatibility layer ----------

REL = {}
for entity_name, entity_meta in ENTITIES.items():
    REL[entity_name] = {}
    for edge_name, edge_meta in entity_meta.get("edges", {}).items():
        target_entity = edge_meta["to"]

        # Handle different edge types for backward compatibility
        if "local" in edge_meta and "foreign" in edge_meta:
            local_field = edge_meta["local"]
            foreign_field = edge_meta["foreign"]

            # Convert to old REL format
            REL[entity_name][edge_name] = {
                "target": target_entity,
                "join": {f"{target_entity}.{foreign_field}": f"{entity_name}.{local_field}"},
            }
        else:
            # For complex edges, provide a simplified version
            REL[entity_name][edge_name] = {
                "target": target_entity,
                "join": {f"{target_entity}._id": f"{entity_name}._id"},  # Default fallback
            }

# Also provide the old Collection variable for compatibility
Collection = str
