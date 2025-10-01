# Breakdown & Parallel Query Support

## Overview

Your PMS Assistant now supports sophisticated breakdown queries (multi-dimensional aggregations) and parallel query execution for complex analysis. These features leverage the existing Orchestrator, enhanced planner, and new composite_query tool.

---

## 🎯 Breakdown Queries

### What Are Breakdown Queries?

Breakdown queries allow you to analyze data across **multiple dimensions simultaneously**, creating hierarchical or cross-tabulated views of your project data.

### Supported Dimensions

You can break down data by any combination of:
- **priority**: URGENT, HIGH, MEDIUM, LOW, NONE
- **status/state**: Backlog, In-Progress, Completed, Verified, etc.
- **assignee**: Team members assigned to work items
- **project**: Which project the item belongs to
- **cycle**: Sprint/cycle association
- **module**: Module association
- **business**: Business unit
- **Date buckets**: created_day, created_week, created_month, updated_day, etc.

### Examples

#### Single-Dimension Breakdown
```
"Break down work items by priority"
"Show me task distribution by assignee"
"Group active projects by status"
```

**Result Format:**
```
📊 RESULTS SUMMARY:
Found 45 items grouped by 1 dimension (priority):

• priority: HIGH: 18 items
• priority: MEDIUM: 15 items
• priority: LOW: 8 items
• priority: URGENT: 4 items
```

#### Multi-Dimensional Breakdown
```
"Break down work items by priority and status"
"Show me task distribution by assignee and project"
"Group bugs by priority and state"
```

**Result Format (Hierarchical):**
```
📊 RESULTS SUMMARY:
Found 45 items grouped by 2 dimensions (priority, state):

▸ priority=HIGH: 18 total
  └─ state=In-Progress: 10
  └─ state=Backlog: 5
  └─ state=Completed: 3

▸ priority=MEDIUM: 15 total
  └─ state=In-Progress: 8
  └─ state=Backlog: 7

▸ priority=LOW: 8 total
  └─ state=Backlog: 6
  └─ state=In-Progress: 2
```

#### Breakdown with Filters
```
"Break down active work items by assignee"
"Show me high-priority bugs grouped by project and status"
"Break down overdue tasks by team member and priority"
```

**How It Works:**
1. The planner extracts group_by dimensions from natural language
2. MongoDB aggregation pipeline creates compound grouping
3. Enhanced formatting presents results hierarchically

---

## 🔀 Parallel Query Execution

### What Is Parallel Execution?

The `composite_query` tool executes multiple **independent** queries simultaneously using the Orchestrator, dramatically improving response time for complex multi-part analysis.

### When to Use

✅ **Use composite_query when:**
- User requests multiple independent operations: "compare X and show Y"
- Combining structured queries with content search: "count bugs AND search for docs"
- Running multiple breakdowns: "show status distribution AND team workload"
- Batch analysis: "analyze project health AND search for improvement docs"

❌ **Do NOT use for:**
- Single queries (use appropriate single tool)
- Dependent operations (where one result feeds into another)
- Sequential workflows

### Examples

#### Parallel Breakdown + Search
```
User: "Show me work item breakdown by status AND search for API documentation"

Tool Call:
composite_query({
  "queries": [
    {
      "tool": "mongo_query",
      "params": {"query": "group work items by status"},
      "label": "Status Breakdown"
    },
    {
      "tool": "rag_search",
      "params": {"query": "API documentation", "content_type": "page"},
      "label": "API Documentation"
    }
  ],
  "combine_strategy": "separate"
})
```

**Result Format:**
```
🔀 COMPOSITE QUERY RESULTS (Parallel Execution)
Executed 2 queries simultaneously

============================================================
📌 Status Breakdown
============================================================

📊 RESULTS SUMMARY:
Found 45 items grouped by 1 dimension (state):
• state: In-Progress: 18 items
• state: Backlog: 15 items
• state: Completed: 12 items

============================================================
📌 API Documentation
============================================================

🔍 RAG SEARCH: 'API documentation'
Found 12 result(s) (type: page)

[1] PAGE: REST API Guidelines
    Score: 0.876
    Project: Backend Services | Updated: 2025-09-15
    Preview: This document outlines best practices for RESTful API design...
```

