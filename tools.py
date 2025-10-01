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
async def mongo_query(query: str, show_all: bool = False, enable_complex_joins: bool = True) -> str:
    """Plan-first Mongo query executor for structured, factual questions.

    Use this ONLY when the user asks for authoritative data that must come from
    MongoDB (counts, lists, filters, group-by, state/assignee/project details)
    across collections: `project`, `workItem`, `cycle`, `module`, `members`,
    `page`, `projectState`.

    Do NOT use this for:
    - Free-form content questions (use `rag_answer_question` or `rag_content_search`).
    - Pure summarization or opinion without data retrieval.
    - When you already have the exact answer in prior tool results.

    Behavior:
    - Follows a planner to generate a safe aggregation pipeline; avoids
      hallucinated fields.
    - Can generate complex aggregation pipelines with multiple joins when
      enable_complex_joins=True (default), reducing need for tool chaining.
    - Return concise summaries by default; pass `show_all=True` only when the
      user explicitly requests full records.

    Args:
        query: Natural language, structured data request about PM entities.
        show_all: If True, output full details instead of a summary. Use sparingly.
        enable_complex_joins: If True, allows complex multi-collection aggregation pipelines.

    Returns: A compact result suitable for direct user display.
    """
    if not plan_and_execute_query:
        return "❌ Intelligent query planner not available. Please ensure query_planner.py is properly configured."

    try:
        result = await plan_and_execute_query(query, enable_complex_joins=enable_complex_joins)

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
async def rag_content_search(query: str, content_type: str = None, limit: int = 5) -> str:
    """Retrieve relevant content snippets for inspection (not final answers).

    Use to locate semantically relevant `page` or `work_item` snippets via RAG
    when the user asks to "search/find/show examples" or when you need context
    BEFORE answering. Prefer `rag_answer_question` when the user asks a direct
    question that needs synthesized context.

    Do NOT use this for:
    - Structured database facts (use `mongo_query`).
    - Producing the final answer. This returns excerpts to read, not conclusions.
    - Large limits by default; keep `limit` small (<= 5) unless the user asks.

    Args:
        query: Search phrase to find related content.
        content_type: 'page' | 'work_item' | None (both).
        limit: How many snippets to show (default 5).

    Returns: Snippets with scores to inform subsequent reasoning.
    """
    try:
        # rag_tool = RAGTool()
        rag_tool = RAGTool.get_instance()
        results = await rag_tool.search_content(query, content_type=content_type, limit=limit)

        if not results:
            return f"❌ No relevant content found for query: '{query}'"

        # Format response
        response = f"🔍 RAG SEARCH RESULTS for '{query}':\n\n"
        response += f"Found {len(results)} relevant content pieces:\n\n"

        for i, result in enumerate(results, 1):
            response += f"[{i}] {result['content_type'].upper()}: {result['title']}\n"
            response += f"Relevance Score: {result['score']:.3f}\n"
            response += f"Content Preview: {result['content'][:300]}{'...' if len(result['content']) > 300 else ''}\n"

            # if result['metadata']:
            #     response += f"Metadata: {json.dumps(result['metadata'], indent=2)}\n"

            response += "\n" + "="*50 + "\n"

        return response

    except ImportError:
        return "❌ RAG functionality not available. Please install qdrant-client and sentence-transformers."
    except Exception as e:
        return f"❌ RAG SEARCH ERROR:\nQuery: '{query}'\nError: {str(e)}"


