"""WebSocket handler for streaming chat responses"""
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Any, AsyncGenerator
import json
import asyncio
from datetime import datetime
import uuid
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_ollama import ChatOllama
import time
import re

from constants import DATABASE_NAME

def _should_use_planner(message_text: str) -> bool:
    q = (message_text or "").lower()
    # Heuristics: group by / count / sum / avg / min / max / sort by / limit / between / in [ ... ] / comparisons
    triggers = ["group by","count","sum","avg","average","minimum","maximum","sort by","limit ","between "," in ["," in ["," this month"," last month"," this week"," last week"," today"," yesterday"]
    if any(t in q for t in triggers):
        return True
    # comparisons like field >= 10
    if re.search(r'\w+\s*(>=|<=|!=|==|=|>|<)\s*[^\s,]+', q):
        return True
    return False


class StreamingCallbackHandler(AsyncCallbackHandler):
    """Callback handler for streaming LLM responses"""

    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.start_time = None

    async def on_llm_start(self, *args, **kwargs):
        """Called when LLM starts generating"""
        self.start_time = time.time()
        await self.websocket.send_json({
            "type": "llm_start",
            "timestamp": datetime.now().isoformat()
        })

    async def on_llm_new_token(self, token: str, **kwargs):
        """Stream each token as it's generated"""
        await self.websocket.send_json({
            "type": "token",
            "content": token,
            "timestamp": datetime.now().isoformat()
        })

    async def on_llm_end(self, *args, **kwargs):
        """Called when LLM finishes generating"""
        elapsed_time = time.time() - self.start_time if self.start_time else 0
        await self.websocket.send_json({
            "type": "llm_end",
            "elapsed_time": elapsed_time,
            "timestamp": datetime.now().isoformat()
        })

    async def on_tool_start(self, serialized: Dict[str, Any], input_str: str, **kwargs):
        """Called when a tool starts executing"""
        tool_name = serialized.get("name", "Unknown Tool")
        await self.websocket.send_json({
            "type": "tool_start",
            "tool_name": tool_name,
            "input": input_str,
            "timestamp": datetime.now().isoformat()
        })

    async def on_tool_end(self, output: str, **kwargs):
        """Called when a tool finishes executing"""
        await self.websocket.send_json({
            "type": "tool_end",
            "output": output,
            "timestamp": datetime.now().isoformat()
        })

class WebSocketManager:
    """Manages WebSocket connections"""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        """Accept and store a new WebSocket connection"""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        print(f"Client {client_id} connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, client_id: str):
        """Remove a WebSocket connection"""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            print(f"Client {client_id} disconnected. Total connections: {len(self.active_connections)}")

    async def send_message(self, client_id: str, message: dict):
        """Send a message to a specific client"""
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_json(message)

    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients"""
        for client_id, connection in self.active_connections.items():
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"Error broadcasting to {client_id}: {e}")

# Global WebSocket manager instance
ws_manager = WebSocketManager()

async def handle_chat_websocket(websocket: WebSocket, mongodb_agent):
    """Handle WebSocket chat connections with streaming"""
    client_id = str(uuid.uuid4())

    try:
        await ws_manager.connect(websocket, client_id)

        # Send welcome message
        await websocket.send_json({
            "type": "connected",
            "client_id": client_id,
            "timestamp": datetime.now().isoformat()
        })

        while True:
            # Receive message from client
            data = await websocket.receive_json()

            if data.get("type") == "ping":
                # Handle ping/pong for connection keepalive
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": datetime.now().isoformat()
                })
                continue

            message = data.get("message", "")
            conversation_id = data.get("conversation_id") or f"conv_{client_id}"
            force_planner = data.get("planner", False)

            # Send user message acknowledgment
            await websocket.send_json({
                "type": "user_message",
                "content": message,
                "conversation_id": conversation_id,
                "timestamp": datetime.now().isoformat()
            })

            # Route to planner or LLM based on heuristics/flag
            if force_planner or _should_use_planner(message):
                # Use deterministic planner
                op_id = str(uuid.uuid4())
            else:
                # Use regular LLM with tool calling
                async for response_chunk in mongodb_agent.run_streaming(
                    query=message,
                    websocket=websocket,
                    conversation_id=conversation_id
                ):
                    # The streaming is handled internally by the callback handler
                    # Just iterate through the generator to complete the streaming
                    pass

            # Send completion message
            await websocket.send_json({
                "type": "complete",
                "conversation_id": conversation_id,
                "timestamp": datetime.now().isoformat()
            })

    except WebSocketDisconnect:
        ws_manager.disconnect(client_id)
        print(f"Client {client_id} disconnected")
    except Exception as e:
        print(f"WebSocket error for client {client_id}: {e}")
        await websocket.send_json({
            "type": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        })
        ws_manager.disconnect(client_id)
