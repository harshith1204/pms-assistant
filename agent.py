from langchain_ollama import ChatOllama

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, BaseMessage, SystemMessage
from langchain_core.callbacks import AsyncCallbackHandler
import asyncio
import contextlib
from typing import Dict, Any, List, AsyncGenerator, Optional
import tools
from datetime import datetime
import time
from collections import defaultdict, deque
import os

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
from mongo.constants import DATABASE_NAME, mongodb_tools

DEFAULT_SYSTEM_PROMPT = (
    "You are a precise, non-speculative Project Management assistant.\n\n"
    "GENERAL RULES:\n"
    "- Never guess facts about the database or content. Prefer invoking a tool.\n"
    "- If a tool is appropriate, always call it before answering.\n"
    "- Keep answers concise and structured. If lists are long, summarize and offer to expand.\n"
    "- If tooling is unavailable for the task, state the limitation plainly.\n\n"
    "DECISION GUIDE:\n"
    "1) Use 'mongo_query' for structured questions about entities/fields in collections: project, workItem, cycle, module, members, page, projectState.\n"
    "   - Examples: counts, lists, filters, sort, group by, assignee/state/project info.\n"
    "   - Do NOT answer from memory; run a query.\n"
    "2) Use 'rag_search' for content-based searches (semantic meaning, not just keywords).\n"
    "   - Find pages/work items by meaning, group by metadata, analyze content patterns.\n"
    "   - Examples: 'find notes about OAuth', 'show API docs grouped by project', 'break down bugs by priority'.\n"
    "3) Use 'rag_mongo' when searching by content/meaning AND need complete MongoDB records with all fields.\n"
    "   - Combines semantic search with authoritative Mongo data.\n"
    "   - Examples: 'find auth bugs with their status', 'security pages with project info', 'microservices projects'.\n\n"
    "TOOL CHEATSHEET:\n"
    "- mongo_query(query:str, show_all:bool=False): Natural-language to Mongo aggregation. Safe fields only.\n"
    "  REQUIRED: 'query' - natural language description of what MongoDB data you want.\n"
    "- rag_search(query:str, content_type:str|None, group_by:str|None, limit:int=10, show_content:bool=True): Universal RAG search.\n"
    "  REQUIRED: 'query' - semantic search terms.\n"
    "  OPTIONAL: content_type ('page'|'work_item'|etc), group_by (field name), limit, show_content.\n"
    "- rag_mongo(query:str, entity_type:str, limit:int=15): Semantic search → MongoDB records with full fields.\n"
    "  REQUIRED: 'query' - semantic search, 'entity_type' ('work_item'|'page'|'project'|'cycle'|'module').\n\n"
    "WHEN UNSURE WHICH TOOL:\n"
    "- If the question references states, assignees, counts, filters, dates, or IDs → mongo_query.\n"
    "- If the question references 'content', 'notes', 'docs', 'pages', 'descriptions', or needs semantic search → rag_search.\n"
    "- If the user searches by content BUT needs complete MongoDB fields (state, assignee, dates, etc.) → rag_mongo.\n\n"
    "Respond with tool calls first, then synthesize a concise answer grounded ONLY in tool outputs."
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
    model=os.getenv("OLLAMA_MODEL", "qwen3:0.6b-fp16"),
    temperature=float(os.getenv("OLLAMA_TEMPERATURE", "0.2")),
    num_ctx=int(os.getenv("OLLAMA_NUM_CTX", "4096")),
    num_predict=int(os.getenv("OLLAMA_NUM_PREDICT", "1024")),
    num_thread=int(os.getenv("OLLAMA_NUM_THREAD", "8")),
    streaming=True,
    verbose=False,
    top_p=float(os.getenv("OLLAMA_TOP_P", "0.8")),
    top_k=int(os.getenv("OLLAMA_TOP_K", "40")),
)

# Simple per-query tool router: restrict RAG unless content/context is requested
_TOOLS_BY_NAME = {getattr(t, "name", str(i)): t for i, t in enumerate(tools_list)}


