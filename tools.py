from langchain_core.tools import tool
from typing import Optional, Dict, List, Any, Union
import json
import constants
import os
import re
mongodb_tools = constants.mongodb_tools
DATABASE_NAME = constants.DATABASE_NAME

# Import the registry and intelligent query planner
from registry import REL, ALLOWED_FIELDS, ALIASES, resolve_field_alias, validate_fields, build_lookup_stage

# Import the intelligent query planner
try:
    from query_planner import plan_and_execute_query
except ImportError:
    plan_and_execute_query = None

# Qdrant inserter
try:
    from qdrant.insertdocs import upsert_documents
except Exception:
    upsert_documents = None


@tool
async def intelligent_query(query: str) -> str:
    """Intelligent query processor that understands natural language and handles any permutation of PMS queries.

    USE THIS TOOL WHEN:
    - No other specific tool matches the query exactly
    - User asks complex questions spanning multiple collections
    - Questions involve relationships between projects, work items, cycles, members, etc.
    - Need dynamic query generation based on relationship registry
    - Questions involve filtering, aggregation, or complex relationships
    - AS A LAST RESORT when specific tools like count_work_items_by_module don't apply

    This is the SMART FALLBACK tool that replaces the need for hundreds of specific tools by:
    ✅ Understanding natural language queries
    ✅ Using relationship registry to build optimal MongoDB pipelines
    ✅ Handling any combination of entities and relationships
    ✅ Applying security constraints automatically
    ✅ Generating appropriate aggregations and projections

    Args:
        query: Natural language query (e.g., "Show me high priority tasks in the API project", "How many work items are in upcoming cycles?", "List all projects with their team members")

    Returns intelligently processed query results based on the relationship registry.

    Examples:
    - "Show me work items for upcoming cycles"
    - "How many high priority tasks are in the mobile project?"
    - "List projects with their active cycles and work items"
    - "Find members working on completed tasks"
    - "Get project overview with cycle and task counts"
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
                        stage_content = stage_content + "..."
                    response += f"• {stage_name}: {stage_content}\n"
                response += "\n"

            # Show results
            response += f"📊 RESULTS:\n{result['result']}"

            return response
        else:
            return f"❌ QUERY FAILED:\nQuery: '{query}'\nError: {result['error']}"

    except Exception as e:
        return f"❌ INTELLIGENT QUERY ERROR:\nQuery: '{query}'\nError: {str(e)}"

# Define the tools list with only main collection related tools and intelligent query tool
tools = [
    intelligent_query,
]


@tool
def qdrant_upsert(items_json: str) -> str:
    """Upsert documents into Qdrant with auto-creation of hybrid collection.

    Args:
        items_json: JSON string of a list of items. Each item must contain:
            - id: unique id (str/int)
            - vector: List[float] dense embedding
            - payload: dict payload to store alongside
            - optional sparse: {index(int): weight(float)} for hybrid search

    Returns a status string with the number of items upserted.
    """
    if upsert_documents is None:
        return "❌ Qdrant upsert not available (missing qdrant client or module)."
    try:
        items: List[Dict[str, Any]] = json.loads(items_json)
        if not isinstance(items, list):
            return "❌ items_json must be a JSON array."
        upsert_documents(items)
        return f"✅ Upserted {len(items)} item(s) into Qdrant."
    except Exception as e:
        return f"❌ Qdrant upsert error: {str(e)}"

# Expose the tool
tools.append(qdrant_upsert)
