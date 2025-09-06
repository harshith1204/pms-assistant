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

MAX_TOOL_OUTPUT_CHARS = 1500
MAX_TOOL_OUTPUT_ITEMS = 10

def _summarize_tool_output(result: Any, max_chars: int = MAX_TOOL_OUTPUT_CHARS, max_items: int = MAX_TOOL_OUTPUT_ITEMS) -> str:
    """Summarize potentially large tool output to keep context small and concise."""
    try:
        data = None
        text = None

        if isinstance(result, str):
            text = result
            try:
                data = json.loads(result)
            except Exception:
                data = None
        else:
            data = result

        if data is not None:
            if isinstance(data, list):
                preview = data[:max_items]
                summary_obj = {
                    "preview": preview,
                    "total_items": len(data),
                    "truncated": len(data) > max_items
                }
                text = json.dumps(summary_obj, ensure_ascii=False)
            elif isinstance(data, dict):
                # If dict has a large list under common keys, truncate it
                truncated_text = None
                for key in ["results", "items", "data"]:
                    if key in data and isinstance(data[key], list) and len(data[key]) > max_items:
                        summary_obj = dict(data)
                        summary_obj[key] = data[key][:max_items]
                        summary_obj[f"{key}_total_items"] = len(data[key])
                        summary_obj[f"{key}_truncated"] = True
                        truncated_text = json.dumps(summary_obj, ensure_ascii=False)
                        break
                text = truncated_text or json.dumps(data, ensure_ascii=False)
            else:
                text = json.dumps(data, ensure_ascii=False)

        if text is None:
            text = str(result)
    except Exception:
        text = str(result)

    if len(text) > max_chars:
        return text[:max_chars] + f"... [truncated {len(text)-max_chars} chars]"
    return text

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
        if len(messages) <= 6:  # Return all if small conversation
            return messages
        else:
            # Return last 10 messages to keep context manageable
            return messages[-6:]

# Global conversation memory instance
conversation_memory = ConversationMemory()

# Initialize the LLM with optimized settings for tool calling
llm = ChatOllama(
    model="qwen3:0.6b-fp16",
    temperature=0.2,  # Tighter, more deterministic outputs
    num_ctx=4096,
    num_predict=1024,  # Reduce mid-sentence cutoffs
    num_thread=8,
    streaming=True,
    verbose=False,  # Reduce unnecessary verbosity
    top_p=0.8,
    top_k=25,
)

# Enhanced system prompt for better multi-step planning recognition
system_prompt = """
You are a Project Management System Assistant with advanced MongoDB querying capabilities.

IMPORTANT: For complex queries that require data from multiple collections or involve relationships between different entities, ALWAYS use the 'execute_multi_collection_plan' tool. This tool allows you to:

- Query cycles and then aggregate work items within those cycles
- Find projects and then get work item counts per project
- Perform cross-collection analyses and aggregations
- Handle queries like "work items in cycles", "projects and their tasks", etc.

Examples of queries that should use execute_multi_collection_plan:
- "How many active work items within cycles?"
- "Work items breakdown by project"
- "Find projects and count their work items"
- "Get cycle details and work item counts"

When using execute_multi_collection_plan, provide a JSON array of steps where each step has:
- "op": "find" or "aggregate"
- "collection": the collection name
- "args": the operation arguments

For simple single-collection queries, use the individual collection tools (query_project, aggregate_work_item, etc.).

RESPONSE STYLE:
- Be concise and direct. Prefer short paragraphs or bullet points.
- Default to summaries over raw data. If results are long, show top 10 items and totals.
- Keep answers under ~150 words unless asked to elaborate.
- Do not repeat yourself. Stop when the question is answered.
- Do not include raw JSON longer than 1500 characters; summarize instead.
"""

# Bind tools to the LLM for tool calling with enhanced prompt
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
        if not token:
            return
        # Drop overly verbose whitespace-only tokens
        if token.strip() == "":
            return
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
        from langchain_core.messages import SystemMessage
        self.llm_with_tools = llm_with_tools
        self.system_message = SystemMessage(content=system_prompt)
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

    def _analyze_query_complexity(self, query: str) -> bool:
        """Analyze if a query requires multi-step planning"""
        query_lower = query.lower()

        # Patterns that indicate multi-step queries
        multi_step_indicators = [
            # Cross-collection queries
            "in cycles", "within cycles", "across projects", "by project",
            "work items in", "tasks in", "items within",

            # Multiple operations
            "find.*and.*count", "get.*and.*aggregate",
            "projects.*work items", "cycles.*work items",

            # Complex aggregations
            "breakdown by", "distribution of", "summary of",
            "group by", "aggregate by",

            # Comparative queries
            "compare", "versus", "vs", "between"
        ]

        return any(indicator in query_lower for indicator in multi_step_indicators)

    def _generate_multi_step_plan(self, query: str) -> dict:
        """Generate a multi-step plan based on query analysis"""
        query_lower = query.lower()

        if "active work items" in query_lower and "cycles" in query_lower:
            return {
                "plan_json": [
                    {
                        "op": "find",
                        "collection": "cycle",
                        "args": {"filter": {"status": "ACTIVE"}, "limit": 20}
                    },
                    {
                        "op": "aggregate",
                        "collection": "workItem",
                        "args": {
                            "pipeline": [
                                {"$match": {"status": {"$in": ["IN_PROGRESS", "TODO", "OPEN", "ACTIVE"]}}},
                                {"$group": {"_id": "$cycle.name", "count": {"$sum": 1}}},
                                {"$sort": {"count": -1}}
                            ]
                        }
                    }
                ]
            }

        elif "work items by project" in query_lower:
            return {
                "plan_json": [
                    {
                        "op": "find",
                        "collection": "project",
                        "args": {"filter": {}, "limit": 50}
                    },
                    {
                        "op": "aggregate",
                        "collection": "workItem",
                        "args": {
                            "pipeline": [
                                {"$group": {"_id": "$project.name", "count": {"$sum": 1}}},
                                {"$sort": {"count": -1}}
                            ]
                        }
                    }
                ]
            }

        # Default fallback
        return None

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

            # Check if query requires multi-step planning
            if self._analyze_query_complexity(query):
                plan = self._generate_multi_step_plan(query)
                if plan:
                    # Use multi-step planning tool directly
                    multi_step_tool = next((t for t in tools_list if t.name == "execute_multi_collection_plan"), None)
                    if multi_step_tool:
                        try:
                            result = await multi_step_tool.ainvoke(plan)
                            return f"📊 MULTI-STEP ANALYSIS RESULTS:\n{result}"
                        except Exception as e:
                            # Fall back to normal processing if multi-step fails
                            pass

            # Add current user message
            human_message = HumanMessage(content=query)
            messages = [self.system_message] + conversation_context + [human_message]

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
                        summarized = _summarize_tool_output(result)
                        tool_message = ToolMessage(
                            content=summarized,
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

            # Get conversation history
            conversation_context = conversation_memory.get_recent_context(conversation_id)

            # Add current user message
            human_message = HumanMessage(content=query)
            messages = [self.system_message] + conversation_context + [human_message]

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
                        summarized = _summarize_tool_output(result)
                        await callback_handler.on_tool_end(summarized)

                        tool_message = ToolMessage(
                            content=summarized,
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

# ProjectManagement Insights Examples
async def main():
    """Example usage of the ProjectManagement Insights Agent"""
    agent = MongoDBAgent()
    await agent.connect()


if __name__ == "__main__":
    asyncio.run(main())