def _detect_multistep(user_query: str) -> bool:
    """Detect whether a query likely requires multiple steps/tools.

    Signals include: explicit sequencing terms, multiple distinct intents
    (e.g., count + list + search), or requests to run in parallel/batch.
    """
    q = (user_query or "").lower()
    # Obvious multi-step markers
    multi_markers = [
        " compare ", " versus ", " vs ", " side by side ", " and also ",
        " together ", ";", " then ", " in parallel", " simultaneously",
        " at the same time", " both ", " batch ", " run multiple", " multi-step",
    ]
    if any(m in q for m in multi_markers):
        return True

    # Multiple action categories in one sentence
    action_structured = ["count", "group", "breakdown", "distribution", "compare"]
    action_listing = ["list", "show", "top", "recent", "titles", "items"]
    action_content = ["summarize", "snippet", "snippets", "context", "explain", "search"]

    def has_any(terms):
        return any(term in q for term in terms)

    multiple_actions = (
        (has_any(action_structured) and has_any(action_listing)) or
        (has_any(action_structured) and has_any(action_content)) or
        (has_any(action_listing) and has_any(action_content))
    )
    if multiple_actions:
        return True

    # Heuristic: presence of multiple entity types hints multi-step
    entity_terms = ["project", "work item", "work items", "cycle", "module", "members", "page", "pages", "documentation", "docs"]
    if sum(1 for t in entity_terms if t in q) >= 2 and ("and" in q or ";" in q):
        return True
    return False

