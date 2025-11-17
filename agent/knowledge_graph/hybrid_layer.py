"""
Mem0 Hybrid Context Layer

Automatically injects user persona and relevant context into agent messages.
This is a hybrid layer that combines:
- User persona from Mem0 memories
- Relevant context via semantic search
- Preferences and traits
- Broader awareness context
- User name and personalized response instructions

All context is injected automatically as SystemMessages - agent doesn't need to call Mem0.
"""

import logging
from typing import List, Dict, Any, Optional
from langchain_core.messages import SystemMessage
from agent.knowledge_graph.client import mem0_wrapper, get_user_id_for_mem0
from cachetools import TTLCache

logger = logging.getLogger(__name__)

# Cache for user names (TTL: 1 hour)
_user_name_cache: TTLCache = TTLCache(maxsize=1000, ttl=3600)


async def get_user_name(user_id: str, business_id: Optional[str] = None) -> Optional[str]:
    """Get user name from MongoDB members collection (with caching)."""
    # Check cache first
    cache_key = f"{user_id}:{business_id or ''}"
    cached_name = _user_name_cache.get(cache_key)
    if cached_name is not None:
        return cached_name
    
    try:
        from mongo.client import direct_mongo_client
        from mongo.constants import DATABASE_NAME, uuid_str_to_mongo_binary
        
        await direct_mongo_client.connect()
        db = direct_mongo_client.client[DATABASE_NAME]
        members_col = db["members"]
        
        # Convert UUID to binary
        member_bin = uuid_str_to_mongo_binary(user_id)
        
        # Query members collection
        # Try memberId first (staff identifier)
        member_doc = await members_col.find_one({
            "$or": [
                {"memberId": member_bin},
                {"staff._id": member_bin}
            ]
        })
        
        if member_doc:
            # Try different name fields
            name = (
                member_doc.get("name") or
                member_doc.get("displayName") or
                (member_doc.get("staff", {}) or {}).get("name") or
                (member_doc.get("staff", {}) or {}).get("displayName")
            )
            if name:
                # Cache the result
                _user_name_cache[cache_key] = name
                return name
        
        # Cache None to avoid repeated lookups for non-existent users
        _user_name_cache[cache_key] = None
        return None
    except Exception as e:
        logger.debug(f"Failed to get user name: {e}")
        return None


