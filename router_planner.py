# router_planner.py
from __future__ import annotations
import re, json
from typing import Dict, Any, List
from pydantic import BaseModel
from langchain_ollama import ChatOllama
from tool_registry import REGISTRY, ToolSpec

# --- Router (keyword + tags) ---
KEYWORDS = [
    ("status", ["search_projects_by_status","get_project_overview"]),
    ("priority", ["get_work_item_by_priority","get_work_item_insights"]),
    ("workload", ["get_member_workload","get_team_productivity"]),
    ("member", ["get_member_workload","get_team_member_roles"]),
    ("timeline", ["get_project_timeline"]),
    ("business", ["get_business_insights"]),
    ("count work items", ["count_work_items_by_project","get_total_work_item_count"]),
    ("count projects", ["get_total_project_count"]),
    ("list projects", ["list_all_projects","search_projects_by_name"]),
    ("breakdown", ["get_work_items_breakdown_by_project"]),
    ("project", ["search_projects_by_name","get_project_overview","get_project_work_item_details"]),
    ("work items", ["get_project_work_item_details","get_work_item_insights"]),
    ("cycle", ["get_cycle_overview","get_active_cycles","get_upcoming_cycles"]),
    ("sprint", ["get_cycle_overview","get_active_cycles","get_upcoming_cycles"]),
    ("module", ["get_module_overview","get_module_leads"]),
    ("workflow", ["get_project_states","get_project_workflow_states"]),
]

def shortlist_tools(query: str, k: int = 6) -> List[ToolSpec]:
    q = query.lower()
    scores: Dict[str,int] = {}
    # keyword boosts
    for kw, tools in KEYWORDS:
        if kw in q:
            for t in tools:
                scores[t] = scores.get(t,0) + 5
    # tag proximity
    for name, spec in REGISTRY.items():
        tag_hits = sum(1 for tag in spec.tags if tag in q)
        scores[name] = scores.get(name,0) + tag_hits
        # generic project/workitems clue
        if "project" in q and "project" in spec.tags: scores[name]+=1
        if "work" in q and "workitems" in spec.tags: scores[name]+=1
    ranked = sorted(REGISTRY.values(), key=lambda s: scores.get(s.name,0), reverse=True)
    return ranked[:k]

# --- Plan schema ---
class PlanNode(BaseModel):
    id: str
    tool: str
    args: Dict[str, Any] = {}
class Plan(BaseModel):
    nodes: List[PlanNode]
    final: str  # id of final node

# Simple arg extraction heuristics
STATUS_VALUES = ["STARTED","COMPLETED","ONHOLD","CANCELLED","PLANNED","PAUSED","ACTIVE","UPCOMING"]
PRIO_VALUES = ["P0","P1","P2","P3","HIGH","MEDIUM","LOW"]

def _extract_status(q: str) -> str|None:
    for s in STATUS_VALUES:
        if s.lower() in q.lower(): return s
    return None

def _extract_priority(q: str) -> str|None:
    for p in PRIO_VALUES:
        if p.lower() in q.lower(): return p
    return None

def _extract_email(q: str) -> str|None:
    m = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', q)
    return m.group(0) if m else None

def _extract_project_name(q: str) -> str|None:
    # try quoted text first
    m = re.search(r'"([^"]+)"|\'([^\']+)\'', q)
    if m: return (m.group(1) or m.group(2))
    # fallback: title-ish phrase after 'for' or 'of'
    m = re.search(r'(?:for|of|project)\s+([A-Z][\w \-]{2,40})', q, re.IGNORECASE)
    if m: return m.group(1).strip()
    # more fallback: any capitalized phrase
    m = re.search(r'([A-Z][\w \-]{2,40})', q)
    return m.group(1).strip() if m else None

def make_plan(query: str, model_name: str = "llama3.1") -> Plan:
    shortlist = shortlist_tools(query)
    ql = query.lower()

    # choose primary
    primary = shortlist[0].name if shortlist else "get_project_overview"
    args: Dict[str,Any] = {}

    if primary == "search_projects_by_status":
        args["status"] = _extract_status(query) or "STARTED"
    elif primary == "get_work_item_by_priority":
        args["priority"] = _extract_priority(query) or "P1"
    elif primary in ("get_member_workload",):
        email = _extract_email(query)
        if email: args["email"] = email
    elif primary in ("search_projects_by_name","count_work_items_by_project","get_project_work_item_details","get_project_workflow_states"):
        pname = _extract_project_name(query) or ( " ".join(w for w in query.split() if w.isalpha())[:32] or "TEST" )
        key = "name" if primary=="search_projects_by_name" else "project_name"
        args[key] = pname

    nodes = [PlanNode(id="n1", tool=primary, args=args)]
    return Plan(nodes=nodes, final="n1")