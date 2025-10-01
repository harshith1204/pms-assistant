# Quick Start: Chunk-Aware RAG

## What Changed?

**Before**: RAG search returned 200-character snippets
**After**: RAG search returns 3000-5000 character reconstructed documents with full context

## TL;DR

```python
# Automatic - chunk-aware is ON by default
result = await rag_search(query="authentication methods", limit=5)

# Returns: 5 full documents with ~3-5KB context each (not 200-char snippets!)
```

## Why This Matters

### Problem
```
User: "Explain our OAuth 2.0 implementation"
Old System: "OAuth 2.0 Implementation. We use OAuth..." [truncated]
LLM: "Based on limited info, I think you might use..." [guessing/hallucinating]
```

### Solution
```
User: "Explain our OAuth 2.0 implementation"
New System: [Returns 3500 chars covering OAuth flows, token handling, SAML, JWT, error codes]
LLM: "Your OAuth 2.0 implementation supports authorization code flow, client credentials, and device flow. Access tokens expire after 1 hour and use JWT format..." [accurate, complete answer]
```

## How It Works (Simple Explanation)

1. **Documents are chunked** when indexed (320 words per chunk, 80-word overlap)
2. **Search finds relevant chunks** using vector similarity
3. **System groups chunks** by parent document
4. **Fetches adjacent chunks** for context (±1 chunk around each match)
5. **Reconstructs documents** by merging chunks intelligently
6. **Returns full context** to LLM (~3000-5000 chars instead of 200)

## Usage Examples

### Basic Usage (Default Behavior)
```python
from tools import rag_search

# Simple search - chunk-aware automatic
result = await rag_search(
    query="authentication implementation",
    content_type="page"
)

# Output: Full reconstructed documents with complete context
```

### Filtered Search
```python
# Search specific content type
result = await rag_search(
    query="API security",
    content_type="page",  # Only pages, not work_items
    limit=10
)
```

### Backward Compatible Mode
```python
# Disable chunk-aware (old 200-char behavior)
result = await rag_search(
    query="quick overview",
    use_chunk_aware=False  # Falls back to simple retrieval
)
```

### Grouped Results (Auto-Disables Chunk-Aware)
```python
# Grouping automatically uses standard retrieval
result = await rag_search(
    query="authentication",
    group_by="project_name"  # Chunk-aware disabled for grouping
)
```

## Output Format

### Example Output
```
🔍 CHUNK-AWARE RETRIEVAL: 3 document(s) reconstructed

[1] PAGE: Authentication Architecture Guide
    Relevance: 0.856 (avg: 0.803)
    Coverage: chunks 2-5 of 12
    Project: Security Framework | Visibility: PUBLIC
    Matched chunks: #2(0.86), #3(0.82), #4(0.79), #5(0.71)
    
    Content:
    OAuth 2.0 Implementation
    
    We use OAuth 2.0 for third-party authentication. The flow begins with
    client registration where applications receive a client_id and client_secret.
    
    Supported Flows:
    - Authorization Code Flow (for web apps with backend)
    - Client Credentials Flow (for service-to-service)
    - Device Flow (for IoT and limited-input devices)
    
    Token Handling:
    Access tokens expire after 1 hour and use JWT format. Refresh tokens 
    are valid for 30 days and stored securely in httpOnly cookies.
    
    [... continues with full context from chunks 2-5 ...]

[2] PAGE: API Security Best Practices
    Relevance: 0.742 (avg: 0.742)
    Coverage: chunks 1-2 of 6
    ...
```

### Key Elements

- **Relevance Scores**: 
  - `max_score`: Highest scoring chunk (0.856)
  - `avg_score`: Average of all matched chunks (0.803)
  
- **Coverage Info**: "chunks 2-5 of 12"
  - Shows which chunks from the full document
  - Total chunks in original document
  
- **Matched Chunks**: "#2(0.86), #3(0.82), #4(0.79)"
  - Individual chunk scores
  - Helps understand what parts matched best

- **Full Content**: 3000-5000 characters of merged chunks
  - Adjacent chunks included for context
  - Gaps marked (e.g., "...chunks 6-7 omitted...")

## Advanced Usage

### Direct API Access
```python
from qdrant.chunk_aware_retrieval import ChunkAwareRetriever
from qdrant.qdrant_initializer import RAGTool

rag_tool = RAGTool.get_instance()
retriever = ChunkAwareRetriever(
    qdrant_client=rag_tool.qdrant_client,
    embedding_model=rag_tool.embedding_model
)

docs = await retriever.search_with_context(
    query="OAuth implementation details",
    collection_name="pms_collection",
    content_type="page",
    limit=5,
    chunks_per_doc=3,        # Max scored chunks per document
    include_adjacent=True,    # Fetch ±1 chunks for context
    min_score=0.5            # Only chunks above this threshold
)

# Access reconstructed documents
for doc in docs:
    print(f"Title: {doc.title}")
    print(f"Score: {doc.max_score:.3f}")
    print(f"Coverage: {doc.chunk_coverage}")
    print(f"Content length: {len(doc.full_content)} chars")
    print(f"Full text:\n{doc.full_content}\n")
```

