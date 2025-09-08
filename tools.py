from langchain_core.tools import tool
from typing import Optional, Dict, List, Any, Union
import constants
import os
import json
import re
mongodb_tools = constants.mongodb_tools
DATABASE_NAME = constants.DATABASE_NAME

# Import the registry and intelligent query planner
from registry import ENTITIES, ALIASES, ALLOWED_FIELDS, resolve_field_alias, validate_fields, build_lookup_stage
# Keep REL for backward compatibility with existing tools
try:
    from registry import REL
except ImportError:
    REL = {}

# Import the intelligent query planner
from query_planner import plan_and_execute_query, suggest_pipeline_template, get_pipeline_template, PIPELINE_TEMPLATES

@tool
def intelligent_query(query: str) -> Dict[str, Any]:
    """
    🎯 INTELLIGENT PMS QUERY PROCESSOR - Your Go-To Tool for ANY PMS Question!

    🚀 This tool understands NATURAL LANGUAGE and can handle LITERALLY ANY PMS query you can think of!

    📊 WHAT IT CAN QUERY:
    • Projects, Work Items (tasks/bugs/issues), Cycles (sprints), Modules, Members (team), Pages (docs)
    • Complex cross-entity relationships and inter-dependencies

    🎯 WHAT IT CAN DO:
    ✅ Filter by: status, priority, dates, projects, assignees, creators
    ✅ Group by: state, priority, assignee, project, etc.
    ✅ Sort by: created date, priority, status, etc.
    ✅ Cross-collection joins: members↔work items, pages↔modules/cycles
    ✅ Date ranges: today, yesterday, last week, last 30 days, etc.
    ✅ Complex conditions: multiple filters, nested relationships
    ✅ ADVANCED: Multi-entity analysis, workload distribution, progress tracking
    ✅ ADVANCED: Content network analysis, team productivity metrics

    💡 TRIGGER PHRASES (use these to activate this tool):
    • "show me", "find", "list", "get me", "tell me about"
    • "work items", "tasks", "tickets", "bugs", "issues"
    • "projects", "cycles", "sprints", "modules", "pages"
    • "members", "team", "assignees", "users"
    • "grouped by", "sorted by", "filtered by"
    • "in project", "for project", "with status"
    • "who is working on", "what's the progress", "how are we doing"
    • "team productivity", "workload analysis", "resource allocation"

    🌟 REAL EXAMPLES (just ask naturally!):
    • "Show work items in Test PMS grouped by status"
    • "Who are the members in Test PMS and what tasks do they have?"
    • "Find pages linked to modules in project Test PMS"
    • "Top 20 recent tickets sorted by creation date"
    • "High priority work items from last week"
    • "Cycles ending this month in Test PMS"
    • "Work items assigned to John in project API"
    • "Members with completed tasks in last 30 days"
    • "Pages linked to cycle Sprint 1"
    • "Show me team productivity in Test PMS"
    • "What's the workload distribution across team members?"
    • "How is project health looking across all projects?"
    • "Find content network connections between pages and modules"

    ⚙️ ADVANCED FEATURES:
    • Builds optimal MongoDB aggregation pipelines automatically
    • Handles complex cross-collection relationships with intelligent joins
    • Applies security filtering and field validation
    • Uses specialized pipeline templates for common patterns
    • Returns both data and the generated query pipeline
    • Supports multi-entity analysis with relationship complexity analysis

    🎪 JUST ASK NATURALLY - This tool will figure out what you mean and get you the data!

    🔥 IMPORTANT: This is the PRIMARY tool for most PMS questions. Use it for ANY query involving:
    - Work items, projects, members, cycles, modules, pages
    - Filtering, grouping, sorting, relationships
    - Complex multi-condition queries
    - Team productivity and workload analysis
    - Project health and progress tracking
    - Content network and collaboration analysis
    - Natural language questions about PMS data

    Args:
        query: Any natural language question about PMS data (projects, work items, teams, etc.)

    Returns:
        Complete results with data and the MongoDB pipeline that was executed
    """
    import asyncio

    try:
        # Get the current event loop
        try:
            loop = asyncio.get_event_loop()
            # Check if it's already running
            if loop.is_running():
                # If loop is running, we need to handle differently
                import concurrent.futures
                import threading

                def run_async():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(plan_and_execute_query(query))
                    finally:
                        new_loop.close()

                # Run in a thread pool to avoid blocking
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(run_async)
                    result = future.result(timeout=30)  # 30 second timeout
            else:
                # Loop exists but not running, we can use it
                result = loop.run_until_complete(plan_and_execute_query(query))
        except RuntimeError:
            # No event loop exists, create a new one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(plan_and_execute_query(query))
            finally:
                loop.close()

        # Enhance the result with pipeline template suggestions for future queries
        if isinstance(result, dict) and "pipeline" in result:
            template_suggestions = suggest_pipeline_template(query)
            if template_suggestions:
                result["template_suggestions"] = template_suggestions
                result["available_templates"] = list(PIPELINE_TEMPLATES.keys())

        return result

    except Exception as e:
        return {
            "success": False,
            "error": f"Query execution failed: {str(e)}",
            "query": query
        }


