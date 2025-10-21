# RBAC Quick Start Guide

Get started with the RBAC system in 5 minutes!

## Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

## Step 2: Configure Environment

```bash
# Copy example configuration
cp .env.example .env

# Edit .env and set your member ID
nano .env
```

Set the `DEFAULT_MEMBER_ID` to a valid member UUID from your database:

```bash
# Get a member ID from your database
mongosh mongodb://backendInterns:mUXe57JwdugphnEn@4.213.88.219:27017/ProjectManagement

# In MongoDB shell:
db.members.findOne({}, {memberId: 1, name: 1, role: 1})
```

Copy the `memberId` value and add to `.env`:

```env
DEFAULT_MEMBER_ID=ce64c003-378b-fd1e-db34-e30004c95fda
```

## Step 3: Start the Application

```bash
python main.py
```

## Step 4: Test RBAC

### Test 1: Access with Member ID Header

```bash
# Get conversations (requires CONVERSATION_READ permission)
curl -H "X-Member-Id: ce64c003-378b-fd1e-db34-e30004c95fda" \
     http://localhost:7000/conversations

# Expected: 200 OK with list of conversations
```

### Test 2: Create a Work Item

```bash
curl -H "X-Member-Id: ce64c003-378b-fd1e-db34-e30004c95fda" \
     -H "Content-Type: application/json" \
     -X POST http://localhost:7000/work-items \
     -d '{
       "title": "Test Work Item",
       "description": "Testing RBAC",
       "project_identifier": "MCU"
     }'

# Expected: 200 OK with created work item
```

### Test 3: Test Permission Denial

Find a VIEWER role member in your database:

```bash
mongosh mongodb://backendInterns:mUXe57JwdugphnEn@4.213.88.219:27017/ProjectManagement

db.members.findOne({role: "VIEWER"}, {memberId: 1})
```

Try to create a work item as a VIEWER (should fail):

```bash
curl -H "X-Member-Id: <viewer-member-id>" \
     -H "Content-Type: application/json" \
     -X POST http://localhost:7000/work-items \
     -d '{"title": "Test"}'

# Expected: 403 Forbidden - Insufficient permissions
```

## Step 5: Check Member Roles

You can check member roles in MongoDB:

```javascript
// Connect to MongoDB
mongosh mongodb://backendInterns:mUXe57JwdugphnEn@4.213.88.219:27017/ProjectManagement

// View all members and their roles
db.members.find({}, {name: 1, email: 1, role: 1, "project.name": 1}).pretty()

// Find admins
db.members.find({role: "ADMIN"}, {name: 1, email: 1})

// Find members
db.members.find({role: "MEMBER"}, {name: 1, email: 1})
```

## Common Tasks

### Add RBAC to a New Endpoint

```python
from fastapi import Depends
from typing import Annotated
from rbac import get_current_member, MemberContext, Permission, require_permissions

@app.get("/my-endpoint")
async def my_endpoint(
    member: Annotated[MemberContext, Depends(require_permissions(Permission.WORK_ITEM_READ))]
):
    # Your code here
    return {"user": member.name, "role": member.role}
```

### Filter a MongoDB Query

```python
from rbac.filters import apply_member_filter

# Build base query
query = {"status": "active"}

# Apply member filter (automatically adds project restrictions)
filtered_query = apply_member_filter(query, "workItem", member)

# Execute query
results = await collection.find(filtered_query).to_list(100)
```

### Check if User Can Delete

```python
from rbac import check_permission, Permission

if await check_permission(member, Permission.WORK_ITEM_DELETE):
    # User can delete
    await collection.delete_one({"_id": item_id})
else:
    # User cannot delete
    raise HTTPException(403, "Permission denied")
```

## Troubleshooting

### "Member not found" Error

**Cause:** The member ID doesn't exist in the database.

**Solution:**
1. Check your database for valid member IDs
2. Verify the UUID format is correct
3. Make sure you're using `memberId` field, not `_id`

### "Insufficient permissions" Error

**Cause:** The member's role doesn't have the required permission.

**Solution:**
1. Check the member's role in the database
2. Verify the role has the permission in `rbac/permissions.py`
3. Update the member's role if needed

### No Results Returned

**Cause:** Member has no project access.

**Solution:**
1. Verify the member has project memberships in the database
2. Check if the member's `project._id` field is set correctly
3. Use an ADMIN role member for testing

## Next Steps

1. **Read the full documentation:** `README_RBAC.md`
2. **Study the examples:** `examples/rbac_usage_examples.py`
3. **Run the tests:** `pytest tests/test_rbac.py -v`
4. **Implement JWT authentication** for production use

## Quick Reference

### Header Format

```bash
X-Member-Id: <member-uuid>
# or
Authorization: Bearer <jwt-token>
```

### Common Permissions

- `Permission.WORK_ITEM_CREATE` - Create work items
- `Permission.WORK_ITEM_READ` - Read work items
- `Permission.WORK_ITEM_UPDATE` - Update work items
- `Permission.WORK_ITEM_DELETE` - Delete work items
- `Permission.PAGE_CREATE` - Create pages
- `Permission.PAGE_READ` - Read pages
- `Permission.ADMIN_FULL_ACCESS` - Full admin access

### Member Context Properties

```python
member.member_id      # UUID string
member.name          # Full name
member.email         # Email address
member.role          # Role (ADMIN, MEMBER, VIEWER, GUEST)
member.project_ids   # List of accessible project IDs
member.is_admin()    # True if admin
member.has_permission(perm)  # Check single permission
```

## Support

For issues or questions:
1. Check `README_RBAC.md` for detailed documentation
2. Review `examples/rbac_usage_examples.py` for usage patterns
3. Run tests to verify your setup: `pytest tests/test_rbac.py -v`

Happy coding! 🚀
