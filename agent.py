from langchain_ollama import ChatOllama

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, BaseMessage, SystemMessage
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_mcp_adapters.client import MultiServerMCPClient
import json
import asyncio
from typing import Dict, Any, List, AsyncGenerator, Optional, Tuple
from pydantic import BaseModel
import tools
from datetime import datetime
import time
from collections import defaultdict, deque
import re
import hashlib

tools_list = tools.tools
from constants import DATABASE_NAME, mongodb_tools

class MessageSummary:
    """Represents a summary of multiple messages"""
    def __init__(self, original_count: int, summary_content: str, timestamp: datetime, importance_score: float = 0.5):
        self.original_count = original_count
        self.summary_content = summary_content
        self.timestamp = timestamp
        self.importance_score = importance_score

class SmartConversationMemory:
    """Advanced conversation memory with intelligent context management"""

    def __init__(self, max_context_tokens: int = 2800, max_messages_per_conversation: int = 100):
        self.conversations: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_messages_per_conversation))
        self.summaries: Dict[str, List[MessageSummary]] = defaultdict(list)
        self.max_context_tokens = max_context_tokens
        self.max_messages_per_conversation = max_messages_per_conversation
        
        # Performance tracking
        self.token_estimation_cache = {}
        self.context_access_times = defaultdict(list)
        
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text (cached for performance)"""
        text_hash = hashlib.md5(text.encode()).hexdigest()
        if text_hash in self.token_estimation_cache:
            return self.token_estimation_cache[text_hash]
        
        # Simple token estimation: ~4 chars per token for most models
        # This is much faster than actual tokenization
        estimated_tokens = len(text) // 4 + 1
        self.token_estimation_cache[text_hash] = estimated_tokens
        
        # Limit cache size to prevent memory bloat
        if len(self.token_estimation_cache) > 1000:
            # Remove oldest entries (simple FIFO)
            oldest_keys = list(self.token_estimation_cache.keys())[:200]
            for key in oldest_keys:
                del self.token_estimation_cache[key]
                
        return estimated_tokens
    
    def _calculate_message_importance(self, message: BaseMessage) -> float:
        """Calculate importance score for a message (0.0 to 1.0)"""
        if isinstance(message, ToolMessage):
            return 0.9  # Tool results are usually important
        elif isinstance(message, AIMessage) and message.tool_calls:
            return 0.85  # AI messages with tool calls are important
        elif isinstance(message, HumanMessage):
            return 0.8  # User messages are important
        elif isinstance(message, AIMessage):
            # Check for error patterns or key information
            content = message.content.lower() if message.content else ""
            if any(keyword in content for keyword in ["error", "failed", "exception", "important"]):
                return 0.75
            return 0.6
        return 0.5
    
    def _create_summary(self, messages: List[BaseMessage]) -> MessageSummary:
        """Create a summary of multiple messages"""
        if not messages:
            return None
            
        # Extract key information for summary
        summary_parts = []
        total_importance = 0
        
        for message in messages:
            importance = self._calculate_message_importance(message)
            total_importance += importance
            
            if isinstance(message, HumanMessage):
                # Truncate long user messages but keep key points
                content = message.content[:200] + "..." if len(message.content) > 200 else message.content
                summary_parts.append(f"User: {content}")
            elif isinstance(message, AIMessage):
                if message.tool_calls:
                    tools_used = [tc.get("name", "unknown") for tc in message.tool_calls]
                    summary_parts.append(f"AI used tools: {', '.join(tools_used)}")
                else:
                    content = message.content[:150] + "..." if len(message.content) > 150 else message.content
                    summary_parts.append(f"AI: {content}")
            elif isinstance(message, ToolMessage):
                # Keep tool results concise
                content = str(message.content)[:100] + "..." if len(str(message.content)) > 100 else str(message.content)
                summary_parts.append(f"Tool result: {content}")
        
        summary_content = " | ".join(summary_parts)
        avg_importance = total_importance / len(messages) if messages else 0.5
        
        return MessageSummary(
            original_count=len(messages),
            summary_content=summary_content,
            timestamp=datetime.now(),
            importance_score=avg_importance
        )
    
    def add_message(self, conversation_id: str, message: BaseMessage):
        """Add a message to the conversation history"""
        self.conversations[conversation_id].append(message)
        
        # Track context access for performance monitoring
        self.context_access_times[conversation_id].append(time.time())
        if len(self.context_access_times[conversation_id]) > 50:
            self.context_access_times[conversation_id] = self.context_access_times[conversation_id][-25:]
    
    def _should_compress_context(self, conversation_id: str) -> bool:
        """Determine if context compression is needed based on usage patterns"""
        messages = list(self.conversations[conversation_id])
        if len(messages) < 15:  # Don't compress small conversations
            return False
            
        # Check if we're approaching token limits
        total_tokens = sum(self._estimate_tokens(self._get_message_content(msg)) for msg in messages)
        return total_tokens > self.max_context_tokens * 0.7  # Compress at 70% of limit
    
    def _get_message_content(self, message: BaseMessage) -> str:
        """Extract content from any message type"""
        if hasattr(message, 'content') and message.content:
            return str(message.content)
        elif isinstance(message, ToolMessage):
            return f"Tool result: {str(message.content)[:200]}"
        elif isinstance(message, AIMessage) and message.tool_calls:
            return f"AI made tool calls: {len(message.tool_calls)} calls"
        return "[Empty message]"
    
    def get_optimized_context(self, conversation_id: str, max_tokens: int = None) -> List[BaseMessage]:
        """Get intelligently managed conversation context"""
        if max_tokens is None:
            max_tokens = self.max_context_tokens
            
        messages = list(self.conversations[conversation_id])
        if not messages:
            return []
        
        # If conversation is small, return as-is
        if len(messages) <= 8:
            return messages
        
        # Always keep the most recent messages
        recent_count = min(6, len(messages))
        recent_messages = messages[-recent_count:]
        older_messages = messages[:-recent_count]
        
        # Calculate tokens for recent messages
        recent_tokens = sum(self._estimate_tokens(self._get_message_content(msg)) for msg in recent_messages)
        
        # Available tokens for older context
        available_tokens = max_tokens - recent_tokens - 300  # Reserve 300 tokens for safety
        
        # If we have space, include some older messages directly
        context_messages = []
        if available_tokens > 500 and older_messages:
            # Sort older messages by importance and recency
            scored_messages = []
            for i, msg in enumerate(older_messages):
                importance = self._calculate_message_importance(msg)
                recency_bonus = i / len(older_messages) * 0.2  # More recent = higher score
                score = importance + recency_bonus
                scored_messages.append((msg, score))
            
            # Select high-importance messages that fit in available tokens
            scored_messages.sort(key=lambda x: x[1], reverse=True)
            current_tokens = 0
            
            for msg, score in scored_messages:
                msg_tokens = self._estimate_tokens(self._get_message_content(msg))
                if current_tokens + msg_tokens <= available_tokens:
                    context_messages.append(msg)
                    current_tokens += msg_tokens
                else:
                    break
        
        # If we still have many unused older messages, create a summary
        remaining_messages = [msg for msg in older_messages if msg not in context_messages]
        if len(remaining_messages) >= 4:  # Only summarize if we have enough messages
            summary = self._create_summary(remaining_messages)
            if summary and available_tokens > 200:  # Only add summary if we have space
                summary_message = SystemMessage(
                    content=f"[SUMMARY of {summary.original_count} previous messages]: {summary.summary_content}"
                )
                context_messages.insert(0, summary_message)
        
        # Combine context: summaries/selected older messages + recent messages
        # Sort context messages by their original position (if we can determine it)
        final_context = context_messages + recent_messages
        return final_context
    
    def get_conversation_history(self, conversation_id: str) -> List[BaseMessage]:
        """Get the full conversation history for a given conversation ID"""
        return list(self.conversations[conversation_id])
    
    def clear_conversation(self, conversation_id: str):
        """Clear the conversation history for a given conversation ID"""
        if conversation_id in self.conversations:
            self.conversations[conversation_id].clear()
        if conversation_id in self.summaries:
            self.summaries[conversation_id].clear()
        if conversation_id in self.context_access_times:
            del self.context_access_times[conversation_id]
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory and performance statistics"""
        total_conversations = len(self.conversations)
        total_messages = sum(len(conv) for conv in self.conversations.values())
        cache_size = len(self.token_estimation_cache)
        
        return {
            "total_conversations": total_conversations,
            "total_messages": total_messages,
            "cache_size": cache_size,
            "max_context_tokens": self.max_context_tokens
        }

    # Backward compatibility alias
    def get_recent_context(self, conversation_id: str, max_tokens: int = 3000) -> List[BaseMessage]:
        """Backward compatibility method"""
        return self.get_optimized_context(conversation_id, max_tokens)

