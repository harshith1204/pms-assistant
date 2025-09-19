#!/usr/bin/env python3
"""
PMS Registry - Central definitions for relationships, fields, and aliases
"""

from typing import Dict, List, Any, Set

# ---- Relation Registry (single source of truth for hops)
REL: Dict[str, Dict[str, dict]] = {
    "workItem": {
        # workItem has embedded project {_id, name}; lookup only if you need more fields
        "project": {
            "target": "project",
            "localField": "project._id",
            "foreignField": "_id",
            "as": "projectDoc",
            "many": False
        },
        # workItem.assignee is an array of subdocs (with _id). Join to members by _id.
        "assignee": {
            "target": "members",
            "localField": "assignee._id",
            "foreignField": "_id",
            "as": "assignees",
            "many": True
        },
        # workItem has embedded cycle {_id, name}; join only if deeper cycle fields are needed
        "cycle": {
            "target": "cycle",
            "localField": "cycle._id",
            "foreignField": "_id",
            "as": "cycleDoc",
            "many": False
        },
        # workItem has embedded modules {_id, name} (single module reference despite plural key)
        "modules": {
            "target": "module",
            "localField": "modules._id",
            "foreignField": "_id",
            "as": "moduleDoc",
            "many": False
        },
    },

    "project": {
        # One project → many cycles/modules/members/pages/projectStates
        "cycles": {
            "target": "cycle",
            "localField": "_id",
            "foreignField": "project._id",
            "as": "cycles",
            "many": True
        },
        "modules": {
            "target": "module",
            "localField": "_id",
            "foreignField": "project._id",
            "as": "modules",
            "many": True
        },
        "members": {
            "target": "members",
            "localField": "_id",
            "foreignField": "project._id",
            "as": "members",
            "many": True
        },
        "pages": {
            "target": "page",
            "localField": "_id",
            "foreignField": "project._id",
            "as": "pages",
            "many": True
        },
        "projectStates": {
            "target": "projectState",
            "localField": "_id",
            "foreignField": "projectId",
            "as": "projectStates",
            "many": True
        },
    },

    "cycle": {
        "project": {
            "target": "project",
            "localField": "project._id",
            "foreignField": "_id",
            "as": "project",
            "many": False
        }
    },

    "module": {
        "project": {
            "target": "project",
            "localField": "project._id",
            "foreignField": "_id",
            "as": "project",
            "many": False
        }
    },

    "members": {
        "project": {
            "target": "project",
            "localField": "project._id",
            "foreignField": "_id",
            "as": "project",
            "many": False
        }
    },

    "page": {
        "project": {
            "target": "project",
            "localField": "project._id",
            "foreignField": "_id",
            "as": "projectDoc",
            "many": False
        },
        # If linkedCycle / linkedModule store ObjectId arrays, you can enable these:
        # "linkedCycle": {
        #     "target": "cycle",
        #     "localField": "linkedCycle",
        #     "foreignField": "_id",
        #     "as": "linkedCycleDocs",
        #     "many": True
        # },
        # "linkedModule": {
        #     "target": "module",
        #     "localField": "linkedModule",
        #     "foreignField": "_id",
        #     "as": "linkedModuleDocs",
        #     "many": True
        # },
    },

    "projectState": {
        "project": {
            "target": "project",
            "localField": "projectId",
            "foreignField": "_id",
            "as": "project",
            "many": False
        }
    }
}

# ---- Collections (one source of truth)
Collection = str  # Simplified for tool usage

