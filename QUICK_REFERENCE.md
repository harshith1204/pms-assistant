# Intelligent Content Type Routing - Quick Reference

## 🎯 Content Type Mapping

| Query Contains | Content Type | Example |
|---------------|--------------|---------|
| release, documentation, notes, wiki | `page` | "What is the next release about?" |
| work items, bugs, tasks, issues | `work_item` | "What are recent work items about?" |
| cycle, sprint, iteration | `cycle` | "What is the active cycle about?" |
| module, component, feature area | `module` | "What is the CRM module about?" |
| project | `project` | "What is the payment project about?" |
| Ambiguous | `None` (all) | "Find content about authentication" |

## 🚀 Quick Examples

### Page Queries
```
"What is the next release about?"
"Show me documentation about APIs"
"Find notes about the migration"
"What's in the release notes?"
```
→ `rag_search(query='...', content_type='page')`

### Work Item Queries
```
"What are recent work items about?"
"Show me high priority bugs"
"Find tasks related to authentication"
"What issues are assigned to me?"
```
→ `rag_search(query='...', content_type='work_item')`

### Cycle Queries
```
"What is the active cycle about?"
"Show me sprint 5 details"
"What's in the current iteration?"
"Find information about Q2 cycle"
```
→ `rag_search(query='...', content_type='cycle')`

### Module Queries
```
"What is the CRM module about?"
"Show me the payment component details"
"What's in the auth module?"
"Find information about the API module"
```
→ `rag_search(query='...', content_type='module')`

### Project Queries
```
"What is the mobile app project about?"
"Show me the web platform project"
"Find details about the migration project"
```
→ `rag_search(query='...', content_type='project')`

### All-Type Queries
```
"Find content about OAuth"
"Search for anything mentioning API keys"
"What do we have about authentication?"
```
→ `rag_search(query='...', content_type=None)`

## 🔧 Usage

### Python API
```python
from agent import MongoDBAgent

agent = MongoDBAgent()
await agent.connect()

# Automatic routing - just ask naturally!
response = await agent.run("What is the next release about?")

await agent.disconnect()
```

### Expected Behavior
```python
# User asks about release
"What is the next release about?"
↓
# Agent automatically routes to page
rag_search(query='next release', content_type='page')
↓
# Returns only page documents (release notes, docs)
```

## 📊 Advanced Usage

### Grouping by Field
```python
# Content type + grouping
"Show work items about auth, grouped by priority"
→ rag_search(
    query='auth', 
    content_type='work_item',
    group_by='priority'
)
```

### Limiting Results
```python
# Content type + limit
"Show top 20 pages about APIs"
→ rag_search(
    query='APIs',
    content_type='page',
    limit=20
)
```

### Metadata Only
```python
# Content type without full content
"List cycles related to Q2"
→ rag_search(
    query='Q2',
    content_type='cycle',
    show_content=False
)
```

### Hybrid Queries
```python
# Structured + Semantic
"Count bugs by priority and show related docs"
→ mongo_query(query='count bugs by priority')
→ rag_search(query='bug documentation', content_type='page')
```

## 🎨 Keyword Cheatsheet

### Page Keywords
- release, documentation, docs, notes
- wiki, guide, readme, manual
- specification, overview

### Work Item Keywords
- work items, bugs, tasks, issues
- tickets, stories, defects
- features, enhancements

### Cycle Keywords
- cycle, sprint, iteration
- milestone, phase

### Module Keywords
- module, component, package
- feature area, subsystem
- library, plugin

### Project Keywords
- project, initiative
- program, portfolio

## ✅ Testing Quick Check

```bash
# Run test script
cd /workspace
python3 test_content_type_routing.py

# Expected output: Demonstrations of routing for 14+ query types
```

## 📝 Key Files

- **Implementation**: `agent.py` (lines 75-123, 984-1024, 1231-1271)
- **Tool Definition**: `tools.py` (lines 709-899)
- **Documentation**: `CONTENT_TYPE_ROUTING.md`
- **Tests**: `test_content_type_routing.py`
- **Summary**: `CHANGES_SUMMARY.md`

## 🔍 Troubleshooting

### Not routing correctly?
- Check if query contains clear keywords
- Make query more specific (e.g., "release notes" vs "show me info")
- Use explicit content type if needed (though not required)

### Want to search all types?
- Use generic/ambiguous query
- System will automatically use `content_type=None`

### Want multiple types?
- Ask for both explicitly: "Show pages and work items about auth"
- Agent will call rag_search multiple times

## 💡 Tips

1. **Be Specific**: Use clear keywords like "release", "bugs", "sprint"
2. **Natural Language**: Ask naturally - the agent understands context
3. **Trust the Routing**: The LLM selects appropriate content types automatically
4. **Combine Filters**: Use content_type with group_by, limit, etc.
5. **Check Results**: Review the tool calls to see routing decisions

## 🎯 Success Criteria

✅ Query about releases → Returns only page documents
✅ Query about bugs → Returns only work_item documents  
✅ Query about cycles → Returns only cycle documents
✅ Query about modules → Returns only module documents
✅ Ambiguous query → Searches all document types
✅ Multi-type query → Calls rag_search multiple times
✅ No manual content_type specification needed

---

**Happy querying! The agent now intelligently routes your searches to the right content types! 🚀**