### Custom Formatting
```python
from qdrant.chunk_aware_retrieval import format_reconstructed_results

# Metadata only (no content)
output = format_reconstructed_results(
    docs=reconstructed_docs,
    show_full_content=False,     # Hide content
    show_chunk_details=True      # Show chunk scores
)

# Full content with chunk details
output = format_reconstructed_results(
    docs=reconstructed_docs,
    show_full_content=True,      # Show full merged content
    show_chunk_details=True      # Show which chunks matched
)
```

## Configuration Tuning

### For Short Documents
```python
# Documents < 1000 words (usually 1-3 chunks)
retriever.search_with_context(
    query="...",
    chunks_per_doc=1,          # Single chunk sufficient
    include_adjacent=False     # Skip adjacent fetches
)
```

### For Long Technical Docs
```python
# Documents > 5000 words (10+ chunks)
retriever.search_with_context(
    query="...",
    chunks_per_doc=5,          # Fetch more chunks
    include_adjacent=True,     # Important for continuity
    min_score=0.6             # Higher quality threshold
)
```

### For Performance-Critical Scenarios
```python
# Minimize latency
result = await rag_search(
    query="...",
    use_chunk_aware=False,    # Disable reconstruction
    show_content=False         # Metadata only
)
```

## Performance Characteristics

| Query Type | Latency | Context Size | Best For |
|------------|---------|--------------|----------|
| Chunk-Aware (default) | 350ms | 15-25KB | Detailed answers, complex questions |
| Standard (old) | 120ms | 2KB | Quick lookups, simple queries |
| Grouped | 200ms | 5KB | Analytics, distributions |
| No content | 100ms | <1KB | Metadata-only searches |

## Common Patterns

### Detailed Question Answering
```python
# User asks: "How does our authentication system work?"
result = await rag_search(
    query="authentication system architecture implementation",
    content_type="page",
    limit=3  # Get top 3 most relevant docs
)
# Returns: 3 full documents with complete implementation details
```

### Finding Specific Information
```python
# User asks: "What error codes does our OAuth implementation return?"
result = await rag_search(
    query="OAuth error codes error handling",
    content_type="page",
    limit=2
)
# Returns: Relevant sections with error code lists and handling logic
```

### Broad Exploration
```python
# User asks: "What documentation do we have about security?"
result = await rag_search(
    query="security documentation best practices",
    limit=10  # Cast wider net
)
# Returns: 10 documents covering various security topics
```

## Troubleshooting

### "No results found"
```python
# Try lowering the score threshold
retriever.search_with_context(
    query="...",
    min_score=0.3  # Lower from default 0.5
)
```

### "Results too long"
```python
# Reduce chunks per document
retriever.search_with_context(
    query="...",
    chunks_per_doc=1,          # Keep only best chunk
    include_adjacent=False     # Skip context chunks
)
```

### "Missing context"
```python
# Increase chunks and include adjacent
retriever.search_with_context(
    query="...",
    chunks_per_doc=5,          # More chunks
    include_adjacent=True      # Include ±1 for context
)
```

## Migration from Old System

### Before
```python
# Old code (< 200 chars per result)
results = await rag_search(query="auth", limit=5)
# Got: 5 results × 200 chars = 1KB total
```

### After (No Code Changes Needed!)
```python
# Same code, but now gets full context automatically
results = await rag_search(query="auth", limit=5)
# Gets: 5 docs × 3-5KB = 15-25KB total (full context!)
```

### Explicit Control
```python
# New parameter for explicit control
results = await rag_search(
    query="auth", 
    limit=5,
    use_chunk_aware=True  # Explicit enable (default)
)
```

## Key Benefits Summary

1. ✅ **15-25x More Context**: 3000-5000 chars vs 200 chars
2. ✅ **Better Answers**: LLM has complete information
3. ✅ **Less Hallucination**: Real details, not guesses
4. ✅ **Automatic**: ON by default, no code changes
5. ✅ **Backward Compatible**: `use_chunk_aware=False` for old behavior
6. ✅ **Smart Reconstruction**: Merges chunks, handles gaps
7. ✅ **Transparent**: Shows which chunks matched and why

## Questions?

- See [CHUNK_AWARE_RAG.md](./CHUNK_AWARE_RAG.md) for detailed architecture
- See [RAG_IMPROVEMENTS_SUMMARY.md](./RAG_IMPROVEMENTS_SUMMARY.md) for metrics and comparisons
- Check tests: `tests/test_chunk_aware_retrieval.py`
