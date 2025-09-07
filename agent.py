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
    """
    MongoDB Agent with Iterative Tool Calling Capability
    
    This agent supports complex multi-step reasoning by performing iterative tool calling:
    
    KEY FEATURES:
    - Iterative Processing: Continues calling tools until task completion
    - Sequential Decision Making: Analyzes results from each tool call before deciding next steps
    - Context Preservation: Maintains conversation context across iterations
    - Streaming Support: Real-time streaming with iteration progress tracking
    - Error Handling: Graceful handling of tool failures and max iteration limits
    
    FLOW EXAMPLE:
    User Query → LLM Analysis → Tool Call(s) → Result Analysis → 
    More Tool Calls (if needed) → Final Response
    
    This enables handling of complex queries like:
    - "Find the highest budget project and analyze all its tasks"
    - "Compare performance metrics across all teams and provide recommendations"  
    - "Generate a comprehensive report on project status with risk analysis"
    
    PARAMETERS:
    - max_iterations: Maximum number of tool calling rounds (default: 10)
    """

    def __init__(self, max_iterations: int = 10):
        self.llm_with_tools = llm_with_tools
        self.connected = False
        self.max_iterations = max_iterations
        
        # Statistics tracking
        self.stats = {
            "total_queries": 0,
            "total_iterations": 0,
            "total_tool_calls": 0,
            "avg_iterations_per_query": 0,
            "max_iterations_reached": 0
        }

    async def connect(self):
        """Connect to MongoDB MCP server"""
        await mongodb_tools.connect()
        self.connected = True
        print("MongoDB Agent connected successfully!")

    async def disconnect(self):
        """Disconnect from MongoDB MCP server"""
        await mongodb_tools.disconnect()
        self.connected = False

    def get_stats(self) -> Dict[str, Any]:
        """Get agent performance statistics"""
        if self.stats["total_queries"] > 0:
            self.stats["avg_iterations_per_query"] = round(
                self.stats["total_iterations"] / self.stats["total_queries"], 2
            )
        return self.stats.copy()
    
    def reset_stats(self):
        """Reset agent statistics"""
        self.stats = {
            "total_queries": 0,
            "total_iterations": 0,
            "total_tool_calls": 0,
            "avg_iterations_per_query": 0,
            "max_iterations_reached": 0
        }

    async def run(self, query: str, conversation_id: Optional[str] = None) -> str:
        """Run the agent with iterative tool calling until task completion"""
        if not self.connected:
            await self.connect()

        try:
            # Use default conversation ID if none provided
            if not conversation_id:
                conversation_id = f"conv_{int(time.time())}"

            # Get conversation history
            conversation_context = conversation_memory.get_recent_context(conversation_id)

            # Add current user message
            human_message = HumanMessage(content=query)
            messages = conversation_context + [human_message]
            
            # Add human message to memory immediately
            conversation_memory.add_message(conversation_id, human_message)

            # Update query stats
            self.stats["total_queries"] += 1

            # Iterative tool calling loop
            iteration = 0
            while iteration < self.max_iterations:
                print(f"Agent iteration {iteration + 1}")
                
                # Get LLM response
                response = await self.llm_with_tools.ainvoke(messages)
                messages.append(response)
                conversation_memory.add_message(conversation_id, response)
                
                # Check if there are tool calls to execute
                if response.tool_calls:
                    print(f"Executing {len(response.tool_calls)} tool call(s)")
                    self.stats["total_tool_calls"] += len(response.tool_calls)
                    
                    # Execute all tool calls in this iteration
                    for tool_call in response.tool_calls:
                        # Find the tool
                        tool = next((t for t in tools_list if t.name == tool_call["name"]), None)
                        if tool:
                            print(f"Calling tool: {tool_call['name']}")
                            # Execute the tool
                            result = await tool.ainvoke(tool_call["args"])
                            tool_message = ToolMessage(
                                content=str(result),
                                tool_call_id=tool_call["id"]
                            )
                            messages.append(tool_message)
                            conversation_memory.add_message(conversation_id, tool_message)
                        else:
                            print(f"Warning: Tool {tool_call['name']} not found")
                    
                    # Continue to next iteration to let LLM process the tool results
                    iteration += 1
                    continue
                else:
                    # No more tool calls - we're done
                    print("No more tool calls needed - task complete")
                    self.stats["total_iterations"] += iteration + 1
                    return response.content
            
            # If we exit the loop due to max iterations, return the last response
            print(f"Reached maximum iterations ({self.max_iterations})")
            self.stats["total_iterations"] += self.max_iterations
            self.stats["max_iterations_reached"] += 1
            return response.content if 'response' in locals() else "Max iterations reached without completion"

        except Exception as e:
            return f"Error running agent: {str(e)}"

    async def run_streaming(self, query: str, websocket=None, conversation_id: Optional[str] = None) -> AsyncGenerator[str, None]:
        """Run the agent with iterative tool calling and streaming support"""
        if not self.connected:
            await self.connect()

        try:
            # Use default conversation ID if none provided
            if not conversation_id:
                conversation_id = f"conv_{int(time.time())}"

            # Get conversation history
            conversation_context = conversation_memory.get_recent_context(conversation_id)

            # Add current user message
            human_message = HumanMessage(content=query)
            messages = conversation_context + [human_message]
            
            # Add human message to memory immediately
            conversation_memory.add_message(conversation_id, human_message)

            callback_handler = ToolCallingCallbackHandler(websocket)

            # Send iteration start event
            if websocket:
                await websocket.send_json({
                    "type": "agent_start",
                    "query": query,
                    "conversation_id": conversation_id,
                    "timestamp": datetime.now().isoformat()
                })

            # Iterative tool calling loop
            iteration = 0
            while iteration < self.max_iterations:
                # Send iteration event
                if websocket:
                    await websocket.send_json({
                        "type": "iteration_start",
                        "iteration": iteration + 1,
                        "max_iterations": self.max_iterations,
                        "timestamp": datetime.now().isoformat()
                    })
                
                # Get LLM response with streaming
                response = await self.llm_with_tools.ainvoke(
                    messages,
                    config={"callbacks": [callback_handler]}
                )
                messages.append(response)
                conversation_memory.add_message(conversation_id, response)
                
                # Check if there are tool calls to execute
                if response.tool_calls:
                    # Send tool execution start event
                    if websocket:
                        await websocket.send_json({
                            "type": "tools_execution_start",
                            "tool_count": len(response.tool_calls),
                            "iteration": iteration + 1,
                            "timestamp": datetime.now().isoformat()
                        })
                    
                    # Execute all tool calls in this iteration
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
                        else:
                            # Send warning about unknown tool
                            if websocket:
                                await websocket.send_json({
                                    "type": "warning",
                                    "message": f"Tool {tool_call['name']} not found",
                                    "timestamp": datetime.now().isoformat()
                                })
                    
                    # Continue to next iteration to let LLM process the tool results
                    iteration += 1
                    continue
                else:
                    # No more tool calls - we're done
                    if websocket:
                        await websocket.send_json({
                            "type": "agent_complete",
                            "iterations_used": iteration + 1,
                            "reason": "no_more_tools_needed",
                            "timestamp": datetime.now().isoformat()
                        })
                    yield response.content
                    return
            
            # If we exit the loop due to max iterations
            if websocket:
                await websocket.send_json({
                    "type": "agent_complete",
                    "iterations_used": self.max_iterations,
                    "reason": "max_iterations_reached",
                    "timestamp": datetime.now().isoformat()
                })
            
            if 'response' in locals():
                yield response.content
            else:
                yield "Max iterations reached without completion"

        except Exception as e:
            error_msg = f"Error running streaming agent: {str(e)}"
            if websocket:
                await websocket.send_json({
                    "type": "agent_error",
                    "error": error_msg,
                    "timestamp": datetime.now().isoformat()
                })
            yield error_msg

