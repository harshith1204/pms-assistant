from cachetools import TTLCache
from threading import RLock
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, BaseMessage, SystemMessage
import asyncio
from typing import Dict, Any, List, Optional, Set, Tuple
from datetime import datetime
from time import perf_counter
import math
from collections import deque
import os
import json
import logging
import redis.asyncio as aioredis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

class ScenarioOptimizedMemory:
    """Memory layer optimized for new conversations and loading old ones"""

    def __init__(
        self, 
        max_messages_per_conversation: int = 50,
        redis_url: Optional[str] = None,
        ttl_hours: int = 168,
        l1_cache_size: int = 250,      
        l1_cache_ttl_seconds: int = 300
    ):
        self.max_messages_per_conversation = max_messages_per_conversation
        self.ttl_seconds = ttl_hours * 3600
        
        # L1 Cache - stores (messages, summary) tuple for instant access
        # Summary is cached to avoid Redis calls on every L1 hit
        self.l1_cache: TTLCache[str, Tuple[deque[BaseMessage], Optional[str]]] = TTLCache(
            maxsize=l1_cache_size,
            ttl=l1_cache_ttl_seconds
        )
        self.l1_lock = RLock()
        
        # ✅ NEW: Track loading state to prevent duplicate loads
        self._loading_conversations: Set[str] = set()
        self._loading_lock = asyncio.Lock()
        
        # ✅ NEW: Track new conversations (no DB record yet)
        self._new_conversations: Set[str] = set()
        self._new_conversations_lock = RLock()
        
        default_redis_url = "redis://redis:6379/0"
        self.redis_url = redis_url or os.getenv("REDIS_URL") or default_redis_url
        self.redis_client: Optional[aioredis.Redis] = None
        self._connection_lock = asyncio.Lock()
        self._connected = False
        self._last_connection_check = 0
        self._connection_check_interval = 5.0
        
        self.use_fallback = False

    async def _ensure_connected(self, force: bool = False):
        """Optimized connection check with caching"""
        current_time = perf_counter()
        if not force and self._connected and self.redis_client:
            if current_time - self._last_connection_check < self._connection_check_interval:
                return
        
        async with self._connection_lock:
            if not force and self._connected and self.redis_client:
                if current_time - self._last_connection_check < self._connection_check_interval:
                    return
            
            if self._connected and self.redis_client:
                try:
                    await asyncio.wait_for(self.redis_client.ping(), timeout=0.1)
                    self._last_connection_check = current_time
                    return
                except (asyncio.TimeoutError, RedisError):
                    self._connected = False
            
            try:
                self.redis_client = await aioredis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    max_connections=50,  # Increased for concurrent loads
                    socket_connect_timeout=2,
                    socket_keepalive=True,
                    health_check_interval=30,
                )
                await asyncio.wait_for(self.redis_client.ping(), timeout=1.0)
                self._connected = True
                self._last_connection_check = current_time
                self.use_fallback = False
                logger.info("Redis connection established")
            except Exception as e:
                logger.error(f"Redis connection failed: {e}")
                self.use_fallback = True
                self._connected = False

    def _get_conversation_key(self, conversation_id: str) -> str:
        return f"conversation:messages:{conversation_id}"
    
    def _get_summary_key(self, conversation_id: str) -> str:
        return f"conversation:summary:{conversation_id}"
    
    def _get_turn_counter_key(self, conversation_id: str) -> str:
        return f"conversation:turns:{conversation_id}"

    def _serialize_message(self, message: BaseMessage) -> str:
        msg_dict = {
            "type": message.__class__.__name__,
            "content": message.content,
        }
        if hasattr(message, "tool_call_id"):
            msg_dict["tool_call_id"] = message.tool_call_id
        if hasattr(message, "tool_calls"):
            msg_dict["tool_calls"] = message.tool_calls
        if hasattr(message, "additional_kwargs"):
            msg_dict["additional_kwargs"] = message.additional_kwargs
        return json.dumps(msg_dict)

    def _deserialize_message(self, msg_str: str) -> BaseMessage:
        msg_dict = json.loads(msg_str)
        msg_type = msg_dict.get("type")
        content = msg_dict.get("content", "")
        
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
            return ToolMessage(content=content, tool_call_id=msg_dict.get("tool_call_id", ""))
        elif msg_type == "SystemMessage":
            return SystemMessage(content=content)
        else:
            return AIMessage(content=content)

    # ============================================================================
    # SCENARIO 1: NEW CONVERSATION - Optimized for instant first message
    # ============================================================================
    
    def mark_as_new_conversation(self, conversation_id: str):
        """✅ OPTIMIZATION: Mark conversation as new (no DB record yet)
        
        Call this when creating a new conversation to skip expensive DB lookups.
        """
        with self._new_conversations_lock:
            self._new_conversations.add(conversation_id)
        
        # Initialize empty L1 cache for this conversation (no summary yet)
        with self.l1_lock:
            self.l1_cache[conversation_id] = (
                deque(maxlen=self.max_messages_per_conversation),
                None  # No summary for new conversations
            )

    def _is_new_conversation(self, conversation_id: str) -> bool:
        """Check if this is a new conversation (no DB record)"""
        with self._new_conversations_lock:
            return conversation_id in self._new_conversations

    async def add_message(self, conversation_id: str, message: BaseMessage):
        """✅ OPTIMIZED: Ultra-fast for both new and existing conversations"""
        
        # Update L1 cache immediately (0.5-2ms)
        with self.l1_lock:
            # Get existing summary if present, preserve it when adding message
            existing_summary = None
            if conversation_id in self.l1_cache:
                messages_deque, existing_summary = self.l1_cache[conversation_id]
            else:
                messages_deque = deque(maxlen=self.max_messages_per_conversation)
            
            # Add new message
            messages_deque.append(message)
            
            # Store back with preserved summary
            self.l1_cache[conversation_id] = (messages_deque, existing_summary)  # Refresh TTL

        # Background Redis write (non-blocking)
        asyncio.create_task(self._add_message_to_redis_safe(conversation_id, message))

    async def _add_message_to_redis_safe(self, conversation_id: str, message: BaseMessage):
        """Background Redis write with error handling"""
        try:
            if not self.use_fallback:
                if not self._connected or not self.redis_client:
                    await self._ensure_connected()

                if self.use_fallback:
                    return

                key = self._get_conversation_key(conversation_id)
                serialized = self._serialize_message(message)

                async with self.redis_client.pipeline() as pipe:
                    pipe.rpush(key, serialized)
                    pipe.ltrim(key, -self.max_messages_per_conversation, -1)
                    pipe.expire(key, self.ttl_seconds)
                    await pipe.execute()
        except Exception as e:
            logger.warning(f"Background Redis write failed: {e}")

    # ============================================================================
    # SCENARIO 2: LOADING OLD CONVERSATION - Pre-warm cache before first message
    # ============================================================================
    
    async def pre_warm_conversation(self, conversation_id: str) -> bool:
        """✅ OPTIMIZATION: Eagerly load conversation into cache when user opens it
        
        Call this when:
        - User opens a conversation from the sidebar
        - User navigates to a conversation URL
        - Before the first message is sent
        
        This ensures the conversation is ready in L1 cache when user sends first message.
        
        Returns:
            bool: True if successfully loaded, False if conversation doesn't exist
        """
        # Check if already cached in L1
        with self.l1_lock:
            if conversation_id in self.l1_cache:
                return True
        
        # Check if this is a new conversation
        if self._is_new_conversation(conversation_id):
            return True
        
        # Prevent duplicate concurrent loads
        async with self._loading_lock:
            if conversation_id in self._loading_conversations:
                # Wait for the other load to complete
                while conversation_id in self._loading_conversations:
                    await asyncio.sleep(0.01)
                
                # Check if it's now in cache
                with self.l1_lock:
                    if conversation_id in self.l1_cache:
                        return True
                return False
            
            # Mark as loading
            self._loading_conversations.add(conversation_id)
        
        try:
            # ✅ OPTIMIZATION: Try Redis first (fast path, 5-20ms)
            messages = await self._load_from_redis_fast(conversation_id)
            
            if messages:
                # Redis hit - populate L1 with messages AND summary
                summary = await self._get_summary_fast(conversation_id)  # Fetch once
                with self.l1_lock:
                    self.l1_cache[conversation_id] = (
                        deque(messages, maxlen=self.max_messages_per_conversation),
                        summary  # ✅ Cache summary in L1
                    )
                return True
            
            # ✅ OPTIMIZATION: Load from MongoDB with parallel operations
            messages = await self._load_from_mongodb_optimized(conversation_id)
            
            if not messages:
                # ✅ CRITICAL FIX: Cache "not found" result to prevent repeated Redis/MongoDB lookups
                # Use empty deque + None summary to mark as "not found" (cached for short time via TTL)
                with self.l1_lock:
                    self.l1_cache[conversation_id] = (
                        deque(maxlen=self.max_messages_per_conversation),
                        None  # No summary = not found
                    )
                return False
            
            # Immediately populate L1 cache with messages AND summary
            summary = await self._get_summary_fast(conversation_id)  # Fetch once
            with self.l1_lock:
                self.l1_cache[conversation_id] = (
                    deque(messages[-self.max_messages_per_conversation:],
                          maxlen=self.max_messages_per_conversation),
                    summary  # ✅ Cache summary in L1
                )
            
            # Background: populate Redis for next access
            asyncio.create_task(self._cache_to_redis_background(conversation_id, messages))
            
            return True
            
        except Exception as e:
            logger.error(f"Pre-warm failed for {conversation_id}: {e}")
            return False
        finally:
            # Remove from loading set
            async with self._loading_lock:
                self._loading_conversations.discard(conversation_id)

    async def _load_from_redis_fast(self, conversation_id: str) -> List[BaseMessage]:
        """Fast Redis load with timeout"""
        try:
            await self._ensure_connected()
            if self.use_fallback or not self.redis_client:
                return []
            
            key = self._get_conversation_key(conversation_id)
            
            # Use pipeline for atomic read + TTL refresh
            async with self.redis_client.pipeline() as pipe:
                pipe.lrange(key, 0, -1)
                pipe.expire(key, self.ttl_seconds)
                results = await asyncio.wait_for(pipe.execute(), timeout=2.0)
            
            messages_str = results[0]
            if not messages_str:
                return []
            
            return [self._deserialize_message(msg_str) for msg_str in messages_str]
            
        except (asyncio.TimeoutError, RedisError) as e:
            logger.warning(f"Redis load timeout/error: {e}")
            return []

    async def _load_from_mongodb_optimized(self, conversation_id: str) -> List[BaseMessage]:
        """✅ OPTIMIZED: Fast MongoDB load with projection and timeout"""
        try:
            from mongo.conversations import conversation_mongo_client, CONVERSATIONS_DB_NAME, CONVERSATIONS_COLLECTION_NAME
            
            coll = await conversation_mongo_client.get_collection(CONVERSATIONS_DB_NAME, CONVERSATIONS_COLLECTION_NAME)
            
            # ✅ OPTIMIZATION: Only fetch recent messages (not entire history)
            # This is much faster for conversations with thousands of messages
            doc = await asyncio.wait_for(
                coll.find_one(
                {"conversationId": conversation_id},
                    {"messages": {"$slice": -100}}  # Last 100 messages only
                ),
                timeout=3.0  # 3 second timeout
            )
            
            if not doc:
                return []
            
            messages = doc.get("messages") or []
            if not messages:
                return []
            
            # Convert to LangChain messages
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
                    continue  # Skip tool/action messages
                
                lc_messages.append(lc_message)
            
            return lc_messages
            
        except asyncio.TimeoutError:
            logger.error(f"MongoDB load timeout for {conversation_id}")
            return []
        except Exception as e:
            logger.error(f"MongoDB load error: {e}")
            return []

    async def _cache_to_redis_background(self, conversation_id: str, messages: List[BaseMessage]):
        """Background task to populate Redis cache"""
        try:
            await self._ensure_connected()
            if self.use_fallback or not self.redis_client:
                return
                        
            key = self._get_conversation_key(conversation_id)
            serialized = [self._serialize_message(msg) for msg in messages]
            
            async with self.redis_client.pipeline() as pipe:
                pipe.delete(key)
                pipe.rpush(key, *serialized)
                pipe.ltrim(key, -self.max_messages_per_conversation, -1)
                pipe.expire(key, self.ttl_seconds)
                await pipe.execute()
        except Exception as e:
            logger.warning(f"Background Redis cache failed: {e}")

    # ============================================================================
    # EXISTING METHODS (with optimizations)
    # ============================================================================

    async def get_recent_context(self, conversation_id: str, max_tokens: int = 3000) -> List[BaseMessage]:
        """✅ OPTIMIZED: Fast context retrieval with L1 priority"""
        
        def approx_tokens(text: str) -> int:
            return max(1, math.ceil(len(text) / 4))

        budget = max(500, max_tokens)
        
        # Fast path: L1 cache (0.5-2ms) - NOW WITH CACHED SUMMARY!
        with self.l1_lock:
            if conversation_id in self.l1_cache:
                messages_deque, cached_summary = self.l1_cache[conversation_id]
                messages = list(messages_deque)
                if messages:
                    # ✅ NO REDIS CALL! Use cached summary from L1
                    return self._apply_token_budget(messages, cached_summary, budget, approx_tokens)
        
        # ✅ OPTIMIZATION: If new conversation, return empty immediately
        if self._is_new_conversation(conversation_id):
            return []
        
        # Slow path: Load from cache/DB
        messages = await self._load_from_redis_fast(conversation_id)
        
        if not messages:
            # Load from MongoDB with budget
            messages = await self._load_from_mongodb_with_budget(conversation_id, budget)
            
            # Populate L1 cache with messages AND summary
            if messages:
                # Fetch summary once and cache it
                summary = await self._get_summary_fast(conversation_id)
                with self.l1_lock:
                    self.l1_cache[conversation_id] = (
                        deque(messages[-self.max_messages_per_conversation:],
                              maxlen=self.max_messages_per_conversation),
                        summary  # ✅ Cache summary in L1
                    )
                return self._apply_token_budget(messages, summary, budget, approx_tokens)
        
        # Redis hit path - also cache summary
        summary = await self._get_summary_fast(conversation_id)
        with self.l1_lock:
            self.l1_cache[conversation_id] = (
                deque(messages[-self.max_messages_per_conversation:],
                      maxlen=self.max_messages_per_conversation),
                summary  # ✅ Cache summary
            )
        
        return self._apply_token_budget(messages, summary, budget, approx_tokens)

    async def _load_from_mongodb_with_budget(self, conversation_id: str, max_tokens: int) -> List[BaseMessage]:
        """✅ OPTIMIZED: Load only what's needed from MongoDB with streaming response
        
        When L1 and L2 both miss, this is the slow path (100-500ms).
        Optimizations:
        1. Use projection to fetch only recent messages (not entire history)
        2. Add timeout to prevent hanging
        3. Immediately populate L1 cache for instant subsequent access
        4. Background populate Redis for next session
        """
        try:
            from mongo.conversations import conversation_mongo_client, CONVERSATIONS_DB_NAME, CONVERSATIONS_COLLECTION_NAME
            
            estimated_messages = max(10, min(50, max_tokens // 100))
            coll = await conversation_mongo_client.get_collection(CONVERSATIONS_DB_NAME, CONVERSATIONS_COLLECTION_NAME)
            
            # ✅ OPTIMIZATION: Use projection + index for fast query
            doc = await asyncio.wait_for(
                coll.find_one(
                    {"conversationId": conversation_id},
                    {"messages": {"$slice": -estimated_messages}}  # Only recent messages
                ),
                timeout=3.0  # Fail fast if MongoDB is slow
            )
            
            if not doc:
                return []
            
            messages = doc.get("messages") or []
            lc_messages: List[BaseMessage] = []
            
            # Convert to LangChain messages
            for msg in messages:
                if not isinstance(msg, dict):
                    continue
                
                msg_type = msg.get("type", "assistant")
                content = msg.get("content", "")
                
                if msg_type == "user":
                    lc_messages.append(HumanMessage(content=content))
                elif msg_type == "assistant":
                    lc_messages.append(AIMessage(content=content))
                elif msg_type == "system":
                    lc_messages.append(SystemMessage(content=content))
            
            # ✅ CRITICAL: Immediately populate L1 cache for next access (with summary)
            if lc_messages:
                # Fetch summary once and cache it
                summary = await self._get_summary_fast(conversation_id)
                with self.l1_lock:
                    self.l1_cache[conversation_id] = (
                        deque(lc_messages[-self.max_messages_per_conversation:],
                              maxlen=self.max_messages_per_conversation),
                        summary  # ✅ Cache summary in L1
                    )
                
                # ✅ OPTIMIZATION: Background populate Redis for next session
                asyncio.create_task(
                    self._cache_to_redis_background(conversation_id, lc_messages)
                )
            
            return lc_messages
            
        except asyncio.TimeoutError:
            logger.error(f"MongoDB load timeout for {conversation_id}")
            return []
        except Exception as e:
            logger.error(f"MongoDB load error for {conversation_id}: {e}")
            return []

    def _apply_token_budget(
        self, 
        messages: List[BaseMessage], 
        summary: Optional[str], 
        budget: int,
        approx_tokens
    ) -> List[BaseMessage]:
        """Apply token budget to messages"""
        summary_tokens = 0
        if summary:
            summary_tokens = approx_tokens(summary) + 50
        
        message_budget = budget - summary_tokens
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
            selected = [SystemMessage(content=f"Conversation summary:\n{summary}")] + selected

        return selected

    async def _get_summary_fast(self, conversation_id: str) -> Optional[str]:
        """Fast summary retrieval"""
        try:
            await self._ensure_connected()
            if self.use_fallback or not self.redis_client:
                return None
            
            key = self._get_summary_key(conversation_id)
            return await asyncio.wait_for(
                self.redis_client.get(key),
                timeout=0.5
            )
        except (asyncio.TimeoutError, RedisError):
            return None

    async def close(self):
        """Close connections"""
        if self.redis_client:
            await self.redis_client.close()
            self._connected = False

# Global instance
conversation_memory = ScenarioOptimizedMemory()