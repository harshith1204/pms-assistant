# How to Integrate RBAC Collection Endpoints

## Quick Integration

Add these lines to `main.py` to enable RBAC-protected endpoints for all collections:

```python
# Add this import at the top of main.py
from rbac.collection_endpoints import router as collection_router

# Add this after creating the app
app.include_router(collection_router)
```

That's it! Now you have RBAC-protected endpoints for:
- ✅ Work Items: `GET /api/work-items`
- ✅ Cycles: `GET /api/cycles`, `GET /api/cycles/{id}`
- ✅ Modules: `GET /api/modules`, `GET /api/modules/{id}`
- ✅ Pages: `GET /api/pages`

## Testing the New Endpoints

```bash
# List cycles (only from member's projects)
curl -H "X-Member-Id: ce64c003-378b-fd1e-db34-e30004c95fda" \
     http://localhost:7000/api/cycles

# List modules
curl -H "X-Member-Id: ce64c003-378b-fd1e-db34-e30004c95fda" \
     http://localhost:7000/api/modules

# List work items with filters
curl -H "X-Member-Id: ce64c003-378b-fd1e-db34-e30004c95fda" \
     "http://localhost:7000/api/work-items?status=IN_PROGRESS&priority=HIGH"

# Get specific cycle
curl -H "X-Member-Id: ce64c003-378b-fd1e-db34-e30004c95fda" \
     http://localhost:7000/api/cycles/507f1f77bcf86cd799439011
```

## What Happens Under the Hood

For each request:

1. **Authentication**: Member ID extracted from header
2. **Fetch Member**: Get member details from `members` collection
3. **Get Projects**: Collect all projects member belongs to
4. **Check Permission**: Verify member has required permission (e.g., `CYCLE_READ`)
5. **Filter Query**: Add `project._id` filter to only show member's projects
6. **Execute**: Run filtered query against database
7. **Return**: Send back only accessible data

## Example: What Different Roles See

### Admin Role
```bash
curl -H "X-Member-Id: <admin-member-id>" http://localhost:7000/api/cycles
```
**Returns:** ALL cycles from ALL projects (no filter applied)

### Member Role
```bash
curl -H "X-Member-Id: <member-member-id>" http://localhost:7000/api/cycles
```
**Returns:** Only cycles from projects where this member is assigned

### Viewer Role
```bash
curl -H "X-Member-Id: <viewer-member-id>" http://localhost:7000/api/cycles
```
**Returns:** Read-only view of cycles from member's projects

### Guest Role
```bash
curl -H "X-Member-Id: <guest-member-id>" http://localhost:7000/api/cycles
```
**Returns:** 403 Forbidden (Guests don't have CYCLE_READ permission)

## Database Queries Generated

### For MEMBER Role (2 projects: MCU and Avengers)

```javascript
// List Cycles Query
db.cycle.find({
  "project._id": {
    $in: [
      Binary("474e9e07-d646-1db8-1a30-a4d33680b590"),  // MCU
      Binary("abc123...-...")  // Avengers
    ]
  }
})

// List Modules Query
db.module.find({
  "project._id": {
    $in: [
      Binary("474e9e07-d646-1db8-1a30-a4d33680b590"),
      Binary("abc123...-...")
    ]
  }
})

// List Work Items Query with Status Filter
db.workItem.find({
  "$and": [
    { "status": "IN_PROGRESS" },
    { "project._id": {
        $in: [
          Binary("474e9e07-d646-1db8-1a30-a4d33680b590"),
          Binary("abc123...-...")
        ]
      }
    }
  ]
})
```

### For ADMIN Role

```javascript
// No project filter - sees everything
db.cycle.find({})
db.module.find({})
db.workItem.find({ "status": "IN_PROGRESS" })
```

## Complete Flow Diagram

```
User Request with Member ID
         │
         ▼
┌─────────────────────┐
│ Extract Member ID   │
│ from Header         │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────────────────┐
│ Query Members Collection        │
│ Get: role + all project IDs     │
└──────────┬──────────────────────┘
           │
           ▼
┌─────────────────────────────────┐
│ Check Permission                │
│ (based on role)                 │
└──────────┬──────────────────────┘
           │
           ├─── ✅ Has Permission ────────────┐
           │                                  │
           └─── ❌ No Permission              │
                      │                       │
                      ▼                       ▼
               ┌────────────┐       ┌──────────────────┐
               │ 403        │       │ Apply Filter     │
               │ Forbidden  │       │ by project._id   │
               └────────────┘       └─────────┬────────┘
                                              │
                                              ▼
                                    ┌──────────────────┐
                                    │ Query Collection │
                                    │ (filtered)       │
                                    └─────────┬────────┘
                                              │
                                              ▼
                                    ┌──────────────────┐
                                    │ Return Results   │
                                    │ (only member's   │
                                    │  projects)       │
                                    └──────────────────┘
```

## Available Endpoints Summary

| Endpoint | Method | Permission Required | Filter Applied |
|----------|--------|-------------------|----------------|
| `/api/work-items` | GET | WORK_ITEM_READ | ✅ By project._id |
| `/api/cycles` | GET | CYCLE_READ | ✅ By project._id |
| `/api/cycles/{id}` | GET | CYCLE_READ | ✅ Individual check |
| `/api/modules` | GET | MODULE_READ | ✅ By project._id |
| `/api/modules/{id}` | GET | MODULE_READ | ✅ Individual check |
| `/api/pages` | GET | PAGE_READ | ✅ By project._id |

All endpoints automatically:
- ✅ Authenticate the member
- ✅ Check required permissions
- ✅ Filter results by project access
- ✅ Return 403 if unauthorized
- ✅ Return 404 if resource not found
