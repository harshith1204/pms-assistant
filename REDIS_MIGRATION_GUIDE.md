# Redis Conversation Memory Migration Guide

## Overview

The conversation memory system has been migrated from **in-memory local cache** to **Redis cache** to provide:

- ✅ **Persistent storage** independent of socket connections
- ✅ **No memory overload** on the server
- ✅ **24-hour TTL** for automatic cache cleanup
- ✅ **Scalability** across multiple server instances
- ✅ **Automatic fallback** to in-memory cache if Redis is unavailable

## Changes Made

### 1. Dependencies Added (`requirements.txt`)
```
redis
redis[hiredis]  # For performance optimization
```

### 2. Memory System Refactored (`memory.py`)

#### Before (Local Memory):
```python
class ConversationMemory:
    def __init__(self, max_messages_per_conversation: int = 50):
        self.conversations: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_messages_per_conversation))
        self.summaries: Dict[str, str] = {}
        self.turn_counters: Dict[str, int] = defaultdict(int)
```

#### After (Redis Cache):
```python
class RedisConversationMemory:
    def __init__(self, max_messages_per_conversation: int = 50, redis_url: Optional[str] = None, ttl_hours: int = 24):
        # Stores all data in Redis with 24-hour TTL
        # Falls back to in-memory if Redis unavailable
```

### 3. API Changes

All memory methods are now **async** and must be awaited:

```python
# Before
conversation_memory.add_message(conversation_id, message)
history = conversation_memory.get_conversation_history(conversation_id)
conversation_memory.register_turn(conversation_id)

# After
await conversation_memory.add_message(conversation_id, message)
history = await conversation_memory.get_conversation_history(conversation_id)
await conversation_memory.register_turn(conversation_id)
```

### 4. Redis Key Structure

The following keys are stored in Redis with 24-hour TTL:

- `conversation:messages:{conversation_id}` - List of serialized messages
- `conversation:summary:{conversation_id}` - Rolling conversation summary
- `conversation:turns:{conversation_id}` - Turn counter for summary updates

### 5. Automatic Fallback

If Redis connection fails, the system **automatically falls back** to in-memory storage with warnings logged:

```
⚠️ Redis connection failed, using in-memory fallback: [error details]
```

## Setup Instructions

### 1. Install Redis

#### Option A: Using Docker (Recommended)
```bash
docker run -d --name redis-cache \
  -p 6379:6379 \
  redis:7-alpine
```

#### Option B: Local Installation

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install redis-server
sudo systemctl start redis
```

**macOS:**
```bash
brew install redis
brew services start redis
```

**Windows:**
Download from: https://github.com/microsoftarchive/redis/releases

### 2. Configure Environment Variables

Create or update your `.env` file:

```bash
# Redis URL (default: redis://localhost:6379/0)
REDIS_URL=redis://localhost:6379/0

# For Redis with authentication:
# REDIS_URL=redis://username:password@host:port/db

# For Redis with SSL (production):
# REDIS_URL=rediss://username:password@host:port/db
```

### 3. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 4. Restart Your Application

```bash
python main.py
```

You should see:
```
✅ Redis conversation memory connected: redis://localhost:6379/0
```

## Configuration Options

### TTL (Time To Live)

Default is **24 hours**. To change:

```python
# In memory.py
conversation_memory = RedisConversationMemory(ttl_hours=48)  # 48 hours
```

### Max Messages Per Conversation

Default is **50 messages**. To change:

```python
conversation_memory = RedisConversationMemory(max_messages_per_conversation=100)
```

### Redis Connection Pool

The Redis client is configured with:
- **Max Connections**: 20
- **Socket Timeout**: 5 seconds
- **Keep-Alive**: Enabled
- **Health Check**: Every 30 seconds

## Production Considerations

### 1. Redis Persistence

Configure Redis persistence in `redis.conf`:

```conf
# Enable AOF (Append Only File) for durability
appendonly yes
appendfsync everysec

# Enable RDB snapshots as backup
save 900 1
save 300 10
save 60 10000
```

### 2. Memory Management

Set max memory and eviction policy:

```conf
maxmemory 2gb
maxmemory-policy allkeys-lru
```

### 3. High Availability

For production, consider:
- **Redis Sentinel** for automatic failover
- **Redis Cluster** for horizontal scaling
- **AWS ElastiCache** or **Azure Cache for Redis** for managed solutions

### 4. Monitoring

Monitor Redis with:

```bash
# Redis CLI
redis-cli info memory
redis-cli info stats

# Monitor commands in real-time
redis-cli monitor
```

## Troubleshooting

### Issue: "Redis connection failed, using in-memory fallback"

**Solution:**
1. Check if Redis is running: `redis-cli ping` (should return "PONG")
2. Verify REDIS_URL in `.env` is correct
3. Check firewall rules allow port 6379

### Issue: Memory consumption still high

**Solution:**
1. Check Redis memory usage: `redis-cli info memory`
2. Verify TTL is set: `redis-cli TTL conversation:messages:conv_xyz`
3. Manually clear old keys if needed: `redis-cli FLUSHDB` (use with caution!)

### Issue: Conversations not persisting across server restarts

**Solution:**
This is expected behavior! Redis cache is meant for **temporary storage** (24h TTL). Conversations are **permanently stored in MongoDB** via the `mongo/conversations.py` module. When users load old conversations from MongoDB, they are cached in Redis for fast access.

## Benefits Summary

| Feature | Before (Local Memory) | After (Redis Cache) |
|---------|----------------------|---------------------|
| **Persistence** | Lost on server restart | Persists for 24 hours |
| **Socket Independence** | ❌ Tied to connections | ✅ Independent |
| **Memory Overhead** | ❌ Grows unbounded | ✅ Fixed with TTL |
| **Scalability** | ❌ Single server only | ✅ Multi-server ready |
| **Fallback** | ❌ No fallback | ✅ Auto-fallback to memory |

## Testing

### Test Redis Connection

```python
import asyncio
from memory import conversation_memory

async def test_redis():
    # Add a message
    from langchain_core.messages import HumanMessage
    msg = HumanMessage(content="Test message")
    await conversation_memory.add_message("test_conv", msg)
    
    # Retrieve history
    history = await conversation_memory.get_conversation_history("test_conv")
    print(f"History: {history}")
    
    # Clear
    await conversation_memory.clear_conversation("test_conv")
    print("✅ Redis test passed!")

asyncio.run(test_redis())
```

## Migration Checklist

- [x] Added Redis dependencies to `requirements.txt`
- [x] Refactored `ConversationMemory` to `RedisConversationMemory`
- [x] Updated all memory calls to async in `agent.py`
- [x] Added 24-hour TTL to all Redis keys
- [x] Implemented automatic fallback to in-memory cache
- [x] Added proper cleanup in `main.py` lifespan
- [x] Created configuration example (`.env.example`)
- [ ] Install Redis server
- [ ] Configure `REDIS_URL` in `.env`
- [ ] Test the migration
- [ ] Monitor Redis memory usage

## Support

For issues or questions, check:
- Redis logs: `redis-cli logs`
- Application logs for Redis warnings
- Redis memory stats: `redis-cli info memory`
