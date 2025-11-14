from cachetools import TTLCache
from threading import Lock
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, BaseMessage, SystemMessage
from langchain_core.callbacks import AsyncCallbackHandler
import asyncio
import contextlib
from typing import Dict, Any, List, AsyncGenerator, Optional
from typing import Tuple
from agent.tools import tools
from datetime import datetime
import time
import math
from collections import defaultdict, deque
import os
import json
import logging
import redis.asyncio as aioredis
from redis.exceptions import RedisError

# Configure logging
logger = logging.getLogger(__name__)

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
        ttl_hours: int = 168,  # ✅ OPTIMIZED: 7 days (168 hours) instead of 24 hours
        l1_cache_size: int = 250,      
        l1_cache_ttl_seconds: int = 300
    ):
        self.max_messages_per_conversation = max_messages_per_conversation
        self.ttl_seconds = ttl_hours * 3600  # 7 days = 604800 seconds
        
        # --- New L1 Cache ---
        self.l1_cache: TTLCache[str, deque[BaseMessage]] = TTLCache(
            maxsize=l1_cache_size,
            ttl=l1_cache_ttl_seconds
        )
        self.l1_lock = Lock()  # Thread-safe lock for L1
        # Initialize Redis connection
        default_redis_url = "redis://redis:6379/0"
        self.redis_url = redis_url or os.getenv("REDIS_URL") or default_redis_url
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
            except Exception as e:
                logger.error(f"Redis connection failed, using in-memory fallback: {e}")
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
        # --- L1 Cache Write (Thread-safe) ---
        with self.l1_lock:
            if conversation_id not in self.l1_cache:
                self.l1_cache[conversation_id] = deque(maxlen=self.max_messages_per_conversation)
            self.l1_cache[conversation_id].append(message)
                # Re-assign to update its TTL status
            self.l1_cache[conversation_id] = self.l1_cache[conversation_id]

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
            logger.error(f"Redis error in add_message, falling back to memory: {e}")
            self.use_fallback = True
            self.fallback_conversations[conversation_id].append(message)

    async def get_conversation_history(self, conversation_id: str) -> List[BaseMessage]:
        """Get the conversation history for a given conversation ID from Redis
        
        If not in cache, returns empty list (will be populated as new messages are added).
        Use get_recent_context() instead to get context from MongoDB when cache is empty.
        """
        with self.l1_lock:
            if conversation_id in self.l1_cache:
                # L1 Hit: Fastest path
                return list(self.l1_cache[conversation_id])
            
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

            with self.l1_lock:
                self.l1_cache[conversation_id] = deque(
                    messages, 
                    maxlen=self.max_messages_per_conversation
                )
            # Refresh TTL on access
            await self.redis_client.expire(key, self.ttl_seconds)
            
            return messages
            
        except RedisError as e:
            logger.error(f"Redis error in get_conversation_history, falling back to memory: {e}")
            self.use_fallback = True
            return list(self.fallback_conversations[conversation_id])

    async def clear_conversation(self, conversation_id: str):
        """Clear the conversation history for a given conversation ID"""
        with self.l1_lock:
            if conversation_id in self.l1_cache:
                try:
                    del self.l1_cache[conversation_id]
                except KeyError:
                    pass
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
            logger.error(f"Redis error in clear_conversation: {e}")
            if conversation_id in self.fallback_conversations:
                self.fallback_conversations[conversation_id].clear()

    async def get_recent_context(self, conversation_id: str, max_tokens: int = 3000) -> List[BaseMessage]:
        """Get recent conversation context with a token budget and rolling summary.
        
        ✅ OPTIMIZED: 
        1. First checks L1 cache (in-memory) for fastest access
        2. Then checks Redis cache (L2) for fast access
        3. If cache is empty/expired, loads ONLY recent messages from MongoDB (within token budget)
        4. Applies consistent token budget selection (handles both cache hit and miss)
        5. Adds summary if it fits within budget
        """
        # Approximate token counting (≈4 chars/token)
        def approx_tokens(text: str) -> int:
            try:
                return max(1, math.ceil(len(text) / 4))
            except Exception:
                return len(text) // 4

        budget = max(500, max_tokens)
        
        # ✅ OPTIMIZED: Check L1 cache first (fastest path)
        with self.l1_lock:
            if conversation_id in self.l1_cache:
                messages = list(self.l1_cache[conversation_id])
                if messages:
                    # L1 cache hit - skip Redis check
                    summary = await self._get_summary(conversation_id)
                    summary_tokens = 0
                    if summary:
                        summary_tokens = approx_tokens(summary) + 50
                    message_budget = budget - summary_tokens
                    
                    # Apply token budget selection
                    used = 0
                    selected: List[BaseMessage] = []
                    for msg in reversed(messages):
                        content = getattr(msg, "content", "")
                        msg_tokens = approx_tokens(str(content)) + 8
                        if used + msg_tokens > message_budget and selected:
                            break
                        selected.append(msg)
                        used += msg_tokens
                    selected.reverse()
                    
                    if summary and summary_tokens <= budget - used:
                        selected = [SystemMessage(content=f"Conversation summary (condensed):\n{summary}")] + selected
                    
                    return selected
        
        # Reserve space for summary (if present)
        summary = await self._get_summary(conversation_id)
        summary_tokens = 0
        if summary:
            summary_tokens = approx_tokens(summary) + 50  # +50 for formatting
        
        # Adjust budget for messages to leave room for summary
        message_budget = budget - summary_tokens
        
        # Try to get from Redis cache (L2) - only if L1 miss
        messages = await self.get_conversation_history(conversation_id)
        
        # If cache is empty, load recent messages from MongoDB
        if not messages:
            try:
                # Load with adjusted budget (accounting for summary)
                messages = await self._load_recent_from_mongodb(conversation_id, message_budget)
            except Exception as e:
                logger.error(f"Could not load recent messages from MongoDB: {e}")
                messages = []
        
        # Apply token budget selection while keeping tool-call batches intact.
        # We group an assistant request with its subsequent tool responses so
        # trimming never drops one side of the exchange.
        segments: List[Tuple[List[BaseMessage], int]] = []
        idx = 0
        while idx < len(messages):
            msg = messages[idx]
            group: List[BaseMessage] = [msg]
            group_tokens = approx_tokens(str(getattr(msg, "content", ""))) + 8
            idx += 1

            if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
                while idx < len(messages):
                    following = messages[idx]
                    if not isinstance(following, ToolMessage):
                        break
                    group.append(following)
                    group_tokens += approx_tokens(str(getattr(following, "content", ""))) + 8
                    idx += 1

            segments.append((group, group_tokens))

        used = 0
        selected_messages: deque[BaseMessage] = deque()

        for group, group_tokens in reversed(segments):
            if used and used + group_tokens > message_budget:
                break
            for message in reversed(group):
                selected_messages.appendleft(message)
            used += group_tokens

        selected = list(selected_messages)

        # Prepend rolling summary if present
        if summary and summary_tokens <= budget - used:
            selected = [SystemMessage(content=f"Conversation summary (condensed):\n{summary}")] + selected
            used += summary_tokens

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
            logger.error(f"Redis error in _get_summary: {e}")
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
            logger.error(f"Redis error in _set_summary: {e}")
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
            logger.error(f"Redis error in register_turn: {e}")
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
            logger.error(f"Redis error in should_update_summary: {e}")
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
            logger.error(f"Failed to update summary: {e}")

    async def _load_recent_from_mongodb(self, conversation_id: str, max_tokens: int = 3000) -> List[BaseMessage]:
        """Load ONLY recent messages from MongoDB (limited by token budget).
        
        ✅ OPTIMIZED: Uses MongoDB projection with $slice to fetch only recent messages.
        This is much more efficient than loading entire conversation history.
        Only loads what's actually needed for context.
        
        Returns:
            List of recent messages (already within token budget)
        """
        try:
            # Import here to avoid circular dependency
            from mongo.conversations import conversation_mongo_client, CONVERSATIONS_DB_NAME, CONVERSATIONS_COLLECTION_NAME
            
            # ✅ OPTIMIZED: Use projection with $slice to fetch only recent messages
            # Estimate: ~100 tokens per message, so fetch last N messages where N = max_tokens / 100
            estimated_messages = max(10, min(50, max_tokens // 100))
            
            coll = await conversation_mongo_client.get_collection(CONVERSATIONS_DB_NAME, CONVERSATIONS_COLLECTION_NAME)
            # Use projection to fetch only the last N messages
            doc = await coll.find_one(
                {"conversationId": conversation_id},
                {"messages": {"$slice": -estimated_messages}}  # Only fetch last N messages
            )
            
            if not doc:
                return []
            
            messages = doc.get("messages") or []
            if not messages:
                return []
            
            # Approximate token counting
            def approx_tokens(text: str) -> int:
                try:
                    return max(1, math.ceil(len(text) / 4))
                except Exception:
                    return len(text) // 4
            
            # Load recent messages within token budget (work backwards)
            budget = max(500, max_tokens)
            used = 0
            recent_messages: List[BaseMessage] = []
            
            # Start from end (most recent) and work backwards
            for msg in reversed(messages):
                if not isinstance(msg, dict):
                    continue
                
                msg_type = msg.get("type", "assistant")
                content = msg.get("content", "")
                
                # Check token budget
                msg_tokens = approx_tokens(str(content)) + 8
                if used + msg_tokens > budget and recent_messages:
                    # Budget exceeded, stop loading
                    break
                
                # Convert to appropriate LangChain message type
                if msg_type == "user":
                    lc_message = HumanMessage(content=content)
                elif msg_type == "assistant":
                    lc_message = AIMessage(content=content)
                elif msg_type == "system":
                    lc_message = SystemMessage(content=content)
                else:
                    # Skip action/tool/work_item/page messages
                    continue
                
                recent_messages.append(lc_message)
                used += msg_tokens
            
            # Reverse to get chronological order
            recent_messages.reverse()
            
            # Optionally cache in Redis for next access (background task, non-blocking)
            if recent_messages:
                asyncio.create_task(self._cache_messages_background(conversation_id, recent_messages))
            
            return recent_messages
            
        except Exception as e:
            logger.error(f"Failed to load recent messages from MongoDB: {e}")
            return []

    # async def _cache_messages_background(self, conversation_id: str, messages: List[BaseMessage]) -> None:
    #     """Cache messages in Redis as a background task (non-blocking)"""
    #     try:
    #         for msg in messages:
    #             await self.add_message(conversation_id, msg)
    #     except Exception as e:
    #         logger.error(f"Background cache failed: {e}")
    async def _cache_messages_background(self, conversation_id: str, messages: List[BaseMessage]) -> None:
        """Optimized: Cache messages in L1 and L2 (using pipeline)"""
        
        # --- L1 Cache Populate (Thread-safe) ---
        with self.l1_lock:
            # We only cache the most recent messages, matching maxlen
            self.l1_cache[conversation_id] = deque(
                messages, 
                maxlen=self.max_messages_per_conversation
            )
        # --- End L1 Populate ---

        await self._ensure_connected()
        if self.use_fallback or not self.redis_client:
            self.fallback_conversations[conversation_id].extend(messages)
            return

        try:
            # --- Optimized: Use pipeline for L2 write ---
            key = self._get_conversation_key(conversation_id)
            serialized = [self._serialize_message(msg) for msg in messages]
            
            async with self.redis_client.pipeline() as pipe:
                pipe.delete(key)  # Clear old entries
                pipe.rpush(key, *serialized) # Add all
                pipe.ltrim(key, -self.max_messages_per_conversation, -1) # Trim
                pipe.expire(key, self.ttl_seconds)
                await pipe.execute()
            # --- End L2 Pipeline ---

        except Exception as e:
            logger.error(f"Background cache failed: {e}")
            # Populate fallback as a last resort
            self.fallback_conversations[conversation_id].extend(messages)

    # async def load_conversation_from_mongodb(self, conversation_id: str) -> bool:
    #     """Load an existing conversation from MongoDB into Redis cache
        
    #     This is called when a user opens an older conversation to ensure it's
    #     available in Redis cache for fast access.
        
    #     Returns:
    #         bool: True if conversation was loaded successfully, False otherwise
    #     """
    #     try:
    #         # Import here to avoid circular dependency
    #         from mongo.conversations import conversation_mongo_client, CONVERSATIONS_DB_NAME, CONVERSATIONS_COLLECTION_NAME
            
    #         # Fetch conversation from MongoDB
    #         coll = await conversation_mongo_client.get_collection(CONVERSATIONS_DB_NAME, CONVERSATIONS_COLLECTION_NAME)
    #         doc = await coll.find_one({"conversationId": conversation_id})
            
    #         if not doc:
    #             return False
            
    #         messages = doc.get("messages") or []
    #         if not messages:
    #             return False
            
    #         # Convert MongoDB messages to LangChain messages and load into Redis
    #         loaded_count = 0
    #         for msg in messages:
    #             if not isinstance(msg, dict):
    #                 continue
                
    #             msg_type = msg.get("type", "assistant")
    #             content = msg.get("content", "")
                
    #             # Convert to appropriate LangChain message type
    #             if msg_type == "user":
    #                 lc_message = HumanMessage(content=content)
    #             elif msg_type == "assistant":
    #                 lc_message = AIMessage(content=content)
    #             elif msg_type == "system":
    #                 lc_message = SystemMessage(content=content)
    #             else:
    #                 # Skip action/tool/work_item/page messages for now
    #                 # Only load conversational messages into memory
    #                 continue
                
    #             # Add to Redis cache
    #             await self.add_message(conversation_id, lc_message)
    #             loaded_count += 1
            
    #         return True
            
    #     except Exception as e:
    #         logger.error(f"Failed to load conversation from MongoDB: {e}")
    #         return False
    async def load_conversation_from_mongodb(self, conversation_id: str) -> bool:
        """Load an existing conversation from MongoDB into L1/L2 cache
           using a single efficient Redis pipeline.
        """
        try:
            # Import here to avoid circular dependency
            from mongo.conversations import conversation_mongo_client, CONVERSATIONS_DB_NAME, CONVERSATIONS_COLLECTION_NAME
            
            # Fetch conversation from MongoDB
            coll = await conversation_mongo_client.get_collection(CONVERSATIONS_DB_NAME, CONVERSATIONS_COLLECTION_NAME)
            doc = await coll.find_one({"conversationId": conversation_id})
            
            if not doc:
                return False
            
            messages = doc.get("messages") or []
            if not messages:
                return False
            
            # Convert MongoDB messages to LangChain messages
            lc_messages: List[BaseMessage] = []
            for msg in messages:
                if not isinstance(msg, dict):
                    continue
                
                msg_type = msg.get("type", "assistant")
                content = msg.get("content", "")
                
                if msg_type == "user":
                    lc_message = HumanMessage(content=content)
                elif msg_type == "assistant":
                    lc_message = AIMessage(content=content)
                elif msg_type == "system":
                    lc_message = SystemMessage(content=content)
                else:
                    continue
                lc_messages.append(lc_message)

            if not lc_messages:
                return False

            # --- This is the fix ---
            # Call the single efficient function
            # This is non-blocking by default, but even if awaited,
            # it's just 1 Mongo read + 1 Redis pipeline.
            await self._cache_messages_background(conversation_id, lc_messages)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to load conversation from MongoDB: {e}")
            return False

    async def ensure_conversation_cached(self, conversation_id: str) -> None:
        """Ensure a conversation is cached in Redis, loading from MongoDB if needed
        
        This should be called at the start of any conversation interaction to ensure
        the conversation history is available in Redis cache.
        """
        with self.l1_lock:
            if conversation_id in self.l1_cache:
                return
            
        await self._ensure_connected()
        
        # Check if conversation exists in Redis
        key = self._get_conversation_key(conversation_id)
        
        if self.use_fallback:
            # In fallback mode, try to load from MongoDB
            await self.load_conversation_from_mongodb(conversation_id)
            return
        
        try:
            exists = await self.redis_client.exists(key)
            
            if exists:
                # Conversation is cached, refresh TTL
                await self.redis_client.expire(key, self.ttl_seconds)
            else:
                # Conversation not in cache, load from MongoDB
                await self.load_conversation_from_mongodb(conversation_id)
                
        except RedisError as e:
            logger.error(f"Redis error in ensure_conversation_cached: {e}")
            # Try to load from MongoDB anyway
            await self.load_conversation_from_mongodb(conversation_id)

    async def close(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()
            self._connected = False

# Global conversation memory instance using Redis
conversation_memory = RedisConversationMemory()
