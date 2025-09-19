from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
import json
import asyncio
from typing import Dict, Any, List, AsyncGenerator, Optional
from pydantic import BaseModel
from datetime import datetime
import time
from collections import defaultdict, deque
from tools import intelligent_query as intelligent_query_tool

from constants import DATABASE_NAME, mongodb_tools

DEFAULT_SYSTEM_PROMPT = (
    "You are a planning and tool-using agent for a Project Management System."
    " Break complex requests into sequential steps and decide next actions based on tool results."
    " Call tools to gather data, transform it, and iterate until the goal is met."
    " Only produce the final answer when you have gathered enough evidence."
    "\n\nTOOL SELECTION GUIDANCE:"
    "\n• Natural language queries: Prefer intelligent_query. It plans cross-collection joins using the"
    " relationship registry and executes the optimal MongoDB aggregation pipeline."
    "\n• Data safety: Use only allow-listed fields and relations from the registry. Avoid projecting or"
    " filtering on fields outside the allow-list."
    "\n\nCOLLECTION NAMES: project, workItem, cycle, members, page, module, projectState."
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

class MongoDBAgent:
    """Simple context-aware agent that forwards queries to the MongoDB tool.

    Behavior:
    - Maintains conversation context per conversation_id.
    - By default, forwards the user's query directly to the `intelligent_query` tool.
    - If the query depends on prior context (pronouns/ellipses with no entity nouns),
      it synthesizes a precise follow-up by referencing the last relevant user message.
    """

    def __init__(self, max_steps: int = 8, system_prompt: Optional[str] = DEFAULT_SYSTEM_PROMPT):
        self.connected = False
        self.system_prompt = system_prompt
        # max_steps retained for interface compatibility; unused in simple agent
        self.max_steps = max_steps

    def _depends_on_context(self, query: str) -> bool:
        """Heuristic: returns True if the query likely depends on previous context."""
        if not query:
            return False
        ql = query.strip().lower()
        pronouns = [
            "it", "this", "that", "those", "these", "them", "the same",
            "based on above", "as before", "like earlier", "as earlier",
            "those ones", "that one"
        ]
        has_pronoun = any(p in ql for p in pronouns)
        entity_keywords = [
            "workitem", "work item", "project", "cycle", "module",
            "member", "members", "page", "projectstate", "project state",
            "bug", "task", "issue"
        ]
        mentions_entity = any(k in ql for k in entity_keywords)
        # Depend on context if pronouns present and no explicit entity terms
        return has_pronoun and not mentions_entity

    def _build_contextual_query(self, query: str, conversation_id: str) -> str:
        """Construct a precise follow-up by referencing the last user message with entity context."""
        history = conversation_memory.get_conversation_history(conversation_id)
        # Find the last HumanMessage before the current one
        last_context: Optional[str] = None
        for msg in reversed(history[:-1] if history else []):
            if isinstance(msg, HumanMessage) and isinstance(msg.content, str) and msg.content.strip():
                last_context = msg.content.strip()
                break
        if last_context:
            return f"Follow-up to previous: {last_context}\nNow: {query}"
        return query

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
        """Run the simple agent: forward the query (with minimal context if needed) to the tool."""
        if not self.connected:
            await self.connect()

        try:
            if not conversation_id:
                conversation_id = f"conv_{int(time.time())}"

            # Persist the human message first
            human_message = HumanMessage(content=query)
            conversation_memory.add_message(conversation_id, human_message)

            final_query = query
            if self._depends_on_context(query):
                final_query = self._build_contextual_query(query, conversation_id)

            # Execute the intelligent query tool directly
            result = await intelligent_query_tool.ainvoke({"query": final_query})

            # Persist assistant response
            ai_message = AIMessage(content=str(result))
            conversation_memory.add_message(conversation_id, ai_message)
            return str(result)

        except Exception as e:
            return f"Error running agent: {str(e)}"

    async def run_streaming(self, query: str, websocket=None, conversation_id: Optional[str] = None) -> AsyncGenerator[str, None]:
        """Run the simple agent with optional streaming via websocket events.

        Emits a single content chunk (no token-level streaming) and optional tool_start/tool_end events.
        """
        if not self.connected:
            await self.connect()

        try:
            if not conversation_id:
                conversation_id = f"conv_{int(time.time())}"

            # Persist the human message
            human_message = HumanMessage(content=query)
            conversation_memory.add_message(conversation_id, human_message)

            final_query = query
            if self._depends_on_context(query):
                final_query = self._build_contextual_query(query, conversation_id)

            # Send tool_start
            if websocket:
                await websocket.send_json({
                    "type": "tool_start",
                    "tool_name": "intelligent_query",
                    "input": json.dumps({"query": final_query}),
                    "timestamp": datetime.now().isoformat()
                })

            # Execute tool
            result = await intelligent_query_tool.ainvoke({"query": final_query})

            # Send tool_end
            if websocket:
                await websocket.send_json({
                    "type": "tool_end",
                    "output": str(result),
                    "timestamp": datetime.now().isoformat()
                })

            # Persist assistant message and yield
            ai_message = AIMessage(content=str(result))
            conversation_memory.add_message(conversation_id, ai_message)
            yield str(result)
            return

        except Exception as e:
            err = f"Error running streaming agent: {str(e)}"
            if websocket:
                await websocket.send_json({
                    "type": "error",
                    "message": err,
                    "timestamp": datetime.now().isoformat()
                })
            yield err

# ProjectManagement Insights Examples
async def main():
    """Example usage of the ProjectManagement Insights Agent"""
    agent = MongoDBAgent()
    await agent.connect()


if __name__ == "__main__":
    asyncio.run(main())