@tool
async def rag_answer_question(question: str, content_types: List[str] = None) -> str:
    """Assemble compact context to answer a content question (RAG-first).

    Use when the user asks a direct question about content in `page`/`work_item`
    data and you need short, high-signal context to support your answer.

    Do NOT use this for:
    - Structured facts like counts/groupings (use `mongo_query`).
    - Broad content discovery (use `rag_content_search`).

    Behavior:
    - Gathers a few high-relevance snippets and returns them as context to read.
    - Keep the final answer in the agent message; this tool returns only context.

    Args:
        question: The specific content question to answer.
        content_types: Optional list of ['page','work_item']; defaults to both.

    Returns: Concise context snippets for the agent to read and then answer.
    """
    try:
        rag_tool = RAGTool.get_instance()
        context = await rag_tool.get_content_context(question, content_types)

        if not context or "No relevant content found" in context:
            return f"❌ No relevant context found for question: '{question}'"

        response = f"📖 CONTEXT FOR QUESTION: '{question}'\n\n"
        response += "Relevant content found:\n\n"
        response += context
        response += "\n" + "="*50 + "\n"
        response += "Use this context to answer the question about page and work item content."

        return response

    except ImportError:
        return "❌ RAG functionality not available. Please install qdrant-client and sentence-transformers."
    except Exception as e:
        return f"❌ RAG QUESTION ERROR:\nQuestion: '{question}'\nError: {str(e)}"


