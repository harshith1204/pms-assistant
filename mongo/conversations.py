from __future__ import annotations

from typing import Optional, Dict, Any
from datetime import datetime
import uuid
import asyncio
import contextlib
from motor.motor_asyncio import AsyncIOMotorClient
import os
import re

# Optional LLM imports for title generation
try:
    from langchain_groq import ChatGroq  # type: ignore
    from langchain_core.messages import SystemMessage, HumanMessage  # type: ignore
except Exception:  # pragma: no cover - fallback if langchain_groq not installed
    ChatGroq = None  # type: ignore
    SystemMessage = None  # type: ignore
    HumanMessage = None  # type: ignore

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
    # Trigger non-blocking title generation after first user message
    try:
        asyncio.create_task(_maybe_generate_title_after_user_message(conversation_id, content or ""))
    except Exception:
        # Best-effort; do not block on failures
        pass


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


# -----------------------------
# Conversation Title Generation
# -----------------------------

TITLE_MIN_WORDS = 3
TITLE_MAX_WORDS = 7
TITLE_CHAR_LIMIT = 60
TITLE_LLM_WORD_THRESHOLD = int(os.getenv("TITLE_LLM_WORD_THRESHOLD", "15"))

_GENERIC_TITLE_BLACKLIST = {
    "conversation",
    "new conversation",
    "general chat",
    "chat",
    "untitled",
}


def _strip_code_and_urls(text: str) -> str:
    """Remove code fences, inline code, and URLs/emails to reduce noise."""
    if not text:
        return ""
    cleaned = re.sub(r"```[\s\S]*?```", " ", text)  # fenced code blocks
    cleaned = re.sub(r"`[^`]*`", " ", cleaned)         # inline code
    cleaned = re.sub(r"https?://\S+", " ", cleaned)   # URLs
    cleaned = re.sub(r"\S+@\S+", " ", cleaned)       # emails
    cleaned = re.sub(r"[\n\r\t]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _to_title_case(text: str) -> str:
    words = [w for w in re.split(r"\s+", text.strip()) if w]
    return " ".join(w.capitalize() for w in words)


def _postprocess_title(raw: str) -> str:
    """Normalize and bound title length and words."""
    if not raw:
        return ""
    title = raw.strip().strip('"').strip("'.;:!?,")
    title = re.sub(r"\s+", " ", title)
    # Enforce char limit first
    if len(title) > TITLE_CHAR_LIMIT:
        title = title[:TITLE_CHAR_LIMIT].rstrip()
    # Enforce word bounds by trimming
    words = title.split()
    if len(words) > TITLE_MAX_WORDS:
        words = words[:TITLE_MAX_WORDS]
        title = " ".join(words)
    title = _to_title_case(title)
    # Filter generic
    if title.lower() in _GENERIC_TITLE_BLACKLIST or not title:
        return ""
    return title


def _heuristic_title_from_text(text: str) -> str:
    """Fast heuristic title from a single user message."""
    cleaned = _strip_code_and_urls(text)
    if not cleaned:
        return "New Conversation"
    # Keep informative tokens only (letters, numbers, hyphens)
    tokens = [t for t in re.findall(r"[\w\-]+", cleaned) if t]
    if not tokens:
        return "New Conversation"
    title = " ".join(tokens[: max(TITLE_MIN_WORDS, min(TITLE_MAX_WORDS, 8))])
    title = _postprocess_title(title)
    return title or "New Conversation"


def _should_use_llm_for_title(text: str) -> bool:
    words = len(re.findall(r"\S+", text or ""))
    return words > TITLE_LLM_WORD_THRESHOLD and ChatGroq is not None and SystemMessage is not None and HumanMessage is not None


async def update_conversation_title(
    conversation_id: str,
    title: str,
    *,
    source: str,
    final: bool = False,
    manual: bool = False,
) -> None:
    """Set conversation title with provenance fields."""
    coll = await _get_collection()
    await coll.update_one(
        {"conversationId": conversation_id},
        {
            "$set": {
                "title": title.strip(),
                "titleSource": source,
                "titleFinal": bool(final),
                "manuallyEdited": bool(manual),
                "titleUpdatedAt": _now_iso(),
                "updatedAt": _now_iso(),
            }
        },
        upsert=True,
    )


async def _llm_title_from_text(text: str) -> Optional[str]:
    """Generate a concise title using a small LLM from a single prompt."""
    if ChatGroq is None or SystemMessage is None:
        return None
    try:
        model_name = os.getenv("GROQ_TITLE_MODEL", os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"))
        llm = ChatGroq(
            model=model_name,
            temperature=0.0,
            max_tokens=48,
            streaming=False,
            verbose=False,
            top_p=0.8,
        )
        prompt = [
            SystemMessage(content=(
                "You are a title generator. Create a concise 3–7 word Title Case chat title. "
                "No quotes, emojis, code, or URLs. Make it specific and helpful."
            )),
            HumanMessage(content=(
                f"Request: \"{_strip_code_and_urls(text)}\"\n"
                "Respond with ONLY the title."
            )),
        ]
        resp = await llm.ainvoke(prompt)
        content = str(getattr(resp, "content", "")).strip()
        return _postprocess_title(content) or None
    except Exception:
        return None


async def _maybe_generate_title_after_user_message(conversation_id: str, user_content: str) -> None:
    """Best-effort title creation after a user message if missing/not finalized.

    Uses heuristic for short inputs; uses LLM for longer inputs (first message only).
    Does not overwrite user-edited titles.
    """
    try:
        coll = await _get_collection()
        # Fetch minimal fields to decide whether to generate
        doc = await coll.find_one(
            {"conversationId": conversation_id},
            {"_id": 0, "title": 1, "titleFinal": 1, "manuallyEdited": 1}
        )
        if not doc:
            # Shouldn't happen (upserted in append_message), but guard anyway
            pass
        # Respect manual edits
        if doc and doc.get("manuallyEdited"):
            return
        # If already finalized, do nothing
        if doc and doc.get("titleFinal"):
            return

        # Decide generation path based on first user message length
        if _should_use_llm_for_title(user_content):
            title = await _llm_title_from_text(user_content)
            if title:
                await update_conversation_title(conversation_id, title, source="llm", final=False, manual=False)
                return

        # Fallback to heuristic
        heur_title = _heuristic_title_from_text(user_content)
        await update_conversation_title(conversation_id, heur_title, source="heuristic", final=False, manual=False)
    except Exception:
        # Non-fatal path: ignore failures to keep main UX responsive
        return

