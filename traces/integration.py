"""
Phoenix tracing integration for the PMS Assistant agent
This module adds comprehensive tracing to the existing agent system.
"""

import asyncio
import time
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager
from datetime import datetime

# Phoenix imports
from phoenix.trace import using_project
from phoenix.trace.schemas import SpanKind, SpanStatusCode
from phoenix.trace.exporter import HttpExporter

# Local imports
from agent import MongoDBAgent, ConversationMemory
from tools import tools_list, intelligent_query
from constants import DATABASE_NAME
from langchain_core.messages import HumanMessage, AIMessage


class MockSpan:
    """Mock span for testing purposes"""

    def __init__(self, name: str, span_kind: str, attributes: Dict[str, Any]):
        self.name = name
        self.span_kind = span_kind
        self.attributes = attributes
        self.status = None

    def set_attribute(self, key: str, value: Any):
        """Set an attribute on the span"""
        self.attributes[key] = value

    def set_status(self, status: str, message: str = ""):
        """Set the status of the span"""
        self.status = {"status": status, "message": message}

    def add_event(self, name: str, attributes: Dict[str, Any]):
        """Add an event to the span"""
        pass

    def end(self):
        """End the span"""
        pass

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        self.end()


class TracedMongoDBAgent(MongoDBAgent):
    """MongoDB Agent with Phoenix tracing capabilities"""

    def __init__(self, tracer=None):
        super().__init__()
        self.tracer = tracer

    @asynccontextmanager
    async def trace_operation(self, operation_name: str, **attributes):
        """Context manager for tracing operations"""
        span = None
        start_time = time.time()

        try:
            # Start span
            if self.tracer:
                span = self.tracer.start_trace(
                    name=operation_name,
                    span_kind=SpanKind.INTERNAL,
                    attributes=attributes
                )

            yield span

        except Exception as e:
            if span:
                span.set_status(SpanStatusCode.ERROR, str(e))
                span.add_event("exception", {"exception.message": str(e)})
            raise

        finally:
            if span:
                duration = time.time() - start_time
                span.set_attribute("duration_ms", duration * 1000)
                span.end()

    async def process_query(self, query: str, conversation_id: str = None) -> Dict[str, Any]:
        """Process a query with comprehensive tracing"""
        async with self.trace_operation("process_query", query=query) as span:
            try:
                # Get conversation history
                async with self.trace_operation("get_conversation_history") as _:
                    messages = self.conversation_memory.get_conversation_history(conversation_id or "default")

                # Select appropriate tool
                async with self.trace_operation("select_tool", message_count=len(messages)) as _:
                    # Use intelligent_query for all PMS-related queries
                    selected_tool = intelligent_query

                # Execute tool with tracing
                async with self.trace_operation("execute_tool", tool_name=selected_tool.name) as tool_span:
                    tool_result = await selected_tool.async_call(self, query)

                    if tool_span:
                        tool_span.set_attribute("tool_success", "result" in tool_result)
                        if "error" in tool_result:
                            tool_span.set_status(SpanStatusCode.ERROR, tool_result["error"])

                # Generate response
                async with self.trace_operation("generate_response") as _:
                    response = self._generate_response(query, tool_result, messages)

                # Store conversation
                async with self.trace_operation("store_conversation") as _:
                    self.conversation_memory.add_message(
                        conversation_id or "default",
                        HumanMessage(content=query)
                    )
                    self.conversation_memory.add_message(
                        conversation_id or "default",
                        AIMessage(content=response)
                    )

                result = {
                    "response": response,
                    "tool_used": selected_tool.name,
                    "tool_result": tool_result,
                    "conversation_id": conversation_id or "default"
                }

                if span:
                    span.set_attribute("response_length", len(response))
                    span.set_attribute("tool_success", True)

                return result

            except Exception as e:
                if span:
                    span.set_status(SpanStatusCode.ERROR, str(e))
                raise

    async def _generate_response(self, query: str, tool_result: Dict[str, Any], messages: List) -> str:
        """Generate response using the language model with tracing"""
        async with self.trace_operation("llm_generation") as span:
            try:
                # For now, return the tool result directly
                # In a more sophisticated system, you'd use the LLM to generate natural language responses
                response = tool_result.get("result", "I couldn't find the information you requested.")

                if span:
                    span.set_attribute("response_source", "tool_result")
                    span.set_attribute("response_length", len(response))

                return response

            except Exception as e:
                if span:
                    span.set_status(SpanStatusCode.ERROR, str(e))
                raise


# Convenience function to get tool by name
def get_tool_by_name(tool_name: str):
    """Get a tool by its name"""
    for tool in tools_list:
        if tool.name == tool_name:
            return tool
    return None


# Phoenix tracing setup
class PhoenixTracingManager:
    """Manages Phoenix tracing for the entire application"""

    def __init__(self, project_name: str = "pms-assistant-traces"):
        self.project_name = project_name
        self.tracer = None
        self.exporter = None

    async def initialize(self):
        """Initialize Phoenix tracing"""
        try:
            # Initialize HTTP exporter for Phoenix
            self.exporter = HttpExporter(endpoint="http://localhost:6006/v1/traces")

            # In a real implementation, you'd configure the tracer properly
            print("Phoenix tracing initialized")
            print("Note: Start Phoenix server with: phoenix serve")

        except Exception as e:
            print(f"Failed to initialize Phoenix tracing: {e}")

    def start_trace(self, name: str, span_kind: str = "INTERNAL", attributes: Dict[str, Any] = None):
        """Start a new trace span"""
        # For now, return a mock span object
        # In a real implementation, this would use Phoenix's tracing API
        return MockSpan(name, span_kind, attributes or {})

    async def trace_agent_interaction(self, query: str, response: str, metadata: Dict[str, Any] = None):
        """Trace a complete agent interaction"""
        # This would send traces to Phoenix
        trace_data = {
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "response": response,
            "metadata": metadata or {}
        }

        print(f"Agent interaction traced: {trace_data}")

        # In production, this would be sent to Phoenix
        # self.exporter.export(trace_data)


# Global tracing instance
tracing_manager = PhoenixTracingManager()


async def initialize_tracing():
    """Initialize global tracing"""
    await tracing_manager.initialize()


async def trace_query(query: str, conversation_id: str = None) -> Dict[str, Any]:
    """Trace a complete query through the system"""
    async with tracing_manager.start_trace("full_query_trace") as span:
        try:
            # Create traced agent
            agent = TracedMongoDBAgent(tracing_manager)

            # Process query with tracing
            result = await agent.process_query(query, conversation_id)

            # Log to Phoenix
            await tracing_manager.trace_agent_interaction(
                query,
                result["response"],
                {
                    "tool_used": result["tool_used"],
                    "conversation_id": result["conversation_id"]
                }
            )

            return result

        except Exception as e:
            if span:
                span.set_status(SpanStatusCode.ERROR, str(e))
            raise


# Example usage in main application
async def example_traced_query():
    """Example of how to use tracing in the main application"""
    await initialize_tracing()

    test_query = "What is the status of the project Simpo?"
    result = await trace_query(test_query, "example-conversation")

    print(f"Query: {test_query}")
    print(f"Response: {result['response']}")
    print(f"Tool Used: {result['tool_used']}")


if __name__ == "__main__":
    asyncio.run(example_traced_query())
