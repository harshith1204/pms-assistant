from langchain_ollama import ChatOllama
from langchain.agents import create_react_agent, AgentExecutor
from langchain_core.prompts import PromptTemplate
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
import json
import asyncio
from typing import Dict, Any, List
from pydantic import BaseModel
import pms_tools
tools = pms_tools.tools

from constants import DATABASE_NAME, mongodb_tools

# React Agent prompt template
REACT_PROMPT = PromptTemplate.from_template("""You are a ProjectManagement AI assistant with access to readonly database tools.

Available tools and their purposes:
{tools}

You must use these tools to answer questions. Do not guess or make up data.

Use the following format:
Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {input}
Thought: {agent_scratchpad}""")

# Initialize the LLM with optimized settings for better performance
llm = ChatOllama(
    model="qwen3:1.7b-fp16",
    temperature=0.1,  # Lower temperature for more consistent responses
    num_ctx=4096,  # Increased context for better understanding
    num_predict=512,  # Allow longer responses for detailed insights
    num_thread=8,  # Use multiple threads for speed
    streaming=True,  # Enable streaming for real-time responses
    verbose=True,
    top_p=0.9,  # Better response diversity
    top_k=40,  # Focus on high-probability tokens
)

# Create the React agent with tools and prompt
react_agent = create_react_agent(llm, tools, REACT_PROMPT)

# Create the agent executor
agent_executor = AgentExecutor(
    agent=react_agent,
    tools=tools,
    verbose=True,
    handle_parsing_errors=True,
    max_iterations=3
)

# Agent uses React Agent for tool calling

class MongoDBAgent:
    """MongoDB Agent using React Agent and MCP"""

    def __init__(self):
        self.agent_executor = agent_executor
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
            result = await self.agent_executor.ainvoke({"input": query})
            return result["output"]
        except Exception as e:
            return f"Error running agent: {str(e)}"
    
    async def run_streaming(self, query: str, callback_handler=None, websocket=None):
        """Run the agent with streaming support"""
        if not self.connected:
            await self.connect()

        try:
            result = await self.agent_executor.ainvoke({"input": query})
            return result["output"]
        except Exception as e:
            return f"Error running streaming agent: {str(e)}"

# ProjectManagement Insights Examples
async def main():
    """Example usage of the ProjectManagement Insights Agent"""

if __name__ == "__main__":
    asyncio.run(main())