# Global conversation memory instance
conversation_memory = SmartConversationMemory()

# Initialize the LLM with optimized settings for tool calling
llm = ChatOllama(
    model="qwen3:0.6b-fp16",
    temperature=0.3,  # Lower temperature for more consistent responses
    num_ctx=4096,  # Increased context for better understanding
    num_predict=512,  # Allow longer responses for detailed insights
    num_thread=8,  # Use multiple threads for speed
    streaming=True,  # Enable streaming for real-time responses
    verbose=True,
    top_p=0.9,  # Better response diversity
    top_k=40,  # Focus on high-probability tokens
)

# Bind tools to the LLM for tool calling
llm_with_tools = llm.bind_tools(tools_list)

class ToolCallingCallbackHandler(AsyncCallbackHandler):
    """Callback handler for tool calling streaming"""

    def __init__(self, websocket=None):
        self.websocket = websocket
        self.start_time = None

    async def on_llm_start(self, *args, **kwargs):
        """Called when LLM starts generating"""
        self.start_time = time.time()
        if self.websocket:
            await self.websocket.send_json({
                "type": "llm_start",
                "timestamp": datetime.now().isoformat()
            })

    async def on_llm_new_token(self, token: str, **kwargs):
        """Stream each token as it's generated"""
        if self.websocket:
            await self.websocket.send_json({
                "type": "token",
                "content": token,
                "timestamp": datetime.now().isoformat()
            })

    async def on_llm_end(self, *args, **kwargs):
        """Called when LLM finishes generating"""
        elapsed_time = time.time() - self.start_time if self.start_time else 0
        if self.websocket:
            await self.websocket.send_json({
                "type": "llm_end",
                "elapsed_time": elapsed_time,
                "timestamp": datetime.now().isoformat()
            })

    async def on_tool_start(self, serialized: Dict[str, Any], input_str: str, **kwargs):
        """Called when a tool starts executing"""
        tool_name = serialized.get("name", "Unknown Tool")
        if self.websocket:
            await self.websocket.send_json({
                "type": "tool_start",
                "tool_name": tool_name,
                "input": input_str,
                "timestamp": datetime.now().isoformat()
            })

    async def on_tool_end(self, output: str, **kwargs):
        """Called when a tool finishes executing"""
        if self.websocket:
            await self.websocket.send_json({
                "type": "tool_end",
                "output": output,
                "timestamp": datetime.now().isoformat()
            })

