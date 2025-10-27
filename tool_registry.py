from pydantic import BaseModel, Field
from typing import Dict, Any, Callable, Optional, List, Literal
import asyncio
import time

# Local tools
import tools as local_tools_module


class ToolSpec(BaseModel):
    name: str
    description: str = ""
    input_schema: Dict[str, Any] = {}
    output_schema: Optional[Dict[str, Any]] = None
    tags: List[str] = []
    freshness: Literal["static", "daily", "hourly", "realtime"] = "static"
    est_latency_ms: int = 200
    est_cost_tokens: int = 2000
    reliability: float = 0.99
    run: Callable[[Dict[str, Any]], Any]
    auth_scope: Optional[str] = None
    examples: List[Dict[str, Any]] = []


_registry: Dict[str, ToolSpec] = {}
_initialized = False


async def _ainvoke_tool(tool, args: Dict[str, Any]):
    # langchain tools support ainvoke for async
    if hasattr(tool, "ainvoke"):
        return await tool.ainvoke(args)
    # fallback to sync
    if hasattr(tool, "invoke"):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: tool.invoke(args))
    # direct call if callable
    if callable(tool):
        maybe = tool(args)
        if asyncio.iscoroutine(maybe):
            return await maybe
        return maybe
    raise ValueError(f"Tool {getattr(tool, 'name', str(tool))} is not invokable")


def _tool_to_spec(t) -> ToolSpec:
    # Best-effort JSON schema capture
    input_schema: Dict[str, Any] = {}
    try:
        if hasattr(t, "args_schema") and t.args_schema is not None:
            schema = t.args_schema.schema() if hasattr(t.args_schema, "schema") else None
            if isinstance(schema, dict):
                input_schema = schema
    except Exception:
        input_schema = {}

    desc = getattr(t, "description", "") or ""
    name = getattr(t, "name", t.__name__ if hasattr(t, "__name__") else "unknown")

    async def runner(args: Dict[str, Any]):
        # Normalize None to {}
        args = args or {}
        return await _ainvoke_tool(t, args)

    return ToolSpec(
        name=name,
        description=desc,
        input_schema=input_schema,
        tags=["local"],
        run=runner,
        est_latency_ms=300,
        reliability=0.99,
    )


def initialize_registry() -> Dict[str, ToolSpec]:
    global _initialized, _registry
    if _initialized:
        return _registry

    # Register local tools from tools.tools
    for t in getattr(local_tools_module, "tools", []):
        spec = _tool_to_spec(t)
        _registry[spec.name] = spec

    _initialized = True
    return _registry


def get_registry() -> Dict[str, ToolSpec]:
    return initialize_registry()


def rank_tools(query: str, tools: List[ToolSpec], k: int = 6) -> List[ToolSpec]:
    q = (query or "").lower()

    def score(spec: ToolSpec) -> float:
        base = 0.0
        haystack = f"{spec.name} {spec.description} {' '.join(spec.tags)}".lower()
        # keyword overlap
        for token in set(q.split()):
            if len(token) < 3:
                continue
            if token in haystack:
                base += 1.0
        # boosts
        if "project" in q and "project" in haystack:
            base += 1.0
        if "work" in q and "work" in haystack:
            base += 0.5
        if "cycle" in q and "cycle" in haystack:
            base += 0.5
        # latency/cost preference
        base += max(0.0, 1.0 - (spec.est_latency_ms / 2000.0))
        base += max(0.0, 1.0 - (spec.est_cost_tokens / 8000.0))
        # reliability
        base += spec.reliability * 0.5
        return base

    scored = sorted(tools, key=score, reverse=True)
    return scored[:k]

