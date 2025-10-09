# Content Generation Token Optimization

## Problem
When generating large content (work items, pages) through the agent, the full generated content was being returned to the LLM, causing:
- **Expensive token overhead**: Large generated content (thousands of tokens) sent back to LLM
- **Redundant processing**: LLM doesn't need to see content it just generated
- **Wasted costs**: Paying for tokens that provide no value

## Solution
Created a new `generate_content` tool that:
1. **Sends content DIRECTLY to the frontend** via WebSocket (bypasses agent completely)
2. **Returns only a minimal success signal** to the agent (`✅ Content generated`)
3. **Agent just acknowledges** without needing to process or talk about the content

### Key Changes

#### 1. New Tool: `generate_content` (tools.py)
```python
@tool
async def generate_content(
    content_type: str,
    prompt: str,
    template_title: str = "",
    template_content: str = "",
    context: Optional[Dict[str, Any]] = None
) -> str:
    """Generate work items or pages using LLM - returns SUMMARY only (not full content)."""
```

**What it does:**
- Calls your existing generation API (`/generate-work-item` or `/stream-page-content`)
- Receives the full generated content from the API
- **Sends full content directly to frontend** via WebSocket message:
  ```json
  {
    "type": "content_generated",
    "content_type": "work_item",
    "data": { /* full content here */ },
    "success": true
  }
  ```
- **Returns minimal signal to agent**: `✅ Content generated` (only 3 tokens!)
- Agent sees only success/failure - no content details

**Example flow:**
```
User: "Generate a bug report for login issue"
↓
Agent calls generate_content tool
↓
Tool generates 2000 tokens → Sends to frontend via WebSocket
↓
Tool returns to agent: "✅ Content generated" (3 tokens)
↓
Agent responds: "I've generated the bug report for you"
↓
User sees full content on screen (sent directly, not through agent)
```

#### 2. Updated Agent Instructions (agent.py)
Added the new tool to:
- System prompt (DEFAULT_SYSTEM_PROMPT)
- Tool selection logic (_select_tools_for_query)
- Routing instructions (both run() and run_streaming() methods)

**Usage examples:**
```python
# Generate work item
generate_content(
    content_type="work_item", 
    prompt="Bug: login fails on mobile"
)

# Generate page
generate_content(
    content_type="page",
    prompt="Create API documentation for authentication endpoints",
    context={...}
)
```

### Token Savings Example

**Before (without optimization):**
```
User: "Generate a bug report for login issue"
→ Tool generates 2000 tokens of content
→ Returns full 2000 tokens to agent
→ Agent sends 2000 tokens back to LLM for processing
→ Agent synthesizes response using those 2000 tokens
→ Total: ~6000+ tokens (generation + return + synthesis)
```

**After (with direct frontend streaming):**
```
User: "Generate a bug report for login issue"
→ Tool generates 2000 tokens of content
→ Content sent DIRECTLY to frontend via WebSocket (bypasses agent)
→ Tool returns to agent: "✅ Content generated" (3 tokens)
→ Agent sends 3 tokens to LLM
→ Agent responds: "I've generated the bug report" (~10 tokens)
→ Total: ~2013 tokens (generation + minimal signal)
```

**Savings: ~67% reduction in token usage for generation tasks!**

### Architecture Flow

```
User Request ("Generate work item")
    ↓
Agent (LLM decides to use generate_content tool)
    ↓
generate_content tool
    ↓
Generation API (/generate-work-item or /stream-page-content)
    ↓
Full content generated (2000+ tokens)
    ↓
[OPTIMIZATION POINT - DIRECT STREAMING]
    ↓
    ├─→ WebSocket → Frontend (full 2000 tokens)
    │   User sees full content immediately!
    │
    └─→ Agent (minimal "✅ Content generated" - 3 tokens)
        ↓
        Agent: "I've generated the bug report"
        
Flow comparison:
OLD: Generate → Agent → LLM → User (6000+ tokens)
NEW: Generate → Frontend (direct) + Agent gets signal (2013 tokens)
```

### Configuration

Set the API base URL in your environment (optional):
```bash
API_BASE_URL=http://localhost:8000  # Default value
```

### Benefits

1. **Massive Cost Reduction**: ~67% less tokens for generation tasks
2. **Faster Response**: Minimal data through LLM pipeline
3. **Better UX**: User sees full content immediately (direct streaming)
4. **Cleaner Agent Responses**: Agent just confirms success, no content regurgitation
5. **Scalable**: Works for any size content without token concerns

### Frontend Integration

Your frontend needs to listen for the `content_generated` WebSocket event:

```javascript
// Frontend WebSocket listener
websocket.onmessage = (event) => {
  const message = JSON.parse(event.data);
  
  if (message.type === 'content_generated') {
    if (message.success) {
      // Display the generated content
      if (message.content_type === 'work_item') {
        displayWorkItem(message.data);
      } else if (message.content_type === 'page') {
        displayPageContent(message.data);
      }
    } else {
      // Show error
      showError(message.error);
    }
  }
};
```

### Next Steps (Optional Enhancements)

1. **Direct DB Storage**: Modify tool to save generated content directly to MongoDB (no frontend needed)
2. **Progress Streaming**: Stream generation progress in real-time
3. **Batch Generation**: Generate multiple items with single confirmation
4. **Template Library**: Pre-defined templates for common generation tasks

## Usage

The tool is now available to the agent automatically. Just ask:

- "Generate a bug report for the login issue"
- "Create documentation page for our API"
- "Draft meeting notes for today's standup"

The agent will use the optimized tool and give you a summary without wasting tokens!
