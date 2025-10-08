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

# Tracing imports (Phoenix via OpenTelemetry exporter)
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from phoenix import Client
from phoenix.trace.trace_dataset import TraceDataset
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
import pandas as pd
import threading
import time
from opentelemetry.sdk.trace.export import SpanProcessor
from traces.tracing import PhoenixSpanProcessor as MongoDBSpanProcessor, mongodb_span_collector
import math

# OpenInference semantic conventions (optional)
try:
    from openinference.semconv.trace import SpanAttributes as OI
except Exception:  # Fallback when OpenInference isn't installed
    class _OI:
        INPUT_VALUE = "input.value"
        OUTPUT_VALUE = "output.value"
        SPAN_KIND = "openinference.span.kind"
        LLM_MODEL_NAME = "llm.model_name"
        LLM_TEMPERATURE = "llm.temperature"
        LLM_TOP_P = "llm.top_p"
        LLM_TOP_K = "llm.top_k"
        LLM_PROMPT = "llm.prompt"
        LLM_SYSTEM = "llm.system_prompt"
        LLM_INVOCATION_PARAMETERS = "llm.invocation_parameters"
        TOOL_NAME = "tool.name"
        TOOL_INPUT = "tool.input"
        TOOL_OUTPUT = "tool.output"
        ERROR_TYPE = "error.type"
        ERROR_MESSAGE = "error.message"

    OI = _OI()

# Import tools list
try:
    tools_list = tools.tools
except AttributeError:
    # Fallback: define empty tools list if import fails
    tools_list = []
