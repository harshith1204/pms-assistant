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

# MongoDB imports
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure


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

            # MongoDB span processor (our working solution)
            mongodb_processor = PhoenixSpanProcessor()
            self.tracer_provider.add_span_processor(mongodb_processor)

            # Start MongoDB span collector
            mongodb_span_collector.start_periodic_export()
            print("✅ MongoDB span processor and collector configured")

            self.tracer = trace.get_tracer(__name__)
            self._initialized = True
            print("✅ Unified tracing initialized with MongoDB storage")
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


class MongoDBSpanCollector:
    """Collects and exports spans to MongoDB"""

    def __init__(self):
        self.collected_spans = []
        self.mongodb_client = None
        self.database = None
        self.collection = None
        self.events_collection = None
        self.metrics_collection = None
        self.export_thread = None
        self.running = False
        self.batch_size = 50
        self.initialize_mongodb()

    def initialize_mongodb(self):
        """Initialize MongoDB connection"""
        try:
            from .config import PHOENIX_DB_CONFIG
            self.mongodb_client = MongoClient(PHOENIX_DB_CONFIG["connection_string"])
            self.database = self.mongodb_client[PHOENIX_DB_CONFIG["database"]]
            self.collection = self.database[PHOENIX_DB_CONFIG["collection"]]
            # Standardized collections
            self.events_collection = self.database["trace_events"]
            self.metrics_collection = self.database["metrics"]
            print("✅ MongoDB connection initialized for span collection")
        except Exception as e:
            print(f"❌ Failed to initialize MongoDB connection: {e}")
            self.mongodb_client = None

    def collect_span(self, span):
        """Collect a span for export to MongoDB"""
        if not self.mongodb_client:
            print("⚠️  MongoDB not connected, skipping span collection")
            return

        self.collected_spans.append(span)

        # If we have many spans, export them
        if len(self.collected_spans) >= self.batch_size:
            self.export_to_mongodb()

    def convert_span_to_dict(self, span):
        """Convert OpenTelemetry span to MongoDB document"""
        def format_timestamp(timestamp):
            """Convert OpenTelemetry timestamp to datetime"""
            if isinstance(timestamp, (int, float)):
                # Convert nanoseconds to datetime
                from datetime import datetime
                return datetime.fromtimestamp(timestamp / 1e9)
            return timestamp

        def _to_hex(value):
            """Convert to hex string"""
            if isinstance(value, int):
                return f"{value:032x}" if len(f"{value:x}") <= 32 else f"{value:016x}"
            if isinstance(value, str):
                v = value[2:] if value.startswith('0x') else value
                try:
                    return f"{int(v, 16):032x}"
                except:
                    return value
            return str(value)

        # Calculate duration if end_time is available
        duration_ms = None
        if span.start_time and span.end_time:
            duration_ms = (span.end_time - span.start_time) // 1_000_000  # Convert to milliseconds

        span_dict = {
            'trace_id': _to_hex(span.context.trace_id),
            'span_id': _to_hex(span.context.span_id),
            'parent_id': _to_hex(span.parent.span_id) if span.parent and hasattr(span.parent, 'span_id') else None,
            'name': span.name,
            'span_kind': str(span.kind),
            'kind': getattr(getattr(span, 'kind', None), 'name', str(getattr(span, 'kind', 'INTERNAL'))),
            'start_time': format_timestamp(span.start_time),
            'end_time': format_timestamp(span.end_time) if span.end_time else None,
            'duration_ms': duration_ms,
            'status_code': span.status.status_code.name,
            'status_message': span.status.description or '',
            'attributes': dict(span.attributes),
            'context': {
                'trace_id': _to_hex(span.context.trace_id),
                'span_id': _to_hex(span.context.span_id),
                'trace_state': str(span.context.trace_state)
            },
            'created_at': datetime.now()
        }

        # Extract input/output from attributes for convenience
        attrs = dict(span.attributes)
        if 'input.value' in attrs:
            span_dict['input'] = str(attrs['input.value'])
        if 'tool.input' in attrs:
            span_dict['input'] = str(attrs['tool.input'])
        if 'output.value' in attrs:
            span_dict['output'] = str(attrs['output.value'])
        if 'tool.output' in attrs:
            span_dict['output'] = str(attrs['tool.output'])

        # Do not attach events here; events are stored in dedicated collection

        return span_dict

    def export_to_mongodb(self):
        """Export collected spans to MongoDB"""
        if not self.collected_spans or not self.mongodb_client:
            return

        try:
            # Build documents for traces, events, and metrics
            trace_docs = []
            event_docs = []
            metric_docs = []

            for span in self.collected_spans:
                span_doc = self.convert_span_to_dict(span)
                trace_docs.append(span_doc)

                # Build event documents (one per event)
                if span.events:
                    for event in span.events:
                        event_docs.append({
                            'trace_id': span_doc['trace_id'],
                            'span_id': span_doc['span_id'],
                            'span_name': span_doc['name'],
                            'name': event.name,
                            'timestamp': event.timestamp if not isinstance(event.timestamp, (int, float)) else datetime.fromtimestamp(event.timestamp / 1e9),
                            'attributes': dict(event.attributes),
                            'created_at': datetime.now()
                        })

                # Build basic metrics document per span
                metric_docs.append({
                    'trace_id': span_doc['trace_id'],
                    'span_id': span_doc['span_id'],
                    'span_name': span_doc['name'],
                    'span_kind': span_doc.get('kind'),
                    'status_code': span_doc.get('status_code'),
                    'duration_ms': span_doc.get('duration_ms'),
                    'start_time': span_doc.get('start_time'),
                    'end_time': span_doc.get('end_time'),
                    'attributes_count': len(span_doc.get('attributes', {})),
                    'events_count': len(span.events or []),
                    'created_at': datetime.now()
                })

            # Insert traces
            if trace_docs:
                self.collection.insert_many(trace_docs, ordered=False)
                print(f"✅ Exported {len(trace_docs)} spans to MongoDB collection 'traces'")

                # Also store in time-based collection for better querying
                now = datetime.now()
                time_collection_name = f"traces_{now.strftime('%Y_%m')}"
                time_collection = self.database[time_collection_name]
                time_collection.insert_many(trace_docs, ordered=False)
                print(f"✅ Also stored in time-based collection: {time_collection_name}")

            # Insert events
            if event_docs and self.events_collection is not None:
                self.events_collection.insert_many(event_docs, ordered=False)
                print(f"✅ Exported {len(event_docs)} events to MongoDB collection 'trace_events'")

            # Insert metrics
            if metric_docs and self.metrics_collection is not None:
                self.metrics_collection.insert_many(metric_docs, ordered=False)
                print(f"✅ Exported {len(metric_docs)} metrics to MongoDB collection 'metrics'")

            # Clear collected spans
            self.collected_spans.clear()

        except Exception as e:
            print(f"❌ Error exporting spans to MongoDB: {e}")

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
        self.export_to_mongodb()  # Export any remaining spans

    def _periodic_export_worker(self):
        """Worker thread for periodic span export"""
        while self.running:
            time.sleep(5)  # Export every 5 seconds
            self.export_to_mongodb()

    def get_trace_by_id(self, trace_id):
        """Retrieve all spans for a given trace ID"""
        if not self.mongodb_client:
            return []

        try:
            return list(self.collection.find({'trace_id': trace_id}).sort('start_time', 1))
        except Exception as e:
            print(f"❌ Error retrieving trace {trace_id}: {e}")
            return []

    def get_recent_traces(self, limit=100):
        """Get recent traces"""
        if not self.mongodb_client:
            return []

        try:
            return list(self.collection.find().sort('start_time', -1).limit(limit))
        except Exception as e:
            print(f"❌ Error retrieving recent traces: {e}")
            return []

    def search_traces(self, query, limit=50):
        """Search traces by text query"""
        if not self.mongodb_client:
            return []

        try:
            search_pipeline = [
                {
                    '$search': {
                        'text': {
                            'query': query,
                            'path': ['name', 'status_message', 'attributes', 'events.name']
                        }
                    }
                },
                {'$limit': limit},
                {'$sort': {'start_time': -1}}
            ]

            return list(self.collection.aggregate(search_pipeline))
        except Exception as e:
            print(f"❌ Error searching traces: {e}")
            return []


class PhoenixSpanProcessor(SpanProcessor):
    """Custom span processor that sends spans to MongoDB collector"""

    def on_start(self, span, parent_context=None):
        """Called when a span starts"""
        pass

    def on_end(self, span):
        """Called when a span ends - send to MongoDB"""
        try:
            mongodb_span_collector.collect_span(span)
        except Exception as e:
            # Don't let span processing errors break the application
            print(f"Warning: Failed to collect span for MongoDB: {e}")

    def shutdown(self, timeout_millis=30000):
        """Shutdown the processor"""
        try:
            mongodb_span_collector.export_to_mongodb()
        except Exception as e:
            print(f"Warning: Failed to export spans during shutdown: {e}")

    def force_flush(self, timeout_millis=30000):
        """Force flush any pending spans"""
        try:
            mongodb_span_collector.export_to_mongodb()
        except Exception as e:
            print(f"Warning: Failed to flush spans: {e}")


# Global span collector
mongodb_span_collector = MongoDBSpanCollector()

# Global unified tracing manager instance
unified_tracing_manager = UnifiedTracingManager()
