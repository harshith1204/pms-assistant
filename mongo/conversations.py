from __future__ import annotations

from typing import Optional, Dict, Any
from datetime import datetime
import uuid
import asyncio
import contextlib
from motor.motor_asyncio import AsyncIOMotorClient

try:
    from openinference.semconv.trace import SpanAttributes as OI
except Exception:
    class _OI:
        TOOL_INPUT = "tool.input"
        TOOL_OUTPUT = "tool.output"
        ERROR_TYPE = "error.type"
        ERROR_MESSAGE = "error.message"
    OI = _OI()


class ConversationMongoClient:
    """Dedicated MongoDB client for conversations using separate connection string"""

    def __init__(self, connection_string: str):
        self.client = None
        self.connected = False
        self._connect_lock = asyncio.Lock()
        self.connection_string = connection_string

    async def connect(self):
        """Initialize MongoDB connection for conversations"""
        span_cm = contextlib.nullcontext()
        with span_cm as span:
            try:
                async with self._connect_lock:
                    if self.connected and self.client:
                        return

                    # Create Motor client with optimized connection pool settings for conversations
                    self.client = AsyncIOMotorClient(
                        self.connection_string,
                        maxPoolSize=20,          # Smaller pool for conversations
                        minPoolSize=5,           # Keep minimum connections alive
                        maxIdleTimeMS=45000,     # Keep idle connections for 45s
                        waitQueueTimeoutMS=5000, # Faster timeout for queue
                        serverSelectionTimeoutMS=5000,  # Faster server selection
                        connectTimeoutMS=10000,  # Connection timeout
                        socketTimeoutMS=20000,   # Socket timeout
                    )

                    # Test connection
                    await self.client.admin.command('ping')

                    self.connected = True

                    print("✅ Conversations MongoDB connected with persistent connection pool")

            except Exception as e:
                print(f"❌ Failed to connect to Conversations MongoDB: {e}")
                raise

    async def disconnect(self):
        """Disconnect from MongoDB"""
        if self.client:
            self.client.close()
        self.connected = False
        self.client = None

    async def get_collection(self, db_name: str, collection_name: str):
        """Get a collection from the conversations database"""
        if not self.client:
            await self.connect()
        return self.client[db_name][collection_name]


# Initialize conversations client with the provided connection string
CONVERSATIONS_CONNECTION_STRING = "mongodb://BeeOSAdmin:Proficornlabs%401118@172.214.123.233:27017/?authSource=admin"
conversation_mongo_client = ConversationMongoClient(CONVERSATIONS_CONNECTION_STRING)


CONVERSATIONS_DB_NAME = "SimpoAssist"
CONVERSATIONS_COLLECTION_NAME = "conversations"


async def ensure_conversation_client_connected():
    """Ensure the conversation MongoDB client is connected"""
    if not conversation_mongo_client.connected:
        await conversation_mongo_client.connect()


async def cleanup_conversation_client():
    """Cleanup the conversation MongoDB client connection"""
    await conversation_mongo_client.disconnect()


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
    return await conversation_mongo_client.get_collection(CONVERSATIONS_DB_NAME, CONVERSATIONS_COLLECTION_NAME)


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


async def update_message_reaction(
    conversation_id: str,
    message_id: str,
    liked: Optional[bool] = None,
    feedback: Optional[str] = None,
) -> bool:
    """Update reaction fields for a specific message in a conversation.

    When `liked` is True/False we set `messages.$.liked` accordingly.
    When `liked` is None we UNSET the `messages.$.liked` field (clear reaction).
    Optionally updates `messages.$.feedback` when provided.
    Returns True if a document was modified, False otherwise.
    """
    coll = await _get_collection()

    update_doc: Dict[str, Any] = {}

    if liked is None:
        # Clear the reaction field
        update_doc["$unset"] = {"messages.$.liked": ""}
    else:
        update_doc["$set"] = {"messages.$.liked": liked}

    if feedback is not None:
        # Ensure $set exists if we also need to update feedback
        update_doc.setdefault("$set", {})["messages.$.feedback"] = feedback

    result = await coll.update_one(
        {"conversationId": conversation_id, "messages.id": message_id},
        update_doc,
    )
    return getattr(result, "modified_count", 0) > 0