# ---- Allow-listed fields (restrict what the LLM can query/sort/project)
ALLOWED_FIELDS: Dict[str, Set[str]] = {
    "workItem": {
        "_id", "displayBugNo", "title", "description",
        "priority", "status",
        # Embedded state/cycle/module per production schema
        "state.name",
        "project._id", "project.name",
        "cycle._id", "cycle.name",
        "modules._id", "modules.name",
        "createdBy._id", "createdBy.name",
        "createdTimeStamp", "updatedTimeStamp",
        "assignee", "assignee._id", "assignee.name", "label"
    },
    "project": {
        "_id", "projectDisplayId", "name", "description",
        "imageUrl", "icon", "access", "isActive", "status",
        "favourite", "isArchived", "createdTimeStamp", "updatedTimeStamp",
        "business._id", "business.name",
        # creator info (for queries like "who created the project")
        "createdBy._id", "createdBy.name"
    },
    "cycle": {
        "_id", "title", "name", "description", "status",
        "startDate", "endDate",
        "project._id",
        "isDefault", "isFavourite",
        "createdTimeStamp", "updatedTimeStamp",
        "business._id"
    },
    "module": {
        "_id", "title", "name", "description", "isFavourite",
        "project._id", "business._id",
        "createdTimeStamp", "assignee"
    },
    "members": {
        "_id", "name", "email", "role", "joiningDate",
        "type", "project._id",
        "memberId", "staff._id", "staff.name"
    },
    "page": {
        "_id", "title", "content", "visibility",
        "project._id", "project.name",
        "createdBy._id", "createdBy.name",
        "linkedCycle", "linkedModule",
        "locked", "isFavourite",
        "createdAt", "updatedAt",
        "business._id", "business.name"
    },
    "projectState": {
        "_id", "projectId", "name", "icon",
        "subStates.name", "subStates.order"
    }
}

# ---- Optional field aliases (normalize synonyms / UI names)
ALIASES: Dict[str, Dict[str, str]] = {
    "project": {"id": "_id", "displayId": "projectDisplayId"},
    "workItem": {"bug": "displayBugNo", "stateName": "state.name"},
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

def build_lookup_stage(from_collection: str, relationship: Dict[str, Any], current_collection: str, additional_filters: Dict[str, Any] = None, local_field_prefix: str = None) -> Dict[str, Any]:
    """Build MongoDB $lookup stage based on relationship definition.

    Enhancements:
    - Supports field-to-field joins with $expr
    - Handles array-joins using $in when appropriate
    - Parses simple "X in Y" and "X = Y" expressions from relationship["expr"]
    - Keeps local field paths relative to current document context
    """
    def _is_array_like(path: str) -> bool:
        candidates = [
            "assignee", "linkedCycle", "linkedModule",
            "assignees", "members", "labels", "subStates._id"
        ]
        return any(c in path for c in candidates)

    # Helper to strip collection prefix from a dotted path
    def _strip_prefix(path: str, prefix: str) -> str:
        parts = path.split(".")
        if parts[0] == prefix:
            return ".".join(parts[1:])
        return path

    alias_name = relationship.get("as") or relationship.get("alias") or relationship.get("target") or from_collection
    lookup_stage: Dict[str, Any] = {
        "$lookup": {
            "from": from_collection,
            "let": {},
            "pipeline": [],
            "as": alias_name
        }
    }

    # New style: localField / foreignField
    if "localField" in relationship and "foreignField" in relationship:
        local_field_raw = relationship["localField"]
        foreign_field_raw = relationship["foreignField"]
        # Keep local path relative to current document
        local_field_path = _strip_prefix(local_field_raw, current_collection)
        if local_field_prefix:
            # When doing multi-hop, reference the field from prior lookup alias
            local_field_path = f"{local_field_prefix}.{local_field_path}"
        # Foreign path should be relative to remote collection
        foreign_field_path = _strip_prefix(foreign_field_raw, from_collection)

        var_name = f"local_{local_field_path.replace('.', '_')}"
        lookup_stage["$lookup"]["let"][var_name] = f"${local_field_path}"

        if _is_array_like(local_field_path):
            match_condition = {"$expr": {"$in": [f"${foreign_field_path}", f"$${var_name}"]}}
        else:
            match_condition = {"$expr": {"$eq": [f"$${var_name}", f"${foreign_field_path}"]}}
        lookup_stage["$lookup"]["pipeline"].append({"$match": match_condition})

    elif "join" in relationship:
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
                if local_field_prefix:
                    local_field_path = f"{local_field_prefix}.{local_field_path}"

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
                if local_field_prefix:
                    local_field_path = f"{local_field_prefix}.{local_field_path}"
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