# Define ProjectManagement-specific readonly insight tools
@tool
def get_project_overview() -> str:
    """Returns comprehensive project status distribution with counts and project names by status.

    USE THIS TOOL WHEN:
    - User asks for project portfolio overview or status summary
    - Questions like "How are projects distributed?", "What's the project status breakdown?"
    - Need high-level project portfolio analysis across all statuses
    - Want to see which projects are in each status (STARTED, COMPLETED, etc.)

    Returns formatted analysis with project counts by status and specific project names."""
    import asyncio

    try:
        # Get the current event loop
        try:
            loop = asyncio.get_event_loop()
            # Check if it's already running
            if loop.is_running():
                # If loop is running, we need to handle differently
                import concurrent.futures

                def run_async():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(mongodb_tools.execute_tool("aggregate", {
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
                        }))
                    finally:
                        new_loop.close()

                # Run in a thread pool to avoid blocking
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(run_async)
                    result = future.result(timeout=30)
            else:
                # Loop exists but not running, we can use it
                result = loop.run_until_complete(mongodb_tools.execute_tool("aggregate", {
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
                }))
        except RuntimeError:
            # No event loop exists, create a new one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(mongodb_tools.execute_tool("aggregate", {
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
                }))
            finally:
                loop.close()

        return f"📊 PROJECT STATUS OVERVIEW:\n{result}"
    except Exception as e:
        return f"❌ Error getting project overview: {str(e)}"

@tool
def get_work_item_insights() -> str:
    """Returns detailed task distribution analysis by project, status, and priority.

    USE THIS TOOL WHEN:
    - User asks about task/work item distribution or workload analysis
    - Questions like "How are tasks distributed?", "What's the priority breakdown?"
    - Need to understand workload allocation across different projects
    - Want to analyze task status distribution (TODO, IN_PROGRESS, COMPLETED, etc.)
    - Analyzing priority levels (HIGH, MEDIUM, LOW) across the organization

    Returns aggregated analysis showing task counts grouped by project, status, and priority."""
    import asyncio

    try:
        # Get the current event loop
        try:
            loop = asyncio.get_event_loop()
            # Check if it's already running
            if loop.is_running():
                # If loop is running, we need to handle differently
                import concurrent.futures

                def run_async():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(mongodb_tools.execute_tool("aggregate", {
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
                        }))
                    finally:
                        new_loop.close()

                # Run in a thread pool to avoid blocking
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(run_async)
                    result = future.result(timeout=30)
            else:
                # Loop exists but not running, we can use it
                result = loop.run_until_complete(mongodb_tools.execute_tool("aggregate", {
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
                }))
        except RuntimeError:
            # No event loop exists, create a new one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(mongodb_tools.execute_tool("aggregate", {
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
                }))
            finally:
                loop.close()

        return f"🎯 WORK ITEM ANALYSIS:\n{result}"
    except Exception as e:
        return f"❌ Error getting work item insights: {str(e)}"

