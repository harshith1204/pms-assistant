# Quick Start: Content Generation Optimization

## 🎯 What Changed?

We optimized content generation to **save ~67% of tokens** by sending generated content **directly to the frontend** instead of routing it through the LLM.

## 📦 What's Included?

### New Files
- `CONTENT_GENERATION_OPTIMIZATION.md` - Detailed explanation
- `OPTIMIZATION_FLOW.md` - Visual flow diagrams
- `test_generate_content.py` - Test script

### Modified Files
- `tools.py` - Added `generate_content` tool with direct WebSocket streaming
- `agent.py` - Updated prompts to use the new tool
- `websocket_handler.py` - Injects WebSocket connection into tool

## 🚀 How to Use

### 1. Agent Side (Already Done!)

The agent can now generate content with a simple request:

```python
# User asks: "Generate a bug report for login issue"
# Agent automatically calls:
generate_content(
    content_type="work_item",
    prompt="Bug: login fails on mobile"
)
# Agent receives: "✅ Content generated"
# Agent responds: "I've generated the bug report for you"
```

### 2. Frontend Side (Action Required)

Add this WebSocket message handler to your frontend:

```javascript
// In your WebSocket message handler
websocket.onmessage = (event) => {
  const message = JSON.parse(event.data);
  
  // Handle generated content
  if (message.type === 'content_generated') {
    if (message.success) {
      // Display the generated content
      if (message.content_type === 'work_item') {
        // Show work item in UI
        displayWorkItem(message.data);
      } else if (message.content_type === 'page') {
        // Show page content in Editor.js
        displayPageContent(message.data);
      }
    } else {
      // Show error message
      showError(message.error);
    }
  }
  
  // ... handle other message types
};
```

### Message Format

Your frontend will receive:

```json
{
  "type": "content_generated",
  "content_type": "work_item",
  "data": {
    "title": "Fix authentication bug",
    "description": "## Problem\n\nUsers cannot login..."
  },
  "success": true
}
```

For pages:

```json
{
  "type": "content_generated",
  "content_type": "page",
  "data": {
    "blocks": [
      { "id": "...", "type": "header", "data": {...} },
      { "id": "...", "type": "paragraph", "data": {...} }
    ]
  },
  "success": true
}
```

## 💰 Token Savings

**Example: Generate 2000-token work item**

| Metric | Before | After | Savings |
|--------|--------|-------|---------|
| Total Tokens | ~6000 | ~2013 | **67%** |
| Cost (GPT-4) | $0.18 | $0.06 | **$0.12** |
| Response Time | Slow | Fast | **Faster** |

## ✅ Testing

Run the test script:

```bash
# Make sure your API is running
python test_generate_content.py
```

Or test via the agent:

```
User: "Generate a bug report for authentication issue"
Agent: [Calls generate_content tool]
Frontend: [Receives full content via WebSocket]
Agent: "I've generated the bug report for you!"
```

## 🔍 How It Works

1. **User Request**: "Generate a bug report"
2. **Agent**: Calls `generate_content` tool
3. **Tool**: 
   - Generates content via API (2000 tokens)
   - Sends full content to frontend via WebSocket ✨
   - Returns to agent: "✅ Content generated" (3 tokens)
4. **Agent**: 
   - Receives minimal signal
   - Responds: "Bug report generated" (~10 tokens)
5. **User**: 
   - Sees full content on screen (from WebSocket)
   - Sees agent's confirmation

**Total LLM tokens: ~2013 instead of ~6000 = 67% savings!**

## 🛠️ Environment Setup

Optional configuration:

```bash
# .env file
API_BASE_URL=http://localhost:8000  # Your generation API
```

## 🎨 Frontend Examples

### React Example

```typescript
// useWebSocket.ts
const handleMessage = (event: MessageEvent) => {
  const message = JSON.parse(event.data);
  
  if (message.type === 'content_generated') {
    if (message.success) {
      if (message.content_type === 'work_item') {
        setWorkItem(message.data);
        toast.success('Work item generated!');
      } else if (message.content_type === 'page') {
        setPageBlocks(message.data.blocks);
        toast.success('Page generated!');
      }
    } else {
      toast.error(message.error);
    }
  }
};
```

### Vue Example

```javascript
// WebSocket handler
onMessage(message) {
  if (message.type === 'content_generated') {
    if (message.success) {
      if (message.content_type === 'work_item') {
        this.workItem = message.data;
        this.$toast.success('Work item generated!');
      } else if (message.content_type === 'page') {
        this.editorBlocks = message.data.blocks;
        this.$toast.success('Page generated!');
      }
    }
  }
}
```

## 🐛 Troubleshooting

**Q: Frontend not receiving content?**
- Check WebSocket connection is active
- Verify message handler includes `content_generated` type
- Check browser console for errors

**Q: Agent shows error "❌ Invalid content type"?**
- Ensure `content_type` is either `'work_item'` or `'page'`

**Q: Content generation slow?**
- Check your generation API response time
- Verify GROQ_API_KEY is set correctly

## 📚 Additional Resources

- `CONTENT_GENERATION_OPTIMIZATION.md` - Full technical details
- `OPTIMIZATION_FLOW.md` - Visual flow diagrams
- `test_generate_content.py` - Example usage

## 🎉 Success Indicators

You'll know it's working when:

1. ✅ Agent responds with simple confirmations like "Content generated"
2. ✅ User sees full content appear on screen immediately
3. ✅ Token usage for generation tasks drops by ~67%
4. ✅ No large content blocks in agent responses

---

**That's it! Your content generation is now optimized for maximum token efficiency!** 🚀