@tool
async def rag_grouped_search(query: str, group_by: List[str] = None, content_types: List[str] = None, limit: int = 50, filters: Dict[str, Any] = None) -> str:
    """Semantic search with grouping by metadata buckets.

    Use when the user asks for a breakdown/distribution of semantically matched content
    (docs, pages, work item descriptions) by content type, project, or last modified.

    Args:
        query: Free-text query to retrieve relevant content snippets.
        group_by: One or more of ["content_type", "project", "project_name",
                  "updated_day", "updated_week", "updated_month"]. If omitted,
                  will infer from phrasing in `query` (e.g., "by content type").
        content_types: Optional list like ["page", "work_item"]. Defaults to both.
        limit: Max total hits to consider (across content types); keep modest (<=100).
        filters: Optional metadata filters, e.g. {"project_name": "PMS", "content_type": "page"}.

    Returns: A compact summary of groups with counts, optionally showing examples per group.
    """
    try:
        rag_tool = RAGTool.get_instance()

        # Normalize args
        group_by = group_by or []
        filters = filters or {}
        if not content_types:
            content_types = ["page", "work_item", "project", "cycle", "module"]

        # Heuristic: infer group_by when not specified
        ql = (query or "").lower()
        if not group_by:
            if "by content type" in ql or "by type" in ql or "by kind" in ql:
                group_by.append("content_type")
            if "by project" in ql or "per project" in ql:
                group_by.append("project_name")
            # Date buckets
            if "by day" in ql or "daily" in ql or "last modified date" in ql or "updated date" in ql or "last modified" in ql:
                group_by.append("updated_day")
            elif "by week" in ql or "weekly" in ql:
                group_by.append("updated_week")
            elif "by month" in ql or "monthly" in ql:
                group_by.append("updated_month")
        # Default if still empty
        if not group_by:
            group_by = ["content_type"]

        # Normalize group_by synonyms → canonical keys
        def normalize_group_key(k: str) -> str:
            s = (k or "").strip().lower()
            if s in {"type", "contenttype"}:
                return "content_type"
            if s in {"project", "projectname"}:
                return "project_name"
            if s in {"updated_at", "updatedat", "modified", "modified_at", "modifiedat", "last_modified", "last_modified_date"}:
                return "updated_day"
            if s in {"updated_day", "updatedday", "day"}:
                return "updated_day"
            if s in {"updated_week", "updatedweek", "week"}:
                return "updated_week"
            if s in {"updated_month", "updatedmonth", "month"}:
                return "updated_month"
            return k
        group_by = [normalize_group_key(k) for k in group_by]

        # Fetch results per content type up to the limit (round-robin cap)
        per_type_limit = max(1, int(limit / max(1, len(content_types))))
        hits: List[Dict[str, Any]] = []
        for ct in content_types:
            # Honor an explicit filter for content_type, if present
            ct_filter = filters.get("content_type")
            if ct_filter and ct != ct_filter:
                continue
            results = await rag_tool.search_content(query, content_type=ct, limit=per_type_limit)
            hits.extend(results or [])

        # Apply client-side filters beyond content_type
        def passes_filters(item: Dict[str, Any]) -> bool:
            # project_name substring match
            pn = filters.get("project_name")
            if pn:
                if not isinstance(item.get("project_name"), str) or pn.lower() not in item.get("project_name", "").lower():
                    return False
            # Future: date range filters can be added here
            return True

        filtered_hits = [h for h in hits if passes_filters(h)]

        # Enrich missing metadata (updated_at, project_name) from Mongo as a fallback
        try:
            # Group ids by collection type
            by_type: Dict[str, List[str]] = {}
            for h in filtered_hits:
                ct = (h.get("content_type") or "").strip()
                mid = str(h.get("mongo_id") or "").strip()
                if not mid:
                    continue
                by_type.setdefault(ct, []).append(mid)

            async def fetch_updates(collection: str, ids: List[str]) -> Dict[str, Dict[str, Any]]:
                # Build $expr $in with $toObjectId for 24-hex ids; ignore non-hex ids
                hex_ids = [i for i in ids if isinstance(i, str) and len(i) == 24 and all(c in '0123456789abcdefABCDEF' for c in i)]
                if not hex_ids:
                    return {}
                if collection == "page":
                    project_stage = {
                        "$project": {
                            "_id": 1,
                            "updatedAt": 1,
                            "project.name": 1,
                        }
                    }
                elif collection == "workItem":
                    project_stage = {
                        "$project": {
                            "_id": 1,
                            "updatedTimeStamp": 1,
                            "createdTimeStamp": 1,
                            "project.name": 1,
                        }
                    }
                else:
                    return {}

                pipeline = [
                    {
                        "$match": {
                            "$expr": {
                                "$in": [
                                    "$_id",
                                    {"$map": {"input": hex_ids, "as": "id", "in": {"$toObjectId": "$$id"}}}
                                ]
                            }
                        }
                    },
                    project_stage,
                ]
                rows = await mongodb_tools.execute_tool("aggregate", {
                    "database": DATABASE_NAME,
                    "collection": collection,
                    "pipeline": pipeline,
                })
                # Parse Mongo MCP format
                try:
                    parsed = json.loads(rows) if isinstance(rows, str) else rows
                except Exception:
                    parsed = rows
                docs: List[Dict[str, Any]] = []
                if isinstance(parsed, list) and parsed:
                    if isinstance(parsed[0], str) and parsed[0].startswith("Found"):
                        for it in parsed[1:]:
                            try:
                                if isinstance(it, str):
                                    docs.append(json.loads(it))
                                elif isinstance(it, dict):
                                    docs.append(it)
                            except Exception:
                                continue
                    else:
                        docs = [d for d in parsed if isinstance(d, dict)]
                elif isinstance(parsed, dict):
                    docs = [parsed]
                # Build map by stringified id
                def str_id(d: Dict[str, Any]) -> str:
                    _id = d.get("_id")
                    if isinstance(_id, dict) and "$oid" in _id:
                        return str(_id.get("$oid"))
                    return str(_id)
                out: Dict[str, Dict[str, Any]] = {}
                for d in docs:
                    out[str_id(d)] = d
                return out

            # Fetch for pages and work items only
            page_ids = by_type.get("page", [])
            wi_ids = by_type.get("work_item", [])
            page_map: Dict[str, Dict[str, Any]] = {}
            wi_map: Dict[str, Dict[str, Any]] = {}
            if page_ids:
                page_map = await fetch_updates("page", page_ids)
            if wi_ids:
                wi_map = await fetch_updates("workItem", wi_ids)

            # Apply enrichment
            for h in filtered_hits:
                if h.get("updated_at") and h.get("project_name"):
                    continue
                ct = h.get("content_type")
                mid = str(h.get("mongo_id") or "")
                if not mid:
                    continue
                source = page_map if ct == "page" else (wi_map if ct == "work_item" else None)
                if not source:
                    continue
                doc = source.get(mid)
                if not isinstance(doc, dict):
                    continue
                # updated
                upd = doc.get("updatedAt") or doc.get("updatedTimeStamp") or doc.get("createdTimeStamp")
                if upd is not None and not h.get("updated_at"):
                    h["updated_at"] = upd if not isinstance(upd, dict) else upd.get("$date")
                # project name
                if not h.get("project_name"):
                    proj = doc.get("project") if isinstance(doc.get("project"), dict) else None
                    pname = (proj.get("name") if isinstance(proj, dict) else None)
                    if pname:
                        h["project_name"] = pname
        except Exception:
            # Best-effort; continue without enrichment on errors
            pass

        # Grouping helpers
        from datetime import datetime

        def parse_dt(val: Any) -> Optional[datetime]:
            if isinstance(val, datetime):
                return val
            if isinstance(val, str) and val:
                try:
                    # Accept ISO-like strings
                    return datetime.fromisoformat(val.replace("Z", "+00:00"))
                except Exception:
                    return None
            return None

        def bucket_value(item: Dict[str, Any], key: str) -> Any:
            k = key.lower()
            if k in ("project", "project_name"):
                return item.get("project_name") or "(unknown project)"
            if k == "content_type":
                return item.get("content_type") or "unknown"
            if k in ("updated_day", "updated_week", "updated_month"):
                dt = parse_dt(item.get("updated_at"))
                if not dt:
                    return "(no date)"
                if k == "updated_day":
                    return dt.date().isoformat()
                if k == "updated_week":
                    # ISO week-year-Www
                    return f"{dt.isocalendar().year}-W{dt.isocalendar().week:02d}"
                if k == "updated_month":
                    return f"{dt.year}-{dt.month:02d}"
            # Fallback: direct field
            return item.get(key) or f"({key} missing)"

        # Build nested grouping (supports 1-2 keys realistically)
        from collections import defaultdict
        counts = defaultdict(int)
        samples: Dict[Any, List[Dict[str, Any]]] = defaultdict(list)

        for h in filtered_hits:
            if not group_by:
                gkey = ("all",)
            else:
                gkey = tuple(bucket_value(h, gb) for gb in group_by)
            counts[gkey] += 1
            if len(samples[gkey]) < 3:
                samples[gkey].append(h)

        # Render summary
        total = sum(counts.values())
        if total == 0:
            return f"❌ No RAG hits for '{query}' after filters."

        # Friendlier label if grouping by updated buckets
        label_keys = {
            "updated_day": "last_modified_date (day)",
            "updated_week": "last_modified_date (week)",
            "updated_month": "last_modified_date (month)",
        }
        label = ", ".join([label_keys.get(k, k) for k in group_by])
        response = f"📊 RAG BREAKDOWN by {label} (n={total}):\n\n"
        # Sort by count desc
        for gkey, cnt in sorted(counts.items(), key=lambda kv: kv[1], reverse=True):
            # Pretty label
            if isinstance(gkey, tuple):
                parts = [str(p) for p in gkey]
                group_label = ", ".join(parts)
            else:
                group_label = str(gkey)
            response += f"• {group_label}: {cnt}\n"
        response += "\n"

        # Add a few examples for the top 3 groups
        top_groups = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:3]
        for gkey, _ in top_groups:
            exs = samples.get(gkey, [])
            if not exs:
                continue
            if isinstance(gkey, tuple):
                group_label = ", ".join([str(p) for p in gkey])
            else:
                group_label = str(gkey)
            response += f"Examples for {group_label}:\n"
            for ex in exs:
                title = ex.get("title") or "Untitled"
                ctype = ex.get("content_type") or "unknown"
                preview = (ex.get("content") or "")[:140]
                response += f"  - [{ctype}] {title}: {preview}{'...' if len(preview) == 140 else ''}\n"
            response += "\n"

        return response

    except Exception as e:
        return f"❌ RAG GROUPED SEARCH ERROR:\nQuery: '{query}'\nError: {str(e)}"

