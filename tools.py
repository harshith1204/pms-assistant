import sys
from langchain_core.tools import tool
from typing import Optional, Dict, List, Any, Union
import mongo.constants
import os
import json
import re
from glob import glob
from datetime import datetime
from orchestrator import Orchestrator, StepSpec, as_async
from qdrant.initializer import RAGTool
# Qdrant and RAG dependencies
# try:
#     from qdrant_client import QdrantClient
#     from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
#     from sentence_transformers import SentenceTransformer
#     import numpy as np
# except ImportError:
#     QdrantClient = None
#     SentenceTransformer = None
#     np = None

mongodb_tools = mongo.constants.mongodb_tools
DATABASE_NAME = mongo.constants.DATABASE_NAME
try:
    from planner import plan_and_execute_query
except ImportError:
    plan_and_execute_query = None


# ------------------ RAG Retrieval Defaults ------------------
# Per content_type default limits for retrieval. These are applied when the caller
# does not explicitly provide a limit (i.e., limit is None).
# Rationale: pages/work_items generally require broader recall; projects/cycles/modules
# tend to be fewer and more concise.
CONTENT_TYPE_DEFAULT_LIMITS: Dict[str, int] = {
    "page": 12,
    "work_item": 12,
    "project": 6,
    "cycle": 6,
    "module": 6,
}

# Fallback when content_type is unknown or not provided
DEFAULT_RAG_LIMIT: int = 10

# Optional: per content_type chunk-level tuning for chunk-aware retrieval
# - chunks_per_doc controls how many high-scoring chunks are kept per reconstructed doc
# - include_adjacent controls whether to pull neighboring chunks for context
# - min_score sets a score threshold for initial vector hits
CONTENT_TYPE_CHUNKS_PER_DOC: Dict[str, int] = {
    "page": 3,          # Reduced from 4 to minimize context window usage
    "work_item": 4,     # Reduced from 3 to minimize context window usage
    "project": 2,
    "cycle": 2,
    "module": 2,
}

CONTENT_TYPE_INCLUDE_ADJACENT: Dict[str, bool] = {
    "page": True,      # Disabled to reduce context window usage (was True)
    "work_item": True,  # Keep adjacent for work items for better context
    "project": False,
    "cycle": False,
    "module": False,
}

CONTENT_TYPE_MIN_SCORE: Dict[str, float] = {
    "page": 0.5,
    "work_item": 0.5,
    "project": 0.55,
    "cycle": 0.55,
    "module": 0.55,
}


