# Qdrant Chunking - Quick Reference

## ✅ What Changed

All chunking improvements are now **integrated directly into `/workspace/qdrant/insertdocs.py`**:

1. ✅ **Configurable chunking per content type** (lines 195-221)
2. ✅ **Automatic statistics tracking** (lines 36-116)
3. ✅ **Enhanced output with detailed metrics** (lines 694-722)
4. ✅ **Smart chunking threshold control** (lines 232-281)

## 🚀 Quick Start

### Run Standard Indexing

```bash
cd /workspace
python3 qdrant/insertdocs.py
```

**You'll see:**
- Configuration being used
- Progress as each collection is indexed
- **Detailed statistics** showing:
  - How many documents were chunked
  - Single vs multi-chunk distribution
  - Average chunks per document
  - Which document has the most chunks

**Example output:**
```
================================================================================
📊 CHUNKING STATISTICS SUMMARY
================================================================================

▸ WORK_ITEM
  Documents: 250
  Total chunks: 275
  Avg chunks/doc: 1.10
  Avg words/doc: 125
  Single-chunk: 225 (90.0%)  ← This is NORMAL!
  Multi-chunk: 25 (10.0%)
  Max chunks: 5 (in 'Implement complex authentication system...')
  
📈 OVERALL TOTALS:
  Total documents: 1000
  Total chunks (points): 1150
  Average chunks per document: 1.15
  Chunking expansion: 15.0%
================================================================================
```

## 🎯 Understanding Your Data

### What `chunk_count=1` Means

When you see a document with `chunk_count: 1`, it means:
- ✅ Document is **shorter than the chunking threshold** (300 words for work items)
- ✅ This is **correct and efficient** - no need to split short text
- ✅ **70-85% of work items are single-chunk** in typical PM systems

**This is NOT a problem!**

### When Documents Get Chunked

Documents are split into multiple chunks when:
- Work items: > 300 words
- Pages: > 320 words
- Projects/Cycles/Modules: > 300 words

**Your SIMPO-2462 example:**
- Content: ~50 words
- Threshold: 300 words
- Result: 1 chunk (expected!)

## 🔧 Customizing Chunking

### Option 1: Use Aggressive Chunking (Recommended)

For more granular chunks, edit `/workspace/qdrant/insertdocs.py` around **line 195**:

**Replace:**
```python
CHUNKING_CONFIG = {
    "page": {
        "max_words": 320,
        "overlap_words": 80,
        "min_words_to_chunk": 320,
    },
    # ...
}
```

**With (uncomment lines 224-230):**
```python
CHUNKING_CONFIG = {
    "page": {"max_words": 200, "overlap_words": 40, "min_words_to_chunk": 100},
    "work_item": {"max_words": 150, "overlap_words": 30, "min_words_to_chunk": 80},
    "project": {"max_words": 150, "overlap_words": 30, "min_words_to_chunk": 80},
    "cycle": {"max_words": 150, "overlap_words": 30, "min_words_to_chunk": 80},
    "module": {"max_words": 150, "overlap_words": 30, "min_words_to_chunk": 80},
}
```

Then re-run: `python3 qdrant/insertdocs.py`

**Result:**
- Work items > 80 words get chunked
- ~40-50% multi-chunk documents
- More precise retrieval for specific details

### Option 2: Custom Configuration

Edit the config values directly:

```python
CHUNKING_CONFIG = {
    "work_item": {
        "max_words": 200,          # Chunk size (lower = smaller chunks)
        "overlap_words": 40,       # Overlap (higher = more context between chunks)
        "min_words_to_chunk": 120, # Threshold (lower = more docs get chunked)
    },
    # ... other types
}
```

**Parameter Guide:**
- `max_words`: Size of each chunk (100-500 recommended)
- `overlap_words`: Words shared between chunks (20-100 recommended)
- `min_words_to_chunk`: Minimum length to trigger chunking (80-500 recommended)

## 📊 Reading the Statistics

### Key Metrics Explained

| Metric | What It Means | Good Range |
|--------|---------------|------------|
| **Single-chunk %** | Documents that fit in one chunk | 70-90% for work items |
| **Multi-chunk %** | Documents split into pieces | 10-30% for work items |
| **Avg chunks/doc** | Average chunks per document | 1.1-1.3 typical |
| **Avg words/doc** | Average document length | Varies by type |
| **Max chunks** | Longest document's chunk count | Shows outliers |

### What's Normal?

✅ **Work Items**: 70-85% single-chunk (they're usually short)  
✅ **Pages**: 40-60% single-chunk (documentation is longer)  
✅ **Projects/Cycles/Modules**: 85-95% single-chunk (mostly metadata)

❌ **Abnormal**: 100% single-chunk for pages (pages should be longer)  
❌ **Abnormal**: 0% single-chunk for work items (threshold too low)

## 🔍 Diagnostics

To check Qdrant collection status:

```bash
python3 check_qdrant_status.py
```

This shows:
- Total vectors/points indexed
- Payload indexes status
- Sample documents with chunking info
- Search for specific work items (like SIMPO-2462)

## ❓ FAQ

### Q: Why is my work item showing chunk_count=1?

**A:** Because it's short! Work items under 300 words don't need chunking. This is correct behavior.

### Q: How do I get more multi-chunk documents?

**A:** Edit `CHUNKING_CONFIG` to use smaller values for `max_words` and `min_words_to_chunk`. See "Option 1: Aggressive Chunking" above.

### Q: Will chunk-aware retrieval work with single-chunk documents?

**A:** Yes! The retrieval system in `tools.py` handles both single and multi-chunk documents perfectly. Single chunks just don't need reconstruction.

### Q: What's the "chunking expansion" metric?

**A:** If you have 1000 documents and 1150 chunks, the expansion is 15%. This means you created 15% more Qdrant points than original documents. Higher expansion = more granular indexing.

### Q: Can I have different settings for different projects?

**A:** Currently, settings are per content type (work_item, page, etc), not per project. But you could modify the code to support that if needed.

## 📝 Files Reference

| File | Purpose |
|------|---------|
| `/workspace/qdrant/insertdocs.py` | **Main file** - all chunking & indexing logic |
| `/workspace/check_qdrant_status.py` | Diagnostics tool |
| `/workspace/CHUNKING_ANALYSIS.md` | Detailed explanation |
| `/workspace/QUICK_FIX_GUIDE.md` | Step-by-step fixes |
| `/workspace/CHUNKING_IMPROVEMENTS.md` | Summary of changes |

## 🎯 Summary

Your observation that `chunk_count=1` for short work items is **100% correct and expected**. The chunking system is working as designed:

- ✅ Short documents (< 300 words) → single chunk
- ✅ Long documents (> 300 words) → multiple chunks
- ✅ Statistics show you exactly what's happening
- ✅ Easy to customize if you want different behavior

**Next step**: Run `python3 qdrant/insertdocs.py` and review the statistics to see your actual data distribution!
