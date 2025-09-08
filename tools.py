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


# Define ProjectManagement-specific readonly insight tools
@tool
async def get_project_overview() -> str:
    """Returns comprehensive project status distribution with counts and project names by status.

    USE THIS TOOL WHEN:
    - User asks for project portfolio overview or status summary
    - Questions like "How are projects distributed?", "What's the project status breakdown?"
    - Need high-level project portfolio analysis across all statuses
    - Want to see which projects are in each status (STARTED, COMPLETED, etc.)

    Returns formatted analysis with project counts by status and specific project names."""
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
    """Returns detailed task distribution analysis by project, status, and priority.

    USE THIS TOOL WHEN:
    - User asks about task/work item distribution or workload analysis
    - Questions like "How are tasks distributed?", "What's the priority breakdown?"
    - Need to understand workload allocation across different projects
    - Want to analyze task status distribution (TODO, IN_PROGRESS, COMPLETED, etc.)
    - Analyzing priority levels (HIGH, MEDIUM, LOW) across the organization

    Returns aggregated analysis showing task counts grouped by project, status, and priority."""
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
    """Returns comprehensive team member workload analysis with task counts and project assignments.

    USE THIS TOOL WHEN:
    - User asks about team productivity, workload, or resource allocation
    - Questions like "How busy is the team?", "Who's working on what?", "Team workload analysis"
    - Need to assess resource distribution across projects
    - Want to see individual team member task counts and project assignments
    - Planning resource allocation or identifying overloaded/underutilized team members

    Returns analysis showing each team member's total tasks, completed tasks, and project involvement."""
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
    """Returns the 20 most recent project activities and events sorted by timestamp.

    USE THIS TOOL WHEN:
    - User asks about recent project activity or timeline
    - Questions like "What's been happening lately?", "Recent project updates?", "Timeline of changes"
    - Need to track recent project events and changes
    - Want to see chronological activity across all projects
    - Monitoring project progress and recent developments

    Returns chronological list of recent project activities and events."""
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
    """Returns business unit performance analysis with project counts and status breakdowns.

    USE THIS TOOL WHEN:
    - User asks about business unit performance or organizational analysis
    - Questions like "How are business units performing?", "Project distribution by business unit?"
    - Need to analyze performance across different business units
    - Want to see active vs completed projects by business unit
    - Evaluating organizational project portfolio distribution

    Returns analysis showing each business unit's total projects, active projects, and completion status."""
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
    """Returns up to 10 projects that match a specific status.

    USE THIS TOOL WHEN:
    - User asks to filter or find projects by specific status
    - Questions like "Show me all STARTED projects", "Find COMPLETED projects", "What projects are in PLANNING?"
    - Need to see projects in a particular state (STARTED, COMPLETED, PLANNING, etc.)
    - Want to focus analysis on projects with specific status

    Args:
        status: The project status to filter by (e.g., "STARTED", "COMPLETED", "PLANNING")

    Returns list of projects matching the specified status with their details."""
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
    """Returns up to 10 most recent work items that match a specific priority level.

    USE THIS TOOL WHEN:
    - User asks about tasks by priority level or critical tasks
    - Questions like "Show me HIGH priority tasks", "What urgent tasks do we have?", "Find MEDIUM priority items"
    - Need to identify critical or high-priority work items
    - Want to focus on tasks with specific priority (HIGH, MEDIUM, LOW)
    - Analyzing priority distribution for planning or resource allocation

    Args:
        priority: The priority level to filter by (e.g., "HIGH", "MEDIUM", "LOW")

    Returns recent work items matching the specified priority level."""
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
    """Returns detailed workload analysis for a specific team member or all team members.

    USE THIS TOOL WHEN:
    - User asks about individual team member workload or performance
    - Questions like "How busy is John?", "What's Sarah's workload?", "Show me everyone's workload"
    - Need to track individual performance and task completion status
    - Want to see completed vs in-progress tasks for team members
    - Analyzing resource utilization and task distribution per person

    Args:
        email: Optional email address of specific team member. If not provided, returns analysis for all members.

    Returns workload analysis including total tasks, completed tasks, and in-progress tasks."""
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
    """Returns up to 10 projects that match a search term in their name (case-insensitive).

    USE THIS TOOL WHEN:
    - User asks to find or search for projects by name
    - Questions like "Find projects with 'mobile' in the name", "Show me 'API' projects", "Search for 'dashboard' projects"
    - Need to locate specific projects by partial name matching
    - Want to discover projects containing certain keywords or themes
    - Looking for projects with similar names or related terms

    Args:
        name: Search term to match against project names (supports partial matching)

    Returns list of projects whose names contain the search term."""
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
    """Returns the total number of work items (tasks) associated with a specific PROJECT (not module).

    USE THIS TOOL WHEN:
    - User asks about project size or task count for a specific PROJECT
    - Questions like "How many tasks are in the mobile app project?", "What's the task count for API project?"
    - User mentions "project" specifically (not "module")
    - Need to assess PROJECT complexity by task volume
    - Want to compare PROJECT sizes or workload estimates
    - Analyzing PROJECT scope and task distribution

    DO NOT USE THIS TOOL WHEN:
    - User mentions "module" (use count_work_items_by_module instead)
    - Question contains "module" keyword

    Args:
        project_name: Name of the PROJECT to count work items for (supports partial matching)

    Returns total work item count for the specified project."""
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
    """Returns detailed breakdown of work items for a specific project including status distribution and percentages.

    USE THIS TOOL WHEN:
    - User asks for detailed task analysis of a specific project
    - Questions like "Show me task breakdown for mobile project", "What's the status distribution in API project?"
    - Need comprehensive analysis of project task status (TODO, IN_PROGRESS, COMPLETED, etc.)
    - Want to see task completion percentages and status distribution
    - Analyzing project progress through task status breakdown

    Args:
        project_name: Name of the project to analyze (supports partial matching)

    Returns detailed task breakdown with counts and percentages by status."""
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
    """Returns the total number of projects in the system across all statuses.

    USE THIS TOOL WHEN:
    - User asks for total project count or portfolio size
    - Questions like "How many total projects are there?", "What's the total project count?", "How many projects do we have?"
    - Need to know the overall scope of the project portfolio
    - Want a simple count of all projects regardless of status
    - Answering basic portfolio size questions

    Returns the total count of all projects in the system."""
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
    """Returns the total number of work items (tasks) across all projects in the system.

    USE THIS TOOL WHEN:
    - User asks for total task count or overall workload
    - Questions like "How many total tasks are there?", "What's the total work item count?", "How many tasks do we have overall?"
    - Need to understand the total scope of work across the organization
    - Want a simple count of all tasks regardless of project or status
    - Assessing overall organizational workload capacity

    Returns the total count of all work items across all projects."""
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
    """Returns a comprehensive list of all projects with their key details including status, lead, and business unit.

    USE THIS TOOL WHEN:
    - User asks to see all projects or complete project list
    - Questions like "List all projects", "Show me all projects", "What projects do we have?", "Project catalog"
    - Need to browse through all available projects
    - Want to see project details including status, project lead, and business unit
    - Creating project inventories or overviews

    Returns formatted list of all projects with their status, lead, business unit, and other key information."""
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
    """Returns a comprehensive breakdown of work items for each project, including status distribution and totals.

    USE THIS TOOL WHEN:
    - User asks for work item breakdown across all projects
    - Questions like "Give me a breakdown of work items for each project", "Task distribution by project", "Project workload comparison"
    - Need to compare project sizes and task distributions
    - Want to see status breakdown (TODO, IN_PROGRESS, COMPLETED) for each project
    - Analyzing project complexity and progress across the portfolio

    Returns detailed analysis showing each project's total work items and status breakdown."""
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

