from langchain_groq import ChatGroq
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, BaseMessage, SystemMessage
from langchain_core.callbacks import AsyncCallbackHandler
import asyncio
import contextlib
from typing import Dict, Any, List, AsyncGenerator, Optional
from typing import Tuple
import tools
from datetime import datetime
import time
from collections import defaultdict, deque
import os


import math

# Import tools list
try:
    tools_list = tools.tools
except AttributeError:
    # Fallback: define empty tools list if import fails
    tools_list = []
import os
from langchain_groq import ChatGroq
from mongo.constants import DATABASE_NAME, mongodb_tools
from mongo.conversations import save_assistant_message, save_action_event
from websocket_handler import user_id_global as _ws_member_id, business_id_global as _ws_business_id


DEFAULT_SYSTEM_PROMPT = (
    "You are a precise, non-speculative Project Management assistant.\n\n"
    "GENERAL RULES:\n"
    "- Never guess facts about the database or content. Prefer invoking a tool.\n"
    "- If a tool is appropriate, always call it before answering.\n"
    "- Keep answers concise and structured. If lists are long, summarize and offer to expand.\n"
    "- If tooling is unavailable for the task, state the limitation plainly.\n\n"
    "TOOL EXECUTION STRATEGY:\n"
    "- When tools are INDEPENDENT (can run without each other's results): Call them together in one batch.\n"
    "- When tools are DEPENDENT (one needs another's output): Call them separately in sequence.\n"
    "- Examples of INDEPENDENT: 'Show bug counts AND feature counts' → call both tools together\n"
    "- Examples of DEPENDENT: 'Find bugs by John, THEN search docs about those bugs' → call mongo_query first, wait for results, then call rag_search\n\n"
    "DECISION GUIDE:\n"
    "1) Use 'mongo_query' for structured questions about entities/fields in collections: project, workItem, cycle, module, members, page, projectState, timeline.\n"
    "   - Examples: counts, lists, filters, sort, group by, breakdowns by assignee/state/project/priority/date.\n"
    "   - Use for: 'count bugs by priority', 'list work items by assignee', 'group projects by business', 'show breakdown by state'.\n"
    "   - The query planner automatically determines when complex joins are beneficial and adds strategic relationships only when they improve query performance.\n"
    "   - Do NOT answer from memory; run a query.\n"
    "2) Use 'rag_search' for content-based searches (semantic meaning, not just keywords).\n"
    "   - Returns FULL chunk content (no truncation) for accurate synthesis and formatting.\n"
    "   - Find pages/work items by meaning, analyze content patterns, search documentation.\n"
    "   - Examples: 'find notes about OAuth', 'show API docs', 'content mentioning authentication', 'analyze patterns in descriptions'.\n"
    "   - INTELLIGENT CONTENT TYPE ROUTING: Choose content_type based on query context:\n"
    "     * Questions about 'release', 'documentation', 'notes', 'wiki' → content_type='page'\n"
    "     * Questions about 'work items', 'bugs', 'tasks', 'issues' → content_type='work_item'\n"
    "     * Questions about 'cycle', 'sprint', 'iteration' → content_type='cycle'\n"
    "     * Questions about 'module', 'component', 'feature area' → content_type='module'\n"
    "     * Questions about 'project' → content_type='project'\n"
    "     * Timeline/history questions → use mongo_query on 'timeline' (do not use RAG)\n"
    "     * Ambiguous queries → omit content_type (searches all types) OR call rag_search multiple times with different types\n"
    "3) Use 'generate_content' to CREATE new work items or pages.\n"
    "   - CRITICAL: Content is sent DIRECTLY to frontend, tool returns only '✅ Content generated' or '❌ Error'.\n"
    "   - Do NOT expect content details in the response - they go straight to the user's screen.\n"
    "   - Just acknowledge success: 'The [type] has been generated' or similar.\n"
    "   - Examples: 'create a bug report', 'generate documentation page', 'draft meeting notes'.\n"
    "   - REQUIRED: content_type ('work_item' or 'page'), prompt (user's instruction).\n"
    "   - OPTIONAL: template_title, template_content, context (for pages).\n"
    "4) Use MULTIPLE tools together when question needs different operations.\n"
    "   - Example: 'Show bug counts by priority (mongo_query) and find related documentation (rag_search)'.\n"
    "   - Agent decides tool combination based on query complexity and dependencies.\n\n"
    "TOOL CHEATSHEET:\n"
    "- mongo_query(query:str, show_all:bool=False): Natural-language to Mongo aggregation. Safe fields only. Automatically uses complex joins when beneficial.\n"
    "  REQUIRED: 'query' - natural language description of what MongoDB data you want.\n"
    "- rag_search(query:str, content_type:str|None, group_by:str|None, limit:int=10, show_content:bool=True): Universal RAG search.\n"
    "  REQUIRED: 'query' - semantic search terms.\n"
    "  OPTIONAL: content_type ('page'|'work_item'|'project'|'cycle'|'module'|None for all), group_by (field name), limit, show_content.\n"
    "- generate_content(content_type:str, prompt:str, template_title:str='', template_content:str='', context:dict=None): Generate work items/pages.\n"
    "  REQUIRED: content_type ('work_item'|'page'), prompt (what to generate).\n"
    "  OPTIONAL: template_title, template_content, context.\n"
    "  NOTE: Returns '✅ Content generated' only - full content sent directly to frontend to save tokens.\n\n"
    "CONTENT TYPE ROUTING EXAMPLES:\n"
    "- 'What is the next release about?' → rag_search(query='next release', content_type='page')\n"
    "- 'What are recent work items about?' → rag_search(query='recent work items', content_type='work_item')\n"
    "- 'What is the active cycle about?' → rag_search(query='active cycle', content_type='cycle')\n"
    "- 'What is the CRM module about?' → rag_search(query='CRM module', content_type='module')\n"
    "- 'Find content about authentication' → rag_search(query='authentication', content_type=None)  # searches all types\n"
    "- 'Create a bug for login issue' → generate_content(content_type='work_item', prompt='Bug: login fails on mobile')\n"
    "- 'Generate API docs page' → generate_content(content_type='page', prompt='API documentation for auth endpoints')\n\n"
    "WHEN UNSURE WHICH TOOL:\n"
    "- If the query is ambiguous or entity/field mapping to Mongo is unclear → prefer rag_search first.\n"
    "- Question about structured data (counts, filters, group by, breakdown by assignee/state/priority/project/date) → mongo_query.\n"
    "- Question about content meaning/semantics (find docs, analyze patterns, content search, descriptions) → rag_search.\n"
    "- Request to CREATE/GENERATE new content → generate_content.\n"
    "- Question needs both structured + semantic analysis → use BOTH tools together.\n\n"
    "Respond with tool calls first, then synthesize a concise answer grounded ONLY in tool outputs."
)

