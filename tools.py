from langchain_core.tools import tool
from typing import Optional, Union
import constants
import os
import json
mongodb_tools = constants.mongodb_tools
DATABASE_NAME = constants.DATABASE_NAME

# ------------------------------
# Helper utilities
# ------------------------------
def _parse_json_object(arg: Union[str, dict, None], fallback: dict) -> dict:
    """Parse a JSON object string or dict into a dict, returning fallback on empty/invalid."""
    if not arg:
        return fallback
    if isinstance(arg, dict):
        return arg
    try:
        value = json.loads(arg)
        if isinstance(value, dict):
            return value
        return fallback
    except Exception:
        return fallback

def _parse_json_array(arg: Union[str, list, None], fallback: list) -> list:
    """Parse a JSON array string or list into a list, returning fallback on empty/invalid."""
    if not arg:
        return fallback
    if isinstance(arg, list):
        return arg
    try:
        value = json.loads(arg)
        if isinstance(value, list):
            return value
        return fallback
    except Exception:
        return fallback

async def _collection_find(
    collection: str,
    filter_json: Union[str, dict, None] = None,
    projection_json: Union[str, dict, None] = None,
    sort_json: Union[str, dict, None] = None,
    limit: Optional[int] = 50,
) -> str:
    """Execute a generic find on the given collection using optional JSON arguments."""
    try:
        filter_obj = _parse_json_object(filter_json, {})
        projection_obj = _parse_json_object(projection_json, {})
        sort_obj = _parse_json_object(sort_json, {})

        arguments = {
            "database": DATABASE_NAME,
            "collection": collection,
            "filter": filter_obj,
        }

        if projection_obj:
            arguments["projection"] = projection_obj
        if sort_obj:
            arguments["sort"] = sort_obj
        if isinstance(limit, int) and limit > 0:
            arguments["limit"] = limit

        result = await mongodb_tools.execute_tool("find", arguments)
        return str(result)
    except Exception as e:
        return f"❌ Error querying {collection}: {str(e)}"

async def _collection_aggregate(
    collection: str,
    pipeline_json: Union[str, list, None] = None,
) -> str:
    """Execute a generic aggregate on the given collection from a pipeline JSON array string."""
    try:
        pipeline = _parse_json_array(pipeline_json, [])
        result = await mongodb_tools.execute_tool(
            "aggregate",
            {
                "database": DATABASE_NAME,
                "collection": collection,
                "pipeline": pipeline,
            },
        )
        return str(result)
    except Exception as e:
        return f"❌ Error aggregating {collection}: {str(e)}"

# Define ProjectManagement-specific readonly insight tools
@tool
async def get_project_overview() -> str:
    """Returns project status distribution with counts and project names by status. Use for overall project portfolio analysis."""
    try:
        result = await mongodb_tools.execute_tool("aggregate", {
            "database": DATABASE_NAME,
            "collection": "project",
            "pipeline": [
                {
                    "$group": {
                        "_id": "$status",
                        "count": {"$sum": 1},
                        "projects": {"$push": {"name": "$name", "lead": "$lead.name"}}
                    }
                },
                {
                    "$sort": {"count": -1}
                }
            ]
        })
        return f"📊 PROJECT STATUS OVERVIEW:\n{result}"
    except Exception as e:
        return f"❌ Error getting project overview: {str(e)}"

@tool
async def get_work_item_insights() -> str:
    """Returns task distribution by project, status, and priority. Use for understanding workload and priority distribution across projects."""
    try:
        result = await mongodb_tools.execute_tool("aggregate", {
            "database": DATABASE_NAME,
            "collection": "workItem",
            "pipeline": [
                {
                    "$group": {
                        "_id": {
                            "project": "$project.name",
                            "status": "$status",
                            "priority": "$priority"
                        },
                        "count": {"$sum": 1}
                    }
                },
                {
                    "$sort": {"count": -1}
                }
            ]
        })
        return f"🎯 WORK ITEM ANALYSIS:\n{result}"
    except Exception as e:
        return f"❌ Error getting work item insights: {str(e)}"

