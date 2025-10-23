# Business & Member Filter Fix

## Problem Summary

You were getting **empty data** when querying members and business information because:

1. **Environment Variable Mismatch**
   - `websocket_handler.py` was using `BUSINESS_ID` 
   - `mongo/client.py` was expecting `BUSINESS_UUID`
   - These didn't match, so the business filter wasn't being applied correctly

2. **Invalid Default UUID**
   - The code was setting `"default_business"` as a fallback
   - This is not a valid UUID format and failed silently during conversion
   - The UUID conversion error was caught but not logged

3. **Silent Error Handling**
   - UUID conversion errors were caught with empty `except Exception: pass`
   - This made debugging impossible

## Changes Made

### 1. Fixed Environment Variable Handling (`websocket_handler.py`)
```python
# Before:
business_id_from_env = os.getenv("BUSINESS_ID", "default_business")

# After:
business_id_from_env = os.getenv("BUSINESS_UUID", os.getenv("BUSINESS_ID", ""))
user_id_from_env = os.getenv("MEMBER_UUID", os.getenv("STAFF_ID", "default_user"))
```

### 2. Added Error Logging (`mongo/client.py`)
```python
# Before:
except Exception:
    # Do not fail query if business filter construction fails
    pass

# After:
except ValueError as e:
    # Invalid UUID format - log and skip business filter
    print(f"⚠️  Invalid BUSINESS_UUID format '{biz_uuid}': {e}")
    print(f"   Skipping business filter for {collection}")
except Exception as e:
    # Other errors - log and skip business filter
    print(f"⚠️  Error applying business filter for {collection}: {e}")
```

This same pattern was applied to both business and member filtering.

## How to Test

### Step 1: Extract UUIDs from Your Data
```bash
python3 extract_uuids.py
```

This will show you the actual UUIDs from your sample data:
```
Business ID (Simpo.ai): c564604e-3905-1f07-685f-e342651963ac
Staff ID (A Vikas):     80c064ce-8b37-1efd-db34-e3004c95fda1
```

### Step 2: Set Environment Variables
```bash
export BUSINESS_UUID='c564604e-3905-1f07-685f-e342651963ac'
export MEMBER_UUID='80c064ce-8b37-1efd-db34-e3004c95fda1'
```

### Step 3: Run the Test Script
```bash
python3 test_business_member_filter.py
```

This will:
- ✅ Validate your UUID formats
- ✅ Test member queries with filtering
- ✅ Test project queries with business filtering
- ✅ Show raw counts without filters for comparison
- ✅ Provide recommendations if issues are found

## Environment Variables Reference

| Variable | Description | Example |
|----------|-------------|---------|
| `BUSINESS_UUID` | Primary business ID for filtering (preferred) | `c564604e-3905-1f07-685f-e342651963ac` |
| `BUSINESS_ID` | Fallback business ID if BUSINESS_UUID not set | `c564604e-3905-1f07-685f-e342651963ac` |
| `MEMBER_UUID` | Member/Staff ID for RBAC filtering (preferred) | `80c064ce-8b37-1efd-db34-e3004c95fda1` |
| `STAFF_ID` | Fallback staff ID if MEMBER_UUID not set | `80c064ce-8b37-1efd-db34-e3004c95fda1` |
| `ENFORCE_BUSINESS_FILTER` | Force business filtering even without UUID | `1` or `true` |
| `ENFORCE_MEMBER_FILTER` | Force member filtering even without UUID | `1` or `true` |

## How the Filtering Works

### Business Filtering
For collections with direct `business._id` field:
- `project`, `workItem`, `cycle`, `module`, `page`
- Directly filters: `{"business._id": <business_uuid>}`

For collections without direct business field:
- `members` - Joins through project: `members.project._id` → `project._id` → `project.business._id`
- `projectState` - Joins through project: `projectState.projectId` → `project._id` → `project.business._id`

### Member Filtering
- `members` collection: Filters by `staff._id`
- Other collections: Joins to `members` via project to ensure member has access

## Troubleshooting

### Still Getting Empty Data?

1. **Check your UUIDs are valid**
   ```bash
   python3 extract_uuids.py
   ```

2. **Verify the UUIDs exist in your database**
   - The UUIDs must match actual documents in your MongoDB
   - Use MongoDB Compass or shell to verify

3. **Check if member has access to the business**
   - The member's project must belong to the specified business
   - In the sample data:
     - Member "A Vikas" is in project "MCU" 
     - But project "MCU" might belong to a different business than "Simpo.ai"

4. **Disable filtering temporarily for debugging**
   ```bash
   unset BUSINESS_UUID
   unset MEMBER_UUID
   ```
   This will return all data without filtering.

### Enable Debug Logging

The code now logs warnings when:
- UUID format is invalid
- Filter construction fails
- You'll see messages like: `⚠️ Invalid BUSINESS_UUID format 'xxx': ...`

## Production Deployment

For production, ensure these environment variables are set in your deployment configuration:
- Docker: Add to `.env` file or docker-compose environment section
- Kubernetes: Add to ConfigMap or Secret
- Cloud: Set in environment configuration (AWS ECS, GCP Cloud Run, etc.)

## Next Steps

1. ✅ Extract your actual UUIDs: `python3 extract_uuids.py`
2. ✅ Set environment variables with real UUIDs
3. ✅ Test with: `python3 test_business_member_filter.py`
4. ✅ If still seeing issues, check the warning logs
5. ✅ Deploy with correct environment variables set