@tool
async def get_cycle_overview() -> str:
    """Returns cycle (sprint) status distribution with counts and cycle details across all projects.

    USE THIS TOOL WHEN:
    - User asks about sprint or cycle status across projects
    - Questions like "How are cycles distributed?", "Sprint status overview", "Cycle progress summary"
    - Need to understand agile development cycles and their status
    - Want to see which cycles are ACTIVE, COMPLETED, UPCOMING, etc.
    - Analyzing sprint planning and execution across the organization

    Returns distribution of cycles by status with cycle details including project assignments."""
    try:
        result = await mongodb_tools.execute_tool("aggregate", {
            "database": DATABASE_NAME,
            "collection": "cycle",
            "pipeline": [
                {
                    "$group": {
                        "_id": "$status",
                        "count": {"$sum": 1},
                        "cycles": {"$push": {"title": "$title", "project": "$project", "startDate": "$startDate", "endDate": "$endDate"}}
                    }
                },
                {
                    "$sort": {"count": -1}
                }
            ]
        })
        return f"🔄 CYCLE STATUS OVERVIEW:\n{result}"
    except Exception as e:
        return f"❌ Error getting cycle overview: {str(e)}"

@tool
async def get_active_cycles() -> str:
    """Returns all currently active cycles (sprints) with their detailed information.

    USE THIS TOOL WHEN:
    - User asks about ongoing or current sprints
    - Questions like "What cycles are active?", "Show me current sprints", "Ongoing sprint details"
    - Need to track active development cycles across projects
    - Want to see which projects have active sprints running
    - Monitoring current sprint progress and timelines

    Returns list of all active cycles with their project, start/end dates, and other details."""
    try:
        result = await mongodb_tools.execute_tool("find", {
            "database": DATABASE_NAME,
            "collection": "cycle",
            "filter": {"status": "ACTIVE"},
            "sort": {"startDate": -1},
            "limit": 20
        })
        return f"⚡ ACTIVE CYCLES:\n{result}"
    except Exception as e:
        return f"❌ Error getting active cycles: {str(e)}"

@tool
async def get_module_overview() -> str:
    """Returns module status distribution and lead assignments across all projects.

    USE THIS TOOL WHEN:
    - User asks about module organization or structure
    - Questions like "How are modules distributed?", "Module status overview", "Module portfolio analysis"
    - Need to understand module organization within projects
    - Want to see module leads and their assignments
    - Analyzing module state distribution (ACTIVE, COMPLETED, etc.) across projects

    Returns analysis of modules grouped by project and state, including lead assignments."""
    try:
        result = await mongodb_tools.execute_tool("aggregate", {
            "database": DATABASE_NAME,
            "collection": "module",
            "pipeline": [
                {
                    "$lookup": {
                        "from": "project",
                        "localField": "project._id",
                        "foreignField": "_id",
                        "as": "project_info"
                    }
                },
                {
                    "$group": {
                        "_id": {
                            "project": {"$arrayElemAt": ["$project_info.name", 0]},
                            "state": "$state.name"
                        },
                        "count": {"$sum": 1},
                        "modules": {"$push": {"title": "$title", "lead": "$lead.name"}}
                    }
                },
                {
                    "$sort": {"count": -1}
                }
            ]
        })
        return f"📦 MODULE OVERVIEW:\n{result}"
    except Exception as e:
        return f"❌ Error getting module overview: {str(e)}"

