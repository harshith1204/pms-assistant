# Content Generation Token Optimization

## Problem
When generating large content (work items, pages) through the agent, the full generated content was being returned to the LLM, causing:
- **Expensive token overhead**: Large generated content (thousands of tokens) sent back to LLM
- **Redundant processing**: LLM doesn't need to see content it just generated
- **Wasted costs**: Paying for tokens that provide no value

## Solution
Created a new `generate_content` tool that returns **ONLY a compact summary** instead of full content.

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
- **Returns only a summary** to the agent:
  - Work items: Title preview + word count + status
  - Pages: Block count + content preview + status
- Full content is available from the API response but NOT sent back to the LLM

**Example output (instead of full content):**
```
✅ Work item generated successfully!
Title: Fix login authentication bug on mobile devices
Content: 245 words (This work item addresses the critical issue where users are unable to log in on mobile devices...)
Status: Ready to save
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
→ Total: ~4000 tokens (generation + re-processing)
```

**After (with optimization):**
```
User: "Generate a bug report for login issue"
→ Tool generates 2000 tokens of content
→ Returns ~50 token summary to agent
→ Agent sends 50 tokens to LLM for synthesis
→ Total: ~2050 tokens (generation + summary)
```

**Savings: ~50% reduction in token usage for generation tasks**

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
[OPTIMIZATION POINT]
    ↓
Return summary only (~50 tokens) ← Agent receives this
    ↓
Agent synthesizes response with summary
    ↓
User sees confirmation

Note: Full content is available from API but never sent back to LLM
```

### Configuration

Set the API base URL in your environment (optional):
```bash
API_BASE_URL=http://localhost:8000  # Default value
```

### Benefits

1. **Cost Reduction**: ~50% less tokens for generation tasks
2. **Faster Response**: Less data to process
3. **Same Functionality**: Full content still generated and available
4. **Better UX**: User gets concise confirmation instead of overwhelming output

### Next Steps (Optional Enhancements)

1. **Direct DB Storage**: Modify tool to save generated content directly to MongoDB
2. **Frontend Integration**: Return content ID for frontend to fetch/display separately
3. **Streaming Support**: Stream only progress updates, not full content
4. **Webhook Pattern**: Generate content async, notify when complete

## Usage

The tool is now available to the agent automatically. Just ask:

- "Generate a bug report for the login issue"
- "Create documentation page for our API"
- "Draft meeting notes for today's standup"

The agent will use the optimized tool and give you a summary without wasting tokens!
