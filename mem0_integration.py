"""
Mem0 integration for intelligent memory management with LLM and database storage.

This module replaces the basic ConversationMemory with Mem0's advanced features:
- LLM-powered memory extraction and summarization
- Vector database storage for semantic search
- Automatic memory relevance scoring and filtering
- Support for user, agent, and session-level memories
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import os
from copy import deepcopy
from mem0 import Memory
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from dotenv import load_dotenv
try:
    # Prefer existing Qdrant config from the codebase
    from mongo import constants as mongo_constants
except Exception:
    mongo_constants = None

# Load environment variables from .env file
load_dotenv()


class Mem0Manager:
    """
    Manages conversational memory using Mem0 for intelligent, LLM-powered memory storage.

    Features:
    - Automatically extracts important facts and context from conversations
    - Stores memories in existing Qdrant cloud instance (GCP) for semantic retrieval
    - Uses LLM to determine memory relevance and summarization
    - Supports user-specific and agent-specific memory scoping
    - Uses existing embedding model (google/embeddinggemma-300m) for consistency

    Hard-coded configuration to match existing infrastructure:
    - Qdrant cloud URL: dc88ad91-1e1e-48b4-bf73-0e5c1db1cffd.europe-west3-0.gcp.cloud.qdrant.io
    - Qdrant collection: mem0_memories
    - Embedding model: google/embeddinggemma-300m (768 dimensions)
    - LLM provider: groq (configurable via GROQ_API_KEY and GROQ_MODEL env vars)
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize Mem0Manager with configuration.

        Args:
            config: Optional configuration dict. If not provided, uses hard-coded existing infrastructure:
                   - Qdrant cloud instance on GCP
                   - google/embeddinggemma-300m embedding model
                   - groq LLM provider
        """
        if config is None:
            config = self._get_default_config()

        # Store and validate config before initializing Mem0
        self.config = config
        try:
            self._validate_config(self.config)
        except Exception as e:
            print("❌ Mem0 configuration validation failed:", e)
            print("ℹ️  Effective Mem0 config (sanitized):")
            print(self._sanitize_config(self.config))
            raise

        try:
            self.memory = Memory.from_config(self.config)
            print("✅ Mem0 memory manager initialized with configuration")
        except Exception as e:
            print("❌ Mem0 initialization error:", repr(e))
            print("ℹ️  Effective Mem0 config (sanitized):")
            print(self._sanitize_config(self.config))
            # Provide common hints
            groq_key_missing = (
                (self.config.get("llm", {}).get("provider") == "groq") and not os.getenv("GROQ_API_KEY")
            )
            if groq_key_missing:
                print("➡️  Hint: Set GROQ_API_KEY or switch MEM0_LLM_PROVIDER to a provider with a configured API key.")
            if "cloud.qdrant.io" in (self.config.get("vector_store", {}).get("config", {}).get("url", "") or "") and not os.getenv("QDRANT_API_KEY") and not (mongo_constants and getattr(mongo_constants, "QDRANT_API_KEY", None)):
                print("➡️  Hint: Set QDRANT_API_KEY for Qdrant Cloud access.")
            raise
        
        # Track recent messages for context (lightweight buffer before Mem0 processing)
        self.recent_messages: Dict[str, List[BaseMessage]] = {}
        self.max_recent_messages = 10  # Keep last 10 messages for immediate context
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Build Mem0 configuration using repo/environment settings safely (no hard-coded secrets)."""

        # Resolve Qdrant settings (prefer env, then repo constants)
        qdrant_url = os.getenv("QDRANT_URL") or (getattr(mongo_constants, "QDRANT_URL", None) if mongo_constants else None)
        qdrant_api_key = os.getenv("QDRANT_API_KEY") or (getattr(mongo_constants, "QDRANT_API_KEY", None) if mongo_constants else None)
        collection_name = os.getenv("MEM0_QDRANT_COLLECTION", "mem0_memories")

        # LLM settings
        llm_provider = os.getenv("MEM0_LLM_PROVIDER", "groq").lower()
        groq_api_key = os.getenv("GROQ_API_KEY")
        groq_model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

        # Lightweight, readily available embedding model
        embedding_model = os.getenv("MEM0_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

        config: Dict[str, Any] = {
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "collection_name": collection_name,
                    # Provide both keys for compatibility with qdrant-client
                    "url": qdrant_url,
                    "host": qdrant_url,
                    "api_key": qdrant_api_key,
                    "prefer_grpc": False,
                },
            },
            "llm": {
                "provider": llm_provider,
                "config": {
                    "model": groq_model,
                    "temperature": 0.1,
                    "max_tokens": 1000,
                },
            },
            "embedder": {
                "provider": "huggingface",
                "config": {
                    "model": embedding_model,
                },
            },
            "version": "v1.1",
        }

        # Attach API key for Groq if using that provider
        if config["llm"]["provider"] == "groq" and groq_api_key:
            config["llm"]["config"]["api_key"] = groq_api_key

        return config

    def _validate_config(self, config: Dict[str, Any]) -> None:
        """Validate config and environment; raise ValueError with actionable guidance on failure."""
        # Qdrant checks
        vs = config.get("vector_store", {})
        if vs.get("provider") != "qdrant":
            raise ValueError("Only 'qdrant' vector_store is supported by this integration.")
        qconf = vs.get("config", {})
        q_url = qconf.get("url") or qconf.get("host")
        if not q_url:
            raise ValueError("QDRANT_URL is not set. Provide via env QDRANT_URL or mongo.constants.QDRANT_URL.")
        if "cloud.qdrant.io" in (q_url or ""):
            q_api = qconf.get("api_key")
            if not q_api:
                raise ValueError("QDRANT_API_KEY is required for Qdrant Cloud. Set env QDRANT_API_KEY.")

        # LLM checks
        llm = config.get("llm", {})
        provider = (llm.get("provider") or "").lower()
        if provider == "groq" and not os.getenv("GROQ_API_KEY") and not llm.get("config", {}).get("api_key"):
            raise ValueError("GROQ_API_KEY is missing. Set it in environment to use Groq LLM.")

        # Embedder checks
        emb = config.get("embedder", {})
        if emb.get("provider") != "huggingface":
            raise ValueError("Only 'huggingface' embedder is configured here. Set MEM0_EMBED_MODEL or adjust provider.")
        model_name = (emb.get("config", {}) or {}).get("model")
        if not model_name:
            raise ValueError("MEM0_EMBED_MODEL must specify a model name (e.g., 'sentence-transformers/all-MiniLM-L6-v2').")
        # Guard against heavy or invalid default from earlier revisions
        if model_name.strip().lower() in {"google/embeddinggemma-300m", "google/embeddinggemma"}:
            raise ValueError("'google/embeddinggemma-300m' is not a supported HuggingFace sentence embedding model. Use a sentence-transformers model instead (e.g., 'sentence-transformers/all-MiniLM-L6-v2').")

    def _sanitize_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Return a copy of config with secrets redacted for safe logging."""
        redacted = deepcopy(config)
        try:
            def _walk(node: Any):
                if isinstance(node, dict):
                    for k, v in list(node.items()):
                        if k.lower() in {"api_key", "apikey", "token", "bearer", "password"}:
                            node[k] = "***REDACTED***" if v else v
                        else:
                            _walk(v)
                elif isinstance(node, list):
                    for item in node:
                        _walk(item)
            _walk(redacted)
        except Exception:
            pass
        return redacted
    
    def add_message(self, conversation_id: str, message: BaseMessage, user_id: Optional[str] = None) -> None:
        """
        Add a message to the conversation and update Mem0 memories.
        
        Args:
            conversation_id: Unique conversation identifier
            message: LangChain message object
            user_id: Optional user identifier for user-scoped memories
        """
        # Add to recent messages buffer
        if conversation_id not in self.recent_messages:
            self.recent_messages[conversation_id] = []
        
        self.recent_messages[conversation_id].append(message)
        
        # Keep only recent messages in buffer
        if len(self.recent_messages[conversation_id]) > self.max_recent_messages:
            self.recent_messages[conversation_id].pop(0)
        
        # Extract content for Mem0 processing
        content = self._extract_message_content(message)
        
        if not content or not content.strip():
            return
        
        # Add to Mem0 with appropriate metadata
        metadata = {
            "conversation_id": conversation_id,
            "message_type": message.__class__.__name__,
            "timestamp": datetime.now().isoformat(),
        }
        
        # Add tool-specific metadata if it's a tool message
        if isinstance(message, ToolMessage):
            metadata["tool_call_id"] = getattr(message, "tool_call_id", "unknown")
        
        try:
            # Store in Mem0 with user_id as the memory scope
            mem0_user_id = user_id or conversation_id
            self.memory.add(
                content,
                user_id=mem0_user_id,
                metadata=metadata
            )
        except Exception as e:
            print(f"⚠️  Warning: Failed to add message to Mem0: {e}")
    
    def _extract_message_content(self, message: BaseMessage) -> str:
        """Extract meaningful content from a message for Mem0 storage."""
        if isinstance(message, (HumanMessage, AIMessage, SystemMessage)):
            return str(message.content)
        elif isinstance(message, ToolMessage):
            # For tool messages, include both the tool result and context
            return f"Tool result: {str(message.content)[:500]}"  # Limit tool output length
        else:
            return str(message.content) if hasattr(message, "content") else ""
    
    def get_conversation_history(self, conversation_id: str) -> List[BaseMessage]:
        """
        Get the full conversation history from recent messages buffer.
        
        Note: This returns the recent message buffer. For semantic memory retrieval,
        use get_relevant_memories() instead.
        
        Args:
            conversation_id: Unique conversation identifier
            
        Returns:
            List of recent BaseMessage objects
        """
        return self.recent_messages.get(conversation_id, [])
    
    def get_relevant_memories(
        self, 
        conversation_id: str, 
        query: str, 
        user_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant memories from Mem0 based on the current query.
        
        This uses semantic search to find the most relevant past context,
        which is much smarter than just returning recent messages.
        
        Args:
            conversation_id: Unique conversation identifier
            query: Current user query for semantic search
            user_id: Optional user identifier
            limit: Maximum number of memories to retrieve
            
        Returns:
            List of memory dictionaries with content and metadata
        """
        try:
            mem0_user_id = user_id or conversation_id
            memories = self.memory.search(
                query=query,
                user_id=mem0_user_id,
                limit=limit
            )
            return memories
        except Exception as e:
            print(f"⚠️  Warning: Failed to retrieve memories from Mem0: {e}")
            return []
    
    def get_recent_context(
        self, 
        conversation_id: str, 
        max_tokens: int = 3000,
        user_id: Optional[str] = None,
        include_semantic_memories: bool = True
    ) -> List[BaseMessage]:
        """
        Get recent conversation context with optional semantic memory integration.
        
        This method combines:
        1. Recent messages from the buffer (immediate context)
        2. Relevant memories from Mem0 (semantic context from past conversations)
        
        Args:
            conversation_id: Unique conversation identifier
            max_tokens: Approximate token budget for context
            user_id: Optional user identifier
            include_semantic_memories: Whether to include Mem0 semantic memories
            
        Returns:
            List of BaseMessage objects for context
        """
        messages = []
        
        # Get recent messages from buffer
        recent_messages = self.recent_messages.get(conversation_id, [])
        
        # If we have recent messages and semantic memories are enabled, get relevant context
        if include_semantic_memories and recent_messages:
            # Use the last user message as query for semantic search
            last_user_message = None
            for msg in reversed(recent_messages):
                if isinstance(msg, HumanMessage):
                    last_user_message = msg
                    break
            
            if last_user_message:
                # Retrieve relevant memories
                memories = self.get_relevant_memories(
                    conversation_id=conversation_id,
                    query=str(last_user_message.content),
                    user_id=user_id,
                    limit=5  # Get top 5 relevant memories
                )
                
                # Add memories as a system message if we found any
                if memories:
                    memory_context = self._format_memories_for_context(memories)
                    if memory_context:
                        messages.append(SystemMessage(content=memory_context))
        
        # Add recent messages (with token budget approximation)
        def approx_tokens(text: str) -> int:
            try:
                return max(1, len(text) // 4)
            except Exception:
                return len(text) // 4
        
        used_tokens = sum(approx_tokens(str(msg.content)) for msg in messages)
        
        # Add recent messages in reverse order until we hit token budget
        for msg in reversed(recent_messages):
            content = str(getattr(msg, "content", ""))
            msg_tokens = approx_tokens(content)
            
            if used_tokens + msg_tokens > max_tokens:
                break
            
            messages.insert(1 if messages else 0, msg)  # Insert after memory context if present
            used_tokens += msg_tokens
        
        return messages
    
    def _format_memories_for_context(self, memories: List[Dict[str, Any]]) -> str:
        """Format retrieved memories into a context string for the LLM."""
        if not memories:
            return ""
        
        context_parts = ["Relevant context from past conversations:"]
        
        for i, memory in enumerate(memories, 1):
            # Extract memory content and metadata
            memory_text = memory.get("memory", memory.get("text", ""))
            
            if memory_text:
                context_parts.append(f"{i}. {memory_text}")
        
        return "\n".join(context_parts)
    
    def clear_conversation(self, conversation_id: str) -> None:
        """
        Clear the recent message buffer for a conversation.
        
        Note: This only clears the recent buffer. Mem0 memories are persistent
        and remain in the database. To delete Mem0 memories, use delete_memories().
        
        Args:
            conversation_id: Unique conversation identifier
        """
        if conversation_id in self.recent_messages:
            self.recent_messages[conversation_id].clear()
    
    def delete_memories(
        self, 
        conversation_id: str, 
        user_id: Optional[str] = None
    ) -> None:
        """
        Delete all Mem0 memories for a conversation or user.
        
        Args:
            conversation_id: Unique conversation identifier
            user_id: Optional user identifier
        """
        try:
            mem0_user_id = user_id or conversation_id
            memories = self.memory.get_all(user_id=mem0_user_id)
            
            for memory in memories:
                memory_id = memory.get("id")
                if memory_id:
                    self.memory.delete(memory_id=memory_id)
            
            print(f"✅ Deleted all memories for {mem0_user_id}")
        except Exception as e:
            print(f"⚠️  Warning: Failed to delete memories: {e}")
    
    def get_all_memories(
        self, 
        conversation_id: str, 
        user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all stored memories for a conversation or user.
        
        Args:
            conversation_id: Unique conversation identifier
            user_id: Optional user identifier
            
        Returns:
            List of all memory dictionaries
        """
        try:
            mem0_user_id = user_id or conversation_id
            return self.memory.get_all(user_id=mem0_user_id)
        except Exception as e:
            print(f"⚠️  Warning: Failed to retrieve all memories: {e}")
            return []
    
    def update_memory(
        self, 
        memory_id: str, 
        content: str, 
        user_id: str
    ) -> None:
        """
        Update an existing memory in Mem0.
        
        Args:
            memory_id: Unique memory identifier
            content: New content for the memory
            user_id: User identifier
        """
        try:
            self.memory.update(
                memory_id=memory_id,
                data=content,
                user_id=user_id
            )
            print(f"✅ Updated memory {memory_id}")
        except Exception as e:
            print(f"⚠️  Warning: Failed to update memory: {e}")
    
    def register_turn(self, conversation_id: str) -> None:
        """
        Register a conversation turn (for compatibility with old ConversationMemory API).
        
        With Mem0, turn counting is less relevant since memories are automatically
        extracted and managed by the LLM.
        """
        pass  # No-op for Mem0 - it handles memory management automatically
    
    def should_update_summary(self, conversation_id: str, every_n_turns: int = 3) -> bool:
        """
        Check if summary should be updated (for compatibility with old API).
        
        With Mem0, this is handled automatically, so always return False.
        """
        return False  # Mem0 handles summarization automatically
    
    async def update_summary_async(self, conversation_id: str, llm_for_summary) -> None:
        """
        Update summary (for compatibility with old API).
        
        With Mem0, summarization is handled automatically during memory addition.
        """
        pass  # No-op for Mem0 - it handles summarization automatically


def create_mem0_manager(config: Optional[Dict[str, Any]] = None) -> Mem0Manager:
    """
    Factory function to create a Mem0Manager instance.
    
    Args:
        config: Optional configuration dict
        
    Returns:
        Initialized Mem0Manager instance
    """
    return Mem0Manager(config=config)

