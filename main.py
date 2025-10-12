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
from mongo.conversations import ensure_conversation_client_connected
from mongo.conversations import conversation_mongo_client, CONVERSATIONS_DB_NAME, CONVERSATIONS_COLLECTION_NAME
from mongo.conversations import update_message_reaction
from mongo.constants import mongodb_tools, DATABASE_NAME
from mongo.constants import mongodb_tools, DATABASE_NAME
from bson import ObjectId
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


class ReactionRequest(BaseModel):
    conversation_id: str
    message_id: str
    liked: Optional[bool] = None
    feedback: Optional[str] = None

class WorkItemCreateRequest(BaseModel):
    title: str
    description: Optional[str] = ""
    project_identifier: Optional[str] = None
    project_id: Optional[str] = None
    created_by: Optional[str] = None

class WorkItemCreateResponse(BaseModel):
    id: str
    title: str
    description: str
    projectIdentifier: Optional[str] = None
    sequenceId: Optional[int] = None
    link: Optional[str] = None


class WorkItemCreateRequest(BaseModel):
    title: str
    description: str
    projectId: Optional[str] = None

class WorkItemCreateResponse(BaseModel):
    id: str
    title: str
    description: str
    projectIdentifier: Optional[str] = None
    sequenceId: Optional[str | int] = None
    link: Optional[str] = None

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
    lifespan=lifespan,
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
                "liked": m.get("liked"),
                "feedback": m.get("feedback"),
            })
        return {"id": conversation_id, "messages": norm}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/work-items", response_model=WorkItemCreateResponse)
async def create_work_item(req: WorkItemCreateRequest):
    """Create a minimal work item in MongoDB 'workItem' collection.

    Fields stored: title, description, project (identifier), sequenceId, createdAt/updatedAt.
    """
    try:
        if not mongodb_tools.client:
            # Ensure Mongo connected via direct client
            await mongodb_tools.connect()

        db = mongodb_tools.client[DATABASE_NAME]
        coll = db["workItem"]

        # Derive next sequence per project identifier (best-effort)
        seq: Optional[int] = None
        filt = {"project.identifier": req.project_identifier} if req.project_identifier else {}
        try:
            cursor = coll.find(filt, {"sequenceId": 1}).sort("sequenceId", -1).limit(1)
            top = await cursor.to_list(length=1)
            if top and isinstance(top[0], dict):
                seq_val = top[0].get("sequenceId")
                if isinstance(seq_val, int):
                    seq = seq_val + 1
            if seq is None:
                seq = 1
        except Exception:
            seq = None

        from datetime import datetime
        now_iso = datetime.utcnow().isoformat()

        doc = {
            "title": (req.title or "").strip(),
            "description": (req.description or "").strip(),
            "createdAt": now_iso,
            "updatedAt": now_iso,
        }
        if req.project_identifier:
            doc["project"] = {"identifier": req.project_identifier}
        if seq is not None:
            doc["sequenceId"] = seq
        if req.created_by:
            doc["createdBy"] = {"name": req.created_by}

        result = await coll.insert_one(doc)

        return WorkItemCreateResponse(
            id=str(result.inserted_id),
            title=doc["title"],
            description=doc["description"],
            projectIdentifier=req.project_identifier,
            sequenceId=seq,
            link=None,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/conversations/reaction")
async def set_reaction(req: ReactionRequest):
    """Set like/dislike and optional feedback on an assistant message."""
    try:
        ok = await update_message_reaction(
            conversation_id=req.conversation_id,
            message_id=req.message_id,
            liked=req.liked,
            feedback=req.feedback,
        )
        if not ok:
            raise HTTPException(status_code=404, detail="Message not found")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/work-items", response_model=WorkItemCreateResponse)
async def create_work_item(req: WorkItemCreateRequest):
    """Create a work item document in MongoDB."""
    try:
        # Ensure Mongo is connected
        await mongodb_tools.connect()

        client = getattr(mongodb_tools, "client", None)
        if client is None:
            raise HTTPException(status_code=500, detail="Database client not available")

        db = client[DATABASE_NAME]
        doc = {
            "title": (req.title or "").strip(),
            "description": (req.description or "").strip(),
            "createdAt": ws_manager._now().isoformat() if hasattr(ws_manager, "_now") else "",
            "updatedAt": ws_manager._now().isoformat() if hasattr(ws_manager, "_now") else "",
        }
        if req.projectId:
            # Store minimal reference; full embedding can be done by later updaters
            doc["project"] = {"_id": req.projectId}

        result = await db["workItem"].insert_one(doc)
        inserted_id = str(getattr(result, "inserted_id", ""))

        return WorkItemCreateResponse(
            id=inserted_id,
            title=doc["title"],
            description=doc["description"],
        )
    except HTTPException:
        raise
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


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=7000,
        reload=True,
        log_level="info",
        forwarded_allow_ips="*"
        )
