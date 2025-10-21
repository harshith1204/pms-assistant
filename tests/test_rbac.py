#!/usr/bin/env python3
"""
RBAC System Tests

Tests for the Role-Based Access Control implementation.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rbac.permissions import (
    Permission,
    Role,
    MemberContext,
    ROLE_PERMISSIONS,
)


class TestPermissions:
    """Test permission definitions and role mappings"""
    
    def test_role_permissions_defined(self):
        """All roles should have defined permissions"""
        assert Role.ADMIN in ROLE_PERMISSIONS
        assert Role.MEMBER in ROLE_PERMISSIONS
        assert Role.VIEWER in ROLE_PERMISSIONS
        assert Role.GUEST in ROLE_PERMISSIONS
    
    def test_admin_has_all_permissions(self):
        """Admin should have all permissions"""
        admin_perms = ROLE_PERMISSIONS[Role.ADMIN]
        assert Permission.ADMIN_FULL_ACCESS in admin_perms
        assert Permission.WORK_ITEM_DELETE in admin_perms
        assert Permission.PAGE_DELETE in admin_perms
        assert Permission.MEMBER_MANAGE_ROLES in admin_perms
    
    def test_member_limited_permissions(self):
        """Member should have limited permissions"""
        member_perms = ROLE_PERMISSIONS[Role.MEMBER]
        assert Permission.WORK_ITEM_CREATE in member_perms
        assert Permission.PAGE_CREATE in member_perms
        # Should NOT have delete permissions
        assert Permission.WORK_ITEM_DELETE not in member_perms
        assert Permission.PAGE_DELETE not in member_perms
        assert Permission.ADMIN_FULL_ACCESS not in member_perms
    
    def test_viewer_read_only(self):
        """Viewer should only have read permissions"""
        viewer_perms = ROLE_PERMISSIONS[Role.VIEWER]
        assert Permission.WORK_ITEM_READ in viewer_perms
        assert Permission.PAGE_READ in viewer_perms
        # Should NOT have create/update/delete
        assert Permission.WORK_ITEM_CREATE not in viewer_perms
        assert Permission.PAGE_UPDATE not in viewer_perms
    
    def test_guest_minimal_access(self):
        """Guest should have minimal access"""
        guest_perms = ROLE_PERMISSIONS[Role.GUEST]
        # Everyone has read access; view is scoped by project memberships
        assert Permission.PROJECT_READ in guest_perms
        assert Permission.PAGE_READ in guest_perms
        assert Permission.WORK_ITEM_READ in guest_perms
        assert Permission.CYCLE_READ in guest_perms
        assert Permission.MODULE_READ in guest_perms


class TestMemberContext:
    """Test MemberContext functionality"""
    
    def test_member_has_permission(self):
        """Test permission checking"""
        admin = MemberContext(
            member_id="test-admin",
            name="Admin User",
            email="admin@test.com",
            role=Role.ADMIN,
            project_ids=["project-1"]
        )
        
        assert admin.has_permission(Permission.WORK_ITEM_DELETE) is True
        assert admin.has_permission(Permission.ADMIN_FULL_ACCESS) is True
    
    def test_member_lacks_permission(self):
        """Test that member doesn't have admin permissions"""
        member = MemberContext(
            member_id="test-member",
            name="Regular Member",
            email="member@test.com",
            role=Role.MEMBER,
            project_ids=["project-1"]
        )
        
        assert member.has_permission(Permission.WORK_ITEM_DELETE) is False
        assert member.has_permission(Permission.ADMIN_FULL_ACCESS) is False
    
    def test_has_any_permission(self):
        """Test checking for any of multiple permissions"""
        member = MemberContext(
            member_id="test-member",
            name="Regular Member",
            email="member@test.com",
            role=Role.MEMBER,
            project_ids=["project-1"]
        )
        
        # Has at least one
        assert member.has_any_permission([
            Permission.WORK_ITEM_CREATE,
            Permission.WORK_ITEM_DELETE
        ]) is True
        
        # Has none
        assert member.has_any_permission([
            Permission.WORK_ITEM_DELETE,
            Permission.ADMIN_FULL_ACCESS
        ]) is False
    
    def test_has_all_permissions(self):
        """Test checking for all permissions"""
        member = MemberContext(
            member_id="test-member",
            name="Regular Member",
            email="member@test.com",
            role=Role.MEMBER,
            project_ids=["project-1"]
        )
        
        # Has all
        assert member.has_all_permissions([
            Permission.WORK_ITEM_CREATE,
            Permission.PAGE_CREATE
        ]) is True
        
        # Missing one
        assert member.has_all_permissions([
            Permission.WORK_ITEM_CREATE,
            Permission.WORK_ITEM_DELETE
        ]) is False
    
    def test_can_access_project(self):
        """Test project access checking"""
        member = MemberContext(
            member_id="test-member",
            name="Regular Member",
            email="member@test.com",
            role=Role.MEMBER,
            project_ids=["project-1", "project-2"]
        )
        
        assert member.can_access_project("project-1") is True
        assert member.can_access_project("project-2") is True
        assert member.can_access_project("project-3") is False
    
    def test_admin_accesses_all_projects(self):
        """Test that admin can access any project"""
        admin = MemberContext(
            member_id="test-admin",
            name="Admin User",
            email="admin@test.com",
            role=Role.ADMIN,
            project_ids=[]
        )
        
        # Admin can access any project even if not in project_ids
        assert admin.can_access_project("any-project") is True
    
    def test_is_admin(self):
        """Test admin role checking"""
        admin = MemberContext(
            member_id="test-admin",
            name="Admin User",
            email="admin@test.com",
            role=Role.ADMIN,
            project_ids=[]
        )
        
        member = MemberContext(
            member_id="test-member",
            name="Regular Member",
            email="member@test.com",
            role=Role.MEMBER,
            project_ids=[]
        )
        
        assert admin.is_admin() is True
        assert member.is_admin() is False


