"""
RBAC (Role-Based Access Control) Module

Provides permission management and authentication for the PMS application
based on member ID and roles.
"""

from rbac.permissions import (
    Permission,
    Role,
    MemberContext,
    PermissionError,
    ResourceAccessError,
    ROLE_PERMISSIONS,
)

from rbac.auth import (
    get_current_member,
    require_permissions,
    check_permission,
    require_permission,
    check_project_access,
    require_project_access,
)

__all__ = [
    # Permissions
    "Permission",
    "Role",
    "MemberContext",
    "PermissionError",
    "ResourceAccessError",
    "ROLE_PERMISSIONS",
    # Auth
    "get_current_member",
    "require_permissions",
    "check_permission",
    "require_permission",
    "check_project_access",
    "require_project_access",
]
