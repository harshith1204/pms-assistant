"""
Vector Memory System for Long-term Context

Stores and retrieves conversation summaries and context using Qdrant vector database.
Enables semantic search over past conversations to provide relevant context.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json


@dataclass
class ConversationSummary:
    """Represents a stored conversation summary"""
    conversation_id: str
    user_id: Optional[str]
    summary: str
    key_entities: List[str]  # People, projects, topics mentioned
    timestamp: datetime
    message_count: int
    importance_score: float  # 0-1, based on user engagement, length, etc.


class VectorMemorySystem:
    """Manages long-term memory using Qdrant vector database"""
    
    def __init__(self, qdrant_client, embedding_model, collection_name: str = "conversation_memory"):
        """
        Initialize the vector memory system.
        
        Args:
            qdrant_client: Qdrant client instance
            embedding_model: Embedding model for text encoding
            collection_name: Name of the Qdrant collection for conversation memory
        """
        self.qdrant_client = qdrant_client
        self.embedding_model = embedding_model
        self.collection_name = collection_name
        self._ensure_collection()
    
    def _ensure_collection(self):
        """Ensure the conversation memory collection exists in Qdrant"""
        from qdrant_client.models import Distance, VectorParams
        
        try:
            # Check if collection exists
            collections = [col.name for col in self.qdrant_client.get_collections().collections]
            
            if self.collection_name not in collections:
                # Create collection with 768-dimensional vectors (sentence-transformers default)
                self.qdrant_client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config={
                        "summary": VectorParams(size=768, distance=Distance.COSINE)
                    }
                )
                print(f"✅ Created Qdrant collection: {self.collection_name}")
        except Exception as e:
            print(f"⚠️ Error ensuring collection: {e}")
    
    async def store_conversation_summary(
        self,
        conversation_id: str,
        summary: str,
        key_entities: Optional[List[str]] = None,
        user_id: Optional[str] = None,
        message_count: int = 0,
        importance_score: float = 0.5
    ) -> bool:
        """
        Store a conversation summary in the vector database.
        
        Args:
            conversation_id: Unique conversation identifier
            summary: Text summary of the conversation
            key_entities: List of important entities (people, projects, topics)
            user_id: Optional user identifier for multi-tenant scenarios
            message_count: Number of messages in the conversation
            importance_score: Importance score (0-1) based on engagement, length, etc.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            from qdrant_client.models import PointStruct
            
            # Generate embedding for the summary
            embedding = self.embedding_model.encode(summary).tolist()
            
            # Create a unique ID for this summary (hash of conversation_id + timestamp)
            point_id = hashlib.md5(
                f"{conversation_id}_{datetime.now().isoformat()}".encode()
            ).hexdigest()
            
            # Prepare payload with metadata
            payload = {
                "conversation_id": conversation_id,
                "summary": summary,
                "key_entities": key_entities or [],
                "user_id": user_id or "default",
                "timestamp": datetime.now().isoformat(),
                "message_count": message_count,
                "importance_score": importance_score,
                "type": "conversation_summary"
            }
            
            # Store in Qdrant
            self.qdrant_client.upsert(
                collection_name=self.collection_name,
                points=[
                    PointStruct(
                        id=point_id,
                        vector={"summary": embedding},
                        payload=payload
                    )
                ]
            )
            
            print(f"✅ Stored conversation summary: {conversation_id[:20]}...")
            return True
            
        except Exception as e:
            print(f"❌ Error storing conversation summary: {e}")
            return False
    
    async def search_similar_conversations(
        self,
        query: str,
        user_id: Optional[str] = None,
        limit: int = 5,
        min_score: float = 0.5,
        exclude_conversation_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar past conversations using semantic search.
        
        Args:
            query: Search query (current message or conversation context)
            user_id: Optional user ID to filter results
            limit: Maximum number of results to return
            min_score: Minimum similarity score (0-1)
            exclude_conversation_id: Optional conversation ID to exclude from results
        
        Returns:
            List of similar conversation summaries with metadata
        """
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            
            # Generate embedding for the query
            query_embedding = self.embedding_model.encode(query).tolist()
            
            # Build filter
            filter_conditions = []
            if user_id:
                filter_conditions.append(
                    FieldCondition(key="user_id", match=MatchValue(value=user_id))
                )
            if exclude_conversation_id:
                # Note: Qdrant doesn't have NOT EQUAL, so we'll filter in post-processing
                pass
            
            search_filter = Filter(must=filter_conditions) if filter_conditions else None
            
            # Search in Qdrant
            results = self.qdrant_client.search(
                collection_name=self.collection_name,
                query_vector=("summary", query_embedding),
                query_filter=search_filter,
                limit=limit + (1 if exclude_conversation_id else 0),  # Get extra to account for exclusion
                score_threshold=min_score,
                with_payload=True
            )
            
            # Format results
            similar_conversations = []
            for result in results:
                payload = result.payload or {}
                
                # Skip excluded conversation
                if exclude_conversation_id and payload.get("conversation_id") == exclude_conversation_id:
                    continue
                
                similar_conversations.append({
                    "conversation_id": payload.get("conversation_id"),
                    "summary": payload.get("summary"),
                    "key_entities": payload.get("key_entities", []),
                    "timestamp": payload.get("timestamp"),
                    "message_count": payload.get("message_count", 0),
                    "importance_score": payload.get("importance_score", 0.5),
                    "similarity_score": result.score
                })
                
                # Stop once we have enough results (excluding the current conversation)
                if len(similar_conversations) >= limit:
                    break
            
            return similar_conversations
            
        except Exception as e:
            print(f"❌ Error searching similar conversations: {e}")
            return []
    
    async def get_relevant_context(
        self,
        query: str,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        max_results: int = 3
    ) -> str:
        """
        Get relevant context from past conversations formatted for the LLM.
        
        Args:
            query: Current query or conversation context
            conversation_id: Current conversation ID (to exclude from results)
            user_id: User ID for filtering
            max_results: Maximum number of past conversations to include
        
        Returns:
            Formatted context string to inject into the system prompt
        """
        similar = await self.search_similar_conversations(
            query=query,
            user_id=user_id,
            limit=max_results,
            min_score=0.6,  # Higher threshold for context injection
            exclude_conversation_id=conversation_id
        )
        
        if not similar:
            return ""
        
        # Format context
        context_parts = ["RELEVANT PAST CONTEXT (from similar conversations):"]
        
        for i, conv in enumerate(similar, 1):
            timestamp = conv.get("timestamp", "")
            summary = conv.get("summary", "")
            entities = conv.get("key_entities", [])
            
            context_parts.append(f"\n{i}. Past conversation (similarity: {conv['similarity_score']:.2f}):")
            context_parts.append(f"   Summary: {summary}")
            if entities:
                context_parts.append(f"   Key topics: {', '.join(entities)}")
        
        context_parts.append("")  # Empty line separator
        
        return "\n".join(context_parts)
    
    async def extract_key_entities(self, conversation_text: str) -> List[str]:
        """
        Extract key entities from conversation text.
        
        This is a simple implementation - could be enhanced with NER models.
        
        Args:
            conversation_text: Full conversation text
        
        Returns:
            List of key entities (capitalized words, common project terms, etc.)
        """
        import re
        
        # Simple heuristic: extract capitalized words and common project terms
        words = conversation_text.split()
        
        entities = set()
        
        # Find capitalized words (potential proper nouns)
        for word in words:
            # Remove punctuation
            clean_word = re.sub(r'[^\w\s]', '', word)
            if clean_word and clean_word[0].isupper() and len(clean_word) > 2:
                entities.add(clean_word)
        
        # Limit to top 10 entities
        return list(entities)[:10]
    
    async def calculate_importance_score(
        self,
        message_count: int,
        has_user_feedback: bool = False,
        conversation_length_chars: int = 0
    ) -> float:
        """
        Calculate importance score for a conversation.
        
        Args:
            message_count: Number of messages in conversation
            has_user_feedback: Whether user provided feedback (likes/dislikes)
            conversation_length_chars: Total character count
        
        Returns:
            Importance score between 0 and 1
        """
        score = 0.3  # Base score
        
        # More messages = more important
        if message_count > 10:
            score += 0.3
        elif message_count > 5:
            score += 0.2
        elif message_count > 2:
            score += 0.1
        
        # User feedback indicates importance
        if has_user_feedback:
            score += 0.2
        
        # Longer conversations are more important
        if conversation_length_chars > 2000:
            score += 0.2
        elif conversation_length_chars > 1000:
            score += 0.1
        
        return min(score, 1.0)  # Cap at 1.0


# Global instance (initialized in agent.py)
_vector_memory_instance: Optional[VectorMemorySystem] = None


def get_vector_memory(qdrant_client=None, embedding_model=None) -> Optional[VectorMemorySystem]:
    """Get or create the global vector memory instance"""
    global _vector_memory_instance
    
    if _vector_memory_instance is None and qdrant_client and embedding_model:
        _vector_memory_instance = VectorMemorySystem(qdrant_client, embedding_model)
    
    return _vector_memory_instance
