#!/usr/bin/env python3
"""
Simple test to check if agent responds at all.
This is the most basic test - does the agent yield anything?
"""
import asyncio
import sys
sys.path.insert(0, '/workspace')

async def test_agent():
    from agent.agent import MongoDBAgent
    from dotenv import load_dotenv
    
    load_dotenv()
    
    print("\n" + "="*70)
    print("SIMPLE AGENT TEST")
    print("="*70)
    
    print("\n1. Creating agent...")
    agent = MongoDBAgent(max_steps=3)
    
    print("2. Connecting...")
    await agent.connect()
    print("   ✅ Connected")
    
    query = "How many work items are there?"
    print(f"\n3. Query: '{query}'")
    print("4. Running agent...")
    
    response_received = False
    chunks = []
    
    try:
        async for chunk in agent.run_streaming(query=query, conversation_id="debug_test"):
            if chunk:
                response_received = True
                chunks.append(chunk)
                print(f"   📦 Chunk received: {chunk[:80]}{'...' if len(chunk) > 80 else ''}")
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*70)
    print("RESULT")
    print("="*70)
    if response_received:
        total_length = len(''.join(chunks))
        print(f"✅ SUCCESS!")
        print(f"   - Chunks received: {len(chunks)}")
        print(f"   - Total length: {total_length} characters")
        print(f"\nFirst 200 chars:")
        print(f"   {(''.join(chunks))[:200]}")
    else:
        print(f"❌ FAILURE!")
        print(f"   - NO response received from agent")
        print(f"   - Agent yielded nothing")
        print(f"\nThis means:")
        print(f"   1. Agent loop may not be executing")
        print(f"   2. Agent hits exception before yielding")
        print(f"   3. LLM returns empty content")
        print(f"   4. Agent never reaches finalization")
    print("="*70 + "\n")
    
    await agent.disconnect()
    
    return response_received

if __name__ == "__main__":
    try:
        success = asyncio.run(test_agent())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
