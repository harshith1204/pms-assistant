# Implementation Plan: Integrate Long-Term Memory (QdrantMemoryStore)

## Overview
This document provides step-by-step instructions to properly integrate the QdrantMemoryStore for long-term conversation memory.

---

## Step 1: Create Global Instance

**File:** `agent.py`  
**Location:** After line 196 (after `conversation_memory = ConversationMemory()`)

```python
# Global long-term memory instance
qdrant_memory_store = QdrantMemoryStore()
```

---

## Step 2: Initialize in Application Lifespan

**File:** `main.py`  
**Location:** In the `lifespan()` function, after line 52

**Add:**
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

**Import required:**
Add to imports at top of `main.py`:
```python
from agent import qdrant_memory_store
```

---

## Step 3: Store Conversations After Each Interaction

**File:** `agent.py`  
**Method:** `MongoDBAgent.run_streaming()`  
**Location:** After line 1240 (before return in success path)

**Add:**
```python
# Store conversation in long-term memory (async, non-blocking)
if qdrant_memory_store.enabled and last_response:
    try:
        import asyncio
        asyncio.create_task(
            _store_in_long_term_memory(
                query=query,
                response=last_response.content,
                conversation_id=conversation_id
            )
        )
    except Exception as e:
        # Silent failure - don't break the main flow
        print(f"Warning: Failed to store in long-term memory: {e}")
```

**Add helper function** (after line 705, before `class MongoDBAgent`):
```python
async def _store_in_long_term_memory(query: str, response: str, conversation_id: str):
    """Helper to store conversation in QdrantMemoryStore asynchronously."""
    try:
        import time
        conversation_text = f"User Query: {query}\n\nAssistant Response: {response}"
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

---

## Step 4: Retrieve Relevant Past Context

**File:** `agent.py`  
**Method:** `MongoDBAgent.run_streaming()`  
**Location:** After line 1098 (after getting conversation_context)

**Add:**
```python
# Retrieve relevant long-term memories
past_memories = []
if qdrant_memory_store.enabled:
    try:
        past_memories = qdrant_memory_store.search(
            query=query,
            top_k=3,
            filters=None  # Can add conversation_id filter if needed
        )
    except Exception as e:
        print(f"Warning: Failed to retrieve long-term memories: {e}")
```

**Then update message building** (around line 1100-1104):
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
        if score > 0.5:  # Only include relevant memories
            memory_snippets.append(
                f"[Past Context {i+1}, relevance: {score:.2f}]\n"
                f"Q: {payload.get('query', '')[:150]}\n"
                f"A: {payload.get('response', '')[:150]}"
            )
    
    if memory_snippets:
        memory_context = "\n\n".join(memory_snippets)
        messages.append(SystemMessage(
            content=f"Relevant past conversations:\n{memory_context}\n\n"
                   f"Use these for context if relevant, but prioritize the current query."
        ))

messages.extend(conversation_context)
```

---

## Step 5: Add Same Logic to Non-Streaming Method

**File:** `agent.py`  
**Method:** `MongoDBAgent.run()`  
**Location:** Apply similar changes after line 905 (context retrieval) and before line 1067 (return)

Same pattern:
1. Retrieve past memories after line 905
2. Add to messages if relevant
3. Store conversation before returning (around line 1065)

---

## Step 6: Add Configuration (Optional)

**File:** Create new file `config.py` or add to `mongo/constants.py`

```python
import os

# Long-term memory configuration
ENABLE_LONG_TERM_MEMORY = os.getenv("ENABLE_LONG_TERM_MEMORY", "true").lower() == "true"
LONG_TERM_MEMORY_TOP_K = int(os.getenv("LONG_TERM_MEMORY_TOP_K", "3"))
LONG_TERM_MEMORY_MIN_SCORE = float(os.getenv("LONG_TERM_MEMORY_MIN_SCORE", "0.5"))
```

Then use in agent.py:
```python
if qdrant_memory_store.enabled and ENABLE_LONG_TERM_MEMORY:
    # ... memory logic
```

---

## Step 7: Add Observability

**File:** `agent.py`  
**Location:** In retrieval and storage sections