class ConversationMemory:
    """Manages conversation history for maintaining context"""

    def __init__(self, max_messages_per_conversation: int = 50):
        self.conversations: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_messages_per_conversation))
        self.max_messages_per_conversation = max_messages_per_conversation
        # Rolling summary per conversation (compact)
        self.summaries: Dict[str, str] = {}
        self.turn_counters: Dict[str, int] = defaultdict(int)

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
        """Get recent conversation context with a token budget and rolling summary."""
        messages = self.get_conversation_history(conversation_id)

        # Approximate token counting (≈4 chars/token)
        def approx_tokens(text: str) -> int:
            try:
                return max(1, math.ceil(len(text) / 4))
            except Exception:
                return len(text) // 4

        budget = max(500, max_tokens)
        used = 0
        selected: List[BaseMessage] = []

        # Walk backwards to select most recent turns under budget
        for msg in reversed(messages):
            content = getattr(msg, "content", "")
            used += approx_tokens(str(content)) + 8
            if used > budget:
                break
            selected.append(msg)

        selected.reverse()

        # Prepend rolling summary if present and within budget
        summary = self.summaries.get(conversation_id)
        if summary:
            stoks = approx_tokens(summary)
            if used + stoks <= budget:
                selected = [SystemMessage(content=f"Conversation summary (condensed):\n{summary}")] + selected

        return selected

    def register_turn(self, conversation_id: str) -> None:
        self.turn_counters[conversation_id] += 1

    def should_update_summary(self, conversation_id: str, every_n_turns: int = 3) -> bool:
        return self.turn_counters[conversation_id] % every_n_turns == 0

    async def update_summary_async(self, conversation_id: str, llm_for_summary) -> None:
        """Update the rolling summary asynchronously to avoid latency in main path."""
        try:
            history = self.get_conversation_history(conversation_id)
            if not history:
                return
            recent = history[-12:]
            prompt = [
                SystemMessage(content=(
                    "Summarize the durable facts, goals, and decisions from the conversation. "
                    "Keep it 6-10 bullets, under 600 tokens. Avoid chit-chat."
                ))
            ] + recent + [HumanMessage(content="Produce condensed summary now.")]
            resp = await llm_for_summary.ainvoke(prompt)
            if getattr(resp, "content", None):
                self.summaries[conversation_id] = str(resp.content)
        except Exception:
            # Best-effort; ignore failures
            pass

# Global conversation memory instance
conversation_memory = ConversationMemory()


# Initialize the LLM with optimized settings for tool calling
llm = ChatGroq(
    model=os.getenv("GROQ_MODEL", "moonshotai/kimi-k2-instruct-0905"),
    temperature=float(os.getenv("GROQ_TEMPERATURE", "0.1")),
    max_tokens=int(os.getenv("GROQ_MAX_TOKENS", "1024")),
    streaming=True,
    verbose=False,
    top_p=0.8,
)


class TTLCache:
    """Simple TTL cache for tool results to reduce repeat latency."""

    def __init__(self, max_items: int = 256, ttl_seconds: int = 900):
        self.store: Dict[str, tuple[float, Any]] = {}
        self.max_items = max_items
        self.ttl = ttl_seconds

    def _evict_if_needed(self):
        if len(self.store) <= self.max_items:
            return
        oldest_key = min(self.store.items(), key=lambda kv: kv[1][0])[0]
        self.store.pop(oldest_key, None)

    def get(self, key: str) -> Optional[Any]:
        rec = self.store.get(key)
        if not rec:
            return None
        ts, value = rec
        if time.time() - ts > self.ttl:
            self.store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        self.store[key] = (time.time(), value)
        self._evict_if_needed()