@tool
async def get_project_states() -> str:
    """Returns all project states and their sub-states for workflow management across projects.

    USE THIS TOOL WHEN:
    - User asks about project workflow states or state management
    - Questions like "What are the project states?", "Show me workflow states", "Project state definitions"
    - Need to understand project lifecycle and state transitions
    - Want to see state configurations and sub-states for each project
    - Analyzing workflow definitions and state management

    Returns comprehensive list of project states with their sub-states and project associations."""
    try:
        result = await mongodb_tools.execute_tool("aggregate", {
            "database": DATABASE_NAME,
            "collection": "projectState",
            "pipeline": [
                {
                    "$lookup": {
                        "from": "project",
                        "localField": "projectId",
                        "foreignField": "_id",
                        "as": "project_info"
                    }
                },
                {
                    "$project": {
                        "project_name": {"$arrayElemAt": ["$project_info.name", 0]},
                        "state_name": "$name",
                        "icon": "$icon",
                        "sub_states": "$subStates"
                    }
                },
                {
                    "$sort": {"project_name": 1, "state_name": 1}
                }
            ]
        })
        return f"🔄 PROJECT STATES & WORKFLOWS:\n{result}"
    except Exception as e:
        return f"❌ Error getting project states: {str(e)}"

@tool
async def get_team_member_roles() -> str:
    """Returns team member role distribution and counts across different projects.

    USE THIS TOOL WHEN:
    - User asks about team roles or role distribution
    - Questions like "What roles do we have?", "Team role breakdown", "Role distribution across projects"
    - Need to understand team composition and role allocation
    - Want to see which roles are assigned to which projects
    - Analyzing team structure and role assignments

    Returns analysis of team member roles with counts and project assignments."""
    try:
        result = await mongodb_tools.execute_tool("aggregate", {
            "database": DATABASE_NAME,
            "collection": "members",
            "pipeline": [
                {
                    "$group": {
                        "_id": {
                            "role": "$role",
                            "project": "$project.name"
                        },
                        "count": {"$sum": 1},
                        "members": {"$push": {"name": "$name", "email": "$email"}}
                    }
                },
                {
                    "$sort": {"_id.role": 1, "count": -1}
                }
            ]
        })
        return f"👥 TEAM MEMBER ROLES:\n{result}"
    except Exception as e:
        return f"❌ Error getting team member roles: {str(e)}"

@tool
async def get_upcoming_cycles() -> str:
    """Returns all upcoming cycles (sprints) sorted by their start date.

    USE THIS TOOL WHEN:
    - User asks about future sprints or upcoming cycles
    - Questions like "What cycles are coming up?", "Future sprint schedule", "Upcoming sprint planning"
    - Need to plan for upcoming development cycles
    - Want to see sprint timelines and start dates
    - Preparing for sprint planning and resource allocation

    Returns list of upcoming cycles sorted by start date with their project and timeline information."""
    try:
        result = await mongodb_tools.execute_tool("find", {
            "database": DATABASE_NAME,
            "collection": "cycle",
            "filter": {"status": "UPCOMING"},
            "sort": {"startDate": 1},
            "limit": 15
        })
        return f"📅 UPCOMING CYCLES:\n{result}"
    except Exception as e:
        return f"❌ Error getting upcoming cycles: {str(e)}"

@tool
async def get_module_leads() -> str:
    """Returns module lead distribution, workload analysis, and project assignments.

    USE THIS TOOL WHEN:
    - User asks about module leadership or lead assignments
    - Questions like "Who are the module leads?", "Module lead workload", "Lead distribution analysis"
    - Need to understand leadership structure across modules
    - Want to see which leads are responsible for which modules and projects
    - Analyzing lead workload and module assignment distribution

    Returns analysis of module leads with their module count, project assignments, and workload details."""
    try:
        result = await mongodb_tools.execute_tool("aggregate", {
            "database": DATABASE_NAME,
            "collection": "module",
            "pipeline": [
                {
                    "$match": {"lead": {"$exists": True}}
                },
                {
                    "$group": {
                        "_id": "$lead.name",
                        "module_count": {"$sum": 1},
                        "projects": {"$addToSet": "$project"},
                        "modules": {"$push": {"title": "$title", "project": "$project"}}
                    }
                },
                {
                    "$sort": {"module_count": -1}
                }
            ]
        })
        return f"👨‍💼 MODULE LEADS WORKLOAD:\n{result}"
    except Exception as e:
        return f"❌ Error getting module leads: {str(e)}"

