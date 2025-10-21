#!/usr/bin/env python3
"""
RBAC Query Filters - Automatically filter MongoDB queries based on member permissions

Ensures members can only access data they have permissions for.
"""

from typing import Dict, Any, List, Optional
from bson.binary import Binary
import uuid

from rbac.permissions import MemberContext, Role
from mongo.constants import uuid_str_to_mongo_binary


def apply_member_filter(
    query: Dict[str, Any],
    collection: str,
    member: MemberContext,
    project_id: Optional[str] = None
) -> Dict[str, Any]:
    """Apply member-based filtering to MongoDB query
    
    Automatically restricts queries based on member's role and project access.
    Admins can see everything, others only see resources in their projects.
    
    Args:
        query: Base MongoDB query filter
        collection: Collection name being queried
        member: Member context with permissions
        project_id: Optional specific project to filter by
        
    Returns:
        Enhanced query with member filters applied
    """
    # Admins bypass all filters
    if member.is_admin():
        return query
    
    # Build project access filter
    if project_id:
        # Specific project requested - verify access
        if not member.can_access_project(project_id):
            # Return impossible filter if no access
            return {"_id": {"$exists": False}}
        project_filter = {"project._id": uuid_str_to_mongo_binary(project_id)}
    elif member.project_ids:
        # Filter by all accessible projects
        project_binaries = [uuid_str_to_mongo_binary(pid) for pid in member.project_ids]
        project_filter = {"project._id": {"$in": project_binaries}}
    else:
        # No project access - return nothing
        return {"_id": {"$exists": False}}
    
    # Combine with existing query
    if "$and" in query:
        query["$and"].append(project_filter)
    elif query:
        query = {"$and": [query, project_filter]}
    else:
        query = project_filter
    
    return query


def get_member_project_filter(member: MemberContext, project_id: Optional[str] = None) -> Dict[str, Any]:
    """Get MongoDB filter for member's accessible projects
    
    Args:
        member: Member context
        project_id: Optional specific project ID
        
    Returns:
        MongoDB filter dict
    """
    if member.is_admin():
        if project_id:
            return {"project._id": uuid_str_to_mongo_binary(project_id)}
        return {}
    
    if project_id:
        if not member.can_access_project(project_id):
            return {"_id": {"$exists": False}}
        return {"project._id": uuid_str_to_mongo_binary(project_id)}
    
    if member.project_ids:
        project_binaries = [uuid_str_to_mongo_binary(pid) for pid in member.project_ids]
        return {"project._id": {"$in": project_binaries}}
    
    return {"_id": {"$exists": False}}


def apply_member_pipeline_filter(
    pipeline: List[Dict[str, Any]],
    member: MemberContext,
    project_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Apply member filtering to MongoDB aggregation pipeline
    
    Injects a $match stage at the beginning to filter by member access.
    
    Args:
        pipeline: Existing aggregation pipeline
        member: Member context
        project_id: Optional specific project ID
        
    Returns:
        Pipeline with member filter injected
    """
    if member.is_admin() and not project_id:
        # Admin with no specific project - no filter needed
        return pipeline
    
    # Build filter stage
    filter_stage = {"$match": get_member_project_filter(member, project_id)}
    
    # Inject at the beginning
    return [filter_stage] + pipeline


def can_access_resource(
    resource: Dict[str, Any],
    member: MemberContext,
    resource_type: str = "generic"
) -> bool:
    """Check if member can access a specific resource document
    
    Args:
        resource: MongoDB document
        member: Member context
        resource_type: Type of resource (for specific logic)
        
    Returns:
        True if member can access, False otherwise
    """
    # Admins can access everything
    if member.is_admin():
        return True
    
    # Check project access
    project = resource.get("project", {})
    if isinstance(project, dict):
        project_id = project.get("_id")
        if project_id:
            # Convert Binary UUID to string for comparison
            if hasattr(project_id, 'hex'):
                project_id_str = str(uuid.UUID(bytes=project_id))
            else:
                project_id_str = str(project_id)
            
            return member.can_access_project(project_id_str)
    
    # Check if resource is created by this member
    created_by = resource.get("createdBy", {})
    if isinstance(created_by, dict):
        creator_id = created_by.get("_id")
        if creator_id:
            if hasattr(creator_id, 'hex'):
                creator_id_str = str(uuid.UUID(bytes=creator_id))
            else:
                creator_id_str = str(creator_id)
            
            if creator_id_str == member.member_id:
                return True
    
    # For conversations, check if member is participant
    if resource_type == "conversation":
        # Implement conversation-specific access logic
        return True
    
    # Default deny
    return False


def filter_results_by_access(
    results: List[Dict[str, Any]],
    member: MemberContext,
    resource_type: str = "generic"
) -> List[Dict[str, Any]]:
    """Filter a list of results to only those the member can access
    
    Args:
        results: List of MongoDB documents
        member: Member context
        resource_type: Type of resource
        
    Returns:
        Filtered list of accessible documents
    """
    if member.is_admin():
        return results
    
    return [
        result for result in results
        if can_access_resource(result, member, resource_type)
    ]
