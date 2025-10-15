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
from bson import json_util as bjson
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
async def mongo_query(query: str, show_all: bool = False, structured: bool = True, include_raw: bool = True) -> str:
    """Execute a natural-language MongoDB query and return CLEAN, STRUCTURED JSON.

    - Uses an LLM-backed planner to build a safe aggregation pipeline
    - Executes the pipeline via the direct Mongo client
    - Returns structured JSON with minimal noise and no data loss

    Returns: JSON string with keys: {ok, source, intent, primary_entity, meta?, data}
    data contains: {raw (extended JSON), clean (Python-native types), filtered (readable projection)}
    """
    if not plan_and_execute_query:
        return json.dumps({
            "ok": False,
            "source": "mongo",
            "error": "Intelligent query planner not available",
        })

    try:
        planner_result = await plan_and_execute_query(query)
        if not planner_result.get("success"):
            return json.dumps({
                "ok": False,
                "source": "mongo",
                "error": planner_result.get("error") or "Planner failed",
            })

        intent = planner_result.get("intent") or {}
        primary_entity = intent.get("primary_entity") if isinstance(intent, dict) else None
        rows = planner_result.get("result")

        # Serialize raw with Extended JSON (lossless)
        try:
            raw_ext_json_obj = json.loads(bjson.dumps(rows, ensure_ascii=False))
        except Exception:
            # Best-effort fallback
            raw_ext_json_obj = rows

        # Clean (convert Mongo types to Python-native/strings) without dropping fields
        clean_full = normalize_mongodb_types(raw_ext_json_obj)

        # Optional filtered projection for readability (drops IDs/UUIDs etc.)
        filtered = filter_and_transform_content(clean_full, primary_entity=primary_entity)

        response_obj: Dict[str, Any] = {
            "ok": True,
            "source": "mongo",
            "query": query,
            "intent": intent,
            "primary_entity": primary_entity,
            "count": (len(raw_ext_json_obj) if isinstance(raw_ext_json_obj, list) else 1 if raw_ext_json_obj else 0),
            "data": {
                **({"raw": raw_ext_json_obj} if include_raw else {}),
                "clean": clean_full,
                "filtered": filtered,
            },
        }

        # Attach meta only when caller requests exhaustive details
        if show_all:
            response_obj["meta"] = {
                "pipeline": planner_result.get("pipeline"),
                "pipeline_js": planner_result.get("pipeline_js"),
            }

        return json.dumps(response_obj, ensure_ascii=False)

    except Exception as e:
        return json.dumps({
            "ok": False,
            "source": "mongo",
            "error": str(e),
        })


