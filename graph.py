from typing import Any, Dict, Optional, List
from pydantic import BaseModel

from langgraph.graph import StateGraph, END

from tool_registry import get_registry
from planning_schema import Plan
from result_store import persist_result, make_preview


class AgentState(BaseModel):
    query: str
    plan: Dict[str, Any] = {}
    nodes_done: Dict[str, Any] = {}
    handles: Dict[str, Any] = {}
    budget: Dict[str, Any] = {"token": 60000, "time_ms": 15000}


def _node_ready(state: AgentState, node_id: str) -> bool:
    node = next((n for n in state.plan.get("nodes", []) if n.get("id") == node_id), None)
    if not node:
        return False
    deps = node.get("deps", [])
    return all(d in state.nodes_done for d in deps)


def decide_next(state: AgentState) -> str:
    for node in state.plan.get("nodes", []):
        nid = node.get("id")
        if nid not in state.nodes_done and _node_ready(state, nid):
            return f"call::{nid}"
    return "summarize_or_end"


async def call_tool(state: AgentState, node_id: str) -> AgentState:
    registry = get_registry()
    node = next((n for n in state.plan.get("nodes", []) if n.get("id") == node_id), None)
    if not node:
        return state
    tool_name = node.get("tool")
    tool = registry.get(tool_name)
    if not tool:
        state.nodes_done[node_id] = {"error": f"Tool {tool_name} not found"}
        return state

    args_resolved = node.get("args", {})
    try:
        result = await tool.run(args_resolved)
        handle = persist_result(tool.name, args_resolved, result)
        preview = make_preview(result)
        state.nodes_done[node_id] = {"handle": handle["_id"], "preview": preview}
        state.handles[handle["_id"]] = {"tool": tool.name}
    except Exception as e:
        state.nodes_done[node_id] = {"error": str(e)}
    return state


def summarize_or_end(state: AgentState) -> str:
    final_selector = state.plan.get("final_selector")
    if final_selector and final_selector in state.nodes_done:
        return END
    return END


graph = StateGraph(AgentState)
graph.add_node("decide_next", decide_next)
graph.add_node("summarize_or_end", summarize_or_end)


async def _call_node(state: AgentState, node_id: str) -> AgentState:
    return await call_tool(state, node_id)


def _router(state: AgentState) -> str:
    nxt = decide_next(state)
    if nxt.startswith("call::"):
        return nxt
    return "summarize_or_end"


graph.add_node("call::dynamic", lambda s: s)
graph.add_edge("decide_next", "summarize_or_end")
graph.set_entry_point("decide_next")

app_graph = graph.compile()

