# Agent Debugging Guide

## Overview
This guide documents the key differences between the working legacy agent and the current implementation, along with comprehensive tests to debug issues.

## Key Differences Found

### 1. Import Path Structure

**Current Version (agent/):**
```python
from agent.memory import conversation_memory
from agent.tools import tools
from agent.orchestrator import Orchestrator
from agent.planner import plan_and_execute_query
```

**Legacy Version (legacy code/):**
```python
from memory import conversation_memory
import tools
from orchestrator import Orchestrator
from planner import plan_and_execute_query
```

**Issue:** The current version uses absolute imports with `agent.` prefix, which may cause import errors if the module structure is not properly configured.

### 2. Logging Differences

**Current Version:**
- Uses `logging.getLogger(__name__)` and `logger.error()`, `logger.warning()`
- Errors may be silently logged

**Legacy Version:**
- Uses `print()` statements for debugging
- Errors are immediately visible in console

**Issue:** Current version's logging might hide errors during development.

### 3. Tool Registration

Both versions register tools similarly, but the current version has additional complexity:

**Current (agent/tools.py line 1730-1734):**
```python
tools = [
    mongo_query,
    rag_search,
    generate_content,
]
```

**Legacy (legacy code/tools.py line 1728-1732):**
```python
tools = [
    mongo_query,
    rag_search,
    generate_content,
]
```

Same structure, but import paths differ.

### 4. Agent Initialization

**Current (agent/agent.py line 446-453):**
```python
def __init__(self, max_steps: int = 8, system_prompt: Optional[str] = DEFAULT_SYSTEM_PROMPT, enable_parallel_tools: bool = True):
    self.llm_base = llm
    self.connected = False
    self.max_steps = max_steps
    self.system_prompt = system_prompt
    self.tracing_enabled = False
    self.enable_parallel_tools = enable_parallel_tools
```

**Legacy (legacy code/agent.py line 441-448):**
```python
def __init__(self, max_steps: int = 8, system_prompt: Optional[str] = DEFAULT_SYSTEM_PROMPT, enable_parallel_tools: bool = True):
    self.llm_base = llm
    self.connected = False
    self.max_steps = max_steps
    self.system_prompt = system_prompt
    self.tracing_enabled = False
    self.enable_parallel_tools = enable_parallel_tools
```

Identical initialization.

### 5. WebSocket Handler Differences

**Current (websocket_handler.py line 16):**
```python
from agent.planner import plan_and_execute_query
```

**Legacy (legacy code/websocket_handler.py line 15):**
```python
from planner import plan_and_execute_query
```

## Test Files Created

### 1. test_tool_calling.py
**Purpose:** Test fundamental tool execution and LLM binding

**Tests:**
- Tool imports from both current and legacy paths
- Direct tool execution (mongo_query, rag_search)
- Tool binding to LLM
- Tool execution from LLM responses

**Run:** `python tests/test_tool_calling.py`

### 2. test_agent_conversation.py
**Purpose:** Test full agent conversation flow

**Tests:**
- Agent initialization
- Simple queries (no tools)
- Queries requiring mongo_query
- Queries requiring rag_search
- Multi-turn conversations with context
- Parallel tool execution
- Error handling

**Run:** `python tests/test_agent_conversation.py`

### 3. test_websocket_interaction.py
**Purpose:** Test WebSocket message flow and events

**Tests:**
- Basic WebSocket message flow
- Tool execution events through WebSocket
- Error handling via WebSocket
- Message ordering validation
- Conversation persistence to MongoDB

**Run:** `python tests/test_websocket_interaction.py`

## Running All Tests

```bash
# Run individual tests
cd /workspace
python tests/test_tool_calling.py
python tests/test_agent_conversation.py
python tests/test_websocket_interaction.py

# Or run test runner (if created)
python tests/run_all_tests.py
```

## Common Issues and Solutions

### Issue 1: Import Errors

**Symptom:** `ModuleNotFoundError: No module named 'agent'`

**Solutions:**
1. Check PYTHONPATH includes workspace root
2. Use relative imports in legacy code folder
3. Verify `__init__.py` files exist in agent/ directory

### Issue 2: Tool Not Calling

**Symptom:** Agent responds without calling tools, even when needed

**Debug Steps:**
1. Run `test_tool_calling.py` to verify tool binding
2. Check LLM response for `tool_calls` attribute
3. Verify system prompt instructs tool usage
4. Check if tools are properly registered in tools list

### Issue 3: WebSocket Not Streaming

**Symptom:** No token events, or messages arrive all at once

**Debug Steps:**
1. Run `test_websocket_interaction.py`
2. Check if callback_handler is passed to LLM
3. Verify streaming=True in ChatGroq initialization
4. Check WebSocket connection is open

### Issue 4: Context Not Preserved

**Symptom:** Multi-turn conversations don't remember context

**Debug Steps:**
1. Check conversation_memory is loading from MongoDB
2. Verify conversation_id is consistent across turns
3. Check Redis connection for caching
4. Run multi-turn test in `test_agent_conversation.py`

## Debugging Workflow

1. **Start with Tool Tests**
   ```bash
   python tests/test_tool_calling.py
   ```
   This verifies basic tool functionality.

2. **Test Agent Logic**
   ```bash
   python tests/test_agent_conversation.py
   ```
   This tests the agent's decision-making and tool orchestration.

3. **Test WebSocket Integration**
   ```bash
   python tests/test_websocket_interaction.py
   ```
   This tests the full streaming flow.

4. **Check Logs**
   - Current version: Check log output
   - Legacy version: Check print statements

5. **Compare with Legacy**
   - Run same query in both versions
   - Compare tool calls made
   - Compare response quality

## Environment Setup

Ensure these are set in `.env`:

```bash
# Required
GROQ_API_KEY=your_key
GROQ_MODEL=moonshotai/kimi-k2-instruct-0905
MONGODB_URI=your_mongodb_uri
QDRANT_URL=http://qdrant:6333

# Optional debugging
LOG_LEVEL=DEBUG
STREAM_TOOL_OUTPUTS=true
```

## Next Steps

1. Run all three test files
2. Identify which specific test fails
3. Use that test's output to narrow down the issue
4. Compare with legacy code behavior
5. Fix the specific component that's broken

## Git Branch Comparison

To compare with older working versions:

```bash
# List recent branches
git branch -a | grep dev

# Checkout an older dev branch to compare
git checkout <older-dev-branch>

# Compare specific files
git diff cursor/debug-agent-issues-by-testing-tool-calling-and-interactions-6b13 <older-branch> -- agent/agent.py
```
