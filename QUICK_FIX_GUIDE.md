# Quick Fix Guide: Qdrant Chunking & Indexing Issues

## 🎯 Understanding Your Issue

You saw:
```
chunk_index: 0
chunk_count: 1
```

And you're worried about:
1. Chunking not happening
2. Vector index count being 0
3. RAG tools not working properly

## ✅ TL;DR - Is This Actually A Problem?

**NO** - In most cases, `chunk_count=1` is **normal and correct**:
- Your example work item has ~50 words
- Chunking threshold is 300 words
- Short documents **should not** be chunked
- **70-80% of typical PM work items are single-chunk** ← This is expected!

## 🔍 Step 1: Run Diagnostics (Required)

This will tell you if there's an actual problem:

```bash
cd /workspace
python3 check_qdrant_status.py
```

**What to look for:**
- ✅ `Vectors count > 0` and `Points count > 0` → Collection is indexed
- ✅ Payload schema shows indexes for `content_type`, `title`, `full_text` → Indexing works
- ⚠️  `Vectors count = 0` → Collection is empty, need to re-index
- ⚠️  No payload schema → Indexes not created properly

## 🛠️ Step 2: Fixes (If Needed)

### Fix A: Collection is Empty (vectors count = 0)

**Problem**: Nothing indexed in Qdrant

**Solution**: Run initial indexing
```bash
cd /workspace
python3 qdrant/insertdocs.py
```

This will index all MongoDB collections to Qdrant.

---

### Fix B: You Want MORE Chunking (More Multi-Chunk Documents)

**Problem**: Most documents are single-chunk, you want more granularity

**Solution**: Use aggressive chunking

1. **Edit `/workspace/qdrant/chunking_config.py`:**
```python
# Line 78 - Change from DEFAULT to AGGRESSIVE
ACTIVE_CONFIG = AGGRESSIVE_CHUNK_CONFIG  # ← Change this line
```

2. **Re-index with statistics:**
```bash
cd /workspace
python3 qdrant/reindex_with_stats.py
```

This will show you:
- How many documents got chunked
- Average chunks per document
- Distribution of chunk counts

**Expected results with AGGRESSIVE:**
- Work items > 80 words → chunked
- 40-50% multi-chunk documents
- Better granularity for search

---

### Fix C: Payload Indexes Missing

**Problem**: Filtering by content_type, displayBugNo, etc. doesn't work

**Solution**: Already handled by `insertdocs.py`, but you can verify:

```python
# Check if indexes exist
from qdrant.dbconnection import qdrant_client, QDRANT_COLLECTION

info = qdrant_client.get_collection(QDRANT_COLLECTION)
print("Payload indexes:", info.payload_schema)
```

If empty, re-run indexing (Fix A).

---

### Fix D: Chunk-Aware Retrieval Not Working

**Problem**: RAG search doesn't use chunk-aware retrieval

**Check tools.py usage:**
```python
# In tools.py, line 759, verify:
if use_chunk_aware and not group_by:  # ← Should be True
    from qdrant.retrieval import ChunkAwareRetriever
    # ... uses advanced retrieval
```

**Solution**: Make sure `use_chunk_aware=True` when calling `rag_search`:
```python
await rag_search.ainvoke({
    "query": "your query",
    "use_chunk_aware": True,  # ← Ensure this is True (default)
})
```

## 📊 Step 3: Verify Results

After re-indexing, check specific work item:

```bash
python3 check_qdrant_status.py
```

Look for the section:
```
🔎 Searching for work items with SIMPO-2462...
```

This will show you:
- If your specific work item is indexed
- Its chunk count
- Content length

## 🎓 Understanding the Numbers

### What's Normal?

| Content Type | Avg Words | Typical Chunk Count | % Multi-Chunk |
|-------------|-----------|---------------------|---------------|
| Work Items  | 50-150    | 1                   | 20-30%        |
| Pages       | 200-500   | 1-2                 | 40-60%        |
| Projects    | 30-100    | 1                   | 10%           |
| Cycles      | 20-80     | 1                   | 5%            |
| Modules     | 30-100    | 1                   | 10%           |

**If you see these numbers → everything is working correctly!**

### What's Abnormal?

- ❌ 0 vectors/points → Nothing indexed, run Fix A
- ❌ 100% single-chunk documents → Chunking config too conservative
- ❌ No multi-chunk documents for pages → Pages are very short OR chunking disabled

## 🔧 Advanced: Custom Chunking

If you want fine-tuned control, edit `/workspace/qdrant/chunking_config.py`:

```python
# Create custom configuration
CUSTOM_CONFIG = {
    "work_item": {
        "max_words": 200,          # Chunk size
        "overlap_words": 40,       # Overlap between chunks
        "min_words_to_chunk": 100, # Minimum length to trigger chunking
    },
    "page": {
        "max_words": 250,
        "overlap_words": 50,
        "min_words_to_chunk": 150,
    },
    # ... other types
}

# Activate it
ACTIVE_CONFIG = CUSTOM_CONFIG  # Line 78
```

Then re-index with `python3 qdrant/reindex_with_stats.py`.

## 📞 Still Having Issues?

If after running diagnostics you see:

1. **Vectors count = 0**: 
   - Run `python3 qdrant/insertdocs.py`
   - Check MongoDB connection in `qdrant/dbconnection.py`

2. **Search not working**:
   - Check if `use_chunk_aware=True` in tool calls
   - Verify payload indexes exist (run diagnostics)
   - Check query embedding model is loaded

3. **No multi-chunk documents**:
   - This is NORMAL for short PM data
   - Use aggressive chunking (Fix B) if you want more

4. **Retrieval returns wrong results**:
   - Check if embeddings are correct
   - Try increasing `limit` parameter
   - Verify `content_type` filter is set correctly

## 🚀 Quick Start (Most Common Case)

If you just want to get started:

```bash
# 1. Run diagnostics
python3 check_qdrant_status.py

# 2. If vectors count = 0, index everything
python3 qdrant/insertdocs.py

# 3. Run diagnostics again to verify
python3 check_qdrant_status.py

# 4. If you want more chunking (optional)
# Edit chunking_config.py: ACTIVE_CONFIG = AGGRESSIVE_CHUNK_CONFIG
# Then: python3 qdrant/reindex_with_stats.py
```

## Summary

| Your Concern | Status | Action |
|-------------|--------|--------|
| `chunk_count=1` for short work items | ✅ Normal | None needed |
| Vector index count is 0 | ⚠️  Needs verification | Run diagnostics (Step 1) |
| Chunking not happening | ℹ️  Conditional | Normal for short text |
| RAG retrieval not working | ⚠️  Depends | Check `use_chunk_aware=True` |

**Bottom line**: Run the diagnostic script first, then decide if you need to make changes!