@tool
async def get_team_productivity() -> str:
    """Returns team member workload analysis with task counts and project assignments. Use for resource allocation and productivity assessment."""
    try:
        result = await mongodb_tools.execute_tool("aggregate", {
            "database": DATABASE_NAME,
            "collection": "members",
            "pipeline": [
                {
                    "$lookup": {
                        "from": "workItem",
                        "localField": "_id",
                        "foreignField": "assignee._id",
                        "as": "assigned_tasks"
                    }
                },
                {
                    "$project": {
                        "name": 1,
                        "email": 1,
                        "role": 1,
                        "task_count": {"$size": "$assigned_tasks"},
                        "projects": {"$size": {"$setUnion": ["$assigned_tasks.project._id"]}}
                    }
                },
                {
                    "$sort": {"task_count": -1}
                }
            ]
        })
        return f"👥 TEAM WORKLOAD ANALYSIS:\n{result}"
    except Exception as e:
        return f"❌ Error getting team productivity: {str(e)}"

@tool
async def get_project_timeline() -> str:
    """Returns recent 20 project activities sorted by timestamp. Use for tracking recent changes and project activity."""
    try:
        result = await mongodb_tools.execute_tool("find", {
            "database": DATABASE_NAME,
            "collection": "timeline",
            "filter": {},
            "sort": {"timestamp": -1},
            "limit": 20
        })
        return f"📅 RECENT PROJECT ACTIVITY:\n{result}"
    except Exception as e:
        return f"❌ Error getting project timeline: {str(e)}"

@tool
async def get_business_insights() -> str:
    """Returns business unit performance with project counts and status breakdown. Use for organizational performance analysis."""
    try:
        result = await mongodb_tools.execute_tool("aggregate", {
            "database": DATABASE_NAME,
            "collection": "project",
            "pipeline": [
                {
                    "$group": {
                        "_id": "$business.name",
                        "total_projects": {"$sum": 1},
                        "active_projects": {
                            "$sum": {"$cond": [{"$eq": ["$status", "STARTED"]}, 1, 0]}
                        },
                        "completed_projects": {
                            "$sum": {"$cond": [{"$eq": ["$status", "COMPLETED"]}, 1, 0]}
                        }
                    }
                },
                {
                    "$sort": {"total_projects": -1}
                }
            ]
        })
        return f"🏢 BUSINESS UNIT PERFORMANCE:\n{result}"
    except Exception as e:
        return f"❌ Error getting business insights: {str(e)}"

@tool
async def search_projects_by_status(status: str) -> str:
    """Returns up to 10 projects matching the specified status. Use for filtering projects by current state."""
    try:
        result = await mongodb_tools.execute_tool("find", {
            "database": DATABASE_NAME,
            "collection": "project",
            "filter": {"status": status},
            "limit": 10
        })
        return f"📋 PROJECTS WITH STATUS '{status.upper()}':\n{result}"
    except Exception as e:
        return f"❌ Error searching projects by status: {str(e)}"

@tool
async def get_work_item_by_priority(priority: str) -> str:
    """Returns up to 10 recent work items matching the priority level. Use for identifying critical tasks."""
    try:
        result = await mongodb_tools.execute_tool("find", {
            "database": DATABASE_NAME,
            "collection": "workItem",
            "filter": {"priority": priority},
            "sort": {"createdTimeStamp": -1},
            "limit": 10
        })
        return f"🚨 {priority.upper()} PRIORITY TASKS:\n{result}"
    except Exception as e:
        return f"❌ Error getting work items by priority: {str(e)}"

