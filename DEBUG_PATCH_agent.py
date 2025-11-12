"""
Debug patch to add to agent/agent.py to identify why no response.

Add these lines at the specified locations in agent/agent.py
"""

# ============================================================================
# PATCH #1: At line 563 (start of while loop)
# ============================================================================
"""
while steps < self.max_steps:
    print(f"🔄 DEBUG: Step {steps}/{self.max_steps} starting")  # ← ADD THIS
    # Choose tools for this query iteration
"""

# ============================================================================
# PATCH #2: At line 693 (after LLM response)
# ============================================================================
"""
last_response = response

print(f"🤖 DEBUG: LLM responded")  # ← ADD THIS
print(f"   - Has content: {bool(getattr(response, 'content', None))}")  # ← ADD THIS
print(f"   - Content length: {len(getattr(response, 'content', '') or '')}")  # ← ADD THIS
print(f"   - Has tool_calls: {bool(getattr(response, 'tool_calls', None))}")  # ← ADD THIS
if getattr(response, 'tool_calls', None):
    print(f"   - Tool calls: {[tc.get('name') for tc in response.tool_calls]}")  # ← ADD THIS

# Only persist assistant messages when there are NO tool calls (final response)
"""

# ============================================================================
# PATCH #3: At line 704 (before yield)
# ============================================================================
"""
try:
    await save_assistant_message(conversation_id, getattr(response, "content", "") or "")
except Exception as e:
    print(f"❌ DEBUG: Failed to save: {e}")  # ← ADD THIS (replace logger.error)
    logger.error(f"Failed to save assistant message: {e}")

print(f"✅ DEBUG: About to yield content ({len(response.content)} chars)")  # ← ADD THIS
yield response.content
"""

# ============================================================================
# PATCH #4: At line 778 (after tool execution)
# ============================================================================
"""
steps += 1

print(f"🔧 DEBUG: Tools executed, did_any_tool={did_any_tool}")  # ← ADD THIS

# After executing any tools, force the next LLM turn to synthesize
if did_any_tool:
    need_finalization = True
    print(f"✅ DEBUG: Setting need_finalization=True")  # ← ADD THIS
"""

# ============================================================================
# PATCH #5: At line 784 (if step cap reached)
# ============================================================================
"""
# Step cap reached; send best available response
print(f"⚠️  DEBUG: Reached max steps ({steps}/{self.max_steps})")  # ← ADD THIS
if last_response is not None:
    print(f"   - last_response.content: {last_response.content[:100] if last_response.content else 'EMPTY'}")  # ← ADD THIS
"""

# ============================================================================
# PATCH #6: At line 800 (exception handler)
# ============================================================================
"""
except Exception as e:
    print(f"❌ DEBUG: Exception in run_streaming: {e}")  # ← ADD THIS
    import traceback
    traceback.print_exc()  # ← ADD THIS
    yield f"Error running streaming agent: {str(e)}"
"""

# ============================================================================
# PATCH #7: At line 653 (finalization check)
# ============================================================================
"""
# Determine if this is a finalization turn BEFORE calling LLM
is_finalizing = need_finalization  # ✅ Save the state BEFORE modifying it

print(f"🎯 DEBUG: is_finalizing={is_finalizing}, need_finalization={need_finalization}")  # ← ADD THIS

if need_finalization:
    print(f"📝 DEBUG: Adding finalization instructions")  # ← ADD THIS
    finalization_instructions = SystemMessage(content=(
"""

print("""
============================================================================
HOW TO APPLY THIS DEBUG PATCH
============================================================================

Copy each PATCH section and add the marked lines (with ← ADD THIS) to your
agent/agent.py file at the specified line numbers.

After applying, run your agent and you'll see output like:

  🔄 DEBUG: Step 0/8 starting
  🤖 DEBUG: LLM responded
     - Has content: False
     - Content length: 0
     - Has tool_calls: True
     - Tool calls: ['mongo_query']
  🔧 DEBUG: Tools executed, did_any_tool=True
  ✅ DEBUG: Setting need_finalization=True
  🔄 DEBUG: Step 1/8 starting
  🎯 DEBUG: is_finalizing=True, need_finalization=True
  📝 DEBUG: Adding finalization instructions
  🤖 DEBUG: LLM responded
     - Has content: True
     - Content length: 234
     - Has tool_calls: False
  ✅ DEBUG: About to yield content (234 chars)

This will show you EXACTLY where the flow breaks!

============================================================================
ALTERNATIVE: Quick Test Script
============================================================================

Or create a standalone test script:
""")

# Test script content
test_script = '''
import asyncio
import sys
sys.path.insert(0, '/workspace')

async def test_agent():
    from agent.agent import MongoDBAgent
    from dotenv import load_dotenv
    
    load_dotenv()
    
    agent = MongoDBAgent(max_steps=3)
    await agent.connect()
    
    print("\\n" + "="*70)
    print("TESTING: Agent Response")
    print("="*70 + "\\n")
    
    query = "How many work items are there?"
    print(f"Query: {query}\\n")
    
    response_received = False
    chunks = []
    
    async for chunk in agent.run_streaming(query=query, conversation_id="debug_test"):
        if chunk:
            response_received = True
            chunks.append(chunk)
            print(f"Chunk: {chunk[:100]}")
    
    print(f"\\n" + "="*70)
    if response_received:
        print(f"✅ SUCCESS: Received {len(chunks)} chunks")
        print(f"Total response: {len(''.join(chunks))} chars")
    else:
        print(f"❌ FAIL: No response received")
    print("="*70)
    
    await agent.disconnect()

asyncio.run(test_agent())
'''

print("Save this as test_simple.py and run: python3 test_simple.py")
print(test_script)
