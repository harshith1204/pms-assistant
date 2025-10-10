import time
import inspect
from functools import wraps
from typing import Any, Callable
from events import emitter


def _now_ms() -> int:
    return int(time.time() * 1000)


def safe_shallow(x: Any, max_items: int = 5):
    try:
        if x is None or isinstance(x, (int, float, str, bool)):
            return x
        if isinstance(x, dict):
            return {k: safe_shallow(v) for k, v in list(x.items())[:max_items]}
        if isinstance(x, (list, tuple, set)):
            return [safe_shallow(i) for i in list(x)[:max_items]]
        return str(type(x).__name__)
    except Exception:
        return "unserializable"


def summarize_result(res: Any):
    try:
        if isinstance(res, dict):
            return {"keys": list(res.keys())[:10], "len": len(res)}
        if isinstance(res, (list, tuple)):
            return {"len": len(res), "sample0": safe_shallow(res[0]) if res else None}
        if isinstance(res, str):
            return {"len": len(res), "preview": res[:200]}
        return {"type": type(res).__name__}
    except Exception:
        return {"type": "unknown"}


def instrument_tool(tool_name: str) -> Callable:
    """Decorator for plain async/sync functions to emit start/result/error events.
    Use for non-LangChain utilities. For LangChain Tool objects, prefer agent-level wrapping.
    """
    def deco(fn: Callable):
        if inspect.iscoroutinefunction(fn):
            @wraps(fn)
            async def wrapper(*args, **kwargs):
                action_label = kwargs.pop("_action", "call_tool")
                action_id = f"{tool_name}-{_now_ms()}"
                await emitter.emit({
                    "type": "agent_action",
                    "action_id": action_id,
                    "phase": "tool_call",
                    "subject": tool_name,
                    "text": f"Calling tool {tool_name}",
                    "action": action_label,
                    "meta": {"args": safe_shallow(args), "kwargs": safe_shallow(kwargs)},
                })
                try:
                    res = await fn(*args, **kwargs)
                    await emitter.emit({
                        "type": "agent_result",
                        "action_id": action_id,
                        "phase": "tool_call",
                        "subject": tool_name,
                        "text": f"Tool {tool_name} returned",
                        "action": action_label,
                        "meta": {"summary": summarize_result(res)},
                    })
                    return res
                except Exception as e:
                    await emitter.emit({
                        "type": "agent_error",
                        "action_id": action_id,
                        "phase": "tool_call",
                        "subject": tool_name,
                        "text": str(e),
                        "action": action_label,
                        "meta": {"exception": type(e).__name__},
                    })
                    raise
            return wrapper
        else:
            @wraps(fn)
            def wrapper(*args, **kwargs):
                action_label = kwargs.pop("_action", "call_tool")
                action_id = f"{tool_name}-{_now_ms()}"
                emitter.emit_sync({
                    "type": "agent_action",
                    "action_id": action_id,
                    "phase": "tool_call",
                    "subject": tool_name,
                    "text": f"Calling tool {tool_name}",
                    "action": action_label,
                    "meta": {"args": safe_shallow(args), "kwargs": safe_shallow(kwargs)},
                })
                try:
                    res = fn(*args, **kwargs)
                    emitter.emit_sync({
                        "type": "agent_result",
                        "action_id": action_id,
                        "phase": "tool_call",
                        "subject": tool_name,
                        "text": f"Tool {tool_name} returned",
                        "action": action_label,
                        "meta": {"summary": summarize_result(res)},
                    })
                    return res
                except Exception as e:
                    emitter.emit_sync({
                        "type": "agent_error",
                        "action_id": action_id,
                        "phase": "tool_call",
                        "subject": tool_name,
                        "text": str(e),
                        "action": action_label,
                        "meta": {"exception": type(e).__name__},
                    })
                    raise
            return wrapper
    return deco
