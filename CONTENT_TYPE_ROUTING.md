# Intelligent Content Type Routing for RAG Search

## Overview

The agent now features **intelligent content type routing** that automatically selects the appropriate `content_type` parameter for RAG searches based on query semantics. This improves search precision and relevance by filtering results to the most appropriate document type.

## How It Works

The LLM analyzes the user's query and automatically determines which content type(s) to search based on keywords and semantic context:

### Content Type Mapping

| Query Keywords | Content Type | Example Queries |
|---------------|--------------|-----------------|
| `release`, `documentation`, `notes`, `wiki` | `page` | "What is the next release about?" |
| `work items`, `bugs`, `tasks`, `issues` | `work_item` | "What are recent work items about?" |
| `cycle`, `sprint`, `iteration` | `cycle` | "What is the active cycle about?" |
| `module`, `component`, `feature area` | `module` | "What is the CRM module about?" |
| `project` | `project` | "What is the payment project about?" |
| Ambiguous or multi-type | `None` (all types) | "Find content about authentication" |

## Usage Examples

### Single Content Type Search

**Query:** "What is the next release about?"
```python
rag_search(query='next release', content_type='page')
```
- Searches only `page` documents (release notes, documentation)
- More precise results focused on release-related pages

**Query:** "What are recent work items about?"
```python
rag_search(query='recent work items', content_type='work_item')
```
- Searches only `work_item` documents (bugs, tasks, issues)
- Filters out irrelevant pages, cycles, modules

**Query:** "What is the active cycle about?"
```python
rag_search(query='active cycle', content_type='cycle')
```
- Searches only `cycle` documents (sprints, iterations)
- Returns cycle-specific content

**Query:** "What is the CRM module about?"
```python
rag_search(query='CRM module', content_type='module')
```
- Searches only `module` documents (components, feature areas)
- Focused on module-level information

### Multi-Type or Ambiguous Queries

**Query:** "Find content about authentication"
```python
rag_search(query='authentication', content_type=None)
```
- Searches ALL content types
- Useful when the relevant information could be in multiple types

**Alternative for comprehensive search:**
```python
# Agent can call multiple searches in parallel for broad coverage
rag_search(query='authentication', content_type='page')
rag_search(query='authentication', content_type='work_item')
```

## Benefits

1. **Improved Precision**: Filters results to the most relevant document type
2. **Better Performance**: Searches smaller subsets of data
3. **Reduced Noise**: Eliminates irrelevant results from wrong content types
4. **Semantic Understanding**: LLM interprets query intent to choose appropriate type
5. **Flexible Fallback**: Can search all types when query is ambiguous

## Implementation Details

### System Prompt Enhancement

The system prompt now includes:
- Content type mapping rules
- Keyword-based routing guidelines
- Concrete examples for each content type
- Guidance for ambiguous queries

### Runtime Routing Instructions

The agent provides additional routing instructions at runtime:
- Smart content type selection rules
- Concrete examples with actual tool calls
- Guidance for single vs. multi-type searches

### Multi-Content-Type Support

For queries that require multiple content types:
```python
# Option 1: Search all types
rag_search(query='..., content_type=None)

# Option 2: Parallel searches (LLM-controlled)
rag_search(query='...', content_type='page')
rag_search(query='...', content_type='work_item')
```

## Testing

Test the feature with these example queries:

```python
# Should route to 'page'
"What is the Q2 release about?"
"Show me documentation about the API"
"Find notes about the migration"

# Should route to 'work_item'
"What bugs are high priority?"
"Show recent tasks about authentication"
"Find issues related to performance"

# Should route to 'cycle'
"What is sprint 5 about?"
"Show me the current iteration details"
"Find information about the Q1 cycle"

# Should route to 'module'
"What is the payments module about?"
"Show me details about the auth component"
"Find information about the CRM feature area"

# Should route to 'project'
"What is the mobile app project about?"

# Should search all types (None)
"Find anything about OAuth implementation"
"Search for content mentioning API keys"
```

## Advanced Usage

### Combining with Other Filters

Content type routing works seamlessly with other RAG search parameters:

```python
# Content type + grouping
rag_search(
    query='authentication', 
    content_type='work_item',
    group_by='priority'
)

# Content type + limit
rag_search(
    query='release notes',
    content_type='page',
    limit=20
)

# Content type + show_content control
rag_search(
    query='active cycles',
    content_type='cycle',
    show_content=False  # metadata only
)
```

### Hybrid Queries (Structured + Semantic)

For queries requiring both structured data and content analysis:

```python
# Independent operations - parallel execution
mongo_query(query='count bugs by priority')
rag_search(query='bug documentation', content_type='page')

# Dependent operations - sequential execution
# 1. First get structured data
mongo_query(query='list active cycles')
# 2. Then search related content
rag_search(query='active cycle details', content_type='cycle')
```

## Configuration

No additional configuration required - the feature is enabled by default and works through:
1. Enhanced system prompt (DEFAULT_SYSTEM_PROMPT)
2. Runtime routing instructions
3. Existing rag_search tool parameters

## Future Enhancements

Potential improvements:
- [ ] Confidence scoring for content type selection
- [ ] Automatic multi-type search when confidence is low
- [ ] Content type recommendations in responses
- [ ] Learning from user feedback to improve routing
- [ ] Support for custom content type mappings
- [ ] Hierarchical content type relationships
