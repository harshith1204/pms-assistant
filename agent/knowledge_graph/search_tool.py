"""
Mem0 Search Tool for Agent

Allows the agent to query Mem0 memories dynamically during conversations.
Replaces the KG query tool with Mem0-based search.
"""

import logging
from typing import Dict, Any, Optional, List
from langchain_core.tools import tool
from agent.knowledge_graph.client import mem0_wrapper

logger = logging.getLogger(__name__)


@tool
async def mem0_search(
    query: str,
    user_id: Optional[str] = None,
    business_id: Optional[str] = None,
    memory_types: Optional[str] = None,
    limit: int = 10
) -> str:
    """Search Mem0 memories for user context, preferences, traits, and patterns.
    
    Use this tool when you need to:
    - Understand user preferences or traits
    - Find relevant context from past interactions
    - Access user-specific information stored in memory
    - Query awareness entities or patterns
    
    Args:
        query: Search query (semantic meaning, not just keywords)
        user_id: User ID to search memories for (required)
        business_id: Business ID for scoping (optional)
        memory_types: Comma-separated list of memory types to filter by
                     (e.g., "user_preference,user_trait,user_context")
        limit: Maximum number of results to return (default: 10)
    
    Returns:
        Formatted string with search results
    
    Examples:
        - "What are this user's preferences?" → query="user preferences", user_id=...
        - "What traits does this user have?" → query="user traits", user_id=...
        - "What context is relevant to authentication?" → query="authentication", user_id=...
    """
    try:
        if not user_id:
            return "❌ user_id is required for Mem0 search"
        
        # Parse memory types if provided
        memory_types_list = None
        if memory_types:
            memory_types_list = [mt.strip() for mt in memory_types.split(",")]
        
        # Search Mem0 memories
        memories = await mem0_wrapper.search_memories(
            user_id=user_id,
            business_id=business_id,
            query=query,
            limit=limit,
            memory_types=memory_types_list
        )
        
        if not memories:
            return f"❌ No memories found for query: '{query}'"
        
        # Format results
        result_parts = []
        result_parts.append(f"Found {len(memories)} memory(ies) for query '{query}':\n")
        
        for i, memory in enumerate(memories, 1):
            # Mem0 returns memories in format: {"memory": "...", "metadata": {...}}
            content = memory.get("memory", memory.get("content", ""))
            metadata = memory.get("metadata", {})
            memory_type = metadata.get("type", memory.get("memory_type", ""))
            
            result_parts.append(f"{i}. [{memory_type}] {content}")
            
            # Add metadata if available
            if metadata:
                meta_parts = []
                for key, value in metadata.items():
                    if key not in ["type", "source"]:  # Skip common metadata
                        meta_parts.append(f"{key}: {value}")
                if meta_parts:
                    result_parts.append(f"   Metadata: {', '.join(meta_parts)}")
        
        return "\n".join(result_parts)
        
    except Exception as e:
        logger.error(f"Failed to search Mem0 memories: {e}")
        return f"❌ Error searching Mem0 memories: {str(e)}"


@tool
async def mem0_get_preferences(
    user_id: str,
    business_id: Optional[str] = None
) -> str:
    """Get user preferences from Mem0 memories.
    
    Args:
        user_id: User ID
        business_id: Business ID (optional)
    
    Returns:
        Formatted string with user preferences
    """
    try:
        memories = await mem0_wrapper.get_all_memories(
            user_id=user_id,
            business_id=business_id,
            memory_types=["user_preference"]
        )
        
        if not memories:
            return "No preferences found for this user."
        
        pref_parts = []
        for memory in memories:
            # Mem0 returns memories in format: {"memory": "...", "metadata": {...}}
            content = memory.get("memory", memory.get("content", ""))
            metadata = memory.get("metadata", {})
            pref_type = metadata.get("preference_type") or metadata.get("type", "")
            pref_value = metadata.get("value", "")
            
            if pref_type and pref_value:
                pref_parts.append(f"- {pref_type}: {pref_value}")
            elif content:
                pref_parts.append(f"- {content}")
        
        return "User Preferences:\n" + "\n".join(pref_parts) if pref_parts else "No preferences found."
        
    except Exception as e:
        logger.error(f"Failed to get preferences from Mem0: {e}")
        return f"❌ Error getting preferences: {str(e)}"


@tool
async def mem0_get_traits(
    user_id: str,
    business_id: Optional[str] = None
) -> str:
    """Get user traits from Mem0 memories.
    
    Args:
        user_id: User ID
        business_id: Business ID (optional)
    
    Returns:
        Formatted string with user traits
    """
    try:
        memories = await mem0_wrapper.get_all_memories(
            user_id=user_id,
            business_id=business_id,
            memory_types=["user_trait"]
        )
        
        if not memories:
            return "No traits found for this user."
        
        trait_parts = []
        for memory in memories:
            # Mem0 returns memories in format: {"memory": "...", "metadata": {...}}
            content = memory.get("memory", memory.get("content", ""))
            if content:
                trait_parts.append(f"- {content}")
        
        return "User Traits:\n" + "\n".join(trait_parts) if trait_parts else "No traits found."
        
    except Exception as e:
        logger.error(f"Failed to get traits from Mem0: {e}")
        return f"❌ Error getting traits: {str(e)}"

