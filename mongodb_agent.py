from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, END, MessagesState
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
import json
import asyncio
from typing import Dict, Any, List
from pydantic import BaseModel

# Database configuration
DATABASE_NAME = "ProjectManagement"

# MCP Server Configuration
mongodb_server_config = {
    "mongodb": {
        "command": "npx",
        "args": ["-y", "@mongodb-js/mongodb-mcp-server"],
        "env": {
            "MONGODB_CONNECTION_STRING": "mongodb://localhost:27017",
            "MONGODB_DATABASE_NAME": DATABASE_NAME
        }
    }
}

# HTTP-based configuration for Smithery
smithery_config = {
    "mongodb": {
        "url": "https://server.smithery.ai/@mongodb-js/mongodb-mcp-server/mcp?api_key=4fd11c6a-4c6f-45ce-ab0d-24cb4c051779&profile=furious-lemming-rvSkqO",
        "transport": "streamable_http"
    }
}

class MongoDBTools:
    """MongoDB MCP Tools wrapper using langchain-mcp-adapters"""

    def __init__(self):
        self.client = MultiServerMCPClient(smithery_config)
        self.tools = []
        self.connected = False

    async def connect(self):
        """Initialize connection to MongoDB MCP server using langchain-mcp-adapters"""
        try:
            # Get tools from the MCP server (this will establish connections as needed)
            self.tools = await self.client.get_tools()
            self.connected = True
            print(f"Connected to MongoDB MCP. Available tools: {[tool.name for tool in self.tools]}")

        except Exception as e:
            print(f"Failed to connect to MongoDB MCP server: {e}")
            raise

    async def disconnect(self):
        """Disconnect from MongoDB MCP server"""
        # MultiServerMCPClient handles connection cleanup automatically
        self.connected = False
        self.tools = []

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a MongoDB MCP tool"""
        if not self.connected:
            raise ValueError("Not connected to MCP server")

        # Find the tool
        tool = next((t for t in self.tools if t.name == tool_name), None)
        if not tool:
            raise ValueError(f"Tool {tool_name} not available")

        # Execute the tool directly (it handles MCP communication internally)
        result = await tool.ainvoke(arguments)
        return result

# Global MongoDB tools instance
mongodb_tools = MongoDBTools()

# Define LangGraph tools
@tool
async def list_databases() -> str:
    """List all available databases"""
    try:
        result = await mongodb_tools.execute_tool("list-databases", {})
        return f"Available databases: {result}"
    except Exception as e:
        return f"Error listing databases: {str(e)}"

@tool
async def list_collections(database: str = DATABASE_NAME) -> str:
    """List collections in the specified database"""
    try:
        result = await mongodb_tools.execute_tool("list-collections", {"database": database})
        return f"Collections in {database}: {result}"
    except Exception as e:
        return f"Error listing collections: {str(e)}"

@tool
async def find_documents(collection: str, query: Dict[str, Any] = None, database: str = DATABASE_NAME, limit: int = 10) -> str:
    """Find documents in a collection"""
    try:
        if query is None:
            query = {}
        result = await mongodb_tools.execute_tool("find", {
            "database": database,
            "collection": collection,
            "filter": query,
            "limit": limit
        })
        return f"Found documents: {result}"
    except Exception as e:
        return f"Error finding documents: {str(e)}"

# Define the tools list
tools = [
    list_databases,
    list_collections,
    find_documents,
]

# Initialize the LLM with optimized settings for faster performance
llm = ChatOllama(
    model="qwen3:0.6b-fp16",
    temperature=0.3,
    num_ctx=2048,  # Smaller context window for faster responses
    num_predict=256,  # Limit token generation
    num_thread=8,  # Use multiple threads
    streaming=True,  # Enable streaming
    verbose=False
)
llm_with_tools = llm.bind_tools(tools)

# Define the agent state
class AgentState(MessagesState):
    pass

# Define the agent workflow
def call_agent(state: AgentState):
    """Main agent logic"""
    messages = state["messages"]
    response = llm_with_tools.invoke(messages)

    return {"messages": [response]}

async def call_agent_streaming(state: AgentState, callback_handler=None):
    """Main agent logic with streaming support"""
    messages = state["messages"]
    
    # Create a new LLM instance with the callback handler if provided
    if callback_handler:
        streaming_llm = ChatOllama(
            model="qwen3:0.6b-fp16",
            temperature=0.3,
            num_ctx=2048,
            num_predict=256,
            num_thread=8,
            streaming=True,
            callbacks=[callback_handler]
        )
        streaming_llm_with_tools = streaming_llm.bind_tools(tools)
        response = await streaming_llm_with_tools.ainvoke(messages)
    else:
        response = await llm_with_tools.ainvoke(messages)
    
    return {"messages": [response]}

async def call_tools_async(state: AgentState, callback_handler=None):
    """Execute tools based on agent response (async version)"""
    messages = state["messages"]
    last_message = messages[-1]

    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return {"messages": []}

    tool_results = []
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]

        # Find the corresponding tool
        tool = next((t for t in tools if t.name == tool_name), None)
        if tool:
            try:
                # Notify callback about tool execution
                if callback_handler:
                    await callback_handler.on_tool_start(
                        {"name": tool_name}, 
                        str(tool_args)
                    )
                
                # Run the async tool
                result = await tool.ainvoke(tool_args)
                
                if callback_handler:
                    await callback_handler.on_tool_end(str(result))
                    
                tool_results.append(ToolMessage(
                    content=str(result),
                    tool_call_id=tool_call["id"]
                ))
            except Exception as e:
                error_msg = f"Error executing tool {tool_name}: {str(e)}"
                if callback_handler:
                    await callback_handler.on_tool_end(error_msg)
                    
                tool_results.append(ToolMessage(
                    content=error_msg,
                    tool_call_id=tool_call["id"]
                ))

    return {"messages": tool_results}

def call_tools(state: AgentState):
    """Execute tools based on agent response (sync version)"""
    messages = state["messages"]
    last_message = messages[-1]

    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return {"messages": []}

    tool_results = []
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]

        # Find the corresponding tool
        tool = next((t for t in tools if t.name == tool_name), None)
        if tool:
            try:
                # Run the async tool
                result = asyncio.run(tool.ainvoke(tool_args))
                tool_results.append(ToolMessage(
                    content=str(result),
                    tool_call_id=tool_call["id"]
                ))
            except Exception as e:
                tool_results.append(ToolMessage(
                    content=f"Error executing tool {tool_name}: {str(e)}",
                    tool_call_id=tool_call["id"]
                ))

    return {"messages": tool_results}

def should_continue(state: AgentState) -> str:
    """Determine if we should continue or end"""
    messages = state["messages"]
    last_message = messages[-1]

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return END

# Create the graph
workflow = StateGraph(AgentState)
workflow.add_node("agent", call_agent)
workflow.add_node("tools", call_tools)

workflow.set_entry_point("agent")
workflow.add_conditional_edges("agent", should_continue)
workflow.add_edge("tools", "agent")

# Compile the graph
graph = workflow.compile()

class MongoDBAgent:
    """MongoDB Agent using LangGraph and MCP"""

    def __init__(self):
        self.graph = graph
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

        messages = [HumanMessage(content=query)]
        result = await graph.ainvoke({"messages": messages})

        # Get the final response
        final_message = result["messages"][-1]
        return final_message.content
    
    async def run_streaming(self, query: str, callback_handler=None, websocket=None):
        """Run the agent with streaming support"""
        if not self.connected:
            await self.connect()
            
        messages = [HumanMessage(content=query)]
        state = {"messages": messages}
        
        # Create a custom graph for streaming
        while True:
            # Call agent with streaming
            agent_result = await call_agent_streaming(state, callback_handler)
            state["messages"].extend(agent_result["messages"])
            
            last_message = state["messages"][-1]
            
            # Check if we need to call tools
            if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                # Execute tools
                tool_result = await call_tools_async(state, callback_handler)
                state["messages"].extend(tool_result["messages"])
            else:
                # No more tools to call, we're done
                break
                
        # Return the final response
        return state["messages"][-1].content

# Example usage
async def main():
    """Example usage of the MongoDB Agent"""
    agent = MongoDBAgent()

    try:
        # Connect to MongoDB
        await agent.connect()

        # Example queries
        queries = [
            "List all collections in the ProjectManagement database",
            "Create a new collection called 'projects' if it doesn't exist",
            "Insert a sample project document with name 'AI Assistant' and status 'active'",
            "Find all projects with status 'active'",
        ]

        for query in queries:
            print(f"\nQuery: {query}")
            response = await agent.run(query)
            print(f"Response: {response}")

    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        await agent.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