```python
# When retrieving
if tracer and past_memories:
    with tracer.start_as_current_span(
        "retrieve_long_term_memory",
        kind=trace.SpanKind.INTERNAL
    ) as mem_span:
        mem_span.set_attribute("memory_count", len(past_memories))
        mem_span.set_attribute("query_preview", query[:100])

# When storing
if tracer:
    with tracer.start_as_current_span(
        "store_long_term_memory",
        kind=trace.SpanKind.INTERNAL
    ) as store_span:
        store_span.set_attribute("conversation_id", conversation_id)
```

---

## Step 8: Testing

### Manual Testing Steps:

1. **Test initialization:**
   ```bash
   # Start the server and check logs
   python main.py
   # Look for: "✅ QdrantMemoryStore initialized successfully!"
   ```

2. **Test storage:**
   ```python
   # Send a query via WebSocket
   # Check Qdrant collection for new entries
   from qdrant_client import QdrantClient
   client = QdrantClient(url="http://localhost:6333")
   count = client.count(collection_name="pms_memory")
   print(f"Stored memories: {count.count}")
   ```

3. **Test retrieval:**
   ```python
   # Ask a similar question in a new conversation
   # Should see relevant past context in system message
   # Check traces/logs for "retrieve_long_term_memory" spans
   ```

### Automated Tests:

```python
# tests/test_long_term_memory.py
import pytest
from agent import QdrantMemoryStore

@pytest.mark.asyncio
async def test_qdrant_memory_store_initialization():
    store = QdrantMemoryStore()
    await store.initialize()
    assert store.enabled or store.client is None  # Either works or gracefully fails

@pytest.mark.asyncio
async def test_memory_storage_and_retrieval():
    store = QdrantMemoryStore()
    await store.initialize()
    
    if not store.enabled:
        pytest.skip("Qdrant not available")
    
    # Store
    store.upsert(
        text="Test query about bugs",
        payload={"query": "test", "response": "test response"}
    )
    
    # Retrieve
    results = store.search("bugs", top_k=1)
    assert len(results) > 0
    assert results[0]['payload']['query'] == "test"
```

---

## Rollback Plan

If issues arise:

1. **Disable long-term memory:**
   ```bash
   export ENABLE_LONG_TERM_MEMORY=false
   ```

2. **Remove from code:**
   - Comment out storage calls (Step 3)
   - Comment out retrieval calls (Step 4)
   - System continues working with short-term memory only

---

## Performance Considerations

1. **Async storage:** Store operations are non-blocking (using `asyncio.create_task`)
2. **Retrieval overhead:** ~50-200ms for semantic search (acceptable)
3. **Token usage:** Past context adds ~300-600 tokens (within budget)
4. **Graceful degradation:** If Qdrant fails, short-term memory still works

---

## Expected Behavior After Implementation

### Before:
- ❌ No memory across sessions
- ❌ Cannot reference past conversations
- ❌ No semantic search over history

### After:
- ✅ Remembers relevant past conversations
- ✅ Surfaces similar past queries automatically
- ✅ Maintains long-term context across sessions
- ✅ Gracefully degrades if Qdrant unavailable

---

## Files to Modify Summary

1. ✏️ `agent.py` - Add global instance, helper function, retrieval/storage logic
2. ✏️ `main.py` - Initialize in lifespan
3. ✏️ `config.py` (optional) - Add configuration
4. ✏️ `tests/test_long_term_memory.py` (new) - Add tests

---

## Estimated Implementation Time

- Core changes: 30-45 minutes
- Testing: 15-30 minutes
- Documentation: 15 minutes
- **Total: 1-1.5 hours**

---

## Questions to Consider

1. **Privacy:** Should long-term memory be per-user or shared?
   - Current: Shared across all conversations
   - Recommendation: Add user_id to filters

2. **Retention:** How long to keep memories?
   - Current: Indefinite
   - Recommendation: Add TTL or cleanup job

3. **Scope:** Store all conversations or only important ones?
   - Current: All exchanges
   - Recommendation: Add importance scoring

---

Generated: $(date)
