#!/usr/bin/env python3
"""
RBAC Permissions System - Role-Based Access Control
Defines permissions, roles, and access control logic based on member ID
"""

from enum import Enum
from typing import Set, Dict, Optional, List
from dataclasses import dataclass, field


class Permission(str, Enum):
    """Granular permissions for different actions in the system"""
    
    # Work Item Permissions
    WORK_ITEM_CREATE = "work_item:create"
    WORK_ITEM_READ = "work_item:read"
    WORK_ITEM_UPDATE = "work_item:update"
    WORK_ITEM_DELETE = "work_item:delete"
    WORK_ITEM_ASSIGN = "work_item:assign"
    
    # Page Permissions
    PAGE_CREATE = "page:create"
    PAGE_READ = "page:read"
    PAGE_UPDATE = "page:update"
    PAGE_DELETE = "page:delete"
    PAGE_PUBLISH = "page:publish"
    
    # Project Permissions
    PROJECT_CREATE = "project:create"
    PROJECT_READ = "project:read"
    PROJECT_UPDATE = "project:update"
    PROJECT_DELETE = "project:delete"
    PROJECT_SETTINGS = "project:settings"
    
    # Member Permissions
    MEMBER_INVITE = "member:invite"
    MEMBER_READ = "member:read"
    MEMBER_UPDATE = "member:update"
    MEMBER_REMOVE = "member:remove"
    MEMBER_MANAGE_ROLES = "member:manage_roles"
    
    # Cycle & Module Permissions
    CYCLE_CREATE = "cycle:create"
    CYCLE_READ = "cycle:read"
    CYCLE_UPDATE = "cycle:update"
    CYCLE_DELETE = "cycle:delete"
    
    MODULE_CREATE = "module:create"
    MODULE_READ = "module:read"
    MODULE_UPDATE = "module:update"
    MODULE_DELETE = "module:delete"
    
    # Conversation Permissions
    CONVERSATION_READ = "conversation:read"
    CONVERSATION_CREATE = "conversation:create"
    CONVERSATION_DELETE = "conversation:delete"
    
    # Admin Permissions
    ADMIN_FULL_ACCESS = "admin:full_access"


class Role(str, Enum):
    """Member roles with hierarchical permissions"""
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"
    VIEWER = "VIEWER"
    GUEST = "GUEST"


# Define permissions for each role
ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.ADMIN: {
        # Admins have all permissions
        Permission.WORK_ITEM_CREATE,
        Permission.WORK_ITEM_READ,
        Permission.WORK_ITEM_UPDATE,
        Permission.WORK_ITEM_DELETE,
        Permission.WORK_ITEM_ASSIGN,
        Permission.PAGE_CREATE,
        Permission.PAGE_READ,
        Permission.PAGE_UPDATE,
        Permission.PAGE_DELETE,
        Permission.PAGE_PUBLISH,
        Permission.PROJECT_CREATE,
        Permission.PROJECT_READ,
        Permission.PROJECT_UPDATE,
        Permission.PROJECT_DELETE,
        Permission.PROJECT_SETTINGS,
        Permission.MEMBER_INVITE,
        Permission.MEMBER_READ,
        Permission.MEMBER_UPDATE,
        Permission.MEMBER_REMOVE,
        Permission.MEMBER_MANAGE_ROLES,
        Permission.CYCLE_CREATE,
        Permission.CYCLE_READ,
        Permission.CYCLE_UPDATE,
        Permission.CYCLE_DELETE,
        Permission.MODULE_CREATE,
        Permission.MODULE_READ,
        Permission.MODULE_UPDATE,
        Permission.MODULE_DELETE,
        Permission.CONVERSATION_READ,
        Permission.CONVERSATION_CREATE,
        Permission.CONVERSATION_DELETE,
        Permission.ADMIN_FULL_ACCESS,
    },
    
    Role.MEMBER: {
        # Members can create, read, update work items and pages
        Permission.WORK_ITEM_CREATE,
        Permission.WORK_ITEM_READ,
        Permission.WORK_ITEM_UPDATE,
        Permission.WORK_ITEM_ASSIGN,
        Permission.PAGE_CREATE,
        Permission.PAGE_READ,
        Permission.PAGE_UPDATE,
        Permission.PROJECT_READ,
        Permission.MEMBER_READ,
        Permission.CYCLE_READ,
        Permission.CYCLE_CREATE,
        Permission.CYCLE_UPDATE,
        Permission.MODULE_READ,
        Permission.MODULE_CREATE,
        Permission.MODULE_UPDATE,
        Permission.CONVERSATION_READ,
        Permission.CONVERSATION_CREATE,
    },
    
    Role.VIEWER: {
        # Viewers can only read
        Permission.WORK_ITEM_READ,
        Permission.PAGE_READ,
        Permission.PROJECT_READ,
        Permission.MEMBER_READ,
        Permission.CYCLE_READ,
        Permission.MODULE_READ,
        Permission.CONVERSATION_READ,
    },
    
    Role.GUEST: {
        # Guests have read access across the app; visibility is scoped by project membership
        Permission.PROJECT_READ,
        Permission.PAGE_READ,
        Permission.WORK_ITEM_READ,
        Permission.CYCLE_READ,
        Permission.MODULE_READ,
    },
}


@dataclass
class MemberContext:
    """Context information about the authenticated member"""
    member_id: str
    name: str
    email: str
    role: Role
    project_ids: List[str]  # Projects this member has access to
    # Map of project_id -> role for that project (derived from members collection)
    project_roles: Dict[str, Role] = field(default_factory=dict)
    business_id: Optional[str] = None
    type: Optional[str] = None  # PUBLIC, PRIVATE, etc.
    
    def has_permission(self, permission: Permission) -> bool:
        """Check if member has a specific permission"""
        role_perms = ROLE_PERMISSIONS.get(self.role, set())
        return permission in role_perms
    
    def has_any_permission(self, permissions: List[Permission]) -> bool:
        """Check if member has any of the specified permissions"""
        return any(self.has_permission(perm) for perm in permissions)
    
    def has_all_permissions(self, permissions: List[Permission]) -> bool:
        """Check if member has all of the specified permissions"""
        return all(self.has_permission(perm) for perm in permissions)
    
    def can_access_project(self, project_id: str) -> bool:
        """Check if member can access a specific project"""
        if self.role == Role.ADMIN:
            return True
        # Prefer explicit project_roles mapping when present
        if self.project_roles:
            return project_id in self.project_roles
        return project_id in self.project_ids
    
    def is_admin(self) -> bool:
        """Check if member is an admin"""
        return self.role == Role.ADMIN

    def get_project_role(self, project_id: str) -> Optional[Role]:
        """Get the member's role for a specific project, if known"""
        if self.role == Role.ADMIN:
            return Role.ADMIN
        return self.project_roles.get(project_id)

    def has_project_permission(self, permission: Permission, project_id: str) -> bool:
        """Check a permission within the context of a specific project.

        Falls back to global role when project role is unknown.
        """
        if self.role == Role.ADMIN:
            return True
        project_role = self.get_project_role(project_id) or self.role
        role_perms = ROLE_PERMISSIONS.get(project_role, set())
        return permission in role_perms


class PermissionError(Exception):
    """Raised when a member doesn't have required permissions"""
    pass


class ResourceAccessError(Exception):
    """Raised when a member tries to access a resource they don't own"""
    pass
