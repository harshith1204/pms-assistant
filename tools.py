from langchain_core.tools import tool
from typing import Optional, Dict, List, Any, Union
import constants
import os
import json
import re
from glob import glob

mongodb_tools = constants.mongodb_tools
DATABASE_NAME = constants.DATABASE_NAME
try:
    from planner import plan_and_execute_query
except ImportError:
    plan_and_execute_query = None


# -------------------- Result Pruning Utilities --------------------
CONTENT_KEYWORDS = {
    "title",
    "name",
    "label",
    "summary",
    "description",
    "content",
    "body",
    "text",
    "notes",
    "comment",
    "message",
    "details",
    "reason",
    "resolution",
    "objective",
    "goal",
    "steps",
    "url",
    "link",
    "links",
    "tags",
    "keywords",
}

NOISE_KEYWORDS = {
    "_id",
    "id",
    "__v",
    "class",
    "className",
    "_class",
    "createdAt",
    "updatedAt",
    "created_on",
    "updated_on",
    "timestamp",
    "version",
    "etag",
}


def _looks_like_identifier(text: str) -> bool:
    """Heuristic check for ObjectId/UUID-like identifiers or opaque tokens."""
    if not isinstance(text, str):
        return False
    stripped = text.strip()
    # 24-char hex (Mongo ObjectId)
    if re.fullmatch(r"[a-fA-F0-9]{24}", stripped):
        return True
    # UUID v4-like
    if re.fullmatch(r"[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}", stripped):
        return True
    # Mostly hex/base64-ish opaque tokens
    if len(stripped) >= 18 and re.fullmatch(r"[a-zA-Z0-9_\-]+", stripped):
        # Avoid class/type words being flagged
        if not re.search(r"[a-zA-Z]", stripped):
            return True
    return False


def _is_noise_key(key: str) -> bool:
    lower = key.lower()
    if key in NOISE_KEYWORDS or lower in NOISE_KEYWORDS:
        return True
    # Generic id-ish keys
    if lower == "id" or lower.endswith("id") or lower.endswith("_id") or lower.endswith("ids"):
        return True
    # Common metadata
    if lower in {"owner", "assigneeid", "projectid", "moduleid", "memberid", "cycleid"}:
        return True
    return False


def _normalize_string(value: str, max_length: int = 2000) -> str:
    compact = re.sub(r"\s+", " ", value).strip()
    if len(compact) > max_length:
        return compact[:max_length] + "…"
    return compact


def _prune_to_relevant_content(obj: Any, list_item_limit: int = 10) -> Any:
    """
    Recursively prune documents to keep only human-relevant content fields
    (primarily textual), dropping IDs, classes, and metadata.
    """
    # Strings: keep if not an opaque identifier
    if isinstance(obj, str):
        return None if _looks_like_identifier(obj) else _normalize_string(obj)

    # Lists: recursively prune items and truncate
    if isinstance(obj, list):
        pruned_items = []
        for item in obj:
            pruned = _prune_to_relevant_content(item, list_item_limit=list_item_limit)
            # Keep non-empty strings, non-empty dicts, or non-empty lists
            if isinstance(pruned, str) and pruned:
                pruned_items.append(pruned)
            elif isinstance(pruned, dict) and pruned:
                pruned_items.append(pruned)
            elif isinstance(pruned, list) and pruned:
                pruned_items.append(pruned)
            if len(pruned_items) >= list_item_limit:
                break
        return pruned_items

    # Dicts: keep keys that are not noise and whose values carry content
    if isinstance(obj, dict):
        kept: Dict[str, Any] = {}
        for key, value in obj.items():
            if _is_noise_key(key):
                continue
            # Prefer content-oriented keys; but allow any textual value
            pruned_value = _prune_to_relevant_content(value, list_item_limit=list_item_limit)
            if pruned_value in (None, "", [], {}):
                # If key is content-key, still drop if empty after pruning
                continue
            if isinstance(pruned_value, (str, list, dict)):
                # Keep only if likely textual or nested content
                if isinstance(pruned_value, str):
                    kept[key] = pruned_value
                elif isinstance(pruned_value, list):
                    # Keep list if contains textual/nested content after pruning
                    if pruned_value:
                        kept[key] = pruned_value
                elif isinstance(pruned_value, dict):
                    if pruned_value:
                        kept[key] = pruned_value
        # If nothing kept but there are content-keyed scalar values, try salvage
        if not kept:
            for key, value in obj.items():
                if key.lower() in CONTENT_KEYWORDS and isinstance(value, str):
                    normalized = _normalize_string(value)
                    if normalized:
                        kept[key] = normalized
        return kept

    # Other types: ignore (numbers, booleans, None, etc.)
    return None


@tool
async def intelligent_query(query: str) -> str:
    """Execute natural language queries against the Project Management database.

    Args:
        query: Natural language query about projects, work items, cycles, members, pages, modules, or project states.

    Returns: Query results formatted for easy reading.
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
            pipeline = result["pipeline"]
            if pipeline:
                response += f"🔧 GENERATED PIPELINE:\n"
                for i, stage in enumerate(pipeline):
                    stage_name = list(stage.keys())[0]
                    # Format the stage content nicely
                    stage_content = json.dumps(stage[stage_name], indent=2)
                    # Truncate very long content for readability but show complete structure
                    if len(stage_content) > 200:
                        stage_content = stage_content[:200] + "..."
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

            pruned = _prune_to_relevant_content(parsed)
            if isinstance(parsed, list):
                # If it's a single count document, render a friendly summary
                if len(parsed) == 1 and isinstance(parsed[0], dict) and "total" in parsed[0]:
                    response += f"📊 RESULTS:\nTotal: {parsed[0]['total']}"
                    return response
                first_n_pruned = pruned[:10] if isinstance(pruned, list) else pruned
                preview = json.dumps(first_n_pruned, indent=2, ensure_ascii=False)
                more = f"\n… and {max(len(parsed) - 10, 0)} more (content-only)" if len(parsed) > 10 else ""
                response += f"📊 RESULTS (first {min(10, len(parsed))}, content-only):\n{preview}{more}"
            else:
                # Dict or scalar after pruning
                if isinstance(pruned, (dict, list)):
                    response += f"📊 RESULTS (content-only):\n{json.dumps(pruned, indent=2, ensure_ascii=False)}"
                else:
                    response += f"📊 RESULTS:\n{pruned}"

            return response
        else:
            return f"❌ QUERY FAILED:\nQuery: '{query}'\nError: {result['error']}"

    except Exception as e:
        return f"❌ INTELLIGENT QUERY ERROR:\nQuery: '{query}'\nError: {str(e)}"

# Define the tools list (no schema tool)
tools = [
    intelligent_query,
]
