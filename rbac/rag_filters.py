#!/usr/bin/env python3
"""
RBAC Filters for RAG/Qdrant Retrieval

Applies member-based project filtering to RAG search results.
"""

from typing import List, Dict, Any, Optional
from rbac.permissions import MemberContext


def should_filter_rag_by_project(member: Optional[MemberContext]) -> bool:
    """
    Determine if RAG results should be filtered by project.
    
    Args:
        member: Member context (None means no filtering)
        
    Returns:
        True if filtering should be applied
    """
    if not member:
        return False
    
    # Admins see everything
    if member.is_admin():
        return False
    
    # All other roles are filtered by project
    return True


def get_member_project_names(member: MemberContext) -> List[str]:
    """
    Get list of project names (not IDs) that member can access.
    
    Note: Qdrant stores project_name as string, not project ID.
    This requires a lookup from project IDs to project names.
    
    Args:
        member: Member context
        
    Returns:
        List of project names
    """
    # This would need to fetch project names from MongoDB
    # For now, return empty list which will be populated by caller
    return []


async def get_member_project_names_from_db(member: MemberContext) -> List[str]:
    """
    Fetch project names from MongoDB based on member's project IDs.
    
    Args:
        member: Member context with project_ids
        
    Returns:
        List of project names that member can access
    """
    from mongo.constants import mongodb_tools, DATABASE_NAME, uuid_str_to_mongo_binary
    
    if member.is_admin():
        # Admin can see all projects - return None to indicate no filter
        return None
    
    if not member.project_ids:
        # No project access - return empty list
        return []
    
    try:
        if not mongodb_tools.client:
            await mongodb_tools.connect()
        
        db = mongodb_tools.client[DATABASE_NAME]
        projects_collection = db["project"]
        
        # Convert project IDs to MongoDB Binary format
        project_binaries = [uuid_str_to_mongo_binary(pid) for pid in member.project_ids]
        
        # Fetch project names
        cursor = projects_collection.find(
            {"_id": {"$in": project_binaries}},
            {"name": 1}
        )
        
        project_names = []
        async for project in cursor:
            name = project.get("name")
            if name:
                project_names.append(name)
        
        return project_names
    
    except Exception as e:
        print(f"Error fetching project names for RAG filtering: {e}")
        # Fail closed - return empty list to restrict access
        return []


def filter_rag_results_by_project(
    results: List[Dict[str, Any]],
    member: Optional[MemberContext],
    accessible_project_names: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Filter RAG search results to only those from member's accessible projects.
    
    Args:
        results: List of RAG search results with metadata
        member: Member context
        accessible_project_names: Pre-fetched list of accessible project names
        
    Returns:
        Filtered list of results
    """
    # No filtering if no member context or member is admin
    if not member or member.is_admin():
        return results
    
    # No accessible projects - return empty
    if accessible_project_names is not None and len(accessible_project_names) == 0:
        return []
    
    # Filter results
    filtered = []
    for result in results:
        # Check if result has project metadata
        project_name = None
        
        # Try different metadata structures
        if isinstance(result, dict):
            # Check direct project_name field
            project_name = result.get("project_name")
            
            # Check nested metadata
            if not project_name and "metadata" in result:
                metadata = result.get("metadata", {})
                project_name = metadata.get("project_name")
            
            # Check payload (Qdrant structure)
            if not project_name and "payload" in result:
                payload = result.get("payload", {})
                project_name = payload.get("project_name")
        
        # If no project name, default behavior (include if no filtering, exclude if filtering)
        if not project_name:
            # If accessible_project_names is None (admin), include
            # Otherwise exclude (defensive - if we can't determine project, don't show)
            if accessible_project_names is None:
                filtered.append(result)
            continue
        
        # Check if project name is in accessible list
        if accessible_project_names is None or project_name in accessible_project_names:
            filtered.append(result)
    
    return filtered


def filter_reconstructed_docs_by_project(
    docs: List[Any],  # ReconstructedDocument objects
    member: Optional[MemberContext],
    accessible_project_names: Optional[List[str]] = None
) -> List[Any]:
    """
    Filter reconstructed documents by project access.
    
    Args:
        docs: List of ReconstructedDocument objects
        member: Member context
        accessible_project_names: Pre-fetched list of accessible project names
        
    Returns:
        Filtered list of documents
    """
    # No filtering if no member context or member is admin
    if not member or member.is_admin():
        return docs
    
    # No accessible projects - return empty
    if accessible_project_names is not None and len(accessible_project_names) == 0:
        return []
    
    # Filter documents
    filtered = []
    for doc in docs:
        # Try to get project name from metadata
        project_name = None
        
        if hasattr(doc, 'metadata'):
            project_name = doc.metadata.get("project_name")
        
        # If no project name, exclude (defensive)
        if not project_name:
            if accessible_project_names is None:
                filtered.append(doc)
            continue
        
        # Check if project name is in accessible list
        if accessible_project_names is None or project_name in accessible_project_names:
            filtered.append(doc)
    
    return filtered


def build_qdrant_project_filter(accessible_project_names: Optional[List[str]]) -> Optional[Dict[str, Any]]:
    """
    Build Qdrant filter condition for project names.
    
    Args:
        accessible_project_names: List of project names member can access
                                  None means no filter (admin)
        
    Returns:
        Qdrant filter dict or None
    """
    from qdrant_client.models import Filter, FieldCondition, MatchAny
    
    # None means no filter (admin)
    if accessible_project_names is None:
        return None
    
    # Empty list means no access
    if len(accessible_project_names) == 0:
        # Return filter that matches nothing
        return Filter(
            must=[FieldCondition(key="project_name", match=MatchAny(any=["__IMPOSSIBLE_PROJECT_NAME__"]))]
        )
    
    # Build filter for accessible projects
    return Filter(
        must=[FieldCondition(key="project_name", match=MatchAny(any=accessible_project_names))]
    )
