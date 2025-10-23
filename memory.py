
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, BaseMessage, SystemMessage
from langchain_core.callbacks import AsyncCallbackHandler
import asyncio
import contextlib
from typing import Dict, Any, List, AsyncGenerator, Optional
from typing import Tuple
import tools
from datetime import datetime
import time
import math
from collections import defaultdict, deque
import os
import json
import redis.asyncio as aioredis
from redis.exceptions import RedisError

class RedisConversationMemory:
    """Manages conversation history in Redis cache for scalable, persistent context management
    
    Features:
    - Redis-based storage independent of socket connections
    - 24-hour TTL for automatic cache cleanup
    - Prevents server memory overload
    - Persistent across server restarts
    - Same memory management mechanism as before
    """

    def __init__(
        self, 
        max_messages_per_conversation: int = 50,
        redis_url: Optional[str] = None,
        ttl_hours: int = 24
    ):
        self.max_messages_per_conversation = max_messages_per_conversation
        self.ttl_seconds = ttl_hours * 3600  # 24 hours = 86400 seconds
        
        # Initialize Redis connection
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.redis_client: Optional[aioredis.Redis] = None
        self._connection_lock = asyncio.Lock()
        self._connected = False
        
        # Fallback to in-memory cache if Redis is unavailable
        self.fallback_conversations: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_messages_per_conversation))
        self.fallback_summaries: Dict[str, str] = {}
        self.fallback_turn_counters: Dict[str, int] = defaultdict(int)
        self.use_fallback = False

    async def _ensure_connected(self):
        """Ensure Redis connection is established"""
        if self._connected and self.redis_client:
            return
        
        async with self._connection_lock:
            if self._connected and self.redis_client:
                return
            
            try:
                self.redis_client = await aioredis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    max_connections=20,
                    socket_connect_timeout=5,
                    socket_keepalive=True,
                    health_check_interval=30,
                )
                # Test connection
                await self.redis_client.ping()
                self._connected = True
                self.use_fallback = False
                print(f"✅ Redis conversation memory connected: {self.redis_url}")
            except Exception as e:
                print(f"⚠️ Redis connection failed, using in-memory fallback: {e}")
                self.use_fallback = True
                self._connected = False

    def _get_conversation_key(self, conversation_id: str) -> str:
        """Get Redis key for conversation messages"""
        return f"conversation:messages:{conversation_id}"
    
    def _get_summary_key(self, conversation_id: str) -> str:
        """Get Redis key for conversation summary"""
        return f"conversation:summary:{conversation_id}"
    
    def _get_turn_counter_key(self, conversation_id: str) -> str:
        """Get Redis key for turn counter"""
        return f"conversation:turns:{conversation_id}"

    def _serialize_message(self, message: BaseMessage) -> str:
        """Serialize a LangChain message to JSON string"""
        msg_dict = {
            "type": message.__class__.__name__,
            "content": message.content,
        }
        
        # Add additional fields for specific message types
        if hasattr(message, "tool_call_id"):
            msg_dict["tool_call_id"] = message.tool_call_id
        if hasattr(message, "tool_calls"):
            msg_dict["tool_calls"] = message.tool_calls
        if hasattr(message, "additional_kwargs"):
            msg_dict["additional_kwargs"] = message.additional_kwargs
            
        return json.dumps(msg_dict)

    def _deserialize_message(self, msg_str: str) -> BaseMessage:
        """Deserialize JSON string back to LangChain message"""
        msg_dict = json.loads(msg_str)
        msg_type = msg_dict.get("type")
        content = msg_dict.get("content", "")
        
        # Reconstruct the appropriate message type
        if msg_type == "HumanMessage":
            return HumanMessage(content=content)
        elif msg_type == "AIMessage":
            msg = AIMessage(content=content)
            if "tool_calls" in msg_dict:
                msg.tool_calls = msg_dict["tool_calls"]
            if "additional_kwargs" in msg_dict:
                msg.additional_kwargs = msg_dict["additional_kwargs"]
            return msg
        elif msg_type == "ToolMessage":
            return ToolMessage(
                content=content,
                tool_call_id=msg_dict.get("tool_call_id", "")
            )
        elif msg_type == "SystemMessage":
            return SystemMessage(content=content)
        else:
            # Default to AIMessage for unknown types
            return AIMessage(content=content)

    async def add_message(self, conversation_id: str, message: BaseMessage):
        """Add a message to the conversation history in Redis"""
        await self._ensure_connected()
        
        if self.use_fallback:
            # Use in-memory fallback
            self.fallback_conversations[conversation_id].append(message)
            return
        
        try:
            key = self._get_conversation_key(conversation_id)
            serialized = self._serialize_message(message)
            
            # Add message to Redis list
            await self.redis_client.rpush(key, serialized)
            
            # Trim list to max size (keep only recent messages)
            await self.redis_client.ltrim(key, -self.max_messages_per_conversation, -1)
            
            # Set TTL (24 hours)
            await self.redis_client.expire(key, self.ttl_seconds)
            
        except RedisError as e:
            print(f"⚠️ Redis error in add_message, falling back to memory: {e}")
            self.use_fallback = True
            self.fallback_conversations[conversation_id].append(message)

    async def get_conversation_history(self, conversation_id: str) -> List[BaseMessage]:
        """Get the conversation history for a given conversation ID from Redis"""
        await self._ensure_connected()
        
        if self.use_fallback:
            return list(self.fallback_conversations[conversation_id])
        
        try:
            key = self._get_conversation_key(conversation_id)
            
            # Get all messages from Redis list
            messages_str = await self.redis_client.lrange(key, 0, -1)
            
            if not messages_str:
                return []
            
            # Deserialize messages
            messages = [self._deserialize_message(msg_str) for msg_str in messages_str]
            
            # Refresh TTL on access
            await self.redis_client.expire(key, self.ttl_seconds)
            
            return messages
            
        except RedisError as e:
            print(f"⚠️ Redis error in get_conversation_history, falling back to memory: {e}")
            self.use_fallback = True
            return list(self.fallback_conversations[conversation_id])

    async def clear_conversation(self, conversation_id: str):
        """Clear the conversation history for a given conversation ID"""
        await self._ensure_connected()
        
        if self.use_fallback:
            if conversation_id in self.fallback_conversations:
                self.fallback_conversations[conversation_id].clear()
            return
        
        try:
            # Delete all keys related to this conversation
            keys_to_delete = [
                self._get_conversation_key(conversation_id),
                self._get_summary_key(conversation_id),
                self._get_turn_counter_key(conversation_id),
            ]
            await self.redis_client.delete(*keys_to_delete)
            
        except RedisError as e:
            print(f"⚠️ Redis error in clear_conversation: {e}")
            if conversation_id in self.fallback_conversations:
                self.fallback_conversations[conversation_id].clear()

    async def get_recent_context(self, conversation_id: str, max_tokens: int = 3000) -> List[BaseMessage]:
        """Get recent conversation context with a token budget and rolling summary."""
        messages = await self.get_conversation_history(conversation_id)

        # Approximate token counting (≈4 chars/token)
        def approx_tokens(text: str) -> int:
            try:
                return max(1, math.ceil(len(text) / 4))
            except Exception:
                return len(text) // 4

        budget = max(500, max_tokens)
        used = 0
        selected: List[BaseMessage] = []

        # Walk backwards to select most recent turns under budget
        for msg in reversed(messages):
            content = getattr(msg, "content", "")
            used += approx_tokens(str(content)) + 8
            if used > budget:
                break
            selected.append(msg)

        selected.reverse()

        # Prepend rolling summary if present and within budget
        summary = await self._get_summary(conversation_id)
        if summary:
            stoks = approx_tokens(summary)
            if used + stoks <= budget:
                selected = [SystemMessage(content=f"Conversation summary (condensed):\n{summary}")] + selected

        return selected

    async def _get_summary(self, conversation_id: str) -> Optional[str]:
        """Get conversation summary from Redis"""
        await self._ensure_connected()
        
        if self.use_fallback:
            return self.fallback_summaries.get(conversation_id)
        
        try:
            key = self._get_summary_key(conversation_id)
            summary = await self.redis_client.get(key)
            
            if summary:
                # Refresh TTL on access
                await self.redis_client.expire(key, self.ttl_seconds)
            
            return summary
            
        except RedisError as e:
            print(f"⚠️ Redis error in _get_summary: {e}")
            return self.fallback_summaries.get(conversation_id)

    async def _set_summary(self, conversation_id: str, summary: str):
        """Set conversation summary in Redis"""
        await self._ensure_connected()
        
        if self.use_fallback:
            self.fallback_summaries[conversation_id] = summary
            return
        
        try:
            key = self._get_summary_key(conversation_id)
            await self.redis_client.set(key, summary, ex=self.ttl_seconds)
            
        except RedisError as e:
            print(f"⚠️ Redis error in _set_summary: {e}")
            self.fallback_summaries[conversation_id] = summary

    async def register_turn(self, conversation_id: str) -> None:
        """Register a conversation turn in Redis"""
        await self._ensure_connected()
        
        if self.use_fallback:
            self.fallback_turn_counters[conversation_id] += 1
            return
        
        try:
            key = self._get_turn_counter_key(conversation_id)
            await self.redis_client.incr(key)
            await self.redis_client.expire(key, self.ttl_seconds)
            
        except RedisError as e:
            print(f"⚠️ Redis error in register_turn: {e}")
            self.fallback_turn_counters[conversation_id] += 1

    async def should_update_summary(self, conversation_id: str, every_n_turns: int = 3) -> bool:
        """Check if summary should be updated based on turn count"""
        await self._ensure_connected()
        
        if self.use_fallback:
            return self.fallback_turn_counters[conversation_id] % every_n_turns == 0
        
        try:
            key = self._get_turn_counter_key(conversation_id)
            count = await self.redis_client.get(key)
            
            if count is None:
                return False
            
            return int(count) % every_n_turns == 0
            
        except RedisError as e:
            print(f"⚠️ Redis error in should_update_summary: {e}")
            return self.fallback_turn_counters[conversation_id] % every_n_turns == 0

    async def update_summary_async(self, conversation_id: str, llm_for_summary) -> None:
        """Update the rolling summary asynchronously to avoid latency in main path."""
        try:
            history = await self.get_conversation_history(conversation_id)
            if not history:
                return
            recent = history[-12:]
            prompt = [
                SystemMessage(content=(
                    "Summarize the durable facts, goals, and decisions from the conversation. "
                    "Keep it 6-10 bullets, under 600 tokens. Avoid chit-chat."
                ))
            ] + recent + [HumanMessage(content="Produce condensed summary now.")]
            resp = await llm_for_summary.ainvoke(prompt)
            if getattr(resp, "content", None):
                await self._set_summary(conversation_id, str(resp.content))
        except Exception as e:
            # Best-effort; log but don't fail
            print(f"⚠️ Failed to update summary: {e}")

    async def close(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()
            self._connected = False
            print("✅ Redis conversation memory disconnected")

# Global conversation memory instance using Redis
conversation_memory = RedisConversationMemory()
