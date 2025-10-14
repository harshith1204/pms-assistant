# Context Management - Quick Reference Guide

## 🎯 What Was Improved?

### SHORT-TERM CONTEXT (Current Conversation)
**Before:**
- ❌ Fixed 10 message limit (arbitrary)
- ❌ No token management
- ❌ All messages treated equally
- ❌ Context overflow issues

**After:**
- ✅ Smart token-based limits (2000 tokens)
- ✅ Automatic summarization of older messages
- ✅ Priority given to recent messages
- ✅ Adaptive context window

### LONG-TERM CONTEXT (Conversation History)
**Before:**
- ❌ Memory-only storage
- ❌ Lost on server restart
- ❌ No conversation management
- ❌ Mock data in frontend

**After:**
- ✅ MongoDB persistence
- ✅ Survives restarts
- ✅ Full CRUD operations
- ✅ Real-time conversation list

---

## 📋 Key Features

### 1. Intelligent Context Management
```python
# Automatically optimizes context
conversation_context = await conversation_memory.get_smart_context(
    conversation_id="conv_123",
    max_tokens=2000,  # Token budget
    llm=llm  # For summarization
)

# Returns:
# - Recent messages (last 6-8)
# - Summary of older messages (if needed)
# - Fits within token budget
```

### 2. Persistent Storage
```python
# All messages automatically saved to MongoDB
- conversations collection (metadata)
- messages collection (all messages)

# Auto-generated fields:
- conversation_id
- title (from first message)
- timestamps (created_at, updated_at)
```

### 3. Conversation Management
```typescript
// Frontend API calls
GET    /conversations           // List all
GET    /conversations/{id}      // Get one with messages
DELETE /conversations/{id}      // Delete conversation
```

---

## 🔧 How It Works

### Message Flow
```
User sends message
    ↓
1. Load conversation from DB
    ↓
2. Get smart context (token-managed)
    ↓
3. Generate AI response
    ↓
4. Persist message to DB
    ↓
5. Update conversation metadata
```

### Context Strategy
```
Total Context Budget: 2000 tokens

[System Prompt: ~100 tokens]
    +
[Summary of old messages: ~200 tokens] (if needed)
    +
[Recent 6-8 messages: ~1700 tokens]
    =
Optimized context within budget
```

---

## 💡 Usage Examples

### Start New Conversation
```python
# Backend
response = await agent.run(
    query="Create a new project",
    conversation_id=None  # Auto-generates ID
)
# Creates: conversation + title + persists message
```

### Continue Conversation
```python
# Backend
response = await agent.run(
    query="What was the project name?",
    conversation_id="conv_123"  # Existing conversation
)
# Loads history + smart context + new response
```

### Frontend - Load Conversations
```typescript
// Fetch all conversations
const response = await fetch('/conversations');
const { conversations } = await response.json();

// Each conversation has:
// - id, title, summary
// - created_at, updated_at
```

### Frontend - Switch Conversation
```typescript
// User clicks on conversation in sidebar
onSelectConversation(conversationId);

// App loads messages for that conversation
// WebSocket uses that conversation_id for context
```

---

## 🎨 UI Changes

### Conversation Sidebar
- **Refresh Button**: Manually reload conversations
- **Real Data**: Shows actual conversations from DB
- **Smart Timestamps**: "2 hours ago", "Yesterday", etc.
- **Search**: Filter by title or summary
- **Delete**: Remove conversations permanently

### Chat Interface
- **Context Aware**: Uses smart context automatically
- **Persistent**: Messages saved immediately
- **Resumable**: Can continue any conversation

---

## 🚀 Performance Tips

### Best Practices
1. **Token Budget**: Adjust `max_tokens` based on your model
   ```python
   # For smaller models
   get_smart_context(conversation_id, max_tokens=1500)
   
   # For larger models
   get_smart_context(conversation_id, max_tokens=3000)
   ```

