#!/usr/bin/env python3
"""
Simple demonstration of the context management improvements.
This script shows the key optimizations without requiring external dependencies.
"""

import time
import json
import hashlib
import re
from collections import defaultdict, deque
from datetime import datetime
from typing import Dict, Any, List, Tuple

class MockMessage:
    """Mock message class for demonstration"""
    def __init__(self, content: str, msg_type: str = "human"):
        self.content = content
        self.msg_type = msg_type

class OriginalMemory:
    """Original simple memory implementation"""
    def __init__(self, max_messages: int = 50):
        self.conversations = defaultdict(lambda: deque(maxlen=max_messages))
    
    def add_message(self, conv_id: str, message: MockMessage):
        self.conversations[conv_id].append(message)
    
    def get_context(self, conv_id: str) -> List[MockMessage]:
        messages = list(self.conversations[conv_id])
        # Original naive approach: just return last 10 messages
        return messages[-10:] if len(messages) > 10 else messages

class OptimizedMemory:
    """Optimized memory with intelligent context management"""
    def __init__(self, max_context_tokens: int = 2800):
        self.conversations = defaultdict(lambda: deque(maxlen=100))
        self.max_context_tokens = max_context_tokens
        self.token_cache = {}
    
    def _estimate_tokens(self, text: str) -> int:
        """Fast token estimation with caching"""
        text_hash = hashlib.md5(text.encode()).hexdigest()
        if text_hash in self.token_cache:
            return self.token_cache[text_hash]
        
        # Simple estimation: ~4 chars per token
        tokens = len(text) // 4 + 1
        self.token_cache[text_hash] = tokens
        
        # Limit cache size
        if len(self.token_cache) > 1000:
            oldest_keys = list(self.token_cache.keys())[:200]
            for key in oldest_keys:
                del self.token_cache[key]
        
        return tokens
    
    def _calculate_importance(self, message: MockMessage) -> float:
        """Calculate message importance score"""
        content = message.content.lower()
        
        # Higher importance for certain types
        if message.msg_type == "tool_result":
            return 0.9
        elif message.msg_type == "ai_with_tools":
            return 0.85
        elif message.msg_type == "human":
            return 0.8
        elif any(keyword in content for keyword in ["error", "important", "critical"]):
            return 0.75
        
        return 0.6
    
    def _create_summary(self, messages: List[MockMessage]) -> str:
        """Create intelligent summary of messages"""
        if not messages:
            return ""
        
        summary_parts = []
        for msg in messages:
            content = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
            summary_parts.append(f"{msg.msg_type}: {content}")
        
        return f"[SUMMARY of {len(messages)} messages]: " + " | ".join(summary_parts)
    
    def add_message(self, conv_id: str, message: MockMessage):
        self.conversations[conv_id].append(message)
    
    def get_optimized_context(self, conv_id: str) -> List[MockMessage]:
        """Get intelligently optimized context"""
        messages = list(self.conversations[conv_id])
        if len(messages) <= 8:
            return messages
        
        # Always keep recent messages
        recent_count = min(6, len(messages))
        recent_messages = messages[-recent_count:]
        older_messages = messages[:-recent_count]
        
        # Calculate available space
        recent_tokens = sum(self._estimate_tokens(msg.content) for msg in recent_messages)
        available_tokens = self.max_context_tokens - recent_tokens - 300
        
        # Select important older messages
        context_messages = []
        if available_tokens > 500 and older_messages:
            scored_messages = []
            for i, msg in enumerate(older_messages):
                importance = self._calculate_importance(msg)
                recency_bonus = i / len(older_messages) * 0.2
                score = importance + recency_bonus
                scored_messages.append((msg, score))
            
            scored_messages.sort(key=lambda x: x[1], reverse=True)
            current_tokens = 0
            
            for msg, score in scored_messages:
                msg_tokens = self._estimate_tokens(msg.content)
                if current_tokens + msg_tokens <= available_tokens:
                    context_messages.append(msg)
                    current_tokens += msg_tokens
        
        # Create summary for remaining messages
        remaining = [msg for msg in older_messages if msg not in context_messages]
        if len(remaining) >= 4:
            summary_content = self._create_summary(remaining)
            if available_tokens > 200:
                summary_msg = MockMessage(summary_content, "system_summary")
                context_messages.insert(0, summary_msg)
        
        return context_messages + recent_messages

def chunk_content(content: str, max_size: int = 1000) -> List[str]:
    """Intelligent content chunking"""
    if len(content) <= max_size:
        return [content]
    
    chunks = []
    sentences = re.split(r'(?<=[.!?])\s+', content)
    current_chunk = ""
    
    for sentence in sentences:
        if len(current_chunk) + len(sentence) <= max_size:
            current_chunk += sentence + " "
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence + " "
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks

