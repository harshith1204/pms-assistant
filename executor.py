# executor.py
from __future__ import annotations
from typing import Dict, Any
from tool_registry import REGISTRY
from router_planner import Plan

async def execute(plan: Plan) -> Dict[str, Any]:
    results: Dict[str, Any] = {}
    for node in plan.nodes:
        spec = REGISTRY[node.tool]
        out = await spec.run(node.args)
        results[node.id] = {"tool": node.tool, "args": node.args, "output": out}
    return {"final": results[plan.final]["output"], "steps": results}