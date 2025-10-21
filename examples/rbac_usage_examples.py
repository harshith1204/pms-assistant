#!/usr/bin/env python3
"""
RBAC Usage Examples

Demonstrates how to use the RBAC system in various scenarios.
"""

from fastapi import FastAPI, Depends, HTTPException
from typing import Annotated, Optional, List
from pydantic import BaseModel

# Import RBAC components
from rbac import (
    get_current_member,
    MemberContext,
    Permission,
    require_permissions,
    check_permission,
    require_permission,
    check_project_access,
    require_project_access,
)
from rbac.filters import (
    apply_member_filter,
    get_member_project_filter,
    apply_member_pipeline_filter,
    filter_results_by_access,
)

app = FastAPI()


# ============================================================================
# EXAMPLE 1: Basic Route Protection
# ============================================================================

@app.get("/work-items")
async def list_work_items(
    member: Annotated[MemberContext, Depends(require_permissions(Permission.WORK_ITEM_READ))]
):
    """
    Route is protected by WORK_ITEM_READ permission.
    Only members with this permission can access.
    """
    return {
        "message": f"Hello {member.name}!",
        "role": member.role.value,
        "accessible_projects": member.project_ids
    }


# ============================================================================
# EXAMPLE 2: Multiple Permission Requirements
# ============================================================================

@app.post("/work-items")
async def create_work_item(
    member: Annotated[MemberContext, Depends(
        require_permissions(Permission.WORK_ITEM_CREATE, Permission.WORK_ITEM_ASSIGN)
    )]
):
    """
    Requires both WORK_ITEM_CREATE and WORK_ITEM_ASSIGN permissions.
    """
    return {"message": "Work item created"}


# ============================================================================
# EXAMPLE 3: Manual Permission Checks
# ============================================================================

@app.get("/dashboard")
async def get_dashboard(
    member: Annotated[MemberContext, Depends(get_current_member)]
):
    """
    Get current member without requiring specific permissions.
    Perform manual permission checks inside the function.
    """
    dashboard_data = {
        "user": member.name,
        "role": member.role.value
    }
    
    # Check permissions manually
    if await check_permission(member, Permission.WORK_ITEM_READ):
        dashboard_data["can_read_work_items"] = True
    
    if await check_permission(member, Permission.PAGE_CREATE):
        dashboard_data["can_create_pages"] = True
    
    if member.is_admin():
        dashboard_data["admin_features"] = ["user_management", "settings"]
    
    return dashboard_data


# ============================================================================
# EXAMPLE 4: Project Access Control
# ============================================================================

class WorkItemCreate(BaseModel):
    title: str
    description: str
    project_id: str


@app.post("/projects/{project_id}/work-items")
async def create_work_item_in_project(
    project_id: str,
    item: WorkItemCreate,
    member: Annotated[MemberContext, Depends(require_permissions(Permission.WORK_ITEM_CREATE))]
):
    """
    Create work item with project access verification.
    """
    # Verify member has access to the project
    await require_project_access(member, project_id)
    
    # Member has access, proceed with creation
    return {
        "message": "Work item created",
        "project_id": project_id,
        "created_by": member.name
    }


# ============================================================================
# EXAMPLE 5: MongoDB Query Filtering
# ============================================================================

@app.get("/my-work-items")
async def get_my_work_items(
    member: Annotated[MemberContext, Depends(require_permissions(Permission.WORK_ITEM_READ))],
    status: Optional[str] = None
):
    """
    Query work items with automatic member filtering.
    """
    from mongo.constants import mongodb_tools, DATABASE_NAME
    
    # Build base query
    base_query = {}
    if status:
        base_query["status"] = status
    
    # Apply member filter (automatically restricts to member's projects)
    filtered_query = apply_member_filter(base_query, "workItem", member)
    
    # Execute query
    db = mongodb_tools.client[DATABASE_NAME]
    work_items = await db["workItem"].find(filtered_query).to_list(100)
    
    return {
        "count": len(work_items),
        "items": work_items
    }


# ============================================================================
# EXAMPLE 6: Aggregation Pipeline with RBAC
# ============================================================================

