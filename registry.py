#!/usr/bin/env python3
"""
PMS Registry - Central definitions for relationships, fields, and aliases
"""

from typing import Dict, List, Any, Set

# ---- Relation Registry (single source of truth for hops)
REL: Dict[str, Dict[str, dict]] = {
    # PROJECT is the hub
    "project": {
        "cycles": {
            "target": "cycle",
            "join": {"cycle.project._id": "project._id"},
            "defaults": {"status": "ACTIVE"}  # common filter you can auto-apply
        },
        "workItems": {
            "target": "workItem",
            "join": {"workItem.project._id": "project._id"}
        },
        "members": {
            "target": "members",
            "join": {"members.project._id": "project._id"}
        },
        "pages": {
            "target": "page",
            "join": {"page.project._id": "project._id"}
        },
        "modules": {
            "target": "module",
            "join": {"module.project._id": "project._id"}
        },
        "states": {
            "target": "projectState",
            "join": {"projectState.projectId": "project._id"}
        },
    },

    # CYCLE
    "cycle": {
        "pages": {       # pages link cycles via array
            "target": "page",
            "expr": "cycle._id in page.linkedCycle"
        },
        "workItems": {
            "target": "workItem",
            "join": {"workItem.cycleId": "cycle._id"}
        },
        "project": {
            "target": "project",
            # target collection field on left, local/source field on right
            "join": {"project._id": "cycle.project._id"}
        }
    },

    # WORK ITEM
    "workItem": {
        "project": {
            "target": "project",
            # target collection field on left, local/source field on right
            "join": {"project._id": "workItem.project._id"}
        },
        "stateMaster": {  # map by state._id OR by name fallback
            "target": "projectState",
            "expr": "workItem.state._id in projectState.subStates._id OR name-eq"
        },
        "cycle": {
            "target": "cycle",
            "join": {"cycle._id": "workItem.cycleId"}
        },
        "module": {
            "target": "module",
            "join": {"module._id": "workItem.moduleId"}
        },
        "assignee": {
            "target": "members",
            "join": {"members._id": "workItem.assignee._id"}
        },
        "createdBy": {
            "target": "members",
            "join": {"members._id": "workItem.createdBy._id"}
        }
    },

    # MEMBERS
    "members": {
        "project": {
            "target": "project",
            "join": {"project._id": "members.project._id"}
        }
    },

    # PAGE
    "page": {
        "project": {
            "target": "project",
            "join": {"project._id": "page.project._id"}
        },
        "author": {
            "target": "members",
            "join": {"members._id": "page.createdBy._id"}  # adjust if your members key differs
        },
        "cycles": {
            "target": "cycle",
            "expr": "cycle._id in page.linkedCycle"
        },
        "modules": {
            "target": "module",
            "expr": "module._id in page.linkedModule"
        }
    },

    # MODULE
    "module": {
        "project": {
            "target": "project",
            "join": {"project._id": "module.project._id"}
        },
        "workItems": {
            "target": "workItem",
            "join": {"workItem.moduleId": "module._id"}
        },
        "pages": {
            "target": "page",
            "expr": "module._id in page.linkedModule"
        },
        "assignee": {
            "target": "members",
            "join": {"members._id": "module.assignee._id"}
        }
    },
}

# ---- Collections (one source of truth)
Collection = str  # Simplified for tool usage

# ---- Allow-listed fields (restrict what the LLM can query/sort/project)
ALLOWED_FIELDS: Dict[str, Set[str]] = {
    "project": {
        "_id", "name", "projectDisplayId", "status", "isActive", "isArchived", "createdTimeStamp"
    },
    "cycle": {
        "_id", "title", "status", "startDate", "endDate", "project._id"
    },
    "workItem": {
        "_id", "displayBugNo", "title", "status", "priority",
        "project._id", "project.name",
        "state._id", "state.name", "stateMaster.name",
        "createdTimeStamp",
        "createdBy._id",
        # if/when you persist these, just leave them here:
        "moduleId", "cycleId", "assignee", "assignee._id"
    },
    "members": {
        "_id", "name", "email", "role", "joiningDate", "project._id"
    },
    "page": {
        "_id", "title", "visibility", "project._id",
        "linkedCycle", "linkedModule",           # arrays of IDs
        "createdBy._id", "createdAt"
    },
    "projectState": {
        "_id", "projectId", "name",
        "subStates._id", "subStates.name", "subStates.order"
    },
    "module": {
        "_id", "title", "description", "isFavourite",
        "project._id", "business._id", "assignee",
        "createdTimeStamp"
    },
}

# ---- Optional field aliases (normalize synonyms / UI names)
ALIASES: Dict[str, Dict[str, str]] = {
    "project": {"id": "_id", "displayId": "projectDisplayId"},
    "workItem": {"bug": "displayBugNo", "stateName": "stateMaster.name"},
    "members": {"memberId": "_id"},
    "module": {},
    "page": {},
    "cycle": {},
    "projectState": {},
}

def resolve_field_alias(collection: str, field: str) -> str:
    """Resolve field aliases to actual field names."""
    if collection in ALIASES and field in ALIASES[collection]:
        return ALIASES[collection][field]
    return field

def validate_fields(collection: str, fields: List[str]) -> List[str]:
    """Validate and filter fields against allowed fields for a collection."""
    if collection not in ALLOWED_FIELDS:
        return []
    allowed = ALLOWED_FIELDS[collection]
    return [field for field in fields if resolve_field_alias(collection, field) in allowed]