import os
from langchain_groq import ChatGroq
from mongo.constants import DATABASE_NAME, mongodb_tools


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
    "3) Use BOTH tools together when question needs structured data AND content analysis.\n"
    "   - Example: 'Show bug counts by priority (mongo_query) and find related documentation (rag_search)'.\n"
    "   - Agent decides tool combination based on query complexity and dependencies.\n\n"
    "TOOL CHEATSHEET:\n"
    "- mongo_query(query:str, show_all:bool=False): Natural-language to Mongo aggregation. Safe fields only. Automatically uses complex joins when beneficial.\n"
    "  REQUIRED: 'query' - natural language description of what MongoDB data you want.\n"
    "- rag_search(query:str, content_type:str|None, group_by:str|None, limit:int=10, show_content:bool=True): Universal RAG search.\n"
    "  REQUIRED: 'query' - semantic search terms.\n"
    "  OPTIONAL: content_type ('page'|'work_item'|'project'|'cycle'|'module'|None for all), group_by (field name), limit, show_content.\n\n"
    "CONTENT TYPE ROUTING EXAMPLES:\n"
    "- 'What is the next release about?' → rag_search(query='next release', content_type='page')\n"
    "- 'What are recent work items about?' → rag_search(query='recent work items', content_type='work_item')\n"
    "- 'What is the active cycle about?' → rag_search(query='active cycle', content_type='cycle')\n"
    "- 'What is the CRM module about?' → rag_search(query='CRM module', content_type='module')\n"
    "- 'Find content about authentication' → rag_search(query='authentication', content_type=None)  # searches all types\n\n"
    "WHEN UNSURE WHICH TOOL:\n"
    "- If the query is ambiguous or entity/field mapping to Mongo is unclear → prefer rag_search first.\n"
    "- Question about structured data (counts, filters, group by, breakdown by assignee/state/priority/project/date) → mongo_query.\n"
    "- Question about content meaning/semantics (find docs, analyze patterns, content search, descriptions) → rag_search.\n"
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
    top_p=float(os.getenv("GROQ_TOP_P", "0.8")),
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
    - Always expose both structured (mongo_query) and RAG tools (rag_search).
    - Let the LLM decide routing based on instructions; no keyword gating.
    - Add query analysis hints for complex join decisions.
    """
    allowed_names = ["mongo_query", "rag_search"]
    selected_tools = [tool for name, tool in _TOOLS_BY_NAME.items() if name in allowed_names]
    if not selected_tools and "mongo_query" in _TOOLS_BY_NAME:
        selected_tools = [_TOOLS_BY_NAME["mongo_query"]]
    return selected_tools, allowed_names


class PhoenixSpanManager:
    """Manages Phoenix spans and tracer for the agent."""

    def __init__(self):
        self.tracer_provider = None
        self.tracer = None
        self._initialized = False

    async def initialize(self):
        """Initialize OpenTelemetry tracer provider with Phoenix exporter."""
        if self._initialized:
            return

        try:
            # Add a resource so Phoenix shows a sensible service name
            resource = Resource.create({
                "service.name": "pms-assistant",
                "service.version": "1.0.0",
            })
            self.tracer_provider = TracerProvider(resource=resource)
            trace.set_tracer_provider(self.tracer_provider)

            # Console exporter for local dev visibility
            console_exporter = ConsoleSpanExporter()
            console_processor = BatchSpanProcessor(console_exporter)
            self.tracer_provider.add_span_processor(console_processor)

            # Register MongoDB span processor (stores spans directly in MongoDB)
            try:
                mongodb_processor = MongoDBSpanProcessor()
                self.tracer_provider.add_span_processor(mongodb_processor)
                mongodb_span_collector.start_periodic_export()
                print("✅ MongoDB span processor configured for tracing")
            except Exception as e:
                print(f"⚠️  Failed to configure MongoDB span processor: {e}")

            # Also export to Phoenix UI via OTLP HTTP so GUI shows new spans
            try:
                otlp_http_exporter = OTLPSpanExporter(endpoint="http://localhost:6006/v1/traces")
                otlp_processor = BatchSpanProcessor(otlp_http_exporter)
                self.tracer_provider.add_span_processor(otlp_processor)
                print("✅ OTLP HTTP exporter configured for Phoenix UI (/v1/traces)")
            except Exception as e:
                print(f"⚠️  Failed to configure OTLP HTTP exporter: {e}")

            # Disable custom collector-based export to avoid duplicates
            # (We keep the class around, but do not register the processor or start the collector.)

            self.tracer = trace.get_tracer(__name__)
            self._initialized = True
            print("✅ Tracing initialized with MongoDB + Phoenix UI export")
        except Exception as e:
            print(f"❌ Failed to initialize tracing: {e}")
            import traceback
            traceback.print_exc()


class PhoenixSpanCollector:
    """Collects and exports spans to Phoenix"""

    def __init__(self):
        self.collected_spans = []
        self.phoenix_client = Client()
        self.export_thread = None
        self.running = False

    def collect_span(self, span):
        """Collect a span for export to Phoenix"""
        self.collected_spans.append(span)

        # If we have many spans, export them
        if len(self.collected_spans) >= 10:
            self.export_to_phoenix()

    def export_to_phoenix(self):
        """Export collected spans to Phoenix"""
        if not self.collected_spans:
            return

        try:
            # Convert spans to DataFrame format
            spans_data = []
            for span in self.collected_spans:
                # Extract span information with proper timestamp conversion
                def format_timestamp(timestamp):
                    """Convert OpenTelemetry timestamp to ISO format"""
                    if hasattr(timestamp, 'isoformat'):
                        return timestamp.isoformat()
                    elif isinstance(timestamp, (int, float)):
                        # Convert nanoseconds to datetime
                        from datetime import datetime
                        return datetime.fromtimestamp(timestamp / 1e9).isoformat()
                    else:
                        return str(timestamp)

                def _to_int(value):
                    if isinstance(value, int):
                        return value
                    if isinstance(value, str):
                        v = value[2:] if value.startswith('0x') else value
                        try:
                            return int(v, 16)
                        except Exception:
                            try:
                                return int(v)
                            except Exception:
                                return 0
                    return 0

                def format_trace_id(value):
                    """Return 32-char zero-padded lowercase hex trace ID."""
                    return f"{_to_int(value):032x}"

                def format_span_id(value):
                    """Return 16-char zero-padded lowercase hex span ID."""
                    return f"{_to_int(value):016x}"

                span_dict = {
                    'name': span.name,
                    'span_kind': str(span.kind),
                    'kind': getattr(getattr(span, 'kind', None), 'name', str(getattr(span, 'kind', 'INTERNAL'))),
                    'trace_id': format_trace_id(span.context.trace_id),
                    'span_id': format_span_id(span.context.span_id),
                    'parent_id': format_span_id(span.parent.span_id) if span.parent and getattr(span.parent, 'span_id', None) else None,
                    'start_time': format_timestamp(span.start_time),
                    'end_time': format_timestamp(span.end_time),
                    'status_code': span.status.status_code.name,
                    'status_message': span.status.description or '',
                    # Keep attributes as structured data (dict) for Phoenix UI parsing
                    'attributes': dict(span.attributes),
                    'context.trace_id': format_trace_id(span.context.trace_id),
                    'context.span_id': format_span_id(span.context.span_id),
                    'context.trace_state': str(span.context.trace_state)
                }

                # Extract generic input/output for convenience
                try:
                    def _extract_first(attrs, keys):
                        for k in keys:
                            if k in attrs:
                                return attrs.get(k)
                        return None

                    attrs = dict(span.attributes)
                    input_val = _extract_first(attrs, [
                        getattr(OI, 'INPUT_VALUE', 'input.value'),
                        getattr(OI, 'TOOL_INPUT', 'tool.input'),
                        'input.value',
                        'tool.input'
                    ])
                    output_val = _extract_first(attrs, [
                        getattr(OI, 'OUTPUT_VALUE', 'output.value'),
                        getattr(OI, 'TOOL_OUTPUT', 'tool.output'),
                        'output.value',
                        'tool.output'
                    ])
                    if input_val is not None:
                        span_dict['input'] = str(input_val)
                    if output_val is not None:
                        span_dict['output'] = str(output_val)
                except Exception:
                    pass

                # Add events
                events_list = []
                for event in span.events:
                    events_list.append({
                        'name': event.name,
                        'timestamp': format_timestamp(event.timestamp),
                        'attributes': dict(event.attributes)
                    })
                # Keep events as structured list for Phoenix UI
                span_dict['events'] = events_list

                spans_data.append(span_dict)

            # Create DataFrame and export
            if spans_data:
                df = pd.DataFrame(spans_data)
                trace_dataset = TraceDataset(dataframe=df, name='agent-traces')
                self.phoenix_client.log_traces(trace_dataset, project_name='default')
                print(f"✅ Exported {len(spans_data)} spans to Phoenix")

            # Clear collected spans
            self.collected_spans.clear()

        except Exception as e:
            print(f"❌ Error exporting spans to Phoenix: {e}")

    def start_periodic_export(self):
        """Start periodic export of collected spans"""
        if self.export_thread and self.export_thread.is_alive():
            return

        self.running = True
        self.export_thread = threading.Thread(target=self._periodic_export_worker, daemon=True)
        self.export_thread.start()

    def stop_periodic_export(self):
        """Stop periodic export"""
        self.running = False
        if self.export_thread:
            self.export_thread.join(timeout=5)
        self.export_to_phoenix()  # Export any remaining spans

    def _periodic_export_worker(self):
        """Worker thread for periodic span export"""
        while self.running:
            time.sleep(5)  # Export every 5 seconds
            self.export_to_phoenix()


class PhoenixSpanProcessor(SpanProcessor):
    """Custom span processor that sends spans to Phoenix collector"""

    def on_start(self, span, parent_context=None):
        """Called when a span starts"""
        pass

    def on_end(self, span):
        """Called when a span ends - send to Phoenix"""
        try:
            phoenix_span_collector.collect_span(span)
        except Exception as e:
            # Don't let span processing errors break the application
            print(f"Warning: Failed to collect span for Phoenix: {e}")

    def shutdown(self, timeout_millis=30000):
        """Shutdown the processor"""
        try:
            phoenix_span_collector.export_to_phoenix()
        except Exception as e:
            print(f"Warning: Failed to export spans during shutdown: {e}")

    def force_flush(self, timeout_millis=30000):
        """Force flush any pending spans"""
        try:
            phoenix_span_collector.export_to_phoenix()
        except Exception as e:
            print(f"Warning: Failed to flush spans: {e}")


# Global span collector
phoenix_span_collector = PhoenixSpanCollector()

# Global Phoenix span manager instance
phoenix_span_manager = PhoenixSpanManager()



class PhoenixCallbackHandler(AsyncCallbackHandler):
    """WebSocket streaming callback handler for Phoenix events"""

    def __init__(self, websocket=None):
        super().__init__()
        self.websocket = websocket
        self.start_time = None
        # Tool outputs are now always streamed to the frontend for better visibility

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
            # Always send full tool outputs to frontend for better visibility
            payload = {
                "type": "tool_end",
                "output": output,
                "timestamp": datetime.now().isoformat()
            }
            await self.websocket.send_json(payload)

    def cleanup(self):
        """Clean up Phoenix span collector"""
        try:
            # Clean up the global span collector
            phoenix_span_collector.stop_periodic_export()
            print("✅ Phoenix span collector stopped")
        except Exception as e:
            print(f"Warning: Error stopping Phoenix span collector: {e}")

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

    async def initialize_tracing(self):
        """Enable Phoenix tracing for this agent."""
        await phoenix_span_manager.initialize()
        self.tracing_enabled = True


    def _start_span(self, name: str, attributes: Dict[str, Any] | None = None):
        if not self.tracing_enabled or phoenix_span_manager.tracer is None:
            return None
        try:
            span = phoenix_span_manager.tracer.start_span(
                name=name,
                kind=trace.SpanKind.INTERNAL,
                attributes=attributes or {},
            )
            return span
        except Exception as e:
            print(f"Tracing error starting span '{name}': {e}")
            return None

    def _end_span(self, span, status: str = "OK", message: str = ""):
        if not span:
            return
        try:
            if status == "ERROR":
                span.set_status(Status(StatusCode.ERROR, message))
            span.end()
        except Exception as e:
            print(f"Tracing error ending span: {e}")

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
        if tracer is not None:
            tool_cm = tracer.start_as_current_span(
                "tool_execute",
                kind=trace.SpanKind.INTERNAL,
                attributes={"tool_name": tool_call["name"]},
            )
        
        with (tool_cm if tool_cm is not None else contextlib.nullcontext()) as tool_span:
            # Enforce router: only allow selected tools
            actual_tool = next((t for t in selected_tools if t.name == tool_call["name"]), None)
            if not actual_tool:
                error_msg = ToolMessage(
                    content=f"Tool '{tool_call['name']}' not found.",
                    tool_call_id=tool_call["id"],
                )
                return error_msg, False

            try:
                if tool_span:
                    try:
                        tool_span.set_attribute(getattr(OI, 'TOOL_NAME', 'tool.name'), actual_tool.name)
                        tool_span.set_attribute(getattr(OI, 'TOOL_INPUT', 'tool.input'), str(tool_call.get("args"))[:1000])
                        tool_span.set_attribute(getattr(OI, 'SPAN_KIND', 'openinference.span.kind'), 'TOOL')
                        tool_span.set_attribute(getattr(OI, 'INPUT_VALUE', 'input.value'), str(tool_call.get("args"))[:1000])
                        try:
                            tool_span.set_attribute('openinference.input.value', str(tool_call.get("args"))[:1000])
                        except Exception:
                            pass
                        tool_span.add_event("tool_start", {"tool": actual_tool.name})
                    except Exception:
                        pass
                
                result = await actual_tool.ainvoke(tool_call["args"])
                
                if tool_span:
                    tool_span.set_attribute("tool_success", True)
                    try:
                        tool_span.set_attribute(getattr(OI, 'TOOL_OUTPUT', 'tool.output'), str(result)[:1200])
                        tool_span.set_attribute(getattr(OI, 'OUTPUT_VALUE', 'output.value'), str(result)[:1200])
                        try:
                            tool_span.set_attribute('openinference.output.value', str(result)[:1200])
                        except Exception:
                            pass
                        tool_span.add_event("tool_end", {"tool": actual_tool.name})
                    except Exception:
                        pass
                        
            except Exception as tool_exc:
                result = f"Tool execution error: {tool_exc}"
                if tool_span:
                    tool_span.set_status(Status(StatusCode.ERROR, str(tool_exc)))
                    try:
                        tool_span.set_attribute(getattr(OI, 'ERROR_TYPE', 'error.type'), tool_exc.__class__.__name__)
                        tool_span.set_attribute(getattr(OI, 'ERROR_MESSAGE', 'error.message'), str(tool_exc))
                    except Exception:
                        pass

            tool_message = ToolMessage(
                content=str(result),
                tool_call_id=tool_call["id"],
            )
            return tool_message, True

    async def connect(self):
        """Connect to MongoDB MCP server"""
        # Ensure tracing is initialized so spans include attributes/events
        if not self.tracing_enabled:
            try:
                await self.initialize_tracing()
            except Exception as _e:
                # Proceed without tracing if initialization fails
                pass
        span = self._start_span("mongodb_connect")
        try:
            await mongodb_tools.connect()
            self.connected = True
            if span:
                span.set_attribute("connection_success", True)
            print("MongoDB Agent connected successfully!")
        except Exception as e:
            if span:
                span.set_attribute("connection_success", False)
                span.set_status(Status(StatusCode.ERROR, str(e)))
            raise
        finally:
            self._end_span(span)

    async def disconnect(self):
        """Disconnect from MongoDB MCP server"""
        await mongodb_tools.disconnect()
        self.connected = False
        # Clean up Phoenix tracing
        phoenix_span_manager.cleanup()

    async def run(self, query: str, conversation_id: Optional[str] = None) -> str:
        """Run the agent with a query and optional conversation context"""
        if not self.connected:
            await self.connect()

        try:
            tracer = phoenix_span_manager.tracer if self.tracing_enabled else None
            if tracer is not None:
                span_cm = tracer.start_as_current_span(
                    "agent_run",
                    kind=trace.SpanKind.INTERNAL,
                    attributes={
                        "query_preview": query[:80],
                        "query_length": len(query or ""),
                        "database.name": DATABASE_NAME,
                    },
                )
            else:
                span_cm = None

            with (span_cm if span_cm is not None else contextlib.nullcontext()) as run_span:
                if run_span:
                    try:
                        run_span.add_event("agent_start")
                    except Exception:
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

                    if tracer is not None:
                        llm_cm = tracer.start_as_current_span(
                            "llm_invoke",
                            kind=trace.SpanKind.INTERNAL,
                            attributes={"message_count": len(messages)},
                        )
                    else:
                        llm_cm = None

                    with (llm_cm if llm_cm is not None else contextlib.nullcontext()) as llm_span:
                        # Record model invocation parameters
                        if llm_span:
                            try:
                                llm_span.set_attribute(getattr(OI, 'LLM_MODEL_NAME', 'llm.model_name'), getattr(llm, "model", "unknown"))
                                llm_span.set_attribute(getattr(OI, 'LLM_TEMPERATURE', 'llm.temperature'), getattr(llm, "temperature", None))
                                llm_span.set_attribute(getattr(OI, 'LLM_TOP_P', 'llm.top_p'), getattr(llm, "top_p", None))
                                llm_span.set_attribute(getattr(OI, 'LLM_TOP_K', 'llm.top_k'), getattr(llm, "top_k", None))
                                # Tag span kind for OpenInference UI (uppercase expected)
                                llm_span.set_attribute(getattr(OI, 'SPAN_KIND', 'openinference.span.kind'), 'LLM')
                                # Record the current user input as LLM input
                                try:
                                    llm_input_preview = str(human_message.content)[:1000]
                                except Exception:
                                    llm_input_preview = ""
                                # Set both generic and OpenInference-prefixed keys
                                llm_span.set_attribute(getattr(OI, 'INPUT_VALUE', 'input.value'), llm_input_preview)
                                try:
                                    llm_span.set_attribute('openinference.input.value', llm_input_preview)
                                except Exception:
                                    pass
                                if self.system_prompt:
                                    llm_span.set_attribute(getattr(OI, 'LLM_SYSTEM', 'llm.system_prompt'), self.system_prompt[:1000])
                                # Add prompt summary event
                                llm_span.add_event("llm_prompt", {"message_count": len(messages)})
                            except Exception:
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
                    "3) Use BOTH tools together when question needs structured data AND content analysis.\n"
                    "   - Example: 'Show bug counts by priority (mongo_query) and find related documentation (rag_search)'.\n"
                    "   - Agent decides tool combination based on query complexity and dependencies.\n\n"
                    "TOOL CHEATSHEET:\n"
                    "- mongo_query(query:str, show_all:bool=False): Natural-language to Mongo aggregation. Safe fields only.\n"
                    "  REQUIRED: 'query' - natural language description of what MongoDB data you want.\n"
                    "- rag_search(query:str, content_type:str|None, group_by:str|None, limit:int=10, show_content:bool=True): Universal RAG search.\n"
                    "  REQUIRED: 'query' - semantic search terms.\n"
                    "  OPTIONAL: content_type ('page'|'work_item'|'project'|'cycle'|'module'|None), group_by (field), limit, show_content.\n\n"
                    "CONTENT TYPE EXAMPLES:\n"
                    "- 'What is next release about?' → rag_search(query='next release', content_type='page')\n"
                    "- 'Recent work items about auth?' → rag_search(query='recent work items auth', content_type='work_item')\n"
                    "- 'Active cycle details?' → rag_search(query='active cycle', content_type='cycle')\n"
                    "- 'CRM module overview?' → rag_search(query='CRM module', content_type='module')\n\n"
                    "WHEN UNSURE WHICH TOOL:\n"
                    "- If the query is ambiguous or entity/field mapping to Mongo is unclear → prefer rag_search first.\n"
                    "- Question about structured data (counts, filters, group by, breakdown by assignee/state/priority/project/date) → mongo_query.\n"
                    "- Question about content meaning/semantics (find docs, analyze patterns, content search, descriptions) → rag_search.\n"
                    "- Question needs both structured + semantic analysis → use BOTH tools together.\n\n"
                    "IMPORTANT: Use valid args: mongo_query needs 'query'; rag_search needs 'query' (optional: content_type, group_by, limit, show_content)."
                ))
                invoke_messages = messages + [routing_instructions]
                response = await llm_with_tools.ainvoke(invoke_messages)
                if llm_span and getattr(response, "content", None):
                        try:
                            preview = str(response.content)[:500]
                            llm_span.set_attribute(getattr(OI, 'OUTPUT_VALUE', 'output.value'), preview)
                            llm_span.add_event("llm_response", {"preview_len": len(preview)})
                        except Exception:
                            pass
                last_response = response

                # Persist assistant message
                conversation_memory.add_message(conversation_id, response)

                # If no tools requested, we are done
                if not getattr(response, "tool_calls", None):
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
                    if run_span:
                        run_span.add_event("parallel_tool_execution", {
                            "tool_count": len(response.tool_calls),
                            "tools": tool_names
                        })
                    
                    tool_tasks = [
                        self._execute_single_tool(None, tool_call, selected_tools, tracer)
                        for tool_call in response.tool_calls
                    ]
                    tool_results = await asyncio.gather(*tool_tasks)
                    
                    # Process results in order
                    for tool_message, success in tool_results:
                        messages.append(tool_message)
                        conversation_memory.add_message(conversation_id, tool_message)
                        if success:
                            did_any_tool = True
                else:
                    # Single tool or parallel disabled
                    for tool_call in response.tool_calls:
                        tool_message, success = await self._execute_single_tool(
                            None, tool_call, selected_tools, tracer
                        )
                        messages.append(tool_message)
                        conversation_memory.add_message(conversation_id, tool_message)
                        if success:
                            did_any_tool = True
                
                steps += 1

                # After executing any tools, force the next LLM turn to synthesize
                if did_any_tool:
                    need_finalization = True
                else:
                    # If no tools were executed, return the latest response
                    if last_response is not None:
                        if run_span:
                            try:
                                preview = str(last_response.content)[:500]
                                run_span.set_attribute(getattr(OI, 'OUTPUT_VALUE', 'output.value'), preview)
                                run_span.add_event("agent_end", {"steps": steps})
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
                return last_response.content
            return "Reached maximum reasoning steps without a final answer."

        except Exception as e:
            return f"Error running agent: {str(e)}"

    async def run_streaming(self, query: str, websocket=None, conversation_id: Optional[str] = None) -> AsyncGenerator[str, None]:
        """Run the agent with streaming support and conversation context"""
        if not self.connected:
            await self.connect()

        try:
            tracer = phoenix_span_manager.tracer if self.tracing_enabled else None
            if tracer is not None:
                span_cm = tracer.start_as_current_span(
                    "agent_run_streaming",
                    kind=trace.SpanKind.INTERNAL,
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

                callback_handler = PhoenixCallbackHandler(websocket)

                # Persist the human message
                conversation_memory.add_message(conversation_id, human_message)

                steps = 0
                last_response: Optional[AIMessage] = None
                need_finalization: bool = False

                while steps < self.max_steps:
                    # Choose tools for this query iteration
                    selected_tools, allowed_names = _select_tools_for_query(query)
                    llm_with_tools = self.llm_base.bind_tools(selected_tools)
                    if tracer is not None:
                        llm_cm = tracer.start_as_current_span(
                            "llm_invoke",
                            kind=trace.SpanKind.INTERNAL,
                            attributes={"message_count": len(messages)},
                        )
                    else:
                        llm_cm = None

                    with (llm_cm if llm_cm is not None else contextlib.nullcontext()) as llm_span:
                        if llm_span:
                            try:
                                llm_span.set_attribute(getattr(OI, 'LLM_MODEL_NAME', 'llm.model_name'), getattr(llm, "model", "unknown"))
                                llm_span.set_attribute(getattr(OI, 'LLM_TEMPERATURE', 'llm.temperature'), getattr(llm, "temperature", None))
                                llm_span.set_attribute(getattr(OI, 'LLM_TOP_P', 'llm.top_p'), getattr(llm, "top_p", None))
                                llm_span.set_attribute(getattr(OI, 'LLM_TOP_K', 'llm.top_k'), getattr(llm, "top_k", None))
                                llm_span.set_attribute(getattr(OI, 'SPAN_KIND', 'openinference.span.kind'), 'llm')
                                if self.system_prompt:
                                    llm_span.set_attribute(getattr(OI, 'LLM_SYSTEM', 'llm.system_prompt'), self.system_prompt[:1000])
                                llm_span.add_event("llm_prompt", {"message_count": len(messages)})
                            except Exception:
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
                            "3) Use BOTH tools together when question needs structured data AND content analysis.\n"
                            "   - Example: 'Show bug counts by priority (mongo_query) and find related documentation (rag_search)'.\n"
                            "   - Agent decides tool combination based on query complexity and dependencies.\n\n"
                            "TOOL CHEATSHEET:\n"
                            "- mongo_query(query:str, show_all:bool=False): Natural-language to Mongo aggregation. Safe fields only.\n"
                            "  REQUIRED: 'query' - natural language description of what MongoDB data you want.\n"
                            "- rag_search(query:str, content_type:str|None, group_by:str|None, limit:int=10, show_content:bool=True): Universal RAG search.\n"
                            "  REQUIRED: 'query' - semantic search terms.\n"
                            "  OPTIONAL: content_type ('page'|'work_item'|'project'|'cycle'|'module'|None), group_by (field), limit, show_content.\n\n"
                            "CONTENT TYPE EXAMPLES:\n"
                            "- 'What is next release about?' → rag_search(query='next release', content_type='page')\n"
                            "- 'Recent work items about auth?' → rag_search(query='recent work items auth', content_type='work_item')\n"
                            "- 'Active cycle details?' → rag_search(query='active cycle', content_type='cycle')\n"
                            "- 'CRM module overview?' → rag_search(query='CRM module', content_type='module')\n\n"
                            "WHEN UNSURE WHICH TOOL:\n"
                            "- If the query is ambiguous or entity/field mapping to Mongo is unclear → prefer rag_search first.\n"
                            "- Question about structured data (counts, filters, group by, breakdown by assignee/state/priority/project/date) → mongo_query.\n"
                            "- Question about content meaning/semantics (find docs, analyze patterns, content search, descriptions) → rag_search.\n"
                            "- Question needs both structured + semantic analysis → use BOTH tools together.\n\n"
                            "IMPORTANT: Use valid args: mongo_query needs 'query'; rag_search needs 'query' (optional: content_type, group_by, limit, show_content)."
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
                        response = await llm_with_tools.ainvoke(
                            invoke_messages,
                            config={"callbacks": [callback_handler]},
                        )
                        if llm_span and getattr(response, "content", None):
                            try:
                                preview = str(response.content)[:500]
                                llm_span.set_attribute(getattr(OI, 'OUTPUT_VALUE', 'output.value'), preview)
                                llm_span.add_event("llm_response", {"preview_len": len(preview)})
                            except Exception:
                                pass
                    last_response = response

                    # Persist assistant message
                    conversation_memory.add_message(conversation_id, response)

                    if not getattr(response, "tool_calls", None):
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
                        tool_tasks = [
                            self._execute_single_tool(None, tool_call, selected_tools, tracer)
                            for tool_call in response.tool_calls
                        ]
                        tool_results = await asyncio.gather(*tool_tasks)
                        
                        # Process results and send tool_end events
                        for tool_message, success in tool_results:
                            await callback_handler.on_tool_end(tool_message.content)
                            messages.append(tool_message)
                            conversation_memory.add_message(conversation_id, tool_message)
                            if success:
                                did_any_tool = True
                    else:
                        # Single tool or parallel disabled
                        for tool_call in response.tool_calls:
                            tool = next((t for t in selected_tools if t.name == tool_call["name"]), None)
                            if tool:
                                await callback_handler.on_tool_start({"name": tool.name}, str(tool_call["args"]))
                            
                            tool_message, success = await self._execute_single_tool(
                                None, tool_call, selected_tools, tracer
                            )
                            await callback_handler.on_tool_end(tool_message.content)
                            messages.append(tool_message)
                            conversation_memory.add_message(conversation_id, tool_message)
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