@tool
async def get_member_workload(email: Optional[str] = None) -> str:
    """Returns workload analysis for specific member or all members with task completion status. Use for individual performance tracking."""
    try:
        if email:
            filter_query = {"email": email}
        else:
            filter_query = {}

        result = await mongodb_tools.execute_tool("aggregate", {
            "database": DATABASE_NAME,
            "collection": "members",
            "pipeline": [
                {"$match": filter_query},
                {
                    "$lookup": {
                        "from": "workItem",
                        "localField": "_id",
                        "foreignField": "assignee._id",
                        "as": "tasks"
                    }
                },
                {
                    "$project": {
                        "name": 1,
                        "email": 1,
                        "role": 1,
                        "total_tasks": {"$size": "$tasks"},
                        "completed_tasks": {
                            "$size": {
                                "$filter": {
                                    "input": "$tasks",
                                    "as": "task",
                                    "cond": {"$eq": ["$$task.status", "COMPLETED"]}
                                }
                            }
                        },
                        "in_progress_tasks": {
                            "$size": {
                                "$filter": {
                                    "input": "$tasks",
                                    "as": "task",
                                    "cond": {"$eq": ["$$task.status", "IN_PROGRESS"]}
                                }
                            }
                        }
                    }
                }
            ]
        })
        return f"👤 MEMBER WORKLOAD ANALYSIS:\n{result}"
    except Exception as e:
        return f"❌ Error getting member workload: {str(e)}"

@tool
async def search_projects_by_name(name: str) -> str:
    """Returns up to 10 projects matching the search term (case-insensitive). Use for finding specific projects by name."""
    try:
        result = await mongodb_tools.execute_tool("find", {
            "database": DATABASE_NAME,
            "collection": "project",
            "filter": {"name": {"$regex": name, "$options": "i"}},
            "limit": 10
        })
        return f"🔍 PROJECTS MATCHING '{name}':\n{result}"
    except Exception as e:
        return f"❌ Error searching projects by name: {str(e)}"

@tool
async def count_work_items_by_project(project_name: str) -> str:
    """Returns the total count of work items for a specific project. Use for getting work item counts by project name."""
    try:
        result = await mongodb_tools.execute_tool("aggregate", {
            "database": DATABASE_NAME,
            "collection": "workItem",
            "pipeline": [
                {
                    "$match": {
                        "project.name": {"$regex": project_name, "$options": "i"}
                    }
                },
                {
                    "$count": "total_work_items"
                }
            ]
        })

        # Extract the count from the result, handling varying return types
        data = result
        total = 0

        if isinstance(data, str):
            import json, re
            try:
                data = json.loads(data)
            except Exception:
                match = re.search(r"\btotal_work_items\b\s*[:=]\s*(\d+)", data)
                if match:
                    total = int(match.group(1))
                    return f"📊 WORK ITEMS IN '{project_name.upper()}' PROJECT:\nTotal: {total} work items"
                return f"📊 WORK ITEMS IN '{project_name.upper()}' PROJECT (raw):\n{data}"

        if isinstance(data, list) and len(data) > 0:
            first_item = data[0]
            if isinstance(first_item, dict):
                total = int(first_item.get("total_work_items", 0))
            else:
                return f"📊 WORK ITEMS IN '{project_name.upper()}' PROJECT (raw):\n{data}"
        elif isinstance(data, dict):
            total = int(data.get("total_work_items", 0))
        elif isinstance(data, int):
            total = data
        else:
            return f"📊 WORK ITEMS IN '{project_name.upper()}' PROJECT (raw):\n{data}"

        return f"📊 WORK ITEMS IN '{project_name.upper()}' PROJECT:\nTotal: {total} work items"

    except Exception as e:
        return f"❌ Error counting work items for project '{project_name}': {str(e)}"

@tool
async def get_project_work_item_details(project_name: str) -> str:
    """Returns detailed breakdown of work items for a specific project including status distribution. Use for comprehensive project work item analysis."""
    try:
        result = await mongodb_tools.execute_tool("aggregate", {
            "database": DATABASE_NAME,
            "collection": "workItem",
            "pipeline": [
                {
                    "$match": {
                        "project.name": {"$regex": project_name, "$options": "i"}
                    }
                },
                {
                    "$group": {
                        "_id": "$status",
                        "count": {"$sum": 1}
                    }
                },
                {
                    "$sort": {"count": -1}
                }
            ]
        })

        if result and len(result) > 0:
            total_count = sum(item.get("count", 0) for item in result)
            details = f"📊 DETAILED WORK ITEMS IN '{project_name.upper()}' PROJECT:\n"
            details += f"Total Work Items: {total_count}\n\n"
            details += "Breakdown by Status:\n"
            for item in result:
                status = item.get("_id", "Unknown")
                count = item.get("count", 0)
                percentage = (count / total_count * 100) if total_count > 0 else 0
                details += f"• {status}: {count} ({percentage:.1f}%)\n"
            return details
        else:
            return f"📊 WORK ITEMS IN '{project_name.upper()}' PROJECT:\nNo work items found"

    except Exception as e:
        return f"❌ Error getting work item details for project '{project_name}': {str(e)}"