@tool
def get_team_productivity() -> str:
    """Returns comprehensive team member workload analysis with task counts and project assignments.

    USE THIS TOOL WHEN:
    - User asks about team productivity, workload, or resource allocation
    - Questions like "How busy is the team?", "Who's working on what?", "Team workload analysis"
    - Need to assess resource distribution across projects
    - Want to see individual team member task counts and project assignments
    - Planning resource allocation or identifying overloaded/underutilized team members

    Returns analysis showing each team member's total tasks, completed tasks, and project involvement."""
    import asyncio

    try:
        # Get the current event loop
        try:
            loop = asyncio.get_event_loop()
            # Check if it's already running
            if loop.is_running():
                # If loop is running, we need to handle differently
                import concurrent.futures

                def run_async():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(mongodb_tools.execute_tool("aggregate", {
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
                        }))
                    finally:
                        new_loop.close()

                # Run in a thread pool to avoid blocking
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(run_async)
                    result = future.result(timeout=30)
            else:
                # Loop exists but not running, we can use it
                result = loop.run_until_complete(mongodb_tools.execute_tool("aggregate", {
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
                }))
        except RuntimeError:
            # No event loop exists, create a new one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(mongodb_tools.execute_tool("aggregate", {
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
                }))
            finally:
                loop.close()

        return f"👥 TEAM WORKLOAD ANALYSIS:\n{result}"
    except Exception as e:
        return f"❌ Error getting team productivity: {str(e)}"

@tool
def get_project_timeline() -> str:
    """Returns the 20 most recent project activities and events sorted by timestamp.

    USE THIS TOOL WHEN:
    - User asks about recent project activity or timeline
    - Questions like "What's been happening lately?", "Recent project updates?", "Timeline of changes"
    - Need to track recent project events and changes
    - Want to see chronological activity across all projects
    - Monitoring project progress and recent developments

    Returns chronological list of recent project activities and events."""
    import asyncio

    try:
        # Get the current event loop
        try:
            loop = asyncio.get_event_loop()
            # Check if it's already running
            if loop.is_running():
                # If loop is running, we need to handle differently
                import concurrent.futures

                def run_async():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(mongodb_tools.execute_tool("find", {
                            "database": DATABASE_NAME,
                            "collection": "timeline",
                            "filter": {},
                            "sort": {"timestamp": -1},
                            "limit": 20
                        }))
                    finally:
                        new_loop.close()

                # Run in a thread pool to avoid blocking
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(run_async)
                    result = future.result(timeout=30)
            else:
                # Loop exists but not running, we can use it
                result = loop.run_until_complete(mongodb_tools.execute_tool("find", {
                    "database": DATABASE_NAME,
                    "collection": "timeline",
                    "filter": {},
                    "sort": {"timestamp": -1},
                    "limit": 20
                }))
        except RuntimeError:
            # No event loop exists, create a new one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(mongodb_tools.execute_tool("find", {
                    "database": DATABASE_NAME,
                    "collection": "timeline",
                    "filter": {},
                    "sort": {"timestamp": -1},
                    "limit": 20
                }))
            finally:
                loop.close()

        return f"📅 RECENT PROJECT ACTIVITY:\n{result}"
    except Exception as e:
        return f"❌ Error getting project timeline: {str(e)}"

@tool
def get_business_insights() -> str:
    """Returns business unit performance analysis with project counts and status breakdowns.

    USE THIS TOOL WHEN:
    - User asks about business unit performance or organizational analysis
    - Questions like "How are business units performing?", "Project distribution by business unit?"
    - Need to analyze performance across different business units
    - Want to see active vs completed projects by business unit
    - Evaluating organizational project portfolio distribution

    Returns analysis showing each business unit's total projects, active projects, and completion status."""
    import asyncio

    try:
        # Get the current event loop
        try:
            loop = asyncio.get_event_loop()
            # Check if it's already running
            if loop.is_running():
                # If loop is running, we need to handle differently
                import concurrent.futures

                def run_async():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(mongodb_tools.execute_tool("aggregate", {
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
                        }))
                    finally:
                        new_loop.close()

                # Run in a thread pool to avoid blocking
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(run_async)
                    result = future.result(timeout=30)
            else:
                # Loop exists but not running, we can use it
                result = loop.run_until_complete(mongodb_tools.execute_tool("aggregate", {
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
                }))
        except RuntimeError:
            # No event loop exists, create a new one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(mongodb_tools.execute_tool("aggregate", {
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
                }))
            finally:
                loop.close()

        return f"🏢 BUSINESS UNIT PERFORMANCE:\n{result}"
    except Exception as e:
        return f"❌ Error getting business insights: {str(e)}"


