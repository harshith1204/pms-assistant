# RBAC Implementation Guide

## Overview

This application now implements **Role-Based Access Control (RBAC)** based on member ID. The RBAC system provides fine-grained permission management for all resources including work items, pages, projects, cycles, modules, and conversations.

## Architecture

### Components

1. **Permission System** (`rbac/permissions.py`)
   - Defines granular permissions for all actions
   - Defines role hierarchy (ADMIN, MEMBER, VIEWER, GUEST)
   - Maps permissions to roles
   - Provides MemberContext for authenticated users

2. **Authentication** (`rbac/auth.py`)
   - Extracts member ID from HTTP headers or JWT tokens
   - Fetches member details from MongoDB
   - Creates MemberContext with permissions
   - Provides FastAPI dependencies for route protection

3. **Query Filters** (`rbac/filters.py`)
   - Automatically filters MongoDB queries by member access
   - Ensures members only see resources in their projects
   - Applies project-based access control
   - Filters aggregation pipeline results

## Roles and Permissions

### Role Hierarchy

```
ADMIN    → Full access to all resources
MEMBER   → Create, read, update work items and pages in their projects
VIEWER   → Read-only access to resources in their projects
GUEST    → Minimal read access (pages and projects only)
```

### Permission Matrix

| Permission | ADMIN | MEMBER | VIEWER | GUEST |
|------------|-------|--------|--------|-------|
| work_item:create | ✅ | ✅ | ❌ | ❌ |
| work_item:read | ✅ | ✅ | ✅ | ❌ |
| work_item:update | ✅ | ✅ | ❌ | ❌ |
| work_item:delete | ✅ | ❌ | ❌ | ❌ |
| page:create | ✅ | ✅ | ❌ | ❌ |
| page:read | ✅ | ✅ | ✅ | ✅ |
| page:update | ✅ | ✅ | ❌ | ❌ |
| page:delete | ✅ | ❌ | ❌ | ❌ |
| project:settings | ✅ | ❌ | ❌ | ❌ |
| member:invite | ✅ | ❌ | ❌ | ❌ |
| conversation:create | ✅ | ✅ | ❌ | ❌ |

## Usage

### API Authentication

#### Method 1: X-Member-Id Header (Recommended for Development)

```bash
curl -H "X-Member-Id: ce64c003-378b-fd1e-db34-e30004c95fda" \
     http://localhost:7000/work-items
```

#### Method 2: Bearer Token (Production)

```bash
curl -H "Authorization: Bearer <JWT_TOKEN>" \
     http://localhost:7000/work-items
```

### Protecting Routes

```python
from fastapi import Depends
from typing import Annotated
from rbac import get_current_member, MemberContext, Permission, require_permissions

# Require specific permissions
@app.get("/work-items")
async def list_work_items(
    member: Annotated[MemberContext, Depends(require_permissions(Permission.WORK_ITEM_READ))]
):
    # Member is authenticated and has WORK_ITEM_READ permission
    # Automatically filtered to only show work items in member's projects
    ...

# Get current member without requiring specific permissions
@app.get("/profile")
async def get_profile(
    member: Annotated[MemberContext, Depends(get_current_member)]
):
    return {
        "name": member.name,
        "email": member.email,
        "role": member.role,
        "projects": member.project_ids
    }
```

### Manual Permission Checks

```python
from rbac import check_permission, require_permission, Permission

async def some_function(member: MemberContext):
    # Check permission (non-raising)
    if await check_permission(member, Permission.PAGE_DELETE):
        # Member has permission
        ...
    
    # Require permission (raises exception if not found)
    await require_permission(member, Permission.PROJECT_SETTINGS)
```

### Project Access Control

```python
from rbac import check_project_access, require_project_access

async def access_project(member: MemberContext, project_id: str):
    # Check access (non-raising)
    if await check_project_access(member, project_id):
        # Member has access
        ...
    
    # Require access (raises 403 if denied)
    await require_project_access(member, project_id)
```

### MongoDB Query Filtering

```python
from rbac.filters import apply_member_filter, get_member_project_filter

# Method 1: Apply to existing query
query = {"status": "active"}
filtered_query = apply_member_filter(query, "workItem", member)

# Method 2: Get project filter
project_filter = get_member_project_filter(member, project_id=None)

# Use in MongoDB query
results = await collection.find(project_filter).to_list(100)
```

### Aggregation Pipeline Filtering

```python
from rbac.filters import apply_member_pipeline_filter

# Original pipeline
pipeline = [
    {"$match": {"priority": "high"}},
    {"$group": {"_id": "$project", "count": {"$sum": 1}}}
]

# Apply member filtering
filtered_pipeline = apply_member_pipeline_filter(pipeline, member)

# Execute
results = await collection.aggregate(filtered_pipeline).to_list(100)
```