@tool
async def rag_search(
    query: str,
    content_type: Optional[str] = None,
    group_by: Optional[str] = None,
    limit: int = 10,
    show_content: bool = True,
    use_chunk_aware: bool = True,
    structured: bool = True,
) -> str:
    """RAG search with CLEAN, STRUCTURED JSON output (minimal noise, no data loss).

    Returns JSON: {ok, source:"rag", mode, query, content_type, limit, results|groups}
    - mode: "chunk_aware" when using context reconstruction, else "standard"
    - For chunk_aware: results include full_content and chunk details
    - For standard: results include all payload fields from vector store
    """
    try:
        # Fix: Add project root to sys.path to resolve module imports
        # This makes 'qdrant' and 'mongo' modules importable from any script location.
        # Adjust the number of os.path.dirname if your directory structure is different.
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if project_root not in sys.path:
            sys.path.append(project_root)
        from qdrant.retrieval import ChunkAwareRetriever, format_reconstructed_results
    except ImportError as e:
        return f"❌ RAG dependency error: {e}. Please ensure all modules are in the correct path."
    except Exception as e:
        return f"❌ RAG SEARCH INITIALIZATION ERROR: {str(e)}"
    
    try:
        from collections import defaultdict

        # Ensure RAGTool is initialized
        try:
            rag_tool = RAGTool.get_instance()
        except RuntimeError:
            # Try to initialize if not already done
            await RAGTool.initialize()
            rag_tool = RAGTool.get_instance()
        
        # Resolve effective limit based on content_type defaults (opt-in when caller uses default)
        effective_limit: int = limit
        if content_type:
            default_for_type = CONTENT_TYPE_DEFAULT_LIMITS.get(content_type)
            if default_for_type is not None and (limit is None or limit == DEFAULT_RAG_LIMIT):
                effective_limit = default_for_type

        # Use chunk-aware retrieval if enabled and not grouping
        if use_chunk_aware and not group_by:
            from qdrant.retrieval import ChunkAwareRetriever
            
            retriever = ChunkAwareRetriever(
                qdrant_client=rag_tool.qdrant_client,
                embedding_model=rag_tool.embedding_model
            )
            
            from mongo.constants import QDRANT_COLLECTION_NAME
            
            # Per content_type chunk-level tuning
            chunks_per_doc = CONTENT_TYPE_CHUNKS_PER_DOC.get(content_type or "", 3)
            include_adjacent = CONTENT_TYPE_INCLUDE_ADJACENT.get(content_type or "", True)
            min_score = CONTENT_TYPE_MIN_SCORE.get(content_type or "", 0.5)

            from mongo.constants import RAG_CONTEXT_TOKEN_BUDGET
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
                return json.dumps({
                    "ok": False,
                    "source": "rag",
                    "error": f"No results for query: {query}",
                })

            def chunk_to_dict(c) -> Dict[str, Any]:
                return {
                    "id": c.id,
                    "score": c.score,
                    "content": c.content if show_content else None,
                    "mongo_id": c.mongo_id,
                    "parent_id": c.parent_id,
                    "chunk_index": c.chunk_index,
                    "chunk_count": c.chunk_count,
                    "title": c.title,
                    "content_type": c.content_type,
                    "metadata": c.metadata,
                }

            def doc_to_dict(d) -> Dict[str, Any]:
                return {
                    "mongo_id": d.mongo_id,
                    "title": d.title,
                    "content_type": d.content_type,
                    "max_score": d.max_score,
                    "avg_score": d.avg_score,
                    "chunk_coverage": d.chunk_coverage,
                    "full_content": d.full_content if show_content else None,
                    "metadata": d.metadata,
                    "chunks": [chunk_to_dict(c) for c in (d.chunks or [])],
                }

            payload = {
                "ok": True,
                "source": "rag",
                "mode": "chunk_aware",
                "query": query,
                "content_type": content_type,
                "limit": effective_limit,
                "results": [doc_to_dict(d) for d in reconstructed_docs],
            }
            return json.dumps(payload, ensure_ascii=False)
        
        # Fallback to standard retrieval
        results = await rag_tool.search_content(query, content_type=content_type, limit=effective_limit)

        if not results:
            return json.dumps({
                "ok": False,
                "source": "rag",
                "error": f"No results for query: {query}",
            })

        # NO GROUPING
        if not group_by:
            payload = {
                "ok": True,
                "source": "rag",
                "mode": "standard",
                "query": query,
                "content_type": content_type,
                "limit": effective_limit,
                "results": [
                    {**r, **({"content": r.get("content")} if show_content else {"content": None})}
                    for r in results
                ],
            }
            return json.dumps(payload, ensure_ascii=False)

        # GROUPING
        from collections import defaultdict
        groups = defaultdict(list)
        for r in results:
            group_val = r.get(group_by)
            if group_by in ["createdAt", "updatedAt"] and group_val:
                if isinstance(group_val, str):
                    group_val = group_val.split("T")[0] if "T" in group_val else group_val[:10]
            if group_val is None or group_val == "":
                group_val = "Unknown"
            groups[str(group_val)].append(r)

        grouped_list = [
            {
                "key": k,
                "count": len(v),
                "items": [
                    {**item, **({"content": item.get("content")} if show_content else {"content": None})}
                    for item in v
                ],
            }
            for k, v in sorted(groups.items(), key=lambda x: len(x[1]), reverse=True)
        ]

        payload = {
            "ok": True,
            "source": "rag",
            "mode": "standard",
            "query": query,
            "content_type": content_type,
            "limit": effective_limit,
            "group_by": group_by,
            "groups": grouped_list,
            "total": sum(g["count"] for g in grouped_list),
        }
        return json.dumps(payload, ensure_ascii=False)
        
    except ImportError:
        return json.dumps({"ok": False, "source": "rag", "error": "RAG not available. Install qdrant-client, sentence-transformers"})
    except Exception as e:
        return json.dumps({"ok": False, "source": "rag", "error": str(e)})


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
