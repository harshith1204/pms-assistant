"""
Mem0 Client Wrapper

Provides a unified interface to Mem0 for user memory management.
Handles initialization, memory operations, and search functionality.
"""

import logging
import os
from typing import Dict, Any, Optional, List
from mem0 import MemoryClient
from agent.knowledge_graph.config import initialize_mem0_client

logger = logging.getLogger(__name__)

# Global Mem0 client instance
_mem0_client: Optional[MemoryClient] = None


def get_mem0_client() -> MemoryClient:
    """Get or initialize Mem0 client singleton"""
    global _mem0_client
    
    if _mem0_client is None:
        try:
            # Initialize Mem0 client with configuration
            _mem0_client = initialize_mem0_client()
            logger.info("Mem0 client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Mem0 client: {e}")
            # Fallback to basic initialization
            try:
                api_key = os.getenv("MEM0_API_KEY")
                if api_key:
                    _mem0_client = MemoryClient(api_key=api_key)
                else:
                    # For open source Mem0, try with None or empty string
                    try:
                        _mem0_client = MemoryClient(api_key=None)
                    except (ValueError, TypeError):
                        try:
                            _mem0_client = MemoryClient(api_key="")
                        except Exception:
                            _mem0_client = MemoryClient()
                logger.info("Mem0 client initialized with fallback configuration")
            except Exception as fallback_error:
                logger.error(f"Fallback Mem0 initialization also failed: {fallback_error}")
                raise
    
    return _mem0_client


def get_user_id_for_mem0(user_id: str, business_id: Optional[str] = None) -> str:
    """Generate Mem0 user ID from user_id and business_id"""
    if business_id:
        return f"{user_id}:{business_id}"
    return user_id


class Mem0Wrapper:
    """Wrapper for Mem0 operations with user scoping"""
    
    def __init__(self):
        self.client = get_mem0_client()
    
    async def add_memory(
        self,
        user_id: str,
        business_id: Optional[str],
        messages: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Add memories to Mem0 for a user"""
        try:
            mem0_user_id = get_user_id_for_mem0(user_id, business_id)
            
            # Mem0 expects messages in format: [{"role": "user", "content": "..."}, ...]
            # Metadata can be passed separately or in messages
            formatted_messages = []
            for msg in messages:
                formatted_msg = {
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", str(msg))
                }
                # Add metadata to message if provided
                if metadata:
                    formatted_msg["metadata"] = metadata
                elif msg.get("metadata"):
                    formatted_msg["metadata"] = msg.get("metadata")
                formatted_messages.append(formatted_msg)
            
            # Mem0 add is synchronous, wrap in async
            import asyncio
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self.client.add(formatted_messages, user_id=mem0_user_id)
            )
            return result
            
        except Exception as e:
            logger.error(f"Failed to add memory to Mem0: {e}")
            raise
    
    async def search_memories(
        self,
        user_id: str,
        business_id: Optional[str],
        query: str,
        limit: int = 10,
        memory_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Search memories for a user"""
        try:
            mem0_user_id = get_user_id_for_mem0(user_id, business_id)
            
            # Mem0 search is synchronous, wrap in async
            import asyncio
            loop = asyncio.get_event_loop()
            
            # Build search parameters
            search_params = {
                "query": query,
                "user_id": mem0_user_id,
                "limit": limit
            }
            
            # Add memory type filter if specified (if Mem0 supports it)
            if memory_types:
                search_params["memory_types"] = memory_types
            
            results = await loop.run_in_executor(
                None,
                lambda: self.client.search(**search_params)
            )
            
            # Extract memories from results
            # Mem0 returns: {"results": [{"memory": "...", "metadata": {...}}, ...]}
            if isinstance(results, dict) and "results" in results:
                return results["results"]
            elif isinstance(results, list):
                return results
            else:
                return []
                
        except Exception as e:
            logger.error(f"Failed to search memories in Mem0: {e}")
            return []
    
    async def get_all_memories(
        self,
        user_id: str,
        business_id: Optional[str],
        memory_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Get all memories for a user"""
        try:
            mem0_user_id = get_user_id_for_mem0(user_id, business_id)
            
            # Mem0 get_all is synchronous, wrap in async
            import asyncio
            loop = asyncio.get_event_loop()
            
            # Use search with a broad query to get all memories
            # Or use get_all if available
            try:
                # Try get_all method if it exists
                if hasattr(self.client, "get_all"):
                    params = {"user_id": mem0_user_id}
                    if memory_types:
                        params["memory_types"] = memory_types
                    results = await loop.run_in_executor(
                        None,
                        lambda: self.client.get_all(**params)
                    )
                else:
                    # Fallback: use search with empty/broad query
                    results = await loop.run_in_executor(
                        None,
                        lambda: self.client.search(query="", user_id=mem0_user_id, limit=1000)
                    )
            except Exception:
                # Fallback: use search
                results = await loop.run_in_executor(
                    None,
                    lambda: self.client.search(query="", user_id=mem0_user_id, limit=1000)
                )
            
            # Extract memories from results
            if isinstance(results, dict) and "results" in results:
                memories = results["results"]
                # Filter by memory_types if specified
                if memory_types:
                    memories = [
                        m for m in memories
                        if m.get("metadata", {}).get("type") in memory_types
                        or m.get("memory_type") in memory_types
                    ]
                return memories
            elif isinstance(results, list):
                return results
            else:
                return []
                
        except Exception as e:
            logger.error(f"Failed to get all memories from Mem0: {e}")
            return []
    
    async def delete_memory(
        self,
        user_id: str,
        business_id: Optional[str],
        memory_id: str
    ) -> bool:
        """Delete a specific memory"""
        try:
            mem0_user_id = get_user_id_for_mem0(user_id, business_id)
            import asyncio
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.client.delete(memory_id, user_id=mem0_user_id)
            )
            return True
        except Exception as e:
            logger.error(f"Failed to delete memory from Mem0: {e}")
            return False
    
    async def update_memory(
        self,
        user_id: str,
        business_id: Optional[str],
        memory_id: str,
        messages: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Update an existing memory"""
        try:
            mem0_user_id = get_user_id_for_mem0(user_id, business_id)
            import asyncio
            loop = asyncio.get_event_loop()
            formatted_messages = [
                {"role": msg.get("role", "user"), "content": msg.get("content", str(msg))}
                for msg in messages
            ]
            result = await loop.run_in_executor(
                None,
                lambda: self.client.update(memory_id, formatted_messages, user_id=mem0_user_id)
            )
            return result
        except Exception as e:
            logger.error(f"Failed to update memory in Mem0: {e}")
            raise


# Global wrapper instance (lazy initialization)
_mem0_wrapper_instance: Optional[Mem0Wrapper] = None

def get_mem0_wrapper() -> Mem0Wrapper:
    """Get or create Mem0Wrapper instance (lazy initialization)."""
    global _mem0_wrapper_instance
    if _mem0_wrapper_instance is None:
        _mem0_wrapper_instance = Mem0Wrapper()
    return _mem0_wrapper_instance

# For backward compatibility
mem0_wrapper = property(lambda self: get_mem0_wrapper())

# Create a module-level property-like access
class _Mem0WrapperProxy:
    """Proxy to Mem0Wrapper for lazy initialization."""
    def __getattr__(self, name):
        return getattr(get_mem0_wrapper(), name)

mem0_wrapper = _Mem0WrapperProxy()