## WebSocket Authentication

The WebSocket handler automatically authenticates members and applies RBAC filtering:

```javascript
// Frontend: Send member_id in initial connection or subsequent messages
const ws = new WebSocket('ws://localhost:7000/ws/chat');

// Option 1: Include in user context (modify websocket_handler.py)
ws.send(JSON.stringify({
    type: 'auth',
    member_id: 'ce64c003-378b-fd1e-db34-e30004c95fda'
}));

// Option 2: Set environment variable DEFAULT_MEMBER_ID
```

## Configuration

### Environment Variables

```bash
# Set default member ID for development (optional)
DEFAULT_MEMBER_ID=ce64c003-378b-fd1e-db34-e30004c95fda

# Business UUID for multi-tenant filtering
BUSINESS_UUID=your-business-uuid

# Enable/disable business filtering
ENFORCE_BUSINESS_FILTER=true
```

### Member Data Structure

Members are stored in the `members` collection:

```json
{
  "_id": "...",
  "memberId": "<UUID Binary>",
  "name": "John Doe",
  "email": "john@example.com",
  "role": "ADMIN",  // ADMIN, MEMBER, VIEWER, or GUEST
  "type": "PUBLIC",
  "project": {
    "_id": "<Project UUID>",
    "name": "MCU"
  },
  "staff": {
    "_id": "<Staff UUID>",
    "name": "John Doe"
  },
  "joiningDate": "2025-09-04T20:55:00.938Z"
}
```

## Security Best Practices

1. **Always use HTTPS in production** - Protect member IDs and tokens in transit
2. **Implement JWT validation** - Replace simple token extraction with proper JWT verification
3. **Rate limiting** - Prevent brute force attacks on authentication endpoints
4. **Audit logging** - Log all permission-denied events for security monitoring
5. **Principle of least privilege** - Assign minimum necessary permissions
6. **Regular permission reviews** - Audit member roles and project access periodically

## Testing RBAC

### Test Different Roles

```bash
# Test as ADMIN (from members collection)
export X_MEMBER_ID=ce64c003-378b-fd1e-db34-e30004c95fda
curl -H "X-Member-Id: $X_MEMBER_ID" http://localhost:7000/work-items

# Test as MEMBER
export X_MEMBER_ID=<member-uuid>
curl -H "X-Member-Id: $X_MEMBER_ID" http://localhost:7000/work-items

# Test permission denied
curl -H "X-Member-Id: <viewer-uuid>" \
     -X POST http://localhost:7000/work-items \
     -H "Content-Type: application/json" \
     -d '{"title": "Test", "description": "Test"}'
# Should return 403 Forbidden
```

### Test Project Access

```bash
# Create work item in accessible project (should succeed)
curl -H "X-Member-Id: $X_MEMBER_ID" \
     -X POST http://localhost:7000/work-items \
     -d '{"title": "Task", "project_id": "<accessible-project-id>"}'

# Create work item in inaccessible project (should fail with 403)
curl -H "X-Member-Id: $X_MEMBER_ID" \
     -X POST http://localhost:7000/work-items \
     -d '{"title": "Task", "project_id": "<other-project-id>"}'
```

## Migration Guide

### Updating Existing Code

1. **Add member parameter to routes:**
```python
# Before
@app.get("/items")
async def get_items():
    ...

# After
@app.get("/items")
async def get_items(
    member: Annotated[MemberContext, Depends(require_permissions(Permission.WORK_ITEM_READ))]
):
    ...
```

2. **Apply filters to queries:**
```python
# Before
items = await collection.find({"status": "active"}).to_list(100)

# After
query = apply_member_filter({"status": "active"}, "workItem", member)
items = await collection.find(query).to_list(100)
```

3. **Check project access:**
```python
# Before
# No check

# After
if not member.can_access_project(project_id):
    raise HTTPException(403, "Access denied")
```

## Troubleshooting

### Member Not Found Error

```
HTTPException: 404 - Member not found: <uuid>
```

**Solution:** Verify the member exists in the `members` collection and the UUID is correct.

### Access Denied Errors

```
HTTPException: 403 - Insufficient permissions
```

**Solution:** Check the member's role and ensure they have the required permission.

### No Results Returned

**Cause:** Member has no project access or RBAC filters are too restrictive.

**Solution:** 
- Verify member has project memberships in the database
- Check if member role has appropriate permissions
- For testing, use an ADMIN role member

## Future Enhancements

- [ ] Add custom permission groups
- [ ] Implement team-based access control
- [ ] Add resource-level permissions (e.g., specific work item ownership)
- [ ] Support for temporary permission grants
- [ ] Permission inheritance and delegation
- [ ] Integration with external identity providers (OAuth2, SAML)
