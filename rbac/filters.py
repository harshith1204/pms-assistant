#!/usr/bin/env python3
"""
RBAC Query Filters - Automatically filter MongoDB queries based on member permissions

Ensures members can only access data they have permissions for.
"""

from typing import Dict, Any, List, Optional
from bson.binary import Binary
import uuid

from rbac.permissions import MemberContext
from mongo.constants import uuid_str_to_mongo_binary, BUSINESS_UUID, COLLECTIONS_WITH_DIRECT_BUSINESS


def _project_field_for_collection(collection: str) -> str:
    """Return the field path that stores project reference for a collection."""
    if collection == "project":
        return "_id"
    if collection == "projectState":
        return "projectId"
    # Default schema uses nested project object with _id
    return "project._id"


def apply_member_filter(
    query: Dict[str, Any],
    collection: str,
    member: MemberContext,
    project_id: Optional[str] = None,
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
    
    # Build project access filter (strictly by memberships)
    project_field = _project_field_for_collection(collection)
    print(f"🔒 RBAC apply_member_filter: collection={collection}, project_field={project_field}, member={member.member_id}, project_ids={member.project_ids}")
    
    if project_id:
        # Specific project requested - verify access
        if not member.can_access_project(project_id):
            # Return impossible filter if no access
            print(f"❌ RBAC: Member {member.member_id} cannot access project {project_id}")
            return {"_id": {"$exists": False}}
        value = uuid_str_to_mongo_binary(project_id)
        project_filter = {project_field: value}
        print(f"✅ RBAC: Filtering by specific project {project_id}")
    elif member.project_ids:
        # Filter by all accessible projects
        project_binaries = [uuid_str_to_mongo_binary(pid) for pid in member.project_ids]
        project_filter = {project_field: {"$in": project_binaries}}
        print(f"✅ RBAC: Filtering by {len(member.project_ids)} accessible projects: {member.project_ids}")
    else:
        # If no explicit memberships, return nothing (defensive)
        print(f"❌ RBAC: Member {member.member_id} has no project access")
        return {"_id": {"$exists": False}}
    
    # Optionally apply business scoping (for collections that store business directly)
    if BUSINESS_UUID and collection in COLLECTIONS_WITH_DIRECT_BUSINESS:
        try:
            biz_filter = {"business._id": uuid_str_to_mongo_binary(BUSINESS_UUID)}  # type: ignore[arg-type]
            # Combine project and business filters via $and
            project_filter = {"$and": [project_filter, biz_filter]}
        except Exception:
            # If conversion fails, skip business filter rather than fail the query
            pass

    # Combine with existing query
    if "$and" in query:
        query["$and"].append(project_filter)
    elif query:
        query = {"$and": [query, project_filter]}
    else:
        query = project_filter
    
    return query


def get_member_project_filter(
    member: MemberContext,
    project_id: Optional[str] = None,
    collection: Optional[str] = None,
) -> Dict[str, Any]:
    """Get MongoDB filter for member's accessible projects
    
    Args:
        member: Member context
        project_id: Optional specific project ID
        
    Returns:
        MongoDB filter dict
    """
    project_field = _project_field_for_collection(collection or "") if collection else "project._id"
    print(f"🔒 RBAC get_member_project_filter: collection={collection}, project_field={project_field}, member={member.member_id}, project_ids={member.project_ids}")

    if project_id:
        if not member.can_access_project(project_id):
            print(f"❌ RBAC: Member {member.member_id} cannot access project {project_id}")
            return {"_id": {"$exists": False}}
        filter_result = {project_field: uuid_str_to_mongo_binary(project_id)}
        print(f"✅ RBAC: Built filter for specific project: {filter_result}")
        return filter_result
    
    if member.project_ids:
        project_binaries = [uuid_str_to_mongo_binary(pid) for pid in member.project_ids]
        filter_result = {project_field: {"$in": project_binaries}}
        print(f"✅ RBAC: Built filter for {len(member.project_ids)} projects: {filter_result}")
        return filter_result
    
    print(f"❌ RBAC: Member {member.member_id} has no project access")
    return {"_id": {"$exists": False}}


def apply_member_pipeline_filter(
    pipeline: List[Dict[str, Any]],
    member: MemberContext,
    project_id: Optional[str] = None,
    collection: Optional[str] = None,
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
    # Always apply project filter; access is strictly project-scoped
    
    # Build filter stage
    project_filter = get_member_project_filter(member, project_id, collection)
    filter_stage = {"$match": project_filter}
    
    print(f"🔒 RBAC apply_member_pipeline_filter: Injecting filter stage: {filter_stage}")
    
    # Inject at the beginning
    result_pipeline = [filter_stage] + pipeline
    print(f"✅ RBAC: Pipeline now has {len(result_pipeline)} stages (added 1 RBAC filter)")
    return result_pipeline


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
    return [
        result for result in results
        if can_access_resource(result, member, resource_type)
    ]