# ProjectManagement Insights Examples
async def main():
    """Example usage of the iterative ProjectManagement Insights Agent"""
    # Create agent with custom max iterations
    agent = MongoDBAgent(max_iterations=15)
    await agent.connect()
    
    # Test complex query that requires multiple tool calls
    complex_query = """
    I need a comprehensive project analysis. Please:
    1. First, show me all projects in the database
    2. Then find the project with the highest budget
    3. Get detailed information about that project's tasks
    4. Calculate the total estimated time for all tasks in that project
    5. Find all team members assigned to tasks in that project
    6. Provide a summary with recommendations
    """
    
    print("Starting complex multi-step analysis...")
    print("="*50)
    
    try:
        result = await agent.run(complex_query)
        print("\nFinal Result:")
        print("-" * 30)
        print(result)
        
        # Show agent performance statistics
        stats = agent.get_stats()
        print("\n" + "="*50)
        print("AGENT PERFORMANCE STATISTICS")
        print("="*50)
        print(f"Total Queries: {stats['total_queries']}")
        print(f"Total Iterations: {stats['total_iterations']}")
        print(f"Total Tool Calls: {stats['total_tool_calls']}")
        print(f"Average Iterations per Query: {stats['avg_iterations_per_query']}")
        print(f"Max Iterations Reached: {stats['max_iterations_reached']}")
        
    except Exception as e:
        print(f"Error during analysis: {e}")
    
    await agent.disconnect()

# Example of how the iterative process works:
"""
ITERATIVE TOOL CALLING FLOW:
============================

Query: "Find the highest budget project and analyze its tasks"

Iteration 1:
- LLM decides to call list_all_projects tool
- Tool returns: [Project A: $10k, Project B: $25k, Project C: $15k]

Iteration 2: 
- LLM analyzes results and identifies Project B as highest budget
- LLM calls get_project_details tool with Project B ID
- Tool returns: Project B details with task IDs

Iteration 3:
- LLM calls get_project_tasks tool with Project B ID  
- Tool returns: List of tasks for Project B

Iteration 4:
- LLM analyzes task data and calls additional tools if needed
- Or provides final analysis if sufficient data gathered

This continues until LLM determines the task is complete (no more tool calls)
or max_iterations is reached.
"""

if __name__ == "__main__":
    asyncio.run(main())