# Lightweight helper to create natural, user-facing action statements
async def generate_action_statement(user_query: str, tool_calls: List[Dict[str, Any]]) -> str:
    """Generate a concise, user-facing action sentence based on planned tool calls.

    The sentence avoids exposing internal tooling and focuses on intent/benefit.
    """
    try:
        if not tool_calls:
            return "Thinking through your request..."

        # Build a compact description of planned actions
        tool_summaries: List[str] = []
        for tc in tool_calls:
            try:
                name = tc.get("name")
                args = tc.get("args", {}) or {}
            except Exception:
                name, args = "tool", {}

            if name == "mongo_query":
                q = str(args.get("query", "")).strip()
                tool_summaries.append(f"query structured data about: {q}")
            elif name == "rag_search":
                q = str(args.get("query", "")).strip()
                ctype = args.get("content_type")
                if ctype:
                    tool_summaries.append(f"search {ctype} content about: {q}")
                else:
                    tool_summaries.append(f"search all content about: {q}")
            elif name == "generate_content":
                p = str(args.get("prompt", "")).strip()
                ctype = str(args.get("content_type", "content"))
                tool_summaries.append(f"generate a new {ctype} about: {p}")
            else:
                tool_summaries.append("gather relevant information")

        tools_desc = "; and ".join([s for s in tool_summaries if s])

        action_prompt = [
            SystemMessage(content=(
                "You are a helpful project management assistant. "
                "Based on the user's request and your planned actions, generate ONE short, natural sentence "
                "that explains what you're doing next in a friendly, confident tone. "
                "Do NOT mention tools, databases, or technical details. "
                "Focus on intent and user benefit. Keep it under 15 words."
            )),
            HumanMessage(content=(
                f"User asked: '{user_query}'\n"
                f"Planned actions: {tools_desc}\n"
                "Your next step (one sentence):"
            )),
        ]
        llm = ChatGroq(
            model=os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
            temperature=float(os.getenv("GROQ_TEMPERATURE", "0.1")),
            max_tokens=int(os.getenv("GROQ_MAX_TOKENS", "1024")),
            streaming=True,
            verbose=False,
            top_p=0.8,
        )
        # Use the existing model; rely on instruction for brevity
        resp = await llm.ainvoke(action_prompt)
        action_text = str(getattr(resp, "content", "")).strip().strip("\".")
        if not action_text or len(action_text) > 100:
            return "Gathering relevant information for you..."
        return action_text
    except Exception:
        return "Gathering relevant information for you..."

# Simple per-query tool router: restrict RAG unless content/context is requested
_TOOLS_BY_NAME = {getattr(t, "name", str(i)): t for i, t in enumerate(tools_list)}

def _select_tools_for_query(user_query: str):
    """Return tools exposed to the LLM for this query.

    Enhanced policy:
    - Always expose all available tools (mongo_query, rag_search, generate_content).
    - Let the LLM decide routing based on instructions; no keyword gating.
    - Add query analysis hints for complex join decisions.
    """
    allowed_names = ["mongo_query", "rag_search", "generate_content"]
    selected_tools = [tool for name, tool in _TOOLS_BY_NAME.items() if name in allowed_names]
    if not selected_tools and "mongo_query" in _TOOLS_BY_NAME:
        selected_tools = [_TOOLS_BY_NAME["mongo_query"]]
    return selected_tools, allowed_names


class PhoenixCallbackHandler(AsyncCallbackHandler):
    """WebSocket streaming callback handler for Phoenix events + DB logging"""

    def __init__(self, websocket=None, conversation_id: Optional[str] = None):
        super().__init__()
        self.websocket = websocket
        self.conversation_id = conversation_id
        self.start_time = None
        # Tool events are suppressed from frontend to avoid noise in chat UI
        # Internal step counter for lightweight progress (not exposed directly)
        self._step_counter = 0
        # Whether a dynamic, high-level action statement was already emitted for this step
        self._dynamic_action_emitted = False

    def _safe_extract(self, input_str: str) -> dict:
        """Best-effort parse of tool arg string to a dict without raising.

        Avoids revealing internals; used only to craft short, user-facing action text.
        """
        try:
            import json as _json
            if isinstance(input_str, str):
                # Try JSON first
                return _json.loads(input_str)
        except Exception:
            pass
        try:
            import ast as _ast
            if isinstance(input_str, str):
                val = _ast.literal_eval(input_str)
                if isinstance(val, dict):
                    return val
        except Exception:
            pass
        return {}

    async def _emit_action(self, text: str) -> None:
        if not self.websocket:
            # Still log action to DB if possible
            try:
                if self.conversation_id:
                    await save_action_event(
                        self.conversation_id,
                        "action",
                        text,
                        step=self._step_counter + 1,
                        member_id=_ws_member_id,
                        business_id=_ws_business_id,
                    )
            except Exception:
                pass
            return
        self._step_counter += 1
        payload = {
            "type": "agent_action",
            "text": text,
            "step": self._step_counter,
            "timestamp": datetime.now().isoformat(),
        }
        await self.websocket.send_json(payload)
        try:
            if self.conversation_id:
                await save_action_event(
                    self.conversation_id,
                    "action",
                    text,
                    step=self._step_counter,
                    member_id=_ws_member_id,
                    business_id=_ws_business_id,
                )
        except Exception:
            pass

    async def _emit_result(self, text: str) -> None:
        # No-op: disable sending and persisting 'result' events
        return

    async def on_llm_start(self, *args, **kwargs):
        """Called when LLM starts generating"""
        self.start_time = time.time()
        # Reset dynamic action emission flag at the beginning of a reasoning step
        self._dynamic_action_emitted = False
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

    async def on_tool_end(self, output: str, **kwargs):
        """Called when a tool finishes executing.

        Suppressed: We no longer send tool_end events to the frontend socket.
        """
        return

    async def on_tool_start(self, serialized: Dict[str, Any], input_str: str, **kwargs):
        """Called when a tool starts executing.

        Suppressed: We no longer send tool_start events to the frontend socket.
        """
        return

    def cleanup(self):
        """Clean up Phoenix span collector"""
        pass

    async def emit_dynamic_action(self, text: str) -> None:
        """Emit a single, user-facing dynamic action line and mark it as emitted.

        This prevents fallback action emissions inside on_tool_start for the same step.
        """
        try:
            await self._emit_action(text)
        finally:
            # Ensure we don't emit fallback messages during this step
            self._dynamic_action_emitted = True