@tool
def search_projects_by_name(name: str) -> str:
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
    import asyncio

    try:
        # Get the current event loop
        try:
            loop = asyncio.get_event_loop()
            # Check if it's already running
            if loop.is_running():
                # If loop is running, we need to handle differently
                import concurrent.futures

                def run_async():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(mongodb_tools.execute_tool("find", {
                            "database": DATABASE_NAME,
                            "collection": "project",
                            "filter": {"name": {"$regex": name, "$options": "i"}},
                            "limit": 10
                        }))
                    finally:
                        new_loop.close()

                # Run in a thread pool to avoid blocking
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(run_async)
                    result = future.result(timeout=30)
            else:
                # Loop exists but not running, we can use it
                result = loop.run_until_complete(mongodb_tools.execute_tool("find", {
                    "database": DATABASE_NAME,
                    "collection": "project",
                    "filter": {"name": {"$regex": name, "$options": "i"}},
                    "limit": 10
                }))
        except RuntimeError:
            # No event loop exists, create a new one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(mongodb_tools.execute_tool("find", {
                    "database": DATABASE_NAME,
                    "collection": "project",
                    "filter": {"name": {"$regex": name, "$options": "i"}},
                    "limit": 10
                }))
            finally:
                loop.close()

        return f"🔍 PROJECTS MATCHING '{name}':\n{result}"
    except Exception as e:
        return f"❌ Error searching projects by name: {str(e)}"

# Query Router Helper (internal tool to guide agent decision making)
@tool
def _analyze_query_type(query: str) -> str:
    """
    INTERNAL HELPER: Analyzes query type to recommend the best tool to use.
    This helps the agent decide whether to use intelligent_query or specialized tools.

    Returns analysis of query type and recommended tool.
    """
    query_lower = query.lower()
    analysis = []

    # Check for PMS keywords
    pms_keywords = [
        'work item', 'work items', 'task', 'tasks', 'ticket', 'tickets', 'bug', 'bugs',
        'issue', 'issues', 'project', 'projects', 'cycle', 'cycles', 'sprint', 'sprints',
        'module', 'modules', 'member', 'members', 'team', 'assignee', 'assignees',
        'page', 'pages', 'doc', 'docs', 'document'
    ]

    keyword_count = sum(1 for keyword in pms_keywords if keyword in query_lower)
    if keyword_count >= 2:
        analysis.append("HIGH PMS CONTENT: Multiple PMS keywords detected")
        analysis.append("RECOMMENDATION: Use intelligent_query as primary tool")
    else:
        analysis.append("LOW PMS CONTENT: May not be PMS-related")
        analysis.append("RECOMMENDATION: Consider specialized tools or general response")

    # Check for complex operations
    complex_ops = ['group', 'filter', 'sort', 'join', 'relationship', 'cross', 'complex']
    has_complex = any(op in query_lower for op in complex_ops)
    if has_complex:
        analysis.append("COMPLEX OPERATIONS: Grouping, filtering, or relationships detected")
        analysis.append("RECOMMENDATION: Definitely use intelligent_query")

    # Check for natural language patterns
    natural_patterns = ['show me', 'find', 'list', 'get me', 'tell me about', 'what are']
    has_natural = any(pattern in query_lower for pattern in natural_patterns)
    if has_natural:
        analysis.append("NATURAL LANGUAGE: Conversational query pattern detected")
        analysis.append("RECOMMENDATION: Perfect for intelligent_query")

    return "\n".join(analysis)

