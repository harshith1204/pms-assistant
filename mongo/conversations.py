from __future__ import annotations

from typing import Optional, Dict, Any
from datetime import datetime
import uuid

from mongo.client import direct_mongo_client


CONVERSATIONS_DB_NAME = "SimpoAssist"
CONVERSATIONS_COLLECTION_NAME = "conversations"


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _ensure_message_shape(message: Dict[str, Any]) -> Dict[str, Any]:
    enriched = dict(message)
    if "id" not in enriched:
        enriched["id"] = str(uuid.uuid4())
    if "timestamp" not in enriched:
        enriched["timestamp"] = _now_iso()
    return enriched


async def _get_collection():
    if not direct_mongo_client.client:
        await direct_mongo_client.connect()
    return direct_mongo_client.client[CONVERSATIONS_DB_NAME][CONVERSATIONS_COLLECTION_NAME]


async def append_message(conversation_id: str, message: Dict[str, Any]) -> None:
    coll = await _get_collection()
    safe_message = _ensure_message_shape(message)
    await coll.update_one(
        {"conversationId": conversation_id},
        {
            "$setOnInsert": {
                "conversationId": conversation_id,
                "createdAt": _now_iso(),
            },
            "$push": {"messages": safe_message},
            "$set": {"updatedAt": _now_iso()},
        },
        upsert=True,
    )


async def save_user_message(conversation_id: str, content: str) -> None:
    await append_message(
        conversation_id,
        {
            "type": "user",
            "content": content or "",
        },
    )


async def save_assistant_message(conversation_id: str, content: str) -> None:
    await append_message(
        conversation_id,
        {
            "type": "assistant",
            "content": content or "",
        },
    )


async def save_action_event(
    conversation_id: str,
    kind: str,
    text: str,
    *,
    step: Optional[int] = None,
    tool_name: Optional[str] = None,
) -> None:
    await append_message(
        conversation_id,
        {
            "type": "action" if kind == "action" else "result",
            "content": text or "",
            "step": step,
            "toolName": tool_name,
        },
    )

