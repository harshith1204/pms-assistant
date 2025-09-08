from langchain_ollama import ChatOllama

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, BaseMessage, SystemMessage
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

DEFAULT_SYSTEM_PROMPT = (
    "You are a planning and tool-using agent. For complex requests, break the task into"
    " sequential steps. Decide what to do next based on previous tool results."
    " Call tools as needed to gather data, transform it, and iterate until the goal is met."
    " Only produce the final answer when you have gathered enough evidence."
)

class ConversationMemory:
    """Manages conversation history for maintaining context"""

    def __init__(self, max_messages_per_conversation: int = 50):
        self.conversations: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_messages_per_conversation))
        self.max_messages_per_conversation = max_messages_per_conversation

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

    def get_recent_context(self, conversation_id: str, max_tokens: int = 3000) -> List[BaseMessage]:
        """Get recent conversation context, respecting token limits"""
        messages = self.get_conversation_history(conversation_id)

        # For now, just return the last few messages to stay within context limits
        # In a production system, you'd want to implement proper token counting
        if len(messages) <= 10:  # Return all if small conversation
            return messages
        else:
            # Return last 10 messages to keep context manageable
            return messages[-10:]

# Global conversation memory instance
conversation_memory = ConversationMemory()

# Initialize the LLM with optimized settings for tool calling
llm = ChatOllama(
    model="qwen3:0.6b-fp16",
    temperature=0.3,  # Lower temperature for more consistent responses
    num_ctx=4096,  # Increased context for better understanding
    num_predict=1024,  # Allow longer responses for detailed insights
    num_thread=8,  # Use multiple threads for speed
    streaming=True,  # Enable streaming for real-time responses
    verbose=False,
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
    """MongoDB Agent using Tool Calling"""

    def __init__(self, max_steps: int = 8, system_prompt: Optional[str] = DEFAULT_SYSTEM_PROMPT):
        self.llm_with_tools = llm_with_tools
        self.connected = False
        self.max_steps = max_steps
        self.system_prompt = system_prompt

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

            # Get conversation history
            conversation_context = conversation_memory.get_recent_context(conversation_id)

            # Build messages with optional system instruction
            messages: List[BaseMessage] = []
            if self.system_prompt:
                messages.append(SystemMessage(content=self.system_prompt))
            messages.extend(conversation_context)

            # Add current user message
            human_message = HumanMessage(content=query)
            messages.append(human_message)

            # Persist the human message
            conversation_memory.add_message(conversation_id, human_message)

            steps = 0
            last_response: Optional[AIMessage] = None

            while steps < self.max_steps:
                response = await self.llm_with_tools.ainvoke(messages)
                last_response = response

                # Persist assistant message
                conversation_memory.add_message(conversation_id, response)

                # If no tools requested, we are done
                if not getattr(response, "tool_calls", None):
                    return response.content

                # Execute requested tools sequentially
                messages.append(response)
                for tool_call in response.tool_calls:
                    tool = next((t for t in tools_list if t.name == tool_call["name"]), None)
                    if not tool:
                        # If tool not found, surface an error message and stop
                        error_msg = ToolMessage(
                            content=f"Tool '{tool_call['name']}' not found.",
                            tool_call_id=tool_call["id"],
                        )
                        messages.append(error_msg)
                        conversation_memory.add_message(conversation_id, error_msg)
                        continue

                    try:
                        result = await tool.ainvoke(tool_call["args"])
                    except Exception as tool_exc:
                        result = f"Tool execution error: {tool_exc}"

                    tool_message = ToolMessage(
                        content=str(result),
                        tool_call_id=tool_call["id"],
                    )
                    messages.append(tool_message)
                    conversation_memory.add_message(conversation_id, tool_message)

                steps += 1

            # Step cap reached; return best available answer
            if last_response is not None:
                return last_response.content
            return "Reached maximum reasoning steps without a final answer."

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

            # Get conversation history
            conversation_context = conversation_memory.get_recent_context(conversation_id)

            # Build messages with optional system instruction
            messages: List[BaseMessage] = []
            if self.system_prompt:
                messages.append(SystemMessage(content=self.system_prompt))
            messages.extend(conversation_context)

            # Add current user message
            human_message = HumanMessage(content=query)
            messages.append(human_message)

            callback_handler = ToolCallingCallbackHandler(websocket)

            # Persist the human message
            conversation_memory.add_message(conversation_id, human_message)

            steps = 0
            last_response: Optional[AIMessage] = None

            while steps < self.max_steps:
                response = await self.llm_with_tools.ainvoke(
                    messages,
                    config={"callbacks": [callback_handler]},
                )
                last_response = response

                # Persist assistant message
                conversation_memory.add_message(conversation_id, response)

                if not getattr(response, "tool_calls", None):
                    yield response.content
                    return

                # Execute requested tools sequentially with streaming callbacks
                messages.append(response)
                for tool_call in response.tool_calls:
                    tool = next((t for t in tools_list if t.name == tool_call["name"]), None)
                    if not tool:
                        error_msg = ToolMessage(
                            content=f"Tool '{tool_call['name']}' not found.",
                            tool_call_id=tool_call["id"],
                        )
                        messages.append(error_msg)
                        conversation_memory.add_message(conversation_id, error_msg)
                        continue

                    await callback_handler.on_tool_start({"name": tool.name}, str(tool_call["args"]))
                    try:
                        result = await tool.ainvoke(tool_call["args"])
                        await callback_handler.on_tool_end(str(result))
                    except Exception as tool_exc:
                        result = f"Tool execution error: {tool_exc}"
                        await callback_handler.on_tool_end(str(result))

                    tool_message = ToolMessage(
                        content=str(result),
                        tool_call_id=tool_call["id"],
                    )
                    messages.append(tool_message)
                    conversation_memory.add_message(conversation_id, tool_message)

                steps += 1

            # Step cap reached; send best available response
            if last_response is not None:
                yield last_response.content
            else:
                yield "Reached maximum reasoning steps without a final answer."
            return

        except Exception as e:
            yield f"Error running streaming agent: {str(e)}"

# ProjectManagement Insights Examples
async def main():
    """Example usage of the ProjectManagement Insights Agent"""
    agent = MongoDBAgent()
    await agent.connect()


if __name__ == "__main__":
    asyncio.run(main())
