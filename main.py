from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import asyncio
from contextlib import asynccontextmanager
import uvicorn

from mongodb_agent import MongoDBAgent

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

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, background_tasks: BackgroundTasks):
    """Handle chat requests"""
    global mongodb_agent

    try:
        if not mongodb_agent:
            raise HTTPException(status_code=500, detail="MongoDB agent not initialized")

        # Generate conversation ID if not provided
        conversation_id = request.conversation_id or f"conv_{asyncio.get_event_loop().time()}"

        # Run the agent with the user's message
        response = await mongodb_agent.run(request.message)

        return ChatResponse(
            response=response,
            conversation_id=conversation_id,
            timestamp=asyncio.get_event_loop().time().__str__()
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing chat request: {str(e)}")

@app.get("/api/databases")
async def list_databases():
    """List available databases"""
    try:
        if not mongodb_agent:
            raise HTTPException(status_code=500, detail="MongoDB agent not initialized")

        # Use the agent to list databases
        response = await mongodb_agent.run("List all available databases")
        return {"databases": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing databases: {str(e)}")

@app.get("/api/collections")
async def list_collections(database: str = "ProjectManagement"):
    """List collections in a database"""
    try:
        if not mongodb_agent:
            raise HTTPException(status_code=500, detail="MongoDB agent not initialized")

        # Use the agent to list collections
        response = await mongodb_agent.run(f"List all collections in the {database} database")
        return {"collections": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing collections: {str(e)}")

@app.get("/api/status")
async def get_status():
    """Get the current status of the MongoDB agent"""
    return {
        "agent_connected": mongodb_agent is not None and mongodb_agent.connected,
        "database_name": "ProjectManagement"
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