@app.get("/work-items/by-status")
async def get_work_items_by_status(
    member: Annotated[MemberContext, Depends(require_permissions(Permission.WORK_ITEM_READ))]
):
    """
    Aggregate work items by status with member filtering.
    """
    from mongo.constants import mongodb_tools, DATABASE_NAME
    
    # Build aggregation pipeline
    pipeline = [
        {"$group": {
            "_id": "$status",
            "count": {"$sum": 1},
            "items": {"$push": "$$ROOT"}
        }},
        {"$sort": {"count": -1}}
    ]
    
    # Apply member filtering to pipeline
    filtered_pipeline = apply_member_pipeline_filter(pipeline, member)
    
    # Execute
    db = mongodb_tools.client[DATABASE_NAME]
    results = await db["workItem"].aggregate(filtered_pipeline).to_list(100)
    
    return {
        "groups": results,
        "filtered_by": "member_projects"
    }


# ============================================================================
# EXAMPLE 7: Admin-Only Endpoint
# ============================================================================

@app.get("/admin/all-members")
async def list_all_members(
    member: Annotated[MemberContext, Depends(require_permissions(Permission.ADMIN_FULL_ACCESS))]
):
    """
    Admin-only endpoint. Only members with ADMIN role can access.
    """
    from mongo.constants import mongodb_tools, DATABASE_NAME
    
    db = mongodb_tools.client[DATABASE_NAME]
    members = await db["members"].find({}).to_list(100)
    
    return {
        "count": len(members),
        "members": members
    }


# ============================================================================
# EXAMPLE 8: Conditional Logic Based on Role
# ============================================================================

@app.get("/projects/{project_id}")
async def get_project_details(
    project_id: str,
    member: Annotated[MemberContext, Depends(require_permissions(Permission.PROJECT_READ))]
):
    """
    Return different levels of detail based on member role.
    """
    from mongo.constants import mongodb_tools, DATABASE_NAME
    
    # Check project access
    if not member.can_access_project(project_id):
        raise HTTPException(status_code=403, detail="Access denied to this project")
    
    db = mongodb_tools.client[DATABASE_NAME]
    
    # Basic project info for all
    project_filter = get_member_project_filter(member, project_id)
    project = await db["project"].find_one(project_filter)
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    response = {
        "name": project.get("name"),
        "description": project.get("description"),
        "status": project.get("status")
    }
    
    # Add sensitive info for admins only
    if member.is_admin():
        response["settings"] = project.get("settings")
        response["financial_data"] = project.get("financials")
    
    # Add moderate detail for members
    elif member.role.value == "MEMBER":
        response["team_members"] = project.get("members")
    
    return response


# ============================================================================
# EXAMPLE 9: Post-Query Filtering
# ============================================================================

@app.get("/search/work-items")
async def search_work_items(
    query: str,
    member: Annotated[MemberContext, Depends(require_permissions(Permission.WORK_ITEM_READ))]
):
    """
    Search work items and filter results by member access.
    Useful when you can't apply filters at query time.
    """
    from mongo.constants import mongodb_tools, DATABASE_NAME
    
    db = mongodb_tools.client[DATABASE_NAME]
    
    # Perform text search (example - actual implementation may vary)
    search_query = {"$text": {"$search": query}}
    all_results = await db["workItem"].find(search_query).to_list(100)
    
    # Filter results to only those member can access
    accessible_results = filter_results_by_access(all_results, member, "workItem")
    
    return {
        "query": query,
        "total_found": len(all_results),
        "accessible": len(accessible_results),
        "results": accessible_results
    }


# ============================================================================
# EXAMPLE 10: Resource Ownership Check
# ============================================================================

@app.delete("/work-items/{item_id}")
async def delete_work_item(
    item_id: str,
    member: Annotated[MemberContext, Depends(require_permissions(Permission.WORK_ITEM_DELETE))]
):
    """
    Delete work item - only if member created it or is admin.
    """
    from mongo.constants import mongodb_tools, DATABASE_NAME
    from bson import ObjectId
    
    db = mongodb_tools.client[DATABASE_NAME]
    
    # Fetch the work item
    work_item = await db["workItem"].find_one({"_id": ObjectId(item_id)})
    
    if not work_item:
        raise HTTPException(status_code=404, detail="Work item not found")
    
    # Check if member owns the resource or is admin
    created_by = work_item.get("createdBy", {})
    creator_id = created_by.get("_id")
    
    is_owner = str(creator_id) == member.member_id
    
    if not (is_owner or member.is_admin()):
        raise HTTPException(
            status_code=403,
            detail="You can only delete work items you created"
        )
    
    # Delete the work item
    await db["workItem"].delete_one({"_id": ObjectId(item_id)})
    
    return {"message": "Work item deleted", "id": item_id}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
