# RBAC Flow for Work Items, Cycles, Modules, and Pages

## Overview

Yes! RBAC is implemented for **Work Items, Cycles, Modules, and Pages** based on member permissions from the **members collection**. Here's exactly how it works:

## 🔄 The Complete Flow

```
1. User Request → 2. Extract Member ID → 3. Fetch from Members Collection → 4. Build MemberContext → 5. Filter by Projects → 6. Return Only Accessible Data
```

### Step-by-Step Breakdown

#### **Step 1: User Makes Request**
```bash
curl -H "X-Member-Id: ce64c003-378b-fd1e-db34-e30004c95fda" \
     http://localhost:7000/work-items
```

#### **Step 2: Extract Member ID from Header**
The `get_current_member` dependency extracts the member ID from:
- `X-Member-Id` header, OR
- `Authorization: Bearer <token>` header

#### **Step 3: Fetch Member from Members Collection**
```python
# From rbac/auth.py - get_member_by_id()
member_doc = await members_collection.find_one({"memberId": member_uuid})

# Returns:
{
  "memberId": "ce64c003-378b-fd1e-db34-e30004c95fda",
  "name": "A Vikas",
  "email": "a.vikas21@ifheindia.org",
  "role": "ADMIN",  # ← This determines permissions
  "project": {
    "_id": "474e9e07-d646-1db8-1a30-a4d33680b590",  # ← This determines accessible projects
    "name": "MCU"
  }
}
```

#### **Step 4: Get All Projects for This Member**
```python
# From rbac/auth.py - get_member_projects()
# Finds ALL project memberships for this member
cursor = members_collection.find({"memberId": member_uuid})

# Collects all project._id values
project_ids = ["474e9e07-d646-1db8-1a30-a4d33680b590", "other-project-id", ...]
```

#### **Step 5: Build MemberContext**
```python
MemberContext(
    member_id="ce64c003-378b-fd1e-db34-e30004c95fda",
    name="A Vikas",
    email="a.vikas21@ifheindia.org",
    role=Role.ADMIN,  # Determines what actions allowed
    project_ids=["474e9e07-...", "..."],  # Determines which data visible
)
```

#### **Step 6: Apply Filters to Queries**

For **non-ADMIN** users, all queries are automatically filtered:

```python
# Original query
query = {"status": "active"}

# After RBAC filter applied
query = {
    "$and": [
        {"status": "active"},
        {"project._id": {"$in": [<member's project binaries>]}}
    ]
}
```

## 📁 How It Works for Each Collection

### 1️⃣ **Work Items**

**Collection:** `workItem`

**Filter Field:** `project._id`

**How it works:**
```python
# Member can only see work items in their projects
{
    "project._id": {"$in": [
        "474e9e07-d646-1db8-1a30-a4d33680b590",  # MCU project
        "other-project-id"  # Other projects member belongs to
    ]}
}
```

**Example Query:**
```javascript
// What the member sees (filtered)
db.workItem.find({
    "status": "IN_PROGRESS",
    "project._id": {$in: [<member's projects>]}
})

// What ADMIN sees (no filter)
db.workItem.find({
    "status": "IN_PROGRESS"
})
```

### 2️⃣ **Cycles**

**Collection:** `cycle`

**Filter Field:** `project._id`

**How it works:**
```python
# Member can only see cycles in their projects
{
    "project._id": {"$in": [<member's project IDs>]}
}
```

**Example:**
```javascript
// Member sees only cycles from MCU project
db.cycle.find({
    "project._id": ObjectId("474e9e07...")  // MCU
})
```

### 3️⃣ **Modules**

**Collection:** `module`

**Filter Field:** `project._id`

**How it works:**
```python
# Member can only see modules in their projects
{
    "project._id": {"$in": [<member's project IDs>]}
}
```

**Example:**
```javascript
// Member sees only modules from their projects
db.module.find({
    "project._id": {$in: [ObjectId("474e9e07..."), ...]}
})
```

### 4️⃣ **Pages**

**Collection:** `page`

**Filter Field:** `project._id`

**How it works:**
```python
# Member can only see pages in their projects
{
    "project._id": {"$in": [<member's project IDs>]}
}
```