# New tool to get total number of projects
@tool
async def get_total_project_count() -> str:
    """Returns the total number of projects across all statuses. Use to answer 'how many total projects are there?'."""
    try:
        result = await mongodb_tools.execute_tool("aggregate", {
            "database": DATABASE_NAME,
            "collection": "project",
            "pipeline": [
                {"$count": "total_projects"}
            ]
        })

        # Handle both structured (list/dict) and string results from MCP tools
        total = 0
        data = result

        if isinstance(data, str):
            import json, re
            try:
                data = json.loads(data)
            except Exception:
                match = re.search(r"\btotal_projects\b\s*[:=]\s*(\d+)", data)
                if match:
                    total = int(match.group(1))
                    return f"📦 TOTAL PROJECTS:\nTotal: {total}"
                # Could not parse structured content; return raw response
                return f"📦 TOTAL PROJECTS (raw):\n{data}"

        if isinstance(data, list) and len(data) > 0:
            first_item = data[0]
            if isinstance(first_item, dict):
                total = int(first_item.get("total_projects", 0))
            else:
                # Unexpected list item; return as raw
                return f"📦 TOTAL PROJECTS (raw):\n{data}"
        elif isinstance(data, dict):
            total = int(data.get("total_projects", 0))
        elif isinstance(data, int):
            total = data
        else:
            # Fallback to stringifying unknown structure
            return f"📦 TOTAL PROJECTS (raw):\n{data}"

        return f"📦 TOTAL PROJECTS:\nTotal: {total}"
    except Exception as e:
        return f"❌ Error getting total project count: {str(e)}"

@tool
async def get_total_work_item_count() -> str:
    """Returns the total number of work items across all projects. Use to answer 'how many total work items are there?'."""
    try:
        result = await mongodb_tools.execute_tool("aggregate", {
            "database": DATABASE_NAME,
            "collection": "workItem",
            "pipeline": [
                {"$count": "total_work_items"}
            ]
        })

        # Handle both structured (list/dict) and string results from MCP tools
        total = 0
        data = result

        if isinstance(data, str):
            import json, re
            try:
                data = json.loads(data)
            except Exception:
                match = re.search(r"\btotal_work_items\b\s*[:=]\s*(\d+)", data)
                if match:
                    total = int(match.group(1))
                    return f"📊 TOTAL WORK ITEMS:\nTotal: {total}"
                # Could not parse structured content; return raw response
                return f"📊 TOTAL WORK ITEMS (raw):\n{data}"

        if isinstance(data, list) and len(data) > 0:
            first_item = data[0]
            if isinstance(first_item, dict):
                total = int(first_item.get("total_work_items", 0))
            else:
                # Unexpected list item; return as raw
                return f"📊 TOTAL WORK ITEMS (raw):\n{data}"
        elif isinstance(data, dict):
            total = int(data.get("total_work_items", 0))
        elif isinstance(data, int):
            total = data
        else:
            # Fallback to stringifying unknown structure
            return f"📊 TOTAL WORK ITEMS (raw):\n{data}"

        return f"📊 TOTAL WORK ITEMS:\nTotal: {total}"
    except Exception as e:
        return f"❌ Error getting total work item count: {str(e)}"