def normalize_mongodb_types(obj: Any) -> Any:
    """Convert MongoDB extended JSON types to regular Python types."""
    if obj is None:
        return None

    if isinstance(obj, dict):
        # Handle MongoDB-specific types
        if '$binary' in obj:
            # Convert binary to string representation (we'll filter it out anyway)
            return f"<binary:{obj['$binary']['base64'][:8]}...>"
        elif '$date' in obj:
            # Convert MongoDB date to string representation
            return obj['$date']
        elif '$oid' in obj:
            # Convert ObjectId to string
            return obj['$oid']
        else:
            # Recursively process nested objects
            return {key: normalize_mongodb_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        # Process lists recursively
        return [normalize_mongodb_types(item) for item in obj]
    else:
        # Return primitive types as-is
        return obj


def filter_meaningful_content(data: Any) -> Any:
    """Filter MongoDB documents to keep only meaningful content fields.

    Removes unnecessary fields like _id, timestamps, and other metadata
    while preserving actual content like text, names, descriptions, etc.

    Args:
        data: Raw MongoDB document(s) - can be dict, list, or other types

    Returns:
        Filtered data with only meaningful content fields
    """
    # First, normalize MongoDB extended JSON to regular Python types
    normalized_data = normalize_mongodb_types(data)

    # Handle edge cases
    if normalized_data is None:
        return None

    # Define fields that contain meaningful content (not metadata)
    CONTENT_FIELDS = {
        # Text content
        'title', 'description', 'name', 'content', 'email', 'role',
        'priority', 'status', 'state', 'displayBugNo', 'projectDisplayId',
        # Business logic fields
        'label', 'type', 'access', 'visibility', 'icon', 'imageUrl',
        'business', 'staff', 'createdBy', 'assignee', 'project', 'cycle', 'module',
        'members', 'pages', 'projectStates', 'subStates', 'linkedCycle', 'linkedModule',
        # Date fields (but not timestamps)
        'startDate', 'endDate', 'joiningDate', 'createdAt', 'updatedAt',
        # Estimate and work tracking
        'estimate', 'estimateSystem', 'workLogs',
        # Count/aggregation results
        'total', 'count', 'group', 'items'
    }

    # Fields to always exclude (metadata)
    EXCLUDE_FIELDS = {
        '_id', 'createdTimeStamp', 'updatedTimeStamp',
        '_priorityRank',  # Helper field added by pipeline
        '_class',  # Drop Java class metadata
    }

    def is_meaningful_field(key: str, value: Any) -> bool:
        """Check if a field contains meaningful content."""
        # Always exclude metadata fields
        if key in EXCLUDE_FIELDS:
            return False

        # Keep content fields
        if key in CONTENT_FIELDS:
            return True

        # For unknown fields, check if they have meaningful values
        if isinstance(value, str) and value.strip():
            # Non-empty strings are meaningful
            return True
        elif isinstance(value, (int, float)) and not key.endswith(('Id', '_id')):
            # Numbers that aren't IDs are meaningful
            return True
        elif isinstance(value, bool):
            # Boolean values are meaningful
            return True
        elif isinstance(value, dict):
            # Recursively check nested objects
            return any(is_meaningful_field(k, v) for k, v in value.items())
        elif isinstance(value, list) and value:
            # Check if list contains meaningful content, including dict items
            for item in value:
                if isinstance(item, (str, int, float, bool)):
                    if not isinstance(item, str) or item.strip():
                        return True
                elif isinstance(item, dict):
                    if any(is_meaningful_field(k, v) for k, v in item.items()):
                        return True
            return False

        return False

    def clean_document(doc: Any) -> Any:
        """Clean a single document or value."""
        if isinstance(doc, dict):
            # Filter dictionary
            cleaned = {}
            for key, value in doc.items():
                if is_meaningful_field(key, value):
                    if isinstance(value, (dict, list)):
                        cleaned_value = clean_document(value)
                        if cleaned_value:  # Only add if there's meaningful content
                            cleaned[key] = cleaned_value
                    else:
                        cleaned[key] = value
            return cleaned if cleaned else {}
        elif isinstance(doc, list):
            # Filter list of documents
            cleaned = []
            for item in doc:
                cleaned_item = clean_document(item)
                if cleaned_item:  # Only add if there's meaningful content
                    cleaned.append(cleaned_item)
            return cleaned
        else:
            # Return primitive values as-is
            return doc

    return clean_document(normalized_data)


def _is_hex_object_id(value: str) -> bool:
    try:
        return isinstance(value, str) and len(value) == 24 and all(c in '0123456789abcdefABCDEF' for c in value)
    except Exception:
        return False


def _is_binary_placeholder(value: Any) -> bool:
    return isinstance(value, str) and value.startswith("<binary:")


def _is_uuid_string(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    # Simple UUID v4-like pattern check
    if len(value) != 36:
        return False
    parts = value.split("-")
    if len(parts) != 5:
        return False
    expected_lengths = [8, 4, 4, 4, 12]
    for part, L in zip(parts, expected_lengths):
        if len(part) != L:
            return False
        if not all(c in '0123456789abcdefABCDEF' for c in part):
            return False
    return True


def _is_id_like_key(key: str) -> bool:
    # Allowlist display ids
    ALLOWLIST = {"projectDisplayId"}
    if key in ALLOWLIST:
        return False
    lowered = key.lower()
    return (
        key == "_id"
        or lowered == "id"
        or lowered.endswith("id")  # memberId, projectId, defaultAsigneeId, etc.
        or lowered.endswith("_id")
        or lowered.endswith("uuid")
    )


def _strip_ids(value: Any) -> Any:
    """Recursively remove id/uuid-like fields and raw id values from documents."""
    if isinstance(value, dict):
        cleaned: Dict[str, Any] = {}
        for k, v in value.items():
            if _is_id_like_key(k):
                # drop id-like keys entirely
                continue
            # Recurse first
            v2 = _strip_ids(v)
            # Drop values that are just IDs or binary placeholders
            if isinstance(v2, str) and (_is_hex_object_id(v2) or _is_uuid_string(v2) or _is_binary_placeholder(v2)):
                continue
            if v2 is None:
                continue
            # Drop empty containers
            if isinstance(v2, (dict, list)) and not v2:
                continue
            cleaned[k] = v2
        return cleaned
    if isinstance(value, list):
        items = [_strip_ids(x) for x in value]
        items = [x for x in items if x not in (None, {}) and not (isinstance(x, str) and (_is_hex_object_id(x) or _is_uuid_string(x) or _is_binary_placeholder(x)))]
        return items
    return value


def _ensure_list_of_names(obj: Any) -> List[str]:
    names: List[str] = []
    if isinstance(obj, list):
        for item in obj:
            if isinstance(item, dict):
                name = item.get("name") or item.get("title")
                if isinstance(name, str) and name.strip():
                    names.append(name)
            elif isinstance(item, str) and item.strip() and not _is_hex_object_id(item) and not _is_binary_placeholder(item):
                names.append(item)
    elif isinstance(obj, dict):
        name = obj.get("name") or obj.get("title")
        if isinstance(name, str) and name.strip():
            names.append(name)
    elif isinstance(obj, str) and obj.strip():
        names.append(obj)
    return names


def _transform_by_collection(doc: Dict[str, Any], collection: Optional[str]) -> Dict[str, Any]:
    if not isinstance(doc, dict):
        return doc  # type: ignore[return-value]

    collection = (collection or "").strip()
    out: Dict[str, Any] = {}

    def copy_if_present(key: str, alias: Optional[str] = None):
        val = doc.get(key)
        if val is not None:
            out[alias or key] = val

    # Common flatteners
    def set_name(source_key: str, target_key: str):
        val = doc.get(source_key)
        if isinstance(val, dict):
            name = val.get("name") or val.get("title")
            if name:
                out[target_key] = name

    def set_names_list(source_key: str, target_key: str):
        val = doc.get(source_key)
        names = _ensure_list_of_names(val)
        if names:
            out[target_key] = names

    # Always useful common keys
    for k in ["title", "name", "description", "status", "priority", "label",
              "visibility", "access", "imageUrl", "icon",
              "favourite", "isFavourite", "isActive", "isArchived",
              "content", "displayBugNo", "projectDisplayId",
              "startDate", "endDate", "createdAt", "updatedAt",
              "estimate", "estimateSystem", "workLogs"]:
        if k in doc:
            out[k] = doc[k]

    # Per collection enrichments
    if collection == "workItem":
        set_name("project", "projectName")
        set_name("state", "stateName")
        set_name("stateMaster", "stateMasterName")
        set_name("cycle", "cycleName")
        # modules in schema is a single subdoc despite plural key
        set_name("modules", "moduleName")
        set_name("business", "businessName")
        set_name("createdBy", "createdByName")
        set_names_list("assignee", "assignees")
        set_names_list("updatedBy", "updatedByNames")

    elif collection == "project":
        set_name("business", "businessName")
        set_name("lead", "leadName")
        set_name("defaultAsignee", "defaultAssigneeName")
        set_name("createdBy", "createdByName")
        copy_if_present("leadMail")

    elif collection == "cycle":
        # Project may only contain id; we skip if name isn't present
        set_name("project", "projectName")
        set_name("business", "businessName")

    elif collection == "module":
        set_name("project", "projectName")
        set_name("lead", "leadName")
        set_name("business", "businessName")
        set_names_list("assignee", "assignees")

    elif collection == "members":
        set_name("project", "projectName")
        set_name("staff", "staffName")

    elif collection == "page":
        set_name("project", "projectName")
        set_name("createdBy", "createdByName")
        set_name("business", "businessName")
        # Linked arrays could contain ids only; surface counts
        if isinstance(doc.get("linkedCycle"), list):
            out["linkedCycleCount"] = len(doc["linkedCycle"])  # type: ignore[index]
        if isinstance(doc.get("linkedModule"), list):
            out["linkedModuleCount"] = len(doc["linkedModule"])  # type: ignore[index]
        # Also surface names if available
        set_names_list("linkedCycle", "linkedCycleNames")
        set_names_list("linkedModule", "linkedModuleNames")

    elif collection == "projectState":
        # Keep core fields and slim subStates
        substates = doc.get("subStates")
        if isinstance(substates, list):
            slim: List[Dict[str, Any]] = []
            for s in substates:
                if isinstance(s, dict):
                    entry: Dict[str, Any] = {}
                    if isinstance(s.get("name"), str):
                        entry["name"] = s["name"]
                    if isinstance(s.get("order"), (int, float)):
                        entry["order"] = s["order"]
                    if entry:
                        slim.append(entry)
            if slim:
                out["subStates"] = slim

    # Drop empty/None values and metadata keys
    out = {k: v for k, v in out.items() if v not in (None, "", [], {}) and k != "_class"}
    return out


def filter_and_transform_content(data: Any, primary_entity: Optional[str] = None) -> Any:
    """Preserve meaningful fields, strip IDs/UUIDs, and flatten references per collection.

    Steps:
    1) Use existing filter to keep meaningful content fields.
    2) Strip any remaining id/uuid-like keys/values.
    3) Apply per-collection flatteners to surface human-friendly names.
    """
    base = filter_meaningful_content(data)
    stripped = _strip_ids(base)

    def enrich(obj: Any) -> Any:
        if isinstance(obj, dict):
            # Merge base with collection-specific projection
            extra = _transform_by_collection(obj, primary_entity)
            # Overlay extra on top of obj (extra wins)
            merged = {**obj, **extra}
            return {k: v for k, v in merged.items() if v not in (None, "", [], {})}
        return obj

    if isinstance(stripped, list):
        return [enrich(x) for x in stripped]
    if isinstance(stripped, dict):
        return enrich(stripped)
    return stripped

@tool
async def mongo_query(query: str, show_all: bool = False) -> str:
    """Plan-first Mongo query executor for structured, factual questions.

    Use this ONLY when the user asks for authoritative data that must come from
    MongoDB (counts, lists, filters, group-by, breakdowns, state/assignee/project details)
    across collections: `project`, `workItem`, `cycle`, `module`, `members`,
    `page`, `projectState`.

    Args:
        query: Natural language, structured data request about PM entities.
        show_all: If True, output ALL details. Use when user explicitly asks for "all" or "complete list".

    Returns: Smart-sized results - detailed for small sets, summarized for large sets.
    """
    if not plan_and_execute_query:
        return "❌ Query planner not available."

    try:
        result = await plan_and_execute_query(query)

        if not result["success"]:
            return f"❌ Query failed: {result['error']}"

        # Parse results
        rows = result.get("result")
        try:
            parsed = json.loads(rows) if isinstance(rows, str) else rows
        except Exception:
            parsed = rows

        # Handle MongoDB response format
        if isinstance(parsed, list) and len(parsed) > 0:
            if isinstance(parsed[0], str) and parsed[0].startswith("Found"):
                documents = []
                for item in parsed[1:]:
                    try:
                        doc = json.loads(item) if isinstance(item, str) else item
                        filtered_doc = filter_meaningful_content(doc)
                        if filtered_doc:
                            documents.append(filtered_doc)
                    except Exception:
                        continue
                filtered = documents
            else:
                filtered = parsed
        else:
            filtered = parsed

        # Helper functions for clean formatting
        def get_nested(d: Dict[str, Any], key: str) -> Any:
            if key in d:
                return d[key]
            if "." in key:
                cur: Any = d
                for part in key.split("."):
                    if isinstance(cur, dict) and part in cur:
                        cur = cur[part]
                    else:
                        return None
                return cur
            return None

        def ensure_list_str(val: Any) -> List[str]:
            if isinstance(val, list):
                res: List[str] = []
                for x in val:
                    if isinstance(x, str) and x.strip():
                        res.append(x)
                    elif isinstance(x, dict):
                        n = x.get("name") or x.get("title")
                        if isinstance(n, str) and n.strip():
                            res.append(n)
                return res
            if isinstance(val, dict):
                n = val.get("name") or val.get("title")
                return [n] if isinstance(n, str) and n.strip() else []
            if isinstance(val, str) and val.strip():
                return [val]
            return []

        def truncate_str(s: Any, limit: int = 100) -> str:
            if not isinstance(s, str):
                return str(s)
            return s if len(s) <= limit else s[:limit] + "..."

        def render_entity(entity: Dict[str, Any], entity_type: str, detail_level: str = "normal") -> str:
            """Render entity with adaptive detail level.
            
            Args:
                entity: The entity dict
                entity_type: Type of entity
                detail_level: "minimal", "normal", or "full"
            """
            e = entity_type.lower()
            
            if e == "workitem":
                bug = entity.get("displayBugNo") or entity.get("title") or "Item"
                title = entity.get("title") or entity.get("name") or ""
                state = entity.get("stateName") or get_nested(entity, "state.name") or "N/A"
                project = entity.get("projectName") or get_nested(entity, "project.name") or "N/A"
                assignees = ensure_list_str(entity.get("assignees") or entity.get("assignee"))
                assignee = assignees[0] if assignees else "N/A"
                priority = entity.get("priority") or "N/A"
                
                if detail_level == "minimal":
                    # Ultra-compact for large lists
                    return f"{bug}: {truncate_str(title, 50)} | {state} | P{priority}"
                elif detail_level == "full":
                    # Full details
                    line = f"{bug}: {title}\n"
                    line += f"  State: {state} | Priority: {priority}\n"
                    line += f"  Assignee: {assignee} | Project: {project}\n"
                    
                    estimate = entity.get("estimate")
                    if estimate and isinstance(estimate, dict):
                        hr = estimate.get("hr", 0)
                        min_val = estimate.get("min", 0)
                        if hr or min_val:
                            line += f"  Estimate: {hr}h {min_val}m\n"
                    
                    work_logs = entity.get("workLogs")
                    if work_logs and isinstance(work_logs, list) and len(work_logs) > 0:
                        total_hours = sum(log.get("hours", 0) for log in work_logs if isinstance(log, dict))
                        total_mins = sum(log.get("minutes", 0) for log in work_logs if isinstance(log, dict))
                        total_hours += total_mins // 60
                        total_mins = total_mins % 60
                        line += f"  Logged: {total_hours}h {total_mins}m ({len(work_logs)} entries)\n"
                    
                    description = entity.get("description")
                    if description:
                        line += f"  Description: {truncate_str(description, 200)}\n"
                    
                    return line
                else:
                    # Normal balanced view
                    title_trunc = truncate_str(title, 70)
                    line = f"{bug}: {title_trunc} | {state} | P{priority} | {assignee} | {project}"
                    
                    estimate = entity.get("estimate")
                    if estimate and isinstance(estimate, dict):
                        hr = estimate.get("hr", 0)
                        min_val = estimate.get("min", 0)
                        if hr or min_val:
                            line += f" | Est: {hr}h {min_val}m"
                    
                    work_logs = entity.get("workLogs")
                    if work_logs and isinstance(work_logs, list) and len(work_logs) > 0:
                        total_hours = sum(log.get("hours", 0) for log in work_logs if isinstance(log, dict))
                        total_mins = sum(log.get("minutes", 0) for log in work_logs if isinstance(log, dict))
                        total_hours += total_mins // 60
                        total_mins = total_mins % 60
                        line += f" | Logged: {total_hours}h {total_mins}m"
                    
                    return line
                
            elif e == "project":
                pid = entity.get("projectDisplayId")
                name = entity.get("name") or entity.get("title") or "Project"
                status = entity.get("status") or "N/A"
                lead = entity.get("leadName") or get_nested(entity, "lead.name") or "N/A"
                business = entity.get("businessName") or get_nested(entity, "business.name") or "N/A"
                
                if detail_level == "minimal":
                    return f"{pid or name}: {truncate_str(name, 40)} | {status}"
                elif detail_level == "full":
                    line = f"{pid}: {name}\n"
                    line += f"  Status: {status} | Lead: {lead}\n"
                    line += f"  Business: {business}\n"
                    return line
                else:
                    return f"{pid or name}: {name} | {status} | Lead: {lead} | {business}"
                
            elif e == "cycle":
                title = entity.get("title") or entity.get("name") or "Cycle"
                status = entity.get("status") or "N/A"
                project = entity.get("projectName") or get_nested(entity, "project.name") or "N/A"
                sd = entity.get("startDate", "")
                ed = entity.get("endDate", "")
                
                if detail_level == "minimal":
                    return f"{truncate_str(title, 40)} | {status}"
                elif detail_level == "full":
                    line = f"{title}\n"
                    line += f"  Status: {status} | Project: {project}\n"
                    if sd or ed:
                        line += f"  Period: {sd} → {ed}\n"
                    return line
                else:
                    dates = f"{sd} → {ed}" if sd or ed else "N/A"
                    return f"{truncate_str(title, 70)} | {status} | {project} | {dates}"
                
            elif e == "module":
                title = entity.get("title") or entity.get("name") or "Module"
                project = entity.get("projectName") or get_nested(entity, "project.name") or "N/A"
                assignees = ensure_list_str(entity.get("assignees") or entity.get("assignee"))
                business = entity.get("businessName") or get_nested(entity, "business.name") or "N/A"
                
                if detail_level == "minimal":
                    return f"{truncate_str(title, 40)} | {len(assignees)} assignee(s)"
                elif detail_level == "full":
                    line = f"{title}\n"
                    line += f"  Project: {project} | Business: {business}\n"
                    if assignees:
                        line += f"  Assignees: {', '.join(assignees)}\n"
                    return line
                else:
                    return f"{truncate_str(title, 70)} | {project} | {len(assignees)} assignee(s) | {business}"
                
            elif e == "members":
                name = entity.get("name") or "Member"
                email = entity.get("email") or "N/A"
                role = entity.get("role") or "N/A"
                project = entity.get("projectName") or get_nested(entity, "project.name") or "N/A"
                type_v = entity.get("type") or "N/A"
                
                if detail_level == "minimal":
                    return f"{name} | {role}"
                elif detail_level == "full":
                    line = f"{name}\n"
                    line += f"  Role: {role} | Type: {type_v}\n"
                    line += f"  Email: {email} | Project: {project}\n"
                    return line
                else:
                    return f"{name} | {role} | {type_v} | {email} | {project}"
                
            elif e == "page":
                title = entity.get("title") or entity.get("name") or "Page"
                project = entity.get("projectName") or get_nested(entity, "project.name") or "N/A"
                visibility = entity.get("visibility") or "N/A"
                
                if detail_level == "minimal":
                    return f"{truncate_str(title, 50)} | {visibility}"
                elif detail_level == "full":
                    line = f"{title}\n"
                    line += f"  Visibility: {visibility} | Project: {project}\n"
                    return line
                else:
                    return f"{truncate_str(title, 70)} | {visibility} | {project}"
                
            elif e == "projectstate":
                name = entity.get("name") or "State"
                subs = entity.get("subStates")
                sub_count = len(subs) if isinstance(subs, list) else 0
                
                if detail_level == "minimal":
                    return f"{name} ({sub_count})"
                elif detail_level == "full":
                    line = f"{name}\n"
                    line += f"  Substates: {sub_count}\n"
                    if subs and isinstance(subs, list):
                        for sub in subs[:5]:
                            if isinstance(sub, dict):
                                sub_name = sub.get("name")
                                if sub_name:
                                    line += f"    • {sub_name}\n"
                    return line
                else:
                    return f"{name} | {sub_count} substate(s)"
                
            # Default fallback
            title = truncate_str(entity.get("title") or entity.get("name") or "Item", 80)
            return title

        # Apply filtering and transformation
        primary_entity = result.get("intent", {}).get("primary_entity") if isinstance(result.get("intent"), dict) else None
        filtered = filter_and_transform_content(filtered, primary_entity=primary_entity)

        # SMART SIZING: Adapt display based on result count
        if isinstance(filtered, list):
            result_count = len(filtered)
            
            # Count-only results
            if result_count == 1 and isinstance(filtered[0], dict) and "total" in filtered[0]:
                return f"Total: {filtered[0]['total']}"

            # Grouped/aggregated results
            if result_count > 0 and isinstance(filtered[0], dict) and "count" in filtered[0]:
                total_items = sum(item.get('count', 0) for item in filtered)
                first_item = filtered[0]
                group_keys = [k for k in first_item.keys() if k not in ['count', 'items']]

                if group_keys:
                    response = f"Found {total_items} items grouped by {', '.join(group_keys)}:\n\n"
                    sorted_data = sorted(filtered, key=lambda x: x.get('count', 0), reverse=True)
                    
                    # Show MORE groups for aggregations (they're compact)
                    display_limit = len(sorted_data) if show_all else min(50, len(sorted_data))
                    
                    for item in sorted_data[:display_limit]:
                        group_values = [f"{k}={item[k]}" for k in group_keys if k in item]
                        group_label = ', '.join(group_values)
                        count = item.get('count', 0)
                        response += f"• {group_label}: {count}\n"

                    if not show_all and len(sorted_data) > display_limit:
                        remaining = sum(item.get('count', 0) for item in sorted_data[display_limit:])
                        response += f"\n... {len(sorted_data) - display_limit} more groups ({remaining} items)\n"
                        response += "💡 Tip: Use show_all=True to see complete breakdown"
                    return response
                else:
                    return f"Total: {total_items}"

            # List of documents - ADAPTIVE DISPLAY
            if result_count <= 10:
                # Small set: Show FULL details for all
                response = f"Found {result_count} item(s):\n\n"
                for item in filtered:
                    if isinstance(item, dict):
                        response += f"• {render_entity(item, primary_entity or '', 'full')}\n"
                return response
                
            elif result_count <= 30:
                # Medium set: Show NORMAL details for all
                response = f"Found {result_count} item(s):\n\n"
                for item in filtered:
                    if isinstance(item, dict):
                        response += f"• {render_entity(item, primary_entity or '', 'normal')}\n"
                return response
                
            elif result_count <= 100 and not show_all:
                # Large set: Show first 30 NORMAL + summarize rest
                response = f"Found {result_count} item(s). Showing first 30:\n\n"
                for item in filtered[:30]:
                    if isinstance(item, dict):
                        response += f"• {render_entity(item, primary_entity or '', 'normal')}\n"
                response += f"\n... {result_count - 30} more items\n"
                response += "💡 Tip: Ask me to 'show all' or filter further to see remaining items"
                return response
                
            elif show_all:
                # User explicitly wants ALL - give them everything with minimal format
                response = f"Found {result_count} item(s) - COMPLETE LIST:\n\n"
                for item in filtered:
                    if isinstance(item, dict):
                        response += f"• {render_entity(item, primary_entity or '', 'minimal')}\n"
                return response
                
            else:
                # Very large set: Show first 50 MINIMAL + guide user
                response = f"Found {result_count} item(s). Showing first 50:\n\n"
                for item in filtered[:50]:
                    if isinstance(item, dict):
                        response += f"• {render_entity(item, primary_entity or '', 'minimal')}\n"
                response += f"\n... {result_count - 50} more items\n"
                response += "💡 Large dataset! Consider:\n"
                response += "   • Filter by specific criteria (priority, assignee, state, etc.)\n"
                response += "   • Group by a dimension to see distribution\n"
                response += "   • Ask for 'all items' if you need the complete list"
                return response

        # Single document - always show full
        if isinstance(filtered, dict):
            return render_entity(filtered, primary_entity or '', 'full')
        
        # Fallback
        return json.dumps(filtered, indent=2)

    except Exception as e:
        return f"❌ Query error: {str(e)}"


@tool
async def rag_search(
    query: str,
    content_type: Optional[str] = None,
    group_by: Optional[str] = None,
    limit: int = 10,
    show_content: bool = True,
    use_chunk_aware: bool = True
) -> str:
    """Universal RAG search - returns FULL content for synthesis.
    
    Use for content-based searches:
    - Find pages/work items by meaning
    - Search documentation and notes
    - Analyze content patterns
    - Group results by any dimension
    
    Args:
        query: Search query (semantic meaning)
        content_type: Filter by type ('page', 'work_item', 'project', 'cycle', 'module', or None)
        group_by: Group by field ('project_name', 'priority', 'state_name', etc.)
        limit: Max results - use higher values (20-50) for comprehensive searches
        show_content: Show full content (default True)
        use_chunk_aware: Use chunk-aware retrieval (default True)
    
    Returns: Full content with essential metadata for synthesis.
    
    💡 Tips:
    - Use limit=20-50 for comprehensive searches
    - Use grouping to understand data distribution first
    - Then search specific groups for detailed content
    """
    try:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if project_root not in sys.path:
            sys.path.append(project_root)
        from qdrant.retrieval import ChunkAwareRetriever, format_reconstructed_results
    except ImportError as e:
        return f"❌ RAG unavailable: {e}"
    except Exception as e:
        return f"❌ RAG error: {str(e)}"
    
    try:
        from collections import defaultdict

        # Initialize RAGTool
        try:
            rag_tool = RAGTool.get_instance()
        except RuntimeError:
            await RAGTool.initialize()
            rag_tool = RAGTool.get_instance()
        
        # SMART LIMIT: Increase defaults for better coverage
        effective_limit: int = limit
        if content_type:
            # Higher defaults for better recall
            default_for_type = {
                "page": 20,        # Increased from 12
                "work_item": 20,   # Increased from 12
                "project": 10,     # Increased from 6
                "cycle": 10,       # Increased from 6
                "module": 10,      # Increased from 6
            }.get(content_type)
            if default_for_type is not None and limit == 10:  # User didn't specify custom limit
                effective_limit = default_for_type

        # Chunk-aware retrieval
        if use_chunk_aware and not group_by:
            from qdrant.retrieval import ChunkAwareRetriever, format_reconstructed_results
            
            retriever = ChunkAwareRetriever(
                qdrant_client=rag_tool.qdrant_client,
                embedding_model=rag_tool.embedding_model
            )
            
            from mongo.constants import QDRANT_COLLECTION_NAME, RAG_CONTEXT_TOKEN_BUDGET
            
            # Better chunk settings for quality
            chunks_per_doc = CONTENT_TYPE_CHUNKS_PER_DOC.get(content_type or "", 4)  # Increased default
            include_adjacent = CONTENT_TYPE_INCLUDE_ADJACENT.get(content_type or "", True)
            min_score = CONTENT_TYPE_MIN_SCORE.get(content_type or "", 0.45)  # Lower threshold for better recall

            reconstructed_docs = await retriever.search_with_context(
                query=query,
                collection_name=QDRANT_COLLECTION_NAME,
                content_type=content_type,
                limit=effective_limit,
                chunks_per_doc=chunks_per_doc,
                include_adjacent=include_adjacent,
                min_score=min_score,
                context_token_budget=RAG_CONTEXT_TOKEN_BUDGET
            )
            
            if not reconstructed_docs:
                return f"No results found for: '{query}'\n💡 Tip: Try broader search terms or remove content_type filter"
            
            # Return clean formatted results with full content
            return format_reconstructed_results(
                docs=reconstructed_docs,
                show_full_content=True,
                show_chunk_details=False
            )
        
        # Standard retrieval
        results = await rag_tool.search_content(query, content_type=content_type, limit=effective_limit)
        
        if not results:
            return f"No results found for: '{query}'\n💡 Tip: Try broader search terms or increase limit"
        
        # NO GROUPING - Adaptive detail based on result count
        if not group_by:
            result_count = len(results)
            response = f"Found {result_count} result(s)"
            if content_type:
                response += f" ({content_type})"
            response += ":\n\n"
            
            # Determine detail level
            if result_count <= 5:
                # Small set: Show ALL content fully
                detail_level = "full"
                display_count = result_count
            elif result_count <= 15:
                # Medium set: Show balanced view
                detail_level = "normal"
                display_count = result_count
            else:
                # Large set: Show more items but compact
                detail_level = "compact"
                display_count = min(25, result_count)
            
            for i, result in enumerate(results[:display_count], 1):
                # Title
                response += f"[{i}] {result['title']}\n"
                
                # Metadata - compact
                meta = []
                if result.get('project_name'):
                    meta.append(f"Project: {result['project_name']}")
                if result.get('displayBugNo'):
                    meta.append(f"#{result['displayBugNo']}")
                if result.get('priority'):
                    meta.append(f"P{result['priority']}")
                if result.get('state_name'):
                    meta.append(result['state_name'])
                if result.get('assignee_name'):
                    meta.append(result['assignee_name'])
                
                if meta:
                    response += f"    {' | '.join(meta)}\n"
                
                # Content - adaptive
                if show_content and result.get('content'):
                    content_text = result['content']
                    
                    if detail_level == "full":
                        # Show complete content
                        response += f"\n{content_text}\n"
                    elif detail_level == "normal":
                        # Show substantial preview
                        if len(content_text) > 500:
                            response += f"\n{content_text[:500]}...\n"
                        else:
                            response += f"\n{content_text}\n"
                    else:
                        # Compact: Show meaningful preview
                        if len(content_text) > 200:
                            response += f"    Preview: {content_text[:200]}...\n"
                        else:
                            response += f"    {content_text}\n"
                
                response += "\n"
            
            if result_count > display_count:
                response += f"... {result_count - display_count} more results\n"
                response += f"💡 Tip: Increase limit (current: {limit}) or add filters to see more"
            
            return response
        
        # GROUPING - Show distribution with samples
        groups = defaultdict(list)
        
        for result in results:
            group_val = result.get(group_by)
            
            # Handle date grouping
            if group_by in ['createdAt', 'updatedAt'] and group_val:
                if isinstance(group_val, str):
                    group_val = group_val.split('T')[0] if 'T' in group_val else group_val[:10]
            
            if group_val is None or group_val == "":
                group_val = "Unknown"
            
            groups[str(group_val)].append(result)
        
        # Sort and format
        sorted_groups = sorted(groups.items(), key=lambda x: len(x[1]), reverse=True)
        
        total_items = sum(len(items) for _, items in sorted_groups)
        response = f"Found {total_items} result(s) in {len(sorted_groups)} groups (by {group_by}):\n\n"
        
        # Show MORE groups when grouped (they're compact)
        display_groups = min(30, len(sorted_groups))
        
        for group_key, items in sorted_groups[:display_groups]:
            response += f"▸ {group_key}: {len(items)} item(s)\n"
            
            # Show top 3 items with mini-previews
            for item in items[:3]:
                title = item['title'][:60] + "..." if len(item['title']) > 60 else item['title']
                response += f"  • {title}\n"
                
                # Add tiny content preview for context
                if show_content and item.get('content'):
                    preview = item['content'][:100].replace('\n', ' ') + "..."
                    response += f"    {preview}\n"
            
            if len(items) > 3:
                response += f"  ... {len(items) - 3} more\n"
            response += "\n"
        
        if len(sorted_groups) > display_groups:
            remaining = sum(len(items) for _, items in sorted_groups[display_groups:])
            response += f"... {len(sorted_groups) - display_groups} more groups ({remaining} items)\n"
        
        return response
        
    except ImportError:
        return "❌ RAG dependencies missing"
    except Exception as e:
        return f"❌ RAG error: {str(e)}"
# Global websocket registry for content generation
_GENERATION_WEBSOCKET = None
_GENERATION_CONVERSATION_ID = None

def set_generation_websocket(websocket):
    """Set the websocket connection for direct content streaming."""
    global _GENERATION_WEBSOCKET
    _GENERATION_WEBSOCKET = websocket

def get_generation_websocket():
    """Get the current websocket connection."""
    return _GENERATION_WEBSOCKET

def set_generation_context(websocket, conversation_id):
    """Set websocket and conversation context for generated content persistence."""
    global _GENERATION_WEBSOCKET, _GENERATION_CONVERSATION_ID
    _GENERATION_WEBSOCKET = websocket
    _GENERATION_CONVERSATION_ID = conversation_id

def get_generation_conversation_id():
    """Get the current conversation id for generated content context."""
    return _GENERATION_CONVERSATION_ID


@tool
async def generate_content(
    content_type: str,
    prompt: str,
    template_title: str = "",
    template_content: str = "",
    context: Optional[Dict[str, Any]] = None
) -> str:
    """Generate work items or pages - sends content DIRECTLY to frontend, returns minimal confirmation.
    
    **CRITICAL TOKEN OPTIMIZATION**: 
    - Full generated content is sent directly to the frontend via WebSocket
    - Agent receives only a minimal success/failure signal (no content details)
    - Prevents generated content from being sent back through the LLM
    
    Use this to create new content:
    - Work items: bugs, tasks, features  
    - Pages: documentation, meeting notes, project plans
    
    Args:
        content_type: Type of content - 'work_item' or 'page'
        prompt: User's instruction for what to generate
        template_title: Optional template title to base generation on
        template_content: Optional template content to use as structure
        context: Optional context dict with additional parameters (pageId, projectId, etc.)
    
    Returns:
        Minimal success/failure signal (NOT content details) - saves maximum tokens
    
    Examples:
        generate_content(content_type="work_item", prompt="Bug: login fails on mobile")
        generate_content(content_type="page", prompt="Create API documentation", context={...})
    """
    import httpx
    
    try:
        if content_type not in ["work_item", "page"]:
            return "❌ Invalid content type"
        
        # Get API base URL from environment or use default
        api_base = os.getenv("API_BASE_URL", "http://localhost:8000")
        
        if content_type == "work_item":
            # Call work item generation endpoint
            url = f"{api_base}/generate-work-item"
            payload = {
                "prompt": prompt,
                "template": {
                    "title": template_title or "Work Item",
                    "content": template_content or ""
                }
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                result = response.json()
            
            # Send full content directly to frontend (bypass agent)
            websocket = get_generation_websocket()
            if websocket:
                try:
                    await websocket.send_json({
                        "type": "content_generated",
                        "content_type": "work_item",
                        "data": result,  # Full content to frontend
                        "success": True
                    })
                except Exception as e:
                    print(f"Warning: Could not send to websocket: {e}")

            # Persist generated artifact as a conversation message (best-effort)
            try:
                conv_id = get_generation_conversation_id()
                if conv_id:
                    from mongo.conversations import save_generated_work_item
                    title = (result or {}).get("title") if isinstance(result, dict) else None
                    description = (result or {}).get("description") if isinstance(result, dict) else None
                    await save_generated_work_item(conv_id, {
                        "title": (title or "Work item").strip(),
                        "description": (description or "").strip(),
                        # Optional fields; may be filled later by explicit save to domain DB
                        "projectIdentifier": (result or {}).get("projectIdentifier") if isinstance(result, dict) else None,
                        "sequenceId": (result or {}).get("sequenceId") if isinstance(result, dict) else None,
                        "link": (result or {}).get("link") if isinstance(result, dict) else None,
                    })
            except Exception as e:
                # Non-fatal
                print(f"Warning: failed to persist generated work item to conversation: {e}")
            
            # Return MINIMAL confirmation to agent (no content details)
            return "✅ Content generated"
            
        else:  # content_type == "page"
            # Call page generation endpoint
            url = f"{api_base}/stream-page-content"
            
            # Build request context
            page_context = context or {}
            payload = {
                "prompt": prompt,
                "template": {
                    "title": template_title or "Page",
                    "content": template_content or ""
                },
                "context": page_context.get("context", {
                    "tenantId": "",
                    "page": {"type": "DOCUMENTATION"},
                    "subject": {},
                    "timeScope": {},
                    "retrieval": {},
                    "privacy": {}
                }),
                "pageId": page_context.get("pageId", ""),
                "projectId": page_context.get("projectId", ""),
                "tenantId": page_context.get("tenantId", "")
            }
            
            # Send as query param (matching the endpoint's expectation)
            import json as json_lib
            params = {"data": json_lib.dumps(payload)}
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                result = response.json()
            
            # Send full content directly to frontend (bypass agent)
            websocket = get_generation_websocket()
            if websocket:
                try:
                    await websocket.send_json({
                        "type": "content_generated",
                        "content_type": "page",
                        "data": result,  # Full content to frontend
                        "success": True
                    })
                except Exception as e:
                    print(f"Warning: Could not send to websocket: {e}")

            # Persist generated page as a conversation message (best-effort)
            try:
                conv_id = get_generation_conversation_id()
                if conv_id:
                    from mongo.conversations import save_generated_page
                    # Ensure blocks shape
                    blocks = result if isinstance(result, dict) else {}
                    if not isinstance(blocks.get("blocks"), list):
                        blocks = {"blocks": []}
                    title = (result or {}).get("title") if isinstance(result, dict) else None
                    await save_generated_page(conv_id, {
                        "title": (title or "Generated Page").strip(),
                        "blocks": blocks
                    })
            except Exception as e:
                print(f"Warning: failed to persist generated page to conversation: {e}")
            
            # Return MINIMAL confirmation to agent (no content details)
            return "✅ Content generated"
            
    except httpx.HTTPStatusError as e:
        error_msg = f"API error: {e.response.status_code}"
        # Send error to frontend
        websocket = get_generation_websocket()
        if websocket:
            try:
                await websocket.send_json({
                    "type": "content_generated",
                    "content_type": content_type,
                    "error": error_msg,
                    "success": False
                })
            except Exception:
                pass
        return f"❌ {error_msg}"
    except httpx.RequestError as e:
        error_msg = "Connection error"
        websocket = get_generation_websocket()
        if websocket:
            try:
                await websocket.send_json({
                    "type": "content_generated",
                    "content_type": content_type,
                    "error": error_msg,
                    "success": False
                })
            except Exception:
                pass
        return f"❌ {error_msg}"
    except Exception as e:
        error_msg = "Generation failed"
        websocket = get_generation_websocket()
        if websocket:
            try:
                await websocket.send_json({
                    "type": "content_generated",
                    "content_type": content_type,
                    "error": str(e)[:200],
                    "success": False
                })
            except Exception:
                pass
        return f"❌ {error_msg}"


# Define the tools list - streamlined and powerful
tools = [
    mongo_query,              # Structured MongoDB queries with intelligent planning
    rag_search,               # Universal RAG search with filtering, grouping, and metadata
    generate_content,         # Generate work items/pages (returns summary only, not full content)
]

# import asyncio

# if __name__ == "__main__":
#     async def main():
#         # Test the tools    
#         while True:
#             question = input("Enter your question: ")
#             if question.lower() in ['exit', 'quit']:
#                 break

#             print("\n🎯 Testing intelligent_query...")

#             print("🔍 Testing rag_content_search...")
#             result1 = await rag_content_search.ainvoke({
#                 "query": question,   # rag_content_search expects `query`
#             })
#             print(result1)

#             print("\n📖 Testing rag_answer_question...")
#             result2 = await rag_answer_question.ainvoke({
#                 "question": question,   # rag_answer_question expects `question`
#             })
#             print(result2)

#     asyncio.run(main())
