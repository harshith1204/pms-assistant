#!/usr/bin/env python3
"""
Traced MongoDB Agent for Phoenix integration
This module integrates Phoenix tracing into the main MongoDB agent.
"""

import asyncio
import time
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager
from datetime import datetime

# Phoenix imports
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from phoenix.trace.exporter import HttpExporter

# Local imports
from agent import MongoDBAgent, ConversationMemory, llm_with_tools, tools_list
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage, ToolMessage


class PhoenixSpanManager:
    """Manages Phoenix spans for the agent"""

    def __init__(self):
        self.tracer_provider = None
        self.tracer = None
        self._initialized = False

    async def initialize(self):
        """Initialize Phoenix tracing"""
        if self._initialized:
            return

        try:
            # Set up OpenTelemetry tracer provider
            self.tracer_provider = TracerProvider()
            trace.set_tracer_provider(self.tracer_provider)

            # Add console exporter for development
            console_exporter = ConsoleSpanExporter()
            span_processor = BatchSpanProcessor(console_exporter)
            self.tracer_provider.add_span_processor(span_processor)

            # Try to add Phoenix HTTP exporter
            try:
                phoenix_exporter = HttpExporter(endpoint="http://localhost:6006/v1/traces")
                phoenix_processor = BatchSpanProcessor(phoenix_exporter)
                self.tracer_provider.add_span_processor(phoenix_processor)
                print("✅ Phoenix HTTP exporter configured for agent tracing")
            except Exception as e:
                print(f"⚠️  Phoenix server not available for agent tracing: {e}")

            # Get the tracer
            self.tracer = trace.get_tracer(__name__)
            self._initialized = True
            print("✅ Phoenix tracing initialized for agent")

        except Exception as e:
            print(f"❌ Failed to initialize Phoenix tracing for agent: {e}")
            import traceback
            traceback.print_exc()

    def start_span(self, name: str, span_kind: str = "INTERNAL", attributes: Dict[str, Any] = None):
        """Start a new trace span"""
        if not self.tracer:
            return None

        try:
            span = self.tracer.start_span(
                name=name,
                kind=getattr(trace.SpanKind, span_kind.upper(), trace.SpanKind.INTERNAL),
                attributes=attributes
            )
            return span
        except Exception as e:
            print(f"Error starting span '{name}': {e}")
            return None

    def end_span(self, span, status: str = "OK", message: str = ""):
        """End a span with status"""
        if not span:
            return

        try:
            if status == "ERROR":
                span.set_status(Status(StatusCode.ERROR, message))
            span.end()
        except Exception as e:
            print(f"Error ending span: {e}")