**Example:**
```javascript
// Member sees only pages from their projects
db.page.find({
    "project._id": {$in: [ObjectId("474e9e07..."), ...]}
})
```

## 🔍 Real Example

Let's trace a complete request:

### **Scenario: Member "A Vikas" wants to see work items**

**Members Collection Entry:**
```json
{
  "memberId": "ce64c003-378b-fd1e-db34-e30004c95fda",
  "name": "A Vikas",
  "email": "a.vikas21@ifheindia.org",
  "role": "ADMIN",
  "project": {
    "_id": "474e9e07-d646-1db8-1a30-a4d33680b590",
    "name": "MCU"
  }
}
```

**1. Request:**
```bash
curl -H "X-Member-Id: ce64c003-378b-fd1e-db34-e30004c95fda" \
     http://localhost:7000/api/work-items?status=IN_PROGRESS
```

**2. System fetches member from members collection:**
```python
member_doc = await members.find_one({
    "memberId": Binary("ce64c003-378b-fd1e-db34-e30004c95fda")
})
# Returns: role="ADMIN", project._id="474e9e07..."
```

**3. System gets all projects for this member:**
```python
projects = await members.find({"memberId": Binary("...")})
# Returns: ["474e9e07-d646-1db8-1a30-a4d33680b590"]
```

**4. System builds filter (ADMIN bypasses, but for MEMBER it would be):**
```python
# For MEMBER role:
query = {
    "$and": [
        {"status": "IN_PROGRESS"},
        {"project._id": {
            "$in": [Binary("474e9e07-d646-1db8-1a30-a4d33680b590")]
        }}
    ]
}

# For ADMIN role:
query = {"status": "IN_PROGRESS"}  # No project filter
```

**5. Query executes:**
```python
work_items = await db.workItem.find(query).to_list(100)
```

**6. Returns only work items from MCU project (or all if ADMIN)**

## 🎯 Permission Levels per Collection

### Work Items
| Role | Create | Read | Update | Delete | Assign |
|------|--------|------|--------|--------|--------|
| **ADMIN** | ✅ All | ✅ All | ✅ All | ✅ All | ✅ All |
| **MEMBER** | ✅ Own Projects | ✅ Own Projects | ✅ Own Projects | ❌ | ✅ Own Projects |
| **VIEWER** | ❌ | ✅ Own Projects | ❌ | ❌ | ❌ |
| **GUEST** | ❌ | ❌ | ❌ | ❌ | ❌ |

### Cycles
| Role | Create | Read | Update | Delete |
|------|--------|------|--------|--------|
| **ADMIN** | ✅ All | ✅ All | ✅ All | ✅ All |
| **MEMBER** | ✅ Own Projects | ✅ Own Projects | ✅ Own Projects | ❌ |
| **VIEWER** | ❌ | ✅ Own Projects | ❌ | ❌ |
| **GUEST** | ❌ | ❌ | ❌ | ❌ |

### Modules
| Role | Create | Read | Update | Delete |
|------|--------|------|--------|--------|
| **ADMIN** | ✅ All | ✅ All | ✅ All | ✅ All |
| **MEMBER** | ✅ Own Projects | ✅ Own Projects | ✅ Own Projects | ❌ |
| **VIEWER** | ❌ | ✅ Own Projects | ❌ | ❌ |
| **GUEST** | ❌ | ❌ | ❌ | ❌ |

### Pages
| Role | Create | Read | Update | Delete | Publish |
|------|--------|------|--------|--------|---------|
| **ADMIN** | ✅ All | ✅ All | ✅ All | ✅ All | ✅ All |
| **MEMBER** | ✅ Own Projects | ✅ Own Projects | ✅ Own Projects | ❌ | ❌ |
| **VIEWER** | ❌ | ✅ Own Projects | ❌ | ❌ | ❌ |
| **GUEST** | ❌ | ✅ Public Only | ❌ | ❌ | ❌ |

## 🔐 How Members Collection Links Everything

