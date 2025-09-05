from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Union
import asyncio
from contextlib import asynccontextmanager
import uvicorn

from mongodb_agent import MongoDBAgent, smithery_config
from websocket_handler import handle_chat_websocket, ws_manager
from agent_graph import AgentRuntime

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
agent_runtime: Optional[AgentRuntime] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage the lifespan of the FastAPI application"""
    global mongodb_agent, agent_runtime

    # Startup
    print("Starting MongoDB Agent...")
    mongodb_agent = MongoDBAgent()
    await mongodb_agent.connect()
    print("MongoDB Agent connected successfully!")
    
    # Initialize the new insight agent runtime
    print("Starting Insight Agent Runtime...")
    agent_runtime = AgentRuntime(smithery_config)
    await agent_runtime.start()
    print("Insight Agent Runtime started successfully!")

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
    
    if not mongodb_agent:
        await websocket.close(code=1003, reason="MongoDB agent not initialized")
        return
        
    await handle_chat_websocket(websocket, mongodb_agent)

@app.websocket("/ws/insights")
async def websocket_insights(websocket: WebSocket):
    """WebSocket endpoint for streaming insight agent progress"""
    global agent_runtime
    
    if not agent_runtime:
        await websocket.close(code=1003, reason="Insight agent not initialized")
        return
        
    await websocket.accept()
    
    try:
        while True:
            # Receive query from client
            data = await websocket.receive_json()
            query = data.get("query", "")
            conversation_id = data.get("conversation_id")
            
            if not query:
                await websocket.send_json({"type": "error", "message": "No query provided"})
                continue
                
            # Define progress callback
            async def progress_callback(event: dict):
                await websocket.send_json(event)
                
            # Run agent with progress streaming
            try:
                insights = await agent_runtime.ask_with_progress(
                    query, 
                    progress_callback=progress_callback,
                    conversation_id=conversation_id
                )
                
                # Send final result
                await websocket.send_json({
                    "type": "complete",
                    "insights": insights,
                    "conversation_id": conversation_id
                })
                
            except Exception as e:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Error processing query: {str(e)}"
                })
                
    except WebSocketDisconnect:
        print(f"WebSocket disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")
        await websocket.close()

# Keep a minimal HTTP endpoint for backward compatibility
@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, background_tasks: BackgroundTasks):
    """Handle chat requests (legacy HTTP endpoint)"""
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

@app.post("/ask")
async def ask(request: ChatRequest):
    """Ask the insight agent for data analysis"""
    global agent_runtime
    
    if agent_runtime is None:
        raise HTTPException(status_code=503, detail="Agent not ready")
        
    try:
        # Get insights from the planner-executor agent
        insights = await agent_runtime.ask(
            request.message, 
            conversation_id=request.conversation_id
        )
        
        return {
            "insights": insights,
            "conversation_id": request.conversation_id or f"conv_{asyncio.get_event_loop().time()}",
            "timestamp": asyncio.get_event_loop().time().__str__()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")

@app.get("/api/status")
async def get_status():
    """Get the current status of the MongoDB agent"""
    return {
        "agent_connected": mongodb_agent is not None and mongodb_agent.connected,
        "insight_agent_ready": agent_runtime is not None,
        "database_name": "ProjectManagement",
        "websocket_clients": len(ws_manager.active_connections),
        "supports_streaming": True
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
