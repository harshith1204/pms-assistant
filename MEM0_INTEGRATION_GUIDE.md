# Mem0 Integration Guide

This guide explains how to use Mem0 for intelligent memory management in your PMS Assistant.

## What is Mem0?

Mem0 is an intelligent memory layer for AI applications that:
- **Uses LLMs** to extract and maintain relevant facts from conversations
- **Stores memories** in vector databases for semantic retrieval
- **Automatically scores** memory relevance and filters outdated information
- **Provides smart retrieval** based on semantic similarity, not just recency

## Benefits Over Basic ConversationMemory

| Feature | Basic ConversationMemory | Mem0 |
|---------|-------------------------|------|
| Storage | In-memory (lost on restart) | Persistent database |
| Retrieval | Recent messages only | Semantic search across all conversations |
| Memory extraction | Manual | Automatic (LLM-powered) |
| Context understanding | Limited | Deep semantic understanding |
| Scaling | Limited by memory | Scales with database |
| Cross-session memory | No | Yes |

## Installation

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Copy and configure environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

## Configuration

### Required Environment Variables

Add these to your `.env` file:

```bash
# Enable Mem0
USE_MEM0=true

# Groq API Key (used for both agent and Mem0)
GROQ_API_KEY=your_groq_api_key_here

# Mem0 Qdrant Configuration
MEM0_QDRANT_HOST=localhost
MEM0_QDRANT_PORT=6333

# Mem0 LLM Configuration
MEM0_LLM_PROVIDER=groq
GROQ_MODEL=llama-3.3-70b-versatile

# Mem0 Embedding Model
MEM0_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

### Optional: Use Embedded Qdrant

If you want to use file-based Qdrant storage instead of a server:

```bash
MEM0_QDRANT_PATH=./qdrant_mem0_data
# Comment out MEM0_QDRANT_HOST and MEM0_QDRANT_PORT
```

## How It Works

### 1. Memory Addition

When a user or assistant sends a message, Mem0:
- Extracts important facts using an LLM
- Converts them to embeddings
- Stores them in Qdrant with metadata (timestamp, conversation_id, etc.)

```python
# Automatically called when messages are added
conversation_memory.add_message(conversation_id, message)
```

### 2. Memory Retrieval

When generating a response, Mem0:
- Takes the current user query
- Performs semantic search in Qdrant
- Returns the most relevant past memories
- Includes them as context for the LLM

```python
# Get relevant memories for context
memories = conversation_memory.get_relevant_memories(
    conversation_id=conversation_id,
    query=current_user_query,
    limit=5
)
```

### 3. Automatic Context Management

The `get_recent_context()` method combines:
- **Recent messages** (immediate conversation flow)
- **Relevant memories** (semantic context from past conversations)

```python
context = conversation_memory.get_recent_context(
    conversation_id=conversation_id,
    max_tokens=3000,
    include_semantic_memories=True  # Enable Mem0 semantic retrieval
)
```

## Usage Examples

### Basic Usage (Already Integrated!)

The integration is automatic. Just use the existing conversation memory API:

```python
from agent import conversation_memory, MongoDBAgent

# Initialize agent
agent = MongoDBAgent()
await agent.connect()

# Have a conversation - Mem0 handles memory automatically
response = await agent.run(
    query="Show me all bugs assigned to John",
    conversation_id="user123"
)

# Later, in a different session:
response = await agent.run(
    query="What were we discussing about John's bugs?",
    conversation_id="user123"
)
# Mem0 will retrieve relevant memories from the previous conversation!
```

### Advanced Usage

#### Get All Memories for a User

```python
memories = conversation_memory.get_all_memories(
    conversation_id="user123"
)

for memory in memories:
    print(f"Memory: {memory['memory']}")
    print(f"Created: {memory['created_at']}")