### **Members Collection Structure:**
```json
{
  "_id": "...",
  "memberId": "ce64c003-378b-fd1e-db34-e30004c95fda",  // ← Used for authentication
  "name": "A Vikas",
  "email": "a.vikas21@ifheindia.org",
  "role": "ADMIN",  // ← Determines WHAT actions allowed
  "project": {
    "_id": "474e9e07-d646-1db8-1a30-a4d33680b590",  // ← Determines WHICH data visible
    "name": "MCU"
  },
  "staff": {...}
}
```

### **Key Points:**

1. **One member can have MULTIPLE memberships** (one per project):
   ```javascript
   // Member "A Vikas" in two projects
   [
     {
       "memberId": "ce64c003-378b-fd1e-db34-e30004c95fda",
       "role": "ADMIN",
       "project": {"_id": "project-1", "name": "MCU"}
     },
     {
       "memberId": "ce64c003-378b-fd1e-db34-e30004c95fda",
       "role": "MEMBER",
       "project": {"_id": "project-2", "name": "Avengers"}
     }
   ]
   ```

2. **Role can differ per project** (not implemented yet, but structure supports it)

3. **RBAC collects ALL projects** for a member:
   ```python
   # get_member_projects() returns:
   ["project-1", "project-2", "project-3", ...]
   ```

4. **Filters apply to all 4 collections** using `project._id` field

## 🚀 Adding RBAC to New Endpoints

### Example: Add Cycles Endpoint

```python
from rbac import require_permissions, Permission, MemberContext
from rbac.filters import apply_member_filter

@app.get("/cycles")
async def list_cycles(
    member: Annotated[MemberContext, Depends(require_permissions(Permission.CYCLE_READ))]
):
    # Build base query
    query = {"status": "active"}
    
    # Apply member filter (automatically adds project restrictions)
    filtered_query = apply_member_filter(query, "cycle", member)
    
    # Execute query
    db = mongodb_tools.client[DATABASE_NAME]
    cycles = await db["cycle"].find(filtered_query).to_list(100)
    
    return {"cycles": cycles}
```

### Example: Add Modules Endpoint

```python
@app.get("/modules")
async def list_modules(
    member: Annotated[MemberContext, Depends(require_permissions(Permission.MODULE_READ))]
):
    query = {}
    filtered_query = apply_member_filter(query, "module", member)
    
    db = mongodb_tools.client[DATABASE_NAME]
    modules = await db["module"].find(filtered_query).to_list(100)
    
    return {"modules": modules}
```

## 📊 Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        1. HTTP Request                           │
│   Header: X-Member-Id: ce64c003-378b-fd1e-db34-e30004c95fda     │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              2. Fetch from Members Collection                    │
│   Query: {memberId: "ce64c003-378b-fd1e-db34-e30004c95fda"}    │
│   Returns: {role: "ADMIN", project: {_id: "474e9e07..."}}      │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│           3. Get All Projects for This Member                    │
│   Query: {memberId: "ce64c003-378b-fd1e-db34-e30004c95fda"}    │
│   Returns: ["474e9e07...", "project-2-id", ...]                │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  4. Build MemberContext                          │
│   • member_id: "ce64c003..."                                    │
│   • role: ADMIN (determines permissions)                        │
│   • project_ids: ["474e9e07...", ...] (determines data scope)  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              5. Apply Filter to Target Collection                │
│   Collection: workItem / cycle / module / page                  │
│   Filter: {project._id: {$in: [member's project IDs]}}         │
│   (ADMIN bypasses this filter)                                  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  6. Return Filtered Results                      │
│   Only data from projects member has access to                  │
└─────────────────────────────────────────────────────────────────┘
```

## ✅ Summary

**Yes, RBAC is implemented for Work Items, Cycles, Modules, and Pages based on:**

1. ✅ **Member permissions** from the `members` collection
2. ✅ **Member's role** (`ADMIN`, `MEMBER`, `VIEWER`, `GUEST`)
3. ✅ **Member's project memberships** (fetched from `members.project._id`)
4. ✅ **Automatic filtering** by `project._id` for all 4 collections
5. ✅ **Permission-based actions** (create, read, update, delete)

**The members collection is the SINGLE SOURCE OF TRUTH for:**
- Who the user is (`memberId`)
- What they can do (`role` → permissions)
- What they can see (`project._id` → data filtering)