def build_lookup_stage(from_collection: str, relationship: Dict[str, Any], current_collection: str, additional_filters: Dict[str, Any] = None) -> Dict[str, Any]:
    """Build MongoDB $lookup stage based on relationship definition.

    Enhancements:
    - Supports field-to-field joins with $expr
    - Handles array-joins using $in when appropriate
    - Parses simple "X in Y" and "X = Y" expressions from relationship["expr"]
    - Keeps local field paths relative to current document context
    """
    def _is_array_like(path: str) -> bool:
        candidates = [
            "assignee", "assignee._id", "linkedCycle", "linkedModule",
            "assignees", "members", "labels", "subStates._id"
        ]
        return any(c in path for c in candidates)

    lookup_stage: Dict[str, Any] = {
        "$lookup": {
            "from": from_collection,
            "let": {},
            "pipeline": [],
            "as": relationship.get("target", from_collection)
        }
    }

    if "join" in relationship:
        # Simple join relationship using field mappings
        join_conditions = relationship["join"]
        for foreign_field, local_field in join_conditions.items():
            foreign_parts = foreign_field.split(".")
            local_parts = local_field.split(".")
            if len(foreign_parts) > 1 and len(local_parts) > 1:
                foreign_collection = foreign_parts[0]
                foreign_field_name = ".".join(foreign_parts[1:])

                # Keep the local path relative to current document unless it's prefixed with current_collection
                if local_parts[0] == current_collection:
                    local_field_path = ".".join(local_parts[1:])
                else:
                    local_field_path = ".".join(local_parts)

                var_name = f"local_{local_field_path.replace('.', '_')}"
                lookup_stage["$lookup"]["let"][var_name] = f"${local_field_path}"

                # Choose $eq or $in depending on whether local looks like an array
                if _is_array_like(local_field_path):
                    match_condition = {
                        "$expr": {"$in": [f"${foreign_field_name}", f"$${var_name}"]}
                    }
                else:
                    match_condition = {
                        "$expr": {"$eq": [f"$${var_name}", f"${foreign_field_name}"]}
                    }
                lookup_stage["$lookup"]["pipeline"].append({"$match": match_condition})

    elif "expr" in relationship:
        # Parse simple expressions like "A.B in C.D" or "A.B = C.D"
        expr_str: str = relationship["expr"].strip()
        # Normalize operators
        normalized = expr_str.replace("==", "=")
        op = "in" if " in " in normalized else "=" if "=" in normalized else None
        if op is not None:
            left, right = [p.strip() for p in normalized.split(" in " if op == "in" else "=")]
            # left refers to one side (could be local or foreign), right the other
            # Determine which side is remote (from_collection) and which is local (current_collection)
            left_prefix = left.split(".")[0]
            right_prefix = right.split(".")[0]

            # Build paths without their collection prefixes when referencing remote
            def strip_prefix(path: str, prefix: str) -> str:
                parts = path.split(".")
                if parts[0] == prefix:
                    return ".".join(parts[1:])
                return path

            # Identify local and remote sides
            if left_prefix == from_collection:
                remote_field = strip_prefix(left, from_collection)
                # right should be from current document
                if right_prefix == current_collection:
                    local_field_path = strip_prefix(right, current_collection)
                else:
                    local_field_path = right  # already relative to current doc
                var_name = f"local_{local_field_path.replace('.', '_')}"
                lookup_stage["$lookup"]["let"][var_name] = f"${local_field_path}"

                if op == "in":
                    # remote scalar IN local array
                    match_condition = {"$expr": {"$in": [f"${remote_field}", f"$${var_name}"]}}
                else:
                    # equality
                    match_condition = {"$expr": {"$eq": [f"${remote_field}", f"$${var_name}"]}}
                lookup_stage["$lookup"]["pipeline"].append({"$match": match_condition})

            else:
                # Treat left as local, right as remote
                if left_prefix == current_collection:
                    local_field_path = strip_prefix(left, current_collection)
                else:
                    local_field_path = left
                var_name = f"local_{local_field_path.replace('.', '_')}"
                lookup_stage["$lookup"]["let"][var_name] = f"${local_field_path}"
                remote_field = strip_prefix(right, from_collection)

                if op == "in":
                    # local scalar IN remote array
                    match_condition = {"$expr": {"$in": [f"$${var_name}", f"${remote_field}"]}}
                else:
                    match_condition = {"$expr": {"$eq": [f"$${var_name}", f"${remote_field}"]}}
                lookup_stage["$lookup"]["pipeline"].append({"$match": match_condition})

        # Special-case: optional fallback noted in expr string
        if "name-eq" in expr_str.lower():
            # Heuristic: attempt to match by name fields as a fallback
            # local: try state.name, remote: try name or subStates.name
            or_conditions = []
            # local state.name
            lookup_stage["$lookup"]["let"]["local_state_name"] = "$state.name"
            or_conditions.append({"$expr": {"$eq": ["$name", "$$local_state_name"]}})
            or_conditions.append({"$expr": {"$in": ["$$local_state_name", "$subStates.name"]}})
            lookup_stage["$lookup"]["pipeline"].append({"$match": {"$or": or_conditions}})

    # Add additional filters if provided
    if additional_filters:
        lookup_stage["$lookup"]["pipeline"].append({"$match": additional_filters})

    # Add defaults if specified
    if "defaults" in relationship:
        lookup_stage["$lookup"]["pipeline"].append({"$match": relationship["defaults"]})

    return lookup_stage