@tool
async def list_all_projects() -> str:
    """Returns a comprehensive list of all projects with key details. Use to answer 'list all projects' or 'show me all projects'."""
    try:
        result = await mongodb_tools.execute_tool("find", {
            "database": DATABASE_NAME,
            "collection": "project",
            "filter": {},
            "projection": {
                "name": 1,
                "status": 1,
                "lead.name": 1,
                "business.name": 1,
                "description": 1,
                "createdTimeStamp": 1
            },
            "sort": {"createdTimeStamp": -1},
            "limit": 50
        })

        # Handle the result - MongoDB MCP returns list with message + JSON strings
        import json

        if isinstance(result, list) and len(result) > 1:
            # Skip the first element (message) and parse the JSON strings
            projects = []
            for item in result[1:]:  # Skip first element which is the message
                if isinstance(item, str):
                    try:
                        project = json.loads(item)
                        projects.append(project)
                    except json.JSONDecodeError:
                        continue

            if projects:
                response = "📋 ALL PROJECTS:\n\n"
                for i, project in enumerate(projects, 1):
                    name = project.get("name", "Unknown")
                    status = project.get("status", "Unknown")
                    lead = project.get("lead", {}).get("name", "Unknown") if project.get("lead") else "Unknown"
                    business = project.get("business", {}).get("name", "Unknown") if project.get("business") else "Unknown"

                    response += f"{i}. **{name}**\n"
                    response += f"   Status: {status}\n"
                    response += f"   Lead: {lead}\n"
                    response += f"   Business: {business}\n"
                    response += "\n"

                return response
            else:
                return f"📋 ALL PROJECTS (no valid projects found):\n{result}"
        elif isinstance(result, str):
            # Fallback for string responses
            import re
            json_pattern = r'\{[^}]*\}'
            json_matches = re.findall(json_pattern, result)

            projects = []
            for match in json_matches:
                try:
                    project = json.loads(match)
                    projects.append(project)
                except json.JSONDecodeError:
                    continue

            if projects:
                response = "📋 ALL PROJECTS:\n\n"
                for i, project in enumerate(projects[:50], 1):
                    name = project.get("name", "Unknown")
                    status = project.get("status", "Unknown")
                    lead = project.get("lead", {}).get("name", "Unknown") if project.get("lead") else "Unknown"
                    business = project.get("business", {}).get("name", "Unknown") if project.get("business") else "Unknown"

                    response += f"{i}. **{name}**\n"
                    response += f"   Status: {status}\n"
                    response += f"   Lead: {lead}\n"
                    response += f"   Business: {business}\n"
                    response += "\n"

                return response
            else:
                return f"📋 ALL PROJECTS (raw):\n{result}"
        else:
            return f"📋 ALL PROJECTS (unexpected format):\n{result}"

    except Exception as e:
        return f"❌ Error listing all projects: {str(e)}"

@tool
async def get_work_items_breakdown_by_project() -> str:
    """Returns a breakdown of work items for each project, including counts by status. Use to answer 'give me a breakdown of work items for each project'."""
    try:
        result = await mongodb_tools.execute_tool("aggregate", {
            "database": DATABASE_NAME,
            "collection": "workItem",
            "pipeline": [
                {
                    "$group": {
                        "_id": {
                            "project_name": "$project.name",
                            "status": "$status"
                        },
                        "count": {"$sum": 1}
                    }
                },
                {
                    "$group": {
                        "_id": "$_id.project_name",
                        "total_work_items": {"$sum": "$count"},
                        "status_breakdown": {
                            "$push": {
                                "status": "$_id.status",
                                "count": "$count"
                            }
                        }
                    }
                },
                {
                    "$sort": {"total_work_items": -1}
                }
            ]
        })

        # Handle the result - parse and format
        import json

        if isinstance(result, list) and len(result) > 1:
            # MongoDB MCP typically returns [message, data, data, ...]
            # Skip the first element (message) and parse the JSON strings
            parsed_items = []
            for item_str in result[1:]:  # Skip the message
                if isinstance(item_str, str):
                    try:
                        parsed_item = json.loads(item_str)
                        parsed_items.append(parsed_item)
                    except json.JSONDecodeError:
                        continue

            if parsed_items:
                response = "📊 WORK ITEMS BREAKDOWN BY PROJECT:\n\n"
                for item in parsed_items:
                    project_name = item.get("_id", "Unknown Project")
                    if project_name is None:
                        project_name = "No Project Assigned"
                    total_count = item.get("total_work_items", 0)
                    status_breakdown = item.get("status_breakdown", [])

                    response += f"**{project_name}**\n"
                    response += f"Total Work Items: {total_count}\n"

                    if status_breakdown:
                        response += "Status Breakdown:\n"
                        for status_item in status_breakdown:
                            status = status_item.get("status", "Unknown")
                            count = status_item.get("count", 0)
                            percentage = (count / total_count * 100) if total_count > 0 else 0
                            response += f"  • {status}: {count} ({percentage:.1f}%)\n"
                    response += "\n"
                return response
            else:
                return f"📊 WORK ITEMS BREAKDOWN BY PROJECT (no valid data found):\n{result}"
        elif isinstance(result, str):
            # Try to parse JSON from string
            try:
                data = json.loads(result)
                if isinstance(data, list):
                    return await get_work_items_breakdown_by_project()  # Retry with parsed data
            except:
                pass
            return f"📊 WORK ITEMS BREAKDOWN BY PROJECT (raw):\n{result}"
        else:
            return f"📊 WORK ITEMS BREAKDOWN BY PROJECT (unexpected format):\n{result}"

    except Exception as e:
        return f"❌ Error getting work items breakdown by project: {str(e)}"

