from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import asyncio
from contextlib import asynccontextmanager
import uvicorn

from agent import MongoDBAgent
from websocket_handler import handle_chat_websocket, ws_manager

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

    yield

    # Shutdown
    print("Shutting down MongoDB Agent...")
    await mongodb_agent.disconnect()
    print("MongoDB Agent disconnected.")

# Create FastAPI app
app = FastAPI(
    title="PMS Assistant API",
    description="Project Management System Assistant with MongoDB integration",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "PMS Assistant API", "status": "running"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

@app.get("/conversations")
async def get_conversations(limit: int = 50):
    """Get all conversations"""
    from agent import conversation_memory
    conversations = await conversation_memory.get_all_conversations(limit=limit)
    return {"conversations": conversations}

@app.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get a specific conversation with its messages"""
    from agent import conversation_memory
    messages = await conversation_memory.load_conversation_from_db(conversation_id, limit=100)
    
    # Convert messages to dict format
    message_dicts = []
    for msg in messages:
        msg_dict = {
            "type": msg.__class__.__name__,
            "content": str(msg.content)
        }
        if hasattr(msg, "tool_call_id"):
            msg_dict["tool_call_id"] = msg.tool_call_id
        message_dicts.append(msg_dict)
    
    return {"conversation_id": conversation_id, "messages": message_dicts}

@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation"""
    from agent import conversation_memory
    
    # Delete from database
    if conversation_memory.conversations_collection:
        await conversation_memory.conversations_collection.delete_one({"conversation_id": conversation_id})
    if conversation_memory.messages_collection:
        await conversation_memory.messages_collection.delete_many({"conversation_id": conversation_id})
    
    # Clear from memory
    conversation_memory.clear_conversation(conversation_id)
    
    return {"status": "deleted", "conversation_id": conversation_id}

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket endpoint for streaming chat"""
    global mongodb_agent

    # Initialize agent if not already done (for testing/development)
    if not mongodb_agent:
        print("Initializing MongoDB Agent for WebSocket...")
        mongodb_agent = MongoDBAgent()
        await mongodb_agent.connect()

    await handle_chat_websocket(websocket, mongodb_agent)

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
