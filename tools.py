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
from planner import plan_and_execute_query, plan_and_execute_query_v2
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

            if isinstance(parsed, list):
                # If it's a single count document, render a friendly summary
                if len(parsed) == 1 and isinstance(parsed[0], dict) and "total" in parsed[0]:
                    response += f"📊 RESULTS:\nTotal: {parsed[0]['total']}"
                    return response
                first_n = parsed[:10]
                preview = json.dumps(first_n, indent=2)
                more = f"\n… and {max(len(parsed) - 10, 0)} more" if len(parsed) > 10 else ""
                response += f"📊 RESULTS (first {min(10, len(parsed))}):\n{preview}{more}"
            else:
                response += f"📊 RESULTS:\n{parsed}"

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


# Define the tools list (no schema tool)
tools = [
    intelligent_query,
    run_aggregation,
]


@tool
async def intelligent_query_v2(query: str) -> str:
    """Experimental IR-based planner: routable, join-aware, explainable.

    - Parses NLQ to a minimal QueryPlan (collections, filters, joins, sort)
    - Executes per-collection capped queries, then performs key-based joins outside Mongo
    - Returns results and an explain block with the plan and which joins/filters fired
    """
    if not plan_and_execute_query_v2:
        return "❌ intelligent_query_v2 not available."
    try:
        result = await plan_and_execute_query_v2(query)
        import json as _json
        return _json.dumps(result, indent=2, default=str)
    except Exception as e:
        return f"❌ IR planner error: {str(e)}"


# Register v2 as well
tools.append(intelligent_query_v2)
