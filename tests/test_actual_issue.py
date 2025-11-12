"""
Test to identify why no response is reaching the frontend.

This focuses on the ACTUAL issue: agent not responding at all.
"""
import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

async def test_agent_returns_anything():
    """Test if agent returns ANYTHING at all"""
    print("\n=== TEST 1: Does agent return anything? ===")
    try:
        from agent.agent import MongoDBAgent
        from dotenv import load_dotenv
        load_dotenv()
        
        agent = MongoDBAgent(max_steps=3)
        await agent.connect()
        
        query = "Hello"
        print(f"Query: '{query}'")
        print("Checking if we get ANY response...")
        
        response_received = False
        chunk_count = 0
        
        async for chunk in agent.run_streaming(query=query, conversation_id="test_any_response"):
            chunk_count += 1
            if chunk:
                response_received = True
                print(f"\n✅ Got chunk #{chunk_count}: {chunk[:100]}")
        
        await agent.disconnect()
        
        if response_received:
            print(f"\n✅ PASS: Agent returned {chunk_count} chunks")
            return True
        else:
            print(f"\n❌ FAIL: Agent returned NOTHING (0 chunks)")
            print("This is the root issue - agent.run_streaming yields nothing")
            return False
            
    except Exception as e:
        print(f"\n❌ FAIL: Exception occurred: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_llm_is_responding():
    """Test if LLM itself is responding"""
    print("\n=== TEST 2: Is LLM responding? ===")
    try:
        from langchain_groq import ChatGroq
        from langchain_core.messages import HumanMessage
        from dotenv import load_dotenv
        import os
        
        load_dotenv()
        
        llm = ChatGroq(
            model=os.getenv("GROQ_MODEL", "moonshotai/kimi-k2-instruct-0905"),
            temperature=0.1,
            streaming=True,
        )
        
        print("Testing direct LLM call...")
        response = await llm.ainvoke([HumanMessage(content="Say 'Hello'")])
        
        if response and response.content:
            print(f"✅ PASS: LLM responded with: {response.content[:100]}")
            return True
        else:
            print(f"❌ FAIL: LLM returned empty response")
            return False
            
    except Exception as e:
        print(f"❌ FAIL: LLM error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_agent_with_websocket_mock():
    """Test agent with WebSocket to see if tokens are sent"""
    print("\n=== TEST 3: Are tokens sent via WebSocket? ===")
    try:
        from agent.agent import MongoDBAgent
        from dotenv import load_dotenv
        load_dotenv()
        
        # Mock WebSocket
        class MockWS:
            def __init__(self):
                self.messages = []
            
            async def send_json(self, data):
                self.messages.append(data)
                msg_type = data.get("type")
                if msg_type == "token":
                    print(".", end="", flush=True)
                elif msg_type in ["llm_start", "llm_end", "agent_action"]:
                    print(f"\n📨 {msg_type}", end="", flush=True)
        
        mock_ws = MockWS()
        agent = MongoDBAgent(max_steps=3)
        await agent.connect()
        
        query = "Count work items"
        print(f"Query: '{query}'")
        print("Monitoring WebSocket messages...", flush=True)
        
        chunk_count = 0
        async for chunk in agent.run_streaming(
            query=query, 
            websocket=mock_ws,
            conversation_id="test_ws_tokens"
        ):
            if chunk:
                chunk_count += 1
        
        await agent.disconnect()
        
        # Analyze what was sent
        token_count = sum(1 for m in mock_ws.messages if m.get("type") == "token")
        action_count = sum(1 for m in mock_ws.messages if m.get("type") == "agent_action")
        llm_starts = sum(1 for m in mock_ws.messages if m.get("type") == "llm_start")
        
        print(f"\n\nWebSocket Statistics:")
        print(f"  Total messages: {len(mock_ws.messages)}")
        print(f"  Tokens sent: {token_count}")
        print(f"  Actions sent: {action_count}")
        print(f"  LLM starts: {llm_starts}")
        print(f"  Generator chunks: {chunk_count}")
        
        if token_count > 0:
            print(f"\n✅ PASS: Tokens are being sent via WebSocket")
            return True
        else:
            print(f"\n❌ FAIL: NO tokens sent via WebSocket")
            print("Issue: Streaming callback not working")
            return False
            
    except Exception as e:
        print(f"\n❌ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_agent_reasoning_loop():
    """Test if agent enters the reasoning loop"""
    print("\n=== TEST 4: Does agent enter reasoning loop? ===")
    try:
        from agent.agent import MongoDBAgent
        from dotenv import load_dotenv
        load_dotenv()
        
        # Patch to track loop entry
        agent = MongoDBAgent(max_steps=2)
        await agent.connect()
        
        query = "Hello"
        print(f"Query: '{query}'")
        
        entered_loop = False
        try:
            async for chunk in agent.run_streaming(query=query, conversation_id="test_loop"):
                entered_loop = True
                if chunk:
                    print(f"\n✅ Loop executing, got: {chunk[:50]}")
                    break
        except Exception as e:
            print(f"\n❌ Exception in loop: {e}")
            import traceback
            traceback.print_exc()
        
        await agent.disconnect()
        
        if entered_loop:
            print(f"\n✅ PASS: Agent enters reasoning loop")
            return True
        else:
            print(f"\n❌ FAIL: Agent never enters reasoning loop")
            return False
            
    except Exception as e:
        print(f"\n❌ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_connection_issues():
    """Test if there are connection issues"""
    print("\n=== TEST 5: Connection issues? ===")
    
    results = {}
    
    # Test MongoDB
    try:
        from mongo.constants import mongodb_tools
        await mongodb_tools.connect()
        print("✅ MongoDB: Connected")
        results['mongodb'] = True
        await mongodb_tools.disconnect()
    except Exception as e:
        print(f"❌ MongoDB: Failed - {e}")
        results['mongodb'] = False
    
    # Test Qdrant
    try:
        from qdrant.initializer import RAGTool
        await RAGTool.initialize()
        print("✅ Qdrant: Initialized")
        results['qdrant'] = True
    except Exception as e:
        print(f"❌ Qdrant: Failed - {e}")
        results['qdrant'] = False
    
    # Test Groq API
    try:
        from langchain_groq import ChatGroq
        from langchain_core.messages import HumanMessage
        import os
        llm = ChatGroq(model=os.getenv("GROQ_MODEL"), temperature=0.1)
        response = await llm.ainvoke([HumanMessage(content="test")])
        print("✅ Groq API: Working")
        results['groq'] = True
    except Exception as e:
        print(f"❌ Groq API: Failed - {e}")
        results['groq'] = False
    
    all_connected = all(results.values())
    if all_connected:
        print(f"\n✅ PASS: All services connected")
    else:
        print(f"\n❌ FAIL: Some services not available")
        failed = [k for k, v in results.items() if not v]
        print(f"Failed: {', '.join(failed)}")
    
    return all_connected

async def main():
    """Run focused debugging tests"""
    print("=" * 70)
    print("DEBUGGING: WHY NO RESPONSE IN FRONTEND")
    print("=" * 70)
    print("\nThis will identify the exact point of failure...\n")
    
    from dotenv import load_dotenv
    load_dotenv()
    
    # Run tests in order of debugging priority
    results = {}
    
    # First: Check connections
    print("\n" + "=" * 70)
    results['connections'] = await test_connection_issues()
    
    if not results['connections']:
        print("\n⚠️ Connection issues detected. Fix these first!")
        return False
    
    # Second: Check if LLM works at all
    print("\n" + "=" * 70)
    results['llm_basic'] = await test_llm_is_responding()
    
    if not results['llm_basic']:
        print("\n⚠️ LLM not responding. Check API key and model name!")
        return False
    
    # Third: Check if agent returns anything
    print("\n" + "=" * 70)
    results['agent_returns'] = await test_agent_returns_anything()
    
    # Fourth: Check reasoning loop
    print("\n" + "=" * 70)
    results['reasoning_loop'] = await test_agent_reasoning_loop()
    
    # Fifth: Check WebSocket tokens
    print("\n" + "=" * 70)
    results['websocket_tokens'] = await test_agent_with_websocket_mock()
    
    # Analysis
    print("\n" + "=" * 70)
    print("ROOT CAUSE ANALYSIS")
    print("=" * 70)
    
    if not results['agent_returns']:
        print("\n🔴 ROOT CAUSE: Agent's run_streaming() returns NOTHING")
        print("\nPossible reasons:")
        print("  1. Agent loop never executes (check max_steps)")
        print("  2. Agent hits exception and fails silently")
        print("  3. Agent loop executes but never yields")
        print("  4. LLM response is empty or malformed")
        print("\nNext steps:")
        print("  - Add print() statements in agent.py run_streaming()")
        print("  - Check line 704: yield response.content")
        print("  - Check if response.content is empty")
        
    elif not results['websocket_tokens']:
        print("\n🔴 ROOT CAUSE: Agent returns data but doesn't stream tokens")
        print("\nPossible reasons:")
        print("  1. Callback handler not properly attached")
        print("  2. should_stream flag is False")
        print("  3. Callback handler methods not being called")
        print("\nNext steps:")
        print("  - Check line 680: should_stream = is_finalizing")
        print("  - Check line 684: config={\"callbacks\": [callback_handler]}")
        print("  - Add print() in PhoenixCallbackHandler.on_llm_new_token()")
        
    else:
        print("\n🟢 Agent appears to be working in isolation")
        print("\nIf still not working in production, check:")
        print("  1. Frontend WebSocket connection")
        print("  2. WebSocket message handling in frontend")
        print("  3. CORS settings")
        print("  4. Network/firewall issues")
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name:20s}: {status}")
    
    return all(results.values())

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