def demonstrate_improvements():
    """Demonstrate the key improvements"""
    print("🧠 Context Window Optimization Demo")
    print("=" * 50)
    
    # Create test data
    conversation_data = [
        ("What is MongoDB?", "human"),
        ("MongoDB is a NoSQL database that uses document storage with flexible schemas...", "ai"),
        ("How does sharding work?", "human"),
        ("Sharding in MongoDB distributes data across multiple servers for horizontal scaling...", "ai"),
        ("Can you explain indexing in detail?", "human"),
        ("Indexing in MongoDB improves query performance by creating data structures that allow fast lookups...", "ai"),
        ("What about replication and high availability?", "human"),
        ("MongoDB replication provides high availability through replica sets with automatic failover...", "ai"),
        ("How do MongoDB transactions work?", "human"),
        ("MongoDB supports ACID transactions across multiple documents and collections...", "ai_with_tools"),
        ("Error: Connection timeout occurred", "system"),
        ("Important: This is a critical operation", "human"),
        ("Tell me about the aggregation pipeline", "human"),
        ("The aggregation pipeline processes data through multiple stages for complex queries...", "ai"),
        ("What are the different storage engines?", "human"),
        ("MongoDB supports WiredTiger, MMAPv1, and encrypted storage engines...", "ai"),
        ("How does GridFS handle large files?", "human"),
        ("GridFS stores large files by dividing them into chunks and metadata collections...", "ai"),
    ]
    
    # Test original vs optimized memory
    original = OriginalMemory()
    optimized = OptimizedMemory(max_context_tokens=2000)
    
    conv_id = "test_conversation"
    
    # Add messages to both systems
    for content, msg_type in conversation_data:
        msg = MockMessage(content, msg_type)
        original.add_message(conv_id, msg)
        optimized.add_message(conv_id, msg)
    
    # Compare performance
    print(f"📊 Performance Comparison:")
    print(f"   Total messages added: {len(conversation_data)}")
    
    # Original system
    start_time = time.time()
    original_context = original.get_context(conv_id)
    original_time = time.time() - start_time
    
    # Optimized system
    start_time = time.time()
    optimized_context = optimized.get_optimized_context(conv_id)
    optimized_time = time.time() - start_time
    
    print(f"   Original context: {len(original_context)} messages (took {original_time:.6f}s)")
    print(f"   Optimized context: {len(optimized_context)} messages (took {optimized_time:.6f}s)")
    
    # Token comparison
    def count_tokens(messages):
        return sum(len(msg.content) // 4 for msg in messages)
    
    original_tokens = count_tokens(original_context)
    optimized_tokens = count_tokens(optimized_context)
    
    print(f"   Original tokens: ~{original_tokens}")
    print(f"   Optimized tokens: ~{optimized_tokens}")
    print(f"   Token reduction: {((original_tokens - optimized_tokens) / original_tokens * 100):.1f}%")
    
    # Show context quality
    print(f"\n🎯 Context Quality:")
    print(f"   Original approach: Takes last {len(original_context)} messages blindly")
    print(f"   Optimized approach: Intelligently selects {len(optimized_context)} messages")
    
    # Show what's included in optimized context
    message_types = {}
    for msg in optimized_context:
        message_types[msg.msg_type] = message_types.get(msg.msg_type, 0) + 1
    print(f"   Message type distribution: {message_types}")

def demonstrate_chunking():
    """Demonstrate chunked processing"""
    print(f"\n🔄 Chunked Processing Demo")
    print("=" * 50)
    
    # Create large content
    large_content = """
    Artificial intelligence and machine learning have revolutionized how we approach data processing and analysis. 
    These technologies enable systems to learn from data without explicit programming for every scenario.
    Machine learning algorithms can identify patterns in large datasets that would be impossible for humans to detect manually.
    Deep learning, a subset of machine learning, uses neural networks with multiple layers to process complex data.
    Natural language processing allows computers to understand and generate human language with increasing accuracy.
    Computer vision enables machines to interpret visual information from images and videos.
    The applications of AI span across industries including healthcare, finance, transportation, and entertainment.
    However, with these advances come challenges related to ethics, privacy, and the responsible development of AI systems.
    """ * 3
    
    print(f"📦 Content Chunking:")
    print(f"   Original content length: {len(large_content)} characters")
    
    start_time = time.time()
    chunks = chunk_content(large_content, max_size=400)
    chunking_time = time.time() - start_time
    
    print(f"   Number of chunks created: {len(chunks)}")
    print(f"   Average chunk size: {len(large_content) // len(chunks)} characters")
    print(f"   Chunking time: {chunking_time:.6f}s")
    
    print(f"\n   First 3 chunks preview:")
    for i, chunk in enumerate(chunks[:3]):
        print(f"   Chunk {i+1}: {chunk[:80]}...")

def main():
    """Run the demonstration"""
    print("🚀 Context Window & Performance Optimization Demo")
    print("=" * 60)
    print("Demonstrating improvements to prevent context overflow and enhance performance")
    print()
    
    demonstrate_improvements()
    demonstrate_chunking()
    
    print(f"\n" + "=" * 60)
    print("🎉 Key Improvements Summary:")
    print("✅ Intelligent context selection (not just recent messages)")
    print("✅ Token-aware management with caching for performance")
    print("✅ Message importance scoring for better context quality")
    print("✅ Automatic summarization of older context")
    print("✅ Smart chunking for large content processing")
    print("✅ Memory optimization to prevent system slowdown")
    print("\n💡 These optimizations solve the context window overflow problem")
    print("   while maintaining fast response times and system performance!")

if __name__ == "__main__":
    main()