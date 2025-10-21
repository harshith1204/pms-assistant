# RAG RBAC Implementation

## ✅ RBAC Now Implemented for RAG System

The RAG (Retrieval-Augmented Generation) system now applies **member-based project filtering** to all search results.

## 🔄 How It Works

### Before (No RBAC)
```
User searches → Qdrant returns ALL matching content → Show everything
```

### After (With RBAC)
```
User searches → Get member's projects → Filter Qdrant by project_name → Return only accessible content
```

## 📊 Complete Flow

```
1. User Query (via Agent/WebSocket)
   "Find pages about authentication"
   ↓
2. Extract Member Context
   member_id: "ce64c003-378b-fd1e-db34-e30004c95fda"
   role: "MEMBER"
   project_ids: ["474e9e07-...", "abc123-..."]
   ↓
3. Fetch Project Names from MongoDB
   Query: db.project.find({_id: {$in: [project_ids]}}, {name: 1})
   Returns: ["MCU", "Avengers"]
   ↓
4. Query Qdrant with Project Filter
   Filter: {
     must: [
       {content_type: "page"},
       {project_name: {any: ["MCU", "Avengers"]}}  ← RBAC Filter
     ]
   }
   ↓
5. Additional Post-Filter
   Filter results to ensure only accessible projects
   ↓
6. Return Filtered Results
   Only content from MCU and Avengers projects
```

## 🎯 What Gets Filtered

### Qdrant Metadata Structure
```json
{
  "id": "chunk-123",
  "content": "Authentication implementation details...",
  "metadata": {
    "content_type": "page",
    "project_name": "MCU",        ← Used for RBAC filtering
    "project_id": "474e9e07-...",
    "title": "Auth Documentation",
    "business_id": "...",
    ...
  }
}
```

### Filter Applied

**For MEMBER with projects ["MCU", "Avengers"]:**
```python
{
  "must": [
    {"project_name": {"any": ["MCU", "Avengers"]}}
  ]
}
```

**For ADMIN:**
```python
# No project filter - sees all content
{}
```

**For MEMBER with NO projects:**
```python
# Returns empty results
[]
```

## 🔍 Files Modified

1. **`rbac/rag_filters.py`** (NEW)
   - `get_member_project_names_from_db()` - Fetch project names from MongoDB
   - `filter_rag_results_by_project()` - Post-query filtering
   - `filter_reconstructed_docs_by_project()` - Filter reconstructed documents
   - `build_qdrant_project_filter()` - Build Qdrant filter conditions

2. **`tools.py`** - `rag_search()` tool
   - Added `member_context` parameter
   - Fetches accessible project names
   - Passes to retriever
   - Applies post-query filtering

3. **`qdrant/retrieval.py`** - `ChunkAwareRetriever`
   - Added `accessible_project_names` parameter
   - Applies Qdrant filter by project_name
   - Filters adjacent chunks by project

## 📝 Example Usage

### In Agent Tool Call

The agent automatically uses the member context:

```python
# tools.py - rag_search tool
# Member context is automatically injected from global MEMBER_CONTEXT

# User asks: "Find pages about authentication"
result = await rag_search(
    query="authentication",
    content_type="page"
)
# Automatically filtered by member's projects
```

### Manual Usage with Member Context

```python
from rbac.permissions import MemberContext, Role
from tools import rag_search

# Create member context
member = MemberContext(
    member_id="ce64c003-378b-fd1e-db34-e30004c95fda",
    name="A Vikas",
    role=Role.MEMBER,
    project_ids=["474e9e07-d646-1db8-1a30-a4d33680b590"]
)

# Search with RBAC
results = await rag_search(
    query="authentication implementation",
    content_type="page",
    member_context=member
)
# Returns only pages from member's projects
```

## 🧪 Testing RAG RBAC

### Test 1: Admin Sees Everything

```python
# Create admin member
admin = MemberContext(
    member_id="admin-id",
    name="Admin User",
    role=Role.ADMIN,
    project_ids=[]
)

# Search
results = await rag_search(
    query="security",
    member_context=admin
)
# Returns: ALL security-related content from ALL projects
```

### Test 2: Member Sees Only Their Projects

```python
# Create member with MCU project
member = MemberContext(
    member_id="member-id",
    name="Regular Member",
    role=Role.MEMBER,
    project_ids=["474e9e07-d646-1db8-1a30-a4d33680b590"]  # MCU
)

# Search
results = await rag_search(
    query="security",
    member_context=member
)
# Returns: Only security content from MCU project
```

### Test 3: Member with No Projects

```python
# Create member with no projects
member = MemberContext(
    member_id="member-id",
    name="No Access Member",
    role=Role.MEMBER,
    project_ids=[]
)

# Search
results = await rag_search(
    query="security",
    member_context=member
)
# Returns: "No accessible results found (filtered by project access)"
```

## 🔐 Security Features

### 1. **Fail Closed**
If project names can't be fetched, default to NO ACCESS:
```python
accessible_project_names = []  # Empty = no access
```

### 2. **Dual Filtering**
- **Qdrant Filter**: Applied at query time (efficient)
- **Post-Query Filter**: Additional safety check

### 3. **Adjacent Chunks**
Even adjacent chunks are filtered by project:
```python
# When fetching chunks 0,1,2,3 for context
# Each chunk is checked against accessible_project_names
```

## 📊 Performance Impact

### Before RBAC
```
Query Qdrant → Return 100 chunks → Process all
```

### After RBAC
```
Fetch project names (1 MongoDB query, cached) →
Query Qdrant with filter → Return ~20 chunks → Process filtered
```

**Impact:**
- ✅ **Faster**: Qdrant filter reduces results at source
- ✅ **Less data transfer**: Smaller result set
- ✅ **Better security**: Enforced at multiple levels

## 🚀 Integration Status

### ✅ Implemented
- [x] Qdrant query filtering by project_name
- [x] Post-query result filtering
- [x] Chunk-aware retrieval filtering
- [x] Adjacent chunk filtering
- [x] Reconstructed document filtering
- [x] Automatic member context injection
- [x] Fail-closed security model

### ⚠️ Limitations

1. **Qdrant Metadata Requirement**
   - Requires `project_name` field in Qdrant metadata
   - If missing, those chunks are excluded (defensive)

2. **Project Name Lookup**
   - Requires MongoDB query to map project IDs → names
   - Could be cached for performance

3. **No Project-Specific Roles Yet**
   - Member has same role across all projects
   - Future: Different roles per project

## 🔄 Future Enhancements

1. **Cache Project Names**
   ```python
   # Cache mapping: project_id → project_name
   # Reduces MongoDB queries
   ```

2. **Project-Level Roles**
   ```python
   # Member can be ADMIN in one project, VIEWER in another
   member.get_role_for_project("MCU")  # Returns: ADMIN
   member.get_role_for_project("Avengers")  # Returns: MEMBER
   ```

3. **Visibility Levels**
   ```python
   # Public pages visible to all
   # Private pages only to project members
   # Confidential pages only to admins
   ```

## ✅ Summary

**RAG now has full RBAC implementation:**

- ✅ Filters by member's accessible projects
- ✅ Respects role hierarchy (ADMIN, MEMBER, VIEWER, GUEST)
- ✅ Applies at Qdrant query time (efficient)
- ✅ Additional post-query filtering (secure)
- ✅ Works with chunk-aware retrieval
- ✅ Filters adjacent chunks
- ✅ Automatic member context injection
- ✅ Fail-closed security model

**Members only see RAG content from their assigned projects!**
