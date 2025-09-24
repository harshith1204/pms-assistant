from langchain_ollama import ChatOllama

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, BaseMessage, SystemMessage
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_mcp_adapters.client import MultiServerMCPClient
import json
import asyncio
import contextlib
from typing import Dict, Any, List, AsyncGenerator, Optional
from pydantic import BaseModel
import tools
from datetime import datetime
import time
from collections import defaultdict, deque

# Tracing imports (Phoenix via OpenTelemetry exporter)
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from phoenix.trace.exporter import HttpExporter
from phoenix import Client
from phoenix.trace.trace_dataset import TraceDataset
import pandas as pd
import threading
import time
from opentelemetry.sdk.trace.export import SpanExporter, SpanProcessor

# Import tools list
try:
    tools_list = tools.tools
except AttributeError:
    # Fallback: define empty tools list if import fails
    tools_list = []
from mongo.constants import DATABASE_NAME, mongodb_tools

DEFAULT_SYSTEM_PROMPT = (
    "You are a Project Management System assistant. Use tools to answer questions about projects, work items, cycles, members, pages, modules, and project states."
    "\n\nAvailable tool: mongo_query - Use this for any questions requiring data from the database."
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
    temperature=0.3,
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
            self.tracer_provider = TracerProvider()
            trace.set_tracer_provider(self.tracer_provider)

            # Console exporter for local dev visibility
            console_exporter = ConsoleSpanExporter()
            console_processor = BatchSpanProcessor(console_exporter)
            self.tracer_provider.add_span_processor(console_processor)

            # Phoenix span processor (our working solution)
            phoenix_processor = PhoenixSpanProcessor()
            self.tracer_provider.add_span_processor(phoenix_processor)

            # Start Phoenix span collector
            phoenix_span_collector.start_periodic_export()
            print("✅ Phoenix span processor and collector configured")

            self.tracer = trace.get_tracer(__name__)
            self._initialized = True
            print("✅ Tracing initialized with Phoenix export")
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

                def clean_hex_id(hex_id):
                    """Convert hex IDs to proper hex string format"""
                    if isinstance(hex_id, str):
                        if hex_id.startswith('0x'):
                            return hex_id[2:]
                        else:
                            return hex_id
                    elif isinstance(hex_id, int):
                        # Convert integer to hex and remove 0x prefix
                        return hex(hex_id)[2:]
                    else:
                        return str(hex_id)

                span_dict = {
                    'name': span.name,
                    'span_kind': str(span.kind),
                    'trace_id': clean_hex_id(span.context.trace_id),
                    'span_id': clean_hex_id(span.context.span_id),
                    'parent_id': clean_hex_id(span.parent.span_id) if span.parent and span.parent.span_id else None,
                    'start_time': format_timestamp(span.start_time),
                    'end_time': format_timestamp(span.end_time),
                    'status_code': span.status.status_code.name,
                    'status_message': span.status.description or '',
                    'attributes': json.dumps(dict(span.attributes)),
                    'context.trace_id': clean_hex_id(span.context.trace_id),
                    'context.span_id': clean_hex_id(span.context.span_id),
                    'context.trace_state': str(span.context.trace_state)
                }

                # Add events
                events_list = []
                for event in span.events:
                    events_list.append({
                        'name': event.name,
                        'timestamp': event.timestamp,
                        'attributes': dict(event.attributes)
                    })
                span_dict['events'] = json.dumps(events_list)

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

class PhoenixSpanManager(AsyncCallbackHandler):
    """Manages Phoenix tracing configuration"""

    def __init__(self, websocket=None):
        super().__init__()
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
        self.llm_with_tools = llm_with_tools
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
                    attributes={"query_preview": query[:80]},
                )
            else:
                span_cm = None

            with (span_cm if span_cm is not None else contextlib.nullcontext()) as run_span:
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

                while steps < self.max_steps:
                    if tracer is not None:
                        llm_cm = tracer.start_as_current_span(
                            "llm_invoke",
                            kind=trace.SpanKind.INTERNAL,
                            attributes={"message_count": len(messages)},
                        )
                    else:
                        llm_cm = None

                    with (llm_cm if llm_cm is not None else contextlib.nullcontext()):
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
                        if tracer is not None:
                            tool_cm = tracer.start_as_current_span(
                                "tool_execute",
                                kind=trace.SpanKind.INTERNAL,
                                attributes={"tool_name": tool_call["name"]},
                            )
                        else:
                            tool_cm = None

                        with (tool_cm if tool_cm is not None else contextlib.nullcontext()) as tool_span:
                            tool = next((t for t in tools_list if t.name == tool_call["name"]), None)
                            if not tool:
                                error_msg = ToolMessage(
                                    content=f"Tool '{tool_call['name']}' not found.",
                                    tool_call_id=tool_call["id"],
                                )
                                messages.append(error_msg)
                                conversation_memory.add_message(conversation_id, error_msg)
                                continue

                            try:
                                result = await tool.ainvoke(tool_call["args"])
                                if tool_span:
                                    tool_span.set_attribute("tool_success", True)
                            except Exception as tool_exc:
                                result = f"Tool execution error: {tool_exc}"
                                if tool_span:
                                    tool_span.set_status(Status(StatusCode.ERROR, str(tool_exc)))

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
            tracer = phoenix_span_manager.tracer if self.tracing_enabled else None
            if tracer is not None:
                span_cm = tracer.start_as_current_span(
                    "agent_run_streaming",
                    kind=trace.SpanKind.INTERNAL,
                    attributes={"query_preview": query[:80]},
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

                callback_handler = PhoenixSpanManager(websocket)

                # Persist the human message
                conversation_memory.add_message(conversation_id, human_message)

                steps = 0
                last_response: Optional[AIMessage] = None

                while steps < self.max_steps:
                    if tracer is not None:
                        llm_cm = tracer.start_as_current_span(
                            "llm_invoke",
                            kind=trace.SpanKind.INTERNAL,
                            attributes={"message_count": len(messages)},
                        )
                    else:
                        llm_cm = None

                    with (llm_cm if llm_cm is not None else contextlib.nullcontext()):
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
                        if tracer is not None:
                            tool_cm = tracer.start_as_current_span(
                                "tool_execute",
                                kind=trace.SpanKind.INTERNAL,
                                attributes={"tool_name": tool_call["name"]},
                            )
                        else:
                            tool_cm = None

                        with (tool_cm if tool_cm is not None else contextlib.nullcontext()) as tool_span:
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
                                if tool_span:
                                    tool_span.set_attribute("tool_success", True)
                                await callback_handler.on_tool_end(str(result))
                            except Exception as tool_exc:
                                result = f"Tool execution error: {tool_exc}"
                                if tool_span:
                                    tool_span.set_status(Status(StatusCode.ERROR, str(tool_exc)))
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
