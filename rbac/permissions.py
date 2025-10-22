#!/usr/bin/env python3
"""
Simplified RBAC - Project Membership Based Access

Removes role/permission checks. Access is granted strictly by project membership.
If a member belongs to a project, they can access that project's resources.
"""

from typing import Dict, Optional, List
from dataclasses import dataclass, field


@dataclass
class MemberContext:
    """Authenticated member context used for access filtering."""
    member_id: str
    name: str
    email: str
    # List of project UUID strings the member can access
    project_ids: List[str]
    # Optional map of project_id -> arbitrary metadata from membership document
    project_memberships: Dict[str, dict] = field(default_factory=dict)
    business_id: Optional[str] = None
    type: Optional[str] = None  # PUBLIC, PRIVATE, etc.

    def can_access_project(self, project_id: str) -> bool:
        """Return True if member is a member of given project."""
        return project_id in self.project_ids


class PermissionError(Exception):
    """Kept for compatibility with callers that catch PermissionError."""
    pass


class ResourceAccessError(Exception):
    """Raised when a member tries to access a resource they don't own."""
    pass
