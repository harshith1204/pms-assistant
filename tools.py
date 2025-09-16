from langchain_core.tools import tool
from typing import Optional, Dict, List, Any, Union
import constants
import os
import json
import re
from glob import glob

mongodb_tools = constants.mongodb_tools
DATABASE_NAME = constants.DATABASE_NAME

# Import the registry and intelligent query planner
from registry import REL, ALLOWED_FIELDS, ALIASES, resolve_field_alias, validate_fields, build_lookup_stage

# Import the intelligent query planner
try:
    from query_planner import plan_and_execute_query
except ImportError:
    plan_and_execute_query = None


@tool
async def intelligent_query(query: str) -> str:
    """Plan and run cross-collection MongoDB queries from natural language.

    When to use:
    - Complex, multi-hop questions across collections (projects, work items, cycles, members, pages, modules, states)
    - You need automatic join planning using the registry-defined relations and allow-listed fields
    - You want details or counts without hand-writing a pipeline

    What it does:
    - Parses the query, selects the primary collection, joins required relations, applies filters, projections, sorting
    - Generates and executes an aggregation pipeline via the Mongo MCP server

    Tip: If you already have a precise pipeline, use run_aggregation instead.

    Args:
        query: Natural language prompt, e.g. "Show urgent work items in project 'CRM' grouped by cycle".

    Returns: A formatted string with understood intent, generated pipeline, and results.
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

@tool
async def run_aggregation(
    collection: str,
    pipeline_json: Union[str, List[Dict[str, Any]]],
    database: Optional[str] = None,
) -> Any:
    """Execute a MongoDB aggregation pipeline against a collection.

    When to use:
    - You have an explicit pipeline to run (including cross-collection $lookup stages)
    - You want to iterate on a pipeline that intelligent_query cannot infer

    Args:
        collection: Target collection name (e.g., "workItem", "project").
        pipeline_json: Aggregation pipeline as a JSON string or a native list of stages.
        database: Optional database name. Defaults to 'ProjectManagement'.

    Examples:
        - Run a prebuilt pipeline string:
          collection="workItem", pipeline_json='[{"$match": {"priority": "HIGH"}}]'
        - Run a native pipeline list:
          collection="project", pipeline_json=[{"$limit": 5}]
    """
    try:
        pipeline: List[Dict[str, Any]]
        if isinstance(pipeline_json, str):
            pipeline = json.loads(pipeline_json)
        else:
            pipeline = pipeline_json

        if not isinstance(pipeline, list):
            raise ValueError("pipeline must be a list of stages")

        result = await mongodb_tools.execute_tool(
            "aggregate",
            {
                "database": database or DATABASE_NAME,
                "collection": collection,
                "pipeline": pipeline,
            },
        )
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@tool
async def describe_local_collections(pattern: Optional[str] = None, max_docs_per_file: int = 50) -> Any:
    """Summarize local JSON dumps (ProjectManagement.*.json) to reveal collections and fields.

    When to use:
    - You are unsure of collection names or available fields
    - You want a quick schema overview before planning joins or projections

    Args:
        pattern: Optional glob to match files (defaults to 'ProjectManagement.*.json').
        max_docs_per_file: Number of sample documents to scan for field discovery.

    Returns: A JSON summary per file with collection name, count hint, and discovered fields.
    """
    try:
        search_roots = list({os.getcwd(), "/workspace"})
        glob_pattern = pattern or "ProjectManagement.*.json"

        summaries: List[Dict[str, Any]] = []

        for root in search_roots:
            for file_path in glob(os.path.join(root, glob_pattern)):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    # Normalize to list of docs
                    if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
                        docs = data["data"]
                    elif isinstance(data, list):
                        docs = data
                    else:
                        docs = []

                    sample = docs[: max_docs_per_file]
                    field_set = set()
                    for d in sample:
                        if isinstance(d, dict):
                            field_set.update(d.keys())

                    base = os.path.basename(file_path)
                    # Heuristic collection name extraction: ProjectManagement.<collection>.json
                    parts = base.split(".")
                    collection_name = parts[1] if len(parts) >= 3 and parts[0].lower().startswith("projectmanagement") else base.replace(".json", "")

                    rels = list(REL.get(collection_name, {}).keys()) if 'REL' in globals() else []

                    summaries.append(
                        {
                            "file": file_path,
                            "collection": collection_name,
                            "sample_count": len(sample),
                            "top_level_fields": sorted(field_set),
                            "known_relations": rels,
                        }
                    )
                except Exception as inner_e:
                    summaries.append(
                        {
                            "file": file_path,
                            "error": str(inner_e),
                        }
                    )

        return {"success": True, "summaries": summaries}
    except Exception as e:
        return {"success": False, "error": str(e)}


# Define the tools list with intelligent query and utility tools
tools = [
    intelligent_query,
    run_aggregation,
    describe_local_collections,
]
