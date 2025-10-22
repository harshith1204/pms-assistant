#!/usr/bin/env python3
"""
Authentication utilities for RBAC system
Handles member authentication and context extraction
"""

from fastapi import Header, HTTPException, Depends
from typing import Optional, Annotated
from motor.motor_asyncio import AsyncIOMotorClient
import uuid
from bson.binary import Binary

from rbac.permissions import MemberContext, PermissionError
from mongo.constants import mongodb_tools, DATABASE_NAME, uuid_str_to_mongo_binary


async def get_member_by_id(member_id: str) -> Optional[dict]:
    """Fetch member details from MongoDB by member ID
    
    Args:
        member_id: UUID string of the member
        
    Returns:
        Member document or None if not found
    """
    try:
        if not mongodb_tools.client:
            await mongodb_tools.connect()
        
        db = mongodb_tools.client[DATABASE_NAME]
        members_collection = db["members"]
        
        # Convert string UUID to MongoDB Binary format
        member_uuid = uuid_str_to_mongo_binary(member_id)
        
        # Find member by memberId field
        member = await members_collection.find_one({"memberId": member_uuid})
        
        return member
    except Exception as e:
        print(f"Error fetching member: {e}")
        return None


async def get_member_projects(member_id: str) -> list[str]:
    """Get all project IDs that a member has access to
    
    Args:
        member_id: UUID string of the member
        
    Returns:
        List of project ID strings
    """
    try:
        if not mongodb_tools.client:
            await mongodb_tools.connect()
        
        db = mongodb_tools.client[DATABASE_NAME]
        members_collection = db["members"]
        
        # Convert string UUID to MongoDB Binary format
        member_uuid = uuid_str_to_mongo_binary(member_id)
        
        # Find all project memberships for this member
        cursor = members_collection.find({"memberId": member_uuid})
        projects = []
        
        async for member_doc in cursor:
            project = member_doc.get("project", {})
            project_id = project.get("_id")
            if project_id:
                # Convert Binary UUID to string
                if hasattr(project_id, 'hex'):
                    projects.append(str(uuid.UUID(bytes=project_id)))
                else:
                    projects.append(str(project_id))
        
        return projects
    except Exception as e:
        print(f"Error fetching member projects: {e}")
        return []


async def get_member_project_memberships(member_id: str) -> dict[str, dict]:
    """Return mapping of project_id -> membership info for a member.

    Reads from the `members` collection which stores memberships per project.
    Only project membership is relevant for access decisions.
    """
    try:
        if not mongodb_tools.client:
            await mongodb_tools.connect()
        db = mongodb_tools.client[DATABASE_NAME]
        members_collection = db["members"]

        member_uuid = uuid_str_to_mongo_binary(member_id)
        cursor = members_collection.find({"memberId": member_uuid})

        project_memberships: dict[str, dict] = {}
        async for member_doc in cursor:
            project = member_doc.get("project", {})
            project_id = project.get("_id")
            if not project_id:
                continue
            if hasattr(project_id, 'hex'):
                project_id_str = str(uuid.UUID(bytes=project_id))
            else:
                project_id_str = str(project_id)

            # Store minimal membership info (can be expanded later if needed)
            project_memberships[project_id_str] = {
                "project_id": project_id_str,
                "membership_id": str(member_doc.get("_id", "")),
            }

        return project_memberships
    except Exception as e:
        print(f"Error fetching member project memberships: {e}")
        return {}