# ------------------------------
# Generic collection FIND tools
# ------------------------------
@tool
async def query_project_state(
    filter_json: Union[str, dict, None] = None,
    projection_json: Union[str, dict, None] = None,
    sort_json: Union[str, dict, None] = None,
    limit: Optional[int] = 50,
) -> str:
    """Query the projectState collection. Provide JSON strings or dicts for filter, projection, sort. Defaults to {} and limit 50."""
    return await _collection_find("projectState", filter_json, projection_json, sort_json, limit)

@tool
async def query_page(
    filter_json: Union[str, dict, None] = None,
    projection_json: Union[str, dict, None] = None,
    sort_json: Union[str, dict, None] = None,
    limit: Optional[int] = 50,
) -> str:
    """Query the page collection. Provide JSON strings or dicts for filter, projection, sort. Defaults to {} and limit 50."""
    return await _collection_find("page", filter_json, projection_json, sort_json, limit)

@tool
async def query_cycle(
    filter_json: Union[str, dict, None] = None,
    projection_json: Union[str, dict, None] = None,
    sort_json: Union[str, dict, None] = None,
    limit: Optional[int] = 50,
) -> str:
    """Query the cycle collection. Provide JSON strings or dicts for filter, projection, sort. Defaults to {} and limit 50."""
    return await _collection_find("cycle", filter_json, projection_json, sort_json, limit)

@tool
async def query_module(
    filter_json: Union[str, dict, None] = None,
    projection_json: Union[str, dict, None] = None,
    sort_json: Union[str, dict, None] = None,
    limit: Optional[int] = 50,
) -> str:
    """Query the module collection. Provide JSON strings or dicts for filter, projection, sort. Defaults to {} and limit 50."""
    return await _collection_find("module", filter_json, projection_json, sort_json, limit)

@tool
async def query_project(
    filter_json: Union[str, dict, None] = None,
    projection_json: Union[str, dict, None] = None,
    sort_json: Union[str, dict, None] = None,
    limit: Optional[int] = 50,
) -> str:
    """Query the project collection. Provide JSON strings or dicts for filter, projection, sort. Defaults to {} and limit 50."""
    return await _collection_find("project", filter_json, projection_json, sort_json, limit)

@tool
async def query_work_item(
    filter_json: Union[str, dict, None] = None,
    projection_json: Union[str, dict, None] = None,
    sort_json: Union[str, dict, None] = None,
    limit: Optional[int] = 50,
) -> str:
    """Query the workItem collection. Provide JSON strings or dicts for filter, projection, sort. Defaults to {} and limit 50."""
    return await _collection_find("workItem", filter_json, projection_json, sort_json, limit)

# ------------------------------
# Generic collection AGGREGATE tools
# ------------------------------
@tool
async def aggregate_project_state(pipeline_json: Union[str, list, None] = None) -> str:
    """Run an aggregation pipeline on projectState. Provide a JSON array string or list for pipeline."""
    return await _collection_aggregate("projectState", pipeline_json)

