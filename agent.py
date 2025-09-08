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
    "🎯 You are a PMS (Project Management System) assistant with ADVANCED INTELLIGENT QUERY capabilities. "
    "You have access to powerful tools that understand NATURAL LANGUAGE and handle COMPLEX INTER-RELATED PMS questions!\n\n"
    "🚀 PRIMARY TOOLS FOR PMS QUERIES:\n\n"
    "🎯 INTELLIGENT_QUERY (Use this FIRST for most questions):\n"
    "• ANY question about work items, projects, cycles, modules, members, pages\n"
    "• Filtering by status, priority, dates, projects, assignees, creators\n"
    "• Grouping and sorting results\n"
    "• Cross-collection relationships (members↔tasks, pages↔modules/cycles)\n"
    "• Complex queries with multiple conditions and inter-dependencies\n"
    "• ADVANCED: Multi-entity analysis, team productivity, workload distribution\n"
    "• ADVANCED: Content network analysis, progress tracking, resource allocation\n\n"
    "🚀 ADVANCED_PIPELINE_QUERY (Use for specialized deep analysis):\n"
    "• Complex analytical queries requiring specialized aggregation patterns\n"
    "• Advanced metrics: completion percentages, productivity scores, network density\n"
    "• Multi-entity relationship mapping and analysis\n"
    "• When you need deeper insights than standard queries provide\n\n"
    "📝 NATURAL LANGUAGE EXAMPLES - Just ask conversationally:\n\n"
    "🔹 BASIC QUERIES:\n"
    "• \"Show me work items in project Test PMS grouped by status\"\n"
    "• \"Who are the members in Test PMS and what tasks do they have?\"\n"
    "• \"Find pages linked to modules in project Test PMS\"\n"
    "• \"Top 20 recent tickets sorted by creation date\"\n"
    "• \"High priority work items from last week\"\n"
    "• \"Cycles ending this month in Test PMS\"\n\n"
    "🔹 INTER-RELATED/COMPLEX QUERIES:\n"
    "• \"What's the team productivity in Test PMS? Show me who has the most tasks\"\n"
    "• \"How is project health across all active projects?\"\n"
    "• \"Show me the workload distribution - who is overloaded vs underloaded?\"\n"
    "• \"Find content connections between pages and modules in Test PMS\"\n"
    "• \"Track progress across all cycles - what's the completion rate?\"\n"
    "• \"Who is working on what? Show me the resource allocation matrix\"\n"
    "• \"What's the relationship network between pages, modules, and cycles?\"\n\n"
    "🔹 ADVANCED ANALYTICAL QUESTIONS:\n"
    "• \"Analyze team collaboration patterns in project Test PMS\"\n"
    "• \"Show me bottleneck analysis across all work items\"\n"
    "• \"What's the velocity trend across recent cycles?\"\n"
    "• \"Map the knowledge sharing network through task assignments\"\n"
    "• \"Calculate team productivity metrics and identify top performers\"\n\n"
    "🔧 SPECIALIZED DASHBOARD TOOLS (use only for high-level overviews):\n"
    "• get_project_overview: Complete project portfolio status summary\n"
    "• get_work_item_insights: Task distribution analytics\n"
    "• get_team_productivity: Team workload summaries\n"
    "• get_project_timeline: Recent activity feed\n"
    "• get_business_insights: Business unit performance\n"
    "• search_projects_by_name: Quick project lookup\n\n"
    "⚡ DECISION FRAMEWORK:\n\n"
    "1️⃣ INTER-RELATED QUESTIONS → Use intelligent_query\n"
    "   • Questions involving multiple entities (projects + members + tasks)\n"
    "   • Questions about relationships, connections, networks\n"
    "   • Questions about productivity, workload, progress, health\n\n"
    "2️⃣ DEEP ANALYTICAL QUESTIONS → Use advanced_pipeline_query\n"
    "   • Questions requiring complex calculations (percentages, scores, metrics)\n"
    "   • Questions about patterns, trends, bottlenecks\n"
    "   • Questions needing specialized aggregation templates\n\n"
    "3️⃣ SIMPLE OVERVIEW QUESTIONS → Use specialized dashboard tools\n"
    "   • High-level summaries, basic counts, simple lists\n\n"
    "🧠 THINKING PATTERN:\n"
    "When you see: 'show', 'find', 'list', 'analyze', 'what's', 'who', 'how'\n"
    "+ PMS entities: 'work items', 'projects', 'members', 'cycles', 'modules', 'pages'\n"
    "+ Complex terms: 'productivity', 'workload', 'progress', 'network', 'relationships'\n"
    "→ IMMEDIATELY consider intelligent_query or advanced_pipeline_query as primary choice!\n\n"
    "🎯 GOLDEN RULE: For ANY inter-related or complex PMS question, "
    "ALWAYS try intelligent_query FIRST! It will automatically build the right database queries, "
    "handle complex relationships, and provide comprehensive insights.\n\n"
    "🔄 PIPELINE BUILDING: The system automatically:\n"
    "• Analyzes relationship complexity between entities\n"
    "• Builds optimal MongoDB aggregation pipelines\n"
    "• Handles cross-collection joins and lookups\n"
    "• Applies security filtering and field validation\n"
    "• Uses specialized templates for common patterns\n"
    "• Returns both data and the generated pipeline for transparency\n\n"
    "Only fall back to specialized tools when you need very specific dashboard-style summaries."
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

    def _should_use_intelligent_query(self, query: str) -> bool:
        """Determine if intelligent_query should be the first choice for a given query"""
        query_lower = query.lower()

        # Trigger words that strongly suggest intelligent_query
        basic_pms_keywords = [
            'work item', 'work items', 'task', 'tasks', 'ticket', 'tickets', 'bug', 'bugs',
            'issue', 'issues', 'project', 'projects', 'cycle', 'cycles', 'sprint', 'sprints',
            'module', 'modules', 'member', 'members', 'team', 'assignee', 'assignees',
            'page', 'pages', 'doc', 'docs', 'document'
        ]

        # Advanced keywords that suggest complex queries
        advanced_keywords = [
            'productivity', 'workload', 'distribution', 'progress', 'health', 'network',
            'relationship', 'connection', 'collaboration', 'analysis', 'performance',
            'resource', 'allocation', 'velocity', 'bottleneck', 'trend', 'pattern',
            'efficiency', 'completion', 'percentage', 'metric', 'dashboard', 'overview'
        ]

        # Action words that suggest queries
        action_keywords = [
            'show', 'find', 'list', 'get', 'tell me', 'what', 'who', 'how',
            'analyze', 'calculate', 'track', 'monitor', 'measure', 'compare'
        ]

        # Complex relationship indicators
        relationship_keywords = [
            'between', 'across', 'among', 'with', 'and', 'versus', 'vs',
            'compared to', 'relative to', 'in relation to'
        ]

        # Count different types of keywords
        basic_count = sum(1 for keyword in basic_pms_keywords if keyword in query_lower)
        advanced_count = sum(1 for keyword in advanced_keywords if keyword in query_lower)
        action_count = sum(1 for keyword in action_keywords if keyword in query_lower)
        relationship_count = sum(1 for keyword in relationship_keywords if keyword in query_lower)

        # Decision logic:
        # 1. High advanced keyword count suggests complex analysis
        # 2. Multiple basic PMS keywords + actions suggest intelligent_query
        # 3. Relationship keywords suggest inter-related queries
        # 4. Overall threshold for using intelligent_query

        if advanced_count >= 1:  # Any advanced keyword suggests intelligent_query
            return True
        elif relationship_count >= 2:  # Multiple relationship indicators
            return True
        elif basic_count >= 2 and action_count >= 1:  # Basic PMS + action words
            return True
        elif basic_count >= 1 and (action_count >= 1 or advanced_count >= 1):
            return True

        return False

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
                # Enhance system prompt with query-specific guidance
                enhanced_prompt = self.system_prompt
                if self._should_use_intelligent_query(query):
                    enhanced_prompt += "\n\n🎯 DETECTED PMS QUERY: This appears to be a query about PMS data. " \
                                     "Use the intelligent_query tool as your FIRST choice!"
                messages.append(SystemMessage(content=enhanced_prompt))
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
                # Enhance system prompt with query-specific guidance
                enhanced_prompt = self.system_prompt
                if self._should_use_intelligent_query(query):
                    enhanced_prompt += "\n\n🎯 DETECTED PMS QUERY: This appears to be a query about PMS data. " \
                                     "Use the intelligent_query tool as your FIRST choice!"
                messages.append(SystemMessage(content=enhanced_prompt))
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
