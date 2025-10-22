# RBAC Filters Debug Guide

## Problem Statement
Member authentication is working, but when querying for projects, work items, cycles, or modules, the system returns everything at the business level rather than filtering by the member's project access.

## Solution Implemented
Added comprehensive debug logging throughout the RBAC filter chain to identify and diagnose the issue.

## Changes Made

### 1. Enhanced Debug Logging in `rbac/filters.py`

**Function: `apply_member_filter()`**
- Added logging to show:
  - Collection being filtered
  - Project field being used for filtering
  - Member ID and accessible project IDs
  - Whether specific project or multiple projects
  - Filter construction results

**Function: `get_member_project_filter()`**
- Added logging to show:
  - Collection and project field mapping
  - Member context details
  - Generated filter structure
  - Success/failure of filter construction

**Function: `apply_member_pipeline_filter()`**
- Added logging to show:
  - Filter stage being injected
  - Pipeline transformation (before/after stage count)

### 2. Enhanced Debug Logging in `mongo/client.py`

**Function: `aggregate()`**
- Added logging to show:
  - Member context availability
  - Number of accessible projects
  - RBAC filter application status
  - Pipeline stage counts (original vs with RBAC filters)
  - First injected stage (RBAC filter)
  - Query results count

### 3. Enhanced Debug Logging in `websocket_handler.py`

**Function: `handle_chat_websocket()`**
- Added logging to show:
  - Member authentication process
  - Member document details
  - Project memberships count
  - Actual project IDs loaded
  - Final member context creation

## How RBAC Filters Work

### 1. Authentication Phase (WebSocket Connection)
```
websocket_handler.py:
1. WebSocket connects with member_id (hardcoded: ce64c080-378b-fd1e-db34-e3004c95fda1)
2. Calls get_member_by_id() to fetch member document
3. Calls get_member_project_memberships() to get project access
4. Creates MemberContext with project_ids list
5. Sets member_context_global for access by other modules
```

### 2. Query Execution Phase
```
mongo/client.py → aggregate():
1. Fetches member_context_global via _get_current_member_context()
2. Calls apply_member_pipeline_filter() from rbac/filters.py
3. Injects $match stage at start of pipeline
4. Executes query with RBAC filter applied
```

### 3. Filter Construction
```
rbac/filters.py → get_member_project_filter():
1. Determines correct field for collection:
   - "project" → "_id"
   - "projectState" → "projectId"  
   - everything else → "project._id"
2. Builds MongoDB filter:
   - Single project: {field: binary_uuid}
   - Multiple projects: {field: {$in: [binary_uuids]}}
   - No access: {_id: {$exists: false}}
```

## Project Field Mapping by Collection

| Collection | Field Used for Filtering | Rationale |
|-----------|-------------------------|-----------|
| `project` | `_id` | Direct project document |
| `projectState` | `projectId` | References project by projectId field |
| `workItem` | `project._id` | Embedded project object |
| `cycle` | `project._id` | Embedded project object |
| `module` | `project._id` | Embedded project object |
| `members` | `project._id` | Embedded project object |
| `page` | `project._id` | Embedded project object |

## What to Look For in Logs

### On WebSocket Connection:
```
🔑 Member Authentication: member_id=ce64c080-378b-fd1e-db34-e3004c95fda1
   Member doc found: name=..., email=...
   Project memberships: X memberships
   Project IDs: ['proj-id-1', 'proj-id-2', ...]
✅ Member authenticated: ... with X project(s)
```

**What This Tells You:**
- Member was found in database
- How many projects they have access to
- Actual project UUID strings

### On Every Query:
```
🔐 MongoDB Client: Applying RBAC filters for member ... on collection 'workItem'
   Member has access to X projects: [...]
✅ MongoDB Client: RBAC filter applied successfully - 1 stage(s) injected
```

**What This Tells You:**
- RBAC filters are being applied
- Member context is available (not None)
- Filter injection succeeded

### Filter Construction:
```
🔒 RBAC get_member_project_filter: collection=workItem, project_field=project._id, member=..., project_ids=[...]
✅ RBAC: Built filter for X projects: {'project._id': {'$in': [Binary(...), ...]}}
```

