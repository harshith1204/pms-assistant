#!/usr/bin/env python3
"""
RBAC-Protected Collection Endpoints

Example endpoints for Cycles and Modules with full RBAC protection.
These can be added to main.py or used as a reference.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Annotated, Optional, List, Dict, Any
from pydantic import BaseModel

from rbac import (
    get_current_member,
    MemberContext,
    Permission,
    require_permissions,
)
from rbac.filters import apply_member_filter
from mongo.constants import mongodb_tools, DATABASE_NAME


router = APIRouter(prefix="/api", tags=["collections"])


# ============================================================================
# CYCLES ENDPOINTS
# ============================================================================

class CycleResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    status: Optional[str] = None
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    projectName: Optional[str] = None


@router.get("/cycles", response_model=List[CycleResponse])
async def list_cycles(
    member: Annotated[MemberContext, Depends(require_permissions(Permission.CYCLE_READ))],
    status: Optional[str] = None,
    project_id: Optional[str] = None
):
    """
    List all cycles accessible to the member.
    
    - Members see only cycles from their projects
    - Admins see all cycles
    - Optional filters: status, project_id
    """
    if not mongodb_tools.client:
        await mongodb_tools.connect()
    
    db = mongodb_tools.client[DATABASE_NAME]
    coll = db["cycle"]
    
    # Build base query
    query = {}
    if status:
        query["status"] = status
    
    # Apply member-based filtering
    filtered_query = apply_member_filter(query, "cycle", member, project_id)
    
    # Execute query
    cursor = coll.find(filtered_query).limit(100)
    cycles = []
    
    async for doc in cursor:
        cycle_data = {
            "id": str(doc.get("_id", "")),
            "title": doc.get("title") or doc.get("name", ""),
            "description": doc.get("description"),
            "status": doc.get("status"),
            "startDate": doc.get("startDate"),
            "endDate": doc.get("endDate"),
        }
        
        # Extract project name if available
        project = doc.get("project", {})
        if isinstance(project, dict):
            cycle_data["projectName"] = project.get("name")
        
        cycles.append(CycleResponse(**cycle_data))
    
    return cycles


@router.get("/cycles/{cycle_id}", response_model=CycleResponse)
async def get_cycle(
    cycle_id: str,
    member: Annotated[MemberContext, Depends(require_permissions(Permission.CYCLE_READ))]
):
    """
    Get a specific cycle by ID.
    
    - Verifies member has access to the cycle's project
    """
    from bson import ObjectId
    
    if not mongodb_tools.client:
        await mongodb_tools.connect()
    
    db = mongodb_tools.client[DATABASE_NAME]
    coll = db["cycle"]
    
    # Fetch cycle
    try:
        cycle = await coll.find_one({"_id": ObjectId(cycle_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid cycle ID format")
    
    if not cycle:
        raise HTTPException(status_code=404, detail="Cycle not found")
    
    # Verify access using filter
    from rbac.filters import can_access_resource
    if not can_access_resource(cycle, member, "cycle"):
        raise HTTPException(status_code=403, detail="Access denied to this cycle")
    
    project = cycle.get("project", {})
    return CycleResponse(
        id=str(cycle["_id"]),
        title=cycle.get("title") or cycle.get("name", ""),
        description=cycle.get("description"),
        status=cycle.get("status"),
        startDate=cycle.get("startDate"),
        endDate=cycle.get("endDate"),
        projectName=project.get("name") if isinstance(project, dict) else None
    )


# ============================================================================
# MODULES ENDPOINTS
# ============================================================================

class ModuleResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    projectName: Optional[str] = None
    leadName: Optional[str] = None
    isFavourite: Optional[bool] = None


@router.get("/modules", response_model=List[ModuleResponse])
async def list_modules(
    member: Annotated[MemberContext, Depends(require_permissions(Permission.MODULE_READ))],
    project_id: Optional[str] = None
):
    """
    List all modules accessible to the member.
    
    - Members see only modules from their projects
    - Admins see all modules
    """
    if not mongodb_tools.client:
        await mongodb_tools.connect()
    
    db = mongodb_tools.client[DATABASE_NAME]
    coll = db["module"]
    
    # Build base query
    query = {}
    
    # Apply member-based filtering
    filtered_query = apply_member_filter(query, "module", member, project_id)
    
    # Execute query
    cursor = coll.find(filtered_query).limit(100)
    modules = []
    
    async for doc in cursor:
        module_data = {
            "id": str(doc.get("_id", "")),
            "title": doc.get("title") or doc.get("name", ""),
            "description": doc.get("description"),
            "isFavourite": doc.get("isFavourite"),
        }
        
        # Extract project name
        project = doc.get("project", {})
        if isinstance(project, dict):
            module_data["projectName"] = project.get("name")
        
        # Extract lead name
        lead = doc.get("lead", {})
        if isinstance(lead, dict):
            module_data["leadName"] = lead.get("name")
        
        modules.append(ModuleResponse(**module_data))
    
    return modules


@router.get("/modules/{module_id}", response_model=ModuleResponse)
async def get_module(
    module_id: str,
    member: Annotated[MemberContext, Depends(require_permissions(Permission.MODULE_READ))]
):
    """
    Get a specific module by ID.
    
    - Verifies member has access to the module's project
    """
    from bson import ObjectId
    
    if not mongodb_tools.client:
        await mongodb_tools.connect()
    
    db = mongodb_tools.client[DATABASE_NAME]
    coll = db["module"]
    
    # Fetch module
    try:
        module = await coll.find_one({"_id": ObjectId(module_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid module ID format")
    
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    
    # Verify access
    from rbac.filters import can_access_resource
    if not can_access_resource(module, member, "module"):
        raise HTTPException(status_code=403, detail="Access denied to this module")
    
    project = module.get("project", {})
    lead = module.get("lead", {})
    
    return ModuleResponse(
        id=str(module["_id"]),
        title=module.get("title") or module.get("name", ""),
        description=module.get("description"),
        projectName=project.get("name") if isinstance(project, dict) else None,
        leadName=lead.get("name") if isinstance(lead, dict) else None,
        isFavourite=module.get("isFavourite")
    )


# ============================================================================
# WORK ITEMS ENDPOINT (Additional - can replace the one in main.py)
# ============================================================================

class WorkItemListResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    displayBugNo: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    projectName: Optional[str] = None
    assignees: Optional[List[str]] = []


@router.get("/work-items", response_model=List[WorkItemListResponse])
async def list_work_items(
    member: Annotated[MemberContext, Depends(require_permissions(Permission.WORK_ITEM_READ))],
    status: Optional[str] = None,
    priority: Optional[str] = None,
    project_id: Optional[str] = None
):
    """
    List all work items accessible to the member.
    
    - Members see only work items from their projects
    - Admins see all work items
    - Optional filters: status, priority, project_id
    """
    if not mongodb_tools.client:
        await mongodb_tools.connect()
    
    db = mongodb_tools.client[DATABASE_NAME]
    coll = db["workItem"]
    
    # Build base query
    query = {}
    if status:
        query["status"] = status
    if priority:
        query["priority"] = priority
    
    # Apply member-based filtering
    filtered_query = apply_member_filter(query, "workItem", member, project_id)
    
    # Execute query
    cursor = coll.find(filtered_query).limit(100)
    work_items = []
    
    async for doc in cursor:
        # Extract assignee names
        assignees = []
        assignee_data = doc.get("assignee", [])
        if isinstance(assignee_data, list):
            for assignee in assignee_data:
                if isinstance(assignee, dict) and assignee.get("name"):
                    assignees.append(assignee["name"])
        
        item_data = {
            "id": str(doc.get("_id", "")),
            "title": doc.get("title", ""),
            "description": doc.get("description"),
            "displayBugNo": doc.get("displayBugNo"),
            "priority": doc.get("priority"),
            "status": doc.get("status"),
            "assignees": assignees,
        }
        
        # Extract project name
        project = doc.get("project", {})
        if isinstance(project, dict):
            item_data["projectName"] = project.get("name")
        
        work_items.append(WorkItemListResponse(**item_data))
    
    return work_items


# ============================================================================
# PAGES ENDPOINT (Additional - can replace the one in main.py)
# ============================================================================

class PageListResponse(BaseModel):
    id: str
    title: str
    visibility: Optional[str] = None
    projectName: Optional[str] = None
    createdByName: Optional[str] = None
    isFavourite: Optional[bool] = None


@router.get("/pages", response_model=List[PageListResponse])
async def list_pages(
    member: Annotated[MemberContext, Depends(require_permissions(Permission.PAGE_READ))],
    visibility: Optional[str] = None,
    project_id: Optional[str] = None
):
    """
    List all pages accessible to the member.
    
    - Members see only pages from their projects
    - Admins see all pages
    - Optional filters: visibility, project_id
    """
    if not mongodb_tools.client:
        await mongodb_tools.connect()
    
    db = mongodb_tools.client[DATABASE_NAME]
    coll = db["page"]
    
    # Build base query
    query = {}
    if visibility:
        query["visibility"] = visibility
    
    # Apply member-based filtering
    filtered_query = apply_member_filter(query, "page", member, project_id)
    
    # Execute query
    cursor = coll.find(filtered_query).limit(100)
    pages = []
    
    async for doc in cursor:
        page_data = {
            "id": str(doc.get("_id", "")),
            "title": doc.get("title", ""),
            "visibility": doc.get("visibility"),
            "isFavourite": doc.get("isFavourite"),
        }
        
        # Extract project name
        project = doc.get("project", {})
        if isinstance(project, dict):
            page_data["projectName"] = project.get("name")
        
        # Extract creator name
        created_by = doc.get("createdBy", {})
        if isinstance(created_by, dict):
            page_data["createdByName"] = created_by.get("name")
        
        pages.append(PageListResponse(**page_data))
    
    return pages


# To use this in main.py, add:
# from rbac.collection_endpoints import router as collection_router
# app.include_router(collection_router)
