# tool_registry.py
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Any, Callable, Awaitable, Dict, List, Optional, Literal
import asyncio
import inspect
import tools as user_tools  # your /mnt/data/tools.py

class ToolSpec(BaseModel):
    name: str
    description: str
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Optional[Dict[str, Any]] = None
    tags: List[str] = Field(default_factory=list)
    freshness: Literal["static","daily","hourly","realtime"] = "daily"
    est_latency_ms: int = 300
    reliability: float = 0.98
    run: Callable[[Dict[str, Any]], Awaitable[Any]]

def _wrap_async(func: Callable[..., Any]) -> Callable[[Dict[str, Any]], Awaitable[Any]]:
    async def _runner(args: Dict[str, Any]) -> Any:
        sig = inspect.signature(func)
        bound = sig.bind_partial(**(args or {}))
        bound.apply_defaults()
        if inspect.iscoroutinefunction(func):
            return await func(*bound.args, **bound.kwargs)
        return func(*bound.args, **bound.kwargs)
    return _runner

def _spec(name: str,
          description: str,
          fn: Callable[..., Any],
          input_schema: Dict[str, Any],
          tags: List[str],
          est_latency_ms: int = 300) -> ToolSpec:
    return ToolSpec(
        name=name,
        description=description,
        input_schema=input_schema,
        output_schema={"type": "string"},
        tags=tags,
        est_latency_ms=est_latency_ms,
        run=_wrap_async(getattr(user_tools, name))
    )

REGISTRY: Dict[str, ToolSpec] = {}

def register_all() -> Dict[str, ToolSpec]:
    # No-arg tools
    for name, desc, tags in [
        ("get_project_overview",        "Portfolio snapshot of projects by status plus quick stats.", ["project","portfolio","status"]),
        ("get_work_item_insights",      "Aggregated insights about work items across projects.",      ["workitems","insight"]),
        ("get_team_productivity",       "Team throughput/velocity overview.",                         ["team","productivity"]),
        ("get_project_timeline",        "Recent project activity/timeline entries.",                  ["project","timeline"]),
        ("get_business_insights",       "Business unit performance across projects.",                 ["business","portfolio"]),
        ("get_total_project_count",     "Count of all projects.",                                     ["project","count"]),
        ("get_total_work_item_count",   "Count of all work items.",                                   ["workitems","count"]),
        ("list_all_projects",           "List every project with basic fields.",                      ["project","list"]),
        ("get_work_items_breakdown_by_project", "Per-project work items breakdown.",                  ["workitems","project","breakdown"]),
        ("get_cycle_overview",          "Cycle status distribution with counts and cycle details.",   ["cycle","sprint","overview"]),
        ("get_active_cycles",           "All currently active cycles with their details.",            ["cycle","sprint","active"]),
        ("get_module_overview",         "Module status and lead distribution across projects.",       ["module","overview"]),
        ("get_project_states",          "All project states and their sub-states for workflow.",      ["project","workflow","states"]),
        ("get_team_member_roles",       "Team member role distribution across projects.",             ["team","member","roles"]),
        ("get_upcoming_cycles",         "Upcoming cycles sorted by start date.",                      ["cycle","sprint","upcoming"]),
        ("get_module_leads",            "Module lead distribution and workload.",                     ["module","lead","workload"]),
    ]:
        REGISTRY[name] = _spec(
            name, desc, getattr(user_tools, name),
            input_schema={"type":"object","properties":{},"additionalProperties":False},
            tags=tags
        )

    # Single-arg tools
    REGISTRY["search_projects_by_status"] = _spec(
        "search_projects_by_status",
        "Find projects filtered by status (e.g., STARTED, COMPLETED).",
        user_tools.search_projects_by_status,
        {"type":"object","properties":{"status":{"type":"string"}}, "required":["status"], "additionalProperties":False},
        ["project","status","search"]
    )
    REGISTRY["get_work_item_by_priority"] = _spec(
        "get_work_item_by_priority",
        "List work items by priority (e.g., P0, P1, High, Medium, Low).",
        user_tools.get_work_item_by_priority,
        {"type":"object","properties":{"priority":{"type":"string"}}, "required":["priority"], "additionalProperties":False},
        ["workitems","priority","search"]
    )
    REGISTRY["get_member_workload"] = _spec(
        "get_member_workload",
        "Workload for a specific member (email) or all members if email omitted.",
        user_tools.get_member_workload,
        {"type":"object","properties":{"email":{"type":"string"}}, "additionalProperties":False},
        ["member","workload"]
    )
    REGISTRY["search_projects_by_name"] = _spec(
        "search_projects_by_name",
        "Search projects by name (partial/keyword).",
        user_tools.search_projects_by_name,
        {"type":"object","properties":{"name":{"type":"string"}}, "required":["name"], "additionalProperties":False},
        ["project","search","name"]
    )
    REGISTRY["count_work_items_by_project"] = _spec(
        "count_work_items_by_project",
        "Count work items belonging to a specific project.",
        user_tools.count_work_items_by_project,
        {"type":"object","properties":{"project_name":{"type":"string"}}, "required":["project_name"], "additionalProperties":False},
        ["workitems","project","count"]
    )
    REGISTRY["get_project_work_item_details"] = _spec(
        "get_project_work_item_details",
        "List detailed work items for a given project.",
        user_tools.get_project_work_item_details,
        {"type":"object","properties":{"project_name":{"type":"string"}}, "required":["project_name"], "additionalProperties":False},
        ["workitems","project","details"]
    )
    REGISTRY["get_project_workflow_states"] = _spec(
        "get_project_workflow_states",
        "Returns workflow states for a specific project.",
        user_tools.get_project_workflow_states,
        {"type":"object","properties":{"project_name":{"type":"string"}}, "required":["project_name"], "additionalProperties":False},
        ["project","workflow","states"]
    )
    return REGISTRY

# one-time init
register_all()