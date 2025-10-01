from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import asyncio
from contextlib import asynccontextmanager
import uvicorn

from agent import MongoDBAgent, phoenix_span_manager
from traces.setup import EvaluationPipeline
from traces.upload_dataset import PhoenixDatasetUploader
from websocket_handler import handle_chat_websocket, ws_manager
from qdrant.qdrant_initializer import RAGTool
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
    print("Starting MongoDB Agent with Phoenix tracing...")
    await phoenix_span_manager.initialize()
    mongodb_agent = MongoDBAgent()
    await mongodb_agent.initialize_tracing()
    await mongodb_agent.connect()
    print("MongoDB Agent connected successfully!")
    await RAGTool.initialize()
    print("RAGTool initialized successfully!")
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
        await phoenix_span_manager.initialize()
        mongodb_agent = MongoDBAgent()
        await mongodb_agent.initialize_tracing()
        await mongodb_agent.connect()

    await handle_chat_websocket(websocket, mongodb_agent)


@app.post("/eval/run")
async def run_evaluation(sample_size: int | None = None):
    """Run the evaluation pipeline and return the report."""
    pipeline = EvaluationPipeline()
    await pipeline.initialize()
    results = await pipeline.run_evaluation(sample_size=sample_size)
    report = await pipeline.generate_evaluation_report(results)
    return {"report": report}


@app.post("/phoenix/dataset/upload")
async def upload_phoenix_dataset():
    """Build and save the Phoenix evaluation dataset JSON locally."""
    uploader = PhoenixDatasetUploader()
    dataset = uploader.load_test_dataset()
    if not dataset:
        raise HTTPException(status_code=400, detail="No dataset loaded")
    dataset_info = uploader.create_phoenix_dataset(dataset)
    if not dataset_info.get("success"):
        raise HTTPException(status_code=500, detail="Failed to create Phoenix dataset")
    success = uploader.upload_to_phoenix(dataset_info)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save dataset JSON")
    return {"success": True, "entries": len(dataset)}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
