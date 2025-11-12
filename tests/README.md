# Agent Debug Test Suite

This directory contains comprehensive tests to debug and verify the agent's functionality end-to-end.

## Quick Start

```bash
# Run all tests
cd /workspace
python tests/run_all_tests.py

# Or run individual test suites
python tests/test_tool_calling.py          # Test tool execution
python tests/test_agent_conversation.py    # Test agent logic
python tests/test_websocket_interaction.py # Test WebSocket flow
```

## Test Files

### 1. test_tool_calling.py
Tests the fundamental tool infrastructure:
- ✅ Tool imports (current and legacy paths)
- ✅ Direct tool execution (mongo_query, rag_search)
- ✅ Tool binding to LLM
- ✅ Tool execution from LLM responses

### 2. test_agent_conversation.py
Tests the agent's conversation capabilities:
- ✅ Agent initialization and connection
- ✅ Simple queries without tools
- ✅ Queries requiring mongo_query tool
- ✅ Queries requiring rag_search tool
- ✅ Multi-turn conversations with context
- ✅ Parallel tool execution
- ✅ Error handling and recovery

### 3. test_websocket_interaction.py
Tests WebSocket streaming and events:
- ✅ Basic message flow (tokens, llm_start, llm_end)
- ✅ Tool execution events
- ✅ Error handling through WebSocket
- ✅ Message ordering validation
- ✅ Conversation persistence to MongoDB

### 4. run_all_tests.py
Master test runner that executes all tests and provides a comprehensive report.

## Understanding Test Output

### Success Indicators
- `✅` - Test passed successfully
- Green dots (`.`) - Streaming tokens being received
- Tool names with checkmarks - Tools executing properly

### Failure Indicators
- `❌` - Test failed
- Red error messages with stack traces
- `⚠️` - Warning or unexpected behavior

## Common Test Failures

### "ModuleNotFoundError: No module named 'agent'"
**Cause:** Import path issues between current and legacy structure.

**Fix:** Tests automatically try both import paths. If both fail, check:
1. PYTHONPATH includes workspace root
2. `__init__.py` exists in agent/ directory
3. Run from workspace root: `python tests/...`

### "Connection refused" or "MongoDB/Qdrant not available"
**Cause:** Required services not running.

**Fix:**
```bash
# Start services with docker-compose
docker-compose up -d

# Or check if services are running
docker ps
```

### "Tool not called when expected"
**Cause:** LLM not recognizing when to use tools.

**Debug:**
1. Check tool binding succeeded (test_tool_calling.py)
2. Verify system prompt includes tool instructions
3. Check LLM response has `tool_calls` attribute
4. Review agent logs for reasoning

### "No tokens received" or "Response timeout"
**Cause:** Streaming not working or LLM not responding.

**Debug:**
1. Verify GROQ_API_KEY is valid
2. Check network connectivity
3. Review LLM initialization parameters
4. Check if streaming=True is set

## Interpreting Results

### All Tests Pass (100%)
🎉 Agent is working correctly! All components functional.

### Partial Pass (50-90%)
⚠️ Some components working, others need attention.
- Check which specific tests failed
- Review their output for error details
- See DEBUGGING_GUIDE.md for solutions

### All Tests Fail (0%)
❌ Major system issues. Check:
1. Environment variables in .env
2. Service connectivity (MongoDB, Qdrant, Groq)
3. Dependencies installed correctly
4. Python version compatibility

## Adding New Tests

To add a new test file:

1. Create `test_your_feature.py` in this directory
2. Follow the pattern:
```python
async def test_something():
    """Test description"""
    print("\n=== Testing Something ===")
    try:
        # Your test code
        return True
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

async def main():
    results = {}
    results['something'] = await test_something()
    # ... more tests
    # Print summary
    return all(results.values())

if __name__ == "__main__":
    asyncio.run(main())
```

3. Add to run_all_tests.py test_suites list

## Environment Variables

Required in `.env`:
```bash
GROQ_API_KEY=your_key_here
GROQ_MODEL=moonshotai/kimi-k2-instruct-0905
MONGODB_URI=mongodb://...
QDRANT_URL=http://qdrant:6333
```

Optional for debugging:
```bash
LOG_LEVEL=DEBUG
STREAM_TOOL_OUTPUTS=true
```

## Troubleshooting

### Tests hang or timeout
- Check if services are responsive
- Verify network connectivity
- Reduce max_steps in agent initialization
- Check for infinite loops in code

### Inconsistent results
- Clear Redis cache: `redis-cli FLUSHDB`
- Restart services
- Check for race conditions in async code
- Verify conversation IDs are unique

### Memory issues
- Reduce batch sizes
- Limit conversation history
- Check for memory leaks in long-running tests

## CI/CD Integration

To run in CI pipeline:
```bash
# Run with exit code for CI
python tests/run_all_tests.py
EXIT_CODE=$?

# Or with pytest (if using pytest)
pytest tests/ -v

exit $EXIT_CODE
```

## Further Reading

- [DEBUGGING_GUIDE.md](DEBUGGING_GUIDE.md) - Detailed debugging information
- [../agent/agent.py](../agent/agent.py) - Current agent implementation
- [../legacy code/agent.py](../legacy%20code/agent.py) - Working legacy version

## Support

If tests fail and you can't resolve:
1. Review DEBUGGING_GUIDE.md
2. Check agent logs for errors
3. Compare with legacy code behavior
4. Create detailed issue with test output
