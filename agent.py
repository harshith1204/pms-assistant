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
from motor.motor_asyncio import AsyncIOMotorClient

tools_list = tools.tools
from constants import DATABASE_NAME, mongodb_tools, MONGODB_CONNECTION_STRING

DEFAULT_SYSTEM_PROMPT = (
    "You are a planning and tool-using agent for a Project Management System. For complex requests, break the task into"
    " sequential steps. Decide what to do next based on previous tool results."
    " Call tools as needed to gather data, transform it, and iterate until the goal is met."
    " Only produce the final answer when you have gathered enough evidence."
    "\n\nTOOL SELECTION GUIDANCE:"
    "\n• For complex queries: Use intelligent_query as fallback"
)

class ConversationMemory:
    """Enhanced conversation memory with smart context management and persistence"""

    def __init__(self, max_messages_per_conversation: int = 100, mongodb_client: Optional[AsyncIOMotorClient] = None):
        self.conversations: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_messages_per_conversation))
        self.max_messages_per_conversation = max_messages_per_conversation
        self.mongodb_client = mongodb_client
        self.db = None
        self.conversations_collection = None
        self.messages_collection = None
        
        if mongodb_client:
            self.db = mongodb_client[DATABASE_NAME]
            self.conversations_collection = self.db["conversations"]
            self.messages_collection = self.db["messages"]

    def estimate_tokens(self, message: BaseMessage) -> int:
        """Estimate tokens in a message (rough approximation: 1 token ≈ 4 characters)"""
        content = ""
        if isinstance(message, (HumanMessage, AIMessage, SystemMessage)):
            content = str(message.content)
        elif isinstance(message, ToolMessage):
            content = str(message.content)
        
        # Rough token estimation
        return len(content) // 4

    def add_message(self, conversation_id: str, message: BaseMessage):
        """Add a message to the conversation history"""
        self.conversations[conversation_id].append(message)

    async def persist_message(self, conversation_id: str, message: BaseMessage, metadata: Optional[Dict] = None):
        """Persist a message to MongoDB for long-term storage"""
        if not self.messages_collection:
            return
        
        try:
            message_doc = {
                "conversation_id": conversation_id,
                "timestamp": datetime.now(),
                "type": message.__class__.__name__,
                "content": str(message.content),
                "metadata": metadata or {}
            }
            
            # Add tool-specific fields
            if isinstance(message, ToolMessage):
                message_doc["tool_call_id"] = getattr(message, "tool_call_id", None)
            
            await self.messages_collection.insert_one(message_doc)
        except Exception as e:
            print(f"Error persisting message: {e}")

    async def persist_conversation_metadata(self, conversation_id: str, title: str = None, summary: str = None):
        """Update or create conversation metadata"""
        if not self.conversations_collection:
            return
        
        try:
            update_doc = {
                "$set": {
                    "updated_at": datetime.now(),
                },
                "$setOnInsert": {
                    "conversation_id": conversation_id,
                    "created_at": datetime.now(),
                }
            }
            
            if title:
                update_doc["$set"]["title"] = title
            if summary:
                update_doc["$set"]["summary"] = summary
            
            await self.conversations_collection.update_one(
                {"conversation_id": conversation_id},
                update_doc,
                upsert=True
            )
        except Exception as e:
            print(f"Error persisting conversation metadata: {e}")

    async def load_conversation_from_db(self, conversation_id: str, limit: int = 50) -> List[BaseMessage]:
        """Load conversation history from MongoDB"""
        if not self.messages_collection:
            return []
        
        try:
            messages_cursor = self.messages_collection.find(
                {"conversation_id": conversation_id}
            ).sort("timestamp", 1).limit(limit)
            
            loaded_messages = []
            async for msg_doc in messages_cursor:
                msg_type = msg_doc.get("type")
                content = msg_doc.get("content", "")
                
                if msg_type == "HumanMessage":
                    loaded_messages.append(HumanMessage(content=content))
                elif msg_type == "AIMessage":
                    loaded_messages.append(AIMessage(content=content))
                elif msg_type == "SystemMessage":
                    loaded_messages.append(SystemMessage(content=content))
                elif msg_type == "ToolMessage":
                    loaded_messages.append(ToolMessage(
                        content=content,
                        tool_call_id=msg_doc.get("tool_call_id", "")
                    ))
            
            return loaded_messages
        except Exception as e:
            print(f"Error loading conversation from DB: {e}")
            return []

    async def get_all_conversations(self, limit: int = 50) -> List[Dict]:
        """Get all conversation metadata for sidebar"""
        if not self.conversations_collection:
            return []
        
        try:
            conversations_cursor = self.conversations_collection.find().sort("updated_at", -1).limit(limit)
            conversations = []
            async for conv in conversations_cursor:
                conversations.append({
                    "id": conv.get("conversation_id"),
                    "title": conv.get("title", "New Conversation"),
                    "summary": conv.get("summary", ""),
                    "created_at": conv.get("created_at"),
                    "updated_at": conv.get("updated_at")
                })
            return conversations
        except Exception as e:
            print(f"Error getting conversations: {e}")
            return []

    def get_conversation_history(self, conversation_id: str) -> List[BaseMessage]:
        """Get the conversation history for a given conversation ID"""
        return list(self.conversations[conversation_id])

    def clear_conversation(self, conversation_id: str):
        """Clear the conversation history for a given conversation ID"""
        if conversation_id in self.conversations:
            self.conversations[conversation_id].clear()

    async def summarize_old_messages(self, messages: List[BaseMessage], llm) -> str:
        """Summarize old messages to compress context"""
        if not messages:
            return ""
        
        # Create a summary prompt
        summary_content = "Previous conversation summary:\n"
        for msg in messages:
            msg_type = "User" if isinstance(msg, HumanMessage) else "Assistant"
            summary_content += f"{msg_type}: {str(msg.content)[:200]}...\n"
        
        try:
            summary_prompt = f"""Summarize this conversation concisely, keeping key facts and context:

{summary_content}

Summary (2-3 sentences):"""
            
            response = await llm.ainvoke([HumanMessage(content=summary_prompt)])
            return response.content
        except Exception as e:
            print(f"Error summarizing messages: {e}")
            return summary_content[:500]  # Fallback to truncated content

    async def get_smart_context(
        self, 
        conversation_id: str, 
        max_tokens: int = 2000,
        llm = None
    ) -> List[BaseMessage]:
        """
        Get optimized conversation context with smart token management.
        
        Strategy:
        1. Always include recent messages (last 6-8)
        2. If context is too large, summarize older messages
        3. Prioritize important messages (tool outputs, errors)
        """
        messages = self.get_conversation_history(conversation_id)
        
        if not messages:
            return []
        
        # Calculate token budget
        recent_message_count = min(8, len(messages))
        recent_messages = messages[-recent_message_count:]
        recent_tokens = sum(self.estimate_tokens(msg) for msg in recent_messages)
        
        # If recent messages fit in budget, return them
        if recent_tokens <= max_tokens:
            return recent_messages
        
        # If we have more messages, we need to be smarter
        if len(messages) > recent_message_count:
            older_messages = messages[:-recent_message_count]
            
            # Summarize older messages if we have an LLM
            if llm and len(older_messages) > 3:
                summary = await self.summarize_old_messages(older_messages, llm)
                summary_msg = SystemMessage(content=f"[Previous conversation summary: {summary}]")
                
                # Return summary + recent messages
                return [summary_msg] + list(recent_messages)
            else:
                # No LLM for summarization, just take most recent that fit
                return list(recent_messages[-6:])
        
        # Truncate recent messages if they're still too long
        token_count = 0
        result = []
        for msg in reversed(recent_messages):
            msg_tokens = self.estimate_tokens(msg)
            if token_count + msg_tokens <= max_tokens:
                result.insert(0, msg)
                token_count += msg_tokens
            else:
                break
        
        return result if result else [recent_messages[-1]]  # At least return the last message

