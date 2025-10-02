# Quick Fix Guide: Context Implementation

## Summary
This guide provides the **exact code changes** needed to fix context issues.

---

## Fix #1: Enable Rolling Summaries (30 minutes)

### Change 1: Add to `agent.py` after line 1242

**Location:** In `MongoDBAgent.run_streaming()`, after the response is yielded

**Add this code:**
```python
# Register turn and update summary if needed
conversation_memory.register_turn(conversation_id)

if conversation_memory.should_update_summary(conversation_id, every_n_turns=3):
    try:
        asyncio.create_task(
            conversation_memory.update_summary_async(conversation_id, self.llm_base)
        )
    except Exception as e:
        print(f"Warning: Failed to update summary: {e}")
```

### Change 2: Add to `agent.py` after line 1065

**Location:** In `MongoDBAgent.run()`, before the final return

**Add this code:**
```python
# Register turn and update summary if needed
conversation_memory.register_turn(conversation_id)

if conversation_memory.should_update_summary(conversation_id, every_n_turns=3):
    try:
        asyncio.create_task(
            conversation_memory.update_summary_async(conversation_id, self.llm_base)
        )
    except Exception as e:
        print(f"Warning: Failed to update summary: {e}")
```

### Test:
```python
# After sending 3+ messages
from agent import conversation_memory
print(conversation_memory.summaries)
# Should show a summary for your conversation_id
```

---

## Fix #2: Enable Long-Term Memory (1-2 hours)

### Change 1: Add to `agent.py` after line 196

**Location:** Right after `conversation_memory = ConversationMemory()`

**Add:**
```python
# Global long-term memory instance
qdrant_memory_store = QdrantMemoryStore()
```

### Change 2: Add helper function to `agent.py` before line 706

**Location:** Before `class MongoDBAgent:`

**Add:**
```python
async def _store_in_long_term_memory(query: str, response: str, conversation_id: str):
    """Store conversation in QdrantMemoryStore asynchronously."""
    try:
        import time
        conversation_text = f"User: {query}\n\nAssistant: {response}"
        qdrant_memory_store.upsert(
            text=conversation_text,
            payload={
                "conversation_id": conversation_id,
                "timestamp": time.time(),
                "query": query,
                "response": response,
                "type": "conversation_exchange"
            }
        )
    except Exception as e:
        print(f"Error storing in long-term memory: {e}")
```

### Change 3: Add to `main.py` after line 52

**Location:** In `lifespan()` function, after RAGTool initialization

**First, add import at top of file:**
```python
from agent import qdrant_memory_store
```

**Then add in lifespan():**
```python
# Initialize long-term memory
try:
    await qdrant_memory_store.initialize()
    if qdrant_memory_store.enabled:
        print("✅ QdrantMemoryStore initialized successfully!")
    else:
        print("⚠️  QdrantMemoryStore disabled (Qdrant not available)")
except Exception as e:
    print(f"⚠️  QdrantMemoryStore initialization failed: {e}")
```

### Change 4: Retrieve memories in `agent.py` after line 1098

**Location:** In `run_streaming()`, after getting conversation_context

**Add:**
```python
# Retrieve relevant long-term memories
past_memories = []
if qdrant_memory_store.enabled:
    try:
        past_memories = qdrant_memory_store.search(query, top_k=3)
    except Exception as e:
        print(f"Warning: Failed to retrieve long-term memories: {e}")
```

### Change 5: Include memories in context in `agent.py` at line 1100-1104

**Location:** Replace the message building section

**Replace:**
```python
# Build messages with optional system instruction
messages: List[BaseMessage] = []
if self.system_prompt:
    messages.append(SystemMessage(content=self.system_prompt))
messages.extend(conversation_context)
```

**With:**
```python
# Build messages with optional system instruction
messages: List[BaseMessage] = []
if self.system_prompt:
    messages.append(SystemMessage(content=self.system_prompt))

# Add relevant long-term memories if available
if past_memories:
    memory_snippets = []
    for i, mem in enumerate(past_memories):
        payload = mem.get('payload', {})
        score = mem.get('score', 0.0)
        if score > 0.5:  # Only high-relevance memories
            memory_snippets.append(
                f"[Past Context {i+1}]\n"
                f"Q: {payload.get('query', '')[:150]}\n"
                f"A: {payload.get('response', '')[:150]}"
            )
    
    if memory_snippets:
        memory_context = "\n\n".join(memory_snippets)
        messages.append(SystemMessage(
            content=f"Relevant past conversations:\n{memory_context}"
        ))

messages.extend(conversation_context)
```

