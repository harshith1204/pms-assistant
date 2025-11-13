# Debug Instructions - Find the Issue

## Changes Made
Added comprehensive debug logging to track the entire request/response flow.

## How to Debug

### Step 1: Restart Backend
```bash
docker-compose restart backend
# OR
docker-compose down && docker-compose up -d
```

### Step 2: Watch Backend Logs
```bash
docker-compose logs -f backend
# OR if not using docker:
# tail -f backend.log
```

### Step 3: Send a Test Message from Frontend
Send a simple message like: **"Hello"**

### Step 4: Check the Logs
You should see this flow in the logs:

```
📨 WEBSOCKET: Received message: 'Hello...'
   conversation_id: conv_xxxxx
   user_id: 1eff982e-749f-6652-99d0-a1fb0d5128f4
   business_id: 1f0a7f43-8793-6a04-9ec9-3125e1eff878
🎯 WEBSOCKET: Starting agent processing...
🔄 WEBSOCKET: Calling agent.run_streaming...

🚀 AGENT: run_streaming called with query: Hello...
🔄 AGENT: Starting loop, max_steps=3

🔁 AGENT: Loop iteration 0/3
🤖 AGENT: Got LLM response, has_tool_calls=True/False, content_len=XXX
✅ AGENT: Final response detected, yielding content
📤 AGENT: Yielding XXX chars
✅ AGENT: Yielded successfully, returning

📦 WEBSOCKET: Got chunk #1, len=XXX
✅ WEBSOCKET: Agent completed, total chunks=1, final_response_len=XXX
📤 WEBSOCKET: Sending final_response to frontend...
✅ WEBSOCKET: final_response sent
🏁 WEBSOCKET: Sending complete signal
✅ WEBSOCKET: Complete signal sent
```

## What to Look For

### If you DON'T see "🚀 AGENT: run_streaming called"
- Agent is not being invoked
- Check MongoDB agent initialization in main.py
- Check if mongodb_agent variable exists

### If you see "🚀 AGENT" but no "🤖 AGENT: Got LLM response"
- LLM call is failing or hanging
- Check GROQ_API_KEY in .env
- Check internet connectivity to Groq API
- Check if LLM model exists

### If you see "🤖 AGENT: Got LLM response, has_tool_calls=True"
- Agent is calling tools instead of responding
- This is EXPECTED for some queries
- Agent should loop and finalize after tools
- Check if you see "⚠️  AGENT: Forcing finalization"

### If you see "⛔ AGENT: Exited loop" without "📤 AGENT: Yielding"
- Agent exhausted max_steps without yielding
- This is the BUG we're trying to fix
- Should see fallback: "📨 AGENT: Sending last_response as fallback"

### If you see "❌ AGENT ERROR:"
- Exception in agent code
- Read the traceback for details

### If NO logs appear at all
- WebSocket not connecting
- Check browser console for WebSocket errors
- Check if backend is running: `curl http://localhost:8000/health`

## Copy the Logs

**IMPORTANT:** Copy the ENTIRE log output and send it back so we can identify exactly where it's failing.

## Quick Health Check Commands

```bash
# Check if backend is running
docker ps | grep backend

# Check if MongoDB is accessible
docker exec -it <mongodb_container> mongosh --eval "db.runCommand({ ping: 1 })"

# Check if agent can connect
docker exec -it <backend_container> python -c "from agent.agent import MongoDBAgent; import asyncio; agent = MongoDBAgent(); asyncio.run(agent.connect()); print('✅ Connected')"
```
