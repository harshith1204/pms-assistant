from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_mcp_adapters.client import MultiServerMCPClient
import json
import asyncio
from typing import Dict, Any, List, AsyncGenerator
from pydantic import BaseModel
import tools
from datetime import datetime
import time

tools_list = tools.tools
from constants import DATABASE_NAME, mongodb_tools

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
    """MongoDB Agent using Tool Calling"""

    def __init__(self):
        self.llm_with_tools = llm_with_tools
        self.connected = False

    async def connect(self):
        """Connect to MongoDB MCP server"""
        await mongodb_tools.connect()
        self.connected = True
        print("MongoDB Agent connected successfully!")

    async def disconnect(self):
        """Disconnect from MongoDB MCP server"""
        await mongodb_tools.disconnect()
        self.connected = False

    async def run(self, query: str) -> str:
        """Run the agent with a query"""
        if not self.connected:
            await self.connect()

        try:
            messages = [HumanMessage(content=query)]
            response = await self.llm_with_tools.ainvoke(messages)

            # Handle tool calls if any
            if response.tool_calls:
                messages.append(response)
                for tool_call in response.tool_calls:
                    # Find the tool
                    tool = next((t for t in tools_list if t.name == tool_call["name"]), None)
                    if tool:
                        # Execute the tool
                        result = await tool.ainvoke(tool_call["args"])
                        messages.append(ToolMessage(
                            content=str(result),
                            tool_call_id=tool_call["id"]
                        ))

                # Get final response after tool calls
                final_response = await self.llm_with_tools.ainvoke(messages)
                return final_response.content
            else:
                return response.content

        except Exception as e:
            return f"Error running agent: {str(e)}"

    async def run_streaming(self, query: str, websocket=None) -> AsyncGenerator[str, None]:
        """Run the agent with streaming support"""
        if not self.connected:
            await self.connect()

        try:
            messages = [HumanMessage(content=query)]
            callback_handler = ToolCallingCallbackHandler(websocket)

            # Get initial response with streaming
            response = await self.llm_with_tools.ainvoke(
                messages,
                config={"callbacks": [callback_handler]}
            )

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

                        messages.append(ToolMessage(
                            content=str(result),
                            tool_call_id=tool_call["id"]
                        ))

                # Get final response after tool calls with streaming
                final_response = await self.llm_with_tools.ainvoke(
                    messages,
                    config={"callbacks": [callback_handler]}
                )
                yield final_response.content
            else:
                yield response.content

        except Exception as e:
            yield f"Error running streaming agent: {str(e)}"

# ProjectManagement Insights Examples
async def main():
    """Example usage of the ProjectManagement Insights Agent"""
    agent = MongoDBAgent()
    await agent.connect()

    # Test the new count_work_items_by_project function
    result = await agent.run("How many work items are there in the Simpo project?")
    print(f"Query Result: {result}")

    # Test the detailed breakdown function
    result2 = await agent.run("Show me detailed work item breakdown for Simpo project")
    print(f"Detailed Result: {result2}")

if __name__ == "__main__":
    asyncio.run(main())
