"""Unified tracing module to avoid circular imports"""
from datetime import datetime
import json
import time
import uuid
from typing import Dict, Any, List

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


class UnifiedTracingManager:
    """Unified tracing manager that consolidates all tracing functionality"""

    def __init__(self):
        self.tracer_provider = None
        self.tracer = None
        self._initialized = False
        self.active_spans = {}
        self.conversation_spans = {}
        self.trace_correlations = {}  # Maps operation IDs to trace info

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
            print("✅ Unified tracing initialized with Phoenix export")
        except Exception as e:
            print(f"❌ Failed to initialize tracing: {e}")
            import traceback
            traceback.print_exc()

    def start_span(self, name: str, span_kind: str = "INTERNAL", attributes: Dict[str, Any] = None, parent_span=None):
        """Start a new span with optional parent context"""
        if not self._initialized or not self.tracer:
            return None

        try:
            # Get parent context if provided
            context = None
            if parent_span:
                context = trace.set_span_in_context(parent_span)

            span = self.tracer.start_span(
                name=name,
                kind=getattr(trace.SpanKind, span_kind.upper(), trace.SpanKind.INTERNAL),
                attributes=attributes or {},
                context=context
            )
            return span
        except Exception as e:
            print(f"Tracing error starting span '{name}': {e}")
            return None

    def start_conversation_span(self, conversation_id: str, user_query: str):
        """Start a conversation-level span that encompasses all operations for a conversation"""
        if not self._initialized:
            return None

        # End any existing conversation span
        if conversation_id in self.conversation_spans:
            prev_span = self.conversation_spans[conversation_id]
            if prev_span:
                prev_span.end()

        span = self.start_span(
            "conversation",
            "INTERNAL",
            {
                "conversation_id": conversation_id,
                "user_query_preview": user_query[:100],
                "query_length": len(user_query)
            }
        )

        self.conversation_spans[conversation_id] = span
        return span

    def end_conversation_span(self, conversation_id: str):
        """End a conversation-level span"""
        if conversation_id in self.conversation_spans:
            span = self.conversation_spans[conversation_id]
            if span:
                span.end()
            del self.conversation_spans[conversation_id]

    def log_user_input(self, conversation_id: str, user_input: str):
        """Log user input as an event in the conversation span"""
        if conversation_id in self.conversation_spans:
            span = self.conversation_spans[conversation_id]
            if span:
                span.add_event(
                    "user_input",
                    {
                        "input_text": user_input,
                        "input_length": len(user_input),
                        "timestamp": datetime.now().isoformat()
                    }
                )

    def log_response(self, conversation_id: str, response: str, response_type: str = "text"):
        """Log response as an event in the conversation span"""
        if conversation_id in self.conversation_spans:
            span = self.conversation_spans[conversation_id]
            if span:
                span.add_event(
                    "response",
                    {
                        "response_text": response,
                        "response_length": len(response),
                        "response_type": response_type,
                        "timestamp": datetime.now().isoformat()
                    }
                )

    def log_tool_call(self, conversation_id: str, tool_name: str, tool_input: Dict[str, Any], tool_output: str, success: bool = True):
        """Log tool call as an event in the conversation span"""
        if conversation_id in self.conversation_spans:
            span = self.conversation_spans[conversation_id]
            if span:
                span.add_event(
                    "tool_call",
                    {
                        "tool_name": tool_name,
                        "tool_input": str(tool_input),
                        "tool_output": tool_output,
                        "success": success,
                        "timestamp": datetime.now().isoformat()
                    }
                )

    def log_io_operation(self, conversation_id: str, operation_type: str, operation_details: str, duration_ms: float):
        """Log I/O operation as an event in the conversation span"""
        if conversation_id in self.conversation_spans:
            span = self.conversation_spans[conversation_id]
            if span:
                span.add_event(
                    "io_operation",
                    {
                        "operation_type": operation_type,
                        "operation_details": operation_details,
                        "duration_ms": duration_ms,
                        "timestamp": datetime.now().isoformat()
                    }
                )

    def create_trace_correlation_id(self, operation_type: str, operation_details: Dict[str, Any] = None) -> str:
        """Create a unique correlation ID for linking related operations"""
        correlation_id = f"{operation_type}_{uuid.uuid4().hex[:8]}"

        self.trace_correlations[correlation_id] = {
            "operation_type": operation_type,
            "operation_details": operation_details or {},
            "created_at": datetime.now().isoformat(),
            "related_operations": []
        }

        return correlation_id

    def link_operations(self, parent_correlation_id: str, child_correlation_id: str):
        """Link child operation to parent operation"""
        if parent_correlation_id in self.trace_correlations:
            self.trace_correlations[parent_correlation_id]["related_operations"].append(child_correlation_id)

    def get_trace_correlation(self, correlation_id: str) -> Dict[str, Any]:
        """Get trace correlation information"""
        return self.trace_correlations.get(correlation_id, {})

    def log_correlated_operation(self, correlation_id: str, operation_type: str, operation_details: str, duration_ms: float):
        """Log an operation with correlation ID"""
        if correlation_id in self.trace_correlations:
            self.trace_correlations[correlation_id]["related_operations"].append({
                "operation_type": operation_type,
                "operation_details": operation_details,
                "duration_ms": duration_ms,
                "timestamp": datetime.now().isoformat()
            })


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
                    'attributes': json.dumps(dict(span.attributes)),
                    'context.trace_id': format_trace_id(span.context.trace_id),
                    'context.span_id': format_span_id(span.context.span_id),
                    'context.trace_state': str(span.context.trace_state)
                }

                # Extract generic input/output for convenience
                try:
                    attrs = dict(span.attributes)
                    def _first(keys):
                        for k in keys:
                            if k in attrs:
                                return attrs.get(k)
                        return None
                    input_val = _first(['input.value', 'tool.input'])
                    output_val = _first(['output.value', 'tool.output'])
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

# Global unified tracing manager instance
unified_tracing_manager = UnifiedTracingManager()
