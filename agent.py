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
import uuid
import hashlib

import math
import json
from events import emitter

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
    "1) Use 'mongo_query' for structured questions about entities/fields in collections: project, workItem, cycle, module, members, page, projectState.\n"
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

def _safe_preview(value: Any, max_chars: int = 600) -> str:
    try:
        text = str(value)
        return text[:max_chars]
    except Exception:
        return "<unpreviewable>"

def _summarize_result(result: Any) -> Dict[str, Any]:
    try:
        if isinstance(result, dict):
            return {"type": "dict", "keys": list(result.keys())[:10], "len": len(result)}
        if isinstance(result, (list, tuple)):
            return {"type": type(result).__name__, "len": len(result)}
        if isinstance(result, str):
            return {"type": "str", "len": len(result), "preview": result[:200]}
        return {"type": type(result).__name__}
    except Exception:
        return {"type": "unknown"}

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
        # Tool outputs are now always streamed to the frontend for better visibility
        # Internal step counter for lightweight progress (not exposed directly)
        self._step_counter = 0

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
                    await save_action_event(self.conversation_id, "action", text, step=self._step_counter + 1)
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
                await save_action_event(self.conversation_id, "action", text, step=self._step_counter)
        except Exception:
            pass

    async def _emit_result(self, text: str) -> None:
        if not self.websocket:
            try:
                if self.conversation_id:
                    await save_action_event(self.conversation_id, "result", text, step=self._step_counter)
            except Exception:
                pass
            return
        payload = {
            "type": "agent_result",
            "text": text,
            "step": self._step_counter,
            "timestamp": datetime.now().isoformat(),
        }
        await self.websocket.send_json(payload)
        try:
            if self.conversation_id:
                await save_action_event(self.conversation_id, "result", text, step=self._step_counter)
        except Exception:
            pass

    async def on_llm_start(self, *args, **kwargs):
        """Called when LLM starts generating"""
        self.start_time = time.time()
        if self.websocket:
            await self.websocket.send_json({
                "type": "llm_start",
                "timestamp": datetime.now().isoformat()
            })
            # Non-revealing action line
            await self._emit_action("Reviewing the request to decide next steps")

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
            # Emit dynamic, user-facing action statement (non-revealing)
            args = self._safe_extract(input_str)
            action_text = None
            try:
                if tool_name == "mongo_query":
                    q = str(args.get("query", "")).strip()
                    preview = (q[:80] + "...") if len(q) > 80 else q
                    action_text = (f"Checking structured data to answer“{preview}”" if preview
                                   else "Checking structured data to answer your question")
                elif tool_name == "rag_search":
                    q = str(args.get("query", "")).strip()
                    ctype = str(args.get("content_type", "")).strip()
                    preview = (q[:80] + "...") if len(q) > 80 else q
                    if preview and ctype:
                        action_text = f"Exploring {ctype} content to understand “{preview}”"
                    elif preview:
                        action_text = f"Exploring content to understand “{preview}”"
                    else:
                        action_text = "Exploring relevant content for context"
                else:
                    action_text = f"Preparing to gather information ({tool_name})"
            except Exception:
                action_text = "Preparing to gather information"
            await self._emit_action(action_text)

    async def on_tool_end(self, output: str, **kwargs):
        """Called when a tool finishes executing"""
        # Do not send raw tool outputs to the UI; emit only a concise RESULT line
            # Emit concise result statement without internals
        summary = "Ready with findings"
        try:
            import re as _re
            # Try to extract a simple count from common patterns
            m = _re.search(r"Found\s+(\d+)\s+result", str(output), flags=_re.IGNORECASE)
            if m:
                summary = f"Found {m.group(1)} relevant results"
            elif "RESULTS SUMMARY" in str(output):
                summary = "Summarized key results"
            elif "RESULT:" in str(output) or "RESULTS:" in str(output):
                summary = "Results ready"
        except Exception:
            pass
        await self._emit_result(summary)

    def cleanup(self):
        """Clean up Phoenix span collector"""
        pass

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

            # Emit tool start event
            action_id = f"tool-{int(time.time()*1000)}"
            try:
                await emitter.emit({
                    "type": "agent_action",
                    "action_id": action_id,
                    "phase": "tool_call",
                    "subject": actual_tool.name,
                    "text": f"Calling tool {actual_tool.name}",
                    "action": "call_tool",
                    "meta": {"args": _safe_preview(tool_call.get("args", {}), 600)}
                })
            except Exception:
                pass

            try:
                result = await actual_tool.ainvoke(tool_call["args"])
            except Exception as tool_exc:
                # Emit error event and return failure ToolMessage
                try:
                    await emitter.emit({
                        "type": "agent_error",
                        "action_id": action_id,
                        "phase": "tool_call",
                        "subject": actual_tool.name,
                        "text": str(tool_exc),
                        "action": "call_tool",
                        "meta": {"exception": type(tool_exc).__name__}
                    })
                except Exception:
                    pass
                result = f"Tool execution error: {tool_exc}"
            else:
                try:
                    await emitter.emit({
                        "type": "agent_result",
                        "action_id": action_id,
                        "phase": "tool_call",
                        "subject": actual_tool.name,
                        "text": f"Tool {actual_tool.name} returned",
                        "action": "call_tool",
                        "meta": {"summary": _summarize_result(result)}
                    })
                except Exception:
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
                # Emit LLM call start event
                llm_action = "finalize_answer" if need_finalization else "decide_next_step"
                llm_action_id = f"llm-{int(time.time()*1000)}"
                try:
                    await emitter.emit({
                        "type": "agent_action",
                        "action_id": llm_action_id,
                        "phase": "llm_call",
                        "subject": "LLM",
                        "text": f"LLM call for action '{llm_action}'",
                        "action": llm_action,
                        "meta": {"message_count": len(messages) + 1}
                    })
                except Exception:
                    pass

                response = await llm_with_tools.ainvoke(invoke_messages)

                # Emit LLM call result event
                try:
                    await emitter.emit({
                        "type": "agent_result",
                        "action_id": llm_action_id,
                        "phase": "llm_call",
                        "subject": "LLM",
                        "text": f"LLM returned for action '{llm_action}'",
                        "action": llm_action,
                        "meta": {"response_preview": _safe_preview(getattr(response, "content", ""), 600)}
                    })
                except Exception:
                    pass
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
                    await save_assistant_message(conversation_id, getattr(response, "content", "") or "")
                except Exception as e:
                    print(f"Warning: failed to save assistant message: {e}")

                # If no tools requested, we are done
                if not getattr(response, "tool_calls", None):
                    try:
                        await emitter.emit({
                            "type": "agent_done",
                            "phase": "finish",
                            "subject": "agent",
                            "text": "Agent finished (no tools)",
                            "action": "finish",
                            "meta": {"answer_len": len(str(response.content or ""))}
                        })
                    except Exception:
                        pass
                    return response.content

                # Execute requested tools
                # The LLM decides execution order by how it calls tools:
                # - Multiple tools in one response = parallel execution
                # - Sequential needs are handled by the LLM making separate calls
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
                        try:
                            await save_action_event(conversation_id, "result", tool_message.content)
                        except Exception:
                            pass
                        if success:
                            did_any_tool = True
                else:
                    # Single tool or parallel disabled
                    for tool_call in response.tool_calls:
                        tool_message, success = await self._execute_single_tool(None, tool_call, selected_tools, None)
                        messages.append(tool_message)
                        conversation_memory.add_message(conversation_id, tool_message)
                        try:
                            await save_action_event(conversation_id, "result", tool_message.content)
                        except Exception:
                            pass
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
                        try:
                            await emitter.emit({
                                "type": "agent_done",
                                "phase": "finish",
                                "subject": "agent",
                                "text": "Agent finished (no tool execution)",
                                "action": "finish",
                                "meta": {"answer_len": len(str(last_response.content or ""))}
                            })
                        except Exception:
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
                try:
                    await emitter.emit({
                        "type": "agent_done",
                        "phase": "finish",
                        "subject": "agent",
                        "text": "Agent finished",
                        "action": "finish",
                        "meta": {"answer_len": len(str(last_response.content or ""))}
                    })
                except Exception:
                    pass
                return last_response.content
            return "Reached maximum reasoning steps without a final answer."

        except Exception as e:
            try:
                await emitter.emit({
                    "type": "agent_error",
                    "phase": "run",
                    "subject": "agent",
                    "text": str(e),
                    "action": "run"
                })
            except Exception:
                pass
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

                # Subscribe to forward emitter events to websocket and DB
                async def _forward_emitter_event(ev: Dict[str, Any]):
                    try:
                        if websocket:
                            await websocket.send_json(ev)
                    except Exception:
                        pass
                    # Persist concise log to DB
                    try:
                        if conversation_id:
                            ev_type = str(ev.get("type", "log"))
                            kind_map = {
                                "agent_action": "action",
                                "agent_result": "result",
                                "agent_error": "error",
                                "agent_log": "log",
                                "agent_done": "done",
                            }
                            kind = kind_map.get(ev_type, "log")
                            text = str(ev.get("text", ev_type))
                            await save_action_event(conversation_id, kind, text)
                    except Exception:
                        pass

                emitter.subscribe(_forward_emitter_event)

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
                            invoke_messages = messages + [routing_instructions, finalization_instructions]
                            need_finalization = False
                        # Emit LLM call start event
                        llm_action = "finalize_answer" if need_finalization else "decide_next_step"
                        llm_action_id = f"llm-{int(time.time()*1000)}"
                        try:
                            await emitter.emit({
                                "type": "agent_action",
                                "action_id": llm_action_id,
                                "phase": "llm_call",
                                "subject": "LLM",
                                "text": f"LLM call for action '{llm_action}'",
                                "action": llm_action,
                                "meta": {"message_count": len(messages) + 1}
                            })
                        except Exception:
                            pass

                        response = await llm_with_tools.ainvoke(
                            invoke_messages,
                            config={"callbacks": [callback_handler]},
                        )

                        # Emit LLM call result event
                        try:
                            await emitter.emit({
                                "type": "agent_result",
                                "action_id": llm_action_id,
                                "phase": "llm_call",
                                "subject": "LLM",
                                "text": f"LLM returned for action '{llm_action}'",
                                "action": llm_action,
                                "meta": {"response_preview": _safe_preview(getattr(response, "content", ""), 600)}
                            })
                        except Exception:
                            pass
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
                        await save_assistant_message(conversation_id, getattr(response, "content", "") or "")
                    except Exception as e:
                        print(f"Warning: failed to save assistant message: {e}")

                    if not getattr(response, "tool_calls", None):
                        try:
                            await emitter.emit({
                                "type": "agent_done",
                                "phase": "finish",
                                "subject": "agent",
                                "text": "Agent finished (no tools)",
                                "action": "finish",
                                "meta": {"answer_len": len(str(response.content or ""))}
                            })
                        except Exception:
                            pass
                        yield response.content
                        return

                    # Execute requested tools with streaming callbacks
                    # The LLM decides execution order by how it calls tools
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
                            try:
                                await save_action_event(conversation_id, "result", tool_message.content)
                            except Exception:
                                pass
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
                            try:
                                await save_action_event(conversation_id, "result", tool_message.content)
                            except Exception:
                                pass
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
                    try:
                        await emitter.emit({
                            "type": "agent_done",
                            "phase": "finish",
                            "subject": "agent",
                            "text": "Agent finished",
                            "action": "finish",
                            "meta": {"answer_len": len(str(last_response.content or ""))}
                        })
                    except Exception:
                        pass
                    yield last_response.content
                else:
                    try:
                        await emitter.emit({
                            "type": "agent_error",
                            "phase": "finish",
                            "subject": "agent",
                            "text": "Reached maximum reasoning steps without a final answer.",
                            "action": "finish"
                        })
                    except Exception:
                        pass
                    yield "Reached maximum reasoning steps without a final answer."
                return

        except Exception as e:
            try:
                await emitter.emit({
                    "type": "agent_error",
                    "phase": "run_streaming",
                    "subject": "agent",
                    "text": str(e),
                    "action": "run_streaming"
                })
            except Exception:
                pass
            yield f"Error running streaming agent: {str(e)}"

# ProjectManagement Insights Examples
async def main():
    """Example usage of the ProjectManagement Insights Agent"""
    agent = MongoDBAgent()
    await agent.connect()
    await agent.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
