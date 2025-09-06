from langchain_ollama import ChatOllama

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, BaseMessage
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_mcp_adapters.client import MultiServerMCPClient
import json
import asyncio
from typing import Dict, Any, List, AsyncGenerator, Optional
from pydantic import BaseModel
import tools
from datetime import datetime
import time
from collections import defaultdict, deque

tools_list = tools.tools
from constants import DATABASE_NAME, mongodb_tools

class ConversationMemory:
    """Manages conversation history with intelligent context optimization"""

    def __init__(self, max_messages_per_conversation: int = 50, max_context_tokens: int = 3000):
        self.conversations: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_messages_per_conversation))
        self.max_messages_per_conversation = max_messages_per_conversation
        self.max_context_tokens = max_context_tokens
        self.thinking_summaries: Dict[str, Dict[str, str]] = defaultdict(dict)  # conversation_id -> {message_id: summary}

    def add_message(self, conversation_id: str, message: BaseMessage):
        """Add a message to the conversation history"""
        self.conversations[conversation_id].append(message)

    def get_conversation_history(self, conversation_id: str) -> List[BaseMessage]:
        """Get the conversation history for a given conversation ID"""
        return list(self.conversations[conversation_id])

    def clear_conversation(self, conversation_id: str):
        """Clear the conversation history for a given conversation ID"""
        if conversation_id in self.conversations:
            self.conversations[conversation_id].clear()
        if conversation_id in self.thinking_summaries:
            del self.thinking_summaries[conversation_id]

    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation (4 chars ≈ 1 token for most models)"""
        return len(text) // 4

    def _is_thinking_content(self, content: str) -> bool:
        """Check if content contains thinking tags"""
        return '<think>' in content or '</think>' in content

    def _extract_thinking_content(self, content: str) -> tuple[str, str]:
        """Extract thinking content and non-thinking content"""
        if not self._is_thinking_content(content):
            return "", content
        
        # Simple extraction - in production you'd want more robust parsing
        thinking_parts = []
        non_thinking_parts = []
        
        # Split by think tags and categorize
        parts = content.split('<think>')
        non_thinking_parts.append(parts[0])
        
        for part in parts[1:]:
            if '</think>' in part:
                think_content, rest = part.split('</think>', 1)
                thinking_parts.append(think_content)
                non_thinking_parts.append(rest)
            else:
                thinking_parts.append(part)
        
        thinking_content = '\n'.join(thinking_parts)
        non_thinking_content = '\n'.join(non_thinking_parts)
        
        return thinking_content, non_thinking_content

    def _compress_thinking(self, thinking_content: str) -> str:
        """Compress thinking content to key insights (simple version)"""
        if not thinking_content.strip():
            return ""
        
        # Simple compression: keep first and last sentences, add ellipsis
        sentences = thinking_content.strip().split('. ')
        if len(sentences) <= 2:
            return thinking_content
        
        # Keep first and last sentence, add summary
        compressed = f"{sentences[0]}. [...thinking process...] {sentences[-1]}"
        
        # If still too long, truncate more aggressively
        if len(compressed) > 200:
            compressed = compressed[:197] + "..."
        
        return compressed

    def _prioritize_messages(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """Prioritize messages by importance for context retention"""
        prioritized = []
        
        for message in messages:
            # Always keep user messages (highest priority)
            if isinstance(message, HumanMessage):
                prioritized.append(message)
            # Keep AI messages but potentially compress thinking content
            elif isinstance(message, AIMessage):
                if hasattr(message, 'content') and self._is_thinking_content(message.content):
                    # Extract and compress thinking
                    thinking_content, non_thinking_content = self._extract_thinking_content(message.content)
                    compressed_thinking = self._compress_thinking(thinking_content)
                    
                    # Create new message with compressed content
                    if compressed_thinking and non_thinking_content:
                        new_content = f"<think>{compressed_thinking}</think>{non_thinking_content}"
                    elif compressed_thinking:
                        new_content = f"<think>{compressed_thinking}</think>"
                    else:
                        new_content = non_thinking_content
                    
                    # Create a new message with compressed content
                    compressed_message = AIMessage(content=new_content)
                    prioritized.append(compressed_message)
                else:
                    prioritized.append(message)
            # Keep tool messages (medium priority)
            elif isinstance(message, ToolMessage):
                prioritized.append(message)
            else:
                prioritized.append(message)
        
        return prioritized

    def get_recent_context(self, conversation_id: str, max_tokens: int = None) -> List[BaseMessage]:
        """Get recent conversation context with intelligent optimization"""
        if max_tokens is None:
            max_tokens = self.max_context_tokens
            
        messages = self.get_conversation_history(conversation_id)
        
        if not messages:
            return []
        
        # Start with recent messages and work backwards
        context_messages = []
        current_tokens = 0
        
        # Always include the most recent message
        for message in reversed(messages):
            message_tokens = self._estimate_tokens(str(message.content))
            
            # If adding this message would exceed the limit
            if current_tokens + message_tokens > max_tokens and context_messages:
                break
                
            context_messages.insert(0, message)
            current_tokens += message_tokens
            
            # Stop if we have a good amount of context
            if len(context_messages) >= 15:  # More generous limit
                break
        
        # Prioritize and optimize the selected messages
        optimized_messages = self._prioritize_messages(context_messages)
        
        # Final token check and compression if needed
        while optimized_messages:
            total_tokens = sum(self._estimate_tokens(str(msg.content)) for msg in optimized_messages)
            if total_tokens <= max_tokens:
                break
            
            # Remove oldest message or compress further
            if len(optimized_messages) > 3:  # Always keep at least 3 messages
                optimized_messages.pop(0)
            else:
                # More aggressive compression on remaining messages
                for i, msg in enumerate(optimized_messages):
                    if isinstance(msg, AIMessage) and hasattr(msg, 'content'):
                        if len(msg.content) > 500:  # Compress long messages
                            compressed_content = msg.content[:200] + "...[truncated]..." + msg.content[-100:]
                            optimized_messages[i] = AIMessage(content=compressed_content)
                break
        
        return optimized_messages

    def handle_thinking_completion(self, conversation_id: str):
        """Called when thinking is complete - compress old thinking content more aggressively"""
        messages = list(self.conversations[conversation_id])
        
        if len(messages) < 2:
            return
        
        # Find messages with thinking content and compress them more aggressively
        # Skip the most recent message (current thinking)
        for i, message in enumerate(messages[:-1]):
            if isinstance(message, AIMessage) and hasattr(message, 'content'):
                if self._is_thinking_content(message.content):
                    thinking_content, non_thinking_content = self._extract_thinking_content(message.content)
                    
                    # More aggressive compression for completed thinking
                    if thinking_content and len(thinking_content) > 100:
                        # Super compressed version for old thinking
                        compressed = f"[Thinking completed: {len(thinking_content)} chars compressed]"
                        
                        if non_thinking_content.strip():
                            new_content = f"<think>{compressed}</think>{non_thinking_content}"
                        else:
                            new_content = f"<think>{compressed}</think>"
                        
                        # Update the message in place
                        messages[i] = AIMessage(content=new_content)
        
        # Replace the conversation with compressed messages
        self.conversations[conversation_id] = deque(messages, maxlen=self.max_messages_per_conversation)

    def get_adaptive_context(self, conversation_id: str, is_complex_task: bool = False, 
                           preserve_recent_thinking: bool = True) -> List[BaseMessage]:
        """Get context with adaptive token limits based on task complexity"""
        # Adjust context size based on task complexity
        if is_complex_task:
            # For complex tasks, allow more context but be smarter about compression
            base_tokens = self.max_context_tokens * 1.5
        else:
            base_tokens = self.max_context_tokens
        
        messages = self.get_recent_context(conversation_id, max_tokens=int(base_tokens))
        
        # If preserving recent thinking, be less aggressive with the latest message
        if preserve_recent_thinking and messages:
            latest_message = messages[-1]
            if isinstance(latest_message, AIMessage) and self._is_thinking_content(latest_message.content):
                # Don't compress the most recent thinking
                return messages
        
        return messages

    def optimize_for_speed(self, conversation_id: str) -> List[BaseMessage]:
        """Get minimal context optimized for speed - removes thinking content more aggressively"""
        messages = self.get_conversation_history(conversation_id)
        
        # Super aggressive optimization for speed
        optimized = []
        for message in messages[-6:]:  # Only last 6 messages
            if isinstance(message, HumanMessage):
                optimized.append(message)
            elif isinstance(message, AIMessage):
                if self._is_thinking_content(message.content):
                    # Remove thinking content entirely for speed
                    _, non_thinking = self._extract_thinking_content(message.content)
                    if non_thinking.strip():
                        optimized.append(AIMessage(content=non_thinking))
                else:
                    optimized.append(message)
            elif isinstance(message, ToolMessage):
                # Summarize tool messages
                content = message.content[:100] + "..." if len(message.content) > 100 else message.content
                optimized.append(ToolMessage(content=content, tool_call_id=message.tool_call_id))
        
        return optimized

# Global conversation memory instance with enhanced settings
conversation_memory = ConversationMemory(
    max_messages_per_conversation=100,  # Increased for better long-term context
    max_context_tokens=3500  # Slightly higher to accommodate compressed content
)

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
    """MongoDB Agent using Tool Calling with adaptive context management"""

    def __init__(self, optimize_for_speed: bool = False):
        self.llm_with_tools = llm_with_tools
        self.connected = False
        self.optimize_for_speed = optimize_for_speed

    async def connect(self):
        """Connect to MongoDB MCP server"""
        await mongodb_tools.connect()
        self.connected = True
        print("MongoDB Agent connected successfully!")

    async def disconnect(self):
        """Disconnect from MongoDB MCP server"""
        await mongodb_tools.disconnect()
        self.connected = False

    async def run(self, query: str, conversation_id: Optional[str] = None) -> str:
        """Run the agent with a query and optional conversation context"""
        if not self.connected:
            await self.connect()

        try:
            # Use default conversation ID if none provided
            if not conversation_id:
                conversation_id = f"conv_{int(time.time())}"

            # Get conversation history with adaptive context management
            if self.optimize_for_speed:
                conversation_context = conversation_memory.optimize_for_speed(conversation_id)
            else:
                # Detect if this might be a complex task (simple heuristic)
                is_complex_task = len(query.split()) > 20 or any(word in query.lower() for word in 
                    ['analyze', 'complex', 'detailed', 'comprehensive', 'thinking', 'reasoning'])
                conversation_context = conversation_memory.get_adaptive_context(
                    conversation_id, 
                    is_complex_task=is_complex_task,
                    preserve_recent_thinking=True
                )

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
                
                # Handle thinking completion if response contains thinking
                if conversation_memory._is_thinking_content(final_response.content):
                    conversation_memory.handle_thinking_completion(conversation_id)
                
                return final_response.content
            else:
                # Handle thinking completion if response contains thinking
                if conversation_memory._is_thinking_content(response.content):
                    conversation_memory.handle_thinking_completion(conversation_id)
                
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

            # Get conversation history with adaptive context management
            if self.optimize_for_speed:
                conversation_context = conversation_memory.optimize_for_speed(conversation_id)
            else:
                # Detect if this might be a complex task (simple heuristic)
                is_complex_task = len(query.split()) > 20 or any(word in query.lower() for word in 
                    ['analyze', 'complex', 'detailed', 'comprehensive', 'thinking', 'reasoning'])
                conversation_context = conversation_memory.get_adaptive_context(
                    conversation_id, 
                    is_complex_task=is_complex_task,
                    preserve_recent_thinking=True
                )

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
                
                # Handle thinking completion if response contains thinking
                if conversation_memory._is_thinking_content(final_response.content):
                    conversation_memory.handle_thinking_completion(conversation_id)
                
                yield final_response.content
            else:
                # Handle thinking completion if response contains thinking
                if conversation_memory._is_thinking_content(response.content):
                    conversation_memory.handle_thinking_completion(conversation_id)
                
                yield response.content

        except Exception as e:
            yield f"Error running streaming agent: {str(e)}"

# ProjectManagement Insights Examples
async def main():
    """Example usage of the ProjectManagement Insights Agent"""
    agent = MongoDBAgent()
    await agent.connect()


if __name__ == "__main__":
    asyncio.run(main())