async def get_current_member(
    x_member_id: Annotated[Optional[str], Header()] = None,
    authorization: Annotated[Optional[str], Header()] = None,
) -> MemberContext:
    """FastAPI dependency to get the current authenticated member
    
    Extracts member ID from headers and builds MemberContext.
    Priority: X-Member-Id header > Authorization header > default
    
    Args:
        x_member_id: Member ID from X-Member-Id header
        authorization: Bearer token from Authorization header
        
    Returns:
        MemberContext with member details and permissions
        
    Raises:
        HTTPException: If member not found or invalid credentials
    """
    # Try to extract member_id from headers
    member_id = None
    
    # Priority 1: X-Member-Id header
    if x_member_id:
        member_id = x_member_id
    # Priority 2: Extract from Authorization Bearer token
    elif authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        # In production, validate JWT and extract member_id
        # For now, treat the token as the member_id
        member_id = token
    
    # For development: use default member if none provided
    if not member_id:
        # This should be removed in production or require authentication
        print("Warning: No member authentication provided, using default")
        # You can set a default member ID from environment or raise error
        import os
        member_id = os.getenv("DEFAULT_MEMBER_ID")
        if not member_id:
            raise HTTPException(
                status_code=401,
                detail="Authentication required. Please provide X-Member-Id header or Authorization token."
            )
    
    # Fetch one member doc to obtain profile details, and compile project memberships
    member_doc = await get_member_by_id(member_id)
    project_memberships = await get_member_project_memberships(member_id)
    project_ids = list(project_memberships.keys()) or await get_member_projects(member_id)

    if not member_doc and not project_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Member not found: {member_id}"
        )

    # Basic profile info
    if member_doc:
        display_name = member_doc.get("displayName") or member_doc.get("name", "")
        email = member_doc.get("email", "") or None
        member_type = member_doc.get("type")
    else:
        display_name = ""
        email = None
        member_type = None

    # Build member context
    context = MemberContext(
        member_id=member_id,
        name=display_name,
        email=(email or ""),
        project_ids=project_ids,
        project_memberships=project_memberships,
        type=member_type,
        business_id=None,  # Can be extracted from project if needed
    )
    
    return context


class PermissionChecker:  # Deprecated
    """Deprecated: No-op permission checker kept for compatibility.

    All access is enforced via project membership filters. This class simply
    ensures the member is authenticated and optionally checks project access
    if a project_id parameter is present.
    """

    def __init__(self, *_ignored):
        pass

    async def __call__(
        self,
        member: Annotated[MemberContext, Depends(get_current_member)],
        **kwargs,
    ) -> MemberContext:
        project_id = (
            kwargs.get("project_id") or kwargs.get("projectId") or kwargs.get("project")
        )
        if project_id and not member.can_access_project(project_id):
            raise HTTPException(status_code=403, detail=f"Access denied to project: {project_id}")
        return member


def require_permissions(*_ignored):  # Deprecated
    """Compatibility helper: returns a no-op checker that authenticates member.

    Replace usages with Depends(get_current_member) over time.
    """
    return PermissionChecker([])


class ResourceOwnerChecker:
    """Check if member owns or has access to a specific resource"""
    
    def __init__(self, project_id_param: str = "project_id"):
        self.project_id_param = project_id_param
    
    async def __call__(
        self, 
        member: Annotated[MemberContext, Depends(get_current_member)],
        **kwargs
    ) -> MemberContext:
        """Check if member can access the resource's project
        
        Args:
            member: Current member context
            kwargs: Path/query parameters containing project_id
            
        Returns:
            MemberContext if authorized
            
        Raises:
            HTTPException: If member cannot access the project
        """
        project_id = kwargs.get(self.project_id_param)
        
        if project_id and not member.can_access_project(project_id):
            raise HTTPException(
                status_code=403,
                detail=f"Access denied to project: {project_id}"
            )
        
        return member


# Helper functions for manual permission checks

async def check_permission(member: MemberContext, *_ignored) -> bool:
    """Deprecated: Always returns True; access is governed by project membership."""
    return True


async def require_permission(member: MemberContext, *_ignored):
    """Deprecated: No-op; use project access checks where appropriate."""
    return None


async def check_project_access(member: MemberContext, project_id: str) -> bool:
    """Check if member can access a project (non-raising)"""
    return member.can_access_project(project_id)


async def require_project_access(member: MemberContext, project_id: str):
    """Require project access or raise exception"""
    if not member.can_access_project(project_id):
        raise HTTPException(
            status_code=403,
            detail=f"Access denied to project: {project_id}"
        )