def _select_tools_for_query(user_query: str):
    """Return a subset of tools to expose to the LLM for this query.

    Policy:
    - Default to mongo_query for structured field questions.
    - Only enable RAG tools when the query clearly asks for content/context.
    - Enable rag_mongo_workitems only when content-like AND canonical fields are requested.
    """
    q = (user_query or "").lower()
    content_markers = [
        "content", "note", "notes", "doc", "docs", "documentation", "page", "pages",
        "description", "context", "summarize", "summary", "snippet", "snippets",
        "search", "find examples", "show examples", "browse"
    ]
    workitem_terms = ["work item", "work items", "ticket", "tickets", "bug", "bugs", "issue", "issues"]
    # Member-related structured queries should always go to mongo_query (avoid RAG)
    member_terms = [
        "member", "members", "team", "teammate", "teammates", "assignee", "assignees",
        "user", "users", "staff", "people", "personnel"
    ]
    canonical_field_terms = [
        "state", "assignee", "project", "count", "group", "filter", "sort",
        "created", "updated", "date", "due", "id", "displaybugno", "priority"
    ]

    def has_any(terms):
        return any(term in q for term in terms)

    # Strict default: Mongo for everything unless content/context explicitly requested
    allow_rag = has_any(content_markers)
    # Override: if the query is about members/assignees/team, force Mongo only
    if has_any(member_terms):
        allow_rag = False

    allowed_names = ["mongo_query"]
    if allow_rag:
        # Allow universal RAG search tool
        allowed_names.append("rag_search")
        # Allow rag_mongo when user needs semantic search + authoritative Mongo fields
        # This works for any entity type (work_item, page, project, cycle, module)
        if has_any(canonical_field_terms):
            allowed_names.append("rag_mongo")

    # Heuristic: enable composite orchestrator when the query likely needs multi-part handling
    multi_markers = [
        " compare ", " versus ", " vs ", " side by side ", " both ", " and also ", " together ", ";", " then ",
        " in parallel", " simultaneously", " at the same time", " batch ", " run multiple"
    ]
    # Detect presence of multiple action intents in one query
    action_structured = ["count", "group", "breakdown", "distribution", "compare"]
    action_listing = ["list", "show", "top", "recent", "titles", "items"]
    action_content = ["summarize", "snippet", "snippets", "context", "explain"]
    multiple_actions = (
        (has_any(action_structured) and has_any(action_listing)) or
        (has_any(action_structured) and has_any(action_content)) or
        (has_any(action_listing) and has_any(action_content))
    )
    # composite_query removed; agent will chain tools internally via planning

    # Map to actual tool objects, keep only those present
    selected_tools = [tool for name, tool in _TOOLS_BY_NAME.items() if name in allowed_names]
    # Fallback safety: if mapping failed for any reason, expose mongo_query only
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
    """MongoDB Agent using Tool Calling"""

    def __init__(self, max_steps: int = 8, system_prompt: Optional[str] = DEFAULT_SYSTEM_PROMPT):
        # Base LLM; tools will be bound per-query via router
        self.llm_base = llm
        self.connected = False
        self.max_steps = max_steps
        self.system_prompt = system_prompt
        self.tracing_enabled = False

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
                    "- First, break the user request into minimal sub-steps.\n"
                    "- For each sub-step, pick exactly one tool using the Decision Guide.\n\n"
                    "DECISION GUIDE:\n"
                    "- Use 'mongo_query' for DB facts (counts, group, filters, dates, assignee/state/project info).\n"
                    "- Use 'rag_search' for content searches, grouping, breakdowns (semantic meaning, not keywords).\n"
                    "- Use 'rag_mongo' to find items by semantic search AND get complete MongoDB fields.\n\n"
                    "IMPORTANT: Use valid args: mongo_query needs 'query'; rag_search needs 'query' (optional: content_type, group_by, limit, show_content); rag_mongo needs 'query' and 'entity_type'."
                ))
                # In non-streaming mode, also support a synthesis pass after tools
                invoke_messages = messages + [routing_instructions]
                if need_finalization:
                    finalization_instructions = SystemMessage(content=(
                        "FINALIZATION: Write a concise answer in your own words based on the tool outputs above. "
                        "Do not paste tool outputs verbatim. Focus on the specific fields requested; if multiple items, present a compact list."
                    ))
                    invoke_messages = messages + [routing_instructions, finalization_instructions]
                    need_finalization = False

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

                # Execute requested tools sequentially
                messages.append(response)
                did_any_tool = False
                for tool_call in response.tool_calls:
                    if tracer is not None:
                        tool_cm = tracer.start_as_current_span(
                            "tool_execute",
                            kind=trace.SpanKind.INTERNAL,
                            attributes={"tool_name": tool_call["name"]},
                        )
                    else:
                        tool_cm = None

                    with (tool_cm if tool_cm is not None else contextlib.nullcontext()) as tool_span:
                        # Enforce router: only allow selected tools
                        tool = next((t for t in selected_tools if t.name == tool_call["name"]), None)
                        if not tool:
                            error_msg = ToolMessage(
                                content=f"Tool '{tool_call['name']}' not found.",
                                tool_call_id=tool_call["id"],
                            )
                            messages.append(error_msg)
                            conversation_memory.add_message(conversation_id, error_msg)
                            continue

                        try:
                            if tool_span:
                                try:
                                    tool_span.set_attribute(getattr(OI, 'TOOL_NAME', 'tool.name'), tool.name)
                                    tool_span.set_attribute(getattr(OI, 'TOOL_INPUT', 'tool.input'), str(tool_call.get("args"))[:1000])
                                    # Tag span kind for OpenInference UI (uppercase expected)
                                    tool_span.set_attribute(getattr(OI, 'SPAN_KIND', 'openinference.span.kind'), 'TOOL')
                                    # Also set generic and OpenInference input.value for Phoenix UI
                                    tool_span.set_attribute(getattr(OI, 'INPUT_VALUE', 'input.value'), str(tool_call.get("args"))[:1000])
                                    try:
                                        tool_span.set_attribute('openinference.input.value', str(tool_call.get("args"))[:1000])
                                    except Exception:
                                        pass
                                    tool_span.add_event("tool_start", {"tool": tool.name})
                                except Exception:
                                    pass
                            result = await tool.ainvoke(tool_call["args"])
                            if tool_span:
                                tool_span.set_attribute("tool_success", True)
                                try:
                                    tool_span.set_attribute(getattr(OI, 'TOOL_OUTPUT', 'tool.output'), str(result)[:1200])
                                    tool_span.set_attribute(getattr(OI, 'OUTPUT_VALUE', 'output.value'), str(result)[:1200])
                                    try:
                                        tool_span.set_attribute('openinference.output.value', str(result)[:1200])
                                    except Exception:
                                        pass
                                    tool_span.add_event("tool_end", {"tool": tool.name})
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
                        messages.append(tool_message)
                        conversation_memory.add_message(conversation_id, tool_message)
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
                            "- Decompose the task into ordered sub-steps.\n"
                            "- Choose exactly one tool per sub-step.\n\n"
                            "DECISION GUIDE:\n"
                            "- 'mongo_query' → DB facts (counts/group/filter/sort/date/assignee/state/project).\n"
                            "- 'rag_search' → content searches, grouping, breakdowns (semantic, not keywords).\n"
                            "- 'rag_mongo' → semantic search + complete MongoDB fields (any entity type).\n\n"
                            "IMPORTANT: Use valid args - mongo_query needs 'query'; rag_search needs 'query' (optional: content_type, group_by, limit, show_content); rag_mongo needs 'query' and 'entity_type'."
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

                    # Execute requested tools sequentially with streaming callbacks
                    messages.append(response)
                    did_any_tool = False
                    for tool_call in response.tool_calls:
                        if tracer is not None:
                            tool_cm = tracer.start_as_current_span(
                                "tool_execute",
                                kind=trace.SpanKind.INTERNAL,
                                attributes={"tool_name": tool_call["name"]},
                            )
                        else:
                            tool_cm = None

                        with (tool_cm if tool_cm is not None else contextlib.nullcontext()) as tool_span:
                            # Enforce router: only allow selected tools
                            tool = next((t for t in selected_tools if t.name == tool_call["name"]), None)
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
                                if tool_span:
                                    try:
                                        tool_span.set_attribute(getattr(OI, 'TOOL_NAME', 'tool.name'), tool.name)
                                        tool_span.set_attribute(getattr(OI, 'TOOL_INPUT', 'tool.input'), str(tool_call.get("args"))[:1000])
                                        tool_span.set_attribute(getattr(OI, 'SPAN_KIND', 'openinference.span.kind'), 'tool')
                                        tool_span.add_event("tool_start", {"tool": tool.name})
                                    except Exception:
                                        pass
                                result = await tool.ainvoke(tool_call["args"])
                                if tool_span:
                                    tool_span.set_attribute("tool_success", True)
                                    try:
                                        tool_span.set_attribute(getattr(OI, 'TOOL_OUTPUT', 'tool.output'), str(result)[:1200])
                                        tool_span.add_event("tool_end", {"tool": tool.name})
                                    except Exception:
                                        pass
                                await callback_handler.on_tool_end(str(result))
                            except Exception as tool_exc:
                                result = f"Tool execution error: {tool_exc}"
                                if tool_span:
                                    tool_span.set_status(Status(StatusCode.ERROR, str(tool_exc)))
                                    try:
                                        tool_span.set_attribute(getattr(OI, 'ERROR_TYPE', 'error.type'), tool_exc.__class__.__name__)
                                        tool_span.set_attribute(getattr(OI, 'ERROR_MESSAGE', 'error.message'), str(tool_exc))
                                    except Exception:
                                        pass
                                await callback_handler.on_tool_end(str(result))

                            tool_message = ToolMessage(
                                content=str(result),
                                tool_call_id=tool_call["id"],
                            )
                            messages.append(tool_message)
                            conversation_memory.add_message(conversation_id, tool_message)
                            did_any_tool = True
                    steps += 1

                    # After executing any tools, force the next LLM turn to synthesize
                    if did_any_tool:
                        need_finalization = True

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
    await agent.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