### Change 6: Store conversations in `agent.py` after line 1240

**Location:** In `run_streaming()`, before the final return

**Add:**
```python
# Store in long-term memory (non-blocking)
if qdrant_memory_store.enabled and last_response:
    try:
        asyncio.create_task(
            _store_in_long_term_memory(query, last_response.content, conversation_id)
        )
    except Exception as e:
        print(f"Warning: Failed to store in long-term memory: {e}")
```

### Change 7: Apply same changes to `run()` method

**Location:** Lines 905 (retrieve) and 1065 (store)

Apply the same retrieval and storage logic to the non-streaming `run()` method.

### Test:
```python
# After sending some queries
from qdrant_client import QdrantClient
client = QdrantClient(url="http://localhost:6333")
count = client.count(collection_name="pms_memory")
print(f"Stored memories: {count.count}")

# Test retrieval
from agent import qdrant_memory_store
results = qdrant_memory_store.search("your query", top_k=3)
print(f"Found {len(results)} memories")
```

---

## Quick Verification Checklist

After implementing all changes:

### Rolling Summaries:
- [ ] Code added after line 1242 in `run_streaming()`
- [ ] Code added after line 1065 in `run()`
- [ ] Test: Send 3+ messages, check `conversation_memory.summaries`

### Long-Term Memory:
- [ ] Global instance created (after line 196)
- [ ] Helper function added (before line 706)
- [ ] Import added to `main.py`
- [ ] Initialization added to lifespan
- [ ] Retrieval added (after line 1098)
- [ ] Messages updated (lines 1100-1104)
- [ ] Storage added (after line 1240)
- [ ] Test: Check Qdrant collection has entries

---

## Exact Line Numbers Reference

| File | Action | Line Number | Description |
|------|--------|-------------|-------------|
| `agent.py` | Add | 196 | Create `qdrant_memory_store` instance |
| `agent.py` | Add | ~705 | Add `_store_in_long_term_memory()` helper |
| `agent.py` | Modify | 1098 | Retrieve past memories |
| `agent.py` | Modify | 1100-1104 | Include memories in messages |
| `agent.py` | Add | 1065 | Register turn + summary in `run()` |
| `agent.py` | Add | 1065 | Store in long-term memory in `run()` |
| `agent.py` | Add | 1242 | Register turn + summary in `run_streaming()` |
| `agent.py` | Add | 1242 | Store in long-term memory in `run_streaming()` |
| `main.py` | Add | Top | Import `qdrant_memory_store` |
| `main.py` | Add | 52 | Initialize long-term memory |

---

## Rollback Plan

If anything breaks:

1. **Disable rolling summaries:** Comment out the `register_turn()` and summary calls
2. **Disable long-term memory:** Set `qdrant_memory_store.enabled = False` in main.py
3. **Emergency:** Revert all changes to last commit

---

## Performance Impact

**Expected overhead:**
- Rolling summaries: ~2-5 seconds every 3 turns (async, non-blocking)
- Long-term memory storage: ~50-100ms per message (async, non-blocking)
- Long-term memory retrieval: ~50-200ms per query (synchronous)

**Total impact:** < 300ms per query (acceptable for chat interface)

---

## Environment Variables (Optional)

Add to your `.env` file:

```bash
# Long-term memory config
ENABLE_LONG_TERM_MEMORY=true
LONG_TERM_MEMORY_TOP_K=3
LONG_TERM_MEMORY_MIN_SCORE=0.5

# Rolling summary config
SUMMARY_UPDATE_INTERVAL=3
MAX_SUMMARY_TOKENS=600
```

---

## Support

If you encounter issues:
1. Check the full analysis in `CONTEXT_IMPLEMENTATION_ANALYSIS.md`
2. Review detailed steps in `FIX_LONG_TERM_MEMORY.md`
3. Check logs for error messages
4. Test each component independently

---

Generated: $(date)