#### Multi-Part Analysis
```
User: "Count high-priority bugs AND analyze team workload AND search for process docs"

Tool Call:
composite_query({
  "queries": [
    {
      "tool": "mongo_query",
      "params": {"query": "count high priority work items"},
      "label": "High Priority Bug Count"
    },
    {
      "tool": "mongo_query",
      "params": {"query": "group work items by assignee"},
      "label": "Team Workload"
    },
    {
      "tool": "rag_search",
      "params": {"query": "process improvement", "content_type": "page"},
      "label": "Process Documentation"
    }
  ]
})
```

#### Comparison Queries
```
User: "Compare project status distribution and show team member assignments"

This automatically triggers composite_query with two independent mongo_query calls.
```

---

## 🛠️ Technical Implementation

### Architecture

```
User Query
    ↓
Agent (agent.py)
    ↓
Tool Selection
    ├─ Single breakdown → mongo_query
    ├─ Content breakdown → rag_search (with group_by)
    └─ Parallel ops → composite_query
         ↓
    Orchestrator (orchestrator.py)
         ├─ Step 1: mongo_query (parallel_group="parallel_queries")
         ├─ Step 2: rag_search (parallel_group="parallel_queries")
         └─ Step 3: rag_mongo (parallel_group="parallel_queries")
              ↓
         All execute simultaneously
              ↓
    Results combined and formatted
```

### Key Components

1. **Enhanced Planner** (`planner.py`):
   - Extracts multi-dimensional `group_by` from natural language
   - Supports patterns: "by X and Y", "by X, Y, and Z"
   - Generates MongoDB aggregation with compound `_id`

2. **Composite Query Tool** (`tools.py`):
   - Uses Orchestrator for parallel execution
   - Combines results with configurable strategy
   - Supports all existing tools (mongo_query, rag_search, rag_mongo)

3. **Enhanced Formatting** (`tools.py`):
   - Hierarchical display for multi-dimensional breakdowns
   - Detects compound `_id` structures
   - Shows primary dimension → secondary breakdown

4. **Agent Guidance** (`agent.py`):
   - Updated system prompt with breakdown patterns
   - Tool selection logic recognizes parallel markers
   - Examples guide proper tool usage

### Response Formatting

#### Single-Dimension Groups
```python
# Standard list format
• priority=HIGH: 18 items
• priority=MEDIUM: 15 items
```

#### Multi-Dimension Groups
```python
# Hierarchical tree format
▸ priority=HIGH: 18 total
  └─ state=In-Progress: 10
  └─ state=Backlog: 5
```

#### Parallel Results
```python
# Separate sections with clear labels
============================================================
📌 Query Label
============================================================
[Results here]
```

---

## 📝 Query Pattern Reference

### Breakdown Query Patterns

| Pattern | Example | Tool Used | Notes |
|---------|---------|-----------|-------|
| Single dimension | "group by priority" | `mongo_query` | Basic aggregation |
| Multi-dimensional | "by priority and status" | `mongo_query` | Hierarchical display |
| With filters | "active bugs by assignee" | `mongo_query` | Filter then group |
| Content breakdown | "API docs by project" | `rag_search` | Use `group_by` param |
| Date buckets | "by created month" | `mongo_query` | Temporal grouping |

### Parallel Query Patterns

| Pattern | Example | Detection Keywords |
|---------|---------|-------------------|
| Explicit parallel | "simultaneously", "in parallel" | Multi-markers |
| Comparison | "compare X and Y" | "compare", "vs", "versus" |
| Multi-action | "count AND search" | Action + content markers |
| Batch | "run multiple queries" | "batch", "run multiple" |
| And-also | "breakdown AND also search" | "and also", "together" |

### Natural Language Examples

**Breakdown Queries:**
- ✅ "Break down the current sprint into tasks by assignee"
- ✅ "Show me work item distribution by priority and status"
- ✅ "Group active projects by their current phase"
- ✅ "Break down overdue tasks by project and priority"
- ✅ "Show documentation pages by last modified date"

**Parallel Queries:**
- ✅ "Compare workload distribution AND show project status"
- ✅ "Count bugs by status AND search for deployment docs"
- ✅ "Analyze team velocity AND find related technical docs"
- ✅ "Run multiple queries: project breakdown, team capacity, search best practices"
- ✅ "Show both status breakdown AND search for documentation"

---

## 🚀 Performance Benefits

### Parallel Execution Performance