@tool
async def aggregate_page(pipeline_json: Union[str, list, None] = None) -> str:
    """Run an aggregation pipeline on page. Provide a JSON array string or list for pipeline."""
    return await _collection_aggregate("page", pipeline_json)

@tool
async def aggregate_cycle(pipeline_json: Union[str, list, None] = None) -> str:
    """Run an aggregation pipeline on cycle. Provide a JSON array string or list for pipeline."""
    return await _collection_aggregate("cycle", pipeline_json)

@tool
async def aggregate_module(pipeline_json: Union[str, list, None] = None) -> str:
    """Run an aggregation pipeline on module. Provide a JSON array string or list for pipeline."""
    return await _collection_aggregate("module", pipeline_json)

@tool
async def aggregate_project(pipeline_json: Union[str, list, None] = None) -> str:
    """Run an aggregation pipeline on project. Provide a JSON array string or list for pipeline."""
    return await _collection_aggregate("project", pipeline_json)

@tool
async def aggregate_work_item(pipeline_json: Union[str, list, None] = None) -> str:
    """Run an aggregation pipeline on workItem. Provide a JSON array string or list for pipeline."""
    return await _collection_aggregate("workItem", pipeline_json)

# ------------------------------
# Multi-step cross-collection plan tool
# ------------------------------
@tool
async def execute_multi_collection_plan(plan_json: Union[str, list, None]) -> str:
    """Execute a sequential multi-step plan across collections. USE THIS for complex queries that require multiple database operations.

    Examples of when to use:
    - "How many active work items in cycles?"
    - "Find projects and their work items"
    - "Get cycle details and count work items per cycle"
    - Any query requiring data from multiple collections

    The plan_json must be a JSON array of steps. Each step is an object like:
    {"op":"find|aggregate", "collection":"project|workItem|cycle|...",
     "args": {"filter": {...}, "projection": {...}, "sort": {...}, "limit": 50} // for find
     or {"pipeline": [...]} // for aggregate }

    Returns a JSON array of step results in order.
    """
    try:
        steps = _parse_json_array(plan_json, [])
        outputs = []
        for step in steps:
            if not isinstance(step, dict):
                outputs.append({"error": "Invalid step format"})
                continue
            op = step.get("op")
            collection = step.get("collection")
            args = step.get("args", {})
            if op == "find":
                result = await _collection_find(
                    collection=collection,
                    filter_json=json.dumps(args.get("filter", {})) if isinstance(args.get("filter"), (dict, list)) else args.get("filter"),
                    projection_json=json.dumps(args.get("projection", {})) if isinstance(args.get("projection"), (dict, list)) else args.get("projection"),
                    sort_json=json.dumps(args.get("sort", {})) if isinstance(args.get("sort"), (dict, list)) else args.get("sort"),
                    limit=args.get("limit", 50),
                )
                outputs.append(result)
            elif op == "aggregate":
                pipeline_arg = args.get("pipeline", [])
                pipeline_json = json.dumps(pipeline_arg) if isinstance(pipeline_arg, (dict, list)) else pipeline_arg
                result = await _collection_aggregate(collection=collection, pipeline_json=pipeline_json)
                outputs.append(result)
            else:
                outputs.append({"error": f"Unsupported op: {op}"})
        return json.dumps(outputs)
    except Exception as e:
        return f"❌ Error executing multi-collection plan: {str(e)}"

# Define the tools list with ProjectManagement-specific readonly tools
tools = [
    get_project_overview,
    get_work_item_insights,
    get_team_productivity,
    get_project_timeline,
    get_business_insights,
    search_projects_by_status,
    get_work_item_by_priority,
    get_member_workload,
    search_projects_by_name,
    count_work_items_by_project,
    get_project_work_item_details,
    get_total_project_count,
    get_total_work_item_count,
    list_all_projects,
    get_work_items_breakdown_by_project,
    # Generic find tools
    query_project_state,
    query_page,
    query_cycle,
    query_module,
    query_project,
    query_work_item,
    # Generic aggregate tools
    aggregate_project_state,
    aggregate_page,
    aggregate_cycle,
    aggregate_module,
    aggregate_project,
    aggregate_work_item,
    # Multi-step planner
    execute_multi_collection_plan,
]
