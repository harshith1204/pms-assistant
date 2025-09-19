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
    "You are a planning and tool-using agent for a Project Management System. For complex requests, break the task into"
    " sequential steps. Decide what to do next based on previous tool results."
    " Call tools as needed to gather data, transform it, and iterate until the goal is met."
    " Only produce the final answer when you have gathered enough evidence."
    "\n\nTOOL SELECTION GUIDANCE:"
    "\n• For complex queries: Use intelligent_query as fallback"
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

# Note: We intentionally avoid binding tools to the LLM.
# Tools will be invoked explicitly by routing logic below.

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
    """MongoDB Agent that maintains conversation context and explicitly calls tools when needed"""

    def __init__(self, max_steps: int = 8, system_prompt: Optional[str] = DEFAULT_SYSTEM_PROMPT):
        self.llm = llm
        self.connected = False
        self.max_steps = max_steps
        self.system_prompt = system_prompt

    async def _decide_route(self, query: str, conversation_context: List[BaseMessage]) -> Dict[str, Any]:
        """Use the LLM to decide whether to answer directly (chat) or call the tool.

        Returns a dict like: {"route": "tool"|"chat", "needs_context": bool, "tool_query": str}
        """
        routing_system = (
            "You are a router for a Project Management System assistant. "
            "Decide whether the user's request requires querying the PMS database via the intelligent_query tool, "
            "or can be answered conversationally without tools. "
            "If the tool call depends on earlier conversation context (pronouns, omitted entities), set needs_context=true and produce a concise tool_query that is self-contained. "
            "Otherwise, set needs_context=false and leave tool_query as an empty string or copy of the user query. "
            "Respond ONLY with strict JSON: {\"route\": \"tool|chat\", \"needs_context\": true|false, \"tool_query\": \"...\"}."
        )

        messages: List[BaseMessage] = [SystemMessage(content=routing_system)]
        # Include minimal context (last few messages) to detect dependencies
        messages.extend(conversation_context[-6:] if len(conversation_context) > 6 else conversation_context)
        messages.append(HumanMessage(content=f"User query: {query}\nReturn JSON only."))

        try:
            response: AIMessage = await self.llm.ainvoke(messages)
            content = response.content or ""
            data = json.loads(content)
            # Basic validation
            if not isinstance(data, dict) or "route" not in data:
                raise ValueError("Router returned invalid structure")
            data.setdefault("needs_context", False)
            data.setdefault("tool_query", "")
            return data
        except Exception:
            # Heuristic fallback: route to tool for data-seeking queries
            lowered = query.lower()
            tool_triggers = [
                "show", "list", "count", "how many", "get", "find", "fetch", "overview",
                "work item", "workitems", "task", "project", "cycle", "member", "module"
            ]
            use_tool = any(t in lowered for t in tool_triggers)
            return {"route": "tool" if use_tool else "chat", "needs_context": False, "tool_query": ""}

    async def _build_precise_tool_query(self, user_query: str, conversation_context: List[BaseMessage]) -> str:
        """When the tool call depends on context, ask LLM to craft a concise, self-contained query string."""
        system_msg = (
            "You transform a user's request plus prior conversation into a SINGLE concise, self-contained natural language query "
            "suited for a PMS intelligent query tool. Use explicit entity names (projects, cycles, work items, members, modules), "
            "resolve pronouns, and omit chit-chat. Return ONLY the query text."
        )
        messages: List[BaseMessage] = [SystemMessage(content=system_msg)]
        messages.extend(conversation_context[-8:] if len(conversation_context) > 8 else conversation_context)
        messages.append(HumanMessage(content=f"Build a precise tool query for: {user_query}\nReturn only the query, no extra text."))
        response: AIMessage = await self.llm.ainvoke(messages)
        return (response.content or "").strip()

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
        """Run the agent: maintain conversation context, optionally call tool, otherwise reply directly."""
        if not self.connected:
            await self.connect()

        try:
            if not conversation_id:
                conversation_id = f"conv_{int(time.time())}"

            conversation_context = conversation_memory.get_recent_context(conversation_id)

            # Persist the human message first
            human_message = HumanMessage(content=query)
            conversation_memory.add_message(conversation_id, human_message)

            # Decide route
            route = await self._decide_route(query, conversation_context)
            if route.get("route") == "tool":
                needs_context = bool(route.get("needs_context", False))
                tool_query: str
                if needs_context:
                    tool_query = await self._build_precise_tool_query(query, conversation_context)
                else:
                    # Directly pass the user's query to the tool
                    tool_query = query

                tool = next((t for t in tools_list if t.name == "intelligent_query"), None)
                if not tool:
                    assistant_msg = AIMessage(content="Tool 'intelligent_query' not available.")
                    conversation_memory.add_message(conversation_id, assistant_msg)
                    return assistant_msg.content

                try:
                    result = await tool.ainvoke({"query": tool_query})
                except Exception as tool_exc:
                    result = f"Tool execution error: {tool_exc}"

                assistant_msg = AIMessage(content=str(result))
                conversation_memory.add_message(conversation_id, assistant_msg)
                return assistant_msg.content

            # Route: chat → answer conversationally using system prompt and context
            messages: List[BaseMessage] = []
            if self.system_prompt:
                messages.append(SystemMessage(content=self.system_prompt))
            messages.extend(conversation_context)
            messages.append(human_message)
            response: AIMessage = await self.llm.ainvoke(messages)
            conversation_memory.add_message(conversation_id, response)
            return response.content

        except Exception as e:
            return f"Error running agent: {str(e)}"

    async def run_streaming(self, query: str, websocket=None, conversation_id: Optional[str] = None) -> AsyncGenerator[str, None]:
        """Run the agent with streaming; for tool calls, emit a single chunk after completion."""
        if not self.connected:
            await self.connect()

        try:
            if not conversation_id:
                conversation_id = f"conv_{int(time.time())}"

            conversation_context = conversation_memory.get_recent_context(conversation_id)

            # Persist the human message first
            human_message = HumanMessage(content=query)
            conversation_memory.add_message(conversation_id, human_message)

            callback_handler = ToolCallingCallbackHandler(websocket)

            # Decide route
            route = await self._decide_route(query, conversation_context)
            if route.get("route") == "tool":
                needs_context = bool(route.get("needs_context", False))
                if needs_context:
                    tool_query = await self._build_precise_tool_query(query, conversation_context)
                else:
                    tool_query = query

                tool = next((t for t in tools_list if t.name == "intelligent_query"), None)
                if not tool:
                    msg = "Tool 'intelligent_query' not available."
                    conversation_memory.add_message(conversation_id, AIMessage(content=msg))
                    yield msg
                    return

                await callback_handler.on_tool_start({"name": "intelligent_query"}, json.dumps({"query": tool_query}))
                try:
                    result = await tool.ainvoke({"query": tool_query})
                except Exception as tool_exc:
                    result = f"Tool execution error: {tool_exc}"
                await callback_handler.on_tool_end(str(result))

                assistant_msg = AIMessage(content=str(result))
                conversation_memory.add_message(conversation_id, assistant_msg)
                yield assistant_msg.content
                return

            # Route: chat → stream a single response (token callbacks handled internally if supported)
            messages: List[BaseMessage] = []
            if self.system_prompt:
                messages.append(SystemMessage(content=self.system_prompt))
            messages.extend(conversation_context)
            messages.append(human_message)

            response: AIMessage = await self.llm.ainvoke(
                messages,
                config={"callbacks": [callback_handler]} if callback_handler else None,
            )
            conversation_memory.add_message(conversation_id, response)
            yield response.content
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