@tool
async def rag_to_mongo_workitems(query: str, limit: int = 20) -> str:
    """Bridge free-text to canonical work item records (RAG → Mongo).

    Use when the user describes issues in prose and wants real work items with
    authoritative fields (e.g., `state.name`, `assignee`, `project.name`). This
    first vector-matches likely items, then fetches official records from Mongo.

    Do NOT use this for:
    - Pure semantic browsing without mapping to Mongo (use `rag_content_search`).
    - Arbitrary entities other than work items.

    Args:
        query: Free-text description to match work items.
        limit: Maximum records to return (keep modest; default 20).

    Returns: Brief lines summarizing matched items with canonical fields.
    """
    try:
        # Step 1: RAG search for work items only
        rag_tool = RAGTool.get_instance()
        rag_results = await rag_tool.search_content(query, content_type="work_item", limit=max(limit, 5))

        # Extract unique Mongo IDs and titles from RAG results (point id is mongo_id)
        all_ids: List[str] = []
        titles: List[str] = []
        seen_ids: set[str] = set()
        for r in rag_results:
            mongo_id = str(r.get("mongo_id") or r.get("id") or "").strip()
            title = str(r.get("title") or "").strip()
            if mongo_id and mongo_id not in seen_ids:
                seen_ids.add(mongo_id)
                all_ids.append(mongo_id)
            if title:
                titles.append(title)

        # Partition IDs: keep only 24-hex strings for ObjectId conversion; ignore UUIDs here
        object_id_strings = [s for s in all_ids if len(s) == 24 and all(c in '0123456789abcdefABCDEF' for c in s)]
        object_id_strings = object_id_strings[: max(0, limit)]
        # Deduplicate and cap titles
        seen_titles: set[str] = set()
        title_patterns: List[str] = []
        for t in titles:
            if t and t not in seen_titles:
                seen_titles.add(t)
                title_patterns.append(t)
            if len(title_patterns) >= max(0, limit):
                break

        # Helper builders
        def build_match_from_ids_and_titles(ids: List[str], title_list: List[str]) -> Dict[str, Any]:
            or_clauses_local: List[Dict[str, Any]] = []
            if ids:
                id_array_expr = {
                    "$map": {
                        "input": ids,
                        "as": "id",
                        "in": {"$toObjectId": "$$id"}
                    }
                }
                or_clauses_local.append({"$expr": {"$in": ["$_id", id_array_expr]}})
            if title_list:
                # Use escaped regex to avoid pathological patterns
                title_or = [{"title": {"$regex": re.escape(t), "$options": "i"}} for t in title_list if t]
                if title_or:
                    or_clauses_local.append({"$or": title_or})
            if not or_clauses_local:
                return {"$match": {"_id": {"$exists": True}}}  # no-op match
            if len(or_clauses_local) == 1:
                return {"$match": or_clauses_local[0]}
            return {"$match": {"$or": or_clauses_local}}

        def project_stage() -> Dict[str, Any]:
            return {
                "$project": {
                    "_id": 1,
                    "displayBugNo": 1,
                    "title": 1,
                    "state.name": 1,
                    "assignee.name": 1,
                    "project.name": 1,
                    "createdTimeStamp": 1,
                }
            }

        def parse_mcp_rows(rows_any: Any) -> List[Dict[str, Any]]:
            try:
                parsed_local = json.loads(rows_any) if isinstance(rows_any, str) else rows_any
            except Exception:
                parsed_local = rows_any
            docs_local: List[Dict[str, Any]] = []
            if isinstance(parsed_local, list) and parsed_local:
                if isinstance(parsed_local[0], str) and parsed_local[0].startswith("Found"):
                    for item in parsed_local[1:]:
                        if isinstance(item, str):
                            try:
                                doc = json.loads(item)
                                if isinstance(doc, dict):
                                    docs_local.append(doc)
                            except Exception:
                                continue
                        elif isinstance(item, dict):
                            docs_local.append(item)
                else:
                    # Filter only dicts
                    docs_local = [d for d in parsed_local if isinstance(d, dict)]
            elif isinstance(parsed_local, dict):
                docs_local = [parsed_local]
            else:
                docs_local = []
            return docs_local

        # Step 2: First attempt — match by RAG object IDs and RAG titles
        primary_match = build_match_from_ids_and_titles(object_id_strings, title_patterns)
        pipeline = [
            primary_match,
            project_stage(),
            {"$limit": limit}
        ]

        args = {
            "database": DATABASE_NAME,
            "collection": "workItem",
            "pipeline": pipeline,
        }

        rows = await mongodb_tools.execute_tool("aggregate", args)

        # Normalize and produce a compact summary
        docs = parse_mcp_rows(rows)

        # Fallback 1: If nothing matched via IDs/titles, try Mongo text search
        if not docs:
            text_pipeline = [
                {"$match": {"$text": {"$search": query}}},
                project_stage(),
                {"$limit": limit}
            ]
            rows_text = await mongodb_tools.execute_tool("aggregate", {
                "database": DATABASE_NAME,
                "collection": "workItem",
                "pipeline": text_pipeline,
            })
            docs = parse_mcp_rows(rows_text)

        # Fallback 2: Regex across common fields and tokens
        if not docs:
            tokens = [w for w in re.findall(r"[A-Za-z0-9_]+", query) if w]
            field_list = ["title", "description", "state.name", "project.name", "cycle.name", "modules.name"]
            and_conditions: List[Dict[str, Any]] = []
            for tok in tokens:
                or_fields = [{fld: {"$regex": re.escape(tok), "$options": "i"}} for fld in field_list]
                and_conditions.append({"$or": or_fields})
            regex_match = {"$match": {"$and": and_conditions}} if and_conditions else {"$match": {"_id": {"$exists": True}}}
            regex_pipeline = [
                regex_match,
                project_stage(),
                {"$limit": limit}
            ]
            rows_regex = await mongodb_tools.execute_tool("aggregate", {
                "database": DATABASE_NAME,
                "collection": "workItem",
                "pipeline": regex_pipeline,
            })
            docs = parse_mcp_rows(rows_regex)

        if not docs:
            return f"❌ No MongoDB records found for the RAG matches or fallbacks of '{query}'"

        # Keep content meaningful
        cleaned = filter_and_transform_content(docs, primary_entity="workItem")

        # Render
        lines = [f"🔗 Matches for '{query}':"]
        for i, d in enumerate(cleaned[:limit], 1):
            if not isinstance(d, dict):
                continue
            bug = d.get("displayBugNo") or d.get("title") or f"Item {i}"
            title = d.get("title", "(no title)")
            state = d.get("stateName") or ((d.get("state") or {}).get("name") if isinstance(d.get("state"), dict) else d.get("state"))
            # assignee may be array or object depending on schema; try best-effort
            assignee_val = d.get("assignee")
            if isinstance(assignee_val, dict):
                assignee = assignee_val.get("name")
            elif isinstance(assignee_val, list) and assignee_val and isinstance(assignee_val[0], dict):
                assignee = assignee_val[0].get("name")
            else:
                assignee = (d.get("assignees") or [None])[0] if isinstance(d.get("assignees"), list) else None
            lines.append(f"• {bug}: {title} — state={state or 'N/A'}, assignee={assignee or 'N/A'}")

        return "\n".join(lines)

    except ImportError:
        return "❌ RAG functionality not available. Please install qdrant-client and sentence-transformers."
    except Exception as e:
        return f"❌ RAG→Mongo ERROR:\nQuery: '{query}'\nError: {str(e)}"

        # This function has been removed. Keep a stub to avoid import-time surprises.
        return "❌ composite_query has been removed. Use mongo_query and agent routing instead."
    except Exception as e:
        return f"❌ Composite query error: {e}"

# Define the tools list (no schema tool)
tools = [
    mongo_query,
    rag_content_search,
    rag_answer_question,
    rag_grouped_search,
    rag_to_mongo_workitems,
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
