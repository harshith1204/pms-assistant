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


    Args:
        query: Natural language prompt, e.g. "Show urgent work items in project 'CRM' grouped by cycle".

    Returns: A formatted string with understood intent, compiled query, and results.
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

            # Show compiled query info
            compiled = result.get("compiled")
            if compiled:
                response += f"🔧 COMPILED QUERY:\n"
                response += f"• Kind: {compiled.get('kind')}\n"
                response += f"• Collection: {compiled.get('collection')}\n"
                if compiled.get('kind') == 'find':
                    if compiled.get('filter'):
                        response += f"• Filter: {json.dumps(compiled.get('filter'), indent=2)}\n"
                    if compiled.get('projection'):
                        response += f"• Projection: {json.dumps(compiled.get('projection'), indent=2)}\n"
                    if compiled.get('sort'):
                        response += f"• Sort: {json.dumps(compiled.get('sort'), indent=2)}\n"
                    response += f"• Limit: {compiled.get('limit')}\n"
                else:
                    pipeline = result.get("pipeline")
                    if pipeline:
                        response += f"• Stages: {len(pipeline)}\n"
                        for i, stage in enumerate(pipeline):
                            stage_name = list(stage.keys())[0]
                            stage_content = json.dumps(stage[stage_name], indent=2)
                            if len(stage_content) > 200:
                                stage_content = stage_content + "..."
                            response += f"  - {stage_name}: {stage_content}\n"
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

# Define the tools list (no schema tool)
tools = [
    intelligent_query,
]