class TracedMongoDBAgent(MongoDBAgent):
    """MongoDB Agent with Phoenix tracing capabilities"""

    def __init__(self, max_steps: int = 8, system_prompt: Optional[str] = None):
        super().__init__(max_steps, system_prompt)
        self.span_manager = PhoenixSpanManager()
        self.tracing_enabled = False

    async def initialize_tracing(self):
        """Initialize tracing for this agent"""
        await self.span_manager.initialize()
        self.tracing_enabled = True

    @asynccontextmanager
    async def trace_operation(self, operation_name: str, **attributes):
        """Context manager for tracing operations"""
        span = None
        start_time = time.time()

        try:
            if self.tracing_enabled:
                span = self.span_manager.start_span(operation_name, attributes=attributes)

            yield span

        except Exception as e:
            if span:
                self.span_manager.end_span(span, "ERROR", str(e))
            raise

        finally:
            if span:
                duration = time.time() - start_time
                span.set_attribute("duration_ms", duration * 1000)
                self.span_manager.end_span(span)

    async def run(self, query: str, conversation_id: Optional[str] = None) -> str:
        """Run the agent with comprehensive tracing"""
        async with self.trace_operation("agent_run", query=query, conversation_id=conversation_id) as span:
            try:
                if not self.connected:
                    await self.connect()

                # Use default conversation ID if none provided
                if not conversation_id:
                    conversation_id = f"conv_{int(time.time())}"

                async with self.trace_operation("get_conversation_context") as _:
                    # Get conversation history
                    conversation_context = conversation_memory.get_recent_context(conversation_id)

                async with self.trace_operation("build_messages") as _:
                    # Build messages with optional system instruction
                    messages: List[BaseMessage] = []
                    if self.system_prompt:
                        messages.append(SystemMessage(content=self.system_prompt))
                    messages.extend(conversation_context)

                    # Add current user message
                    human_message = HumanMessage(content=query)
                    messages.append(human_message)

                async with self.trace_operation("llm_interaction", message_count=len(messages)) as llm_span:
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
                            result = response.content
                            if llm_span:
                                llm_span.set_attribute("final_response", result[:100])
                            return result

                        # Execute requested tools sequentially
                        messages.append(response)
                        for tool_call in response.tool_calls:
                            async with self.trace_operation("tool_execution",
                                                           tool_name=tool_call["name"]) as tool_span:
                                try:
                                    tool = next((t for t in tools_list if t.name == tool_call["name"]), None)
                                    if not tool:
                                        # If tool not found, surface an error message and stop
                                        error_msg = f"Tool '{tool_call['name']}' not found."
                                        messages.append(ToolMessage(tool_call_id=tool_call["id"], content=error_msg))
                                        if tool_span:
                                            tool_span.set_attribute("error", error_msg)
                                        break

                                    # Execute the tool
                                    tool_result = await tool.invoke(tool_call)

                                    # Add tool result to messages
                                    messages.append(ToolMessage(tool_call_id=tool_call["id"], content=tool_result))

                                    if tool_span:
                                        tool_span.set_attribute("tool_success", True)
                                        tool_span.set_attribute("tool_result_length", len(str(tool_result)))

                                except Exception as e:
                                    error_msg = f"Error executing tool '{tool_call['name']}': {str(e)}"
                                    messages.append(ToolMessage(tool_call_id=tool_call["id"], content=error_msg))
                                    if tool_span:
                                        tool_span.set_attribute("error", error_msg)
                                    break

                        steps += 1

                    # If we've exhausted the max steps, return the last response
                    if last_response:
                        result = last_response.content
                        if llm_span:
                            llm_span.set_attribute("final_response", result[:100])
                            llm_span.set_attribute("steps_taken", steps)
                        return result
                    else:
                        error_result = "No response generated after maximum steps."
                        if llm_span:
                            llm_span.set_attribute("error", error_result)
                        return error_result

            except Exception as e:
                if span:
                    span.set_attribute("error", str(e))
                print(f"Error in traced agent run: {e}")
                raise

    async def connect(self):
        """Connect to MongoDB with tracing"""
        async with self.trace_operation("mongodb_connect") as span:
            try:
                await super().connect()
                if span:
                    span.set_attribute("connection_success", True)
            except Exception as e:
                if span:
                    span.set_attribute("connection_success", False)
                    span.set_attribute("error", str(e))
                raise

    async def run_streaming(self, query: str, websocket=None, conversation_id: Optional[str] = None):
        """Run the agent with streaming and tracing wrappers."""
        async with self.trace_operation("agent_run_streaming", query=query, conversation_id=conversation_id) as span:
            try:
                # Ensure tracing is initialized if called directly
                if not self.tracing_enabled:
                    await self.initialize_tracing()

                # Defer to base implementation for streaming callbacks
                async for chunk in super().run_streaming(query=query, websocket=websocket, conversation_id=conversation_id):
                    if span and chunk:
                        # Record that we streamed some output (bounded for safety)
                        span.set_attribute("streaming_chunk_len", len(str(chunk)) if chunk else 0)
                    yield chunk
            except Exception as e:
                if span:
                    span.set_attribute("error", str(e))
                raise


# Global instances
phoenix_span_manager = PhoenixSpanManager()
conversation_memory = ConversationMemory()


def get_traced_agent() -> TracedMongoDBAgent:
    """Get a traced agent instance"""
    return TracedMongoDBAgent()


async def initialize_global_tracing():
    """Initialize global tracing"""
    await phoenix_span_manager.initialize()


async def trace_agent_query(query: str, conversation_id: str = None) -> str:
    """Trace a complete agent query"""
    agent = get_traced_agent()
    await agent.initialize_tracing()
    return await agent.run(query, conversation_id)


# Example usage
async def example_traced_query():
    """Example of how to use the traced agent"""
    await initialize_global_tracing()

    test_query = "What is the status of the project Simpo?"
    result = await trace_agent_query(test_query, "example-conversation")

    print(f"Query: {test_query}")
    print(f"Response: {result}")


if __name__ == "__main__":
    asyncio.run(example_traced_query())