```

#### Search Specific Memories

```python
memories = conversation_memory.get_relevant_memories(
    conversation_id="user123",
    query="authentication bugs",
    limit=10
)
```

#### Delete Memories

```python
# Delete all memories for a user
conversation_memory.delete_memories(
    conversation_id="user123"
)
```

#### Clear Recent Buffer (Not Mem0 Storage)

```python
# Clear recent message buffer (Mem0 memories remain)
conversation_memory.clear_conversation("user123")
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    User Query                            │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│                  Mem0Manager                             │
│  ┌────────────────────────────────────────────────┐    │
│  │  1. Add message to recent buffer                │    │
│  │  2. Extract content using LLM                   │    │
│  │  3. Store in Qdrant (vector embeddings)         │    │
│  └────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│                    Qdrant Vector DB                      │
│  ┌────────────────────────────────────────────────┐    │
│  │  - Stores memory embeddings                     │    │
│  │  - Metadata: conversation_id, timestamp, etc.   │    │
│  │  - Enables semantic search                      │    │
│  └────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│               Context Retrieval                          │
│  ┌────────────────────────────────────────────────┐    │
│  │  1. Recent messages (immediate context)         │    │
│  │  2. Semantic search in Qdrant                   │    │
│  │  3. Combine and format for LLM                  │    │
│  └────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│                  LLM (Groq)                              │
│  Generates response with full context                    │
└─────────────────────────────────────────────────────────┘
```

## Troubleshooting

### Mem0 not initializing

**Error:** `Failed to initialize Mem0: ...`

**Solution:**
1. Check that Qdrant is running:
   ```bash
   docker run -p 6333:6333 qdrant/qdrant
   ```
2. Verify environment variables in `.env`
3. Check Qdrant connection:
   ```bash
   curl http://localhost:6333/collections
   ```

### Embedding dimension mismatch

**Error:** `Dimension mismatch: expected 384, got ...`

**Solution:**
- Make sure `MEM0_EMBEDDING_MODEL` matches the collection dimensions
- Default model `all-MiniLM-L6-v2` uses 384 dimensions
- If using a different model, update the config in `mem0_integration.py`

### Groq API errors

**Error:** `Groq API key not found`

**Solution:**
- Add `GROQ_API_KEY` to your `.env` file
- The same key is used for both the agent and Mem0

### Fallback to ConversationMemory

If Mem0 fails to initialize, the system automatically falls back to the basic `ConversationMemory`:

```
⚠️  Failed to initialize Mem0: ...
Falling back to basic ConversationMemory
```

This ensures your application continues working even if Mem0 has issues.

## Performance Considerations

### Memory vs Database

- **Recent messages** are kept in memory for fast access
- **Long-term memories** are stored in Qdrant (persistent)
- **Semantic search** adds ~50-100ms per query (worth it for context quality!)

### Token Usage

Mem0 uses LLM calls for:
- Memory extraction (~100-200 tokens per message)
- Memory updates (~50-100 tokens per update)

This is typically **much cheaper** than context window bloat from storing full conversations.

### Scaling

- Qdrant scales to millions of memories
- Use `user_id` scoping for multi-tenant applications
- Consider sharding by business/project for large deployments

## Migration from ConversationMemory

The integration is backward compatible! No code changes needed:

1. Install dependencies: `pip install -r requirements.txt`
2. Configure `.env` with Mem0 settings
3. Restart the application
4. Existing conversations will start using Mem0

To disable Mem0:
```bash
USE_MEM0=false
```

## Advanced Configuration

### Custom Mem0 Configuration

Edit `mem0_integration.py` to customize Mem0 behavior:

```python
config = {
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "collection_name": "custom_memories",
            "embedding_model_dims": 768,  # For larger models
        }
    },
    "llm": {
        "provider": "groq",
        "config": {
            "model": "llama-3.3-70b-versatile",
            "temperature": 0.0,  # More deterministic
            "max_tokens": 2000,
        }
    },
    # ... other config
}
```

### Multiple Memory Namespaces

Use different `user_id` values for different memory scopes:

```python
# User-specific memories
conversation_memory.add_message(
    conversation_id="conv123",
    message=message,
    user_id="user_john"
)

# Project-specific memories
conversation_memory.add_message(
    conversation_id="conv123",
    message=message,
    user_id="project_alpha"
)
```

## API Reference

See `mem0_integration.py` for full API documentation.

### Key Methods

- `add_message()`: Add a message and update memories
- `get_recent_context()`: Get context with semantic memories
- `get_relevant_memories()`: Search memories semantically
- `get_all_memories()`: Get all stored memories
- `delete_memories()`: Delete memories for a user/conversation
- `clear_conversation()`: Clear recent buffer (keeps Mem0 storage)

## Resources

- [Mem0 Documentation](https://docs.mem0.ai/)
- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [Groq API Documentation](https://console.groq.com/docs/)

## Support

For issues specific to this integration, check:
1. Application logs for error messages
2. Qdrant logs: `docker logs <qdrant_container>`
3. Mem0 GitHub issues: https://github.com/mem0ai/mem0