# Initialize MongoDB client for conversation persistence
try:
    mongo_client = AsyncIOMotorClient(MONGODB_CONNECTION_STRING)
    # Global conversation memory instance with MongoDB persistence
    conversation_memory = ConversationMemory(mongodb_client=mongo_client)
    print("Conversation memory initialized with MongoDB persistence")
except Exception as e:
    print(f"Warning: Could not initialize MongoDB for conversation memory: {e}")
    # Fallback to in-memory only
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

            # Load conversation from database if it exists
            db_messages = await conversation_memory.load_conversation_from_db(conversation_id)
            if db_messages:
                for msg in db_messages:
                    conversation_memory.add_message(conversation_id, msg)
            
            # Get smart conversation context with token management
            conversation_context = await conversation_memory.get_smart_context(
                conversation_id, 
                max_tokens=2000,
                llm=llm
            )

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
            await conversation_memory.persist_message(conversation_id, human_message)
            
            # Generate title for first message in conversation
            if len(conversation_memory.get_conversation_history(conversation_id)) == 1:
                # Create a simple title from the first message
                title = query[:50] + "..." if len(query) > 50 else query
                await conversation_memory.persist_conversation_metadata(conversation_id, title=title)

            steps = 0
            last_response: Optional[AIMessage] = None

            while steps < self.max_steps:
                response = await self.llm_with_tools.ainvoke(messages)
                last_response = response

                # Persist assistant message
                conversation_memory.add_message(conversation_id, response)
                await conversation_memory.persist_message(conversation_id, response)

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
                        await conversation_memory.persist_message(conversation_id, error_msg)
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
                    await conversation_memory.persist_message(conversation_id, tool_message)

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

            # Load conversation from database if it exists
            db_messages = await conversation_memory.load_conversation_from_db(conversation_id)
            if db_messages:
                for msg in db_messages:
                    conversation_memory.add_message(conversation_id, msg)
            
            # Get smart conversation context with token management
            conversation_context = await conversation_memory.get_smart_context(
                conversation_id, 
                max_tokens=2000,
                llm=llm
            )

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
            await conversation_memory.persist_message(conversation_id, human_message)
            
            # Generate title for first message in conversation
            if len(conversation_memory.get_conversation_history(conversation_id)) == 1:
                # Create a simple title from the first message
                title = query[:50] + "..." if len(query) > 50 else query
                await conversation_memory.persist_conversation_metadata(conversation_id, title=title)

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
                await conversation_memory.persist_message(conversation_id, response)

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
                        await conversation_memory.persist_message(conversation_id, error_msg)
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
                    await conversation_memory.persist_message(conversation_id, tool_message)

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
