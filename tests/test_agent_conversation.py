"""
Test file for debugging agent conversation flow.

This tests the full agent conversation loop including:
- Message handling
- Tool calling orchestration  
- Response generation
- Memory/context management
"""
import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

async def test_agent_initialization():
    """Test if the agent can be initialized"""
    print("\n=== Testing Agent Initialization ===")
    try:
        from agent.agent import MongoDBAgent
        
        print("Creating MongoDBAgent instance...")
        agent = MongoDBAgent(max_steps=5)
        print("✅ Agent instance created")
        
        print("Connecting agent...")
        await agent.connect()
        print("✅ Agent connected successfully")
        
        await agent.disconnect()
        print("✅ Agent disconnected")
        return True, agent
    except Exception as e:
        print(f"❌ Agent initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False, None

async def test_simple_query_no_tools():
    """Test agent with a query that doesn't require tools"""
    print("\n=== Testing Simple Query (No Tools Required) ===")
    try:
        from agent.agent import MongoDBAgent
        
        agent = MongoDBAgent(max_steps=3)
        await agent.connect()
        
        query = "Hello, can you help me?"
        print(f"Query: '{query}'")
        print("Streaming response...")
        
        full_response = ""
        async for chunk in agent.run_streaming(query=query, conversation_id="test_conv_1"):
            if chunk:
                full_response += str(chunk)
                print(".", end="", flush=True)
        
        print(f"\n✅ Got response ({len(full_response)} chars)")
        print(f"Response: {full_response[:200]}...")
        
        await agent.disconnect()
        return True
    except Exception as e:
        print(f"❌ Simple query test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_query_with_mongo_tool():
    """Test agent with a query that requires mongo_query tool"""
    print("\n=== Testing Query Requiring mongo_query Tool ===")
    try:
        from agent.agent import MongoDBAgent
        
        agent = MongoDBAgent(max_steps=5)
        await agent.connect()
        
        query = "How many work items are there in total?"
        print(f"Query: '{query}'")
        print("Expected: Agent should call mongo_query tool")
        print("Streaming response...")
        
        full_response = ""
        async for chunk in agent.run_streaming(query=query, conversation_id="test_conv_2"):
            if chunk:
                full_response += str(chunk)
                print(".", end="", flush=True)
        
        print(f"\n✅ Got response ({len(full_response)} chars)")
        print(f"Response: {full_response[:300]}...")
        
        # Check if response contains expected elements
        has_data = any(keyword in full_response.lower() for keyword in ['work item', 'total', 'count', 'found'])
        if has_data:
            print("✅ Response contains relevant data")
        else:
            print("⚠️ Response may not contain expected data")
        
        await agent.disconnect()
        return True
    except Exception as e:
        print(f"❌ Mongo tool query test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_query_with_rag_tool():
    """Test agent with a query that requires rag_search tool"""
    print("\n=== Testing Query Requiring rag_search Tool ===")
    try:
        from agent.agent import MongoDBAgent
        from qdrant.initializer import RAGTool
        
        # Initialize RAG first
        await RAGTool.initialize()
        
        agent = MongoDBAgent(max_steps=5)
        await agent.connect()
        
        query = "Find pages about authentication"
        print(f"Query: '{query}'")
        print("Expected: Agent should call rag_search tool")
        print("Streaming response...")
        
        full_response = ""
        async for chunk in agent.run_streaming(query=query, conversation_id="test_conv_3"):
            if chunk:
                full_response += str(chunk)
                print(".", end="", flush=True)
        
        print(f"\n✅ Got response ({len(full_response)} chars)")
        print(f"Response: {full_response[:300]}...")
        
        await agent.disconnect()
        return True
    except Exception as e:
        print(f"❌ RAG tool query test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_multi_turn_conversation():
    """Test multi-turn conversation with context"""
    print("\n=== Testing Multi-Turn Conversation ===")
    try:
        from agent.agent import MongoDBAgent
        
        agent = MongoDBAgent(max_steps=5)
        await agent.connect()
        
        conversation_id = f"test_conv_{int(datetime.now().timestamp())}"
        
        # Turn 1
        query1 = "Count all work items"
        print(f"\nTurn 1: '{query1}'")
        response1 = ""
        async for chunk in agent.run_streaming(query=query1, conversation_id=conversation_id):
            if chunk:
                response1 += str(chunk)
        print(f"Response 1: {response1[:150]}...")
        
        # Turn 2 - should use context from turn 1
        query2 = "How many are high priority?"
        print(f"\nTurn 2: '{query2}'")
        print("Expected: Should understand context from previous turn")
        response2 = ""
        async for chunk in agent.run_streaming(query=query2, conversation_id=conversation_id):
            if chunk:
                response2 += str(chunk)
        print(f"Response 2: {response2[:150]}...")
        
        print("\n✅ Multi-turn conversation completed")
        
        await agent.disconnect()
        return True
    except Exception as e:
        print(f"❌ Multi-turn conversation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_parallel_tool_execution():
    """Test if agent can execute multiple independent tools in parallel"""
    print("\n=== Testing Parallel Tool Execution ===")
    try:
        from agent.agent import MongoDBAgent
        from qdrant.initializer import RAGTool
        
        await RAGTool.initialize()
        
        agent = MongoDBAgent(max_steps=5, enable_parallel_tools=True)
        await agent.connect()
        
        # Query that might trigger multiple tools
        query = "Count work items and also search for documentation about testing"
        print(f"Query: '{query}'")
        print("Expected: Might execute mongo_query and rag_search in parallel")
        
        start_time = asyncio.get_event_loop().time()
        response = ""
        async for chunk in agent.run_streaming(query=query, conversation_id="test_parallel"):
            if chunk:
                response += str(chunk)
        elapsed = asyncio.get_event_loop().time() - start_time
        
        print(f"\n✅ Completed in {elapsed:.2f}s")
        print(f"Response: {response[:300]}...")
        
        await agent.disconnect()
        return True
    except Exception as e:
        print(f"❌ Parallel execution test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_error_handling():
    """Test agent's error handling capabilities"""
    print("\n=== Testing Error Handling ===")
    try:
        from agent.agent import MongoDBAgent
        
        agent = MongoDBAgent(max_steps=3)
        await agent.connect()
        
        # Query with potentially invalid parameters
        query = "Show me work items with invalid_field = true"
        print(f"Query: '{query}'")
        print("Expected: Should handle gracefully")
        
        response = ""
        async for chunk in agent.run_streaming(query=query, conversation_id="test_error"):
            if chunk:
                response += str(chunk)
        
        print(f"\n✅ Got response (no crash): {response[:200]}...")
        
        await agent.disconnect()
        return True
    except Exception as e:
        print(f"❌ Error handling test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all agent conversation tests"""
    print("=" * 60)
    print("AGENT CONVERSATION FLOW DEBUG TEST SUITE")
    print("=" * 60)
    
    from dotenv import load_dotenv
    load_dotenv()
    
    results = {}
    
    # Test 1: Initialization
    init_success, agent = await test_agent_initialization()
    results['initialization'] = init_success
    
    if not init_success:
        print("\n❌ Agent initialization failed, skipping other tests")
        return False
    
    # Test 2-7: Various conversation scenarios
    results['simple_query'] = await test_simple_query_no_tools()
    results['mongo_tool'] = await test_query_with_mongo_tool()
    results['rag_tool'] = await test_query_with_rag_tool()
    results['multi_turn'] = await test_multi_turn_conversation()
    results['parallel_tools'] = await test_parallel_tool_execution()
    results['error_handling'] = await test_error_handling()
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name:20s}: {status}")
    
    total = len(results)
    passed = sum(results.values())
    print(f"\nTotal: {passed}/{total} tests passed")
    
    return passed == total

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
