"""
Smart Filter Agent - Combines RAG retrieval with MongoDB queries for intelligent work item filtering
"""

import json
import asyncio
import contextlib
from typing import List, Dict, Any, Optional, Set, AsyncGenerator
from dataclasses import dataclass
from datetime import datetime

from qdrant.retrieval import ChunkAwareRetriever
from mongo.constants import mongodb_tools, DATABASE_NAME
from mongo.registry import build_lookup_stage, REL
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, AIMessage
from .tools import smart_filter_tools
# Import the actual tools that are available
from tools import mongo_query, rag_search
# Orchestration utilities
from orchestrator import Orchestrator, StepSpec, as_async

import os
from dotenv import load_dotenv
load_dotenv()

groq_api_key = os.getenv("GROQ_API_KEY")
if not groq_api_key:
    raise ValueError("FATAL: GROQ_API_KEY environment variable not set.")



@dataclass
class SmartFilterResult:
    """Result from smart filtering operation"""
    work_items: List[Dict[str, Any]]
    total_count: int
    query: str
    rag_context: str
    mongo_query: Dict[str, Any]

DEFAULT_SYSTEM_PROMPT = (
"You are an intelligent query-routing agent that decides which tool to use for each user query.\n"
"Your job is to select exactly one of the following tools for every request:\n"

"Tools:\n"

"mongo_query – Use this when the query involves structured, filterable data.\n"
"Examples include queries that specify attributes such as priority, state, assignee, project, module, date, cycle, or label,\n"
"or that request lists, counts, metrics, or tabular data.\n"
"Examples:\n"

"Show all high-priority bugs assigned to John.\n"

"List completed tasks from last week.\n"

"rag_search – Use this when the query is open-ended, descriptive, or conceptual, requiring semantic understanding, summaries, reasoning, or explanations.\n"
"Examples:\n"

"Summarize recent login crash reports.\n"

"What's blocking the Alpha release?\n"

"Routing Rules:\n"

"Always choose exactly one tool. Never choose both.\n"

"Prefer mongo_query whenever structured filters or data attributes are explicitly mentioned.\n"

"Use rag_search for vague, narrative, or reasoning-based requests.\n"

"Output only the tool call in the correct format — never provide a direct answer.\n"

"Goal:\n"
"Determine the user's intent precisely and route the query deterministically to the appropriate tool."
)

class SmartFilterAgent:
    """Agent that combines RAG retrieval with MongoDB queries for intelligent work item filtering"""

    def __init__(self, max_steps: int = 2, system_prompt: Optional[str] = DEFAULT_SYSTEM_PROMPT):
        self.llm = ChatGroq(
            model="openai/gpt-oss-120b",
            temperature=0.1,  # Slightly creative for query understanding
            max_tokens=1024,
            top_p=0.8,
        )
        self.connected = False
        self.max_steps = max_steps
        self.system_prompt = system_prompt
        from qdrant.initializer import RAGTool
        from mongo.constants import QDRANT_COLLECTION_NAME
        try:
            self.rag_tool = RAGTool.get_instance()
            self.collection_name = QDRANT_COLLECTION_NAME
            self.retriever = ChunkAwareRetriever(
                qdrant_client=self.rag_tool.qdrant_client,
                embedding_model=self.rag_tool.embedding_model
            )
        except Exception:
            # RAG initialization failed - disable RAG functionality
            self.rag_tool = None
            self.collection_name = "workItem"
            self.retriever = None
        
        # Define the tools with proper names
        self.tools = [
            mongo_query,
            rag_search
        ]
    
    async def _execute_single_tool(
        self, 
        tool_call: Dict[str, Any], 
        tracer=None
    ) -> tuple[ToolMessage, bool]:
        """Execute a single tool.
        
        Returns:
            tuple: (ToolMessage, success_flag)
        """
        try:
            # Find the tool by name
            actual_tool = next((t for t in self.tools if t.name == tool_call["name"]), None)
            if not actual_tool:
                error_msg = ToolMessage(
                    content=f"Tool '{tool_call['name']}' not found.",
                    tool_call_id=tool_call["id"],
                )
                return error_msg, False

            # Execute the tool with the provided arguments
            result = await actual_tool.ainvoke(tool_call["args"])
                        
            tool_message = ToolMessage(
                content=str(result),
                tool_call_id=tool_call["id"],
            )
            return tool_message, True
            
        except Exception as tool_exc:
            error_msg = ToolMessage(
                content=f"Tool execution error: {tool_exc}",
                tool_call_id=tool_call["id"],
            )
            return error_msg, False

    async def connect(self):
        """Connect to MongoDB MCP server"""
        try:
            await mongodb_tools.connect()
            self.connected = True
            print("Smart Filter Agent connected successfully!")
        except Exception as e:
            raise Exception(f"Failed to connect: {str(e)}")

    async def disconnect(self):
        """Disconnect from MongoDB MCP server"""
        try:
            await mongodb_tools.disconnect()
            self.connected = False
        except Exception:
            pass


    async def run_streaming(self, query: str, websocket=None, conversation_id: Optional[str] = None) -> AsyncGenerator[str, None]:
        """Run the agent with streaming support"""
        if not self.connected:
            await self.connect()

        try:
            # Create the tools list with proper function objects
            available_tools = self.tools
            
            # Bind tools to LLM
            llm_with_tools = self.llm.bind_tools(available_tools)

            # Get initial response from LLM
            response = await llm_with_tools.ainvoke([
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=query)
            ])

            # Execute any tool calls
            if hasattr(response, "tool_calls") and response.tool_calls:
                # Create a clean version of the response for messages
                clean_response = AIMessage(
                    content="",  # Clear content for clean message handling
                    tool_calls=response.tool_calls,  # Keep tool calls for execution
                )
                
                # Generate action statement for user
                action_text = f"🔍 Processing your request..."
                yield action_text
                
                # Execute each tool call one at a time
                tool_results = []
                for tool_call in response.tool_calls:
                    tool_message, success = await self._execute_single_tool(tool_call)
                    tool_results.append(tool_message)
                    
                    if success:
                        yield f"✅ Tool '{tool_call['name']}' executed successfully"
                    else:
                        yield f"❌ Tool '{tool_call['name']}' failed: {tool_message.content}"
                
                # Provide final response with tool results
                if tool_results:
                    final_content = "📋 Tool Results:\n\n"
                    for i, tool_result in enumerate(tool_results, 1):
                        final_content += f"{i}. {tool_result.content}\n\n"
                    
                    # Send final response
                    final_response = AIMessage(content=final_content)
                    yield final_content
                else:
                    yield "❌ No tool results available"
            else:
                # No tool calls - direct response from LLM
                yield response.content if hasattr(response, "content") else "No response from agent"

        except Exception as e:
            yield f"Error running streaming agent: {str(e)}"
        finally:
            # Clean up resources if needed
            pass

# ProjectManagement Insights Examples
async def main():
    """Example usage of the Work Item filtering Agent"""
    agent = SmartFilterAgent()
    await agent.connect()
    await agent.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