**What This Tells You:**
- Correct field is being used for collection
- Filter is being constructed with proper project IDs
- Binary UUID conversion is working

### Pipeline Injection:
```
🔒 RBAC apply_member_pipeline_filter: Injecting filter stage: {'$match': {...}}
✅ RBAC: Pipeline now has Y stages (added 1 RBAC filter)
```

**What This Tells You:**
- Filter stage is being added to pipeline
- Pipeline transformation is working

### Query Execution:
```
📊 MongoDB Query: collection='workItem', pipeline stages=5 (original: 4, injected: 1)
   First stage (RBAC filter): {'$match': {'project._id': {'$in': [...]}}}
📈 MongoDB Results: Found 10 documents in collection 'workItem'
```

**What This Tells You:**
- Total pipeline stages (should be original + 1)
- RBAC filter is first stage
- How many documents matched the query

## Troubleshooting Guide

### Issue: Seeing all business data (not filtered by projects)

**Possible Causes:**

1. **Member context is None**
   - Look for: `⚠️  MongoDB Client: No member context available`
   - Solution: Check that member_id_from_auth is set in websocket_handler.py
   - Verify get_member_by_id() finds the member

2. **Member has no project access**
   - Look for: `❌ RBAC: Member ... has no project access`
   - Solution: Check members collection - member may not be assigned to any projects
   - Verify get_member_project_memberships() returns data

3. **RBAC filter construction failed**
   - Look for: `❌ MongoDB Client: RBAC filter construction failed`
   - Solution: Check exception details in logs
   - Verify member_context has valid project_ids

4. **Wrong project field for collection**
   - Look for: Filter using wrong field name
   - Solution: Verify _project_field_for_collection() returns correct field
   - Check collection name matches expected values

5. **Binary UUID conversion issue**
   - Look for: Errors in filter construction
   - Solution: Verify uuid_str_to_mongo_binary() is working
   - Check that project_ids are valid UUID strings

### Issue: No results returned (should have some)

**Possible Causes:**

1. **Project IDs don't match database**
   - Compare logged project_ids with actual data in MongoDB
   - Verify Binary UUID format matches database storage

2. **Filter too restrictive**
   - Check if member_context.project_ids is correct
   - Verify the member actually has memberships in the members collection

## Testing RBAC Filters

### Step 1: Check Member Authentication
```bash
# Start the application and watch logs for:
🔑 Member Authentication
```
Verify:
- Member document is found
- Project IDs list is populated
- Not empty or None

### Step 2: Run a Simple Query
```
User: "How many projects?"
```
Look for:
- RBAC filter being applied
- project._id filter with $in
- Results count matches expected projects

### Step 3: Test Different Collections
```
User: "How many work items?"
User: "How many cycles?"  
User: "How many modules?"
```
Verify:
- Each uses correct project field
- Filters are applied consistently
- Results are scoped to member's projects

### Step 4: Verify Business Scoping
```
User: "Show all projects"
```
Should return:
- Only projects where member is a member
- NOT all projects in the business
- Even if business_id matches

## Expected Filter Examples

### For work items:
```json
{
  "$match": {
    "project._id": {
      "$in": [
        Binary("proj-uuid-1"),
        Binary("proj-uuid-2")
      ]
    }
  }
}
```

### For projects:
```json
{
  "$match": {
    "_id": {
      "$in": [
        Binary("proj-uuid-1"),
        Binary("proj-uuid-2")
      ]
    }
  }
}
```

### For projectState:
```json
{
  "$match": {
    "projectId": {
      "$in": [
        Binary("proj-uuid-1"),
        Binary("proj-uuid-2")
      ]
    }
  }
}
```

## Next Steps

1. **Start the application** and establish a WebSocket connection
2. **Watch the logs** for the authentication messages
3. **Note the project IDs** that the member has access to
4. **Run queries** for different collections
5. **Verify** the filters are being applied correctly
6. **Compare results** with what's expected based on project access

If filters are being applied but still seeing wrong data:
- Check the member's project memberships in the database
- Verify the project UUIDs match between members collection and project collection
- Ensure Binary UUID format is consistent

If filters are not being applied:
- Check that member_context_global is not None
- Verify get_member_by_id() is finding the member
- Check for exceptions in filter construction
