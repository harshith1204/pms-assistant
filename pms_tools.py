from langchain_core.tools import tool
from typing import Optional
import constants

mongodb_tools = constants.mongodb_tools
DATABASE_NAME = constants.DATABASE_NAME

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
]