2. **Conversation Cleanup**: Delete old conversations
   ```typescript
   await fetch(`/conversations/${oldConvId}`, { method: 'DELETE' });
   ```

3. **Limit Message History**: Control how many messages to load
   ```python
   load_conversation_from_db(conversation_id, limit=50)
   ```

### Memory Usage
- **In-Memory Cache**: Last 100 messages per conversation
- **Database Storage**: Unlimited history
- **Smart Loading**: Only loads what's needed

---

## 🔍 Debugging

### Check Context Size
```python
# See how many tokens are being used
messages = conversation_memory.get_conversation_history(conv_id)
total_tokens = sum(conversation_memory.estimate_tokens(m) for m in messages)
print(f"Total tokens: {total_tokens}")
```

### View Database
```python
# Check what's in MongoDB
conversations = await conversation_memory.get_all_conversations()
print(f"Total conversations: {len(conversations)}")
```

### Frontend Console
```javascript
// Check what's loaded
console.log("Conversations:", conversations);
console.log("Active:", activeConversationId);
```

---

## ⚙️ Configuration

### Adjust Token Limits
In `agent.py`:
```python
conversation_context = await conversation_memory.get_smart_context(
    conversation_id, 
    max_tokens=2000,  # <- Change this
    llm=llm
)
```

### Change Message Limit
In `agent.py`:
```python
conversation_memory = ConversationMemory(
    max_messages_per_conversation=100  # <- Change this
)
```

### Adjust Context Window Size
In `agent.py` `get_smart_context()`:
```python
recent_message_count = min(8, len(messages))  # <- Change 8 to preferred size
```

---

## 🎓 Key Concepts

### Token vs Message Count
- **Tokens**: Actual units the LLM processes (more accurate)
- **Messages**: Number of exchanges (less precise)
- **Why tokens?**: Different messages have different lengths

### Why Summarization?
- Long conversations exceed token limits
- Summaries preserve key context
- Allows indefinite conversation length

### Hybrid Storage (Memory + DB)
- **Memory**: Fast access for current conversation
- **Database**: Persistent storage for history
- **Best of both**: Speed + persistence

---

## 📊 Monitoring

### What to Track
1. **Average context size** per conversation
2. **Summarization frequency** (how often it's needed)
3. **Database size** (storage usage)
4. **Response time** with context loading

### Health Checks
```python
# Check MongoDB connection
if conversation_memory.mongodb_client:
    print("✅ MongoDB connected")
else:
    print("❌ Using memory-only mode")
```

---

## 🔐 Data Privacy

### What's Stored
- User messages
- AI responses
- Tool outputs
- Conversation metadata

### What's Not Stored
- System prompts (regenerated)
- Temporary UI state
- WebSocket connections

### Retention
- Conversations kept indefinitely
- Manual deletion required
- Consider adding auto-cleanup for old conversations

---

## 🆘 Troubleshooting

### Context Too Large
**Problem**: Token limit exceeded  
**Solution**: Reduce `max_tokens` or increase summarization threshold

### Messages Not Persisting
**Problem**: MongoDB connection failed  
**Solution**: Check `MONGODB_CONNECTION_STRING` in constants.py

### Conversations Not Loading
**Problem**: API endpoint not responding  
**Solution**: Check backend logs, verify MongoDB is running

### Old Conversations Missing
**Problem**: Fresh database installation  
**Solution**: Normal - conversations persist after first message

---

## 📚 References

### Core Files
- `agent.py` - Context management logic
- `main.py` - API endpoints
- `frontend/src/components/chat/ConversationSidebar.tsx` - UI

### Key Methods
- `get_smart_context()` - Token management
- `persist_message()` - Save to DB
- `load_conversation_from_db()` - Load from DB
- `summarize_old_messages()` - Create summaries

---

**Quick Tips:**
💡 Start small - let a conversation grow to see summarization in action  
💡 Use the refresh button to see new conversations  
💡 Delete test conversations to keep things clean  
💡 Monitor MongoDB to see data persistence  

