# Project-Level Access Filter - Issue Resolution

## Problem Identified
The member-based project access filter pipeline was "failing" because **the test data had mismatched project-member relationships**.

### Root Cause
- **Members collection** had a member "A Vikas" for project "MCU" (ID: `R0ueB9ZGHbgaMKTTNoC1kA==`)
- **Project collection** only had project "gggg" (ID: `GERBNxWW/9lPeQtYn4LUpA==`)
- These IDs don't match!
- When the pipeline ran, it found **zero members** for the existing project
- Result: All projects were filtered out → Empty results

## Pipeline Logic (CORRECT)
The pipeline in `/workspace/mongo/client.py` lines 169-181 is **working correctly**:

```python
def _membership_join(local_field: str) -> List[Dict[str, Any]]:
    """Build a $lookup + $match + $unset pipeline ensuring the document's project belongs to member."""
    return [
        # Step 1: Join with members collection
        {"$lookup": {
            "from": "members",
            "localField": local_field,      # project._id
            "foreignField": "project._id",  # members.project._id
            "as": "__mem__",
        }},
        # Step 2: Filter to only projects where user is a member
        {"$match": {"__mem__": {"$elemMatch": {"staff._id": mem_bin}}}},
        # Step 3: Clean up temporary field
        {"$unset": "__mem__"},
    ]
```

### How It Works
1. **$lookup**: Joins projects with members where project IDs match
2. **$match**: Filters to only show projects where at least one member has the given staff._id
3. **$unset**: Removes the temporary `__mem__` array

## Fix Applied
Added a member record for the existing project "gggg" in `collections/ProjectManagement.members.json`:
- **Member**: vihan (ADMIN)
- **Project**: gggg (ID: `GERBNxWW/9lPeQtYn4LUpA==`)
- **Staff ID**: `HGm3S+9pBx8TR97O1mE0tQ==`

## Verification
✅ Project "gggg" now has matching member "vihan"
✅ When `MEMBER_UUID` = vihan's staff ID → Project is returned
✅ When `MEMBER_UUID` = other staff ID → Project is NOT returned (correct!)

## How to Use in Production

### 1. Set Environment Variables
```bash
# Option 1: Use MEMBER_UUID
export MEMBER_UUID="<staff-uuid-string>"
export ENFORCE_MEMBER_FILTER="1"

# Option 2: Use STAFF_ID (fallback)
export STAFF_ID="<staff-uuid-string>"
```

### 2. Via WebSocket Context
The pipeline automatically uses `user_id_global` from websocket context:
```python
# In websocket_handler.py, line 145
user_id_global = user_context["user_id"]  # Automatically used by pipeline
```

### 3. Collections Affected
The member filter applies to:
- ✅ `project` - filters by project._id
- ✅ `workItem` - filters by workItem.project._id
- ✅ `cycle` - filters by cycle.project._id  
- ✅ `module` - filters by module.project._id
- ✅ `page` - filters by page.project._id
- ✅ `projectState` - filters by projectState.projectId
- ✅ `members` - only shows own memberships (staff._id)

## Data Requirements
For the pipeline to work correctly, ensure:

1. **Members collection** has records linking staff to projects:
   ```json
   {
     "project": {
       "_id": "<project-uuid-binary>"
     },
     "staff": {
       "_id": "<staff-uuid-binary>"
     },
     "role": "ADMIN" | "MEMBER" | "GUEST"
   }
   ```

2. **Project IDs match** between:
   - `project._id` in the project collection
   - `project._id` in the members collection

3. **Staff IDs match** between:
   - `MEMBER_UUID` / `STAFF_ID` environment variable
   - `staff._id` in the members collection

## Testing
To test the pipeline:
1. Set `MEMBER_UUID` to a valid staff UUID
2. Query any collection (e.g., projects, workItems)
3. Verify only projects where the staff is a member are returned

Example:
```bash
export MEMBER_UUID="1c69b74b-ef69-071f-1347-deced66134b5"  # vihan's ID
export ENFORCE_MEMBER_FILTER="1"
# Query projects → Should return only "gggg"
```