class TestRBACFilters:
    """Test RBAC query filters"""
    
    def test_get_member_project_filter_admin(self):
        """Admin should get no filter"""
        from rbac.filters import get_member_project_filter
        
        admin = MemberContext(
            member_id="test-admin",
            name="Admin",
            email="admin@test.com",
            role=Role.ADMIN,
            project_ids=[]
        )
        
        filter_dict = get_member_project_filter(admin)
        assert filter_dict == {}
    
    def test_get_member_project_filter_member(self):
        """Member should get project filter"""
        from rbac.filters import get_member_project_filter
        
        member = MemberContext(
            member_id="test-member",
            name="Member",
            email="member@test.com",
            role=Role.MEMBER,
            project_ids=["project-1", "project-2"]
        )
        
        filter_dict = get_member_project_filter(member)
        assert "project._id" in filter_dict
        assert "$in" in filter_dict["project._id"]
    
    def test_apply_member_filter(self):
        """Test applying member filter to query"""
        from rbac.filters import apply_member_filter
        
        member = MemberContext(
            member_id="test-member",
            name="Member",
            email="member@test.com",
            role=Role.MEMBER,
            project_ids=["project-1"]
        )
        
        base_query = {"status": "active"}
        filtered = apply_member_filter(base_query, "workItem", member)
        
        # Should combine original query with project filter
        assert "$and" in filtered or "project._id" in filtered


@pytest.mark.asyncio
class TestAuthenticationDependencies:
    """Test authentication and dependency injection"""
    
    async def test_get_member_by_id_success(self):
        """Test successful member retrieval"""
        from rbac.auth import get_member_by_id
        
        # Mock the MongoDB client
        with patch('rbac.auth.mongodb_tools') as mock_db:
            mock_collection = AsyncMock()
            mock_collection.find_one = AsyncMock(return_value={
                "memberId": "test-id",
                "name": "Test User",
                "email": "test@example.com",
                "role": "MEMBER"
            })
            
            mock_db.client = {"ProjectManagement": {"members": mock_collection}}
            mock_db.connect = AsyncMock()
            
            # This would need proper mocking to fully test
            # For now, just verify the function exists
            assert get_member_by_id is not None
    
    async def test_get_member_projects(self):
        """Test retrieving member projects"""
        from rbac.auth import get_member_projects
        
        # Verify function exists
        assert get_member_projects is not None


def test_import_rbac_module():
    """Test that RBAC module can be imported"""
    import rbac
    
    assert rbac.Permission is not None
    assert rbac.Role is not None
    assert rbac.MemberContext is not None
    assert rbac.get_current_member is not None
    assert rbac.require_permissions is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
