from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import asyncio
from contextlib import asynccontextmanager
import uvicorn
from dotenv import load_dotenv
from generate.router import router as generate_router

# Load environment variables from .env file
load_dotenv()

from agent import MongoDBAgent
import os
from websocket_handler import handle_chat_websocket, ws_manager
from qdrant.initializer import RAGTool
from mongo.conversations import ensure_conversation_client_connected
from mongo.conversations import conversation_mongo_client, CONVERSATIONS_DB_NAME, CONVERSATIONS_COLLECTION_NAME
# Pydantic models for API requests/responses
class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    conversation_id: str
    timestamp: str

class ToolCall(BaseModel):
    name: str
    arguments: Dict[str, Any]
    result: Optional[str] = None

class Message(BaseModel):
    id: str
    type: str  # "user", "assistant", "tool", "thought"
    content: str
    timestamp: str
    tool_name: Optional[str] = None
    tool_output: Optional[Any] = None

# Global MongoDB agent instance
mongodb_agent = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage the lifespan of the FastAPI application"""
    global mongodb_agent

    # Startup
    print("Starting MongoDB Agent...")
    mongodb_agent = MongoDBAgent()
    await mongodb_agent.connect()
    print("MongoDB Agent connected successfully!")
    await RAGTool.initialize()
    # Ensure conversation DB connection pool is ready
    try:
        await ensure_conversation_client_connected()
    except Exception as e:
        print(f"Warning: Conversations DB not connected: {e}")
    print("RAGTool initialized successfully!")
    yield

    # Shutdown
    print("Shutting down MongoDB Agent...")
    await mongodb_agent.disconnect()
    print("MongoDB Agent disconnected.")

# Create FastAPI app
app = FastAPI(
    title="PMS Assistant API",
    description="Project Management System Assistant with MongoDB integration and WebSocket support",
    version="1.0.0",
    docs_url="/docs",  # Swagger UI at /docs
    redoc_url="/redoc",  # ReDoc at /redoc
    openapi_url="/openapi.json",  # OpenAPI schema at /openapi.json
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Vite dev server
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include generation-related API routes
app.include_router(generate_router)

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "PMS Assistant API", "status": "running"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/conversations")
async def list_conversations():
    """List conversation ids and titles from Mongo."""
    try:
        coll = await conversation_mongo_client.get_collection(CONVERSATIONS_DB_NAME, CONVERSATIONS_COLLECTION_NAME)
        cursor = coll.find({}, {"conversationId": 1, "messages": {"$slice": -1}, "updatedAt": 1}).sort("updatedAt", -1).limit(100)
        results = []
        async for doc in cursor:
            conv_id = doc.get("conversationId")
            last = (doc.get("messages") or [{}])[-1] if doc.get("messages") else None
            title = None
            if last and isinstance(last, dict):
                content = str(last.get("content") or "").strip()
                if content:
                    title = content[:60]
            results.append({
                "id": conv_id,
                "title": title or f"Conversation {conv_id}",
                "updatedAt": doc.get("updatedAt"),
            })
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get a conversation's messages."""
    try:
        coll = await conversation_mongo_client.get_collection(CONVERSATIONS_DB_NAME, CONVERSATIONS_COLLECTION_NAME)
        doc = await coll.find_one({"conversationId": conversation_id})
        if not doc:
            return {"id": conversation_id, "messages": []}
        messages = doc.get("messages") or []
        # Normalize
        norm = []
        for m in messages:
            if not isinstance(m, dict):
                continue
            norm.append({
                "id": m.get("id") or "",
                "type": m.get("type") or "assistant",
                "content": m.get("content") or "",
                "timestamp": m.get("timestamp") or "",
            })
        return {"id": conversation_id, "messages": norm}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket endpoint for streaming chat with MongoDB Agent."""
    global mongodb_agent

    # Initialize agent if not already done (for testing/development)
    if not mongodb_agent:
        print("Initializing MongoDB Agent for WebSocket...")
        mongodb_agent = MongoDBAgent()
        await mongodb_agent.connect()

    await handle_chat_websocket(websocket, mongodb_agent)


@app.get("/sse/chat")
async def sse_chat(request: Request, message: str, conversation_id: Optional[str] = None):
    """Server-Sent Events endpoint that streams chat events as JSON lines.

    This mirrors the WebSocket protocol by emitting the same event objects via SSE.
    Frontend can consume with EventSource and reuse the same handlers.
    """
    global mongodb_agent

    # Ensure agent is ready (dev convenience)
    if not mongodb_agent:
        mongodb_agent = MongoDBAgent()
        await mongodb_agent.connect()

    import json as _json
    import asyncio as _asyncio

    class _SSEAdapter:
        def __init__(self, q: "_asyncio.Queue[str]"):
            self.q = q

        async def send_json(self, payload: dict):
            try:
                data = _json.dumps(payload, ensure_ascii=False)
            except Exception:
                data = _json.dumps({"type": "error", "message": "serialization error"})
            await self.q.put(f"data: {data}\n\n")

    async def event_stream():
        q: _asyncio.Queue[str] = _asyncio.Queue()
        adapter = _SSEAdapter(q)

        # Initial connected event
        await q.put(f"data: {_json.dumps({'type': 'connected', 'timestamp': __import__('datetime').datetime.now().isoformat()})}\n\n")

        async def runner():
            try:
                # Drive the streaming generator to completion; tokens are sent via adapter
                async for _ in mongodb_agent.run_streaming(
                    query=message,
                    websocket=adapter,
                    conversation_id=conversation_id
                ):
                    pass
            finally:
                await q.put(f"data: {_json.dumps({'type': 'complete', 'conversation_id': conversation_id or ''})}\n\n")

        task = _asyncio.create_task(runner())
        try:
            while True:
                # Client disconnect handling
                if await request.is_disconnected():
                    task.cancel()
                    break
                chunk = await q.get()
                yield chunk
        finally:
            if not task.done():
                task.cancel()

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=headers)

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=7000,
        reload=True,
        log_level="info",
        forwarded_allow_ips="*"
        )
