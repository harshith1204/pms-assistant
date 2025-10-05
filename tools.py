from langchain_core.tools import tool
from typing import Optional, Dict, List, Any, Union
import mongo.constants
import os
import json
import re
from glob import glob
from datetime import datetime
from orchestrator import Orchestrator, StepSpec, as_async
from qdrant.qdrant_initializer import RAGTool
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
              "startDate", "endDate", "createdAt", "updatedAt"]:
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

    Do NOT use this for:
    - Free-form content questions (use `rag_search`).
    - Pure summarization or opinion without data retrieval.
    - When you already have the exact answer in prior tool results.

    Behavior:
    - Follows a planner to generate a safe aggregation pipeline; avoids
      hallucinated fields.
    - Automatically determines when complex joins are beneficial based on query requirements.
    - Intelligently adds strategic relationships only when they improve query performance:
        - Multi-hop queries: "work items by business" (workItem→project→business)
        - Cross-collection analysis: "members working on projects by business"
        - Complex grouping that spans multiple collections
    - Only adds joins that provide clear benefits for the specific query, avoiding unnecessary complexity.

    Args:
        query: Natural language, structured data request about PM entities.
        show_all: If True, output full details instead of a summary. Use sparingly.

    Returns: A compact result suitable for direct user display.
    """
    if not plan_and_execute_query:
        return "❌ Intelligent query planner not available. Please ensure query_planner.py is properly configured."

    try:
        result = await plan_and_execute_query(query)

        if result["success"]:
            response = f"🎯 INTELLIGENT QUERY RESULT:\n"
            response += f"Query: '{query}'\n\n"

            # Show parsed intent
            intent = result["intent"]
            response += f"📋 UNDERSTOOD INTENT:\n"
            if result.get("planner"):
                response += f"• Planner: {result['planner']}\n"
            response += f"• Primary Entity: {intent['primary_entity']}\n"
            if intent['target_entities']:
                response += f"• Related Entities: {', '.join(intent['target_entities'])}\n"
            if intent['filters']:
                response += f"• Filters: {intent['filters']}\n"
            if intent['aggregations']:
                response += f"• Aggregations: {', '.join(intent['aggregations'])}\n"
            response += "\n"

            # Show the generated pipeline (first few stages)
            pipeline = result.get("pipeline")
            pipeline_js = result.get("pipeline_js")
            if pipeline_js:
                response += f"🔧 GENERATED PIPELINE:\n"
                response += pipeline_js
                response += "\n"
            elif pipeline:
                response += f"🔧 GENERATED PIPELINE:\n"
                # Import the formatting function from planner
                try:
                    from planner import _format_pipeline_for_display
                    formatted_pipeline = _format_pipeline_for_display(pipeline)
                    response += formatted_pipeline
                except ImportError:
                    # Fallback to JSON format if import fails
                    for i, stage in enumerate(pipeline):
                        stage_name = list(stage.keys())[0]
                        # Format the stage content nicely
                        stage_content = json.dumps(stage[stage_name], indent=2)
                        # Truncate very long content for readability but show complete structure
                        if len(stage_content) > 200:
                            stage_content = stage_content + "..."
                        response += f"• {stage_name}: {stage_content}\n"
                response += "\n"

            # Show results (compact preview)
            rows = result.get("result")
            try:
                # Attempt to parse stringified JSON results
                if isinstance(rows, str):
                    parsed = json.loads(rows)
                else:
                    parsed = rows
            except Exception:
                parsed = rows

            # Handle the specific MongoDB response format
            if isinstance(parsed, list) and len(parsed) > 0:
                # Check if first element is a string (like "Found X documents...")
                if isinstance(parsed[0], str) and parsed[0].startswith("Found"):
                    # This is the MongoDB response format: [message, doc1_json, doc2_json, ...]
                    # Parse the JSON strings and filter them
                    documents = []
                    for item in parsed[1:]:  # Skip the first message
                        if isinstance(item, str):
                            try:
                                doc = json.loads(item)
                                filtered_doc = filter_meaningful_content(doc)
                                if filtered_doc:  # Only add if there's meaningful content
                                    documents.append(filtered_doc)
                            except Exception:
                                # Skip invalid JSON
                                continue
                        else:
                            # Already parsed, filter directly
                            filtered_doc = filter_meaningful_content(item)
                            if filtered_doc:
                                documents.append(filtered_doc)

                    filtered = documents
                else:
                    # Regular list, filter as before
                    filtered = parsed
            else:
                # Not a list, filter as before
                filtered = parsed


            def format_llm_friendly(data, max_items=20, primary_entity: Optional[str] = None):
                """Format data in a more LLM-friendly way to avoid hallucinations."""
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

                def truncate_str(s: Any, limit: int = 120) -> str:
                    if not isinstance(s, str):
                        return str(s)
                    return s if len(s) <= limit else s[:limit] + "..."

                def render_line(entity: Dict[str, Any]) -> str:
                    e = (primary_entity or "").lower()
                    if e == "workitem":
                        bug = entity.get("displayBugNo") or entity.get("title") or "Item"
                        title = entity.get("title") or entity.get("name") or ""
                        state = entity.get("stateName") or get_nested(entity, "state.name")
                        project = entity.get("projectName") or get_nested(entity, "project.name")
                        assignees = ensure_list_str(entity.get("assignees") or entity.get("assignee"))
                        priority = entity.get("priority")
                        return f"• {bug}: {truncate_str(title, 80)} — state={state or 'N/A'}, priority={priority or 'N/A'}, assignee={(assignees[0] if assignees else 'N/A')}, project={project or 'N/A'}"
                    if e == "project":
                        pid = entity.get("projectDisplayId")
                        name = entity.get("name") or entity.get("title")
                        status_v = entity.get("status")
                        lead = entity.get("leadName") or get_nested(entity, "lead.name")
                        business = entity.get("businessName") or get_nested(entity, "business.name")
                        return f"• {pid or name}: {name or ''} — status={status_v or 'N/A'}, lead={lead or 'N/A'}, business={business or 'N/A'}"
                    if e == "cycle":
                        title = entity.get("title") or entity.get("name")
                        status_v = entity.get("status")
                        project = entity.get("projectName") or get_nested(entity, "project.name")
                        sd = entity.get("startDate")
                        ed = entity.get("endDate")
                        dates = f"{sd} → {ed}" if sd or ed else "N/A"
                        return f"• {truncate_str(title or 'Cycle', 80)} — status={status_v or 'N/A'}, project={project or 'N/A'}, dates={dates}"
                    if e == "module":
                        title = entity.get("title") or entity.get("name")
                        project = entity.get("projectName") or get_nested(entity, "project.name")
                        assignees = ensure_list_str(entity.get("assignees") or entity.get("assignee"))
                        business = entity.get("businessName") or get_nested(entity, "business.name")
                        return f"• {truncate_str(title or 'Module', 80)} — project={project or 'N/A'}, assignees={(len(assignees) if assignees else 0)}, business={business or 'N/A'}"
                    if e == "members":
                        name = entity.get("name")
                        email = entity.get("email")
                        role = entity.get("role")
                        project = entity.get("projectName") or get_nested(entity, "project.name")
                        type_v = entity.get("type")
                        return f"• {name or 'Member'} — role={role or 'N/A'}, email={email or 'N/A'}, type={type_v or 'N/A'}, project={project or 'N/A'}"
                    if e == "page":
                        title = entity.get("title") or entity.get("name")
                        project = entity.get("projectName") or get_nested(entity, "project.name")
                        visibility = entity.get("visibility")
                        fav = entity.get("isFavourite")
                        return f"• {truncate_str(title or 'Page', 80)} — visibility={visibility or 'N/A'}, favourite={fav if fav is not None else 'N/A'}, project={project or 'N/A'}"
                    if e == "projectstate":
                        name = entity.get("name")
                        icon = entity.get("icon")
                        subs = entity.get("subStates")
                        sub_count = len(subs) if isinstance(subs, list) else 0
                        return f"• {name or 'State'} — icon={icon or 'N/A'}, substates={sub_count}"
                    # Default fallback
                    title = entity.get("title") or entity.get("name") or "Item"
                    return f"• {truncate_str(title, 80)}"
                if isinstance(data, list):
                    # Handle count-only results
                    if len(data) == 1 and isinstance(data[0], dict) and "total" in data[0]:
                        return f"📊 RESULTS:\nTotal: {data[0]['total']}"

                    # Handle grouped/aggregated results
                    if len(data) > 0 and isinstance(data[0], dict) and "count" in data[0]:
                        response = "📊 RESULTS SUMMARY:\n"
                        total_items = sum(item.get('count', 0) for item in data)

                        # Determine what type of grouping this is
                        first_item = data[0]
                        group_keys = [k for k in first_item.keys() if k not in ['count', 'items']]

                        if group_keys:
                            response += f"Found {total_items} items grouped by {', '.join(group_keys)}:\n\n"

                            # Sort by count (highest first) and show more groups
                            sorted_data = sorted(data, key=lambda x: x.get('count', 0), reverse=True)

                            # Show all groups if max_items is None, otherwise limit
                            display_limit = len(sorted_data) if max_items is None else 15
                            for item in sorted_data[:display_limit]:
                                group_values = [f"{k}: {item[k]}" for k in group_keys if k in item]
                                group_label = ', '.join(group_values)
                                count = item.get('count', 0)
                                response += f"• {group_label}: {count} items\n"

                            if max_items is not None and len(data) > 15:
                                remaining = sum(item.get('count', 0) for item in sorted_data[15:])
                                response += f"• ... and {len(data) - 15} other categories: {remaining} items\n"
                            elif max_items is None and len(data) > display_limit:
                                remaining = sum(item.get('count', 0) for item in sorted_data[display_limit:])
                                response += f"• ... and {len(data) - display_limit} other categories: {remaining} items\n"
                        else:
                            response += f"Found {total_items} items\n"
                        print(response)
                        return response

                    # Handle list of documents - show summary instead of raw JSON
                    if max_items is not None and len(data) > max_items:
                        response = f"📊 RESULTS SUMMARY:\n"
                        response += f"Found {len(data)} items. Showing key details for first {max_items}:\n\n"
                        # Show sample items in a collection-aware way
                        for i, item in enumerate(data[:max_items], 1):
                            if isinstance(item, dict):
                                response += render_line(item) + "\n"
                        if len(data) > max_items:
                            response += f"• ... and {len(data) - max_items} more items\n"
                        return response
                    else:
                        # Show all items or small list - show in formatted way
                        response = "📊 RESULTS:\n"
                        for item in data:
                            if isinstance(item, dict):
                                response += render_line(item) + "\n"
                        return response

                # Single document or other data
                if isinstance(data, dict):
                    # Format single document in a readable way
                    response = "📊 RESULT:\n"
                    # Prefer a single-line summary first
                    if isinstance(data, dict):
                        response += render_line(data) + "\n\n"
                    # Then show key fields compactly (truncate long strings)
                    for key, value in data.items():
                        if isinstance(value, (str, int, float, bool)):
                            response += f"• {key}: {truncate_str(value, 140)}\n"
                        elif isinstance(value, dict):
                            # Show only shallow summary for dict
                            name_val = value.get('name') or value.get('title')
                            if name_val:
                                response += f"• {key}: {truncate_str(name_val, 120)}\n"
                            else:
                                child_keys = ", ".join(list(value.keys())[:5])
                                response += f"• {key}: {{ {child_keys} }}\n"
                        elif isinstance(value, list):
                            if len(value) <= 5:
                                response += f"• {key}: {truncate_str(str(value), 160)}\n"
                            else:
                                response += f"• {key}: [{len(value)} items]\n"
                    return response
                else:
                    # Fallback to JSON for other data types
                    return f"📊 RESULTS:\n{json.dumps(data, indent=2)}"

            # Apply strong filter/transform now that we know the primary entity
            primary_entity = intent.get('primary_entity') if isinstance(intent, dict) else None
            filtered = filter_and_transform_content(filtered, primary_entity=primary_entity)

            # Format in LLM-friendly way
            max_items = None if show_all else 20
            formatted_result = format_llm_friendly(filtered, max_items=max_items, primary_entity=primary_entity)
            # If members primary entity and no rows, proactively hint about filters
            try:
                if isinstance(result.get("intent"), dict) and result["intent"].get("primary_entity") == "members" and not filtered:
                    formatted_result += "\n(No members matched. Try filtering by name, role, type, or project.)"
            except Exception:
                pass
            response += formatted_result
            print(response)
            return response
        else:
            return f"❌ QUERY FAILED:\nQuery: '{query}'\nError: {result['error']}"

    except Exception as e:
        return f"❌ INTELLIGENT QUERY ERROR:\nQuery: '{query}'\nError: {str(e)}"


@tool
async def rag_search(
    query: str,
    content_type: str = None,
    group_by: str = None,
    limit: int = 10,
    show_content: bool = True,
    use_chunk_aware: bool = True
) -> str:
    """Universal RAG search tool - returns FULL chunk content for LLM synthesis.
    
    **IMPORTANT**: This tool returns complete, untruncated content chunks so you can:
    - Analyze and understand the actual content
    - Generate properly formatted responses based on real data
    - Answer questions accurately using the retrieved context
    - Synthesize information from multiple sources
    
    Use this for ANY content-based search or analysis needs:
    - Find relevant pages, work items, projects, cycles, modules
    - Search by semantic meaning (not just keywords)
    - Get full context for answering questions
    - Analyze content patterns and distributions
    - Group/breakdown results by any dimension
    
    **When to use:**
    - "Find/search/show me pages about X"
    - "What content discusses Y?"
    - "Which work items mention authentication?"
    - "Show me recent documentation about APIs"
    - "Break down results by project/date/priority/etc."
    
    **Do NOT use for:**
    - Structured database queries (counts, filters on structured fields) → use `mongo_query`
    
    Args:
        query: Search query (semantic meaning, not just keywords)
        content_type: Filter by type - 'page', 'work_item', 'project', 'cycle', 'module', or None (all)
        group_by: Group results by field - 'project_name', 'updatedAt', 'priority', 'state_name', 
                 'content_type', 'assignee_name', 'visibility', etc. (None = no grouping)
        limit: Max results to retrieve (default 10, increase for broader searches)
        show_content: If True, shows full content; if False, shows only metadata
        use_chunk_aware: If True, uses chunk-aware retrieval for better context (default True)
    
    Returns: FULL chunk content with rich metadata - ready for LLM synthesis and formatting
    
    Examples:
        query="authentication" → finds all content about authentication with full text
        query="API documentation", content_type="page" → finds API docs pages with complete content
        query="bugs", content_type="work_item", group_by="priority" → work items grouped by priority
    """
    try:
        from collections import defaultdict

        # Ensure RAGTool is initialized
        try:
            rag_tool = RAGTool.get_instance()
        except RuntimeError:
            # Try to initialize if not already done
            await RAGTool.initialize()
            rag_tool = RAGTool.get_instance()
        
        # Use chunk-aware retrieval if enabled and not grouping
        if use_chunk_aware and not group_by:
            from qdrant.retrieval import ChunkAwareRetriever, format_reconstructed_results
            
            retriever = ChunkAwareRetriever(
                qdrant_client=rag_tool.qdrant_client,
                embedding_model=rag_tool.embedding_model
            )
            
            from mongo.constants import QDRANT_COLLECTION_NAME
            
            reconstructed_docs = await retriever.search_with_context(
                query=query,
                collection_name=QDRANT_COLLECTION_NAME,
                content_type=content_type,
                limit=limit,
                chunks_per_doc=3,
                include_adjacent=True,
                min_score=0.5
            )
            
            if not reconstructed_docs:
                return f"❌ No results found for query: '{query}'"
            
            # Always pass full content chunks to the agent by default for synthesis
            # Force show_full_content=True so downstream LLM has full context
            return format_reconstructed_results(
                docs=reconstructed_docs,
                show_full_content=True,
                show_chunk_details=True
            )
        
        # Fallback to standard retrieval
        results = await rag_tool.search_content(query, content_type=content_type, limit=limit)
        
        if not results:
            return f"❌ No results found for query: '{query}'"
        
        # Build response header
        response = f"🔍 RAG SEARCH: '{query}'\n"
        response += f"Found {len(results)} result(s)"
        if content_type:
            response += f" (type: {content_type})"
        response += "\n\n"
        
        # NO GROUPING - Show detailed list with metadata
        if not group_by:
            response += "📋 RESULTS:\n\n"
            for i, result in enumerate(results[:15], 1):
                response += f"[{i}] {result['content_type'].upper()}: {result['title']}\n"
                response += f"    Score: {result['score']:.3f}\n"
                
                # Show metadata compactly
                meta = []
                if result.get('project_name'):
                    meta.append(f"Project: {result['project_name']}")
                if result.get('priority'):
                    meta.append(f"Priority: {result['priority']}")
                if result.get('state_name'):
                    meta.append(f"State: {result['state_name']}")
                if result.get('assignee_name'):
                    meta.append(f"Assignee: {result['assignee_name']}")
                if result.get('displayBugNo'):
                    meta.append(f"Bug#: {result['displayBugNo']}")
                if result.get('updatedAt'):
                    date_str = str(result['updatedAt']).split('T')[0] if 'T' in str(result['updatedAt']) else str(result['updatedAt'])[:10]
                    meta.append(f"Updated: {date_str}")
                if result.get('visibility'):
                    meta.append(f"Visibility: {result['visibility']}")
                if result.get('business_name'):
                    meta.append(f"Business: {result['business_name']}")
                
                if meta:
                    response += f"    {' | '.join(meta)}\n"
                
                # Always include FULL content for LLM synthesis (no truncation)
                # This enables the LLM to generate properly formatted responses based on actual content
                if result.get('content'):
                    content_text = result['content']
                    response += f"\n    === CONTENT START ===\n{content_text}\n    === CONTENT END ===\n"
                
                response += "\n"
            
            if len(results) > 15:
                response += f"... and {len(results) - 15} more results (increase limit to see more)\n"
            
            return response
        
        # GROUPING - Aggregate and show distribution with content snippets
        groups = defaultdict(list)
        
        for result in results:
            group_val = result.get(group_by)
            
            # Handle date grouping
            if group_by in ['createdAt', 'updatedAt'] and group_val:
                if isinstance(group_val, str):
                    group_val = group_val.split('T')[0] if 'T' in group_val else group_val[:10]
            
            # Handle None/empty
            if group_val is None or group_val == "":
                group_val = "Unknown"
            
            groups[str(group_val)].append(result)
        
        # Sort groups by count
        sorted_groups = sorted(groups.items(), key=lambda x: len(x[1]), reverse=True)
        
        response += f"📊 GROUPED BY '{group_by}':\n"
        response += f"Total groups: {len(sorted_groups)}\n\n"
        
        for group_key, items in sorted_groups[:20]:
            response += f"▸ {group_key}: {len(items)} item(s)\n"
            
            # Show sample items with content snippets for context
            for item in items[:3]:
                title = item['title'][:55] + "..." if len(item['title']) > 55 else item['title']
                response += f"  • {title} (score: {item['score']:.2f})\n"
                # Include content snippet for better LLM understanding
                if show_content and item.get('content'):
                    snippet = item['content'][:200] + "..." if len(item['content']) > 200 else item['content']
                    response += f"    Content: {snippet}\n"
            
            if len(items) > 3:
                response += f"  ... and {len(items) - 3} more\n"
            response += "\n"
        
        if len(sorted_groups) > 20:
            remaining_items = sum(len(items) for _, items in sorted_groups[20:])
            response += f"... and {len(sorted_groups) - 20} more groups ({remaining_items} items)\n"
        
        return response
        
    except ImportError:
        return "❌ RAG not available. Install: qdrant-client, sentence-transformers"
    except Exception as e:
        return f"❌ RAG SEARCH ERROR: {str(e)}"


# Define the tools list - streamlined and powerful
tools = [
    mongo_query,              # Structured MongoDB queries with intelligent planning
    rag_search,               # Universal RAG search with filtering, grouping, and metadata
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
