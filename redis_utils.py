import os
import json
import hashlib
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

# Use asyncio Redis client
from redis import asyncio as aioredis


# Configuration via environment variables
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CONVERSATION_TTL_SECONDS = int(os.getenv("REDIS_CONVERSATION_TTL_SECONDS", "7200"))  # 2 hours
CONVERSATION_HISTORY_WINDOW = int(os.getenv("CONVERSATION_HISTORY_WINDOW", "20"))
TOOL_CACHE_TTL_SECONDS = int(os.getenv("REDIS_TOOL_CACHE_TTL", "30"))
RESPONSE_CACHE_TTL_SECONDS = int(os.getenv("REDIS_RESPONSE_CACHE_TTL", "300"))


_redis_client: Optional[aioredis.Redis] = None


def _conversation_list_key(conversation_id: str) -> str:
    return f"conv:{conversation_id}:messages"


def _response_cache_key(conversation_id: str, query: str) -> str:
    digest = hashlib.sha1(query.encode("utf-8")).hexdigest()
    return f"conv:{conversation_id}:resp:{digest}"


def build_cache_key(namespace: str, payload: Dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha1(serialized.encode("utf-8")).hexdigest()
    return f"{namespace}:{digest}"


async def get_client() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


async def append_conversation_message(
    conversation_id: str,
    role: str,
    content: str,
    timestamp_iso: Optional[str] = None,
) -> None:
    if not conversation_id:
        return
    client = await get_client()
    key = _conversation_list_key(conversation_id)
    record = {
        "role": role,
        "content": content,
        "timestamp": timestamp_iso or datetime.now().isoformat(),
    }
    await client.rpush(key, json.dumps(record, ensure_ascii=False))
    # Keep only the last N messages for short-term memory
    await client.ltrim(key, -CONVERSATION_HISTORY_WINDOW, -1)
    await client.expire(key, CONVERSATION_TTL_SECONDS)


async def get_recent_conversation_messages(
    conversation_id: str,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    if not conversation_id:
        return []
    client = await get_client()
    key = _conversation_list_key(conversation_id)
    k = limit or CONVERSATION_HISTORY_WINDOW
    # LRANGE is inclusive; -k to -1 yields last k items
    raw_items = await client.lrange(key, -k, -1)
    messages: List[Dict[str, Any]] = []
    for item in raw_items:
        try:
            messages.append(json.loads(item))
        except Exception:
            # Fallback if corrupted entry
            messages.append({"role": "unknown", "content": str(item)})
    return messages


async def get_recent_messages_as_langchain(
    conversation_id: str,
    limit: Optional[int] = None,
):
    try:
        from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
    except Exception:
        # If langchain is not available, return raw records
        return await get_recent_conversation_messages(conversation_id, limit)

    records = await get_recent_conversation_messages(conversation_id, limit)
    lc_messages = []
    for rec in records:
        role = rec.get("role")
        content = rec.get("content", "")
        if role == "user":
            lc_messages.append(HumanMessage(content=content))
        elif role == "assistant":
            lc_messages.append(AIMessage(content=content))
        elif role == "tool":
            lc_messages.append(ToolMessage(content=content, tool_call_id=""))
        else:
            # Unknown role, skip or treat as AI
            lc_messages.append(AIMessage(content=content))
    return lc_messages


# Simple JSON cache helpers
async def get_cached_json(key: str) -> Optional[Any]:
    client = await get_client()
    data = await client.get(key)
    if data is None:
        return None
    try:
        return json.loads(data)
    except Exception:
        return data


async def set_cached_json(key: str, value: Any, ttl_seconds: int) -> None:
    client = await get_client()
    try:
        serialized = json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        serialized = str(value)
    await client.set(key, serialized, ex=ttl_seconds)


# Tool cache: namespace helper
def tool_cache_key(tool_name: str, arguments: Dict[str, Any]) -> str:
    return build_cache_key(f"tool:{tool_name}", arguments)


# Response cache helpers
async def get_cached_response(conversation_id: str, query: str) -> Optional[str]:
    if not conversation_id:
        return None
    client = await get_client()
    key = _response_cache_key(conversation_id, query)
    return await client.get(key)


async def set_cached_response(conversation_id: str, query: str, response: str) -> None:
    if not conversation_id:
        return
    client = await get_client()
    key = _response_cache_key(conversation_id, query)
    await client.set(key, response, ex=RESPONSE_CACHE_TTL_SECONDS)

