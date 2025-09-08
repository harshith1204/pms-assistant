from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import asyncio
from contextlib import asynccontextmanager
import uvicorn

from agent import MongoDBAgent
from websocket_handler import handle_chat_websocket, ws_manager
from pydantic import BaseModel
from typing import Optional
import os
from langchain_openai import ChatOpenAI
from langchain_mongodb.agent_toolkit import MongoDBDatabase, MongoDBDatabaseToolkit
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.mongodb import MongoDBSaver
from constants import MONGODB_CONNECTION_STRING, DATABASE_NAME

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

class MQLQueryRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None

class MQLQueryResponse(BaseModel):
    response: str
    conversation_id: str
    timestamp: str

# Global MongoDB agent instance
mongodb_agent = None
text_to_mql_agent = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage the lifespan of the FastAPI application"""
    global mongodb_agent
    global text_to_mql_agent

    # Startup
    print("Starting MongoDB Agent...")
    mongodb_agent = MongoDBAgent()
    await mongodb_agent.connect()
    print("MongoDB Agent connected successfully!")

    # Initialize optional Text-to-MQL agent if environment is configured
    try:
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if openai_api_key:
            db = MongoDBDatabase.from_connection_string(MONGODB_CONNECTION_STRING, database=DATABASE_NAME)
            toolkit = MongoDBDatabaseToolkit(db)
            checkpointer = MongoDBSaver(db.client)
            llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2, api_key=openai_api_key)
            text_to_mql_agent = create_react_agent(llm, toolkit.get_tools(), checkpointer=checkpointer)
            print("Text-to-MQL LangGraph agent initialized.")
        else:
            print("OPENAI_API_KEY not set; skipping Text-to-MQL agent init.")
    except Exception as e:
        print(f"Failed to initialize Text-to-MQL agent: {e}")

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

@app.post("/mql/query", response_model=MQLQueryResponse)
async def run_text_to_mql(request: MQLQueryRequest):
    """Run a Text-to-MQL query via LangGraph agent if initialized."""
    global text_to_mql_agent
    if text_to_mql_agent is None:
        raise HTTPException(status_code=503, detail="Text-to-MQL agent is not initialized.")

    try:
        conv_id = request.conversation_id or "http_api"
        result = text_to_mql_agent.invoke({
            "messages": [("user", request.message)],
            "config": {"thread_id": conv_id}
        })
        # LangGraph returns a dict with messages; extract the last assistant content
        content = ""
        try:
            msgs = result.get("messages", [])
            for m in reversed(msgs):
                if isinstance(m, (list, tuple)) and m[0] == "assistant":
                    content = m[1]
                    break
                if hasattr(m, "type") and getattr(m, "type") == "ai":
                    content = getattr(m, "content", "")
                    break
        except Exception:
            content = str(result)

        return MQLQueryResponse(
            response=content or str(result),
            conversation_id=conv_id,
            timestamp=datetime.now().isoformat()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Text-to-MQL error: {e}")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
