from langchain_core.tools import tool
from typing import Optional, Dict, List, Any, Union
import constants
import os
import json
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


@tool
async def intelligent_query(query: str) -> str:
    """Intelligent query over PMS data. Understands natural language and builds optimal MongoDB aggregations using the relationship registry.

    When to use:
    - Any request involving projects, work items/tasks/bugs/issues, cycles/sprints, modules/components, pages/docs, members/users, or project states/status.
    - Counts, lists, filters, groupings, joins across entities, summaries, or overviews.
    - When unsure which specific tool applies.

    Guidance for best results:
    - Provide concrete filters if known (e.g., project "API", status completed, priority high, assigned to Alice).
    - Mention output preferences if important (e.g., top 10 by priority, include assignee and project, show JSON).
    - If follow-ups refine the query, the agent will re-run with improved filters/sorts.
    """
    if not plan_and_execute_query:
        return "❌ Intelligent query planner not available. Please ensure query_planner.py is properly configured."

    try:
        result = await plan_and_execute_query(query)

        if result["success"]:
            # Compose concise, agent-style output without internal debug unless asked
            intent = result["intent"]
            rows = result["result"]

            # Build short answer header
            header_parts = []
            primary = intent.get("primary_entity")
            if intent.get("wants_count") and isinstance(rows, dict) and "total" in rows:
                header_parts.append(f"Count of {primary}: {rows.get('total')}")
            else:
                header_parts.append(f"{primary} results")
            if intent.get("filters"):
                header_parts.append(f"filters: {intent['filters']}")
            header = " | ".join(header_parts)

            # Format rows as a compact table-like text if list-like
            body = ""
            try:
                if isinstance(rows, list) and rows:
                    # Select a small set of common columns if available
                    candidate_cols = [
                        "title", "name", "status", "priority", "assignee", "project", "cycle", "createdTimeStamp"
                    ]
                    # Determine present columns from first row (flatten nested dict names)
                    first = rows[0] if isinstance(rows[0], dict) else {}
                    cols = [c for c in candidate_cols if c in first]
                    # Fallback to keys of first row if none matched
                    if not cols:
                        cols = list(first.keys())[:6]
                    # Build simple header and up to 20 rows
                    body_lines = []
                    body_lines.append(" | ".join(cols))
                    body_lines.append(" | ".join(["-" * len(c) for c in cols]))
                    for item in rows[:20]:
                        if not isinstance(item, dict):
                            body_lines.append(str(item))
                            continue
                        values = []
                        for c in cols:
                            v = item.get(c)
                            if isinstance(v, dict):
                                v = v.get("name") or v.get("title") or json.dumps(v)
                            values.append(str(v) if v is not None else "")
                        body_lines.append(" | ".join(values))
                    # Note if there are more
                    if len(rows) > 20:
                        body_lines.append(f"… and {len(rows) - 20} more")
                    body = "\n".join(body_lines)
                else:
                    body = json.dumps(rows, indent=2)
            except Exception:
                body = json.dumps(rows, indent=2)

            return f"### Answer\n{header}\n\n### Data\n{body}"
        else:
            return f"❌ QUERY FAILED:\nQuery: '{query}'\nError: {result['error']}"

    except Exception as e:
        return f"❌ INTELLIGENT QUERY ERROR:\nQuery: '{query}'\nError: {str(e)}"

# Define the tools list with only main collection related tools and intelligent query tool
tools = [
    intelligent_query,
]