class Mem0HybridLayer:
    """Hybrid context layer that automatically injects user context"""
    
    def __init__(self):
        self.mem0 = mem0_wrapper
    
    async def build_user_persona(
        self,
        user_id: str,
        business_id: Optional[str] = None
    ) -> Optional[SystemMessage]:
        """Build user persona from Mem0 memories and inject as SystemMessage"""
        try:
            # Get all user memories
            all_memories = await self.mem0.get_all_memories(
                user_id=user_id,
                business_id=business_id
            )
            
            if not all_memories:
                return None
            
            # Extract persona components
            persona_parts = []
            
            # Extract preferences
            preferences = []
            traits = []
            context_items = []
            
            for memory in all_memories:
                # Mem0 returns memories in format: {"memory": "...", "metadata": {...}}
                memory_text = memory.get("memory", memory.get("content", ""))
                metadata = memory.get("metadata", {})
                memory_type = metadata.get("type", memory.get("memory_type", ""))
                
                if memory_type == "user_preference" or "preference" in memory_text.lower():
                    preferences.append(memory_text)
                elif memory_type == "user_trait" or "trait" in memory_text.lower():
                    traits.append(memory_text)
                elif memory_type == "user_context":
                    context_items.append(memory_text)
            
            # Build persona string
            if preferences:
                pref_text = ", ".join(preferences[:5])  # Limit to 5
                persona_parts.append(f"Preferences: {pref_text}")
            
            if traits:
                trait_text = ", ".join(traits[:5])  # Limit to 5
                persona_parts.append(f"Traits: {trait_text}")
            
            if persona_parts:
                persona = "User Persona:\n" + "\n".join(f"- {part}" for part in persona_parts)
                return SystemMessage(content=persona)
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to build user persona from Mem0: {e}")
            return None
    
    async def get_relevant_context(
        self,
        user_id: str,
        business_id: Optional[str],
        query: str,
        max_contexts: int = 3
    ) -> List[str]:
        """Get relevant context from Mem0 based on query semantics"""
        try:
            # Search Mem0 for relevant memories
            memories = await self.mem0.search_memories(
                user_id=user_id,
                business_id=business_id,
                query=query,
                limit=max_contexts * 2  # Get more to filter
            )
            
            if not memories:
                return []
            
            # Extract relevant context strings
            contexts = []
            seen_content = set()
            
            for memory in memories[:max_contexts]:
                # Mem0 returns memories in format: {"memory": "...", "metadata": {...}}
                content = memory.get("memory", memory.get("content", ""))
                if content and content not in seen_content:
                    contexts.append(content)
                    seen_content.add(content)
            
            return contexts
            
        except Exception as e:
            logger.error(f"Failed to get relevant context from Mem0: {e}")
            return []
    
    async def build_context_layer(
        self,
        user_id: str,
        business_id: Optional[str],
        query: str,
        include_long_term: bool = True,
        user_preferences: Optional[Dict[str, Any]] = None
    ) -> Optional[SystemMessage]:
        """Build complete context layer message to inject into agent"""
        try:
            context_parts = []
            
            # 0. Get user name for personalization
            user_name = await get_user_name(user_id, business_id)
            
            # 1. Get user persona
            persona = await self.build_user_persona(user_id, business_id)
            if persona:
                context_parts.append(persona.content)
            
            # 2. Build personalized response instructions based on preferences
            response_instructions = []
            
            if user_preferences:
                response_tone = user_preferences.get("responseTone", "professional")
                domain_focus = user_preferences.get("domainFocus")
                
                # Add response tone guidance
                tone_guidance = {
                    "professional": "Use a professional, formal tone. Be precise and structured.",
                    "friendly": "Use a friendly, warm tone. Be conversational and approachable.",
                    "concise": "Be brief and to the point. Avoid unnecessary details.",
                    "detailed": "Provide comprehensive explanations with context and examples."
                }
                if response_tone in tone_guidance:
                    response_instructions.append(tone_guidance[response_tone])
                
                # Add domain focus guidance
                if domain_focus:
                    domain_guidance = {
                        "product": "Focus on product management, user experience, and feature planning.",
                        "engineering": "Focus on technical implementation, architecture, and code quality.",
                        "design": "Focus on user experience, design systems, and visual design.",
                        "marketing": "Focus on user acquisition, messaging, and go-to-market strategies.",
                        "general": "Provide balanced perspectives across all domains."
                    }
                    if domain_focus in domain_guidance:
                        response_instructions.append(domain_guidance[domain_focus])
            
            # 3. Build personalized greeting/address if name is available
            if user_name:
                greeting_instruction = (
                    f"Greet the user by name ('{user_name}') when starting a new conversation or when appropriate. "
                    f"Address them as '{user_name}' naturally throughout the conversation. "
                    f"Use their name to create a personalized, friendly experience."
                )
                response_instructions.insert(0, greeting_instruction)
            
            # Add response instructions to context
            if response_instructions:
                context_parts.append("Response Style Guidelines:")
                for instruction in response_instructions:
                    context_parts.append(f"  - {instruction}")
            
            # 4. Get relevant long-term context from knowledge graph if enabled
            relevant_contexts = []
            if include_long_term:
                relevant_contexts = await self.get_relevant_context(
                    user_id=user_id,
                    business_id=business_id,
                    query=query,
                    max_contexts=3  # Increased to get more context
                )
                
                if relevant_contexts:
                    context_parts.append("Relevant Context from Knowledge Graph:")
                    for i, ctx in enumerate(relevant_contexts, 1):
                        # Truncate if too long but keep more context
                        ctx_text = ctx[:400] + "..." if len(ctx) > 400 else ctx
                        context_parts.append(f"  {i}. {ctx_text}")
            
            # 5. Get broader awareness context (entities user knows about)
            awareness_memories = []
            if include_long_term:
                awareness_memories = await self.mem0.get_all_memories(
                    user_id=user_id,
                    business_id=business_id,
                    memory_types=["awareness_entity"]
                )
                
                if awareness_memories:
                    aware_items = []
                    for memory in awareness_memories[:5]:  # Increased to 5
                        # Mem0 returns memories in format: {"memory": "...", "metadata": {...}}
                        content = memory.get("memory", memory.get("content", ""))
                        if content:
                            # Keep more context for awareness entities
                            aware_items.append(content[:100])
                    
                    if aware_items:
                        context_parts.append(f"Broader Awareness Context (entities user knows about): {', '.join(aware_items)}")
            
            # 6. Add summary of available context types
            context_summary = []
            if user_name:
                context_summary.append(f"User name: {user_name}")
            if persona:
                context_summary.append("User persona and traits")
            if relevant_contexts:
                context_summary.append(f"{len(relevant_contexts)} relevant context items from knowledge graph")
            if awareness_memories:
                context_summary.append(f"{len(awareness_memories)} awareness entities")
            if user_preferences:
                context_summary.append("User preferences and response style")
            
            if context_summary:
                context_parts.insert(0, f"Available Context: {', '.join(context_summary)}")
            
            # Build context layer message with comprehensive instructions
            if context_parts:
                context_text = "Personalization Context:\n" + "\n".join(f"- {part}" for part in context_parts)
                
                # Add explicit instruction to use all available context
                usage_instruction = (
                    "\n\nIMPORTANT: Use all the above context to personalize your responses:\n"
                    "- Reference the user's name, preferences, and traits naturally\n"
                    "- Incorporate relevant context from their knowledge graph when answering questions\n"
                    "- Use awareness entities to provide broader context when relevant\n"
                    "- Match the user's preferred response tone and domain focus\n"
                    "- Make responses feel personalized and contextually aware"
                )
                context_text += usage_instruction
                
                return SystemMessage(content=context_text)
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to build context layer from Mem0: {e}")
            return None


# Global instance
mem0_hybrid_layer = Mem0HybridLayer()

