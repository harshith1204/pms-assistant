#!/usr/bin/env python3
"""
FastAPI backend for MongoDB Project Management System
"""
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import asyncio
from mongodb_agent import MongoDBAgent, mongodb_tools
import json

app = FastAPI(title="Project Management System", version="1.0.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global agent instance
agent = MongoDBAgent()

# Pydantic models
class Project(BaseModel):
    name: str
    description: str
    status: str = Field(default="planning", pattern="^(planning|active|in_progress|completed|on_hold)$")
    priority: str = Field(default="medium", pattern="^(low|medium|high|critical)$")
    start_date: str
    end_date: Optional[str] = None
    team_members: List[str] = []
    budget: Optional[float] = None
    progress: int = Field(default=0, ge=0, le=100)

class Task(BaseModel):
    title: str
    description: Optional[str] = None
    project_name: str
    assigned_to: Optional[str] = None
    status: str = Field(default="pending", pattern="^(pending|in_progress|completed|blocked)$")
    priority: str = Field(default="medium", pattern="^(low|medium|high|critical)$")
    due_date: Optional[str] = None
    completed_date: Optional[str] = None

class UpdateProject(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    end_date: Optional[str] = None
    team_members: Optional[List[str]] = None
    budget: Optional[float] = None
    progress: Optional[int] = None

class UpdateTask(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assigned_to: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[str] = None
    completed_date: Optional[str] = None

class DatabaseStats(BaseModel):
    total_projects: int
    active_projects: int
    total_tasks: int
    completed_tasks: int
    team_members: List[str]

# Startup event
@app.on_event("startup")
async def startup_event():
    """Connect to MongoDB on startup"""
    try:
        await agent.connect()
        # Ensure collections exist
        await agent.run("Create a collection called 'projects' in the ProjectManagement database if it doesn't exist")
        await agent.run("Create a collection called 'tasks' in the ProjectManagement database if it doesn't exist")
    except Exception as e:
        print(f"Failed to connect to MongoDB: {e}")

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Disconnect from MongoDB on shutdown"""
    await agent.disconnect()

# Direct MongoDB operations
async def execute_mongodb_operation(operation: str, params: Dict[str, Any]) -> Any:
    """Execute a direct MongoDB operation using MCP"""
    try:
        result = await mongodb_tools.execute_tool(operation, params)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MongoDB operation failed: {str(e)}")

# API Endpoints

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serve the main HTML page"""
    with open("static/index.html", "r") as f:
        return HTMLResponse(content=f.read())

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "connected": agent.connected}

@app.get("/api/stats", response_model=DatabaseStats)
async def get_stats():
    """Get database statistics"""
    try:
        # Get all projects
        projects_result = await execute_mongodb_operation("find", {
            "database": "ProjectManagement",
            "collection": "projects",
            "filter": {},
            "limit": 1000
        })
        
        # Get all tasks
        tasks_result = await execute_mongodb_operation("find", {
            "database": "ProjectManagement",
            "collection": "tasks",
            "filter": {},
            "limit": 1000
        })
        
        # Parse results
        projects = json.loads(projects_result) if isinstance(projects_result, str) else projects_result
        tasks = json.loads(tasks_result) if isinstance(tasks_result, str) else tasks_result
        
        # Calculate stats
        active_projects = len([p for p in projects if p.get("status") in ["active", "in_progress"]])
        completed_tasks = len([t for t in tasks if t.get("status") == "completed"])
        
        # Get unique team members
        all_members = set()
        for project in projects:
            if "team_members" in project:
                all_members.update(project["team_members"])
        
        return DatabaseStats(
            total_projects=len(projects),
            active_projects=active_projects,
            total_tasks=len(tasks),
            completed_tasks=completed_tasks,
            team_members=sorted(list(all_members))
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Project endpoints
@app.get("/api/projects")
async def get_projects():
    """Get all projects"""
    try:
        result = await execute_mongodb_operation("find", {
            "database": "ProjectManagement",
            "collection": "projects",
            "filter": {},
            "limit": 100
        })
        return json.loads(result) if isinstance(result, str) else result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/projects", status_code=status.HTTP_201_CREATED)
async def create_project(project: Project):
    """Create a new project"""
    try:
        project_dict = project.dict()
        project_dict["created_at"] = datetime.utcnow().isoformat()
        
        result = await execute_mongodb_operation("insert-one", {
            "database": "ProjectManagement",
            "collection": "projects",
            "document": project_dict
        })
        return {"message": "Project created successfully", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/projects/{project_name}")
async def get_project(project_name: str):
    """Get a specific project by name"""
    try:
        result = await execute_mongodb_operation("find-one", {
            "database": "ProjectManagement",
            "collection": "projects",
            "filter": {"name": project_name}
        })
        if not result:
            raise HTTPException(status_code=404, detail="Project not found")
        return json.loads(result) if isinstance(result, str) else result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/projects/{project_name}")
async def update_project(project_name: str, update: UpdateProject):
    """Update a project"""
    try:
        update_dict = {k: v for k, v in update.dict().items() if v is not None}
        update_dict["updated_at"] = datetime.utcnow().isoformat()
        
        result = await execute_mongodb_operation("update-one", {
            "database": "ProjectManagement",
            "collection": "projects",
            "filter": {"name": project_name},
            "update": {"$set": update_dict}
        })
        return {"message": "Project updated successfully", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/projects/{project_name}")
async def delete_project(project_name: str):
    """Delete a project"""
    try:
        result = await execute_mongodb_operation("delete-one", {
            "database": "ProjectManagement",
            "collection": "projects",
            "filter": {"name": project_name}
        })
        return {"message": "Project deleted successfully", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Task endpoints
@app.get("/api/tasks")
async def get_tasks(project_name: Optional[str] = None):
    """Get all tasks, optionally filtered by project"""
    try:
        filter_dict = {"project_name": project_name} if project_name else {}
        result = await execute_mongodb_operation("find", {
            "database": "ProjectManagement",
            "collection": "tasks",
            "filter": filter_dict,
            "limit": 100
        })
        return json.loads(result) if isinstance(result, str) else result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/tasks", status_code=status.HTTP_201_CREATED)
async def create_task(task: Task):
    """Create a new task"""
    try:
        task_dict = task.dict()
        task_dict["created_at"] = datetime.utcnow().isoformat()
        
        result = await execute_mongodb_operation("insert-one", {
            "database": "ProjectManagement",
            "collection": "tasks",
            "document": task_dict
        })
        return {"message": "Task created successfully", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/tasks/{task_id}")
async def update_task(task_id: str, update: UpdateTask):
    """Update a task"""
    try:
        update_dict = {k: v for k, v in update.dict().items() if v is not None}
        update_dict["updated_at"] = datetime.utcnow().isoformat()
        
        # If task is marked as completed, set completed_date
        if update.status == "completed" and "completed_date" not in update_dict:
            update_dict["completed_date"] = datetime.utcnow().isoformat()
        
        result = await execute_mongodb_operation("update-one", {
            "database": "ProjectManagement",
            "collection": "tasks",
            "filter": {"_id": {"$oid": task_id}},
            "update": {"$set": update_dict}
        })
        return {"message": "Task updated successfully", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str):
    """Delete a task"""
    try:
        result = await execute_mongodb_operation("delete-one", {
            "database": "ProjectManagement",
            "collection": "tasks",
            "filter": {"_id": {"$oid": task_id}}
        })
        return {"message": "Task deleted successfully", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Agent endpoint for natural language queries
@app.post("/api/agent/query")
async def agent_query(query: Dict[str, str]):
    """Process natural language queries using the MongoDB agent"""
    try:
        response = await agent.run(query["query"])
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)