@tool
async def count_work_items_by_module(module_name: str) -> str:
    """Returns the total number of work items (tasks) associated with a specific module.

    USE THIS TOOL WHEN:
    - User asks about work item count for a specific module (not project)
    - Questions like "How many tasks are in CRM module?", "What's the task count for API module?"
    - Need to count work items specifically within a module context
    - User mentions "module" specifically rather than "project"
    - Want module-level task counting and workload assessment

    Args:
        module_name: Name of the module to count work items for (supports partial matching)

    Returns total work item count for the specified module."""
    try:
        # First find modules matching the name to get their project associations
        module_result = await mongodb_tools.execute_tool("find", {
            "database": DATABASE_NAME,
            "collection": "module",
            "filter": {"title": {"$regex": module_name, "$options": "i"}},
            "projection": {"project": 1, "title": 1},
            "limit": 10
        })

        # Parse module results to get associated projects
        import json
        module_projects = []
        if isinstance(module_result, list) and len(module_result) > 1:
            for item in module_result[1:]:  # Skip first element (message)
                if isinstance(item, str):
                    try:
                        module_data = json.loads(item)
                        if "project" in module_data:
                            project_id = module_data["project"].get("$binary", {}).get("base64") if isinstance(module_data["project"], dict) else None
                            if project_id:
                                module_projects.append(project_id)
                    except json.JSONDecodeError:
                        continue

        if not module_projects:
            # If no modules found, try searching work items directly for module references
            result = await mongodb_tools.execute_tool("aggregate", {
                "database": DATABASE_NAME,
                "collection": "workItem",
                "pipeline": [
                    {
                        "$match": {
                            "$or": [
                                {"module.title": {"$regex": module_name, "$options": "i"}},
                                {"module.name": {"$regex": module_name, "$options": "i"}},
                                {"title": {"$regex": module_name, "$options": "i"}}
                            ]
                        }
                    },
                    {
                        "$count": "total_work_items"
                    }
                ]
            })
        else:
            # Count work items for projects that have matching modules
            result = await mongodb_tools.execute_tool("aggregate", {
                "database": DATABASE_NAME,
                "collection": "workItem",
                "pipeline": [
                    {
                        "$match": {
                            "project._id": {"$in": module_projects}
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
                    return f"📊 WORK ITEMS IN '{module_name.upper()}' MODULE:\nTotal: {total} work items"
                return f"📊 WORK ITEMS IN '{module_name.upper()}' MODULE (raw):\n{data}"

        if isinstance(data, list) and len(data) > 0:
            first_item = data[0]
            if isinstance(first_item, dict):
                total = int(first_item.get("total_work_items", 0))
            else:
                return f"📊 WORK ITEMS IN '{module_name.upper()}' MODULE (raw):\n{data}"
        elif isinstance(data, dict):
            total = int(data.get("total_work_items", 0))
        elif isinstance(data, int):
            total = data
        else:
            return f"📊 WORK ITEMS IN '{module_name.upper()}' MODULE (raw):\n{data}"

        return f"📊 WORK ITEMS IN '{module_name.upper()}' MODULE:\nTotal: {total} work items"

    except Exception as e:
        return f"❌ Error counting work items for module '{module_name}': {str(e)}"

@tool
async def get_work_items_for_active_cycles() -> str:
    """Returns all work items (tasks, stories, bugs) that belong to currently active cycles (sprints).

    USE THIS TOOL WHEN:
    - User asks about work items in active cycles or current sprints
    - Questions like "What tasks are in active cycles?", "Show me work items for current sprints", "Active cycle tasks"
    - Need to see what work is currently being done across all active development cycles
    - Want to understand the current workload and progress in active sprints
    - Analyzing task distribution across active cycles

    Returns work items grouped by their active cycle, showing task details like title, status, priority, assignee, and cycle information."""
    try:
        # First get all active cycles
        active_cycles_result = await mongodb_tools.execute_tool("find", {
            "database": DATABASE_NAME,
            "collection": "cycle",
            "filter": {"status": "ACTIVE"},
            "projection": {"_id": 1, "title": 1, "project": 1, "startDate": 1, "endDate": 1}
        })

        # Parse active cycles to get their IDs
        import json
        active_cycle_ids = []
        cycle_info = {}

        if isinstance(active_cycles_result, list) and len(active_cycles_result) > 1:
            for item in active_cycles_result[1:]:  # Skip first element (message)
                if isinstance(item, str):
                    try:
                        cycle_data = json.loads(item)
                        cycle_id = cycle_data.get("_id", {}).get("$binary", {}).get("base64")
                        if cycle_id:
                            active_cycle_ids.append(cycle_id)
                            cycle_info[cycle_id] = {
                                "title": cycle_data.get("title", "Unknown"),
                                "project": cycle_data.get("project", {}).get("name", "Unknown"),
                                "startDate": cycle_data.get("startDate", {}).get("$date") if cycle_data.get("startDate") else None,
                                "endDate": cycle_data.get("endDate", {}).get("$date") if cycle_data.get("endDate") else None
                            }
                    except json.JSONDecodeError:
                        continue

        if not active_cycle_ids:
            return "⚡ ACTIVE CYCLES WORK ITEMS:\nNo active cycles found."

        # Now get work items for these active cycles
        work_items_result = await mongodb_tools.execute_tool("aggregate", {
            "database": DATABASE_NAME,
            "collection": "workItem",
            "pipeline": [
                {
                    "$match": {
                        "cycle._id.$binary.base64": {"$in": active_cycle_ids}
                    }
                },
                {
                    "$lookup": {
                        "from": "project",
                        "localField": "project._id",
                        "foreignField": "_id",
                        "as": "project_info"
                    }
                },
                {
                    "$sort": {"updatedTimeStamp": -1}
                }
            ]
        })

        # Format the results
        output_lines = ["⚡ ACTIVE CYCLES WORK ITEMS:\n"]

        # Group work items by cycle
        cycle_work_items = {}

        if isinstance(work_items_result, list) and len(work_items_result) > 1:
            for item in work_items_result[1:]:  # Skip first element (message)
                if isinstance(item, str):
                    try:
                        work_item = json.loads(item)
                        cycle_id = work_item.get("cycle", {}).get("_id", {}).get("$binary", {}).get("base64")

                        if cycle_id and cycle_id in cycle_info:
                            if cycle_id not in cycle_work_items:
                                cycle_work_items[cycle_id] = []

                            project_name = work_item.get("project", {}).get("name", "Unknown")
                            if work_item.get("project_info") and len(work_item["project_info"]) > 0:
                                project_name = work_item["project_info"][0].get("name", project_name)

                            work_item_summary = {
                                "id": work_item.get("displayBugNo", work_item.get("_id", {}).get("$binary", {}).get("base64", "Unknown")),
                                "title": work_item.get("title", "No Title"),
                                "status": work_item.get("status", "Unknown"),
                                "priority": work_item.get("priority", "NONE"),
                                "state": work_item.get("state", {}).get("name", "Unknown"),
                                "assignee": [assignee.get("name", "Unknown") for assignee in work_item.get("assignee", [])] if work_item.get("assignee") else [],
                                "project": project_name
                            }
                            cycle_work_items[cycle_id].append(work_item_summary)
                    except json.JSONDecodeError:
                        continue

        # Generate formatted output
        if cycle_work_items:
            for cycle_id, work_items in cycle_work_items.items():
                cycle_data = cycle_info[cycle_id]
                output_lines.append(f"🏃 ACTIVE CYCLE: {cycle_data['title']}")
                output_lines.append(f"   📁 Project: {cycle_data['project']}")
                if cycle_data['startDate']:
                    output_lines.append(f"   📅 Start: {cycle_data['startDate'][:10] if len(cycle_data['startDate']) > 10 else cycle_data['startDate']}")
                if cycle_data['endDate']:
                    output_lines.append(f"   🎯 End: {cycle_data['endDate'][:10] if len(cycle_data['endDate']) > 10 else cycle_data['endDate']}")
                output_lines.append(f"   📊 Work Items: {len(work_items)}")
                output_lines.append("")

                for item in work_items[:10]:  # Limit to 10 items per cycle for readability
                    output_lines.append(f"   • [{item['id']}] {item['title']}")
                    output_lines.append(f"     Status: {item['state']} | Priority: {item['priority']}")
                    if item['assignee']:
                        output_lines.append(f"     👤 Assigned to: {', '.join(item['assignee'])}")
                    output_lines.append("")

                if len(work_items) > 10:
                    output_lines.append(f"   ... and {len(work_items) - 10} more work items")
                    output_lines.append("")

                output_lines.append("─" * 60)
                output_lines.append("")
        else:
            output_lines.append("No work items found in active cycles.")

        return "\n".join(output_lines)

    except Exception as e:
        return f"❌ Error getting work items for active cycles: {str(e)}"

@tool
async def traverse_relationships(start_collection: str, start_filters: Dict[str, Any], relationship_path: List[str], projection: List[str] = None, limit: int = 20) -> str:
    """Traverse relationships across collections using the relationship registry to build complex queries.

    USE THIS TOOL WHEN:
    - User asks for complex queries spanning multiple related collections
    - Questions like "Show me work items for project X with their states", "Get pages linked to cycles in project Y", "Find members working on modules in project Z"
    - Need to follow relationship chains defined in the registry
    - Want to combine data from multiple related collections in a single query
    - Analyzing relationships between different entities (projects, work items, cycles, pages, etc.)

    Args:
        start_collection: The collection to start the query from (e.g., "project", "workItem", "cycle")
        start_filters: Filters to apply to the starting collection (e.g., {"name": {"$regex": "mobile", "$options": "i"}})
        relationship_path: List of relationship names to traverse (e.g., ["workItems", "stateMaster"] for project->workItems->states)
        projection: List of fields to include in results (will be validated against allowed fields)
        limit: Maximum number of results to return (default: 20)

    Returns complex query results across related collections following the defined relationship paths."""
    try:
        if start_collection not in REL:
            return f"❌ Invalid start collection '{start_collection}'. Valid collections: {list(REL.keys())}"

        current_collection = start_collection
        pipeline = []

        # Start with filtering the initial collection
        if start_filters:
            pipeline.append({"$match": start_filters})

        # Traverse the relationship path
        for relation_name in relationship_path:
            if current_collection not in REL or relation_name not in REL[current_collection]:
                available_relations = list(REL.get(current_collection, {}).keys())
                return f"❌ Invalid relationship '{relation_name}' from '{current_collection}'. Available: {available_relations}"

            relationship = REL[current_collection][relation_name]
            target_collection = relationship["target"]

            # Build lookup stage for this relationship
            lookup_stage = build_lookup_stage(target_collection, relationship)
            pipeline.append(lookup_stage)

            # Unwind the results if it's a single relationship (not many-to-many)
            if "join" in relationship:
                pipeline.append({"$unwind": {"path": f"${target_collection}", "preserveNullAndEmptyArrays": True}})

            current_collection = target_collection

        # Add projection if specified
        if projection:
            validated_projection = validate_fields(start_collection, projection)
            if validated_projection:
                proj_dict = {field: 1 for field in validated_projection}
                # Always include _id unless explicitly excluded
                if "_id" not in proj_dict and "_id" not in [f for f in projection if f.startswith("-")]:
                    proj_dict["_id"] = 1
                pipeline.append({"$project": proj_dict})

        # Add limit
        pipeline.append({"$limit": limit})

        # Execute the aggregation
        result = await mongodb_tools.execute_tool("aggregate", {
            "database": DATABASE_NAME,
            "collection": start_collection,
            "pipeline": pipeline
        })

        return f"🔗 RELATIONSHIP QUERY RESULTS:\nStart: {start_collection}\nPath: {' -> '.join(relationship_path)}\n{result}"

    except Exception as e:
        return f"❌ Error traversing relationships: {str(e)}"

@tool
async def get_project_with_related_data(project_name: str, include_relations: List[str] = None, limit: int = 10) -> str:
    """Get comprehensive project data with related entities using the relationship registry.

    USE THIS TOOL WHEN:
    - User wants to see a project with all its related data (work items, cycles, members, pages, modules)
    - Questions like "Show me everything about project X", "Get full project details including work items and cycles"
    - Need to understand project scope and all associated entities
    - Want to see project context with related entities

    Args:
        project_name: Name of the project to query (supports partial matching)
        include_relations: List of relationships to include (e.g., ["workItems", "cycles", "members"])
        limit: Maximum number of related items to show per relationship

    Returns comprehensive project data with selected related entities."""
    try:
        # Default relations if none specified
        if not include_relations:
            include_relations = ["workItems", "cycles", "members", "pages", "modules"]

        # Build pipeline starting with project filter
        pipeline = [
            {"$match": {"name": {"$regex": project_name, "$options": "i"}}}
        ]

        # Add lookups for each requested relationship
        for relation_name in include_relations:
            if relation_name in REL["project"]:
                relationship = REL["project"][relation_name]
                target_collection = relationship["target"]

                lookup_stage = build_lookup_stage(target_collection, relationship)
                pipeline.append(lookup_stage)

                # Limit related items for readability
                pipeline.append({
                    "$project": {
                        **{field: 1 for field in ALLOWED_FIELDS["project"]},
                        target_collection: {"$slice": [f"${target_collection}", limit]}
                    }
                })

        pipeline.append({"$limit": 5})  # Limit projects returned

        result = await mongodb_tools.execute_tool("aggregate", {
            "database": DATABASE_NAME,
            "collection": "project",
            "pipeline": pipeline
        })

        return f"📊 COMPREHENSIVE PROJECT DATA:\nProject: {project_name}\nRelations: {', '.join(include_relations)}\n{result}"

    except Exception as e:
        return f"❌ Error getting project with related data: {str(e)}"

@tool
async def get_work_items_for_upcoming_cycles(limit: int = 20) -> str:
    """Get work items that belong to upcoming cycles with full context.

    USE THIS TOOL WHEN:
    - User asks for work items in upcoming cycles or sprints
    - Questions like "Show me work items for upcoming cycles", "What tasks are in future sprints?"
    - Need to see work items planned for upcoming development cycles
    - Want to understand upcoming workload and sprint planning

    Args:
        limit: Maximum number of work items to return

    Returns work items for upcoming cycles with project and state information."""
    try:
        pipeline = [
            # First lookup cycles to get cycle status
            {
                "$lookup": {
                    "from": "cycle",
                    "localField": "cycle._id",
                    "foreignField": "_id",
                    "as": "cycle_info"
                }
            },
            # Filter for upcoming cycles only
            {
                "$match": {
                    "cycle_info": {"$ne": []},  # Has cycle
                    "cycle_info.status": "UPCOMING"
                }
            },
            # Unwind cycle info
            {"$unwind": {"path": "$cycle_info", "preserveNullAndEmptyArrays": False}},
            # Lookup project info
            {
                "$lookup": {
                    "from": "project",
                    "localField": "project._id",
                    "foreignField": "_id",
                    "as": "project_info"
                }
            },
            {"$unwind": {"path": "$project_info", "preserveNullAndEmptyArrays": True}},
            # Lookup state info
            {
                "$lookup": {
                    "from": "projectState",
                    "localField": "state._id",
                    "foreignField": "subStates._id",
                    "as": "state_info"
                }
            },
            {"$unwind": {"path": "$state_info", "preserveNullAndEmptyArrays": True}},
            # Project relevant fields
            {
                "$project": {
                    "_id": 1,
                    "displayBugNo": 1,
                    "title": 1,
                    "status": 1,
                    "priority": 1,
                    "project_name": "$project_info.name",
                    "cycle_title": "$cycle_info.title",
                    "cycle_status": "$cycle_info.status",
                    "state_name": "$state_info.name",
                    "createdTimeStamp": 1
                }
            },
            {"$limit": limit}
        ]

        result = await mongodb_tools.execute_tool("aggregate", {
            "database": DATABASE_NAME,
            "collection": "workItem",
            "pipeline": pipeline
        })

        return f"📅 WORK ITEMS FOR UPCOMING CYCLES:\n{result}"

    except Exception as e:
        return f"❌ Error getting work items for upcoming cycles: {str(e)}"

@tool
async def get_work_items_with_context(work_item_filters: Dict[str, Any] = None, include_context: List[str] = None, limit: int = 20) -> str:
    """Get work items with their full context from related collections.

    USE THIS TOOL WHEN:
    - User wants to see work items with project, state, cycle, and module information
    - Questions like "Show me work items with their states", "Get tasks with full project context", "Work items and their cycles"
    - Need to understand work item context across multiple dimensions
    - Want to see work item relationships and dependencies

    Args:
        work_item_filters: Filters to apply to work items (e.g., {"status": "TODO", "priority": "HIGH"})
        include_context: List of related entities to include (e.g., ["project", "stateMaster"])
        limit: Maximum number of work items to return

    Returns work items with their related context data."""
    try:
        # Default context if none specified
        if not include_context:
            include_context = ["project", "stateMaster"]

        # Start with work item filters
        pipeline = []
        if work_item_filters:
            pipeline.append({"$match": work_item_filters})

        # Add context lookups - handle potential field conflicts
        for context_name in include_context:
            if context_name in REL["workItem"]:
                relationship = REL["workItem"][context_name]
                target_collection = relationship["target"]

                # Use different field names to avoid conflicts
                lookup_stage = build_lookup_stage(target_collection, relationship)
                # Rename the lookup result to avoid conflicts
                if "join" in relationship:
                    lookup_stage["$lookup"]["as"] = f"{context_name}_info"

                pipeline.append(lookup_stage)

                # For single relationships, unwind
                if "join" in relationship:
                    pipeline.append({"$unwind": {"path": f"${context_name}_info", "preserveNullAndEmptyArrays": True}})

        # Project relevant fields - avoid field name conflicts
        projection = {
            field: 1 for field in ALLOWED_FIELDS["workItem"]
        }
        # Add context fields with renamed fields to avoid conflicts
        for context in include_context:
            if context in REL["workItem"] and "join" in REL["workItem"][context]:
                projection[f"{context}_info"] = 1

        pipeline.append({"$project": projection})
        pipeline.append({"$limit": limit})

        result = await mongodb_tools.execute_tool("aggregate", {
            "database": DATABASE_NAME,
            "collection": "workItem",
            "pipeline": pipeline
        })

        return f"🎯 WORK ITEMS WITH CONTEXT:\nFilters: {work_item_filters}\nContext: {', '.join(include_context)}\n{result}"

    except Exception as e:
        return f"❌ Error getting work items with context: {str(e)}"

@tool
async def get_pages_with_relationships(page_filters: Dict[str, Any] = None, include_relations: List[str] = None, limit: int = 15) -> str:
    """Get pages with their relationships to cycles, modules, authors, and projects.

    USE THIS TOOL WHEN:
    - User wants to see pages with their linked cycles and modules
    - Questions like "Show me pages linked to cycle X", "Get pages with their authors", "Pages and their modules"
    - Need to understand page relationships and context
    - Want to see how pages connect different entities (cycles, modules, projects)

    Args:
        page_filters: Filters to apply to pages (e.g., {"visibility": "public", "title": {"$regex": "api"}})
        include_relations: List of relationships to include (e.g., ["cycles", "modules", "author", "project"])
        limit: Maximum number of pages to return

    Returns pages with their relationship data."""
    try:
        # Default relations if none specified
        if not include_relations:
            include_relations = ["project", "author", "cycles", "modules"]

        pipeline = []
        if page_filters:
            pipeline.append({"$match": page_filters})

        # Add relationship lookups
        for relation_name in include_relations:
            if relation_name in REL["page"]:
                relationship = REL["page"][relation_name]
                target_collection = relationship["target"]

                lookup_stage = build_lookup_stage(target_collection, relationship)
                pipeline.append(lookup_stage)

                # Handle array relationships (cycles, modules)
                if relation_name in ["cycles", "modules"]:
                    # For array relationships, unwind if needed
                    pass  # Keep as arrays for now
                elif "join" in relationship:
                    pipeline.append({"$unwind": {"path": f"${target_collection}", "preserveNullAndEmptyArrays": True}})

        # Project relevant fields
        projection = {
            field: 1 for field in ALLOWED_FIELDS["page"]
        }
        for relation in include_relations:
            projection[relation] = 1

        pipeline.append({"$project": projection})
        pipeline.append({"$limit": limit})

        result = await mongodb_tools.execute_tool("aggregate", {
            "database": DATABASE_NAME,
            "collection": "page",
            "pipeline": pipeline
        })

        return f"📄 PAGES WITH RELATIONSHIPS:\nFilters: {page_filters}\nRelations: {', '.join(include_relations)}\n{result}"

    except Exception as e:
        return f"❌ Error getting pages with relationships: {str(e)}"

@tool
async def get_cycles_with_pages(cycle_filters: Dict[str, Any] = None, include_pages: bool = True, limit: int = 10) -> str:
    """Get cycles with their linked pages and related project information.

    USE THIS TOOL WHEN:
    - User wants to see cycles with their associated pages
    - Questions like "Show me cycles and their linked pages", "Get sprint pages", "Cycle documentation"
    - Need to understand cycle context and documentation
    - Want to see how cycles connect to pages and projects

    Args:
        cycle_filters: Filters to apply to cycles (e.g., {"status": "ACTIVE"})
        include_pages: Whether to include linked pages (default: True)
        limit: Maximum number of cycles to return

    Returns cycles with their related pages and project information."""
    try:
        pipeline = []
        if cycle_filters:
            pipeline.append({"$match": cycle_filters})

        # Add project lookup
        if "project" in REL["cycle"]:
            project_lookup = build_lookup_stage("project", REL["cycle"]["project"])
            pipeline.append(project_lookup)
            pipeline.append({"$unwind": {"path": "$project", "preserveNullAndEmptyArrays": True}})

        # Add pages lookup if requested
        if include_pages and "pages" in REL["cycle"]:
            pages_lookup = build_lookup_stage("page", REL["cycle"]["pages"])
            pipeline.append(pages_lookup)

        # Project relevant fields
        projection = {
            field: 1 for field in ALLOWED_FIELDS["cycle"]
        }
        projection["project"] = 1
        if include_pages:
            projection["pages"] = 1

        pipeline.append({"$project": projection})
        pipeline.append({"$limit": limit})

        result = await mongodb_tools.execute_tool("aggregate", {
            "database": DATABASE_NAME,
            "collection": "cycle",
            "pipeline": pipeline
        })

        return f"🔄 CYCLES WITH PAGES:\nFilters: {cycle_filters}\nInclude Pages: {include_pages}\n{result}"

    except Exception as e:
        return f"❌ Error getting cycles with pages: {str(e)}"

@tool
async def analyze_cross_collection_metrics(metric_type: str, filters: Dict[str, Any] = None) -> str:
    """Analyze metrics across multiple related collections using the relationship registry.

    USE THIS TOOL WHEN:
    - User wants to analyze metrics spanning multiple collections
    - Questions like "Project workload vs capacity", "Team productivity across projects", "Module coverage analysis"
    - Need to understand relationships between different metrics across collections
    - Want to see correlations between different entities (projects, work items, members, etc.)

    Args:
        metric_type: Type of analysis to perform (e.g., "workload_distribution", "team_productivity", "project_coverage")
        filters: Optional filters to apply to the analysis

    Returns cross-collection metric analysis."""
    try:
        if metric_type == "workload_distribution":
            # Analyze work item distribution across projects and members
            pipeline = [
                # Start with work items
                {
                    "$lookup": {
                        "from": "project",
                        "localField": "project._id",
                        "foreignField": "_id",
                        "as": "project"
                    }
                },
                {"$unwind": {"path": "$project", "preserveNullAndEmptyArrays": True}},
                {
                    "$lookup": {
                        "from": "members",
                        "localField": "assignee._id",
                        "foreignField": "_id",
                        "as": "assignee"
                    }
                },
                {"$unwind": {"path": "$assignee", "preserveNullAndEmptyArrays": True}},
                {
                    "$group": {
                        "_id": {
                            "project": "$project.name",
                            "assignee": "$assignee.name",
                            "status": "$status"
                        },
                        "count": {"$sum": 1}
                    }
                },
                {
                    "$group": {
                        "_id": {
                            "project": "$_id.project",
                            "assignee": "$_id.assignee"
                        },
                        "total_tasks": {"$sum": "$count"},
                        "status_breakdown": {
                            "$push": {
                                "status": "$_id.status",
                                "count": "$count"
                            }
                        }
                    }
                },
                {"$sort": {"total_tasks": -1}}
            ]

            if filters:
                # Apply filters at the beginning if specified
                pipeline.insert(0, {"$match": filters})

        elif metric_type == "team_productivity":
            # Analyze team member productivity across projects
            pipeline = [
                {
                    "$lookup": {
                        "from": "workItem",
                        "localField": "_id",
                        "foreignField": "assignee._id",
                        "as": "tasks"
                    }
                },
                {
                    "$lookup": {
                        "from": "project",
                        "localField": "project._id",
                        "foreignField": "_id",
                        "as": "projects"
                    }
                },
                {
                    "$project": {
                        "name": 1,
                        "email": 1,
                        "role": 1,
                        "task_count": {"$size": "$tasks"},
                        "completed_tasks": {
                            "$size": {
                                "$filter": {
                                    "input": "$tasks",
                                    "as": "task",
                                    "cond": {"$eq": ["$$task.status", "COMPLETED"]}
                                }
                            }
                        },
                        "project_count": {"$size": {"$setUnion": ["$projects._id"]}}
                    }
                },
                {"$sort": {"task_count": -1}}
            ]

        elif metric_type == "project_coverage":
            # Analyze how well projects are covered by modules, cycles, pages
            pipeline = [
                # Start with projects
                {
                    "$lookup": {
                        "from": "module",
                        "localField": "_id",
                        "foreignField": "project._id",
                        "as": "modules"
                    }
                },
                {
                    "$lookup": {
                        "from": "cycle",
                        "localField": "_id",
                        "foreignField": "project._id",
                        "as": "cycles"
                    }
                },
                {
                    "$lookup": {
                        "from": "page",
                        "localField": "_id",
                        "foreignField": "project._id",
                        "as": "pages"
                    }
                },
                {
                    "$lookup": {
                        "from": "workItem",
                        "localField": "_id",
                        "foreignField": "project._id",
                        "as": "work_items"
                    }
                },
                {
                    "$project": {
                        "name": 1,
                        "status": 1,
                        "module_count": {"$size": "$modules"},
                        "cycle_count": {"$size": "$cycles"},
                        "page_count": {"$size": "$pages"},
                        "work_item_count": {"$size": "$work_items"}
                    }
                },
                {"$sort": {"work_item_count": -1}}
            ]

        else:
            return f"❌ Unknown metric type '{metric_type}'. Supported: workload_distribution, team_productivity, project_coverage"

        result = await mongodb_tools.execute_tool("aggregate", {
            "database": DATABASE_NAME,
            "collection": "project" if metric_type == "project_coverage" else "members" if metric_type == "team_productivity" else "workItem",
            "pipeline": pipeline
        })

        return f"📈 CROSS-COLLECTION METRICS:\nType: {metric_type}\n{result}"

    except Exception as e:
        return f"❌ Error analyzing cross-collection metrics: {str(e)}"

@tool
async def intelligent_query(query: str) -> str:
    """Intelligent query processor that understands natural language and handles any permutation of PMS queries.

    USE THIS TOOL WHEN:
    - User asks complex questions spanning multiple collections
    - Questions involve relationships between projects, work items, cycles, members, etc.
    - Need dynamic query generation based on relationship registry
    - Want to avoid creating individual tools for every query type
    - Questions involve filtering, aggregation, or complex relationships

    This is the SMART tool that replaces the need for hundreds of specific tools by:
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

@tool
async def get_project_workflow_states(project_name: str) -> str:
    """Returns all workflow states and transitions for a specific project.

    USE THIS TOOL WHEN:
    - User asks about workflow states for a particular project
    - Questions like "What are the states for mobile project?", "Show workflow for API project", "Project state transitions"
    - Need to understand project-specific workflow configuration
    - Want to see state definitions and transitions for a specific project
    - Analyzing project lifecycle and state management for individual projects

    Args:
        project_name: Name of the project to get workflow states for (supports partial matching)

    Returns comprehensive list of workflow states specific to the requested project."""
    try:
        # First get project ID
        project_result = await mongodb_tools.execute_tool("find", {
            "database": DATABASE_NAME,
            "collection": "project",
            "filter": {"name": {"$regex": project_name, "$options": "i"}},
            "projection": {"_id": 1},
            "limit": 1
        })

        # Parse project ID from result
        import json
        if isinstance(project_result, list) and len(project_result) > 1:
            try:
                project_data = json.loads(project_result[1])
                project_id = project_data.get("_id", {}).get("$binary", {}).get("base64")
                if project_id:
                    # Get states for this project
                    states_result = await mongodb_tools.execute_tool("find", {
                        "database": DATABASE_NAME,
                        "collection": "projectState",
                        "filter": {"projectId": {"$binary": {"base64": project_id, "subType": "03"}}},
                        "sort": {"name": 1}
                    })
                    return f"🔄 WORKFLOW STATES FOR '{project_name.upper()}':\n{states_result}"
            except:
                pass

        return f"❌ Could not find project '{project_name}' or parse project data"
    except Exception as e:
        return f"❌ Error getting project workflow states: {str(e)}"

# Define the tools list with ProjectManagement-specific readonly tools
tools = [
    # Original tools
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
    count_work_items_by_module,  # NEW: Module-specific work item counting
    get_project_work_item_details,
    get_total_project_count,
    get_total_work_item_count,
    list_all_projects,
    get_work_items_breakdown_by_project,
    # New cycle, module, member, and project state tools
    get_cycle_overview,
    get_active_cycles,
    get_work_items_for_active_cycles,  # NEW: Work items for active cycles
    get_module_overview,
    get_project_states,
    get_team_member_roles,
    get_upcoming_cycles,
    get_module_leads,
    get_project_workflow_states,
    # New relationship-aware tools using the registry
    traverse_relationships,  # Generic relationship traversal
    get_project_with_related_data,  # Comprehensive project data
    get_work_items_for_upcoming_cycles,  # Work items for upcoming cycles
    get_work_items_with_context,  # Work items with full context
    get_pages_with_relationships,  # Pages with relationships
    get_cycles_with_pages,  # Cycles with pages
    analyze_cross_collection_metrics,  # Cross-collection analytics
    # INTELLIGENT QUERY PROCESSOR - THE SMART TOOL
    intelligent_query,  # Handles ANY natural language query dynamically
]
