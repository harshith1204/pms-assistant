from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
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
    print("RAGTool initialized successfully!")
    yield

    # Shutdown
    print("Shutting down MongoDB Agent...")
    await mongodb_agent.disconnect()
    print("MongoDB Agent disconnected.")

# Resolve optional ROOT_PATH for deployments behind a reverse proxy or subpath
ROOT_PATH = os.getenv("ROOT_PATH", "").rstrip("/")

# Create FastAPI app
app = FastAPI(
    title="PMS Assistant API",
    description="Project Management System Assistant with MongoDB integration and WebSocket support",
    version="1.0.0",
    docs_url="/docs",  # Swagger UI at /docs
    redoc_url="/redoc",  # ReDoc at /redoc
    openapi_url="/openapi.json",  # OpenAPI schema at /openapi.json
    lifespan=lifespan,
    root_path=ROOT_PATH,
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

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket endpoint for streaming chat with MongoDB Agent.

    This endpoint provides real-time streaming chat functionality with the following features:

    Message Types:
    - "connected": Sent when client connects successfully
    - "user_message": Acknowledgment of received user message
    - "llm_start": Indicates LLM processing has started
    - "token": Streams individual tokens as they're generated
    - "thought": Streams thinking/reasoning tokens
    - "tool_start": Indicates a tool is being executed
    - "tool_end": Tool execution completed (with output preview unless explicitly enabled)
    - "llm_end": LLM processing completed
    - "planner_result": Result from planner execution (when force_planner=true)
    - "planner_error": Error from planner execution
    - "complete": Chat session completed
    - "error": Error message
    - "pong": Response to ping for connection keepalive

    Usage Example:
    ```javascript
    const ws = new WebSocket('ws://localhost:7000/ws/chat');

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log(data.type, data);
    };

    // Send a message
    ws.send(JSON.stringify({
        message: "Your message here",
        conversation_id: "optional_conversation_id",
        planner: false  // Set to true to force planner usage
    }));

    // Send ping for keepalive
    ws.send(JSON.stringify({ type: "ping" }));
    ```

    Args:
        websocket: The WebSocket connection object

    Returns:
        None (streaming responses sent via WebSocket)
    """
    global mongodb_agent

    # Initialize agent if not already done (for testing/development)
    if not mongodb_agent:
        print("Initializing MongoDB Agent for WebSocket...")
        mongodb_agent = MongoDBAgent()
        await mongodb_agent.initialize_tracing()
        await mongodb_agent.connect()

    await handle_chat_websocket(websocket, mongodb_agent)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=7000,
        reload=True,
        log_level="info",
        proxy_headers=True,
        forwarded_allow_ips="*",
        root_path=ROOT_PATH or None,
    )