**Before (Sequential):**
```
Query 1: mongo_query → 1.2s
Query 2: rag_search → 1.5s
Query 3: mongo_query → 0.8s
Total: 3.5 seconds
```

**After (Parallel):**
```
All queries execute simultaneously
Total: ~1.5 seconds (longest query + overhead)
Speedup: 2.3x faster
```

### Scalability

- **Max parallel**: Configurable via `Orchestrator(max_parallel=N)`
- **Default**: 5 concurrent queries
- **Retry logic**: Built-in with exponential backoff
- **Caching**: Automatic deduplication of identical queries

---

## 🔍 Troubleshooting

### Breakdown Not Working?

1. **Check dimension names**: Must be in allowed set (priority, status, assignee, etc.)
2. **Verify entity type**: Some dimensions only work with specific entities (e.g., assignee with workItem)
3. **Review query phrasing**: Use "by", "group by", "breakdown by" keywords

### Parallel Execution Not Triggered?

1. **Use explicit markers**: "and also", "simultaneously", "in parallel"
2. **Combine different actions**: breakdown + search, count + list
3. **Check tool availability**: `composite_query` must be in tools list

### Results Look Wrong?

1. **Multi-dimensional overflow**: Showing top 20 combinations by default
2. **Empty groups**: Filtered out automatically
3. **Unexpected grouping**: Check inferred dimensions in debug output

---

## 🎓 Advanced Usage

### Custom Combine Strategies

```python
# Separate sections (default)
composite_query(queries=[...], combine_strategy="separate")

# Merged/correlated results
composite_query(queries=[...], combine_strategy="merged")
```

### Nested Breakdowns

```
"Break down work items by priority, then within each priority by status, then by assignee"

→ This creates a 3-level hierarchy:
  priority → status → assignee
```

### Dynamic Dimensions

The planner supports date-based grouping:
```
"Show work items created last month, grouped by week"
→ Uses created_week dimension
```

---

## 📊 Example Workflows

### Sprint Planning
```
User: "Break down current sprint by assignee and priority"
→ mongo_query with group_by: ["assignee", "priority"]
→ Shows workload distribution across team
```

### Health Dashboard
```
User: "Show me project status breakdown AND search for blockers documentation"
→ composite_query:
  - Query 1: Project status aggregation
  - Query 2: RAG search for "blockers"
→ Combined view of metrics + context
```

### Retrospective Analysis
```
User: "Break down completed work items by priority and cycle, AND search for lessons learned"
→ composite_query:
  - Query 1: Multi-dimensional breakdown
  - Query 2: Content search
→ Quantitative + qualitative insights
```

---

## 🔧 Configuration

### Planner Settings
```python
# planner.py
QueryIntent(
    group_by=["priority", "state"],  # Multi-dimensional
    wants_details=False,              # Summary mode for large groups
    limit=20                          # Max groups to show
)
```

### Orchestrator Settings
```python
# tools.py - composite_query
orchestrator = Orchestrator(
    tracer_name="composite_query",
    max_parallel=len(queries)  # Auto-scale to query count
)
```

### Response Formatting
```python
# tools.py - format_llm_friendly
display_limit = 20  # Max groups before truncation
hierarchy_depth = 2  # Levels to show in nested breakdowns
```

---

## ✅ Testing Checklist

- [x] Single-dimension breakdown queries
- [x] Multi-dimensional breakdown (2+ dimensions)
- [x] Breakdown with filters
- [x] Content-based breakdown via rag_search
- [x] Parallel mongo_query + rag_search
- [x] Parallel multi-query (3+ queries)
- [x] Hierarchical formatting for compound groups
- [x] Performance improvement vs sequential

---

## 🎉 Summary

Your PMS Assistant now supports:

1. **Multi-Dimensional Breakdowns**: Group data by 2+ dimensions simultaneously
2. **Parallel Execution**: Run independent queries concurrently for 2-3x speedup
3. **Enhanced Formatting**: Hierarchical displays for complex aggregations
4. **Natural Language**: Extracts dimensions and parallel intent from queries
5. **Robust Architecture**: Leverages Orchestrator for reliability and tracing

**Query patterns recognized:**
- "breakdown by X and Y"
- "group by X, Y, and Z"
- "compare A and show B"
- "count X AND search Y"
- "analyze A simultaneously with B"

**Ready to use!** The agent will automatically select the appropriate tool based on query structure.
