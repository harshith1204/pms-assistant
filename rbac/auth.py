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

from rbac.permissions import MemberContext, Role, Permission, PermissionError
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


async def get_member_project_roles(member_id: str) -> dict[str, Role]:
    """Get a mapping of project_id -> Role for a member from members collection.
    
    Each document in `members` represents a membership of a member in a project
    and stores a `role` that should be interpreted as the role within that project.
    """
    try:
        if not mongodb_tools.client:
            await mongodb_tools.connect()
        db = mongodb_tools.client[DATABASE_NAME]
        members_collection = db["members"]

        member_uuid = uuid_str_to_mongo_binary(member_id)
        cursor = members_collection.find({"memberId": member_uuid})

        project_roles: dict[str, Role] = {}
        async for member_doc in cursor:
            project = member_doc.get("project", {})
            project_id = project.get("_id")
            if not project_id:
                continue
            if hasattr(project_id, 'hex'):
                project_id_str = str(uuid.UUID(bytes=project_id))
            else:
                project_id_str = str(project_id)

            role_str = (member_doc.get("role") or "VIEWER").upper()
            try:
                project_roles[project_id_str] = Role(role_str)
            except ValueError:
                project_roles[project_id_str] = Role.VIEWER

        return project_roles
    except Exception as e:
        print(f"Error fetching member project roles: {e}")
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
    
    # Fetch one member doc to obtain profile details, and compile project roles across memberships
    member_doc = await get_member_by_id(member_id)
    project_roles = await get_member_project_roles(member_id)
    project_ids = list(project_roles.keys()) or await get_member_projects(member_id)

    if not member_doc and not project_roles:
        raise HTTPException(
            status_code=404,
            detail=f"Member not found: {member_id}"
        )

    # Derive a conservative global role: default VIEWER; if any membership is MEMBER, elevate to MEMBER
    derived_global_role = Role.VIEWER
    if any(r in (Role.MEMBER, Role.ADMIN) for r in project_roles.values()):
        derived_global_role = Role.MEMBER

    # Extract role from member doc if present; otherwise fall back to derived role
    if member_doc:
        role_str = member_doc.get("role", derived_global_role.value)
        try:
            role = Role(role_str)
        except ValueError:
            print(f"Warning: Unknown role '{role_str}' for member {member_id}, defaulting to {derived_global_role.value}")
            role = derived_global_role
        display_name = member_doc.get("displayName") or member_doc.get("name", "")
        email = member_doc.get("email", "") or None
        member_type = member_doc.get("type")
    else:
        role = derived_global_role
        display_name = ""
        email = None
        member_type = None

    # Build member context
    context = MemberContext(
        member_id=member_id,
        name=display_name,
        email=(email or ""),
        role=role,
        project_ids=project_ids,
        project_roles=project_roles,
        type=member_type,
        business_id=None,  # Can be extracted from project if needed
    )
    
    return context


class PermissionChecker:
    """Dependency class to enforce project-scoped permissions.

    This checker prioritizes per-project permissions derived from the member's
    memberships. If a `project_id` is present in the endpoint's parameters,
    permissions are validated within that project's role. Otherwise, access is
    allowed and row-level filters will apply.
    """

    def __init__(self, required_permissions: list[Permission]):
        self.required_permissions = required_permissions

    async def __call__(
        self,
        member: Annotated[MemberContext, Depends(get_current_member)],
        **kwargs,
    ) -> MemberContext:
        """Validate required permissions in the context of the provided project.

        Args:
            member: Current member context
            kwargs: Path/query/body parameters (may include `project_id`)

        Returns:
            MemberContext if authorized

        Raises:
            HTTPException: If member lacks required permissions for the project
        """
        # Try common parameter names for project id
        project_id = (
            kwargs.get("project_id")
            or kwargs.get("projectId")
            or kwargs.get("project")
        )

        if project_id:
            # Enforce permissions within the specific project context
            missing_in_project: list[str] = []
            for perm in self.required_permissions:
                if not member.has_project_permission(perm, project_id):
                    missing_in_project.append(perm.value)
            if missing_in_project:
                raise HTTPException(
                    status_code=403,
                    detail=f"Insufficient project permissions for project {project_id}. Required: {missing_in_project}",
                )
        # If no project_id provided, allow; row-level project filters will restrict visibility
        return member


def require_permissions(*permissions: Permission):
    """Decorator factory to require specific permissions
    
    Usage:
        @app.get("/work-items")
        async def list_work_items(member: MemberContext = Depends(require_permissions(Permission.WORK_ITEM_READ))):
            ...
    """
    # Return a callable dependency (PermissionChecker instance). Do NOT wrap in Depends here
    # because usage sites already call Depends(require_permissions(...)), and double-wrapping
    # would pass a non-callable Depends object to FastAPI.
    return PermissionChecker(list(permissions))


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

async def check_permission(member: MemberContext, permission: Permission) -> bool:
    """Check if member has a permission (non-raising)"""
    return member.has_permission(permission)


async def require_permission(member: MemberContext, permission: Permission):
    """Require a permission or raise exception"""
    if not member.has_permission(permission):
        raise PermissionError(f"Missing required permission: {permission.value}")


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