@tool
def advanced_pipeline_query(template_name: str, variables: Dict[str, Any]) -> Dict[str, Any]:
    """
    🚀 ADVANCED PIPELINE QUERY - Use Pre-built Templates for Complex Analysis

    🎯 This tool allows you to use specialized MongoDB aggregation pipeline templates
    for complex PMS data analysis that goes beyond simple queries.

    📋 AVAILABLE TEMPLATES:
    • "workload_distribution": Analyze team member workload and task distribution
    • "content_network_analysis": Map relationships between pages, modules, and cycles
    • "progress_tracking": Track project progress across cycles and work items
    • "cross_entity_join": Complex multi-entity joins with custom relationships

    💡 WHEN TO USE:
    • For complex analytical queries that need specialized aggregation patterns
    • When you need advanced metrics like completion percentages, productivity scores
    • For network analysis and relationship mapping
    • When standard queries aren't providing the depth of analysis you need

    🌟 TEMPLATE DETAILS:

    📊 WORKLOAD_DISTRIBUTION:
    - Shows task distribution across team members
    - Calculates productivity metrics
    - Groups work items by status and priority
    - Variables: project_filter (dict with project filters)

    🔗 CONTENT_NETWORK_ANALYSIS:
    - Maps connections between pages, modules, and cycles
    - Shows content interdependencies
    - Calculates connection density metrics
    - Variables: project_filter (dict with project filters)

    📈 PROGRESS_TRACKING:
    - Tracks completion across cycles
    - Shows progress percentages
    - Groups by status and priority
    - Variables: project_filter (dict with project filters)

    🔄 CROSS_ENTITY_JOIN:
    - Custom multi-entity relationship analysis
    - Flexible join patterns
    - Variables: root_filters, target_collection, target_field, secondary_collection, secondary_field

    🎪 USAGE EXAMPLES:
    • Use "workload_distribution" with {"project_filter": {"name": "Test PMS"}}
    • Use "progress_tracking" with {"project_filter": {"status": "STARTED"}}
    • Use "content_network_analysis" with {"project_filter": {"isActive": true}}

    Args:
        template_name: Name of the pipeline template to use
        variables: Dictionary of variables to substitute in the template

    Returns:
        Complete analysis results with the executed pipeline
    """
    import asyncio

    try:
        pipeline = get_pipeline_template(template_name, variables)

        # Get the current event loop
        try:
            loop = asyncio.get_event_loop()
            # Check if it's already running
            if loop.is_running():
                # If loop is running, we need to handle differently
                import concurrent.futures

                def run_async():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(mongodb_tools.execute_tool("aggregate", {
                            "database": DATABASE_NAME,
                            "collection": "project",  # Most templates start from project
                            "pipeline": pipeline
                        }))
                    finally:
                        new_loop.close()

                # Run in a thread pool to avoid blocking
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(run_async)
                    result = future.result(timeout=30)
            else:
                # Loop exists but not running, we can use it
                result = loop.run_until_complete(mongodb_tools.execute_tool("aggregate", {
                    "database": DATABASE_NAME,
                    "collection": "project",  # Most templates start from project
                    "pipeline": pipeline
                }))
        except RuntimeError:
            # No event loop exists, create a new one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(mongodb_tools.execute_tool("aggregate", {
                    "database": DATABASE_NAME,
                    "collection": "project",  # Most templates start from project
                    "pipeline": pipeline
                }))
            finally:
                loop.close()

        return {
            "success": True,
            "template_used": template_name,
            "pipeline": pipeline,
            "data": result,
            "analysis_type": PIPELINE_TEMPLATES[template_name]["description"]
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "template_name": template_name,
            "available_templates": list(PIPELINE_TEMPLATES.keys())
        }

# Define the tools list with ProjectManagement-specific readonly tools
tools = [
    # ESSENTIAL OVERVIEW TOOLS (keep these - provide high-level insights)
    get_project_overview,        # Project portfolio status distribution
    get_work_item_insights,      # Task distribution analysis
    get_team_productivity,       # Team workload analysis
    get_project_timeline,        # Recent project activity
    get_business_insights,       # Business unit performance

    # UTILITY TOOLS (keep these - simple specific functions)
    search_projects_by_name,     # Simple project name search

    # INTELLIGENT QUERY PROCESSOR - THE PRIMARY TOOL
    intelligent_query,           # Handles ANY natural language query dynamically

    # ADVANCED ANALYTICS TOOLS (for complex analysis)
    advanced_pipeline_query,     # Specialized pipeline templates for deep analysis

    # INTERNAL HELPER (not exposed to user, helps with routing)
    _analyze_query_type,         # Internal query type analyzer
]