class MongoDBAgent:
    """MongoDB Agent using Tool Calling with Optimized Context Management"""

    def __init__(self, max_chunk_size: int = 1000, enable_chunked_processing: bool = True):
        self.llm_with_tools = llm_with_tools
        self.connected = False
        self.max_chunk_size = max_chunk_size
        self.enable_chunked_processing = enable_chunked_processing

    async def connect(self):
        """Connect to MongoDB MCP server"""
        await mongodb_tools.connect()
        self.connected = True
        print("MongoDB Agent connected successfully!")

    async def disconnect(self):
        """Disconnect from MongoDB MCP server"""
        await mongodb_tools.disconnect()
        self.connected = False
    
    def _chunk_large_content(self, content: str, max_size: int = None) -> List[str]:
        """Break large content into manageable chunks"""
        if max_size is None:
            max_size = self.max_chunk_size
            
        if len(content) <= max_size:
            return [content]
        
        chunks = []
        # Try to split on natural boundaries (sentences, paragraphs)
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
    
    async def _process_chunked_response(self, chunks: List[str], messages: List[BaseMessage], websocket=None) -> str:
        """Process large responses in chunks to prevent context overflow"""
        responses = []
        
        for i, chunk in enumerate(chunks):
            if websocket:
                await websocket.send_json({
                    "type": "chunk_processing",
                    "chunk_index": i + 1,
                    "total_chunks": len(chunks),
                    "timestamp": datetime.now().isoformat()
                })
            
            # Create a focused query for this chunk
            chunk_message = HumanMessage(content=f"[Processing chunk {i+1}/{len(chunks)}]: {chunk}")
            chunk_messages = messages[-3:] + [chunk_message]  # Keep only recent context
            
            chunk_response = await self.llm_with_tools.ainvoke(chunk_messages)
            responses.append(chunk_response.content)
            
            # Small delay between chunks to prevent overwhelming the system
            await asyncio.sleep(0.1)
        
        # Combine responses
        return " ".join(responses)

    async def run(self, query: str, conversation_id: Optional[str] = None) -> str:
        """Run the agent with a query and optional conversation context"""
        if not self.connected:
            await self.connect()

        try:
            # Use default conversation ID if none provided
            if not conversation_id:
                conversation_id = f"conv_{int(time.time())}"

            # Get optimized conversation history
            conversation_context = conversation_memory.get_optimized_context(conversation_id)

            # Add current user message
            human_message = HumanMessage(content=query)
            messages = conversation_context + [human_message]

            response = await self.llm_with_tools.ainvoke(messages)

            # Add messages to conversation memory
            conversation_memory.add_message(conversation_id, human_message)
            conversation_memory.add_message(conversation_id, response)

            # Handle tool calls if any
            if response.tool_calls:
                messages.append(response)
                for tool_call in response.tool_calls:
                    # Find the tool
                    tool = next((t for t in tools_list if t.name == tool_call["name"]), None)
                    if tool:
                        # Execute the tool
                        result = await tool.ainvoke(tool_call["args"])
                        tool_message = ToolMessage(
                            content=str(result),
                            tool_call_id=tool_call["id"]
                        )
                        messages.append(tool_message)
                        conversation_memory.add_message(conversation_id, tool_message)

                # Get final response after tool calls
                final_response = await self.llm_with_tools.ainvoke(messages)
                conversation_memory.add_message(conversation_id, final_response)
                return final_response.content
            else:
                return response.content

        except Exception as e:
            return f"Error running agent: {str(e)}"

    async def run_streaming(self, query: str, websocket=None, conversation_id: Optional[str] = None) -> AsyncGenerator[str, None]:
        """Run the agent with streaming support and conversation context"""
        if not self.connected:
            await self.connect()

        try:
            # Use default conversation ID if none provided
            if not conversation_id:
                conversation_id = f"conv_{int(time.time())}"

            # Get optimized conversation history
            conversation_context = conversation_memory.get_optimized_context(conversation_id)

            # Add current user message
            human_message = HumanMessage(content=query)
            messages = conversation_context + [human_message]

            callback_handler = ToolCallingCallbackHandler(websocket)

            # Get initial response with streaming
            response = await self.llm_with_tools.ainvoke(
                messages,
                config={"callbacks": [callback_handler]}
            )

            # Add messages to conversation memory
            conversation_memory.add_message(conversation_id, human_message)
            conversation_memory.add_message(conversation_id, response)

            # Handle tool calls if any
            if response.tool_calls:
                messages.append(response)
                for tool_call in response.tool_calls:
                    # Find the tool
                    tool = next((t for t in tools_list if t.name == tool_call["name"]), None)
                    if tool:
                        # Execute the tool with callback
                        await callback_handler.on_tool_start(
                            {"name": tool.name},
                            str(tool_call["args"])
                        )
                        result = await tool.ainvoke(tool_call["args"])
                        await callback_handler.on_tool_end(str(result))

                        tool_message = ToolMessage(
                            content=str(result),
                            tool_call_id=tool_call["id"]
                        )
                        messages.append(tool_message)
                        conversation_memory.add_message(conversation_id, tool_message)

                # Get final response after tool calls with streaming
                final_response = await self.llm_with_tools.ainvoke(
                    messages,
                    config={"callbacks": [callback_handler]}
                )
                conversation_memory.add_message(conversation_id, final_response)
                yield final_response.content
            else:
                yield response.content

        except Exception as e:
            yield f"Error running streaming agent: {str(e)}"
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Get comprehensive system performance statistics"""
        memory_stats = conversation_memory.get_memory_stats()
        
        return {
            "agent_settings": {
                "max_chunk_size": self.max_chunk_size,
                "chunked_processing_enabled": self.enable_chunked_processing,
                "connected": self.connected
            },
            "memory": memory_stats,
            "model_settings": {
                "model": "qwen3:0.6b-fp16",
                "context_size": 4096,
                "streaming": True
            }
        }
    
    async def optimize_for_performance(self, conversation_id: str):
        """Perform performance optimizations for a specific conversation"""
        if conversation_id in conversation_memory.conversations:
            # Clean up very old conversations to free memory
            if len(conversation_memory.conversations) > 20:  # Keep only 20 most recent conversations
                oldest_convs = sorted(conversation_memory.conversations.keys())[:-20]
                for old_conv in oldest_convs:
                    conversation_memory.clear_conversation(old_conv)
        
        # Clear token estimation cache if it's getting too large
        if len(conversation_memory.token_estimation_cache) > 1500:
            conversation_memory.token_estimation_cache.clear()

# ProjectManagement Insights Examples
async def main():
    """Example usage of the optimized ProjectManagement Insights Agent"""
    # Initialize agent with optimized settings
    agent = MongoDBAgent(max_chunk_size=800, enable_chunked_processing=True)
    await agent.connect()
    
    # Example of getting system stats
    stats = agent.get_system_stats()
    print(f"System Stats: {json.dumps(stats, indent=2)}")
    
    # Example conversation that will demonstrate context optimization
    conversation_id = "demo_conversation"
    
    # Simulate a long conversation to test context management
    queries = [
        "What are the key features of MongoDB?",
        "How does sharding work in MongoDB?",
        "Can you explain MongoDB transactions?",
        "What are the best practices for MongoDB indexing?",
        "How does MongoDB handle replication?"
    ]
    
    for i, query in enumerate(queries):
        print(f"\nQuery {i+1}: {query}")
        response = await agent.run(query, conversation_id)
        print(f"Response: {response[:200]}...")  # Show first 200 chars
        
        # Optimize performance periodically
        if i % 2 == 1:  # Every other query
            await agent.optimize_for_performance(conversation_id)
    
    # Show final memory stats
    final_stats = agent.get_system_stats()
    print(f"\nFinal System Stats: {json.dumps(final_stats, indent=2)}")
    
    await agent.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
