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

# Define the tools list (no schema tool)
tools = [
    intelligent_query,
]