class MongoDBAgent:
    """MongoDB Agent using Tool Calling with LLM-Controlled Execution
    
    Features:
    - LLM-controlled execution: The LLM decides whether tools should run in parallel
      or sequentially based on dependencies. When the LLM calls multiple tools together,
      they execute in parallel. When tools need sequential execution, the LLM will
      make separate calls.
    - Parallel execution: When the LLM calls multiple independent tools together,
      they execute concurrently using asyncio.gather() for improved performance.
    - Sequential execution: When tools have dependencies, the LLM naturally handles
      this by calling them in separate rounds.
    - Full tracing support: All tool executions (parallel or sequential) are properly traced
      with Phoenix/OpenTelemetry.
    - Conversation memory: Maintains context across multiple turns.
    
    Args:
        max_steps: Maximum number of reasoning steps (default: 8)
        system_prompt: Custom system prompt or None to use default
        enable_parallel_tools: Enable parallel tool execution (default: True)
    """

    def __init__(self, max_steps: int = 8, system_prompt: Optional[str] = DEFAULT_SYSTEM_PROMPT, enable_parallel_tools: bool = True):
        # Base LLM; tools will be bound per-query via router
        self.llm_base = llm
        self.connected = False
        self.max_steps = max_steps
        self.system_prompt = system_prompt
        self.tracing_enabled = False
        self.enable_parallel_tools = enable_parallel_tools

    async def _execute_single_tool(
        self, 
        tool, 
        tool_call: Dict[str, Any], 
        selected_tools: List[Any],
        tracer=None
    ) -> tuple[ToolMessage, bool]:
        """Execute a single tool with tracing support.
        
        Returns:
            tuple: (ToolMessage, success_flag)
        """
        tool_cm = None
        with contextlib.nullcontext() as tool_span:
            # Enforce router: only allow selected tools
            actual_tool = next((t for t in selected_tools if t.name == tool_call["name"]), None)
            if not actual_tool:
                error_msg = ToolMessage(
                    content=f"Tool '{tool_call['name']}' not found.",
                    tool_call_id=tool_call["id"],
                )
                return error_msg, False

            try:
                pass
                
                result = await actual_tool.ainvoke(tool_call["args"])
                
                pass
                        
            except Exception as tool_exc:
                result = f"Tool execution error: {tool_exc}"
                pass

            tool_message = ToolMessage(
                content=str(result),
                tool_call_id=tool_call["id"],
            )
            return tool_message, True

    async def connect(self):
        """Connect to MongoDB MCP server"""
        # Tracing initialization removed - method does not exist
        span = None
        try:
            await mongodb_tools.connect()
            self.connected = True
            if span:
                pass
            print("MongoDB Agent connected successfully!")
        except Exception as e:
            if span:
                pass
            raise
        finally:
            pass

    async def disconnect(self):
        """Disconnect from MongoDB MCP server"""
        await mongodb_tools.disconnect()
        self.connected = False
        # Tracing removed: nothing to clean up
        pass

    async def run(self, query: str, conversation_id: Optional[str] = None) -> str:
        """Run the agent with a query and optional conversation context"""
        if not self.connected:
            await self.connect()

        try:
            tracer = None
            if tracer is not None:
                span_cm = tracer.start_as_current_span(
                    "agent_run",
                    # kind=trace.SpanKind.INTERNAL,  # Tracing removed
                    attributes={
                        "query_preview": query[:80],
                        "query_length": len(query or ""),
                        "database.name": DATABASE_NAME,
                    },
                )
            else:
                span_cm = None

            with (span_cm if span_cm is not None else contextlib.nullcontext()) as run_span:
                pass
                # Use default conversation ID if none provided
                if not conversation_id:
                    conversation_id = f"conv_{int(time.time())}"

                # Get conversation history
                conversation_context = conversation_memory.get_recent_context(conversation_id)

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

                steps = 0
                last_response: Optional[AIMessage] = None
                need_finalization: bool = False

                while steps < self.max_steps:
                    # Choose tools for this query iteration
                    selected_tools, allowed_names = _select_tools_for_query(query)
                    llm_with_tools = self.llm_base.bind_tools(selected_tools)

                    llm_cm = None

                    with (llm_cm if llm_cm is not None else contextlib.nullcontext()) as llm_span:
                        # Record model invocation parameters
                        pass
                # Lightweight routing hint to bias correct tool choice
                routing_instructions = SystemMessage(content=(
                    "PLANNING & ROUTING:\n"
                    "- Break the user request into logical steps.\n"
                    "- For INDEPENDENT operations: Call multiple tools together.\n"
                    "- For DEPENDENT operations: Call tools separately (wait for results before next call).\n\n"
                    "DECISION GUIDE:\n"
                    "1) Use 'mongo_query' for structured questions about entities/fields in collections: project, workItem, cycle, module, members, page, projectState, timeline.\n"
                    "   - Examples: counts, lists, filters, sort, group by, breakdowns by assignee/state/project/priority/date.\n"
                    "   - Use for: 'count bugs by priority', 'list work items by assignee', 'group projects by business', 'show breakdown by state'.\n"
                    "   - The query planner automatically determines when complex joins are beneficial and adds strategic relationships only when they improve query performance.\n"
                    "   - Do NOT answer from memory; run a query.\n"
                    "2) Use 'rag_search' for content-based searches (semantic meaning, not just keywords).\n"
                    "   - Returns FULL chunk content for synthesis - analyze and format the actual content in your response.\n"
                    "   - Find pages/work items by meaning, analyze content patterns, search documentation.\n"
                    "   - Examples: 'find notes about OAuth', 'show API docs', 'content mentioning authentication', 'analyze patterns in descriptions'.\n"
                    "   - SMART CONTENT TYPE SELECTION: Choose appropriate content_type based on query semantics:\n"
                    "     • 'release', 'documentation', 'notes', 'wiki' keywords → content_type='page'\n"
                    "     • 'work items', 'bugs', 'tasks', 'issues' keywords → content_type='work_item'\n"
                    "     • 'cycle', 'sprint', 'iteration' keywords → content_type='cycle'\n"
                    "     • 'module', 'component', 'feature area' keywords → content_type='module'\n"
                    "     • 'project' keyword → content_type='project'\n"
                    "     • Timeline/history questions → use mongo_query on 'timeline' (do not use RAG)\n"
                    "     • Unclear/multi-type query → content_type=None (all) OR multiple rag_search calls\n"
                    "3) Use 'generate_content' to CREATE new work items or pages.\n"
                    "   - CRITICAL: Content sent DIRECTLY to frontend, returns only '✅ Content generated'.\n"
                    "   - Do NOT expect details - just acknowledge success to user.\n"
                    "   - Examples: 'create a bug report', 'generate documentation', 'draft meeting notes'.\n"
                    "   - REQUIRED: content_type ('work_item'|'page'), prompt.\n"
                    "   - OPTIONAL: template_title, template_content, context.\n"
                    "4) Use MULTIPLE tools together when question needs different operations.\n"
                    "   - Example: 'Show bug counts by priority (mongo_query) and find related documentation (rag_search)'.\n"
                    "   - Agent decides tool combination based on query complexity and dependencies.\n\n"
                    "TOOL CHEATSHEET:\n"
                    "- mongo_query(query:str, show_all:bool=False): Natural-language to Mongo aggregation. Safe fields only.\n"
                    "  REQUIRED: 'query' - natural language description of what MongoDB data you want.\n"
                    "- rag_search(query:str, content_type:str|None, group_by:str|None, limit:int=10, show_content:bool=True): Universal RAG search.\n"
                    "  REQUIRED: 'query' - semantic search terms.\n"
                    "  OPTIONAL: content_type ('page'|'work_item'|'project'|'cycle'|'module'|None), group_by (field), limit, show_content.\n"
                    "- generate_content(content_type:str, prompt:str, template_title:str='', template_content:str='', context:dict=None): Generate work items/pages.\n"
                    "  REQUIRED: content_type ('work_item'|'page'), prompt.\n"
                    "  OPTIONAL: template_title, template_content, context.\n"
                    "  NOTE: Returns '✅ Content generated' only - content goes directly to frontend.\n\n"
                    "CONTENT TYPE EXAMPLES:\n"
                    "- 'What is next release about?' → rag_search(query='next release', content_type='page')\n"
                    "- 'Recent work items about auth?' → rag_search(query='recent work items auth', content_type='work_item')\n"
                    "- 'Active cycle details?' → rag_search(query='active cycle', content_type='cycle')\n"
                    "- 'CRM module overview?' → rag_search(query='CRM module', content_type='module')\n"
                    "- 'Create bug for login' → generate_content(content_type='work_item', prompt='Bug: login fails on mobile')\n"
                    "- 'Generate API docs' → generate_content(content_type='page', prompt='API documentation for auth')\n\n"
                    "WHEN UNSURE WHICH TOOL:\n"
                    "- If the query is ambiguous or entity/field mapping to Mongo is unclear → prefer rag_search first.\n"
                    "- Question about structured data (counts, filters, group by, breakdown by assignee/state/priority/project/date) → mongo_query.\n"
                    "- Question about content meaning/semantics (find docs, analyze patterns, content search, descriptions) → rag_search.\n"
                    "- Request to CREATE/GENERATE content → generate_content.\n"
                    "- Question needs both structured + semantic analysis → use BOTH tools together.\n\n"
                    "IMPORTANT: Use valid args: mongo_query needs 'query'; rag_search needs 'query' (optional: content_type, group_by, limit, show_content); generate_content needs content_type + prompt."
                ))
                invoke_messages = messages + [routing_instructions]
                response = await llm_with_tools.ainvoke(invoke_messages)
                if llm_span and getattr(response, "content", None):
                        try:
                            preview = str(response.content)[:500]
                            llm_span.set_attribute('output.value', preview)
                            llm_span.add_event("llm_response", {"preview_len": len(preview)})
                        except Exception:
                            pass
                last_response = response

                # Persist assistant message
                conversation_memory.add_message(conversation_id, response)
                try:
                    await save_assistant_message(
                        conversation_id,
                        getattr(response, "content", "") or "",
                        member_id=_ws_member_id,
                        business_id=_ws_business_id,
                    )
                except Exception as e:
                    print(f"Warning: failed to save assistant message: {e}")

                # If no tools requested, we are done
                if not getattr(response, "tool_calls", None):
                    return response.content

                # Execute requested tools
                # The LLM decides execution order by how it calls tools:
                # - Multiple tools in one response = parallel execution
                # - Sequential needs are handled by the LLM making separate calls
                # Emit a dynamic, user-facing action line before running any tools
                try:
                    action_text = await generate_action_statement(query, response.tool_calls)
                    try:
                        await save_action_event(
                            conversation_id,
                            "action",
                            action_text,
                            member_id=_ws_member_id,
                            business_id=_ws_business_id,
                        )
                    except Exception:
                        pass
                except Exception:
                    pass
                messages.append(response)
                did_any_tool = False
                
                # Log execution info
                tool_names = [tc["name"] for tc in response.tool_calls]
                execution_mode = "PARALLEL" if len(response.tool_calls) > 1 else "SINGLE"
                print(f"🔧 Executing {len(response.tool_calls)} tool(s) ({execution_mode}): {tool_names}")
                
                if self.enable_parallel_tools and len(response.tool_calls) > 1:
                    # Multiple tools called together = LLM determined they're independent
                    pass
                    
                    tool_tasks = [
                        self._execute_single_tool(None, tool_call, selected_tools, None)
                        for tool_call in response.tool_calls
                    ]
                    tool_results = await asyncio.gather(*tool_tasks)
                    
                    # Process results in order
                    for tool_message, success in tool_results:
                        messages.append(tool_message)
                        conversation_memory.add_message(conversation_id, tool_message)
                        # Skip saving 'result' events to DB
                        if success:
                            did_any_tool = True
                else:
                    # Single tool or parallel disabled
                    for tool_call in response.tool_calls:
                        tool_message, success = await self._execute_single_tool(None, tool_call, selected_tools, None)
                        messages.append(tool_message)
                        conversation_memory.add_message(conversation_id, tool_message)
                        # Skip saving 'result' events to DB
                        if success:
                            did_any_tool = True
                
                steps += 1

                # After executing any tools, force the next LLM turn to synthesize
                if did_any_tool:
                    need_finalization = True
                else:
                    # If no tools were executed, return the latest response
                    if last_response is not None:
                        pass
                        return last_response.content

            # If we exit the loop due to step cap, return the best available answer
            if last_response is not None:
                # Register turn and update summary if needed
                conversation_memory.register_turn(conversation_id)
                if conversation_memory.should_update_summary(conversation_id, every_n_turns=3):
                    try:
                        asyncio.create_task(
                            conversation_memory.update_summary_async(conversation_id, self.llm_base)
                        )
                    except Exception as e:
                        print(f"Warning: Failed to update summary: {e}")
                return last_response.content
            return "Reached maximum reasoning steps without a final answer."

        except Exception as e:
            return f"Error running agent: {str(e)}"

    async def run_streaming(self, query: str, websocket=None, conversation_id: Optional[str] = None) -> AsyncGenerator[str, None]:
        """Run the agent with streaming support and conversation context"""
        if not self.connected:
            await self.connect()

        try:
            tracer = None
            if tracer is not None:
                span_cm = tracer.start_as_current_span(
                    "agent_run_streaming",
                    # kind=trace.SpanKind.INTERNAL,  # Tracing removed
                    attributes={
                        "query_preview": query[:80],
                        "query_length": len(query or ""),
                        "database.name": DATABASE_NAME,
                    },
                )
            else:
                span_cm = None

            with (span_cm if span_cm is not None else contextlib.nullcontext()):
                # Use default conversation ID if none provided
                if not conversation_id:
                    conversation_id = f"conv_{int(time.time())}"

                # Get conversation history
                conversation_context = conversation_memory.get_recent_context(conversation_id)

                # Build messages with optional system instruction
                messages: List[BaseMessage] = []
                if self.system_prompt:
                    messages.append(SystemMessage(content=self.system_prompt))

                messages.extend(conversation_context)

                # Add current user message
                human_message = HumanMessage(content=query)
                messages.append(human_message)

                callback_handler = PhoenixCallbackHandler(websocket, conversation_id)

                # Persist the human message
                conversation_memory.add_message(conversation_id, human_message)

                steps = 0
                last_response: Optional[AIMessage] = None
                need_finalization: bool = False

                while steps < self.max_steps:
                    # Choose tools for this query iteration
                    selected_tools, allowed_names = _select_tools_for_query(query)
                    llm_with_tools = self.llm_base.bind_tools(selected_tools)
                    llm_cm = None

                    with (llm_cm if llm_cm is not None else contextlib.nullcontext()) as llm_span:
                        pass
                        routing_instructions = SystemMessage(content=(
                            "PLANNING & ROUTING:\n"
                            "- Break the user request into logical steps.\n"
                            "- For INDEPENDENT operations: Call multiple tools together.\n"
                            "- For DEPENDENT operations: Call tools separately (wait for results before next call).\n\n"
                            "DECISION GUIDE:\n"
                            "1) Use 'mongo_query' for structured questions about entities/fields in collections: project, workItem, cycle, module, members, page, projectState.\n"
                            "   - Examples: counts, lists, filters, sort, group by, breakdowns by assignee/state/project/priority/date.\n"
                            "   - Use for: 'count bugs by priority', 'list work items by assignee', 'group projects by business', 'show breakdown by state'.\n"
                            "   - The query planner automatically determines when complex joins are beneficial and adds strategic relationships only when they improve query performance.\n"
                            "   - Do NOT answer from memory; run a query.\n"
                            "2) Use 'rag_search' for content-based searches (semantic meaning, not just keywords).\n"
                            "   - Returns FULL chunk content for synthesis - analyze and format the actual content in your response.\n"
                            "   - Find pages/work items by meaning, analyze content patterns, search documentation.\n"
                            "   - Examples: 'find notes about OAuth', 'show API docs', 'content mentioning authentication', 'analyze patterns in descriptions'.\n"
                            "   - SMART CONTENT TYPE SELECTION: Choose appropriate content_type based on query semantics:\n"
                            "     • 'release', 'documentation', 'notes', 'wiki' keywords → content_type='page'\n"
                            "     • 'work items', 'bugs', 'tasks', 'issues' keywords → content_type='work_item'\n"
                            "     • 'cycle', 'sprint', 'iteration' keywords → content_type='cycle'\n"
                            "     • 'module', 'component', 'feature area' keywords → content_type='module'\n"
                            "     • 'project' keyword → content_type='project'\n"
                            "     • Unclear/multi-type query → content_type=None (all) OR multiple rag_search calls\n"
                            "3) Use 'generate_content' to CREATE new work items or pages.\n"
                            "   - CRITICAL: Content sent DIRECTLY to frontend, returns only '✅ Content generated'.\n"
                            "   - Do NOT expect details - just acknowledge success to user.\n"
                            "   - Examples: 'create a bug report', 'generate documentation', 'draft meeting notes'.\n"
                            "   - REQUIRED: content_type ('work_item'|'page'), prompt.\n"
                            "   - OPTIONAL: template_title, template_content, context.\n"
                            "4) Use MULTIPLE tools together when question needs different operations.\n"
                            "   - Example: 'Show bug counts by priority (mongo_query) and find related documentation (rag_search)'.\n"
                            "   - Agent decides tool combination based on query complexity and dependencies.\n\n"
                            "TOOL CHEATSHEET:\n"
                            "- mongo_query(query:str, show_all:bool=False): Natural-language to Mongo aggregation. Safe fields only.\n"
                            "  REQUIRED: 'query' - natural language description of what MongoDB data you want.\n"
                            "- rag_search(query:str, content_type:str|None, group_by:str|None, limit:int=10, show_content:bool=True): Universal RAG search.\n"
                            "  REQUIRED: 'query' - semantic search terms.\n"
                            "  OPTIONAL: content_type ('page'|'work_item'|'project'|'cycle'|'module'|None), group_by (field), limit, show_content.\n"
                            "- generate_content(content_type:str, prompt:str, template_title:str='', template_content:str='', context:dict=None): Generate work items/pages.\n"
                            "  REQUIRED: content_type ('work_item'|'page'), prompt.\n"
                            "  OPTIONAL: template_title, template_content, context.\n"
                            "  NOTE: Returns '✅ Content generated' only - content goes directly to frontend.\n\n"
                            "CONTENT TYPE EXAMPLES:\n"
                            "- 'What is next release about?' → rag_search(query='next release', content_type='page')\n"
                            "- 'Recent work items about auth?' → rag_search(query='recent work items auth', content_type='work_item')\n"
                            "- 'Active cycle details?' → rag_search(query='active cycle', content_type='cycle')\n"
                            "- 'CRM module overview?' → rag_search(query='CRM module', content_type='module')\n"
                            "- 'Create bug for login' → generate_content(content_type='work_item', prompt='Bug: login fails on mobile')\n"
                            "- 'Generate API docs' → generate_content(content_type='page', prompt='API documentation for auth')\n\n"
                            "WHEN UNSURE WHICH TOOL:\n"
                            "- If the query is ambiguous or entity/field mapping to Mongo is unclear → prefer rag_search first.\n"
                            "- Question about structured data (counts, filters, group by, breakdown by assignee/state/priority/project/date) → mongo_query.\n"
                            "- Question about content meaning/semantics (find docs, analyze patterns, content search, descriptions) → rag_search.\n"
                            "- Request to CREATE/GENERATE content → generate_content.\n"
                            "- Question needs both structured + semantic analysis → use BOTH tools together.\n\n"
                            "IMPORTANT: Use valid args: mongo_query needs 'query'; rag_search needs 'query' (optional: content_type, group_by, limit, show_content); generate_content needs content_type + prompt."
                        ))
                        invoke_messages = messages + [routing_instructions]
                        if need_finalization:
                            finalization_instructions = SystemMessage(content=(
                                "FINALIZATION: Write a concise answer in your own words based on the tool outputs above. "
                                "Do not paste tool outputs verbatim or include banners/emojis. "
                                "If the user asked to browse or see examples, summarize briefly and offer to expand. "
                                "For work items, present canonical fields succinctly."
                            ))
                            # Emit a dynamic action statement to indicate synthesis/finalization
                            try:
                                synth_action = await generate_action_statement(
                                    query,
                                    [{"name": "synthesize", "args": {"query": "finalize answer from gathered findings"}}],
                                )
                                if callback_handler:
                                    await callback_handler.emit_dynamic_action(synth_action)
                            except Exception:
                                pass
                            invoke_messages = messages + [routing_instructions, finalization_instructions]
                            need_finalization = False
                        response = await llm_with_tools.ainvoke(
                            invoke_messages,
                            config={"callbacks": [callback_handler]},
                        )
                        if llm_span and getattr(response, "content", None):
                            try:
                                preview = str(response.content)[:500]
                                llm_span.set_attribute('output.value', preview)
                                llm_span.add_event("llm_response", {"preview_len": len(preview)})
                            except Exception:
                                pass
                    last_response = response

                    # Persist assistant message
                    conversation_memory.add_message(conversation_id, response)
                    try:
                        await save_assistant_message(
                            conversation_id,
                            getattr(response, "content", "") or "",
                            member_id=_ws_member_id,
                            business_id=_ws_business_id,
                        )
                    except Exception as e:
                        print(f"Warning: failed to save assistant message: {e}")

                    if not getattr(response, "tool_calls", None):
                        yield response.content
                        return

                    # Execute requested tools with streaming callbacks
                    # The LLM decides execution order by how it calls tools
                    # Emit a dynamic, user-facing action line before running any tools
                    try:
                        action_text = await generate_action_statement(query, response.tool_calls)
                        if callback_handler:
                            await callback_handler.emit_dynamic_action(action_text)
                    except Exception:
                        pass
                    messages.append(response)
                    did_any_tool = False
                    
                    # Log execution info
                    tool_names = [tc["name"] for tc in response.tool_calls]
                    execution_mode = "PARALLEL" if len(response.tool_calls) > 1 else "SINGLE"
                    print(f"🔧 Executing {len(response.tool_calls)} tool(s) ({execution_mode}): {tool_names}")
                    
                    if self.enable_parallel_tools and len(response.tool_calls) > 1:
                        # Multiple tools called together = LLM determined they're independent
                        # Send tool_start events for all tools first
                        for tool_call in response.tool_calls:
                            tool = next((t for t in selected_tools if t.name == tool_call["name"]), None)
                            if tool:
                                await callback_handler.on_tool_start({"name": tool.name}, str(tool_call["args"]))
                        
                        # Execute all tools in parallel
                        tool_tasks = [self._execute_single_tool(None, tool_call, selected_tools, None) for tool_call in response.tool_calls]
                        tool_results = await asyncio.gather(*tool_tasks)
                        
                        # Process results and send tool_end events
                        for tool_message, success in tool_results:
                            await callback_handler.on_tool_end(tool_message.content)
                            messages.append(tool_message)
                            conversation_memory.add_message(conversation_id, tool_message)
                            # Skip saving 'result' events to DB
                            if success:
                                did_any_tool = True
                    else:
                        # Single tool or parallel disabled
                        for tool_call in response.tool_calls:
                            tool = next((t for t in selected_tools if t.name == tool_call["name"]), None)
                            if tool:
                                await callback_handler.on_tool_start({"name": tool.name}, str(tool_call["args"]))
                            
                            tool_message, success = await self._execute_single_tool(None, tool_call, selected_tools, None)
                            await callback_handler.on_tool_end(tool_message.content)
                            messages.append(tool_message)
                            conversation_memory.add_message(conversation_id, tool_message)
                            # Skip saving 'result' events to DB
                            if success:
                                did_any_tool = True
                    
                    steps += 1

                    # After executing any tools, force the next LLM turn to synthesize
                    if did_any_tool:
                        need_finalization = True

                # Step cap reached; send best available response
                if last_response is not None:
                    # Register turn and update summary if needed
                    conversation_memory.register_turn(conversation_id)
                    if conversation_memory.should_update_summary(conversation_id, every_n_turns=3):
                        try:
                            asyncio.create_task(
                                conversation_memory.update_summary_async(conversation_id, self.llm_base)
                            )
                        except Exception as e:
                            print(f"Warning: Failed to update summary: {e}")
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
    await agent.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
